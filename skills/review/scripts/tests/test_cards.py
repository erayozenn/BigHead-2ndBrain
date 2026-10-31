"""Tests for cards.py. Run: python -m unittest discover skills/review/scripts/tests"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

CARDS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cards.py")

DECK = """---
type: note
author: claude
---
> [!summary]- For future agent
> What: cards. Why kept: review. Goes stale: never.

#flashcards/metrics
What does precision measure?::Of predicted positives, the share that is right [[classification-metrics]]
<!--SR:!2026-10-20,3,250-->
Formula of recall?::TP / (TP + FN) [[classification-metrics]]
<!--SR:!2026-11-20,10,270-->
Precision:::TP / (TP + FP)
<!--SR:!2026-11-05,4,250!2026-10-01,2,230-->
When is accuracy misleading?::On imbalanced data [[classification-metrics]]

#flashcards/nb
Why is Naive Bayes
called naive?
?
It assumes features are independent
given the class.
<!--SR:!2026-10-30,1,230-->
"""


def run(*args):
    result = subprocess.run([sys.executable, CARDS, *args], capture_output=True, text=True,
                            encoding="utf-8", timeout=60)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


class CardsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = self.tmp.name
        os.makedirs(os.path.join(self.vault, "cards"))
        self.file = os.path.join(self.vault, "cards", "cards-metrics.md")
        with open(self.file, "w", encoding="utf-8", newline="\n") as f:
            f.write(DECK)

    def tearDown(self):
        self.tmp.cleanup()

    def test_stats(self):
        out = run("stats", "--vault", self.vault, "--today", "2026-10-31")
        self.assertEqual(out["cards"], 5)
        self.assertEqual(out["new"], 1)          # accuracy card, never reviewed
        self.assertEqual(out["due"], 3)          # precision, reversed (one side due), NB
        questions = [c["question"] for c in out["due_cards"]]
        self.assertEqual(questions[0], "Precision")  # earliest due date first
        self.assertIn("Why is Naive Bayes called naive?", questions)
        self.assertNotIn("Formula of recall?", questions)

    def test_deck_filter(self):
        out = run("stats", "--vault", self.vault, "--today", "2026-10-31", "--deck", "nb")
        self.assertEqual((out["cards"], out["due"]), (1, 1))

    def test_no_cards_dir(self):
        os.remove(self.file)
        os.rmdir(os.path.join(self.vault, "cards"))
        out = run("stats", "--vault", self.vault)
        self.assertEqual((out["cards"], out["files"]), (0, []))

    def test_prefix_detects_append_only(self):
        before = run("prefix", "--file", self.file)
        with open(self.file, "a", encoding="utf-8", newline="\n") as f:
            f.write("New question?::New answer\n")
        after = run("prefix", "--file", self.file, "--lines", str(before["lines"]))
        self.assertEqual(before["sha256"], after["sha256"])
        with open(self.file, encoding="utf-8") as f:
            text = f.read()
        with open(self.file, "w", encoding="utf-8", newline="\n") as f:
            f.write(text.replace("<!--SR:!2026-10-20,3,250-->\n", ""))
        broken = run("prefix", "--file", self.file, "--lines", str(before["lines"]))
        self.assertNotEqual(before["sha256"], broken["sha256"])


if __name__ == "__main__":
    unittest.main()
