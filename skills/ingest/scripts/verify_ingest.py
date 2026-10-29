#!/usr/bin/env python3
"""Verify vault pages after an ingest. Standard library only.

Usage:
  verify_ingest.py --vault <dir> --pages <page.md> [<page.md> ...] [--source-text <file> ...]

Checks on the given pages:
  - frontmatter present with the required keys; `author: me` pages must not be in the list
  - "For future agent" summary callout directly after the frontmatter (wiki pages)
  - every wikilink resolves to exactly one file
  - quoted spans (4+ words) appear in a source text, after normalization (ligatures,
    curly quotes, dashes, hyphenated line breaks, whitespace, case)
Vault-wide checks:
  - duplicate basenames outside raw/ (and wiki vs raw)
  - hot.md <= 500 words

Exit code 1 if any ERROR, else 0. WARN lines need a human look but do not fail.
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

SKIP_DIRS = {".git", ".obsidian", ".claude", ".trash", "node_modules"}
SYSTEM_FILES = {"CLAUDE.md", "index.md", "log.md", "hot.md", "Threads.md",
                "CRITICAL_FACTS.md", "rules.md", "source-register.md"}
REQUIRED_KEYS = ["type", "status", "created", "updated", "tags", "aliases",
                 "sources", "author", "sensitivity"]
SOURCE_KEYS = ["source_type", "authority"]
HOT_MAX_WORDS = 500
MIN_QUOTE_WORDS = 4

WIKILINK_RE = re.compile(r"!?\[\[([^\]|#^]+)(?:[#^][^\]|]*)?(?:\|[^\]]*)?\]\]")
QUOTE_RE = re.compile(r"\"([^\"\n]+)\"|“([^”\n]+)”")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Report:
    def __init__(self) -> None:
        self.errors = 0
        self.warnings = 0

    def error(self, where: str, msg: str) -> None:
        self.errors += 1
        print(f"ERROR {where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings += 1
        print(f"WARN  {where}: {msg}")


def split_frontmatter(text: str) -> tuple[dict[str, str] | None, str]:
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---", 4)
    if end == -1:
        return None, text
    fm: dict[str, str] = {}
    for line in text[4:end].splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    body = text[end + 4:].split("\n", 1)[1] if "\n" in text[end + 4:] else ""
    return fm, body


def strip_code(text: str) -> str:
    return INLINE_CODE_RE.sub("", FENCE_RE.sub("", text))


def normalize(text: str) -> str:
    # Quote marks collapse to one kind: nested quotes often switch between ' and ".
    text = unicodedata.normalize("NFKC", text)  # also expands ligatures like U+FB01
    text = (text.replace("‘", "'").replace("’", "'")
                .replace("“", "'").replace("”", "'").replace('"', "'")
                .replace("–", "-").replace("—", "-").replace("­", ""))
    text = re.sub(r"-\s*\n\s*", "", text)  # hyphenated line breaks in PDF text
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def vault_files(vault: Path) -> list[Path]:
    files = []
    for path in vault.rglob("*"):
        if path.is_file() and not any(part in SKIP_DIRS for part in path.relative_to(vault).parts):
            files.append(path)
    return files


def build_link_index(vault: Path, files: list[Path]) -> tuple[dict, set]:
    by_name: dict[str, list[Path]] = defaultdict(list)
    rel_paths = set()
    for f in files:
        rel = f.relative_to(vault).as_posix()
        rel_paths.add(rel.lower())
        by_name[f.name.lower()].append(f)
        if f.suffix.lower() == ".md":
            by_name[f.stem.lower()].append(f)
    return by_name, rel_paths


def resolve_link(target: str, by_name: dict, rel_paths: set) -> int:
    """Return how many files a link target matches."""
    target = target.strip().replace("\\", "/")
    if "/" in target:
        t = target.lstrip("/").lower()
        return int(t in rel_paths or f"{t}.md" in rel_paths)
    return len(by_name.get(target.lower(), []))


def check_page(page: Path, vault: Path, by_name: dict, rel_paths: set,
               sources: list[str], report: Report) -> None:
    where = page.relative_to(vault).as_posix()
    text = page.read_text(encoding="utf-8")
    if text.startswith("﻿"):
        report.error(where, "file starts with a BOM")
    if "\r\n" in text:
        report.error(where, "CRLF line endings (vault files use LF)")
    text = text.lstrip("﻿").replace("\r\n", "\n")

    is_system = page.name in SYSTEM_FILES
    fm, body = split_frontmatter(text)
    if not is_system:
        if fm is None:
            report.error(where, "missing frontmatter")
        else:
            keys = REQUIRED_KEYS + (SOURCE_KEYS if fm.get("type") == "source" else [])
            missing = [k for k in keys if k not in fm]
            if missing:
                report.error(where, f"frontmatter missing keys: {', '.join(missing)}")
            if fm.get("author") == "me":
                report.error(where, "author: me — Claude must not edit this note")
            for k in ("created", "updated"):
                if k in fm and not DATE_RE.match(fm[k].strip("'\"")):
                    report.error(where, f"{k} is not YYYY-MM-DD: {fm[k]!r}")
        if where.startswith("wiki/"):
            if not body.lstrip("\n").startswith("> [!summary]"):
                report.error(where, "summary callout must follow the frontmatter directly")

    prose = strip_code(body if fm is not None else text)
    for m in WIKILINK_RE.finditer(prose):
        hits = resolve_link(m.group(1), by_name, rel_paths)
        if hits == 0:
            report.error(where, f"broken link [[{m.group(1)}]]")
        elif hits > 1:
            report.error(where, f"ambiguous link [[{m.group(1)}]] ({hits} matches)")

    if sources:
        for m in QUOTE_RE.finditer(prose):
            quote = m.group(1) or m.group(2)
            if len(quote.split()) < MIN_QUOTE_WORDS:
                continue
            nq = normalize(quote)
            if not any(nq in s for s in sources):
                report.warn(where, f"quote not found verbatim in source text: \"{quote[:70]}\"")


def check_vault(vault: Path, files: list[Path], report: Report) -> None:
    stems: dict[str, list[str]] = defaultdict(list)
    for f in files:
        rel = f.relative_to(vault).as_posix()
        if f.suffix.lower() == ".md":
            stems[f.stem.lower()].append(rel)
    for stem, paths in sorted(stems.items()):
        if len(paths) < 2:
            continue
        outside_raw = [p for p in paths if not p.startswith("raw/")]
        if len(outside_raw) > 1 or (outside_raw and len(paths) > len(outside_raw)):
            report.error("vault", f"duplicate basename '{stem}': {', '.join(paths)}")

    hot = vault / "hot.md"
    if hot.exists():
        words = len(hot.read_text(encoding="utf-8").split())
        if words > HOT_MAX_WORDS:
            report.error("hot.md", f"{words} words (max {HOT_MAX_WORDS})")
        else:
            print(f"OK    hot.md: {words} words")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vault", default=".")
    parser.add_argument("--pages", nargs="+", required=True)
    parser.add_argument("--source-text", nargs="*", default=[],
                        help="text of the ingested source(s), for the quote check")
    args = parser.parse_args()

    vault = Path(args.vault).resolve()
    report = Report()
    files = vault_files(vault)
    by_name, rel_paths = build_link_index(vault, files)
    sources = [normalize(Path(s).read_text(encoding="utf-8", errors="replace"))
               for s in args.source_text]
    if not sources:
        print("NOTE  no --source-text given; quote check skipped")

    for p in args.pages:
        page = Path(p)
        page = page if page.is_absolute() else vault / page
        if not page.exists():
            report.error(p, "page does not exist")
            continue
        check_page(page.resolve(), vault, by_name, rel_paths, sources, report)
    check_vault(vault, files, report)

    print(f"\n{report.errors} error(s), {report.warnings} warning(s)")
    sys.exit(1 if report.errors else 0)


if __name__ == "__main__":
    main()
