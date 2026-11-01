#!/usr/bin/env python3
"""Read-only helper for flashcards in the Obsidian Spaced Repetition format. Standard library only.

Usage:
  cards.py stats  [--vault <dir>] [--today YYYY-MM-DD] [--deck <name>]
      JSON: card counts per cards-*.md file, new (never reviewed), due (scheduled date <= today),
      and the due cards' questions with file and line. A reversed card counts once per direction
      in the totals and appears once in due_cards. Invalid scheduled dates go to warnings.
      A vault folder that does not exist is an error. --deck names a tag, not a file: `ml`,
      `flashcards/ml` and `#flashcards/ml` are the same deck; case does not matter.
  cards.py prefix --file <cards file> [--bytes N | --lines N]
      JSON: line and byte counts, and the SHA-256 of the first N bytes or lines, terminators
      included (default: the whole file). Run before appending, then again with
      --bytes <old bytes> after: equal hashes prove the existing bytes were not changed.

Card syntax (plugin defaults): single-line `Q::A` and `Q:::A` (reversed, two cards);
multi-line: question lines, a line `?` (or `??`), answer lines, ended by a blank line.
Scheduling is the plugin's HTML comment `<!--SR:!YYYY-MM-DD,interval,ease-->` after a card
(one `!date,..` group per direction). This script never writes anything.

Counts follow the plugin's parser: fenced code holds no cards and blank lines inside it do not end
a card; a separator inside inline code is ignored; a line with a separator ends an open multi-line
card, which is dropped; `?` with no question above it is no card; empty sides of `Q::A` stay cards.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

SR_RE = re.compile(r"<!--SR:(.*?)-->")
SR_DATE_RE = re.compile(r"!(\d{4}-\d{2}-\d{2}),\d+,\d+")
DECK_RE = re.compile(r"(?:^|\s)#flashcards(?:/([\w/-]+))?")
FENCE_RE = re.compile(r"^(`{3,}|~{3,})")


def fenced_lines(lines: list[str], start: int) -> list[bool]:
    """Which lines belong to a code fence; an unclosed fence runs to the end of the file."""
    fenced = [False] * len(lines)
    i = start
    while i < len(lines):
        m = FENCE_RE.match(lines[i])
        if m:
            fenced[i] = True
            i += 1
            while i < len(lines) and not lines[i].startswith(m.group(1)):
                fenced[i] = True
                i += 1
            if i < len(lines):
                fenced[i] = True
        i += 1
    return fenced


def has_marker(text: str, marker: str) -> bool:
    """The first marker on the line counts unless it sits inside inline code."""
    at = text.find(marker)
    if at == -1:
        return False
    return not (text[:at].count("`") % 2 and text[at + len(marker):].count("`") % 2)


def inline_separator(stripped: str) -> str | None:
    if stripped.startswith(("<!--", ">")):
        return None
    for marker in (":::", "::"):
        if has_marker(stripped, marker):
            return marker
    return None


def parse_cards(text: str) -> list[dict]:
    """Cards in one file: question, line (1-based), deck, sides, scheduled dates."""
    lines = text.replace("\r\n", "\n").split("\n")
    body_start = 0
    if lines and lines[0].strip() == "---":  # skip frontmatter
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                body_start = i + 1
                break
    fenced = fenced_lines(lines, body_start)

    def is_question_line(n: int) -> bool:
        if fenced[n]:
            return True
        text = lines[n].strip()
        return bool(text) and not (DECK_RE.search(text) or SR_RE.search(text) or inline_separator(text))

    cards: list[dict] = []
    deck = ""
    i = body_start
    while i < len(lines):
        if fenced[i]:
            i += 1
            continue
        line = lines[i]
        stripped = line.strip()
        m = DECK_RE.search(line)
        if m and "::" not in line:
            deck = m.group(1) or ""
            i += 1
            continue
        card = None
        separator = inline_separator(stripped)
        if separator:
            q = stripped.split(separator, 1)[0]
            card = {"line": i + 1, "question": SR_RE.sub("", q).strip(), "deck": deck,
                    "sides": 2 if separator == ":::" else 1, "end": i}
        elif stripped in ("?", "??") and i > body_start and is_question_line(i - 1):
            start = i - 1
            while start > body_start and is_question_line(start - 1):
                start -= 1
            end = i
            replaced_at = None
            while end + 1 < len(lines):
                following = lines[end + 1].strip()
                if not fenced[end + 1]:
                    if not following or SR_RE.fullmatch(following):
                        break
                    if inline_separator(following):
                        replaced_at = end + 1
                        break
                end += 1
            if replaced_at is not None:
                i = replaced_at
                continue
            q = " ".join(l.strip() for l in lines[start:i])
            card = {"line": start + 1, "question": q, "deck": deck,
                    "sides": 2 if stripped == "??" else 1, "end": end}
        if card is None:
            i += 1
            continue
        # scheduling comment: on the card's last line or the line after it
        sched = SR_RE.search(lines[card["end"]])
        nxt = card["end"] + 1
        if not sched and nxt < len(lines):
            sched = SR_RE.fullmatch(lines[nxt].strip())
        card["dates"] = SR_DATE_RE.findall(sched.group(1)) if sched else []
        i = max(card["end"], i) + 1
        del card["end"]
        cards.append(card)
    return cards


def deck_key(name: str) -> str:
    """A deck name without `#flashcards/`, lowercased; empty means every deck."""
    key = name.strip().lstrip("#").strip("/").lower()
    if key == "flashcards":
        return ""
    return key.removeprefix("flashcards/")


def stats(vault: Path, today: dt.date, deck: str | None) -> dict:
    out = {"today": today.isoformat(), "files": [], "cards": 0, "new": 0, "due": 0, "due_cards": [],
           "warnings": []}
    deck = deck_key(deck) if deck else ""
    root = vault / "cards"
    for path in sorted(root.rglob("cards-*.md")) if root.is_dir() else []:
        rel = path.relative_to(vault).as_posix()
        cards = parse_cards(path.read_text(encoding="utf-8", errors="replace"))
        if deck:
            cards = [c for c in cards
                     if c["deck"].lower() == deck or c["deck"].lower().startswith(deck + "/")]
        n_cards = n_new = n_due = 0
        for c in cards:
            n_cards += c["sides"]
            n_new += max(c["sides"] - len(c["dates"]), 0)
            due = []
            for date in c["dates"]:
                try:
                    if dt.date.fromisoformat(date) <= today:
                        due.append(date)
                except ValueError:
                    out["warnings"].append({"file": rel, "line": c["line"], "date": date})
            if due:
                n_due += min(len(due), c["sides"])
                out["due_cards"].append({"file": rel, "line": c["line"], "deck": c["deck"],
                                         "question": c["question"][:200], "due": min(due)})
        out["files"].append({"file": rel, "cards": n_cards, "new": n_new, "due": n_due})
        out["cards"] += n_cards
        out["new"] += n_new
        out["due"] += n_due
    out["due_cards"].sort(key=lambda c: (c["due"], c["file"], c["line"]))
    return out


def prefix(path: Path, n_lines: int | None, n_bytes: int | None) -> dict:
    data = path.read_bytes()
    parts = data.split(b"\n")
    lines = [part + b"\n" for part in parts[:-1]] + ([parts[-1]] if parts[-1] else [])
    if n_bytes is not None:
        head = data[:n_bytes]
    elif n_lines is not None:
        head = b"".join(lines[:n_lines])
    else:
        head = data
    return {"file": path.as_posix(), "lines": len(lines), "bytes": len(data),
            "hashed_bytes": len(head), "sha256": hashlib.sha256(head).hexdigest()}


def count(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return number


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_stats = sub.add_parser("stats")
    p_stats.add_argument("--vault", default=".")
    p_stats.add_argument("--today", default=dt.date.today().isoformat())
    p_stats.add_argument("--deck")
    p_prefix = sub.add_parser("prefix")
    p_prefix.add_argument("--file", required=True)
    size = p_prefix.add_mutually_exclusive_group()
    size.add_argument("--lines", type=count)
    size.add_argument("--bytes", type=count)
    args = parser.parse_args()
    if args.cmd == "stats":
        vault = Path(args.vault).resolve()
        if not vault.is_dir():
            parser.error(f"vault folder not found: {args.vault}")
        result = stats(vault, dt.date.fromisoformat(args.today), args.deck)
    else:
        try:
            result = prefix(Path(args.file), args.lines, args.bytes)
        except OSError as exc:
            parser.error(f"cannot read {args.file}: {exc.strerror}")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
