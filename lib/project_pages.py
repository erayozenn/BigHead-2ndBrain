"""Read project pages: a `## section` body and the due dates on a hub's Next step lines.

Due dates use the Obsidian Tasks format: `📅 YYYY-MM-DD` on a step line. Only the hub's
`## Next step` section counts; a done task (`- [x]`) and an invalid date are ignored.

Also shared by the procedures hook and usage_report.py: the kinds of reminded shell commands
(`kinds_in`), checklist item counts and the `# bighead-checklist:` answer line (`parse_answer`).

Standard library only; Python 3.10+.
"""

from __future__ import annotations

import re
from datetime import date

DUE_WINDOW = 7    # days ahead that count as near
MAX_STEP = 80     # characters of step text kept

FENCE_RE = re.compile(r"^(```|~~~)")
DUE_RE = re.compile("\U0001F4C5️?\\s*(\\d{4}-\\d{2}-\\d{2})")
MARKER_RE = re.compile(r"^\s*(?:\d+[.)]|[-*+])\s+(?:\[ \]\s+)?")
DONE_RE = re.compile(r"^\s*(?:\d+[.)]|[-*+])\s+\[[xX]\]")


def _prose_lines(text: str) -> list[str]:
    """Lines outside fenced code blocks, without line endings."""
    out, fenced = [], False
    for line in text.splitlines():
        if FENCE_RE.match(line.strip()):
            fenced = not fenced
            continue
        if not fenced:
            out.append(line)
    return out


def section(text: str, heading: str) -> str | None:
    """Body of the first `## <heading>` section (outside code), or None if there is none."""
    body, inside = [], False
    for line in _prose_lines(text):
        if re.match(r"^##\s", line):
            if inside:
                break
            inside = line[2:].strip() == heading
            continue
        if inside:
            body.append(line)
    return "\n".join(body) if inside else None


# --- reminded shell commands and the checklist answer line (procedures hook, usage report) ---

QUOTED = re.compile(r""""(?:\\.|[^"\\])*"|'[^']*'""")
SEPARATORS = re.compile(r"&&|\|\||[;|&\n]")
ENV_PREFIX = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)+")
GIT_PUSH = re.compile(r"^git(?:\s+(?:-C|-c)\s+\S+|\s+--?[\w-]+(?:=\S+)?)*\s+push(?:\s|$)")
GH_PR = re.compile(r"^gh(?:\s+(?:-R|--repo)\s+\S+)?\s+pr\s+(create|merge)(?:\s|$)")
ITEM_RE = re.compile(r"^(?:[-*+]|\d+[.)])\s+\S")
ANSWER_RE = re.compile(r"#[ \t]*bighead-checklist:[ \t]*([^\n]*)", re.IGNORECASE)
ENTRY_RE = re.compile(r"^(?:\d+[.):]?\s+)?(done|not done|n/a|user ok)\s*(?::\s*(.*))?$", re.IGNORECASE)


def kinds_in(command: str) -> list[str]:
    """Kinds of reminded commands (push, pr, merge) in a shell command line, in order, no repeats."""
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


def count_items(body: str) -> int:
    """Top-level list lines (`-`, `*`, `+`, `1.`, `1)`) of a checklist body, outside code."""
    return sum(1 for line in _prose_lines(body) if ITEM_RE.match(line))


def parse_answer(command: str, expected: int | None) -> dict:
    """Check the `# bighead-checklist:` line of a command.

    `expected` is the item count (0 means at least one entry; None skips the count check).
    Returns {"ok", "problem", "entries", "done", "n_a", "user_ok"}; problem is "" or one of
    "missing", "entry" (unknown entry, or n/a / user ok without text), "not done", "count".
    """
    out = {"ok": False, "problem": "", "entries": 0, "done": 0, "n_a": 0, "user_ok": 0}
    m = ANSWER_RE.search(command)
    if not m:
        out["problem"] = "missing"
        return out
    entries = [e.strip() for e in m.group(1).split(";") if e.strip()]
    out["entries"] = len(entries)
    for entry in entries:
        em = ENTRY_RE.match(entry)
        if not em:
            out["problem"] = "entry"
            return out
        status, text = em.group(1).lower(), (em.group(2) or "").strip()
        if status == "not done":
            out["problem"] = "not done"
            return out
        if status == "done":
            out["done"] += 1
        elif not text:
            out["problem"] = "entry"
            return out
        else:
            out["n_a" if status == "n/a" else "user_ok"] += 1
    if expected is not None and len(entries) != max(expected, 1):
        out["problem"] = "count"
        return out
    if not entries:
        out["problem"] = "count"
        return out
    out["ok"] = True
    return out


# Command kind -> words a `### Before ...` heading may name, best first.
CHECKLIST_WORDS = {
    "pr": ("pr", "pull request"),
    "push": ("push", "pr", "pull request"),
    "merge": ("merge", "merging", "release"),
}


def checklist(overview_text: str, kind: str) -> tuple[str, str] | None:
    """(heading, body) of the `### Before ...` subsection of `## Procedures` for a command kind.

    `push` falls back to the PR list; `merge` takes a merge, then a release list. None when the
    kind is unknown, there is no matching subsection or its body is empty.
    """
    body = section(overview_text, "Procedures")
    words = CHECKLIST_WORDS.get(kind)
    if body is None or not words:
        return None
    subs, current = [], None
    for line in body.splitlines():
        if re.match(r"^###\s", line):
            current = [line[3:].strip(), []]
            subs.append(current)
        elif current is not None:
            current[1].append(line)
    for word in words:
        pattern = re.compile(rf"^before\s+(?:(?:a|an|the)\s+)?{re.escape(word)}\b", re.IGNORECASE)
        for heading, lines in subs:
            if pattern.match(heading):
                text = "\n".join(lines).strip()
                return (heading, text) if text else None
    return None


def due_items(hub_text: str, today: date, window: int = DUE_WINDOW) -> list[dict]:
    """Next step items that are overdue or due within `window` days, oldest date first.

    Each item: {"step": text without marker and date, "date": "YYYY-MM-DD", "days": int},
    where days < 0 means overdue.
    """
    body = section(hub_text, "Next step")
    if not body:
        return []
    items = []
    for line in body.splitlines():
        match = DUE_RE.search(line)
        if not match or DONE_RE.match(line):
            continue
        try:
            due = date.fromisoformat(match.group(1))
        except ValueError:
            continue
        days = (due - today).days
        if days > window:
            continue
        step = MARKER_RE.sub("", DUE_RE.sub("", line)).strip()
        step = re.sub(r"\s{2,}", " ", step)
        if len(step) > MAX_STEP:
            step = step[:MAX_STEP - 3].rstrip() + "..."
        items.append({"step": step, "date": due.isoformat(), "days": days})
    items.sort(key=lambda i: i["date"])
    return items


def due_phrase(days: int) -> str:
    if days < 0:
        return f"overdue by {-days} day{'s' if days != -1 else ''}"
    if days == 0:
        return "due today"
    return f"in {days} day{'s' if days != 1 else ''}"
