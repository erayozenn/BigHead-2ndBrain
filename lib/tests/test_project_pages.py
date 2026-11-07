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


if __name__ == "__main__":
    unittest.main()
