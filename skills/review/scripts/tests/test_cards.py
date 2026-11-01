"""Tests for cards.py. Run: python -m unittest discover skills/review/scripts/tests"""

import hashlib
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
        self.assertEqual(out["cards"], 6)        # the reversed card is two cards
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

    # Regressions from the 2026-11-01 black-box test of hooks and cards.
    def write_cards(self, text, name="cards-metrics.md"):
        path = os.path.join(self.vault, "cards", name)
        with open(path, "wb") as f:
            f.write(text if isinstance(text, bytes) else text.encode("utf-8"))
        return path

    def counts(self):
        out = run("stats", "--vault", self.vault, "--today", "2026-10-31")
        return out["cards"], out["new"], out["due"]

    def test_reversed_cards_count_per_direction(self):
        self.write_cards("Q:::A\n")
        self.assertEqual(self.counts(), (2, 2, 0))
        self.write_cards("Q:::A\n<!--SR:!2026-10-01,2,230-->\n")
        self.assertEqual(self.counts(), (2, 1, 1))
        self.write_cards("Q:::A\n<!--SR:!2026-10-01,2,230!2026-10-02,2,230-->\n")
        self.assertEqual(self.counts(), (2, 0, 2))
        self.write_cards("Q\n??\nA\n")
        self.assertEqual(self.counts(), (2, 2, 0))

    def test_invalid_sr_date_is_reported_not_fatal(self):
        self.write_cards("Bad::1\n<!--SR:!2026-13-45,2,230-->\nGood::2\n<!--SR:!2026-10-01,2,230-->\n")
        out = run("stats", "--vault", self.vault, "--today", "2026-10-31")
        self.assertEqual((out["cards"], out["new"], out["due"]), (2, 0, 1))
        self.assertEqual([w["date"] for w in out["warnings"]], ["2026-13-45"])
        self.assertEqual(out["warnings"][0]["line"], 1)

    def test_only_cards_prefixed_files_count(self):
        self.write_cards("a::b\n", name="notes.md")
        self.write_cards("a::b\n")
        self.assertEqual(self.counts(), (1, 1, 0))

    def test_prefix_is_a_byte_proof(self):
        path = self.write_cards(b"a::1\nb::2\n")
        before = run("prefix", "--file", path)
        self.assertEqual(before["sha256"], hashlib.sha256(b"a::1\nb::2\n").hexdigest())
        self.assertEqual(before["bytes"], 9 + 1)
        self.write_cards(b"a::1\nb::2")  # final newline removed
        self.assertNotEqual(before["sha256"], run("prefix", "--file", path, "--bytes", "10")["sha256"])
        self.assertNotEqual(before["sha256"], run("prefix", "--file", path, "--lines", "2")["sha256"])

    def test_prefix_append_to_empty_file_and_no_final_newline(self):
        path = self.write_cards(b"")
        before = run("prefix", "--file", path)
        self.assertEqual(before["lines"], 0)
        self.write_cards(b"a::1\n")
        for flag, value in (("--bytes", before["bytes"]), ("--lines", before["lines"])):
            self.assertEqual(before["sha256"], run("prefix", "--file", path, flag, str(value))["sha256"])
        path = self.write_cards(b"a::1")
        before = run("prefix", "--file", path)
        self.write_cards(b"a::1\nb::2\n")
        self.assertEqual(before["sha256"], run("prefix", "--file", path, "--bytes", str(before["bytes"]))["sha256"])

    def test_prefix_handles_non_utf8(self):
        path = self.write_cards(b"caf\xe9::1\n")
        self.assertEqual(run("prefix", "--file", path)["sha256"], hashlib.sha256(b"caf\xe9::1\n").hexdigest())

    def test_prefix_rejects_negative_counts(self):
        for flag in ("--lines", "--bytes"):
            result = subprocess.run([sys.executable, CARDS, "prefix", "--file", self.file, flag, "-1"],
                                    capture_output=True, text=True, timeout=60)
            self.assertNotEqual(result.returncode, 0)

    # Decisions on the ambiguous cases of that test, 2026-11-01: counts follow the plugin's parser.
    def test_code_fences_hold_no_cards(self):
        self.write_cards("Real::1\n\n```\nfenced::2\n?\n```\n\n~~~\nalso::3\n~~~\n")
        self.assertEqual(self.counts(), (1, 1, 0))

    def test_unclosed_fence_runs_to_end_of_file(self):
        self.write_cards("Real::1\n\n```\nfenced::2\n\nmore::3\n")
        self.assertEqual(self.counts(), (1, 1, 0))

    def test_blank_line_in_a_fenced_answer_keeps_the_card_open(self):
        self.write_cards("Q\n?\n```\nline\n\nmore\n```\nend\n<!--SR:!2026-10-01,2,230-->\n")
        self.assertEqual(self.counts(), (1, 0, 1))

    def test_marker_in_inline_code_is_no_card(self):
        self.write_cards("Use `std::vector` here\n\nThe `a` token::answer\n")
        self.assertEqual(self.counts(), (1, 1, 0))

    def test_inline_marker_replaces_an_open_multiline_card(self):
        self.write_cards("Line::one\n?\nanswer\n")   # question line is itself a card
        self.assertEqual(self.counts(), (1, 1, 0))
        self.write_cards("Question\n?\nanswer::x\n")  # the plugin drops the multi-line card
        out = run("stats", "--vault", self.vault, "--today", "2026-10-31")
        self.assertEqual(out["cards"], 1)

    def test_separator_without_a_question_is_no_card(self):
        self.write_cards("\n?\nanswer\n")
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_empty_sides_stay_cards_like_the_plugin(self):
        self.write_cards("::A\n\nQ::\n")
        self.assertEqual(self.counts(), (2, 2, 0))

    def test_deck_forms_all_match(self):
        self.write_cards("#flashcards/ml\nQ::A\n")
        for deck in ("ml", "ML", "flashcards/ml", "#flashcards/ml", "#Flashcards/ML"):
            out = run("stats", "--vault", self.vault, "--deck", deck)
            self.assertEqual(out["cards"], 1, deck)
        self.assertEqual(run("stats", "--vault", self.vault, "--deck", "flashcards")["cards"], 1)
        self.assertEqual(run("stats", "--vault", self.vault, "--deck", "m")["cards"], 0)

    def test_deck_comes_from_the_tag_not_the_file_name(self):
        self.write_cards("#flashcards/ml\nQ::A\n", name="cards-other.md")
        os.remove(self.file)
        self.assertEqual(run("stats", "--vault", self.vault, "--deck", "other")["cards"], 0)

    def test_missing_vault_is_an_error(self):
        result = subprocess.run([sys.executable, CARDS, "stats", "--vault", os.path.join(self.vault, "none")],
                                capture_output=True, text=True, timeout=60)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_unreadable_file_gives_an_error_without_traceback(self):
        for target in (self.vault, os.path.join(self.vault, "none.md")):
            result = subprocess.run([sys.executable, CARDS, "prefix", "--file", target],
                                    capture_output=True, text=True, timeout=60)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
