"""Tests for standup.py. Run: python -m unittest discover skills/project/scripts/tests"""

import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
SCRIPT = os.path.join(HERE, "standup.py")

import standup  # noqa: E402

ME = {"login": "me"}
ANA = {"login": "ana"}


def pr(number, author=ME, draft=False, decision="", requests=(), checks=(), reviews=(), title=None):
    return {"number": number, "title": title or f"PR {number}", "author": author, "isDraft": draft,
            "reviewDecision": decision, "reviewRequests": list(requests),
            "statusCheckRollup": list(checks), "latestReviews": list(reviews),
            "url": f"https://github.com/o/r/pull/{number}", "updatedAt": "2026-11-07T10:00:00Z"}


class FakeGh:
    """Answers gh calls from canned data and records the arguments."""

    def __init__(self, prs=(), requested=(), issues=(), login="me", fail=None):
        self.prs, self.requested, self.issues, self.login = list(prs), list(requested), list(issues), login
        self.fail = fail
        self.calls = []

    def __call__(self, args):
        self.calls.append(args)
        if self.fail:
            raise standup.GhError(self.fail)
        if args[:2] == ["api", "user"]:
            return json.dumps({"login": self.login})
        if args[:2] == ["pr", "list"]:
            if "review-requested:@me" in args:
                return json.dumps([{"number": n} for n in self.requested])
            return json.dumps(self.prs)
        if args[:2] == ["issue", "list"]:
            return json.dumps(self.issues)
        raise AssertionError(f"unexpected gh call {args}")


class RemoteTest(unittest.TestCase):
    def test_forms(self):
        for value in ("github.com/o/r", "https://github.com/o/r", "https://github.com/o/r.git",
                      "git@github.com:o/r.git", "o/r"):
            self.assertEqual(standup.repo_slug(value), "o/r", value)

    def test_rejects_other_hosts_and_junk(self):
        for value in ("gitlab.com/o/r", "o", "o/r/x/y", "o/r;rm -rf", "-R/x", "", "../o/r"):
            with self.assertRaises(ValueError, msg=value):
                standup.repo_slug(value)


class ChecksTest(unittest.TestCase):
    def test_summary(self):
        self.assertEqual(standup.checks_state([]), "none")
        self.assertEqual(standup.checks_state([{"status": "COMPLETED", "conclusion": "SUCCESS"},
                                               {"state": "SUCCESS"}]), "passing")
        self.assertEqual(standup.checks_state([{"status": "IN_PROGRESS", "conclusion": ""},
                                               {"status": "COMPLETED", "conclusion": "SUCCESS"}]), "pending")
        self.assertEqual(standup.checks_state([{"status": "COMPLETED", "conclusion": "FAILURE"},
                                               {"status": "IN_PROGRESS"}]), "failing")
        self.assertEqual(standup.checks_state([{"state": "ERROR"}]), "failing")
        self.assertEqual(standup.checks_state([{"status": "COMPLETED", "conclusion": "SKIPPED"},
                                               {"status": "COMPLETED", "conclusion": "NEUTRAL"}]), "passing")


class CollectTest(unittest.TestCase):
    def test_sorts_prs_into_groups(self):
        gh = FakeGh(prs=[pr(1), pr(2, author=ANA), pr(3, author=ANA)], requested=[2])
        out = standup.collect("o/r", gh)
        self.assertTrue(out["ok"])
        self.assertEqual(out["me"], "me")
        self.assertEqual([p["number"] for p in out["mine"]], [1])
        self.assertEqual([p["number"] for p in out["review_requested"]], [2])
        self.assertEqual([p["number"] for p in out["others"]], [3])
        self.assertEqual(out["review_requested"][0]["author"], "ana")

    def test_waiting_on_for_my_prs(self):
        gh = FakeGh(prs=[
            pr(1, draft=True),
            pr(2, decision="CHANGES_REQUESTED", reviews=[{"author": ANA, "state": "CHANGES_REQUESTED"}]),
            pr(3, checks=[{"status": "COMPLETED", "conclusion": "FAILURE"}], requests=[ANA]),
            pr(4, requests=[ANA, {"__typename": "Team", "slug": "core", "name": "Core"}]),
            pr(5, decision="APPROVED"),
            pr(6),
        ])
        mine = {p["number"]: p for p in standup.collect("o/r", gh)["mine"]}
        self.assertEqual(mine[1]["waiting_on"], "you: draft")
        self.assertEqual(mine[2]["waiting_on"], "you: changes requested by ana")
        self.assertEqual(mine[3]["waiting_on"], "you: checks failing")
        self.assertEqual(mine[4]["waiting_on"], "review: ana, core")
        self.assertEqual(mine[5]["waiting_on"], "merge: approved")
        self.assertEqual(mine[6]["waiting_on"], "nobody: no reviewer requested")
        self.assertEqual(mine[3]["checks"], "failing")

    def test_issues_with_milestone_due(self):
        gh = FakeGh(issues=[
            {"number": 12, "title": "split model", "milestone": {"title": "v0.1", "dueOn": "2026-11-17T00:00:00Z"},
             "url": "u", "updatedAt": "2026-11-07T00:00:00Z"},
            {"number": 9, "title": "geri ac", "milestone": None, "url": "u", "updatedAt": "x"},
        ])
        issues = standup.collect("o/r", gh)["issues"]
        self.assertEqual(issues[0], {"number": 12, "title": "split model", "milestone": "v0.1",
                                     "due": "2026-11-17", "url": "u"})
        self.assertEqual(issues[1]["due"], None)
        self.assertEqual(issues[1]["milestone"], None)

    def test_every_call_names_the_repo(self):
        gh = FakeGh(prs=[pr(1)])
        standup.collect("o/r", gh)
        for call in gh.calls:
            if call[:2] != ["api", "user"]:
                self.assertIn("-R", call)
                self.assertEqual(call[call.index("-R") + 1], "o/r")
                self.assertIn("--json", call)

    def test_gh_error_is_reported_not_raised(self):
        out = standup.collect("o/r", FakeGh(fail="HTTP 404: Not Found"))
        self.assertFalse(out["ok"])
        self.assertIn("404", out["error"])
        self.assertEqual(out["mine"], [])

    def test_bad_json_is_reported(self):
        out = standup.collect("o/r", lambda args: "not json")
        self.assertFalse(out["ok"])
        self.assertTrue(out["error"])

    def test_long_title_is_shortened(self):
        out = standup.collect("o/r", FakeGh(prs=[pr(1, title="t" * 300)]))
        self.assertLessEqual(len(out["mine"][0]["title"]), standup.MAX_TITLE)

    def test_limit_flag_marks_truncation(self):
        many = [pr(i, author=ANA) for i in range(standup.LIMIT)]
        out = standup.collect("o/r", FakeGh(prs=many))
        self.assertTrue(out["truncated"])
        self.assertFalse(standup.collect("o/r", FakeGh(prs=many[:3]))["truncated"])


class CliTest(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, timeout=60)

    def test_bad_remote_exits_2_with_json(self):
        result = self.run_cli("--remote", "gitlab.com/o/r")
        self.assertEqual(result.returncode, 2)
        out = json.loads(result.stdout)
        self.assertFalse(out["ok"])
        self.assertIn("github.com", out["error"])

    def test_missing_gh_is_reported(self):
        result = self.run_cli("--remote", "o/r", "--gh", "no-such-gh-binary-xyz")
        self.assertEqual(result.returncode, 0)
        out = json.loads(result.stdout)
        self.assertFalse(out["ok"])
        self.assertIn("gh", out["error"])


if __name__ == "__main__":
    unittest.main()
