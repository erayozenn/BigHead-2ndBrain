#!/usr/bin/env python3
"""PDF helper for the ingest skill.

Subcommands:
  info <pdf>                          page count, whether pypdf is available
  text <pdf> --out <txt> [--skip-references]
                                      per-page text with "=== page N ===" markers, plus an
                                      estimated token count; optionally drop the bibliography
  candidates <pdf> [--min-chars 50]   pages worth a native (text + image) read, with reasons
  extract <pdf> <pages> --out <pdf>   copy pages (e.g. "3,5,7-9", max 10) into one small PDF
  cache --vault <dir> <pdf> [...]     write the text of raw/ PDFs to <vault>/.cache/raw-text/
  cache --vault <dir> --all [--prune] cache every raw/ PDF the wiki cites; report PDFs not yet
                                      ingested (never cached) and orphaned cache files
                                      (deleted only with --prune)

<pdf> may be a path or a file:// URL (percent-encoding is decoded).

The cache mirrors raw/: raw/web/x.pdf -> .cache/raw-text/web/x.pdf.txt, same "=== page N ==="
format as `text`, so Grep hits carry page numbers. It is derived data: gitignored, rebuilt per
machine, skipped when the PDF's size and mtime are unchanged (manifest.json).

Requires pypdf (optional dependency of the kit). Without it, every subcommand except
`info` exits with code 3, and the skill falls back to native Read for PDFs of <= 10 pages.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

try:
    import pypdf
except ImportError:  # optional dependency
    pypdf = None

MAX_NATIVE_PAGES = 10
EXIT_NO_PYPDF = 3

TABLE_FIG_RE = re.compile(r"\b(table|fig\.?|figure)\s*\d+", re.IGNORECASE)
NUMERIC_TOKEN_RE = re.compile(r"^[\d.,/%:()–-]*\d[\d.,/%:()–-]*$")
REFERENCES_RE = re.compile(r"^(\d+\.?\s*)?(references|bibliography)$", re.IGNORECASE)
# First appendix heading after the bibliography: "Appendix", "Appendices ...", "A Some Title".
APPENDIX_RE = re.compile(r"^(?i:appendix|appendices)\b|^A\.?\s+[A-Z][A-Za-z]")
SHORT_PAGE_CHARS = 200   # a page this short after a "...:" line probably shows an image
RUN_MIN_PAGES = 3        # consecutive pages with the same title = a screenshot run


def _pdf_path(arg: str) -> Path:
    if arg.lower().startswith("file:"):
        return Path(url2pathname(urlparse(arg).path))  # also decodes %XX
    return Path(arg)


def _require_pypdf() -> None:
    if pypdf is None:
        print("pypdf is not installed. Install it with: pip install pypdf", file=sys.stderr)
        sys.exit(EXIT_NO_PYPDF)


def _read_pdf_header(path: Path) -> None:
    with path.open("rb") as f:
        if f.read(5) != b"%PDF-":
            print(f"{path} is not a PDF (missing %PDF- header)", file=sys.stderr)
            sys.exit(2)


def _page_texts(path: Path) -> list[str]:
    reader = pypdf.PdfReader(str(path))
    texts = []
    for page in reader.pages:
        try:
            texts.append(page.extract_text() or "")
        except Exception as exc:  # broken content streams happen; keep going
            texts.append(f"[text extraction failed: {exc}]")
    return texts


def _first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return " ".join(line.split()).lower()
    return ""


def _looks_garbled(text: str) -> bool:
    stripped = "".join(text.split())
    if len(stripped) < 50:
        return False
    if "�" in text:
        return True
    readable = sum(ch.isalnum() or ch in ".,;:()-'\"%" for ch in stripped)
    return readable / len(stripped) < 0.7


def _table_like(text: str) -> bool:
    """At least 3 lines that are mostly numbers: frequency tables, results grids."""
    rows = 0
    for line in text.splitlines():
        tokens = line.split()
        numeric = sum(bool(NUMERIC_TOKEN_RE.match(t)) for t in tokens)
        if numeric >= 2 and numeric / len(tokens) >= 0.4:
            rows += 1
    return rows >= 3


def _colon_then_little(text: str, clean: str) -> bool:
    """A "...the following result:" line on a short page: the content is probably an image."""
    if len(clean) >= SHORT_PAGE_CHARS:
        return False
    return any(line.strip().endswith(":") for line in text.splitlines()[:-1])


def _runs(texts: list[str], selected: set[int]) -> list[dict]:
    """Groups of >= RUN_MIN_PAGES consecutive pages with the same title (GUI walkthroughs)."""
    runs, start = [], 0
    titles = [_first_line(t) for t in texts]
    for i in range(1, len(texts) + 1):
        if i < len(texts) and titles[i] and titles[i] == titles[start]:
            continue
        pages = list(range(start + 1, i + 1))
        hits = [p for p in pages if p in selected]
        if len(pages) >= RUN_MIN_PAGES and hits and titles[start]:
            runs.append({"pages": f"{pages[0]}-{pages[-1]}", "title": titles[start][:60],
                         "selected_in_run": hits})
        start = i
    return runs


def cmd_info(args: argparse.Namespace) -> None:
    path = _pdf_path(args.pdf)
    _read_pdf_header(path)
    info = {"file": str(path), "bytes": path.stat().st_size, "pypdf": pypdf is not None}
    if pypdf is not None:
        info["pages"] = len(pypdf.PdfReader(str(path)).pages)
        info["pypdf_version"] = pypdf.__version__
    print(json.dumps(info, indent=2))


def _find_references(texts: list[str]) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """(page, line) where the bibliography starts and where it ends (exclusive), 0-based.

    The end is the first appendix heading after it, else the end of the document.
    Headings on page 1 are ignored (tables of contents, abstracts).
    """
    start = None
    for p, text in enumerate(texts[1:], start=1):
        for ln, line in enumerate(text.splitlines()):
            if REFERENCES_RE.match(line.strip()):
                start = (p, ln)
                break
        if start:
            break
    if start is None:
        return None
    for p in range(start[0], len(texts)):
        lines = texts[p].splitlines()
        first = start[1] + 1 if p == start[0] else 0
        for ln in range(first, len(lines)):
            line = lines[ln].strip()
            if APPENDIX_RE.match(line) and len(line.split()) <= 10 and not line.endswith("."):
                return start, (p, ln)
    return start, (len(texts), 0)


def cmd_text(args: argparse.Namespace) -> None:
    _require_pypdf()
    path = _pdf_path(args.pdf)
    _read_pdf_header(path)
    texts = _page_texts(path)
    skipped = None
    if args.skip_references:
        span = _find_references(texts)
        if span:
            (sp, sl), (ep, el) = span
            dropped = 0
            for p in range(sp, min(ep + 1, len(texts))):
                lines = texts[p].splitlines()
                lo = sl if p == sp else 0
                hi = el if p == ep else len(lines)
                dropped += sum(len(x) + 1 for x in lines[lo:hi])
                marker = [f"[references skipped: pages {sp + 1}-{min(ep + 1, len(texts))}]"] \
                    if p == sp else []
                texts[p] = "\n".join(lines[:lo] + marker + lines[hi:])
            skipped = {"from_page": sp + 1, "to_page": min(ep + 1, len(texts)),
                       "chars_dropped": dropped}
    out = Path(args.out)
    _write_pages(out, texts)
    total = sum(len(t) for t in texts)
    # ~4 chars per token for English prose; Read truncates around 25k tokens.
    result = {"pages": len(texts), "chars": total, "est_tokens": total // 4, "out": str(out)}
    if args.skip_references:
        result["references_skipped"] = skipped or "no References heading found"
    print(json.dumps(result, indent=2))


def cmd_candidates(args: argparse.Namespace) -> None:
    _require_pypdf()
    path = _pdf_path(args.pdf)
    _read_pdf_header(path)
    texts = _page_texts(path)
    pages = []
    for i, text in enumerate(texts):
        clean = " ".join(text.split())
        reasons = []
        if len(clean) < args.min_chars:
            next_title = _first_line(texts[i + 1]) if i + 1 < len(texts) else ""
            if clean and next_title and clean.lower() == next_title:
                # Section divider: its only text is the next slide's title.
                pages.append({"page": i + 1, "reasons": ["section-divider"], "select": False,
                              "chars": len(clean), "preview": clean[:80]})
                continue
            reasons.append("short-text")
        if TABLE_FIG_RE.search(clean):
            reasons.append("table-or-figure")
        elif _table_like(text):
            reasons.append("table-like")
        if clean.endswith(":"):
            reasons.append("ends-with-colon")
        elif _colon_then_little(text, clean):
            reasons.append("colon-then-little-text")
        if _looks_garbled(text):
            reasons.append("garbled")
        if reasons:
            pages.append({"page": i + 1, "reasons": reasons, "select": True,
                          "chars": len(clean), "preview": clean[:80]})
    selected = [p["page"] for p in pages if p["select"]]
    print(json.dumps({"total_pages": len(texts), "selected": selected,
                      "native_reads_needed": -(-len(selected) // MAX_NATIVE_PAGES),
                      # Offer each run as one item the user can keep or drop at once.
                      "screenshot_runs": _runs(texts, set(selected)),
                      "pages": pages}, indent=2, ensure_ascii=False))


CACHE_DIR = Path(".cache") / "raw-text"
RAW_PDF_LINK_RE = re.compile(r"\[\[(raw/[^\]|#]+?\.pdf)(?:[#|][^\]]*)?\]\]", re.IGNORECASE)


def _write_pages(out: Path, texts: list[str]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        for i, text in enumerate(texts, start=1):
            f.write(f"=== page {i} ===\n{text.strip()}\n\n")


def _cited_pdfs(vault: Path) -> set[str]:
    """raw/ PDFs linked anywhere in wiki/ (pages, frontmatter, source register) = ingested."""
    cited = set()
    for page in (vault / "wiki").rglob("*.md"):
        for m in RAW_PDF_LINK_RE.finditer(page.read_text(encoding="utf-8", errors="replace")):
            cited.add(m.group(1).strip())
    return cited


def cmd_cache(args: argparse.Namespace) -> None:
    _require_pypdf()
    vault = Path(args.vault).resolve()
    raw, cache = vault / "raw", vault / CACHE_DIR
    manifest_path = cache / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    if not args.all and not args.pdfs:
        print("give PDF paths under raw/, or --all", file=sys.stderr)
        sys.exit(2)
    if args.all:
        cited = _cited_pdfs(vault)
        all_pdfs = sorted(p.relative_to(vault).as_posix() for p in raw.rglob("*")
                          if p.is_file() and p.suffix.lower() == ".pdf")
        targets = [p for p in all_pdfs if p in cited]
        not_ingested = [p for p in all_pdfs if p not in cited]
        missing = sorted(cited - set(all_pdfs))
    else:
        targets, not_ingested, missing = [], [], []
        for arg in args.pdfs:
            path = _pdf_path(arg).resolve()
            if raw not in path.parents:
                print(f"{arg} is not under {raw}; only raw/ files are cached", file=sys.stderr)
                sys.exit(2)
            targets.append(path.relative_to(vault).as_posix())

    written, unchanged = [], []
    for rel in targets:
        src = vault / rel
        _read_pdf_header(src)
        stat = src.stat()
        stamp = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
        key = Path(rel).relative_to("raw").as_posix()
        out = cache / f"{key}.txt"
        if not args.force and out.exists() and \
                {k: manifest.get(key, {}).get(k) for k in stamp} == stamp:
            unchanged.append(rel)
            continue
        texts = _page_texts(src)
        _write_pages(out, texts)
        manifest[key] = {**stamp, "pages": len(texts)}
        written.append(rel)

    # Orphans: cache entries whose raw file is gone (e.g. moved to archive/).
    orphans = sorted(k for k in manifest if not (raw / k).exists())
    pruned = []
    if args.prune:
        for key in orphans:
            (cache / f"{key}.txt").unlink(missing_ok=True)
            del manifest[key]
            pruned.append(key)
    cache.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8", newline="\n")
    print(json.dumps({"cache": str(cache), "written": written, "unchanged": unchanged,
                      "not_ingested_skipped": not_ingested, "cited_but_missing": missing,
                      "orphans": [] if args.prune else orphans, "pruned": pruned},
                     indent=2, ensure_ascii=False))


def _parse_pages(spec: str, count: int) -> list[int]:
    result: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = (int(x) for x in part.split("-", 1))
            result.extend(range(start, end + 1))
        else:
            result.append(int(part))
    bad = [p for p in result if p < 1 or p > count]
    if bad:
        print(f"pages out of range 1..{count}: {bad}", file=sys.stderr)
        sys.exit(2)
    return result


def cmd_extract(args: argparse.Namespace) -> None:
    _require_pypdf()
    path = _pdf_path(args.pdf)
    _read_pdf_header(path)
    reader = pypdf.PdfReader(str(path))
    pages = _parse_pages(args.pages, len(reader.pages))
    if len(pages) > MAX_NATIVE_PAGES:
        print(f"{len(pages)} pages requested; native Read takes at most {MAX_NATIVE_PAGES}. "
              "Split into several extracts.", file=sys.stderr)
        sys.exit(2)
    writer = pypdf.PdfWriter()
    for p in pages:
        writer.add_page(reader.pages[p - 1])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as f:
        writer.write(f)
    # Page k of the extract is page pages[k-1] of the original.
    print(json.dumps({"out": str(out), "original_pages": pages}, indent=2))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("info")
    p.add_argument("pdf")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("text")
    p.add_argument("pdf")
    p.add_argument("--out", required=True)
    p.add_argument("--skip-references", action="store_true",
                   help="drop the bibliography (from 'References' to the first appendix heading)")
    p.set_defaults(func=cmd_text)

    p = sub.add_parser("candidates")
    p.add_argument("pdf")
    p.add_argument("--min-chars", type=int, default=50)
    p.set_defaults(func=cmd_candidates)

    p = sub.add_parser("extract")
    p.add_argument("pdf")
    p.add_argument("pages")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("cache")
    p.add_argument("pdfs", nargs="*")
    p.add_argument("--vault", default=".")
    p.add_argument("--all", action="store_true", help="every raw/ PDF cited in wiki/")
    p.add_argument("--prune", action="store_true",
                   help="delete cache files whose raw PDF no longer exists (ask the user first)")
    p.add_argument("--force", action="store_true", help="rebuild even if unchanged")
    p.set_defaults(func=cmd_cache)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
