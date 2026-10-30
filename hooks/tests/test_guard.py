"""Tests for hooks/guard.py. Run: python -m unittest discover hooks/tests"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

GUARD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "guard.py")


def write(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def run_guard(payload, cwd=None):
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run([sys.executable, GUARD], input=stdin, capture_output=True,
                          text=True, cwd=cwd, timeout=30)


def file_event(path, tool="Edit", key="file_path"):
    return {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {key: path}}


class GuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = os.path.join(self.tmp.name, "vault")
        write(os.path.join(self.vault, "CLAUDE.md"), "# Vault Schema & Rules (template v0.2)\n")
        write(os.path.join(self.vault, "raw", "paper.md"), "source\n")
        write(os.path.join(self.vault, "notes", "mine.md"), "---\ntype: note\nauthor: me\n---\nbody\n")
        write(os.path.join(self.vault, "notes", "quoted.md"), '---\nauthor: "me"  # mine\n---\n')
        write(os.path.join(self.vault, "wiki", "page.md"), "---\nauthor: claude\n---\nauthor: me\n")
        self.other = os.path.join(self.tmp.name, "project")
        write(os.path.join(self.other, "CLAUDE.md"), "# Some project\n")
        write(os.path.join(self.other, "raw", "data.csv"), "a,b\n")

    def tearDown(self):
        self.tmp.cleanup()

    def v(self, *parts):
        return os.path.join(self.vault, *parts)

    def assertDenied(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "deny")

    def assertNoDecision(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_existing_raw_file_denied(self):
        self.assertDenied(run_guard(file_event(self.v("raw", "paper.md"))))
        self.assertDenied(run_guard(file_event(self.v("raw", "paper.md"), tool="Write")))

    def test_new_raw_web_file_allowed(self):
        self.assertNoDecision(run_guard(file_event(self.v("raw", "web", "new.md"), tool="Write")))

    def test_new_raw_file_outside_web_denied(self):
        self.assertDenied(run_guard(file_event(self.v("raw", "new.md"), tool="Write")))
        self.assertDenied(run_guard(file_event(self.v("raw", "web"), tool="Write")))

    def test_author_me_denied(self):
        self.assertDenied(run_guard(file_event(self.v("notes", "mine.md"))))
        self.assertDenied(run_guard(file_event(self.v("notes", "quoted.md"), tool="Write")))

    def test_author_me_outside_frontmatter_ignored(self):
        self.assertNoDecision(run_guard(file_event(self.v("wiki", "page.md"))))

    def test_wiki_and_new_files_allowed(self):
        self.assertNoDecision(run_guard(file_event(self.v("wiki", "new.md"), tool="Write")))
        self.assertNoDecision(run_guard(file_event(self.v("hot.md"))))

    def test_obsidian_denied(self):
        self.assertDenied(run_guard(file_event(self.v(".obsidian", "graph.json"))))

    def test_notebook_path(self):
        self.assertDenied(run_guard(file_event(self.v("raw", "paper.md"), "NotebookEdit", "notebook_path")))

    def test_forward_slash_and_relative_paths(self):
        self.assertDenied(run_guard(file_event(self.v("raw", "paper.md").replace("\\", "/"))))
        event = file_event(os.path.join("raw", "paper.md"))
        event["cwd"] = self.vault
        self.assertDenied(run_guard(event))

    def test_non_vault_untouched(self):
        self.assertNoDecision(run_guard(file_event(os.path.join(self.other, "raw", "data.csv"))))

    def test_no_path_no_decision(self):
        self.assertNoDecision(run_guard({"tool_name": "Edit", "tool_input": {}}))

    def test_bad_json_fails_closed_in_vault_only(self):
        self.assertEqual(run_guard("not json", cwd=self.vault).returncode, 2)
        self.assertEqual(run_guard("not json", cwd=self.other).returncode, 1)


if __name__ == "__main__":
    unittest.main()
