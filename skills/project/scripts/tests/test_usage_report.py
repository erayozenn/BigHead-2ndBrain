"""Tests for usage_report.py. Run: python -m unittest discover skills/project/scripts/tests"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "usage_report.py")
HUB = "C:/vault/projects/demo/demo.md"


def note(kind="match", hub=HUB):
    if kind == "match":
        body = f'[bighead] Your vault (second brain) is at C:/vault.\nThis folder belongs to the project "demo". Hub: {hub}\n'
    elif kind == "several":
        body = "[bighead] Your vault (second brain) is at C:/vault.\nSeveral project hubs match this folder: a, b.\n"
    else:
        body = "[bighead] Your vault (second brain) is at C:/vault.\nNo project hub matches this folder.\n"
    out = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": body}}
    return {"type": "attachment", "attachment": {"type": "hook_success", "hookEvent": "SessionStart",
                                                  "stdout": json.dumps(out)},
            "timestamp": "2026-11-06T10:00:00.000Z"}


def prompt(text="hi"):
    return {"type": "user", "message": {"role": "user", "content": text}}


def tool(name, tid, **inp):
    return {"type": "assistant", "message": {"role": "assistant",
                                             "content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}]}}


def result(tid, error=False):
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": tid, "is_error": error, "content": "x"}]}}


class UsageReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.projects = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def session(self, folder, sid, records):
        path = os.path.join(self.projects, folder, sid + ".jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            for r in records:
                f.write((r if isinstance(r, str) else json.dumps(r)) + "\n")

    def report(self, *args):
        res = subprocess.run([sys.executable, SCRIPT, "--projects-dir", self.projects, "--days", "0", *args],
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout if "--human" in args else json.loads(res.stdout)

    def test_counts_note_kinds_and_skips_sessions_without_note(self):
        self.session("p1", "a", [note("match"), prompt()])
        self.session("p2", "b", [note("none"), prompt()])
        self.session("p3", "c", [note("several"), prompt()])
        self.session("vault", "d", [prompt()])
        r = self.report()
        self.assertEqual(r["sessions_scanned"], 4)
        self.assertEqual(r["notes"], {"match": 1, "none": 1, "several": 1})

    def test_hub_read_by_read_tool_with_backslashes_and_case(self):
        self.session("p1", "a", [note(), prompt(),
                                 tool("Read", "t1", file_path="c:\\Vault\\projects\\demo\\demo.md"), result("t1")])
        s = self.report()["match_sessions"]
        self.assertEqual((s["count"], s["hub_read"], s["hub_read_with_shell"]), (1, 1, 1))

    def test_failed_read_does_not_count(self):
        self.session("p1", "a", [note(), prompt(), tool("Read", "t1", file_path=HUB), result("t1", error=True)])
        s = self.report()["match_sessions"]
        self.assertEqual(s["hub_read"], 0)

    def test_shell_mention_counts_only_as_upper_bound(self):
        self.session("p1", "a", [note(), prompt(), tool("Bash", "t1", command=f'cat "{HUB}"'), result("t1")])
        s = self.report()["match_sessions"]
        self.assertEqual((s["hub_read"], s["hub_read_with_shell"]), (0, 1))

    def test_edit_outside_vault_without_hub_update_is_flagged(self):
        self.session("p1", "a", [note(), prompt(), tool("Edit", "t1", file_path="C:/code/app.py"), result("t1")])
        s = self.report()["match_sessions"]
        self.assertEqual((s["edited_project"], s["hub_updated"], s["edited_without_hub_update"]), (1, 0, 1))

    def test_hub_update_after_edit(self):
        self.session("p1", "a", [note(), prompt(),
                                 tool("Write", "t1", file_path="C:/code/app.py"), result("t1"),
                                 tool("Edit", "t2", file_path=HUB), result("t2")])
        s = self.report()["match_sessions"]
        self.assertEqual((s["edited_project"], s["hub_updated"], s["edited_without_hub_update"]), (1, 1, 0))

    def test_rejected_hub_edit_is_not_an_update(self):
        self.session("p1", "a", [note(), prompt(), tool("Edit", "t1", file_path="C:/code/a.py"), result("t1"),
                                 tool("Edit", "t2", file_path=HUB), result("t2", error=True)])
        s = self.report()["match_sessions"]
        self.assertEqual((s["hub_updated"], s["edited_without_hub_update"]), (0, 1))

    def test_vault_writes_are_not_project_edits(self):
        self.session("p1", "a", [note(), prompt(), tool("Write", "t1", file_path="C:/vault/wiki/x.md"), result("t1")])
        s = self.report()["match_sessions"]
        self.assertEqual(s["edited_project"], 0)

    def test_tools_before_the_note_do_not_count(self):
        self.session("p1", "a", [tool("Read", "t0", file_path=HUB), result("t0"), note(), prompt()])
        s = self.report()["match_sessions"]
        self.assertEqual(s["hub_read"], 0)

    def test_resume_note_counts_session_once(self):
        self.session("p1", "a", [note(), prompt(), note(), prompt(), tool("Read", "t1", file_path=HUB), result("t1")])
        s = self.report()["match_sessions"]
        self.assertEqual((s["count"], s["hub_read"]), (1, 1))

    def test_prompts_counted_without_tool_results_or_meta(self):
        self.session("p1", "a", [note(), prompt("a"), {"type": "user", "isMeta": True, "message": {"content": "m"}},
                                 tool("Read", "t1", file_path=HUB), result("t1"), prompt("b")])
        r = self.report()
        self.assertEqual(r["sessions"][0]["prompts"], 2)

    def test_bad_lines_and_other_hooks_are_skipped(self):
        self.session("p1", "a", ["not json", {"type": "attachment", "attachment": {
            "type": "hook_success", "hookEvent": "SessionStart", "stdout": "plain text"}}, note(), prompt()])
        r = self.report()
        self.assertEqual(r["notes"]["match"], 1)
        self.assertGreaterEqual(r["skipped_lines"], 1)

    def test_subagent_transcripts_are_ignored(self):
        self.session("p1", "a", [note(), prompt()])
        self.session(os.path.join("p1", "a", "subagents"), "agent-x", [note(), prompt()])
        self.assertEqual(self.report()["sessions_scanned"], 1)

    def test_human_output_names_projects_only_with_names_flag(self):
        self.session("p1", "a", [note(), prompt()])
        self.assertNotIn("demo", self.report("--human"))
        self.assertIn("demo", self.report("--human", "--names"))

    def test_days_filter_uses_file_time(self):
        self.session("p1", "a", [note(), prompt()])
        old = os.path.join(self.projects, "p1", "a.jsonl")
        os.utime(old, (0, 0))
        res = subprocess.run([sys.executable, SCRIPT, "--projects-dir", self.projects, "--days", "14"],
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(json.loads(res.stdout)["sessions_scanned"], 0)

    def test_procedure_reminders_and_reruns(self):
        def denied(tid, content):
            return {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": tid, "is_error": True, "content": content}]}}
        reason = '[bighead procedures] Before "git push" in project "demo": ...'
        self.session("p1", "a", [note(), prompt(),
                                 tool("Bash", "t1", command="git push"), denied("t1", reason),
                                 tool("Bash", "t2", command="git push"), result("t2"),
                                 tool("Bash", "t3", command="gh pr create --fill"),
                                 denied("t3", [{"type": "text", "text": reason}]),
                                 tool("Bash", "t4", command="git push -f"), denied("t4", "other error")])
        data = self.report()
        s = data["match_sessions"]
        self.assertEqual((s["procedure_reminders"], s["reran_after_reminder"]), (2, 1))
        self.assertEqual(data["sessions"][0]["procedure_reminders"], 2)
        self.assertIn("reminders 2", self.report("--human"))


if __name__ == "__main__":
    unittest.main()
