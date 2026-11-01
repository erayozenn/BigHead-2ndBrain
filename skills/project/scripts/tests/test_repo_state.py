"""Tests for repo_state.py. Run: python -m unittest discover skills/project/scripts/tests"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "repo_state.py")


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                           *args], capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip()


def run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True,
                          encoding="utf-8", timeout=60)


class RepoStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.repo = os.path.join(self.tmp.name, "repo")
        os.mkdir(self.repo)
        subprocess.run(["git", "init", "-q", self.repo], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def commit(self, message):
        git(self.repo, "commit", "-q", "--allow-empty", "-m", message)
        return git(self.repo, "rev-parse", "HEAD")

    def state(self, *args):
        result = run("--repo", self.repo, *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_head_without_a_sha(self):
        head = self.commit("one")
        state = self.state()
        self.assertEqual(state["head"], head[:len(state["head"])])
        self.assertEqual(state["seen_state"], "none")
        self.assertIsNone(state["count"])
        self.assertFalse(state["dirty"])

    def test_no_commits(self):
        state = self.state("--sha", "abc1234")
        self.assertIsNone(state["head"])
        self.assertEqual(state["seen_state"], "no_commits")

    def test_commits_since_seen(self):
        seen = self.commit("one")
        self.commit("two")
        self.commit("three")
        state = self.state("--sha", seen[:7])
        self.assertEqual(state["seen_state"], "ancestor")
        self.assertEqual(state["count"], 2)
        self.assertIsNone(state["commits"])  # `open` must not see the list
        state = self.state("--sha", seen[:7], "--commits", "30")
        self.assertEqual([c.split(" ", 1)[1] for c in state["commits"]], ["three", "two"])
        self.assertFalse(state["truncated"])

    def test_truncated_list_is_flagged(self):
        seen = self.commit("one")
        self.commit("two")
        self.commit("three")
        state = self.state("--sha", seen, "--commits", "1")
        self.assertEqual(len(state["commits"]), 1)
        self.assertTrue(state["truncated"])

    def test_same_commit_is_zero(self):
        seen = self.commit("one")
        state = self.state("--sha", seen, "--commits", "30")
        self.assertEqual((state["seen_state"], state["count"], state["commits"]), ("ancestor", 0, []))

    def test_head_behind_seen_is_not_ancestor(self):
        old = self.commit("one")
        seen = self.commit("two")
        git(self.repo, "checkout", "-q", "--detach", old)
        state = self.state("--sha", seen, "--commits", "30")
        self.assertEqual(state["seen_state"], "not_ancestor")
        self.assertIsNone(state["count"])  # a 0 here would read as "nothing changed"
        self.assertIsNone(state["commits"])

    def test_unknown_sha(self):
        self.commit("one")
        state = self.state("--sha", "abcdef1234")
        self.assertEqual(state["seen_state"], "unknown")
        self.assertIsNone(state["count"])

    def test_dirty(self):
        self.commit("one")
        with open(os.path.join(self.repo, "new.txt"), "w", encoding="utf-8") as f:
            f.write("x")
        self.assertTrue(self.state()["dirty"])

    def test_bad_sha_is_refused_before_git_runs(self):
        self.commit("one")
        outside = os.path.join(self.tmp.name, "written.txt")
        for bad in (f"--output={outside}", "HEAD", "abc", "abc..def", "abc 1234", "g" * 8, "a" * 65):
            result = run("--repo", self.repo, f"--sha={bad}")
            self.assertEqual(result.returncode, 2, bad)
            self.assertEqual(result.stdout, "", bad)
        self.assertFalse(os.path.exists(outside))

    def test_bad_commits_value(self):
        self.commit("one")
        for bad in ("0", "-1", "x"):
            self.assertEqual(run("--repo", self.repo, f"--commits={bad}").returncode, 2, bad)

    def test_not_a_repo_or_missing(self):
        plain = os.path.join(self.tmp.name, "plain")
        os.mkdir(plain)
        for path in (plain, os.path.join(self.tmp.name, "missing")):
            result = run("--repo", path)
            self.assertEqual(result.returncode, 1, path)
            self.assertEqual(result.stdout, "", path)
            self.assertNotEqual(result.stderr, "", path)
            self.assertNotIn("Traceback", result.stderr, path)

    def test_repo_config_cannot_run_fsmonitor(self):
        self.commit("one")
        marker = os.path.join(self.tmp.name, "ran.txt").replace("\\", "/")
        git(self.repo, "config", "core.fsmonitor", f"touch '{marker}'; true")
        self.state()
        self.assertFalse(os.path.exists(marker))

    def test_repo_config_cannot_add_signature_output(self):
        seen = self.commit("one")
        self.commit("two")
        git(self.repo, "config", "log.showSignature", "true")
        state = self.state("--sha", seen, "--commits", "30")
        self.assertEqual([c.split(" ", 1)[1] for c in state["commits"]], ["two"])

    # Regressions from the 2026-11-02 spec-only test of this script.
    def test_line_separators_in_subjects_do_not_break_the_list(self):
        seen = self.commit("base")
        self.commit("oldest unseen")
        self.commit("a b c")
        self.commit("newest")
        state = self.state("--sha", seen, "--commits", "2")
        self.assertEqual(len(state["commits"]), 2)
        self.assertTrue(state["truncated"])
        self.assertEqual(state["commits"][1].split(" ", 1)[1], "a b c")
        self.assertFalse(self.state("--sha", seen, "--commits", "3")["truncated"])
        self.assertEqual(len(self.state("--sha", seen, "--commits", "3")["commits"]), 3)

    def test_sha_with_a_trailing_newline_is_refused(self):
        self.commit("one")
        self.assertEqual(run("--repo", self.repo, "--sha", "abc1234\n").returncode, 2)

    def test_repo_log_encoding_cannot_damage_subjects(self):
        seen = self.commit("one")
        self.commit("İğüş")
        git(self.repo, "config", "i18n.logOutputEncoding", "ISO-8859-9")
        self.assertEqual(self.state("--sha", seen, "--commits", "1")["commits"][0].split(" ", 1)[1], "İğüş")

    def test_repo_config_cannot_hide_untracked_files(self):
        self.commit("one")
        git(self.repo, "config", "status.showUntrackedFiles", "no")
        with open(os.path.join(self.repo, "new.txt"), "w", encoding="utf-8") as f:
            f.write("x")
        self.assertTrue(self.state()["dirty"])

    def test_huge_commit_limit(self):
        seen = self.commit("one")
        self.commit("two")
        state = self.state("--sha", seen, "--commits", "99999999999999999999")
        self.assertEqual((len(state["commits"]), state["truncated"]), (1, False))

    def test_missing_path_message_stays_on_one_line(self):
        result = run("--repo", os.path.join(self.tmp.name, "no\nsuch"))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(result.stderr.strip().splitlines()), 1)

    def test_git_environment_cannot_redirect_the_repo(self):
        head = self.commit("one")
        other = os.path.join(self.tmp.name, "other")
        os.mkdir(other)
        subprocess.run(["git", "init", "-q", other], check=True)
        git(other, "commit", "-q", "--allow-empty", "-m", "other")
        env = {**os.environ, "GIT_DIR": os.path.join(other, ".git")}
        result = subprocess.run([sys.executable, SCRIPT, "--repo", self.repo], capture_output=True,
                                text=True, encoding="utf-8", timeout=60, env=env)
        state = json.loads(result.stdout)
        self.assertEqual(state["head"], head[:len(state["head"])])

    def test_branch_named_like_a_sha_is_not_taken_as_the_sha(self):
        self.commit("one")
        self.commit("two")
        git(self.repo, "branch", "deadbee", "HEAD~1")
        state = self.state("--sha", "deadbee")
        self.assertEqual((state["seen_state"], state["count"]), ("unknown", None))

    def test_uppercase_sha(self):
        seen = self.commit("one")
        self.commit("two")
        self.assertEqual(self.state("--sha", seen[:10].upper())["count"], 1)

    def test_a_sha_that_is_not_a_commit_is_unknown(self):
        self.commit("one")
        with open(os.path.join(self.repo, "f.txt"), "w", encoding="utf-8") as f:
            f.write("x")
        blob = git(self.repo, "hash-object", "-w", "f.txt")
        self.assertEqual(self.state("--sha", blob)["seen_state"], "unknown")

    def test_non_ascii_subject(self):
        seen = self.commit("one")
        self.commit("İğüş")
        state = self.state("--sha", seen, "--commits", "30")
        self.assertEqual(state["commits"][0].split(" ", 1)[1], "İğüş")


if __name__ == "__main__":
    unittest.main()
