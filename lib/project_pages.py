"""Read project pages: a `## section` body and the due dates on a hub's Next step lines.

Due dates use the Obsidian Tasks format: `📅 YYYY-MM-DD` on a step line. Only the hub's
`## Next step` section counts; a done task (`- [x]`) and an invalid date are ignored.

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
