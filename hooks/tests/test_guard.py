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

    def test_no_path_fails_closed_in_vault_only(self):
        events = ({"tool_name": "Edit"},
                  {"tool_name": "Edit", "tool_input": None},
                  {"tool_name": "Edit", "tool_input": {}},
                  {"tool_name": "Edit", "tool_input": {"file_path": None}})
        for event in events:
            self.assertEqual(run_guard(event, cwd=self.vault).returncode, 2, event)
            self.assertEqual(run_guard(event, cwd=self.other).returncode, 1, event)

    def test_bad_json_fails_closed_in_vault_only(self):
        self.assertEqual(run_guard("not json", cwd=self.vault).returncode, 2)
        self.assertEqual(run_guard("not json", cwd=self.other).returncode, 1)

    # Regressions from the 2026-11-01 black-box test of hooks and cards.
    def test_bad_path_type_fails_closed_in_vault(self):
        for value in (7, [self.v("raw", "paper.md")]):
            event = file_event(value)
            event["cwd"] = self.vault
            self.assertEqual(run_guard(event, cwd=self.vault).returncode, 2)
            self.assertEqual(run_guard(event, cwd=self.other).returncode, 2)  # event cwd counts
        self.assertEqual(run_guard(file_event(7), cwd=self.other).returncode, 1)

    def test_vault_shaped_folder_inside_raw_stays_protected(self):
        inner = self.v("raw", "unpacked")
        write(os.path.join(inner, "CLAUDE.md"), "# Vault Schema & Rules\n")
        write(os.path.join(inner, "raw", "x.md"), "x\n")
        write(os.path.join(inner, "wiki", "page.md"), "x\n")
        self.assertDenied(run_guard(file_event(os.path.join(inner, "wiki", "page.md"))))
        self.assertDenied(run_guard(file_event(os.path.join(inner, "wiki", "new.md"), tool="Write")))
        self.assertDenied(run_guard(file_event(os.path.join(inner, "raw", "web", "new.md"), tool="Write")))

    def test_vault_shaped_folder_inside_obsidian_stays_protected(self):
        inner = self.v(".obsidian", "plugins", "v")
        write(os.path.join(inner, "CLAUDE.md"), "# Vault Schema & Rules\n")
        os.makedirs(os.path.join(inner, "raw"))
        write(os.path.join(inner, "data.json"), "{}\n")
        self.assertDenied(run_guard(file_event(os.path.join(inner, "data.json"))))

    def test_author_me_with_space_before_colon(self):
        write(self.v("notes", "spaced.md"), "---\nauthor : me\n---\nbody\n")
        self.assertDenied(run_guard(file_event(self.v("notes", "spaced.md"))))

    def test_author_me_in_utf16_file(self):
        path = self.v("notes", "utf16.md")
        with open(path, "wb") as f:
            f.write("---\nauthor: me\n---\nbody\n".encode("utf-16"))
        self.assertDenied(run_guard(file_event(path)))

    def test_author_me_after_long_frontmatter(self):
        long_lines = "".join(f"key{i}: value\n" for i in range(12000))  # over 64 KiB
        write(self.v("notes", "long.md"), f"---\n{long_lines}author: me\n---\nbody\n")
        self.assertDenied(run_guard(file_event(self.v("notes", "long.md"))))
        write(self.v("notes", "wide.md"), f"---\nkey: {'x' * 70000}\nauthor: me\n---\nbody\n")
        self.assertDenied(run_guard(file_event(self.v("notes", "wide.md"))))

    def test_every_path_key_is_checked(self):
        event = file_event(self.v("wiki", "page.md"), tool="NotebookEdit")
        event["tool_input"]["notebook_path"] = self.v("raw", "paper.md")
        self.assertDenied(run_guard(event))

    # Decisions on the ambiguous cases of that test, 2026-11-01.
    def test_author_me_variants_denied(self):
        variants = {"key": "---\nAuthor: me\n---\n", "value": "---\nauthor: Me\n---\n",
                    "list": "---\nauthor: [me]\n---\n", "blank": "\n---\nauthor: me\n---\n"}
        for name, text in variants.items():
            write(self.v("notes", f"{name}.md"), text)
            self.assertDenied(run_guard(file_event(self.v("notes", f"{name}.md"))))

    def test_similar_authors_stay_allowed(self):
        write(self.v("wiki", "other.md"), "---\nauthor: mentor\n---\n")
        self.assertNoDecision(run_guard(file_event(self.v("wiki", "other.md"))))
        write(self.v("wiki", "pair.md"), "---\nauthor: [me, claude]\n---\n")
        self.assertNoDecision(run_guard(file_event(self.v("wiki", "pair.md"))))
        write(self.v("wiki", "body.md"), "\nNot frontmatter.\n---\nauthor: me\n---\n")
        self.assertNoDecision(run_guard(file_event(self.v("wiki", "body.md"))))

    def test_nested_obsidian_folder_denied(self):
        self.assertDenied(run_guard(file_event(self.v("wiki", ".obsidian", "a.json"), tool="Write")))
        self.assertNoDecision(run_guard(file_event(self.v("wiki", ".obsidian-notes.md"), tool="Write")))

    # Blind test of fda549c, 2026-11-01.
    def test_nul_in_path_fails_closed_in_vault(self):
        event = file_event(self.v("notes", "mine.md") + "\0")
        self.assertEqual(run_guard(event, cwd=self.vault).returncode, 2)

    def test_author_me_block_list_denied(self):
        write(self.v("notes", "block.md"), "---\nauthor:\n  - me\n---\n")
        self.assertDenied(run_guard(file_event(self.v("notes", "block.md"))))
        write(self.v("wiki", "both.md"), "---\nauthor:\n  - me\n  - claude\n---\n")
        self.assertNoDecision(run_guard(file_event(self.v("wiki", "both.md"))))

    def test_author_me_with_uppercase_extension_denied(self):
        write(self.v("notes", "upper.MD"), "---\nauthor: me\n---\n")
        self.assertDenied(run_guard(file_event(self.v("notes", "upper.MD"))))

    @unittest.skipUnless(os.name == "nt", "MSYS paths exist on Windows only")
    def test_msys_path_is_protected(self):
        posix = self.v("raw", "paper.md").replace("\\", "/")
        msys = f"/{posix[0].lower()}{posix[2:]}"
        self.assertDenied(run_guard(file_event(msys)))


if __name__ == "__main__":
    unittest.main()
