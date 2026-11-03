#!/usr/bin/env python3
"""PreToolUse guard for BigHead 2ndBrain vaults.

Reads the hook event JSON on stdin and denies file-tool calls that would
break the vault's hard rules:
  - modify an existing file under raw/ (sources are immutable)
  - create a file under raw/ outside raw/web/
  - edit a note whose frontmatter says `author: me`
  - touch a .obsidian/ folder anywhere in the vault

Paths outside a vault get no decision (normal permission flow).
A vault is a folder holding raw/ and a CLAUDE.md that starts with VAULT_MARKER.
Every enclosing vault is checked, so a vault-shaped folder unpacked inside raw/
or .obsidian/ does not lift the protection of the outer vault.

Failure mode: if the guard itself breaks while the target is inside a vault
(or cannot be determined and the event's cwd or the process cwd is a vault),
it blocks with exit 2. An event with no file path counts as that. Outside a
vault it never blocks.

Writes from a session opened outside the vault (the event's cwd is not inside
the target's vault) are free only for wiki/, cards/, index.md, log.md and
hot.md; every other vault path asks the user first. The vault's own
.claude/settings.json does not load in such a session, so this rule stands in
for its ask rules. Events without a cwd keep the old behaviour.

Shell commands (Bash, PowerShell): a delete, move or redirect is denied when
the command names a vault path (the vault around the session folder, or the
plugin option `vault_path`), or when the session runs inside a vault. This is
a heuristic over the command text, not a parser; it never blocks on its own
errors, so a guard bug cannot lock up every shell command.

Limit: a hard link looks like an ordinary file, so one made outside raw/ is
not protected.

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
AUTHOR_ME = re.compile(r"""^author\s*:\s*\[?\s*["']?me["']?\s*\]?\s*(#.*)?$""", re.IGNORECASE)
AUTHOR_KEY = re.compile(r"^author\s*:\s*(#.*)?$", re.IGNORECASE)
ITEM_ME = re.compile(r"""^-\s*["']?me["']?\s*(#.*)?$""", re.IGNORECASE)
MSYS_DRIVE = re.compile(r"^/([A-Za-z])(?=/|$)")
ENV_KEY = "CLAUDE_PLUGIN_OPTION_VAULT_PATH"
SHELL_TOOLS = ("Bash", "PowerShell")
WRITE_TOOLS = ("Write", "Edit", "NotebookEdit")
FREE_TOPS = ("wiki", "cards")
FREE_FILES = ("index.md", "log.md", "hot.md")
QUOTED = re.compile(r""""[^"]*"|'[^']*'""")
VERB = re.compile(
    r"(?:^|[\s;&|(])(rm|rmdir|rd|del|erase|mv|move|ren|rename|unlink|shred|truncate|"
    r"remove-item|move-item|rename-item|clear-content|ri|mi|rni|clc)(?=\s|$)", re.IGNORECASE)
GIT_VERB = re.compile(r"\bgit\b[^;&|]*?\s(rm|mv|clean)(?=\s|$)|\bgit\b[^;&|]*\sreset\s+--hard",
                      re.IGNORECASE)


def from_msys(path: str) -> str:
    """On Windows, /c/Users/x (Git Bash form) means C:/Users/x."""
    return MSYS_DRIVE.sub(r"\1:", path) if os.name == "nt" else path


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
    while lines and not lines[0].strip():  # a blank line before the frontmatter still means it
        lines.pop(0)
    if not lines or lines[0].strip() != "---":
        return False
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            return False
        if AUTHOR_ME.match(line.strip()):
            return True
        if AUTHOR_KEY.match(line.strip()):  # block list with `me` as its only item
            items = []
            for following in lines[i + 1:]:
                if not following.strip().startswith("-") or following.strip() == "---":
                    break
                items.append(following.strip())
            if len(items) == 1 and ITEM_ME.match(items[0]):
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
        if ".obsidian" in parts:
            return ".obsidian/ is Obsidian's config; the vault rules forbid touching it."
        if top == "raw":
            if exists:
                return "raw/ files are immutable sources; existing files may never be modified."
            if len(parts) < 3 or parts[1] != "web":
                return "New raw files may only be added under raw/web/."
    if exists and target.lower().endswith(".md") and has_author_me(target):
        return "This note has `author: me`; Claude never edits the user's notes. Report the problem instead."
    return None


def cross_folder_ask(path: str, cwd) -> str | None:
    """Ask reason for a vault path written from a session outside that vault, else None."""
    if not isinstance(cwd, str) or not cwd:
        return None
    target = norm(path)
    vaults = find_vaults(target)
    if not vaults:
        return None
    vault = vaults[0]
    here = norm(from_msys(cwd))
    if here == vault or here.startswith(vault.rstrip(os.sep) + os.sep):
        return None
    parts = os.path.relpath(target, vault).split(os.sep)
    if parts[0] in FREE_TOPS or (len(parts) == 1 and parts[0] in FREE_FILES):
        return None
    return ("This is an ask-first part of your vault, written from a session outside the vault, "
            "where the vault's own permission rules do not load. Approve only if you asked for it.")


def decide(decision: str, reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": f"[bighead guard] {reason}",
        }
    }))


def deny(reason: str) -> None:
    decide("deny", reason)


def configured_vault():
    value = os.environ.get(ENV_KEY, "").strip().strip('"').strip("'").strip()
    if not value:
        return None
    path = norm(from_msys(value))
    return path if is_vault(path) else None


def path_forms(vault: str) -> set:
    """Lower-case spellings of a vault path that may appear in a command."""
    forms = {vault.lower(), vault.replace("\\", "/").lower()}
    fwd = vault.replace("\\", "/")
    if len(fwd) > 2 and fwd[1] == ":":
        forms.add(("/" + fwd[0] + fwd[2:]).lower())
    return {f.rstrip("/\\") for f in forms if len(f) > 3}


def shell_check(event: dict) -> str | None:
    """Deny reason for a shell command that deletes, moves or overwrites vault files."""
    command = (event.get("tool_input") or {}).get("command")
    if not isinstance(command, str) or not command.strip():
        return None
    cwd = event.get("cwd") if isinstance(event.get("cwd"), str) else os.getcwd()
    unquoted = QUOTED.sub(" ", command)
    destructive = bool(VERB.search(unquoted) or GIT_VERB.search(unquoted))
    if find_vaults(norm(from_msys(cwd))):
        if destructive:
            return "Shell deletes and moves are not allowed inside a vault; nothing is ever deleted."
        return None
    vault = configured_vault()
    if not vault:
        return None
    lowered = command.lower().replace("\\", "/")
    forms = {f.replace("\\", "/") for f in path_forms(vault)}
    if not any(form in lowered for form in forms):
        return None
    redirect = any(re.search(r">\s*[\"']?" + re.escape(form), lowered) for form in forms)
    if destructive or redirect:
        return ("This command deletes, moves or overwrites files in your vault. Nothing in the vault "
                "is ever deleted; use Edit/Write, or ask the user to do it in Obsidian.")
    return None


def in_any_vault(candidates: list) -> bool:
    for candidate in candidates:
        try:
            if isinstance(candidate, str) and candidate and find_vaults(norm(from_msys(candidate))):
                return True
        except Exception:
            continue
    return False


def main() -> int:
    event = None
    paths = []
    try:
        event = json.load(sys.stdin)
        if isinstance(event, dict) and event.get("tool_name") in SHELL_TOOLS:
            try:
                reason = shell_check(event)
            except Exception as exc:  # heuristic check: never lock up the shell
                print(f"[bighead guard] warning: shell check error ({exc!r})", file=sys.stderr)
                return 0
            if reason:
                deny(reason)
            return 0
        tool_input = event.get("tool_input") or {}
        paths = [tool_input[k] for k in PATH_KEYS if tool_input.get(k)]
        if not paths:
            raise ValueError("the event names no file path")
        for path in paths:
            if not isinstance(path, str):
                raise TypeError(f"path is not a string: {path!r}")
            if "\0" in path:
                raise ValueError("path holds a NUL character")
            path = from_msys(path)
            if not os.path.isabs(path) and event.get("cwd"):
                path = os.path.join(event["cwd"], path)
            reason = check(path)
            if reason:
                deny(reason)
                return 0
        for path in paths if event.get("tool_name") in WRITE_TOOLS else []:
            path = from_msys(path)
            if not os.path.isabs(path) and event.get("cwd"):
                path = os.path.join(event["cwd"], path)
            reason = cross_folder_ask(path, event.get("cwd"))
            if reason:
                decide("ask", reason)
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
