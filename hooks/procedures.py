#!/usr/bin/env python3
"""PreToolUse procedure reminder for BigHead 2ndBrain project sessions.

Before `git push`, `gh pr create` or `gh pr merge` in a session opened outside the vault whose
folder matches exactly one project hub, the matching `### Before ...` checklist from the hub's
`<name>-overview.md` (`## Procedures`) is put in front of Claude by denying the call ONCE with
the checklist as the reason. Claude checks each item, asks the user about any item not done,
then reruns the command with a `# bighead-checklist:` comment line holding one entry per item
(`done`, `n/a: <why>`, `user ok: <what>`). A rerun without a valid line is refused with a short
reason (WP8, 0.7.1: in real use a deny text alone got per-item answers in 0 of 7 reminders).
After a valid line, that kind passes for the rest of the session.

Why deny and not additionalContext: a PreToolUse additionalContext reaches Claude next to the
tool result, i.e. after the push or PR already happened.

Checklist per kind (lib/project_pages.checklist): PR -> "Before a PR"; push -> "Before a push",
else "Before a PR"; merge -> "Before a merge", else "Before a release"; none -> no reminder.

Silent (no output, exit 0) when: the tool is not a shell, the command has none of these
commands, the session folder is inside a vault, `vault_path` is unset or not a vault, zero or
several hubs match, there is no checklist for the kind, the event has no session id, the state
folder cannot be written, or anything else goes wrong. It never blocks on its own errors.

State: one marker file per (session, kind) in CLAUDE_PLUGIN_DATA (else the temp folder) holding
`reminded` or `answered`; an empty marker from 0.7.0 counts as answered. Markers older than 7 days
are removed. This is not a security control: it checks the answer's form, not its truth, and a
command written another way (an alias, a script) is not seen.

Standard library only; Python 3.10+.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))

TAG = "[bighead procedures]"
SHELL_TOOLS = ("Bash", "PowerShell")
MAX_BODY = 1500   # characters of checklist text per reminder
MARKER_DAYS = 7
LABELS = {"push": "git push", "pr": "gh pr create", "merge": "gh pr merge"}

REMINDED, ANSWERED = "reminded", "answered"


def state_dir() -> str:
    base = os.environ.get("CLAUDE_PLUGIN_DATA", "").strip()
    return os.path.join(base, "procedures") if base else os.path.join(tempfile.gettempdir(), "bighead-procedures")


def marker(folder: str, session: str, kind: str) -> str:
    return os.path.join(folder, hashlib.sha256(f"{session}\0{kind}".encode()).hexdigest()[:32])


def marker_state(path: str) -> str | None:
    """None (not reminded), REMINDED, or ANSWERED; an empty 0.7.0 marker counts as answered."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return REMINDED if f.read().strip() == REMINDED else ANSWERED
    except OSError:
        return None


def set_marker(path: str, state: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(state)


def entries(n: int) -> str:
    return f"{n} entry" if n == 1 else f"{n} entries"


def example(n: int) -> str:
    """The answer line with exactly n placeholder entries (a fixed 3-entry example misleads)."""
    shown = [f"{i} <answer>" for i in range(1, n + 1)]
    if n > 4:  # long lists: first two, an ellipsis, the last
        shown = shown[:2] + ["…", shown[-1]]
    return "# bighead-checklist: " + "; ".join(shown)


ANSWER_RULE = ("Each `<answer>` is `done`, `n/a: <why>` or `user ok: <what the user allowed>`, "
               "in list order, separated by `;` (no `;` inside an entry).")


def needed(lists: list[tuple[str, str]]) -> int:
    """Entries a checklist answer needs: one per item, at least one per list."""
    import project_pages as pp
    return sum(max(pp.count_items(body), 1) for _, body in lists)


def refusal(problem: str, got: int, need: int, overview: str) -> str:
    why = {
        "missing": "the rerun has no `# bighead-checklist:` line.",
        "count": f"the line has {entries(got)}; this checklist needs {entries(need)}.",
        "not done": "an item is marked not done. Fix it, or stop, ask the user and wait for their "
                    "answer; if they say go on, write `user ok: <what they allowed>`.",
        "entry": "an entry is not `done`, `n/a: <why>` or `user ok: <what the user allowed>` "
                 "(n/a and user ok need text after the colon).",
    }[problem]
    return (f"{TAG} Rerun refused: {why} Run the same command again with one added line holding "
            f"{entries(need)}: `{example(need)}`. {ANSWER_RULE} "
            f'The checklist is in {overview} ("## Procedures").')


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
    kinds = pp.kinds_in(command)
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
    shown = overview.replace(os.sep, "/")
    due, lists, pending, pending_lists = [], [], [], []
    for kind in kinds:
        path = marker(states, session, kind)
        state = marker_state(path)
        if state == ANSWERED:
            continue
        found = pp.checklist(text, kind)
        if not found:
            continue
        kinds_now, lists_now = (due, lists) if state is None else (pending, pending_lists)
        kinds_now.append(kind)
        if found not in lists_now:
            lists_now.append(found)

    if not due:
        # WP8: every reminded kind here needs the answer line (real use 2026-11-08..09: a deny
        # text alone got per-item answers in 0 of 7 reminders).
        if not pending:
            return None
        need = needed(pending_lists)
        answer = pp.parse_answer(command, need)
        if not answer["ok"]:
            return refusal(answer["problem"], answer["entries"], need, shown)
        for kind in pending:
            set_marker(marker(states, session, kind), ANSWERED)
        return None

    # Marker first: if it cannot be written we stay silent rather than deny forever.
    for kind in due:
        set_marker(marker(states, session, kind), REMINDED)
    need = needed(lists)
    commands = " / ".join(f"`{LABELS[k]}`" for k in due)
    # Instructions before the list: in the 2026-11-08 live check, with them after the list,
    # Claude reran before answering every item and went past a "not done" item.
    parts = [f'{TAG} Stopped once: before {commands} in project "{name}", go through the '
             f'checklist below from {shown} ("## Procedures").',
             "Do not run the command again yet. Steps, in order:",
             "1. Check each item below.",
             "2. If an item is not done: fix it, or stop, ask the user and wait for their answer.",
             f"3. Run the same command again with one added line holding {entries(need)}, one per "
             f"item: `{example(need)}`. {ANSWER_RULE} A bare `not done` or a wrong count is "
             "refused. `#` starts a comment in Bash and PowerShell, so the command runs unchanged."]
    room = MAX_BODY
    for heading, body in lists:
        if len(body) > room:
            body = body[:max(room, 0)].rstrip() + "\n(... cut here; read the rest in the overview.)"
        room -= len(body)
        parts.append(f"### {heading}\n{body}")
    parts.append("After a valid line, this kind of command passes for the rest of the session. "
                 "This repo's CLAUDE.md wins on conflict.")
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
