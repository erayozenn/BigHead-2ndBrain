"""Tests for lint_vault.py. Run: python -m unittest discover skills/lint/scripts/tests"""

import datetime as dt
import os
import subprocess
import sys
import tempfile
import unittest

LINT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lint_vault.py")
TODAY = dt.date.today().isoformat()


def page(body, stale="never", author="claude"):
    return (f"---\ntype: concept\nstatus: draft\ncreated: {TODAY}\nupdated: {TODAY}\ntags: []\n"
            f"aliases: []\nsources: []\nauthor: {author}\nsensitivity: public\n---\n"
            f"> [!summary]- For future agent\n> What: x. Why kept: y. Goes stale: {stale}.\n\n{body}\n")


def write(root, rel, text):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def run_lint(vault):
    return subprocess.run([sys.executable, LINT, "--vault", vault], capture_output=True,
                          text=True, encoding="utf-8", timeout=60)


class LintTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = self.tmp.name
        write(self.vault, "CLAUDE.md", "# Vault Schema & Rules\n\n## Layout\n| Path | Owner |\n|---|---|\n"
                                       "| raw/ | user |\n| wiki/concepts/, wiki/ghost/ | claude |\n"
                                       "| archive/YYYY-MM/ | shared |\n\n## Rules\nLink [[source-page]].\n")
        write(self.vault, "raw/paper.md", "source\n")
        write(self.vault, "index.md", "# Index\n- [[a]]\n- [[b]]\n")
        write(self.vault, "hot.md", "# Hot\n")
        write(self.vault, "wiki/concepts/a.md", page("See [[b]] and [[raw/paper.md]]."))
        write(self.vault, "wiki/concepts/b.md", page("See [[a]]."))

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_vault(self):
        result = run_lint(self.vault)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("0 error(s), 1 warning(s)", result.stdout)  # wiki/ghost/
        self.assertIn("Layout path does not exist: wiki/ghost/", result.stdout)

    def test_problems_found(self):
        write(self.vault, "wiki/concepts/c.md", page("Broken [[missing]].", stale="2020-01"))
        write(self.vault, "wiki/concepts/paper.md", page("dup"))
        write(self.vault, "notes/mine.md", "---\nauthor: me\n---\nSee [[nowhere]].\n")
        write(self.vault, "hot.md", "word " * 501)
        result = run_lint(self.vault)
        out = result.stdout
        self.assertEqual(result.returncode, 1, out)
        self.assertIn("ERROR wiki/concepts/c.md: broken link [[missing]]", out)
        self.assertIn("Goes stale date 2020-01 has passed", out)
        self.assertIn("ERROR notes/mine.md: broken link [[nowhere]] (user note: report only)", out)
        self.assertIn("duplicate basename 'paper'", out)
        self.assertIn("ERROR hot.md: 501 words", out)
        self.assertIn("WARN  wiki/concepts/c.md: orphan page", out)
        self.assertIn("WARN  wiki/concepts/c.md: not listed in index.md", out)
        self.assertNotIn("source-page", out)  # CLAUDE.md example links are skipped


if __name__ == "__main__":
    unittest.main()
