#!/usr/bin/env python3
"""Verify vault pages after an ingest. Standard library only.

Usage:
  verify_ingest.py --vault <dir> --pages <page.md> [<page.md> ...] [--source-text <file> ...]

Checks on the given pages:
  - schema (lib/vault_schema.py): frontmatter keys and values, dates, summary callout,
    BOM/CRLF; `author: me` pages must not be in the list
  - every wikilink resolves to exactly one file
  - quoted spans (4+ words) appear in a source text, after normalization (ligatures,
    curly quotes, dashes, hyphenated line breaks, whitespace, case). Source texts are the
    --source-text files plus every raw/ file in the page's `sources:` frontmatter (markdown and
    text directly; PDFs from the fresh `.cache/raw-text/` copy, else via pypdf). System files (hot, index, log, ...) are skipped.
    A warning whose quote is already in the page's git HEAD version is marked "(pre-existing)".
Vault-wide checks:
  - duplicate basenames outside raw/ (and wiki vs raw)
  - hot.md <= 500 words

Exit code 1 if any ERROR, else 0. WARN lines need a human look but do not fail.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from vault_schema import (HOT_MAX_WORDS, SYSTEM_FILES, WIKILINK_RE,  # noqa: E402
                          build_link_index, duplicate_basenames, needs_schema,
                          page_problems, resolve_link, scalar, split_frontmatter,
                          strip_code, vault_files)

try:
    import pypdf  # optional: lets the quote check read PDFs listed in `sources:`
except ImportError:
    pypdf = None

MIN_QUOTE_WORDS = 4

QUOTE_RE = re.compile(r"\"([^\"\n]+)\"|“([^”\n]+)”")


class Report:
    def __init__(self) -> None:
        self.errors = 0
        self.warnings = 0
        self.preexisting = 0

    def error(self, where: str, msg: str) -> None:
        self.errors += 1
        print(f"ERROR {where}: {msg}")

    def warn(self, where: str, msg: str, preexisting: bool = False) -> None:
        self.warnings += 1
        self.preexisting += preexisting
        print(f"WARN  {where}: {msg}{' (pre-existing)' if preexisting else ''}")

    def note(self, msg: str) -> None:
        print(f"NOTE  {msg}")


class SourceTexts:
    """Normalized texts of raw/ files, loaded on first use."""

    def __init__(self, vault: Path, report: Report) -> None:
        self.vault = vault
        self.report = report
        self.cache: dict[str, str | None] = {}

    def get(self, target: str) -> str | None:
        rel = target.strip().replace("\\", "/").lstrip("/")
        if rel not in self.cache:
            self.cache[rel] = self._load(rel)
        return self.cache[rel]

    def _load(self, rel: str) -> str | None:
        path = self.vault / rel
        if not path.exists() and (self.vault / f"{rel}.md").exists():
            path = self.vault / f"{rel}.md"
        if not path.is_file():
            return None
        if path.suffix.lower() == ".pdf":
            cached = self._cached(rel, path)
            if cached is not None:
                return normalize(cached)
            if pypdf is None:
                self.report.note(f"pypdf not installed; quote check cannot read {rel}")
                return None
            try:
                reader = pypdf.PdfReader(str(path))
                return normalize("\n".join(p.extract_text() or "" for p in reader.pages))
            except Exception as exc:  # broken PDFs: skip, do not fail the check
                self.report.note(f"could not extract text from {rel}: {exc}")
                return None
        if path.suffix.lower() in (".md", ".txt"):
            return normalize(path.read_text(encoding="utf-8", errors="replace"))
        return None

    def _cached(self, rel: str, path: Path) -> str | None:
        """Text from `pdf_pages.py cache` (.cache/raw-text/), if fresh for this PDF."""
        key = Path(rel).relative_to("raw").as_posix() if rel.startswith("raw/") else None
        cache = self.vault / ".cache" / "raw-text"
        if key is None or not (cache / f"{key}.txt").exists():
            return None
        try:
            entry = json.loads((cache / "manifest.json").read_text(encoding="utf-8")).get(key, {})
        except (OSError, ValueError):
            return None
        stat = path.stat()
        if entry.get("size") != stat.st_size or entry.get("mtime_ns") != stat.st_mtime_ns:
            return None  # stale: fall back to pypdf
        return (cache / f"{key}.txt").read_text(encoding="utf-8", errors="replace")


def head_version(vault: Path, rel: str) -> str | None:
    """The page as committed at HEAD, or None (new file, no git)."""
    try:
        out = subprocess.run(["git", "-C", str(vault), "show", f"HEAD:{rel}"],
                             capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.decode("utf-8", errors="replace") if out.returncode == 0 else None


def normalize(text: str) -> str:
    # Quote marks collapse to one kind: nested quotes often switch between ' and ".
    text = unicodedata.normalize("NFKC", text)  # also expands ligatures like U+FB01
    text = (text.replace("‘", "'").replace("’", "'")
                .replace("“", "'").replace("”", "'").replace('"', "'")
                .replace("–", "-").replace("—", "-").replace("­", ""))
    text = re.sub(r"-\s*\n\s*", "", text)  # hyphenated line breaks in PDF text
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def check_page(page: Path, vault: Path, by_name: dict, rel_paths: set,
               given: list[str], raw: SourceTexts, report: Report) -> None:
    where = page.relative_to(vault).as_posix()
    raw_text = page.read_text(encoding="utf-8")
    text = raw_text.lstrip("﻿").replace("\r\n", "\n")

    is_system = page.name in SYSTEM_FILES
    fm, body = split_frontmatter(text)
    if fm is not None and scalar(fm.get("author", "")) == "me":
        report.error(where, "author: me — Claude must not edit this note")
    if needs_schema(where):
        for problem in page_problems(raw_text, where):
            report.error(where, problem)

    prose = strip_code(body if fm is not None else text)
    for m in WIKILINK_RE.finditer(prose):
        hits = resolve_link(m.group(1), by_name, rel_paths)
        if hits == 0:
            report.error(where, f"broken link [[{m.group(1)}]]")
        elif hits > 1:
            report.error(where, f"ambiguous link [[{m.group(1)}]] ({hits} matches)")

    if is_system:
        return
    sources = list(given)
    for m in WIKILINK_RE.finditer((fm or {}).get("sources", "")):
        if m.group(1).strip().startswith("raw/"):
            text = raw.get(m.group(1))
            if text is not None:
                sources.append(text)
    quotes = [q for m in QUOTE_RE.finditer(prose)
              if len((q := m.group(1) or m.group(2)).split()) >= MIN_QUOTE_WORDS]
    if quotes and not sources:
        report.note(f"{where}: no readable source text; quote check skipped")
        return
    head = None
    for quote in quotes:
        nq = normalize(quote)
        if any(nq in s for s in sources):
            continue
        if head is None:
            head = normalize(head_version(vault, where) or "")
        report.warn(where, f"quote not found verbatim in source text: \"{quote[:70]}\"",
                    preexisting=bool(head) and nq in head)


def check_vault(vault: Path, files: list[Path], report: Report) -> None:
    for stem, paths in duplicate_basenames(vault, files):
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
    given = [normalize(Path(s).read_text(encoding="utf-8", errors="replace"))
             for s in args.source_text]
    raw = SourceTexts(vault, report)

    for p in args.pages:
        page = Path(p)
        page = page if page.is_absolute() else vault / page
        if not page.exists():
            report.error(p, "page does not exist")
            continue
        check_page(page.resolve(), vault, by_name, rel_paths, given, raw, report)
    check_vault(vault, files, report)

    pre = f" ({report.preexisting} pre-existing)" if report.preexisting else ""
    print(f"\n{report.errors} error(s), {report.warnings} warning(s){pre}")
    sys.exit(1 if report.errors else 0)


if __name__ == "__main__":
    main()
