#!/usr/bin/env python3
"""PDF helper for the ingest skill.

Subcommands:
  info <pdf>                          page count, whether pypdf is available
  text <pdf> --out <txt>              per-page text with "=== page N ===" markers
  candidates <pdf> [--min-chars 50]   pages worth a native (text + image) read, with reasons
  extract <pdf> <pages> --out <pdf>   copy pages (e.g. "3,5,7-9", max 10) into one small PDF

Requires pypdf (optional dependency of the kit). Without it, every subcommand except
`info` exits with code 3, and the skill falls back to native Read for PDFs of <= 10 pages.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import pypdf
except ImportError:  # optional dependency
    pypdf = None

MAX_NATIVE_PAGES = 10
EXIT_NO_PYPDF = 3

TABLE_FIG_RE = re.compile(r"\b(table|fig\.?|figure)\s*\d+", re.IGNORECASE)


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


def cmd_info(args: argparse.Namespace) -> None:
    path = Path(args.pdf)
    _read_pdf_header(path)
    info = {"file": str(path), "bytes": path.stat().st_size, "pypdf": pypdf is not None}
    if pypdf is not None:
        info["pages"] = len(pypdf.PdfReader(str(path)).pages)
        info["pypdf_version"] = pypdf.__version__
    print(json.dumps(info, indent=2))


def cmd_text(args: argparse.Namespace) -> None:
    _require_pypdf()
    path = Path(args.pdf)
    _read_pdf_header(path)
    texts = _page_texts(path)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        for i, text in enumerate(texts, start=1):
            f.write(f"=== page {i} ===\n{text.strip()}\n\n")
    total = sum(len(t) for t in texts)
    print(json.dumps({"pages": len(texts), "chars": total, "out": str(out)}, indent=2))


def cmd_candidates(args: argparse.Namespace) -> None:
    _require_pypdf()
    path = Path(args.pdf)
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
        if clean.endswith(":"):
            reasons.append("ends-with-colon")
        if _looks_garbled(text):
            reasons.append("garbled")
        if reasons:
            pages.append({"page": i + 1, "reasons": reasons, "select": True,
                          "chars": len(clean), "preview": clean[:80]})
    selected = [p["page"] for p in pages if p["select"]]
    print(json.dumps({"total_pages": len(texts), "selected": selected,
                      "native_reads_needed": -(-len(selected) // MAX_NATIVE_PAGES),
                      "pages": pages}, indent=2, ensure_ascii=False))


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
    path = Path(args.pdf)
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

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
