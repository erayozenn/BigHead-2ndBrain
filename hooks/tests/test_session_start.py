"""Tests for hooks/session_start.py. Run: python -m unittest discover hooks/tests"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "session_start.py")
ENV_KEY = "CLAUDE_PLUGIN_OPTION_VAULT_PATH"
MAX_CHARS = 3200  # raised from 2000 for the work rules (acceptance test run 1)


def write(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


class SessionStartTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.tmp.name)
        self.vault = os.path.join(self.root, "vault")
        write(os.path.join(self.vault, "CLAUDE.md"), "# Vault Schema & Rules (template v0.7)\n")
        os.makedirs(os.path.join(self.vault, "raw"))
        write(os.path.join(self.vault, "index.md"), "# Index\n")
        self.proj = os.path.join(self.root, "proj1")
        os.makedirs(self.proj)
        self.add_hub("proj1", f"**Repo.** `{self.proj}`. Last seen commit: none")
        self.add_hub("secretproj", f"**Repo.** `{os.path.join(self.root, 'secretproj')}`")

    def tearDown(self):
        self.tmp.cleanup()

    def add_hub(self, name, repo_line):
        write(os.path.join(self.vault, "projects", name, f"{name}.md"),
              f"---\ntype: project\n---\n# {name}\n\n{repo_line}\n")

    def run_hook(self, cwd, vault_setting=None, event=None, raw=None, project_dir=None):
        env = {k: v for k, v in os.environ.items() if k not in (ENV_KEY, "CLAUDE_PROJECT_DIR")}
        if vault_setting is not None:
            env[ENV_KEY] = vault_setting
        if project_dir is not None:
            env["CLAUDE_PROJECT_DIR"] = project_dir
        if raw is None:
            payload = event if event is not None else {
                "hook_event_name": "SessionStart", "source": "startup", "cwd": cwd}
            raw = json.dumps(payload)
        return subprocess.run([sys.executable, HOOK], input=raw, capture_output=True, text=True,
                              cwd=cwd, env=env, timeout=30)

    def context(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.strip(), "expected context output")
        out = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "SessionStart")
        text = out["additionalContext"]
        self.assertLessEqual(len(text), MAX_CHARS)
        return text

    def assertSilent(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_no_setting_is_silent(self):
        self.assertSilent(self.run_hook(self.proj))

    def test_empty_setting_is_silent(self):
        self.assertSilent(self.run_hook(self.proj, ""))

    def test_setting_not_a_vault_is_silent(self):
        self.assertSilent(self.run_hook(self.proj, self.proj))

    def test_inside_vault_is_silent(self):
        self.assertSilent(self.run_hook(self.vault, self.vault))
        wiki = os.path.join(self.vault, "wiki")
        os.makedirs(wiki)
        self.assertSilent(self.run_hook(wiki, self.vault))

    def test_bad_stdin_is_silent(self):
        self.assertSilent(self.run_hook(self.proj, self.vault, raw="not json"))

    def test_match_names_hub_and_rules(self):
        text = self.context(self.run_hook(self.proj, self.vault))
        self.assertIn("proj1", text)
        self.assertIn("proj1.md", text)
        self.assertNotIn("secretproj", text)
        self.assertIn("CLAUDE.md", text)  # read the vault rules before writing
        self.assertIn("never", text.lower())

    def test_match_from_subfolder(self):
        sub = os.path.join(self.proj, "src")
        os.makedirs(sub)
        self.assertIn("proj1.md", self.context(self.run_hook(sub, self.vault)))

    def test_history_named_when_present(self):
        write(os.path.join(self.vault, "projects", "proj1", "proj1-history.md"), "# h\n")
        self.assertIn("proj1-history.md", self.context(self.run_hook(self.proj, self.vault)))

    def test_no_match_lists_no_hubs(self):
        other = os.path.join(self.root, "unrelated")
        os.makedirs(other)
        text = self.context(self.run_hook(other, self.vault))
        self.assertNotIn("proj1", text)
        self.assertNotIn("secretproj", text)
        self.assertIn("index.md", text)

    def test_several_matches_ask_user(self):
        self.add_hub("proj1-copy", f"**Repo.** `{self.proj}`")
        text = self.context(self.run_hook(self.proj, self.vault))
        self.assertIn("proj1", text)
        self.assertIn("proj1-copy", text)
        self.assertIn("ask", text.lower())
        self.assertNotIn("secretproj", text)

    def test_many_matches_keep_rules(self):  # regression: spec-only test SS-93
        for i in range(40):
            self.add_hub(f"long{i:02d}-" + "y" * 50, f"**Repo.** `{self.proj}`")
        text = self.context(self.run_hook(self.proj, self.vault))
        self.assertIn("ask", text.lower())
        self.assertIn("CLAUDE.md", text)
        self.assertIn("index.md", text)
        self.assertIn("Never copy vault content", text)
        self.assertIn("more", text)

    def test_work_rules_from_acceptance_test(self):  # AT-0.6 run 1: scenarios 2, 3, 5, 8
        text = self.context(self.run_hook(self.proj, self.vault)).lower()
        self.assertIn("before building or choosing", text)   # research first, options, user picks
        self.assertIn("web search", text)
        self.assertIn("show the exact change", text)         # hub writes asked in chat
        self.assertIn("dated", text)                         # dated wiki claims checked
        self.assertIn("projects/", text)                     # nothing else under projects/
        self.assertIn("slash command", text)                 # offer, do not make the user type

    def test_hub_folder_pages_are_allowed(self):  # 2026-11-07: -overview/-status pages were ruled out
        text = self.context(self.run_hook(self.proj, self.vault)).lower()
        self.assertIn("pages it links inside its own project folder", text)
        self.assertNotIn("except the matching hub", text)
        self.assertIn("other projects", text)                # still closed unless asked

    def hub_path(self, name="proj1"):
        return os.path.join(self.vault, "projects", name, f"{name}.md")

    def set_next_steps(self, *steps):
        body = "".join(f"{i}. {s}\n" for i, s in enumerate(steps, 1))
        with open(self.hub_path(), "a", encoding="utf-8", newline="\n") as f:
            f.write(f"\n## Next step\n{body}\n## Decisions\n")

    def test_due_steps_are_shown(self):  # WP5: overdue and near Next step items
        from datetime import date, timedelta
        d = lambda n: (date.today() + timedelta(days=n)).isoformat()  # noqa: E731
        self.set_next_steps(f"Ship it 📅 {d(3)}", f"Review PR 📅 {d(-2)}", f"Later 📅 {d(30)}")
        text = self.context(self.run_hook(self.proj, self.vault))
        self.assertIn(f"Review PR 📅 {d(-2)} (overdue by 2 days)", text)
        self.assertIn(f"Ship it 📅 {d(3)} (in 3 days)", text)
        self.assertNotIn("Later", text)
        self.assertLess(text.index("Review PR"), text.index("Ship it"))

    def test_due_today_wording(self):
        from datetime import date
        self.set_next_steps(f"Demo 📅 {date.today().isoformat()}")
        self.assertIn("(due today)", self.context(self.run_hook(self.proj, self.vault)))

    def test_no_due_line_without_dates(self):
        self.set_next_steps("Plain step")
        self.assertNotIn("📅", self.context(self.run_hook(self.proj, self.vault)))

    def test_at_most_three_due_steps(self):
        from datetime import date, timedelta
        steps = [f"s{i} 📅 {(date.today() + timedelta(days=i)).isoformat()}" for i in range(5)]
        self.set_next_steps(*steps)
        text = self.context(self.run_hook(self.proj, self.vault))
        self.assertIn("s2 ", text)
        self.assertNotIn("s3 ", text)

    def test_procedures_pointer(self):  # WP5: People and Procedures live in the overview page
        overview = os.path.join(self.vault, "projects", "proj1", "proj1-overview.md")
        write(overview, "# o\n\n## People\n- Ana merges\n\n## Procedures\n- run tests before PR\n")
        text = self.context(self.run_hook(self.proj, self.vault))
        self.assertIn("## Procedures", text)
        self.assertIn("proj1-overview.md", text)
        self.assertIn("## People", text)
        self.assertNotIn("run tests before PR", text)   # pointer only, no content copied

    def test_no_procedures_pointer_without_section(self):
        overview = os.path.join(self.vault, "projects", "proj1", "proj1-overview.md")
        write(overview, "# o\n\n```\n## Procedures\n```\n")
        self.assertNotIn("## Procedures", self.context(self.run_hook(self.proj, self.vault)))

    def test_several_matches_show_no_dates(self):
        self.set_next_steps("Overdue 📅 2020-01-01")
        self.add_hub("proj2", f"**Repo.** `{self.proj}`")
        self.assertNotIn("Overdue", self.context(self.run_hook(self.proj, self.vault)))

    def test_project_dir_wins_over_shell_cwd(self):  # live check: shell `cd` moves the event cwd
        event = {"hook_event_name": "SessionStart", "source": "compact", "cwd": self.vault}
        result = self.run_hook(self.vault, self.vault, event=event, project_dir=self.proj)
        self.assertIn("proj1.md", self.context(result))

    def test_empty_stdin_is_silent(self):  # spec-only test SS-102: empty input is invalid
        self.assertSilent(self.run_hook(self.proj, self.vault, raw=""))

    def test_cwd_from_event_wins(self):
        other = os.path.join(self.root, "unrelated")
        os.makedirs(other)
        event = {"hook_event_name": "SessionStart", "source": "resume", "cwd": self.proj}
        self.assertIn("proj1.md", self.context(self.run_hook(other, self.vault, event=event)))

    def test_resume_and_compact_still_inform(self):
        for source in ("resume", "compact", "clear"):
            event = {"hook_event_name": "SessionStart", "source": source, "cwd": self.proj}
            self.assertIn("proj1.md", self.context(self.run_hook(self.proj, self.vault, event=event)))

    def test_broken_hub_file_is_skipped(self):
        path = os.path.join(self.vault, "projects", "broken", "broken.md")
        os.makedirs(os.path.dirname(path))
        with open(path, "wb") as f:
            f.write(b"\xff\xfe\x00garbage\x00")
        self.assertIn("proj1.md", self.context(self.run_hook(self.proj, self.vault)))


if __name__ == "__main__":
    unittest.main()
