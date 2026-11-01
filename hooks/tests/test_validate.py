"""Tests for hooks/validate.py. Run: python -m unittest discover hooks/tests"""

import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import unittest

VALIDATE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validate.py")
TODAY = dt.date.today().isoformat()
GOOD = f"""---
type: concept
status: draft
created: {TODAY}
updated: {TODAY}
tags: []
aliases: []
sources: []
author: claude
sensitivity: public
---
> [!summary]- For future agent
> What: a page. Why kept: a test. Goes stale: never.

Body.
"""


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def run_validate(path, cwd=None):
    event = {"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": path}}
    return subprocess.run([sys.executable, VALIDATE], input=json.dumps(event), capture_output=True,
                          text=True, cwd=cwd, timeout=30)


class ValidateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = os.path.join(self.tmp.name, "vault")
        write(os.path.join(self.vault, "CLAUDE.md"), "# Vault Schema & Rules (template v0.2)\n")
        os.makedirs(os.path.join(self.vault, "raw"))

    def tearDown(self):
        self.tmp.cleanup()

    def v(self, *parts):
        return os.path.join(self.vault, *parts)

    def assertSilent(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_good_page_silent(self):
        write(self.v("wiki", "concepts", "good.md"), GOOD)
        self.assertSilent(run_validate(self.v("wiki", "concepts", "good.md")))

    def test_bad_page_blocked_with_reasons(self):
        write(self.v("wiki", "concepts", "bad.md"), GOOD.replace("status: draft\n", "").replace("> [!summary]", "# x"))
        result = run_validate(self.v("wiki", "concepts", "bad.md"))
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertEqual(out["decision"], "block")
        self.assertIn("wiki/concepts/bad.md", out["reason"])
        self.assertIn("missing keys: status", out["reason"])
        self.assertIn("summary callout", out["reason"])

    def test_crlf_and_bad_encoding_blocked(self):
        path = self.v("wiki", "concepts", "enc.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        for data, reason in ((GOOD.replace("\n", "\r\n").encode(), "CRLF"),
                             ((GOOD + "İğüş\n").encode("cp1254"), "not valid UTF-8")):
            with open(path, "wb") as f:
                f.write(data)
            result = run_validate(path)
            self.assertEqual(json.loads(result.stdout)["decision"], "block")
            self.assertIn(reason, json.loads(result.stdout)["reason"])

    # Regressions from the 2026-11-01 black-box test of hooks and cards.
    def test_summary_callout_shape_blocked(self):
        path = self.v("wiki", "concepts", "shape.md")
        cases = {
            "blank line": GOOD.replace("---\n> [!summary]", "---\n\n> [!summary]"),
            "wrong title": GOOD.replace("For future agent", "Summary"),
            "no fold marker": GOOD.replace("[!summary]-", "[!summary]"),
            "bad stale value": GOOD.replace("Goes stale: never.", "Goes stale: soon."),
        }
        for name, text in cases.items():
            with self.subTest(name):
                write(path, text)
                self.assertEqual(json.loads(run_validate(path).stdout)["decision"], "block")

    def test_valid_stale_values_silent(self):
        path = self.v("wiki", "concepts", "stale.md")
        for value in ("never.", "when the kit changes.", "2099-01.", "2099-01"):
            with self.subTest(value):
                write(path, GOOD.replace("never.", value))
                self.assertSilent(run_validate(path))

    def test_author_me_with_space_before_colon_silent(self):
        write(self.v("projects", "spaced.md"), "---\nauthor : me\n---\n# Mine\n")
        self.assertSilent(run_validate(self.v("projects", "spaced.md")))

    def test_skipped_paths(self):
        for rel in (("raw", "web", "a.md"), ("notes", "n.md"), ("hot.md",), ("wiki", "a.txt")):
            write(self.v(*rel), "no frontmatter\n")
            self.assertSilent(run_validate(self.v(*rel)))

    def test_author_me_silent(self):
        write(self.v("projects", "mine.md"), "---\nauthor: me\n---\n# Mine\n")
        self.assertSilent(run_validate(self.v("projects", "mine.md")))

    def test_outside_vault_silent(self):
        other = os.path.join(self.tmp.name, "other", "page.md")
        write(other, "no frontmatter\n")
        self.assertSilent(run_validate(other))

    def test_bad_json_never_blocks(self):
        result = subprocess.run([sys.executable, VALIDATE], input="nope", capture_output=True,
                                text=True, cwd=self.vault, timeout=30)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
