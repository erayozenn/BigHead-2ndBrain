"""Tests for hooks/guard.py: writes from a session outside the vault, and shell commands.

Run: python -m unittest discover hooks/tests
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

GUARD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "guard.py")
ENV_KEY = "CLAUDE_PLUGIN_OPTION_VAULT_PATH"


def write(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


class CrossFolderGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.tmp.name)
        self.vault = os.path.join(self.root, "vault")
        write(os.path.join(self.vault, "CLAUDE.md"), "# Vault Schema & Rules (template v0.7)\n")
        write(os.path.join(self.vault, "raw", "paper.md"), "source\n")
        write(os.path.join(self.vault, "wiki", "page.md"), "---\nauthor: claude\n---\n")
        write(os.path.join(self.vault, "projects", "p", "p.md"), "---\nauthor: claude\n---\n")
        write(os.path.join(self.vault, "notes", "mine.md"), "---\nauthor: me\n---\n")
        self.proj = os.path.join(self.root, "proj")
        write(os.path.join(self.proj, "src", "app.py"), "print(1)\n")

    def tearDown(self):
        self.tmp.cleanup()

    def v(self, *parts):
        return os.path.join(self.vault, *parts)

    def run_guard(self, event, vault_setting=None, cwd=None, project_dir=None):
        env = {k: val for k, val in os.environ.items() if k not in (ENV_KEY, "CLAUDE_PROJECT_DIR")}
        if vault_setting is not None:
            env[ENV_KEY] = vault_setting
        if project_dir is not None:
            env["CLAUDE_PROJECT_DIR"] = project_dir
        return subprocess.run([sys.executable, GUARD], input=json.dumps(event), capture_output=True,
                              text=True, cwd=cwd or self.proj, env=env, timeout=30)

    def edit(self, path, cwd, tool="Edit"):
        event = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {"file_path": path}}
        if cwd is not None:
            event["cwd"] = cwd
        return event

    def shell(self, command, cwd, tool="Bash"):
        return {"hook_event_name": "PreToolUse", "tool_name": tool, "cwd": cwd,
                "tool_input": {"command": command}}

    def decision(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        if not result.stdout.strip():
            return None
        return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]

    # --- file tools from outside the vault --------------------------------------------------

    def test_free_paths_from_outside_get_no_decision(self):
        for parts in (("wiki", "page.md"), ("wiki", "new.md"), ("index.md",), ("log.md",),
                      ("hot.md",), ("cards", "cards-x.md")):
            self.assertIsNone(self.decision(self.run_guard(self.edit(self.v(*parts), self.proj))), parts)

    def test_ask_first_paths_from_outside_ask(self):
        for parts in (("projects", "p", "p.md"), ("projects", "q", "q.md"), ("playbooks", "x", "x.md"),
                      ("areas", "a.md"), ("archive", "2026-11", "w.md"), ("CLAUDE.md",),
                      ("rules.md",), ("Threads.md",), ("CRITICAL_FACTS.md",), (".claude", "settings.json"),
                      ("raw", "web", "new.md"), ("notes", "new.md"), ("other.md",)):
            self.assertEqual(self.decision(self.run_guard(self.edit(self.v(*parts), self.proj))), "ask", parts)

    def test_write_tool_also_asks(self):
        result = self.run_guard(self.edit(self.v("projects", "p", "p.md"), self.proj, tool="Write"))
        self.assertEqual(self.decision(result), "ask")

    def test_hard_rules_still_deny_from_outside(self):
        for parts in (("raw", "paper.md"), ("raw", "new.md"), ("notes", "mine.md"),
                      (".obsidian", "app.json")):
            self.assertEqual(self.decision(self.run_guard(self.edit(self.v(*parts), self.proj))), "deny", parts)

    def test_inside_vault_session_unchanged(self):
        for parts in (("projects", "p", "p.md"), ("CLAUDE.md",), ("wiki", "page.md")):
            self.assertIsNone(self.decision(self.run_guard(self.edit(self.v(*parts), self.vault),
                                                           cwd=self.vault)), parts)
        sub = self.v("wiki")
        self.assertIsNone(self.decision(self.run_guard(self.edit(self.v("projects", "p", "p.md"), sub),
                                                       cwd=sub)))

    def test_no_cwd_in_event_keeps_old_behaviour(self):
        self.assertIsNone(self.decision(self.run_guard(self.edit(self.v("projects", "p", "p.md"), None),
                                                       cwd=self.vault)))

    def test_outside_paths_untouched(self):
        self.assertIsNone(self.decision(self.run_guard(
            self.edit(os.path.join(self.proj, "src", "app.py"), self.proj))))

    def test_shell_cd_into_vault_does_not_lift_ask(self):  # regression: live check step F
        # The project session ran `cd <vault>` earlier, so the event cwd is the vault;
        # the session's own folder (CLAUDE_PROJECT_DIR) is still the project.
        result = self.run_guard(self.edit(self.v("projects", "p", "p.md"), self.vault),
                                project_dir=self.proj)
        self.assertEqual(self.decision(result), "ask")

    def test_project_dir_inside_vault_no_ask(self):
        result = self.run_guard(self.edit(self.v("projects", "p", "p.md"), self.proj),
                                project_dir=self.vault)
        self.assertIsNone(self.decision(result))

    def test_project_dir_wins_for_free_paths_too(self):
        result = self.run_guard(self.edit(self.v("wiki", "page.md"), self.vault), project_dir=self.proj)
        self.assertIsNone(self.decision(result))

    def test_shell_inside_vault_cwd_still_denied_from_project_session(self):
        result = self.run_guard(self.shell("rm hot.md", self.vault), self.vault, project_dir=self.proj)
        self.assertEqual(self.decision(result), "deny")

    def test_non_write_tool_gets_no_decision(self):  # regression: spec-only test GF-90
        result = self.run_guard(self.edit(self.v("projects", "p", "p.md"), self.proj, tool="Read"))
        self.assertIsNone(self.decision(result))

    def test_ask_reason_mentions_vault(self):
        result = self.run_guard(self.edit(self.v("projects", "p", "p.md"), self.proj))
        out = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertIn("vault", out["permissionDecisionReason"].lower())

    # --- shell commands ---------------------------------------------------------------------

    def forms(self, *parts):
        path = self.v(*parts)
        fwd = path.replace("\\", "/")
        out = {path, fwd, f'"{path}"'}
        if os.name == "nt" and len(fwd) > 1 and fwd[1] == ":":
            out.add("/" + fwd[0].lower() + fwd[2:])
            out.add(fwd[0].lower() + fwd[1:])
        return sorted(out)

    def test_delete_or_move_naming_vault_denied(self):
        for target in self.forms("wiki", "page.md"):
            for command in (f"rm {target}", f"rm -rf {target}", f"mv {target} /tmp/x",
                            f"cd {self.proj} && rm {target}", f"git -C {target} rm page.md",
                            f"del {target}", f"rmdir {target}", f"echo hi > {target}"):
                self.assertEqual(self.decision(self.run_guard(self.shell(command, self.proj), self.vault)),
                                 "deny", command)

    def test_powershell_delete_denied(self):
        target = self.v("wiki", "page.md")
        for command in (f"Remove-Item {target}", f"Remove-Item -Recurse -Force '{self.vault}'",
                        f"Move-Item {target} C:/tmp", f"Rename-Item {target} x.md",
                        f"Clear-Content {target}"):
            result = self.run_guard(self.shell(command, self.proj, tool="PowerShell"), self.vault)
            self.assertEqual(self.decision(result), "deny", command)

    def test_reading_vault_from_shell_allowed(self):
        target = self.v("wiki", "page.md")
        for command in (f"cat {target}", f"ls {self.vault}", f"git -C {self.vault} status",
                        f"grep -rn term {self.vault}/wiki", f"python lint.py --vault {self.vault}"):
            self.assertIsNone(self.decision(self.run_guard(self.shell(command, self.proj), self.vault)), command)

    def test_project_commands_untouched(self):
        for command in ("rm -rf build", "mv a.txt b.txt", "git rm old.py", "del temp.txt",
                        "npm run format", "echo x > out.txt"):
            self.assertIsNone(self.decision(self.run_guard(self.shell(command, self.proj), self.vault)), command)

    def test_words_containing_verbs_not_matched(self):
        for command in (f"python transform.py --vault {self.vault}", f"cat {self.vault}/wiki/firmware.md",
                        f"grep -n 'remove' {self.vault}/log.md"):
            self.assertIsNone(self.decision(self.run_guard(self.shell(command, self.proj), self.vault)), command)

    def test_relative_delete_inside_vault_session_denied(self):
        for command in ("rm wiki/page.md", "mv hot.md old.md", "git rm log.md"):
            self.assertEqual(self.decision(self.run_guard(self.shell(command, self.vault), self.vault,
                                                          cwd=self.vault)), "deny", command)

    def test_heredoc_text_is_not_a_command(self):  # AT-0.6 run 1: a note mentioning rm was blocked
        command = "cat >> notes.txt <<'EOF'\n- F3: rm attempted, git mv blocked\nEOF"
        self.assertIsNone(self.decision(self.run_guard(self.shell(command, self.vault), cwd=self.vault)))

    def test_executed_heredoc_still_checked(self):
        for command in ("bash <<'EOF'\nrm wiki/page.md\nEOF", "sh <<EOF\nmv hot.md x\nEOF",
                        "cat <<'EOF' | sh\nrm wiki/page.md\nEOF",
                        "cat <<'EOF' > x.txt\nnote\nEOF\nrm wiki/page.md"):
            self.assertEqual(self.decision(self.run_guard(self.shell(command, self.vault), cwd=self.vault)),
                             "deny", command)

    def test_inside_vault_session_works_without_setting(self):
        self.assertEqual(self.decision(self.run_guard(self.shell("rm wiki/page.md", self.vault),
                                                      cwd=self.vault)), "deny")

    def test_no_setting_outside_vault_no_decision(self):
        command = f"rm {self.v('wiki', 'page.md')}"
        self.assertIsNone(self.decision(self.run_guard(self.shell(command, self.proj))))

    def test_shell_event_without_command_never_blocks(self):
        event = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": self.vault, "tool_input": {}}
        result = self.run_guard(event, self.vault, cwd=self.vault)
        self.assertNotEqual(result.returncode, 2)
        self.assertNotEqual(self.decision(result) if result.returncode == 0 else None, "deny")


if __name__ == "__main__":
    unittest.main()
