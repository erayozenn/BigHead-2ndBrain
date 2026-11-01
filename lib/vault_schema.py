"""Shared vault schema and page checks for the kit's hooks and skill scripts.

Mirrors the "Frontmatter" and summary-callout rules of templates/vault/CLAUDE.md.tmpl;
change both together. Standard library only; Python 3.10+.
"""
from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict
from pathlib import Path

VAULT_MARKER = "# Vault Schema & Rules"
SKIP_DIRS = {".git", ".obsidian", ".claude", ".trash", ".cache", "node_modules"}
SYSTEM_FILES = {"CLAUDE.md", "index.md", "log.md", "hot.md", "Threads.md",
                "CRITICAL_FACTS.md", "rules.md", "source-register.md"}
USER_DIRS = {"raw", "notes"}  # owned by the user: no schema checks
REQUIRED_KEYS = ["type", "status", "created", "updated", "tags", "aliases",
                 "sources", "author", "sensitivity"]
SOURCE_KEYS = ["source_type", "authority"]
ALLOWED = {
    "type": {"source", "concept", "entity", "synthesis", "decision", "note", "project"},
    "status": {"draft", "active", "stable", "archived"},
    "author": {"claude", "me"},
    "sensitivity": {"public", "private"},
    "source_type": {"paper", "course", "transcript", "web", "code", "decision",
                    "conversation", "data"},
    "authority": {"official", "primary", "secondary", "community"},
}
HOT_MAX_WORDS = 500
INDEX_MAX_BYTES = 16 * 1024
CLAUDE_MD_MAX_LINES = 200  # official target per CLAUDE.md file

# `\|` is how Obsidian writes a link alias inside a table cell.
WIKILINK_RE = re.compile(r"!?\[\[([^\]|#^]+?)(?:[#^][^\]|]*)?(?:\\?\|[^\]]*)?\]\]")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SUMMARY_HEAD = "> [!summary]- For future agent"
SUMMARY_LINE_RE = re.compile(r"^>\s*What:.*Why kept:.*Goes stale:\s*(\S.*)$", re.MULTILINE)
STALE_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})\b")  # "Goes stale: 2027-03", not "when ... 2024-12"
STALE_VALUE_RE = re.compile(r"^(never\b|when\s+\S|\d{4}-\d{2}\b)")  # never | when <X> | <YYYY-MM>


def read_page(path: Path) -> tuple[str, list[str]]:
    """A page's text with line endings intact, plus any encoding problem.

    Text-mode reads translate CRLF to LF, which would hide it from page_problems.
    """
    data = path.read_bytes()
    try:
        return data.decode("utf-8"), []
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace"), ["not valid UTF-8 (vault files use UTF-8)"]


def is_vault(folder: Path) -> bool:
    try:
        with open(folder / "CLAUDE.md", encoding="utf-8-sig", errors="replace") as f:
            return (folder / "raw").is_dir() and f.readline().strip().startswith(VAULT_MARKER)
    except OSError:
        return False


def find_vault(path: Path) -> Path | None:
    for folder in [path, *path.parents]:
        if is_vault(folder):
            return folder
    return None


def split_frontmatter(text: str) -> tuple[dict[str, str] | None, str]:
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---", 4)
    if end == -1:
        return None, text
    fm: dict[str, str] = {}
    for line in text[4:end].splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    body = text[end + 4:].split("\n", 1)[1] if "\n" in text[end + 4:] else ""
    return fm, body


def scalar(value: str) -> str:
    """A frontmatter scalar without quotes or a trailing comment."""
    return value.split(" #", 1)[0].strip().strip("'\"")


def strip_code(text: str) -> str:
    return INLINE_CODE_RE.sub("", FENCE_RE.sub("", text))


def needs_schema(rel: str) -> bool:
    """True for pages the schema applies to: .md outside user dirs, not system files."""
    parts = rel.split("/")
    return (rel.endswith(".md") and parts[0] not in USER_DIRS
            and parts[-1] not in SYSTEM_FILES)


def stale_month(body: str) -> tuple[int, int] | None:
    """The (year, month) from a summary's "Goes stale: YYYY-MM", if it names one."""
    m = SUMMARY_LINE_RE.search(body)
    if not m:
        return None
    month = STALE_MONTH_RE.match(m.group(1))
    return (int(month.group(1)), int(month.group(2))) if month else None


def page_problems(raw_text: str, rel: str, today: dt.date | None = None) -> list[str]:
    """Schema problems of one page (rel: vault-relative, forward slashes).

    Covers encoding, frontmatter keys and values, dates and the summary callout.
    Pages with `author: me` get no checks: Claude may not fix them.
    """
    today = today or dt.date.today()
    problems = []
    if raw_text.startswith("﻿"):
        problems.append("file starts with a BOM")
    if "\r\n" in raw_text:
        problems.append("CRLF line endings (vault files use LF)")
    text = raw_text.lstrip("﻿").replace("\r\n", "\n")

    fm, body = split_frontmatter(text)
    if fm is None:
        return problems + ["missing frontmatter"]
    if scalar(fm.get("author", "")) == "me":
        return []

    keys = REQUIRED_KEYS + (SOURCE_KEYS if scalar(fm.get("type", "")) == "source" else [])
    missing = [k for k in keys if k not in fm]
    if missing:
        problems.append(f"frontmatter missing keys: {', '.join(missing)}")
    for key, allowed in ALLOWED.items():
        if key in fm and scalar(fm[key]) not in allowed:
            problems.append(f"{key}: {scalar(fm[key])!r} is not one of {', '.join(sorted(allowed))}")

    dates = {}
    for key in ("created", "updated"):
        if key not in fm:
            continue
        value = scalar(fm[key])
        try:
            if not DATE_RE.match(value):
                raise ValueError
            dates[key] = dt.date.fromisoformat(value)
        except ValueError:
            problems.append(f"{key} is not a valid YYYY-MM-DD date: {fm[key]!r}")
    if "updated" in dates and dates["updated"] > today:
        problems.append(f"updated {dates['updated']} is in the future")
    if len(dates) == 2 and dates["updated"] < dates["created"]:
        problems.append(f"updated {dates['updated']} is before created {dates['created']}")

    summary = SUMMARY_LINE_RE.search(body)
    if body.split("\n", 1)[0].rstrip() != SUMMARY_HEAD:
        problems.append(f"summary callout ({SUMMARY_HEAD}) must follow the frontmatter directly")
    elif not summary:
        problems.append("summary callout needs 'What: ... Why kept: ... Goes stale: ...'")
    elif not STALE_VALUE_RE.match(summary.group(1)):
        problems.append(f"Goes stale must be never, when <X> or YYYY-MM, not {summary.group(1)!r}")
    else:
        stale = stale_month(body)
        if stale and stale < (today.year, today.month):
            problems.append(f"Goes stale date {stale[0]}-{stale[1]:02d} has passed; review the page")
    return problems


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


def duplicate_basenames(vault: Path, files: list[Path]) -> list[tuple[str, list[str]]]:
    """Basenames shared by two .md files outside raw/, or by a wiki page and a raw file."""
    stems: dict[str, list[str]] = defaultdict(list)
    for f in files:
        if f.suffix.lower() == ".md":
            stems[f.stem.lower()].append(f.relative_to(vault).as_posix())
    dups = []
    for stem, paths in sorted(stems.items()):
        outside_raw = [p for p in paths if not p.startswith("raw/")]
        if len(outside_raw) > 1 or (outside_raw and len(paths) > len(outside_raw)):
            dups.append((stem, paths))
    return dups
