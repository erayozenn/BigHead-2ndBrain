"""Tests for lib/project_pages.py. Run: python -m unittest discover lib/tests"""

import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import project_pages as pp  # noqa: E402

TODAY = date(2026, 11, 10)

HUB = """---
type: project
---
# demo

## Current state
As of 2026-11-01: 📅 2026-11-09 in another section is not a step.

## Next step
1. Ship the release 📅 2026-11-12
2. Review PR #4 📅 2026-11-08
3. Plan v2 📅 2026-12-30

## Decisions
- 2026-11-01: x. Why: y.
"""


class SectionTest(unittest.TestCase):
    def test_returns_body_until_next_heading(self):
        body = pp.section(HUB, "Next step")
        self.assertIn("Ship the release", body)
        self.assertNotIn("Why:", body)

    def test_missing_section_is_none(self):
        self.assertIsNone(pp.section(HUB, "Procedures"))

    def test_heading_inside_code_fence_is_ignored(self):
        text = "# x\n\n```\n## Procedures\n- fake\n```\n"
        self.assertIsNone(pp.section(text, "Procedures"))

    def test_trailing_spaces_and_crlf(self):
        text = "# x\r\n\r\n## People  \r\n- Ana merges\r\n"
        self.assertIn("Ana merges", pp.section(text, "People"))

    def test_deeper_heading_stays_in_section(self):
        text = "## Procedures\n### Before PR\n- run tests\n## Related\n"
        body = pp.section(text, "Procedures")
        self.assertIn("run tests", body)
        self.assertNotIn("Related", body)


class DueItemsTest(unittest.TestCase):
    def test_overdue_and_near_only_sorted_by_date(self):
        items = pp.due_items(HUB, TODAY)
        self.assertEqual([i["date"] for i in items], ["2026-11-08", "2026-11-12"])
        self.assertEqual(items[0]["days"], -2)
        self.assertEqual(items[1]["days"], 2)
        self.assertEqual(items[0]["step"], "Review PR #4")

    def test_window_is_seven_days_inclusive(self):
        text = "## Next step\n1. a 📅 2026-11-17\n2. b 📅 2026-11-18\n"
        self.assertEqual([i["step"] for i in pp.due_items(text, TODAY)], ["a"])

    def test_due_today(self):
        items = pp.due_items("## Next step\n- [ ] demo 📅 2026-11-10\n", TODAY)
        self.assertEqual(items[0]["days"], 0)
        self.assertEqual(items[0]["step"], "demo")

    def test_only_next_step_section(self):
        self.assertNotIn("2026-11-09", [i["date"] for i in pp.due_items(HUB, TODAY)])

    def test_invalid_date_is_ignored(self):
        self.assertEqual(pp.due_items("## Next step\n1. x 📅 2026-02-30\n2. y 📅 soon\n", TODAY), [])

    def test_done_task_is_ignored(self):
        self.assertEqual(pp.due_items("## Next step\n- [x] done 📅 2026-11-09\n", TODAY), [])

    def test_no_next_step(self):
        self.assertEqual(pp.due_items("# x\n", TODAY), [])

    def test_long_step_is_shortened(self):
        text = "## Next step\n1. " + "w" * 200 + " 📅 2026-11-11\n"
        step = pp.due_items(text, TODAY)[0]["step"]
        self.assertLessEqual(len(step), pp.MAX_STEP)
        self.assertTrue(step.endswith("..."))

    def test_variation_selector_is_accepted(self):  # some editors add U+FE0F after the emoji
        items = pp.due_items("## Next step\n1. x \U0001F4C5️ 2026-11-11\n", TODAY)
        self.assertEqual(items[0]["step"], "x")


OVERVIEW = """# demo overview

## People
- Ana merges.

## Procedures
Checklists. The repo's CLAUDE.md wins.

### Before a PR
- Own branch.
- Tests green.

### Before a measurement
- Preregister first.

### Before a Release or browser check
- Check stale JS.

## Related
- ### Before a push (not a heading here)
"""


class ChecklistTest(unittest.TestCase):
    def test_pr_picks_before_a_pr(self):
        heading, body = pp.checklist(OVERVIEW, "pr")
        self.assertEqual(heading, "Before a PR")
        self.assertEqual(body, "- Own branch.\n- Tests green.")

    def test_push_falls_back_to_pr(self):
        self.assertEqual(pp.checklist(OVERVIEW, "push")[0], "Before a PR")

    def test_push_prefers_its_own_section(self):
        text = OVERVIEW.replace("### Before a measurement", "### Before a push\n- Rebase.\n\n### Before a measurement")
        self.assertEqual(pp.checklist(text, "push"), ("Before a push", "- Rebase."))

    def test_merge_uses_release_case_insensitive(self):
        self.assertEqual(pp.checklist(OVERVIEW, "merge"), ("Before a Release or browser check", "- Check stale JS."))

    def test_merge_prefers_merge_section(self):
        text = OVERVIEW.replace("### Before a measurement", "### Before merging\n- Squash.\n\n### Before a measurement")
        self.assertEqual(pp.checklist(text, "merge")[0], "Before merging")

    def test_merge_without_section_is_none(self):
        text = OVERVIEW.replace("### Before a Release or browser check\n- Check stale JS.\n", "")
        self.assertIsNone(pp.checklist(text, "merge"))

    def test_no_procedures_section_is_none(self):
        self.assertIsNone(pp.checklist("# x\n\n### Before a PR\n- a\n", "pr"))

    def test_empty_body_is_none(self):
        self.assertIsNone(pp.checklist("## Procedures\n### Before a PR\n\n### Before a push\n- a\n", "pr"))

    def test_pull_request_wording_and_unknown_kind(self):
        text = "## Procedures\n### Before a pull request\n- a\n"
        self.assertEqual(pp.checklist(text, "pr")[0], "Before a pull request")
        self.assertIsNone(pp.checklist(text, "deploy"))

    def test_word_must_be_whole(self):
        self.assertIsNone(pp.checklist("## Procedures\n### Before a preview\n- a\n", "pr"))


class KindsInTest(unittest.TestCase):
    def test_kinds_in_order_without_repeats(self):
        self.assertEqual(pp.kinds_in("git push && gh pr create --fill; git push"), ["push", "pr"])
        self.assertEqual(pp.kinds_in("gh -R a/b pr merge 3"), ["merge"])

    def test_quoted_and_lookalike_text_is_not_a_kind(self):
        for cmd in ["echo 'git push'", "git commit -m \"git push later\"", "git pushd", "gh pr view 3"]:
            with self.subTest(cmd=cmd):
                self.assertEqual(pp.kinds_in(cmd), [])

    def test_answer_comment_is_not_a_kind(self):
        self.assertEqual(pp.kinds_in("git push\n# bighead-checklist: 1 done; 2 done"), ["push"])


class CountItemsTest(unittest.TestCase):
    def test_top_level_list_lines(self):
        body = "Intro line.\n- a\n  - nested, not counted\n* b\n+ c\n1. d\n2) e\n- [ ] f\n"
        self.assertEqual(pp.count_items(body), 6)

    def test_prose_and_fenced_lines_are_not_items(self):
        self.assertEqual(pp.count_items("Just check the tests.\n```\n- not an item\n```\n"), 0)


class ParseAnswerTest(unittest.TestCase):
    def check(self, command, expected):
        return pp.parse_answer(command, expected)

    def test_valid_line_with_all_entry_kinds(self):
        a = self.check("git push\n# bighead-checklist: 1 done; 2 n/a: no CSS; 3 user ok: push anyway",
                       3)
        self.assertTrue(a["ok"], a)
        self.assertEqual((a["done"], a["n_a"], a["user_ok"]), (1, 1, 1))

    def test_numbers_optional_case_and_spaces_free(self):
        self.assertTrue(self.check("git push   #bighead-checklist:Done ;N/A : x", 2)["ok"])

    def test_missing_line(self):
        self.assertEqual(self.check("git push", 2)["problem"], "missing")

    def test_wrong_count(self):
        self.assertEqual(self.check("git push # bighead-checklist: 1 done", 2)["problem"], "count")

    def test_bare_not_done_is_refused(self):
        a = self.check("git push # bighead-checklist: 1 done; 2 not done", 2)
        self.assertFalse(a["ok"])
        self.assertEqual(a["problem"], "not done")

    def test_reason_required(self):
        for entry in ("n/a", "n/a:", "user ok", "user ok:  "):
            with self.subTest(entry=entry):
                a = self.check(f"git push # bighead-checklist: 1 done; 2 {entry}", 2)
                self.assertEqual(a["problem"], "entry")

    def test_unknown_entry(self):
        self.assertEqual(self.check("git push # bighead-checklist: 1 ok; 2 done", 2)["problem"], "entry")

    def test_zero_items_needs_one_entry(self):
        self.assertTrue(self.check("git push # bighead-checklist: done", 0)["ok"])
        self.assertEqual(self.check("git push # bighead-checklist:", 0)["problem"], "count")


if __name__ == "__main__":
    unittest.main()
