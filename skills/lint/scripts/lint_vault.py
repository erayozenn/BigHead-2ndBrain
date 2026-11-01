#!/usr/bin/env python3
"""Mechanical lint of a whole vault. Standard library only. Read-only.

Usage:
  lint_vault.py [--vault <dir>]

Checks (the vault CLAUDE.md "Lint" list, minus the judgment checks):
  ERROR schema problems on every schema page (lib/vault_schema.py: frontmatter keys and
        values, dates, summary callout, past "Goes stale" month, BOM/CRLF)
  ERROR broken or ambiguous wikilinks (all .md outside raw/ except CLAUDE.md, whose links
        are examples; user notes are flagged "report only" — Claude never edits them)
  ERROR duplicate basenames outside raw/ (and wiki vs raw)
  ERROR hot.md over 500 words, index.md over 16 KiB
  WARN  orphan pages (wiki/ pages no other file links to)
  WARN  wiki/ pages missing from index.md
  WARN  project hubs (projects/<name>/<name>.md): missing, wrong type, missing sections,
        over 4 KiB, not in index.md
  WARN  vault CLAUDE.md over 200 lines
  WARN  paths in the vault CLAUDE.md "Layout" table that do not exist (except .cache/)

Exit code 1 if any ERROR, else 0.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from vault_schema import (CLAUDE_MD_MAX_LINES, HOT_MAX_WORDS, INDEX_MAX_BYTES,  # noqa: E402
                          WIKILINK_RE,
                          build_link_index, duplicate_basenames, needs_schema,
                          page_problems, scalar, split_frontmatter, strip_code, vault_files)

LAYOUT_CELL_RE = re.compile(r"^\|\s*([^|]+?)\s*\|")
HUB_SECTIONS = ("Current state", "Next step", "Decisions", "Lessons")
HUB_MAX_BYTES = 4 * 1024


class Report:
    def __init__(self) -> None:
        self.lines: list[tuple[str, str, str]] = []

    def add(self, level: str, where: str, msg: str) -> None:
        self.lines.append((level, where, msg))

    def count(self, level: str) -> int:
        return sum(1 for lv, _, _ in self.lines if lv == level)

    def print(self) -> None:
        for level in ("ERROR", "WARN"):
            for lv, where, msg in sorted(l for l in self.lines if l[0] == level):
                print(f"{lv:<5} {where}: {msg}")


def link_targets(target: str, by_name: dict, vault: Path) -> list[Path]:
    target = target.strip().replace("\\", "/")
    if "/" in target:
        t = vault / target.lstrip("/")
        return [p for p in (t, t.with_name(t.name + ".md")) if p.is_file()][:1]
    return by_name.get(target.lower(), [])


def is_user_note(rel: str, text: str) -> bool:
    fm, _ = split_frontmatter(text.lstrip("﻿").replace("\r\n", "\n"))
    return rel.startswith("notes/") or (fm is not None and scalar(fm.get("author", "")) == "me")


def layout_paths(claude_md: str) -> list[str]:
    section = claude_md.split("## Layout", 1)[-1].split("\n## ", 1)[0]
    paths = []
    for line in section.splitlines():
        m = LAYOUT_CELL_RE.match(line)
        if not m or m.group(1) in ("Path",) or set(m.group(1)) <= set("-: "):
            continue
        for p in m.group(1).split(","):
            p = p.strip().strip("`")
            # .cache/ is derived and created on first use; a fresh vault has none
            if p and "YYYY" not in p and "<" not in p and not p.startswith(".cache"):
                paths.append(p)
    return paths


def check_project_hubs(report: Report, vault: Path, pages: list[Path], indexed: set[str]) -> None:
    """Every folder under projects/ that holds notes needs a well-formed hub page."""
    folders = set()
    for page in pages:
        parts = page.relative_to(vault).parts
        if parts[0] == "projects" and len(parts) >= 3:
            folders.add(parts[1])
    for name in sorted(folders):
        rel = f"projects/{name}/{name}.md"
        hub = vault / rel
        if not hub.is_file():
            report.add("WARN", f"projects/{name}/", f"no hub page {name}.md")
            continue
        text = hub.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        fm, _ = split_frontmatter(text.lstrip("﻿"))
        if fm is None or scalar(fm.get("type", "")) != "project":
            report.add("WARN", rel, "hub page is not type: project")
        for section in HUB_SECTIONS:
            if not re.search(rf"^## {section}\s*$", text, re.MULTILINE):
                report.add("WARN", rel, f"hub page has no '## {section}' section")
        size = hub.stat().st_size
        if size > HUB_MAX_BYTES:
            report.add("WARN", rel, f"hub page is {size / 1024:.1f} KiB (max "
                                    f"{HUB_MAX_BYTES // 1024}); move old items to {name}-history.md")
        if name.lower() not in indexed:
            report.add("WARN", rel, "not listed in index.md")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vault", default=".")
    args = parser.parse_args()

    vault = Path(args.vault).resolve()
    if not (vault / "CLAUDE.md").is_file():
        sys.exit(f"not a vault (no CLAUDE.md): {vault}")
    report = Report()
    files = vault_files(vault)
    by_name, _ = build_link_index(vault, files)
    pages = [f for f in files if f.suffix.lower() == ".md"
             and not f.relative_to(vault).as_posix().startswith("raw/")]
    inbound: dict[Path, int] = defaultdict(int)

    for page in pages:
        rel = page.relative_to(vault).as_posix()
        text = page.read_text(encoding="utf-8", errors="replace")
        user = is_user_note(rel, text)
        if needs_schema(rel):
            for problem in page_problems(text, rel):
                report.add("ERROR", rel, problem)
        if rel == "CLAUDE.md":
            continue  # schema file: its links are examples
        _, body = split_frontmatter(text.lstrip("﻿").replace("\r\n", "\n"))
        for m in WIKILINK_RE.finditer(strip_code(body)):
            hits = link_targets(m.group(1), by_name, vault)
            suffix = " (user note: report only)" if user else ""
            if not hits:
                report.add("ERROR", rel, f"broken link [[{m.group(1)}]]{suffix}")
            elif len(hits) > 1:
                report.add("ERROR", rel, f"ambiguous link [[{m.group(1)}]] ({len(hits)} matches){suffix}")
            else:
                if hits[0].resolve() != page.resolve():
                    inbound[hits[0].resolve()] += 1

    for stem, paths in duplicate_basenames(vault, files):
        report.add("ERROR", "vault", f"duplicate basename '{stem}': {', '.join(paths)}")

    index = vault / "index.md"
    index_text = index.read_text(encoding="utf-8", errors="replace") if index.exists() else ""
    indexed = {m.group(1).strip().lower().rsplit("/", 1)[-1] for m in WIKILINK_RE.finditer(index_text)}
    for page in pages:
        rel = page.relative_to(vault).as_posix()
        if not rel.startswith("wiki/") or not needs_schema(rel):
            continue
        if inbound[page.resolve()] == 0:
            report.add("WARN", rel, "orphan page (no other file links to it)")
        if page.stem.lower() not in indexed:
            report.add("WARN", rel, "not listed in index.md")
    check_project_hubs(report, vault, pages, indexed)

    hot = vault / "hot.md"
    words = len(hot.read_text(encoding="utf-8").split()) if hot.exists() else 0
    if words > HOT_MAX_WORDS:
        report.add("ERROR", "hot.md", f"{words} words (max {HOT_MAX_WORDS})")
    size = index.stat().st_size if index.exists() else 0
    if size > INDEX_MAX_BYTES:
        report.add("ERROR", "index.md", f"{size / 1024:.1f} KiB (max {INDEX_MAX_BYTES // 1024})")

    claude_md = (vault / "CLAUDE.md").read_text(encoding="utf-8", errors="replace")
    n_lines = len(claude_md.splitlines())
    if n_lines > CLAUDE_MD_MAX_LINES:
        report.add("WARN", "CLAUDE.md", f"{n_lines} lines (target under {CLAUDE_MD_MAX_LINES}; "
                                        "longer files reduce adherence)")
    for p in layout_paths(claude_md):
        if not (vault / p).exists():
            report.add("WARN", "CLAUDE.md", f"Layout path does not exist: {p}")

    report.print()
    print(f"\nStats: {len(pages)} pages checked, hot.md {words} words, index.md {size / 1024:.1f} KiB")
    print(f"{report.count('ERROR')} error(s), {report.count('WARN')} warning(s)")
    sys.exit(1 if report.count("ERROR") else 0)


if __name__ == "__main__":
    main()
