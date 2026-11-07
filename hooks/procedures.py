#!/usr/bin/env python3
"""PreToolUse procedure reminder for BigHead 2ndBrain project sessions.

Before `git push`, `gh pr create` or `gh pr merge` in a session opened outside the vault whose
folder matches exactly one project hub, the matching `### Before ...` checklist from the hub's
`<name>-overview.md` (`## Procedures`) is put in front of Claude by denying the call ONCE with
the checklist as the reason. Claude answers each item, then runs the command again, and the rerun
passes: the reminder shows once per session per kind of command.

Why deny and not additionalContext: a PreToolUse additionalContext reaches Claude next to the
tool result, i.e. after the push or PR already happened.

Checklist per kind (lib/project_pages.checklist): PR -> "Before a PR"; push -> "Before a push",
else "Before a PR"; merge -> "Before a merge", else "Before a release"; none -> no reminder.

Silent (no output, exit 0) when: the tool is not a shell, the command has none of these
commands, the session folder is inside a vault, `vault_path` is unset or not a vault, zero or
several hubs match, there is no checklist for the kind, the event has no session id, the state
folder cannot be written, or anything else goes wrong. It never blocks on its own errors.

State: one empty marker file per (session, kind) in CLAUDE_PLUGIN_DATA (else the temp folder);
markers older than 7 days are removed. This is a reminder, not a security control: a command
written another way (an alias, a script) is not seen.

Standard library only; Python 3.10+.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))

TAG = "[bighead procedures]"
SHELL_TOOLS = ("Bash", "PowerShell")
MAX_BODY = 1500   # characters of checklist text per reminder
MARKER_DAYS = 7
LABELS = {"push": "git push", "pr": "gh pr create", "merge": "gh pr merge"}

QUOTED = re.compile(r""""(?:\\.|[^"\\])*"|'[^']*'""")
SEPARATORS = re.compile(r"&&|\|\||[;|&\n]")
ENV_PREFIX = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)+")
GIT_PUSH = re.compile(r"^git(?:\s+(?:-C|-c)\s+\S+|\s+--?[\w-]+(?:=\S+)?)*\s+push(?:\s|$)")
GH_PR = re.compile(r"^gh(?:\s+(?:-R|--repo)\s+\S+)?\s+pr\s+(create|merge)(?:\s|$)")


def kinds_in(command: str) -> list[str]:
    """Kinds of reminded commands in a shell command line, in order, without repeats."""
    found = []
    for segment in SEPARATORS.split(QUOTED.sub("''", command)):
        segment = ENV_PREFIX.sub("", segment.strip())
        kind = None
        if GIT_PUSH.match(segment):
            kind = "push"
        else:
            m = GH_PR.match(segment)
            if m:
                kind = "pr" if m.group(1) == "create" else "merge"
        if kind and kind not in found:
            found.append(kind)
    return found


def state_dir() -> str:
    base = os.environ.get("CLAUDE_PLUGIN_DATA", "").strip()
    return os.path.join(base, "procedures") if base else os.path.join(tempfile.gettempdir(), "bighead-procedures")


def marker(folder: str, session: str, kind: str) -> str:
    return os.path.join(folder, hashlib.sha256(f"{session}\0{kind}".encode()).hexdigest()[:32])


def prune(folder: str) -> None:
    cutoff = time.time() - MARKER_DAYS * 86400
    try:
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
            except OSError:
                pass
    except OSError:
        pass


def build(event: dict, env: dict) -> str | None:
    """The deny reason, or None to stay silent. Writes the markers for the kinds it reminds."""
    import project_pages as pp
    import vault_locate as vl

    if event.get("hook_event_name", "PreToolUse") != "PreToolUse":
        return None
    if event.get("tool_name") not in SHELL_TOOLS:
        return None
    command = (event.get("tool_input") or {}).get("command")
    session = event.get("session_id")
    if not isinstance(command, str) or not isinstance(session, str) or not session:
        return None
    kinds = kinds_in(command)
    if not kinds:
        return None
    # The session's folder: CLAUDE_PROJECT_DIR, because the event cwd follows the shell's `cd`.
    folder = env.get("CLAUDE_PROJECT_DIR", "").strip() or event.get("cwd") or os.getcwd()
    if vl.find_vaults(folder):
        return None
    vault = vl.configured_vault(env)
    if not vault:
        return None
    matches = vl.match_hubs(folder, vault)
    if len(matches) != 1:
        return None
    name, hub = matches[0]["name"], matches[0]["path"]
    overview = os.path.join(os.path.dirname(hub), f"{name}-overview.md")
    if not os.path.isfile(overview):
        return None
    with open(overview, encoding="utf-8-sig", errors="replace") as f:
        text = f.read()

    states = state_dir()
    os.makedirs(states, exist_ok=True)
    prune(states)
    due, lists = [], []
    for kind in kinds:
        path = marker(states, session, kind)
        if os.path.exists(path):
            continue
        found = pp.checklist(text, kind)
        if not found:
            continue
        with open(path, "w", encoding="utf-8"):
            pass  # marker first: if it cannot be written we stay silent rather than deny forever
        due.append(kind)
        if found not in lists:
            lists.append(found)
    if not due:
        return None

    commands = " / ".join(f"`{LABELS[k]}`" for k in due)
    parts = [f'{TAG} Before {commands} in project "{name}", go through this checklist from '
             f'{overview.replace(os.sep, "/")} ("## Procedures"):']
    room = MAX_BODY
    for heading, body in lists:
        if len(body) > room:
            body = body[:max(room, 0)].rstrip() + "\n(... cut here; read the rest in the overview.)"
        room -= len(body)
        parts.append(f"### {heading}\n{body}")
    parts.append("Answer each item in chat: done, not needed (why), or not done. If an item is not "
                 "done, fix it or ask the user before going on. Then run the same command again; this "
                 "reminder shows once per session for this kind of command. This repo's CLAUDE.md "
                 "wins on conflict.")
    return "\n".join(parts)


def main() -> int:
    try:
        event = json.loads(sys.stdin.read())
        if not isinstance(event, dict):
            return 0
        reason = build(event, dict(os.environ))
        if reason:
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }}))
    except Exception:
        pass  # a reminder must never block work because of its own error
    return 0


if __name__ == "__main__":
    sys.exit(main())
