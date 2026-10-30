"""Tests for lib/vault_schema.py. Run: python -m unittest discover lib/tests"""

import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vault_schema import needs_schema, page_problems  # noqa: E402

TODAY = dt.date(2026, 10, 30)
SUMMARY = ("> [!summary]- For future agent\n"
           "> What: a page. Why kept: a test. Goes stale: {stale}.\n")


def page(fm_overrides=None, drop=(), stale="never", body=None):
    fm = {"type": "concept", "status": "draft", "created": "2026-10-29",
          "updated": "2026-10-30", "tags": "[]", "aliases": "[]",
          "sources": '["[[raw/x.pdf]]"]', "author": "claude", "sensitivity": "public"}
    fm.update(fm_overrides or {})
    lines = [f"{k}: {v}" for k, v in fm.items() if k not in drop]
    text = body if body is not None else SUMMARY.format(stale=stale)
    return "---\n" + "\n".join(lines) + "\n---\n" + text + "\nBody.\n"


def problems(text, rel="wiki/concepts/a.md"):
    return page_problems(text, rel, TODAY)


class PageProblemsTest(unittest.TestCase):
    def test_valid_page(self):
        self.assertEqual(problems(page()), [])
        self.assertEqual(problems(page(stale="when a second source is ingested")), [])
        self.assertEqual(problems(page(stale="2026-10")), [])

    def test_missing_frontmatter_and_keys(self):
        self.assertEqual(problems("# Title\n"), ["missing frontmatter"])
        self.assertIn("frontmatter missing keys: aliases, sources", problems(page(drop=("aliases", "sources"))))
        self.assertIn("frontmatter missing keys: source_type, authority",
                      problems(page({"type": "source"})))

    def test_enum_values(self):
        out = problems(page({"status": "done", "type": '"concept"'}))
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].startswith("status: 'done'"))

    def test_dates(self):
        self.assertTrue(any("not a valid" in p for p in problems(page({"created": "2026-13-01"}))))
        self.assertTrue(any("in the future" in p for p in problems(page({"updated": "2026-11-01"}))))
        self.assertTrue(any("before created" in p for p in problems(page({"created": "2026-10-30",
                                                                            "updated": "2026-10-01"}))))

    def test_summary(self):
        self.assertTrue(any("must follow" in p for p in problems(page(body="# Title\n"))))
        self.assertTrue(any("needs 'What" in p for p in problems(page(body="> [!summary]- For future agent\n> hi\n"))))
        self.assertTrue(any("has passed" in p for p in problems(page(stale="2026-09"))))
        self.assertEqual(problems(page(stale="when the post (dated 2024-12) is revised")), [])

    def test_encoding(self):
        out = problems("﻿" + page().replace("\n", "\r\n"))
        self.assertIn("file starts with a BOM", out)
        self.assertIn("CRLF line endings (vault files use LF)", out)

    def test_author_me_skipped(self):
        self.assertEqual(problems(page({"author": "me"}, drop=("aliases",), body="# Mine\n")), [])

    def test_needs_schema(self):
        self.assertTrue(needs_schema("wiki/concepts/a.md"))
        self.assertTrue(needs_schema("projects/p.md"))
        for rel in ("raw/a.md", "notes/daily/d.md", "hot.md", "wiki/source-register.md", "wiki/a.txt"):
            self.assertFalse(needs_schema(rel), rel)


if __name__ == "__main__":
    unittest.main()
