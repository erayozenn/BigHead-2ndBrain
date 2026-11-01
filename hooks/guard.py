#!/usr/bin/env python3
"""PreToolUse guard for BigHead 2ndBrain vaults.

Reads the hook event JSON on stdin and denies file-tool calls that would
break the vault's hard rules:
  - modify an existing file under raw/ (sources are immutable)
  - create a file under raw/ outside raw/web/
  - edit a note whose frontmatter says `author: me`
  - touch .obsidian/

Paths outside a vault get no decision (normal permission flow).
A vault is a folder holding raw/ and a CLAUDE.md that starts with VAULT_MARKER.
Every enclosing vault is checked, so a vault-shaped folder unpacked inside raw/
or .obsidian/ does not lift the protection of the outer vault.

Failure mode: if the guard itself breaks while the target is inside a vault
(or cannot be determined and the event's cwd or the process cwd is a vault),
it blocks with exit 2. Outside a vault it never blocks.

Standard library only; Python 3.10+.
"""

from __future__ import annotations

import json
import os
import re
import sys

VAULT_MARKER = "# Vault Schema & Rules"
PATH_KEYS = ("file_path", "notebook_path")
UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")
AUTHOR_ME = re.compile(r"""^author\s*:\s*["']?me["']?\s*(#.*)?$""")


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


def find_vaults(path: str) -> list[str]:
    """Every vault enclosing path, nearest first."""
    vaults = []
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    while True:
        if is_vault(folder):
            vaults.append(folder)
        parent = os.path.dirname(folder)
        if parent == folder:
            return vaults
        folder = parent


def has_author_me(path: str) -> bool:
    with open(path, "rb") as f:
        data = f.read()
    encoding = "utf-16" if data[:2] in UTF16_BOMS else "utf-8-sig"
    lines = data.decode(encoding, errors="replace").splitlines()
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
    vaults = find_vaults(target)
    if not vaults:
        return None
    exists = os.path.exists(target)
    for vault in vaults:
        parts = os.path.relpath(target, vault).split(os.sep)
        top = parts[0]
        if top == ".obsidian":
            return ".obsidian/ is Obsidian's config; the vault rules forbid touching it."
        if top == "raw":
            if exists:
                return "raw/ files are immutable sources; existing files may never be modified."
            if len(parts) < 3 or parts[1] != "web":
                return "New raw files may only be added under raw/web/."
    if exists and target.endswith(".md") and has_author_me(target):
        return "This note has `author: me`; Claude never edits the user's notes. Report the problem instead."
    return None


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"[bighead guard] {reason}",
        }
    }))


def in_any_vault(candidates: list) -> bool:
    for candidate in candidates:
        try:
            if isinstance(candidate, str) and candidate and find_vaults(norm(candidate)):
                return True
        except Exception:
            continue
    return False


def main() -> int:
    event = None
    paths = []
    try:
        event = json.load(sys.stdin)
        tool_input = event.get("tool_input") or {}
        paths = [tool_input[k] for k in PATH_KEYS if tool_input.get(k)]
        for path in paths:
            if not isinstance(path, str):
                raise TypeError(f"path is not a string: {path!r}")
            if not os.path.isabs(path) and event.get("cwd"):
                path = os.path.join(event["cwd"], path)
            reason = check(path)
            if reason:
                deny(reason)
                return 0
        return 0
    except Exception as exc:  # fail closed inside a vault only
        event_cwd = event.get("cwd") if isinstance(event, dict) else None
        if in_any_vault([*paths, event_cwd, os.getcwd()]):
            print(f"[bighead guard] blocked: guard error ({exc!r}); fix the hook or edit manually.",
                  file=sys.stderr)
            return 2
        print(f"[bighead guard] warning: guard error outside a vault ({exc!r})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
