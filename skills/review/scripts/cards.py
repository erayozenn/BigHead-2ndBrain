#!/usr/bin/env python3
"""Read-only helper for flashcards in the Obsidian Spaced Repetition format. Standard library only.

Usage:
  cards.py stats  [--vault <dir>] [--today YYYY-MM-DD] [--deck <name>]
      JSON: card counts per file, new (never reviewed), due (scheduled date <= today), and the
      due cards' questions with file and line.
  cards.py prefix --file <cards file> [--lines N]
      JSON: line count and SHA-256 of the first N lines (default: all). Run before appending,
      then again with --lines <old count> after: equal hashes prove nothing above was changed.

Card syntax (plugin defaults): single-line `Q::A` and `Q:::A` (reversed, two cards);
multi-line: question lines, a line `?` (or `??`), answer lines, ended by a blank line.
Scheduling is the plugin's HTML comment `<!--SR:!YYYY-MM-DD,interval,ease-->` after a card
(one `!date,..` group per direction). This script never writes anything.
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


def parse_cards(text: str) -> list[dict]:
    """Cards in one file: question, line (1-based), deck, sides, scheduled dates."""
    lines = text.replace("\r\n", "\n").split("\n")
    body_start = 0
    if lines and lines[0].strip() == "---":  # skip frontmatter
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                body_start = i + 1
                break
    cards: list[dict] = []
    deck = ""
    i = body_start
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        m = DECK_RE.search(line)
        if m and "::" not in line:
            deck = m.group(1) or ""
            i += 1
            continue
        card = None
        if "::" in stripped and not stripped.startswith(("<!--", ">")):
            q = stripped.split(":::" if ":::" in stripped else "::", 1)[0]
            card = {"line": i + 1, "question": SR_RE.sub("", q).strip(), "deck": deck,
                    "sides": 2 if ":::" in stripped else 1, "end": i}
        elif stripped in ("?", "??") and i > body_start:
            start = i - 1
            while (start > body_start and lines[start - 1].strip()
                   and not DECK_RE.search(lines[start - 1]) and not SR_RE.search(lines[start - 1])):
                start -= 1
            end = i + 1
            while end + 1 < len(lines) and lines[end + 1].strip() and not SR_RE.fullmatch(lines[end + 1].strip()):
                end += 1
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


def stats(vault: Path, today: dt.date, deck: str | None) -> dict:
    out = {"today": today.isoformat(), "files": [], "cards": 0, "new": 0, "due": 0, "due_cards": []}
    root = vault / "cards"
    for path in sorted(root.rglob("*.md")) if root.is_dir() else []:
        rel = path.relative_to(vault).as_posix()
        cards = parse_cards(path.read_text(encoding="utf-8", errors="replace"))
        if deck:
            cards = [c for c in cards if c["deck"] == deck or c["deck"].startswith(deck + "/")]
        n_new = n_due = 0
        for c in cards:
            if not c["dates"]:
                n_new += 1
                continue
            due = [d for d in c["dates"] if dt.date.fromisoformat(d) <= today]
            if due:
                n_due += 1
                out["due_cards"].append({"file": rel, "line": c["line"], "deck": c["deck"],
                                         "question": c["question"][:200], "due": min(due)})
        out["files"].append({"file": rel, "cards": len(cards), "new": n_new, "due": n_due})
        out["cards"] += len(cards)
        out["new"] += n_new
        out["due"] += n_due
    out["due_cards"].sort(key=lambda c: (c["due"], c["file"], c["line"]))
    return out


def prefix(path: Path, n: int | None) -> dict:
    data = path.read_bytes().decode("utf-8")
    lines = data.split("\n")
    count = len(lines) - (1 if data.endswith("\n") else 0)
    n = count if n is None else n
    head = "\n".join(lines[:n])
    return {"file": path.as_posix(), "lines": count, "hashed_lines": n,
            "sha256": hashlib.sha256(head.encode("utf-8")).hexdigest()}


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
    p_prefix.add_argument("--lines", type=int)
    args = parser.parse_args()
    if args.cmd == "stats":
        result = stats(Path(args.vault).resolve(), dt.date.fromisoformat(args.today), args.deck)
    else:
        result = prefix(Path(args.file), args.lines)
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
