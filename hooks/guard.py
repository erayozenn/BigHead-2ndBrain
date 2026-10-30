#!/usr/bin/env python3
"""PreToolUse guard for Your 2ndBrain vaults.

Reads the hook event JSON on stdin and denies file-tool calls that would
break the vault's hard rules:
  - modify an existing file under raw/ (sources are immutable)
  - create a file under raw/ outside raw/web/
  - edit a note whose frontmatter says `author: me`
  - touch .obsidian/

Paths outside a vault get no decision (normal permission flow).
A vault is a folder holding raw/ and a CLAUDE.md that starts with VAULT_MARKER.

Failure mode: if the guard itself breaks while the target is inside a vault
(or cannot be determined and the cwd is a vault), it blocks with exit 2.
Outside a vault it never blocks.

Standard library only; Python 3.10+.
"""

from __future__ import annotations

import json
import os
import re
import sys

VAULT_MARKER = "# Vault Schema & Rules"
PATH_KEYS = ("file_path", "notebook_path")
FRONTMATTER_READ_BYTES = 64 * 1024
AUTHOR_ME = re.compile(r"""^author:\s*["']?me["']?\s*(#.*)?$""")


def norm(path: str) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def is_vault(folder: str) -> bool:
    if not os.path.isdir(os.path.join(folder, "raw")):
        return False
    try:
        with open(os.path.join(folder, "CLAUDE.md"), encoding="utf-8-sig", errors="replace") as f:
            return f.readline().strip().startswith(VAULT_MARKER)
    except OSError:
        return False


def find_vault(path: str) -> str | None:
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    while True:
        if is_vault(folder):
            return folder
        parent = os.path.dirname(folder)
        if parent == folder:
            return None
        folder = parent


def has_author_me(path: str) -> bool:
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        head = f.read(FRONTMATTER_READ_BYTES)
    lines = head.splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    for line in lines[1:]:
        if line.strip() == "---":
            return False
        if AUTHOR_ME.match(line.strip()):
            return True
    return False


def check(path: str) -> str | None:
    """Return a deny reason, or None for no decision."""
    target = norm(path)
    vault = find_vault(target)
    if vault is None:
        return None
    parts = os.path.relpath(target, vault).split(os.sep)
    top = parts[0]
    exists = os.path.exists(target)

    if top == ".obsidian":
        return ".obsidian/ is Obsidian's config; the vault rules forbid touching it."
    if top == "raw":
        if exists:
            return "raw/ files are immutable sources; existing files may never be modified."
        if len(parts) < 3 or parts[1] != "web":
            return "New raw files may only be added under raw/web/."
        return None
    if exists and target.endswith(".md") and has_author_me(target):
        return "This note has `author: me`; Claude never edits the user's notes. Report the problem instead."
    return None


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"[your-2ndbrain guard] {reason}",
        }
    }))


def main() -> int:
    path = None
    try:
        event = json.load(sys.stdin)
        tool_input = event.get("tool_input") or {}
        path = next((tool_input[k] for k in PATH_KEYS if tool_input.get(k)), None)
        if path is None:
            return 0
        if not os.path.isabs(path) and event.get("cwd"):
            path = os.path.join(event["cwd"], path)
        reason = check(path)
        if reason:
            deny(reason)
        return 0
    except Exception as exc:  # fail closed inside a vault only
        try:
            in_vault = find_vault(norm(path or os.getcwd())) is not None
        except Exception:
            in_vault = False
        if in_vault:
            print(f"[your-2ndbrain guard] blocked: guard error ({exc!r}); fix the hook or edit manually.",
                  file=sys.stderr)
            return 2
        print(f"[your-2ndbrain guard] warning: guard error outside a vault ({exc!r})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
