"""Tests for hooks/procedures.py. Run: python -m unittest discover hooks/tests"""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "procedures.py")
ENV_KEY = "CLAUDE_PLUGIN_OPTION_VAULT_PATH"
TAG = "[bighead procedures]"

OVERVIEW = """---
type: project
---
# proj1 overview

## Procedures
Checklists.

### Before a PR
- PR-ITEM own branch.
- PR-ITEM tests green.

### Before a measurement
- MEASURE-ITEM preregister.
"""


ANSWER2 = "\n# bighead-checklist: 1 done; 2 n/a: no tests touched"


def write(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


class ProceduresTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = os.path.realpath(self.tmp.name)
        self.vault = os.path.join(self.root, "vault")
        write(os.path.join(self.vault, "CLAUDE.md"), "# Vault Schema & Rules (template v0.7)\n")
        os.makedirs(os.path.join(self.vault, "raw"))
        write(os.path.join(self.vault, "index.md"), "# Index\n")
        self.proj = os.path.join(self.root, "proj1")
        os.makedirs(self.proj)
        self.add_hub("proj1", self.proj)
        self.overview = os.path.join(self.vault, "projects", "proj1", "proj1-overview.md")
        write(self.overview, OVERVIEW)
        self.state = os.path.join(self.root, "state")

    def tearDown(self):
        self.tmp.cleanup()

    def add_hub(self, name, repo):
        write(os.path.join(self.vault, "projects", name, f"{name}.md"),
              f"---\ntype: project\n---\n# {name}\n\n**Repo.** `{repo}`. Last seen commit: none\n")

    def run_hook(self, command, sid="s1", tool="Bash", vault=True, project_dir=None, cwd=None,
                 raw=None, state=None):
        env = {k: v for k, v in os.environ.items()
               if k not in (ENV_KEY, "CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_DATA")}
        if vault:
            env[ENV_KEY] = self.vault
        env["CLAUDE_PROJECT_DIR"] = project_dir if project_dir is not None else self.proj
        env["CLAUDE_PLUGIN_DATA"] = state if state is not None else self.state
        if raw is None:
            event = {"hook_event_name": "PreToolUse", "tool_name": tool,
                     "tool_input": {"command": command}, "cwd": cwd or self.proj}
            if sid is not None:
                event["session_id"] = sid
            raw = json.dumps(event)
        return subprocess.run([sys.executable, HOOK], input=raw, capture_output=True, text=True,
                              encoding="utf-8", cwd=self.proj, env=env, timeout=30)

    def denied(self, res):
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue(res.stdout.strip(), "expected a deny decision")
        out = json.loads(res.stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "PreToolUse")
        self.assertEqual(out["permissionDecision"], "deny")
        reason = out["permissionDecisionReason"]
        self.assertIn(TAG, reason)
        return reason

    def silent(self, res):
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "")

    # --- the reminder ---

    def test_push_denied_once_with_pr_checklist(self):
        reason = self.denied(self.run_hook("git push origin feature"))
        self.assertIn("PR-ITEM own branch", reason)
        self.assertIn("PR-ITEM tests green", reason)
        self.assertNotIn("MEASURE-ITEM", reason)
        self.assertIn("Before a PR", reason)
        self.assertIn('"proj1"', reason)
        self.assertIn(self.overview.replace("\\", "/"), reason)
        self.assertIn("again", reason)

    def test_instructions_come_before_the_checklist(self):
        # Live check 2026-11-08: with the instructions after the list, Claude reran the command
        # before answering every item and went past a "not done" item without asking.
        reason = self.denied(self.run_hook("git push"))
        first_item = reason.index("PR-ITEM own branch")
        for phrase in ("Do not run", "not done", "ask the user", "wait for", "same command again",
                       "# bighead-checklist:", "n/a:", "user ok:", "2 entries"):
            self.assertIn(phrase, reason)
            self.assertLess(reason.index(phrase), first_item, phrase)

    # --- WP8: the answer line in the rerun (real use 2026-11-08..09: 0 of 7 answered per item) ---

    def test_rerun_without_answer_is_refused_briefly(self):
        self.denied(self.run_hook("git push"))
        reason = self.denied(self.run_hook("git push"))
        self.assertIn("# bighead-checklist:", reason)
        self.assertIn("2 entries", reason)
        self.assertNotIn("PR-ITEM", reason)  # the list is not shown again
        self.assertIn(self.overview.replace("\\", "/"), reason)

    def test_rerun_with_answer_passes_then_kind_is_free(self):
        self.denied(self.run_hook("git push"))
        self.silent(self.run_hook("git push" + ANSWER2))
        self.silent(self.run_hook("git push origin other"))

    def test_answer_on_same_line_and_powershell(self):
        self.denied(self.run_hook("git push", tool="PowerShell"))
        self.silent(self.run_hook("git push # bighead-checklist: done; user ok: the user said go",
                                  tool="PowerShell"))

    def test_answer_before_the_reminder_does_not_skip_it(self):
        reason = self.denied(self.run_hook("git push" + ANSWER2))
        self.assertIn("PR-ITEM own branch", reason)

    def test_wrong_count_is_refused(self):
        self.denied(self.run_hook("git push"))
        reason = self.denied(self.run_hook("git push # bighead-checklist: 1 done"))
        self.assertIn("2 entries", reason)
        self.assertIn("1", reason)

    def test_bare_not_done_is_refused_with_ask_the_user(self):
        self.denied(self.run_hook("git push"))
        reason = self.denied(self.run_hook("git push # bighead-checklist: 1 done; 2 not done"))
        self.assertIn("ask the user", reason)
        self.silent(self.run_hook("git push # bighead-checklist: 1 done; 2 user ok: go on"))

    def test_entry_without_reason_is_refused(self):
        self.denied(self.run_hook("git push"))
        self.denied(self.run_hook("git push # bighead-checklist: 1 done; 2 n/a"))

    def test_items_of_two_different_lists_add_up(self):
        write(self.overview, OVERVIEW.replace("### Before a measurement",
                                              "### Before a push\n- PUSH-ITEM rebase.\n\n### Before a measurement"))
        reason = self.denied(self.run_hook("git push && gh pr create --fill"))
        self.assertIn("3 entries", reason)
        self.denied(self.run_hook("git push && gh pr create --fill" + ANSWER2))
        self.silent(self.run_hook("git push && gh pr create --fill # bighead-checklist: done; done; done"))
        self.silent(self.run_hook("gh pr create --fill"))

    def test_rerun_with_a_new_kind_shows_that_list(self):
        self.denied(self.run_hook("git push"))
        reason = self.denied(self.run_hook("git push && gh pr create --fill" + ANSWER2))
        self.assertIn("Stopped once", reason)  # PR not reminded yet: no answer is checked

    def test_checklist_without_list_lines_needs_one_entry(self):
        write(self.overview, "## Procedures\n### Before a PR\nRun the full test suite.\n")
        self.assertIn("1 entry", self.denied(self.run_hook("git push")))
        self.silent(self.run_hook("git push # bighead-checklist: done"))

    def test_example_line_has_the_needed_entry_count(self):
        # Spec-only test 2026-11-10: a fixed 3-entry example could lead Claude to write 3 entries.
        import re

        def example(reason):
            return re.search(r"`(# bighead-checklist: 1 [^`]*)`", reason).group(1)
        write(self.overview, "## Procedures\n### Before a PR\n- ONE-ITEM only.\n")
        for reason in (self.denied(self.run_hook("git push")),
                       self.denied(self.run_hook("git push"))):
            self.assertEqual(example(reason), "# bighead-checklist: 1 <answer>")
        write(self.overview, OVERVIEW)
        self.assertEqual(example(self.denied(self.run_hook("git push", sid="s2"))),
                         "# bighead-checklist: 1 <answer>; 2 <answer>")
        long = "\n".join(f"- ITEM {i}" for i in range(9))
        write(self.overview, "## Procedures\n### Before a PR\n" + long + "\n")
        self.assertEqual(example(self.denied(self.run_hook("git push", sid="s3"))),
                         "# bighead-checklist: 1 <answer>; 2 <answer>; …; 9 <answer>")

    def test_semicolon_rule_is_stated(self):
        # Spec-only test 2026-11-10: `;` separates entries, so it cannot appear inside one.
        self.assertIn("no `;` inside an entry", self.denied(self.run_hook("git push")))
        self.assertIn("no `;` inside an entry", self.denied(self.run_hook("git push")))

    def test_marker_from_0_7_0_counts_as_answered(self):
        import hashlib
        folder = os.path.join(self.state, "procedures")
        write(os.path.join(folder, hashlib.sha256("s1\0push".encode()).hexdigest()[:32]), "")
        self.silent(self.run_hook("git push"))

    def test_other_session_is_reminded_again(self):
        self.denied(self.run_hook("git push", sid="s1"))
        self.denied(self.run_hook("git push", sid="s2"))

    def test_kinds_are_counted_separately(self):
        self.denied(self.run_hook("git push"))
        self.denied(self.run_hook('gh pr create --title "x" --body "y"'))
        self.silent(self.run_hook("gh pr create --fill" + ANSWER2))

    def test_push_section_preferred(self):
        write(self.overview, OVERVIEW.replace("### Before a measurement",
                                              "### Before a push\n- PUSH-ITEM rebase.\n\n### Before a measurement"))
        reason = self.denied(self.run_hook("git push"))
        self.assertIn("PUSH-ITEM", reason)
        self.assertNotIn("PR-ITEM", reason)

    def test_merge_without_section_is_silent_and_not_marked(self):
        self.silent(self.run_hook("gh pr merge 12 --squash"))
        write(self.overview, OVERVIEW + "\n### Before a release\n- REL-ITEM check.\n")
        self.assertIn("REL-ITEM", self.denied(self.run_hook("gh pr merge 12 --squash")))

    def test_command_forms(self):
        for i, cmd in enumerate(["npm test && git push", "GIT_TRACE=1 git push -u origin x",
                                 "git -C ../proj1 push", "cd x; git push", "git status\ngit push"]):
            with self.subTest(cmd=cmd):
                self.denied(self.run_hook(cmd, sid=f"form{i}"))

    def test_non_matching_commands_are_silent(self):
        for cmd in ["git status", "echo git push", "git pushd", "gh pr view 3", "gh pr list",
                    "git commit -m 'git push later'", "ghx pr create"]:
            with self.subTest(cmd=cmd):
                self.silent(self.run_hook(cmd))

    def test_powershell_tool(self):
        self.denied(self.run_hook("git push", tool="PowerShell"))

    def test_two_kinds_in_one_command(self):
        reason = self.denied(self.run_hook("git push -u origin x && gh pr create --fill"))
        self.assertEqual(reason.count("PR-ITEM own branch"), 1)  # same section listed once
        self.assertIn("2 entries", reason)
        self.silent(self.run_hook("git push -u origin x && gh pr create --fill" + ANSWER2))
        self.silent(self.run_hook("git push"))
        self.silent(self.run_hook("gh pr create --fill"))

    def test_long_checklist_is_capped(self):
        long = "\n".join(f"- PR-ITEM line {i} " + "x" * 80 for i in range(100))
        write(self.overview, "## Procedures\n### Before a PR\n" + long + "\n")
        reason = self.denied(self.run_hook("git push"))
        self.assertLess(len(reason), 3000)
        self.assertIn("cut here; read the rest in the overview", reason)

    def test_other_event_names_are_silent(self):
        for name in ("PostToolUse", "SessionStart"):
            with self.subTest(name=name):
                raw = json.dumps({"hook_event_name": name, "tool_name": "Bash", "session_id": "s1",
                                  "tool_input": {"command": "git push"}, "cwd": self.proj})
                self.silent(self.run_hook(None, raw=raw))
        self.denied(self.run_hook("git push"))  # not marked by the ignored events

    # --- silence ---

    def test_non_shell_tool_is_silent(self):
        res = self.run_hook(None, raw=json.dumps({"tool_name": "Edit", "session_id": "s1",
                                                  "tool_input": {"file_path": "x"}, "cwd": self.proj}))
        self.silent(res)

    def test_inside_vault_is_silent(self):
        self.silent(self.run_hook("git push", project_dir=self.vault, cwd=self.vault))

    def test_project_dir_wins_over_event_cwd(self):
        self.denied(self.run_hook("git push", cwd=self.vault))

    def test_no_vault_option_is_silent(self):
        self.silent(self.run_hook("git push", vault=False))

    def test_no_matching_hub_is_silent(self):
        other = os.path.join(self.root, "elsewhere")
        os.makedirs(other)
        self.silent(self.run_hook("git push", project_dir=other, cwd=other))

    def test_several_hubs_are_silent(self):
        self.add_hub("proj2", self.proj)
        self.silent(self.run_hook("git push"))

    def test_no_overview_or_procedures_is_silent(self):
        write(self.overview, "# proj1 overview\n\n## People\n- a\n")
        self.silent(self.run_hook("git push"))
        os.remove(self.overview)
        self.silent(self.run_hook("git push"))

    def test_missing_session_id_is_silent(self):
        self.silent(self.run_hook("git push", sid=None))

    def test_bad_input_is_silent(self):
        self.silent(self.run_hook(None, raw="not json"))
        self.silent(self.run_hook(None, raw=""))
        self.silent(self.run_hook(None, raw=json.dumps({"tool_name": "Bash", "session_id": "s1",
                                                        "tool_input": {"command": 5}})))

    def test_unwritable_state_fails_open(self):
        blocker = os.path.join(self.root, "afile")
        write(blocker, "x")
        self.silent(self.run_hook("git push", state=blocker))

    def test_old_markers_are_removed(self):
        self.denied(self.run_hook("git push", sid="old"))
        folder = os.path.join(self.state, "procedures")
        markers = os.listdir(folder)
        self.assertEqual(len(markers), 1)
        old = time.time() - 8 * 86400
        os.utime(os.path.join(folder, markers[0]), (old, old))
        self.denied(self.run_hook("gh pr create --fill", sid="new"))
        self.assertEqual(len(os.listdir(folder)), 1)


if __name__ == "__main__":
    unittest.main()
