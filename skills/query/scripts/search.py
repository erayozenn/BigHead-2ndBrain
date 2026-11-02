#!/usr/bin/env python3
"""Rank a vault's wiki pages, or chunks of its raw sources, for a query. Read-only: no index is
written. Standard library only.

Usage:
  search.py --vault <dir> --query "<text>" [--method grep|bm25|bm25-tr] [--top 5] [--prefix 4]
            [--corpus wiki|raw]

Corpora:
  wiki  pages under wiki/ (default)
  raw   chunks of raw/ text: Markdown and .txt files split at headings, PDFs through their cached
        text in .cache/raw-text/ split at pages; each chunk at most CHUNK_WORDS words. The heading
        path counts like a page name. A PDF with no cached text is named on stderr and skipped.
        Results: {"chunk", "source", "heading", "score", "text"}.

Methods:
  grep     most distinct query terms found as substrings, then most found in the name or aliases
  bm25     Okapi BM25 on lowercased words
  bm25-tr  BM25 with Turkish letters folded to ASCII and words cut to their first --prefix letters
           (0 keeps whole words)

Prints {"method": ..., "results": [{"page": <stem>, "score": <number>}, ...]}, best first, and only
pages that match. The page name and aliases count NAME_WEIGHT times; other frontmatter does not
count. Exit codes: 0 reported (even with no results), 1 no wiki/ (or raw/) folder, 2 bad arguments.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from vault_schema import from_msys, read_page, split_frontmatter  # noqa: E402

K1 = 1.2
B = 0.75
NAME_WEIGHT = 3
DEFAULT_PREFIX = 4
METHODS = ("grep", "bm25", "bm25-tr")
WORD_RE = re.compile(r"[^\W_]+")
ALIASES_KEY_RE = re.compile(r"^aliases\s*:\s*(.*)$")
BLOCK_ITEM_RE = re.compile(r"^\s*-\s+(.*)$")
STOPWORDS = frozenset("""
a an and are as at be by can did do does for from has have how i if in is it its my of on or
should that the this to was we what when where which who why will with you
acaba ama bana bir biz bu da de daha en gibi hangi hem her için ile kadar kim mi mı mu mü
nasıl ne neden niye o olan veya ve ya
""".split())


CHUNK_WORDS = 200
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
PDF_PAGE_RE = re.compile(r"^=== page (\d+) ===$")
RAW_TEXT_SUFFIXES = (".md", ".txt")
CACHE_DIR = Path(".cache") / "raw-text"


@dataclass
class Page:
    stem: str  # the page name, or a chunk id "<source>#<n>"
    name: str  # the page name and aliases, or a chunk's heading path
    body: str
    source: str = ""
    heading: str = ""


def sections(text: str, markdown: bool) -> list[tuple[str, str]]:
    """(heading path, text) in file order: Markdown at headings, cached PDF text at page markers."""
    out: list[tuple[str, list[str]]] = [("", [])]
    path: list[tuple[int, str]] = []
    fence = ""
    for line in text.splitlines():
        marker = line.lstrip()[:3]
        if markdown and marker in ("```", "~~~") and (not fence or marker == fence):
            fence = "" if fence else marker
        heading = HEADING_RE.match(line) if markdown and not fence else None
        page = None if markdown else PDF_PAGE_RE.match(line)
        if heading:
            level = len(heading.group(1))
            path = [item for item in path if item[0] < level] + [(level, heading.group(2))]
            out.append((" > ".join(title for _, title in path), []))
        elif page:
            out.append((f"page {page.group(1)}", []))
        else:
            out[-1][1].append(line)
    return [(heading, "\n".join(lines)) for heading, lines in out]


def chunk_file(source: str, text: str, markdown: bool, start: int) -> list[Page]:
    chunks = []
    for heading, body in sections(text, markdown):
        words = body.split()
        if not words and not heading:
            continue
        for i in range(0, max(len(words), 1), CHUNK_WORDS):
            start += 1
            chunks.append(Page(f"{source}#{start}", heading, " ".join(words[i:i + CHUNK_WORDS]),
                               source, heading))
    return chunks


def read_text(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"search: skipped {path.name}: {error.__class__.__name__}", file=sys.stderr)
        return None
    return text.removeprefix("﻿").replace("\r\n", "\n")


def load_raw_chunks(vault: Path) -> list[Page]:
    chunks: list[Page] = []
    for path in sorted((vault / "raw").rglob("*")):
        if not path.is_file():
            continue
        source = path.relative_to(vault).as_posix()
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            cached = vault / CACHE_DIR / (path.relative_to(vault / "raw").as_posix() + ".txt")
            if not cached.is_file():
                print(f"search: no cached text for {source}; skipped", file=sys.stderr)
                continue
            text, markdown = read_text(cached), False
        elif suffix in RAW_TEXT_SUFFIXES:
            text, markdown = read_text(path), suffix == ".md"
            if text is not None and markdown:
                text = split_frontmatter(text)[1]
        else:
            continue
        if text is not None:
            chunks += chunk_file(source, text, markdown, 0)
    return chunks


def aliases_value(text: str) -> str:
    """The aliases key in either form: `aliases: [a, b]`, or the block list Obsidian writes."""
    end = text.find("\n---", 4) if text.startswith("---\n") else -1
    values: list[str] = []
    in_aliases = False
    for line in text[4:end].splitlines() if end != -1 else []:
        item = BLOCK_ITEM_RE.match(line)
        if in_aliases and item:
            values.append(item.group(1))
            continue
        key = ALIASES_KEY_RE.match(line)
        in_aliases = bool(key)
        if key:
            values.append(key.group(1))
    return " ".join(values)


def load_pages(vault: Path) -> list[Page]:
    pages = []
    for path in sorted((vault / "wiki").rglob("*.md")):
        if path.stem == "source-register":
            continue
        text, problems = read_page(path)
        if problems:
            print(f"search: skipped {path.name}: {problems[0]}", file=sys.stderr)
            continue
        text = text.removeprefix("﻿").replace("\r\n", "\n")
        _, body = split_frontmatter(text)
        pages.append(Page(path.stem, f"{path.stem.replace('-', ' ')} {aliases_value(text)}", body))
    return pages


def fold(text: str) -> str:
    """Turkish-aware lowercase with diacritics removed, so that ışık, ISIK and isik all match."""
    text = text.replace("İ", "i").replace("I", "i").replace("ı", "i").lower()
    return "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))


FOLDED_STOPWORDS = frozenset(fold(word) for word in STOPWORDS)


def tokens(text: str, method: str, prefix: int) -> list[str]:
    if method == "bm25-tr":
        words = [w for w in WORD_RE.findall(fold(text)) if w not in FOLDED_STOPWORDS]
        return [w[:prefix] for w in words] if prefix else words
    return [w for w in WORD_RE.findall(text.lower()) if w not in STOPWORDS]


def rank_grep(pages: list[Page], query: str) -> list[tuple[str, float]]:
    terms = set(tokens(query, "grep", 0))
    scored = []
    for page in pages:
        name, body = page.name.lower(), page.body.lower()
        in_name = sum(term in name for term in terms)
        found = sum(term in name or term in body for term in terms)
        if found:
            scored.append((page.stem, found + in_name / (len(terms) + 1)))
    return scored


def rank_bm25(pages: list[Page], query: str, method: str, prefix: int) -> list[tuple[str, float]]:
    terms = set(tokens(query, method, prefix))
    if not terms or not pages:
        return []
    counts = []
    for page in pages:
        count = Counter(tokens(page.body, method, prefix))
        for word in tokens(page.name, method, prefix):
            count[word] += NAME_WEIGHT
        counts.append(count)
    lengths = [sum(count.values()) for count in counts]
    average = sum(lengths) / len(lengths) or 1
    scored = []
    for page, count, length in zip(pages, counts, lengths):
        score = 0.0
        for term in terms & count.keys():
            having = sum(term in other for other in counts)
            idf = math.log(1 + (len(pages) - having + 0.5) / (having + 0.5))
            freq = count[term]
            score += idf * freq * (K1 + 1) / (freq + K1 * (1 - B + B * length / average))
        if score > 0:
            scored.append((page.stem, score))
    return scored


def rank(pages: list[Page], query: str, method: str,
         prefix: int = DEFAULT_PREFIX) -> list[tuple[str, float]]:
    """Every matching page, best first; ties in page-name order, so that results are repeatable."""
    if method == "grep":
        scored = rank_grep(pages, query)
    else:
        scored = rank_bm25(pages, query, method, prefix)
    return sorted(scored, key=lambda item: (-item[1], *id_order(item[0])))


def id_order(stem: str) -> tuple[str, int]:
    """Page names sort as text; chunk ids "<source>#<n>" sort by source, then n as a number."""
    source, _, number = stem.rpartition("#")
    return (source, int(number)) if source and number.isdigit() else (stem, 0)


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise ValueError
    return number


def non_negative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise ValueError
    return number


def vault_path(value: str, folder: str = "wiki") -> Path:
    vault = Path(from_msys(value))
    if not (vault / folder).is_dir():
        print(f"search: no {folder}/ folder in {value}".replace("\n", "\\n"), file=sys.stderr)
        sys.exit(1)
    return vault


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--method", choices=METHODS, default="bm25-tr")
    parser.add_argument("--top", type=positive_int, default=5)
    parser.add_argument("--prefix", type=non_negative_int, default=DEFAULT_PREFIX)
    parser.add_argument("--corpus", choices=("wiki", "raw"), default="wiki")
    args = parser.parse_args()
    if args.corpus == "raw":
        chunks = load_raw_chunks(vault_path(args.vault, "raw"))
        by_id = {chunk.stem: chunk for chunk in chunks}
        ranked = rank(chunks, args.query, args.method, args.prefix)[:args.top]
        results = [{"chunk": cid, "source": by_id[cid].source, "heading": by_id[cid].heading,
                    "score": round(score, 4), "text": by_id[cid].body} for cid, score in ranked]
        print(json.dumps({"method": args.method, "corpus": "raw", "results": results},
                         ensure_ascii=False))
        return
    pages = load_pages(vault_path(args.vault))
    ranked = rank(pages, args.query, args.method, args.prefix)[:args.top]
    print(json.dumps({"method": args.method, "corpus": "wiki",
                      "results": [{"page": stem, "score": round(score, 4)} for stem, score in ranked]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
