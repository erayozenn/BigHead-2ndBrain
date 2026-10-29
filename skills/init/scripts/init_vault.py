#!/usr/bin/env python3
"""Create a vault from the kit templates. Standard library only.

Usage:
  init_vault.py --target <dir> --chat-language <lang> --wiki-language <lang>
                [--date YYYY-MM-DD] [--templates <dir>] [--dry-run]

Reads <templates>/manifest.json (default: the kit's templates/ folder), then:
  - creates every directory in "dirs" (plus a .gitkeep in each one that is empty, so git keeps it)
  - copies every file in "files" to its destination, replacing the manifest's placeholders
  - never overwrites: an existing destination file is skipped and reported
Files are written as UTF-8 without BOM, with LF line endings.

Output: one line per action (MKDIR, KEEP, WRITE, SKIP), then a SUMMARY line.
With --dry-run nothing is written; the same lines describe what would happen.
Exit code 0 on success, 2 on a usage or template error (nothing written).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

KIT_TEMPLATES = Path(__file__).resolve().parents[3] / "templates"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(2)


def load_manifest(templates: Path) -> dict:
    path = templates / "manifest.json"
    if not path.is_file():
        fail(f"manifest not found: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    for key in ("placeholders", "dirs", "files"):
        if key not in manifest:
            fail(f"manifest has no '{key}'")
    for src in manifest["files"]:
        if not (templates / src).is_file():
            fail(f"template file missing: {templates / src}")
    return manifest


def render(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace(key, value)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", required=True)
    ap.add_argument("--chat-language", required=True)
    ap.add_argument("--wiki-language", required=True)
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--templates", default=str(KIT_TEMPLATES))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not DATE_RE.match(args.date):
        fail(f"--date must be YYYY-MM-DD, got {args.date!r}")
    for name in ("chat_language", "wiki_language"):
        if not getattr(args, name).strip():
            fail(f"--{name.replace('_', '-')} is empty")

    templates = Path(args.templates).resolve()
    target = Path(args.target).expanduser().resolve()
    kit_root = templates.parent
    if target == kit_root or kit_root in target.parents:
        fail(f"target is inside the kit ({kit_root}); choose a folder outside it")
    if target.exists() and not target.is_dir():
        fail(f"target is not a directory: {target}")

    manifest = load_manifest(templates)
    if manifest.get("never_overwrite") is not True:
        fail("manifest must set never_overwrite: true")
    values = {
        "{{DATE}}": args.date,
        "{{CHAT_LANGUAGE}}": args.chat_language.strip(),
        "{{WIKI_LANGUAGE}}": args.wiki_language.strip(),
    }
    unknown = set(manifest["placeholders"]) - set(values)
    if unknown:
        fail(f"manifest placeholders without a value: {sorted(unknown)}")

    # Render everything first, so a template error writes nothing.
    rendered: list[tuple[Path, str]] = []
    for src, dest in manifest["files"].items():
        text = render((templates / src).read_text(encoding="utf-8-sig"), values)
        left = [k for k in manifest["placeholders"] if k in text]
        if left:
            fail(f"{src}: placeholders left after rendering: {left}")
        rendered.append((target / dest, text))

    if not target.exists():
        state = "does not exist, will be created"
    else:
        existing = sorted(p.name for p in target.iterdir())
        state = "not empty: " + ", ".join(existing) if existing else "empty"
    print(f"TARGET {target} ({state})")

    counts = {"MKDIR": 0, "KEEP": 0, "WRITE": 0, "SKIP": 0}

    def act(kind: str, path: Path, note: str = "") -> None:
        counts[kind] += 1
        rel = path.relative_to(target).as_posix() if path != target else "."
        print(f"{kind} {rel}{'  (' + note + ')' if note else ''}")

    file_dests = {dest for dest, _ in rendered}
    for d in manifest["dirs"]:
        path = target / d
        if path.exists():
            act("KEEP", path, "dir exists")
            continue
        act("MKDIR", path)
        if not args.dry_run:
            path.mkdir(parents=True, exist_ok=True)
        # .gitkeep only if no manifest file lands inside this dir
        if not any(path in f.parents for f in file_dests):
            act("WRITE", path / ".gitkeep")
            if not args.dry_run:
                (path / ".gitkeep").write_bytes(b"")

    for dest, text in rendered:
        if dest.exists():
            act("SKIP", dest, "exists, not overwritten")
            continue
        act("WRITE", dest)
        if not args.dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(text.encode("utf-8"))

    mode = "dry-run, nothing written" if args.dry_run else "done"
    print(f"SUMMARY {mode}: {counts['MKDIR']} dirs created, {counts['KEEP']} dirs kept, "
          f"{counts['WRITE']} files written, {counts['SKIP']} files skipped")


if __name__ == "__main__":
    main()
