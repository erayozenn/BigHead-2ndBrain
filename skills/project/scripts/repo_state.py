#!/usr/bin/env python3
"""Report a repo's state for a project hub. Read-only. Standard library only.

Usage:
  repo_state.py --repo <dir> [--sha <last seen sha>] [--commits <n>]

Prints one JSON object:
  head        current short HEAD, or null if the repo has no commits
  seen_state  none (no --sha) | no_commits | ancestor | not_ancestor | unknown (the sha does not
              name exactly one commit in this repo)
  count       commits in <sha>..<head>, only when seen_state is ancestor
  commits     up to n "<short sha> <subject>" strings of that range, newest first, only with --commits
  truncated   true if commits holds fewer entries than count
  dirty       true if the working tree has uncommitted changes, null if that could not be read

The range is read against the HEAD captured first, so a commit landing during the run cannot be
counted as seen. Exit codes: 0 reported, 1 not a readable repo or git failed, 2 bad arguments.

Only the fixed git commands below ever run, and the sha is checked first, so no option can reach
git. This replaces pre-approving `git -C * status *`, which also matches
`git -C . -c core.fsmonitor=<cmd> status`. fsmonitor and signature checks are turned off, and GIT_*
environment variables are ignored, so --repo always decides which repo is read. A repo's own clean
filter can still run during `git status`, so use this only on repos the user trusts.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

SHA_RE = re.compile(r"[0-9a-fA-F]{7,64}")
GIT_CONFIG = ["-c", "core.fsmonitor=false", "-c", "log.showSignature=false",
              "-c", "i18n.logOutputEncoding=UTF-8"]


def commit_limit(value: str) -> int:
    limit = int(value)
    if limit < 1:
        raise ValueError
    return limit


def sha_value(value: str) -> str:
    if not SHA_RE.fullmatch(value):
        raise ValueError
    return value.lower()


def git(repo: str, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return subprocess.run(["git", *GIT_CONFIG, "-C", repo, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=60, env=env)


def fail(message: str) -> None:
    one_line = message.replace("\r", "\\r").replace("\n", "\\n")
    print(f"repo_state: {one_line}", file=sys.stderr)
    sys.exit(1)


def resolve_commit(repo: str, sha: str) -> str | None:
    """The one commit this sha names; a branch that happens to share the name does not count."""
    found = git(repo, "rev-parse", f"--disambiguate={sha}")
    objects = found.stdout.split()
    if found.returncode != 0 or len(objects) != 1:
        return None
    kind = git(repo, "cat-file", "-t", objects[0])
    return objects[0] if kind.returncode == 0 and kind.stdout.strip() == "commit" else None


def list_commits(repo: str, commit_range: str, limit: int) -> list[str]:
    # NUL-separated, because a subject can hold characters that count as line breaks.
    listed = git(repo, "log", "--format=%h %s%x00", f"--max-count={limit}", commit_range)
    if listed.returncode != 0:
        fail(f"could not list commits: {listed.stderr.strip()}")
    return [entry.lstrip("\n") for entry in listed.stdout.split("\0") if entry.strip("\n")]


def report(repo: str, sha: str | None, commits: int | None) -> dict:
    state = {"head": None, "seen_state": "none", "count": None, "commits": None,
             "truncated": False, "dirty": None}
    if git(repo, "rev-parse", "--git-dir").returncode != 0:
        fail(f"not a git repository: {repo}")
    status = git(repo, "status", "--porcelain", "--untracked-files=normal", "--ignore-submodules=all")
    if status.returncode == 0:
        state["dirty"] = bool(status.stdout.strip())

    head = git(repo, "rev-parse", "--verify", "--quiet", "HEAD")
    if head.returncode != 0:
        state["seen_state"] = "no_commits" if sha else "none"
        return state
    head_sha = head.stdout.strip()
    state["head"] = git(repo, "rev-parse", "--short", head_sha).stdout.strip()
    if not sha:
        return state

    seen = resolve_commit(repo, sha)
    if seen is None:
        state["seen_state"] = "unknown"
        return state
    ancestor = git(repo, "merge-base", "--is-ancestor", seen, head_sha).returncode
    if ancestor != 0:
        state["seen_state"] = "not_ancestor" if ancestor == 1 else "unknown"
        return state
    state["seen_state"] = "ancestor"
    counted = git(repo, "rev-list", "--count", f"{seen}..{head_sha}")
    if counted.returncode != 0:
        fail(f"could not count commits: {counted.stderr.strip()}")
    state["count"] = int(counted.stdout.strip())
    if commits is not None:
        limit = min(commits, state["count"])
        state["commits"] = list_commits(repo, f"{seen}..{head_sha}", limit) if limit else []
        state["truncated"] = len(state["commits"]) < state["count"]
    return state


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--sha", type=sha_value)
    parser.add_argument("--commits", type=commit_limit)
    args = parser.parse_args()
    if not os.path.isdir(args.repo):
        fail(f"no such folder: {args.repo}")
    try:
        state = report(args.repo, args.sha, args.commits)
    except FileNotFoundError:
        fail("git was not found")
    except subprocess.TimeoutExpired:
        fail("git timed out")
    print(json.dumps(state, ensure_ascii=False))


if __name__ == "__main__":
    main()
