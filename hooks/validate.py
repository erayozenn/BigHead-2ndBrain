#!/usr/bin/env python3
"""PostToolUse validator for BigHead 2ndBrain vaults.

After a Write or Edit of a vault page, checks that page against the schema
(lib/vault_schema.py: frontmatter keys and values, dates, summary callout,
encoding). Problems go back to Claude as a "block" decision with the list,
so it fixes the page in the same turn. The file is already written; this
hook cannot undo it.

Skipped: paths outside a vault, raw/, notes/, system files, `author: me`.
Failure mode: never blocks on its own errors (warning on stderr, exit 1).

Standard library only; Python 3.10+.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from vault_schema import find_vault, needs_schema, page_problems  # noqa: E402


def main() -> int:
    try:
        event = json.load(sys.stdin)
        path = (event.get("tool_input") or {}).get("file_path")
        if not path:
            return 0
        if not os.path.isabs(path) and event.get("cwd"):
            path = os.path.join(event["cwd"], path)
        page = Path(path).resolve()
        vault = find_vault(page.parent)
        if vault is None or not page.is_file():
            return 0
        rel = page.relative_to(vault).as_posix()
        if not needs_schema(rel):
            return 0
        problems = page_problems(page.read_text(encoding="utf-8", errors="replace"), rel)
        if problems:
            print(json.dumps({
                "decision": "block",
                "reason": f"[bighead validator] {rel} breaks the vault schema "
                          "(see the vault's CLAUDE.md, Frontmatter). Fix it now:\n- "
                          + "\n- ".join(problems),
            }))
        return 0
    except Exception as exc:
        print(f"[bighead validator] warning: validator error ({exc!r}); page not checked",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
