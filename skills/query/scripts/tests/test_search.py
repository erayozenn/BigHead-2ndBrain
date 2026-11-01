"""Tests for search.py and eval_search.py. Run: python -m unittest discover skills/query/scripts/tests"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEARCH = os.path.join(SCRIPTS, "search.py")
EVAL = os.path.join(SCRIPTS, "eval_search.py")


def run(script, *args):
    return subprocess.run([sys.executable, script, *args], capture_output=True, text=True,
                          encoding="utf-8", timeout=60)


def page(aliases="", body=""):
    return (f"---\ntype: concept\nstatus: active\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            f"tags: [zebra]\naliases: [{aliases}]\nsources: []\nauthor: claude\n"
            f"sensitivity: public\n---\n{body}\n")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.vault = self.tmp.name
        os.makedirs(os.path.join(self.vault, "wiki", "concepts"))

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text, folder="wiki/concepts"):
        path = os.path.join(self.vault, *folder.split("/"), f"{name}.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def search(self, query, *args):
        result = run(SEARCH, "--vault", self.vault, "--query", query, *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["results"]

    def pages(self, query, *args):
        return [r["page"] for r in self.search(query, *args)]


class SearchTest(Base):
    def test_more_occurrences_rank_higher(self):
        self.write("many", page(body="kiwi kiwi kiwi kiwi filler words here"))
        self.write("few", page(body="kiwi other filler words here again"))
        self.assertEqual(self.pages("kiwi", "--method", "bm25"), ["many", "few"])

    def test_rare_term_outweighs_common_term(self):
        self.write("rare", page(body="mango one two three"))
        for name in ("c1", "c2", "c3", "c4"):
            self.write(name, page(body="apple one two three"))
        self.assertEqual(self.pages("apple mango", "--method", "bm25")[0], "rare")

    def test_short_page_beats_long_page_at_equal_count(self):
        self.write("short", page(body="kiwi one"))
        self.write("long", page(body="kiwi " + "padding " * 200))
        self.assertEqual(self.pages("kiwi", "--method", "bm25"), ["short", "long"])

    def test_aliases_and_page_name_count_but_other_frontmatter_does_not(self):
        self.write("name-hit", page(body="nothing"))
        self.write("other", page(aliases="turşu", body="nothing"))
        self.assertEqual(self.pages("turşu", "--method", "bm25"), ["other"])
        self.assertEqual(self.pages("name", "--method", "bm25"), ["name-hit"])
        self.assertEqual(self.pages("zebra", "--method", "bm25"), [])
        self.assertEqual(self.pages("sensitivity", "--method", "bm25"), [])

    def test_alias_outranks_one_body_mention(self):
        self.write("in-alias", page(aliases="kiwi", body="one two three"))
        self.write("in-body", page(body="kiwi two three"))
        self.assertEqual(self.pages("kiwi", "--method", "bm25")[0], "in-alias")

    def test_only_wiki_pages_are_searched(self):
        self.write("kept", page(body="kiwi"))
        self.write("source-register", "kiwi kiwi", folder="wiki")
        self.write("private-note", page(body="kiwi"), folder="notes")
        self.write("hub", page(body="kiwi"), folder="projects/hub")
        self.assertEqual(self.pages("kiwi", "--method", "bm25"), ["kept"])

    def test_no_match_and_empty_query_return_nothing(self):
        self.write("a", page(body="kiwi"))
        self.assertEqual(self.search("absent", "--method", "bm25"), [])
        self.assertEqual(self.search("   ", "--method", "bm25"), [])
        self.assertEqual(self.search("the of and", "--method", "bm25"), [])

    def test_top_limits_and_ties_are_stable(self):
        for name in ("c", "a", "b"):
            self.write(name, page(body="kiwi same words"))
        self.assertEqual(self.pages("kiwi", "--method", "bm25", "--top", "2"), ["a", "b"])

    def test_plain_method_does_not_fold_or_stem(self):
        self.write("a", page(body="kisisel kelimeler"))
        self.assertEqual(self.pages("kişisel", "--method", "bm25"), [])
        self.assertEqual(self.pages("kelimesi", "--method", "bm25"), [])

    def test_turkish_method_folds_and_truncates(self):
        self.write("a", page(body="kisisel kelimeler"))
        self.assertEqual(self.pages("KİŞİSEL", "--method", "bm25-tr"), ["a"])
        self.assertEqual(self.pages("kelimesi", "--method", "bm25-tr"), ["a"])
        self.assertEqual(self.pages("kelimesi", "--method", "bm25-tr", "--prefix", "0"), [])

    def test_dotless_and_dotted_i_fold_together(self):
        self.write("a", page(body="ISIK"))
        self.assertEqual(self.pages("ışık", "--method", "bm25-tr"), ["a"])

    def test_turkish_stopwords_are_dropped(self):
        self.write("a", page(body="için kiwi"))
        self.assertEqual(self.pages("için", "--method", "bm25-tr"), [])

    def test_grep_method_prefers_alias_hits_and_counts_distinct_terms(self):
        self.write("alias", page(aliases="kiwi", body="other"))
        self.write("body", page(body="kiwi kiwi kiwi kiwi"))
        self.write("both", page(body="kiwi mango"))
        self.assertEqual(self.pages("kiwi", "--method", "grep")[0], "alias")
        self.assertEqual(self.pages("kiwi mango", "--method", "grep")[0], "both")

    def test_grep_matches_inside_words(self):
        self.write("a", page(body="kiwifruit"))
        self.assertEqual(self.pages("kiwi", "--method", "grep"), ["a"])

    def test_page_without_frontmatter_and_crlf_page_still_search(self):
        self.write("bare", "kiwi only\n")
        path = os.path.join(self.vault, "wiki", "concepts", "crlf.md")
        with open(path, "wb") as f:
            f.write(page(aliases="mango", body="one").replace("\n", "\r\n").encode("utf-8"))
        self.assertEqual(self.pages("kiwi", "--method", "bm25"), ["bare"])
        self.assertEqual(self.pages("mango", "--method", "bm25"), ["crlf"])

    def test_bad_arguments_exit_2_and_print_nothing(self):
        self.write("a", page(body="kiwi"))
        for extra in (["--top", "0"], ["--top", "x"], ["--method", "vector"], ["--prefix", "-1"]):
            result = run(SEARCH, "--vault", self.vault, "--query", "kiwi", *extra)
            self.assertEqual(result.returncode, 2, extra)
            self.assertEqual(result.stdout, "")

    def test_folder_without_wiki_exits_1_without_traceback(self):
        empty = os.path.join(self.tmp.name, "empty")
        os.mkdir(empty)
        for folder in (empty, os.path.join(self.tmp.name, "absent")):
            result = run(SEARCH, "--vault", folder, "--query", "kiwi")
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("Traceback", result.stderr)

    def test_unreadable_page_is_skipped_and_named(self):
        self.write("good", page(body="kiwi"))
        with open(os.path.join(self.vault, "wiki", "concepts", "bad.md"), "wb") as f:
            f.write(b"kiwi \xff\xfe")
        result = run(SEARCH, "--vault", self.vault, "--query", "kiwi", "--method", "bm25")
        self.assertEqual(result.returncode, 0)
        self.assertEqual([r["page"] for r in json.loads(result.stdout)["results"]], ["good"])
        self.assertIn("bad.md", result.stderr)

    # Regressions from the 2026-11-02 spec-only test of these scripts.
    def test_block_list_aliases_are_searched_and_other_lists_are_not(self):
        for name, eol, indent in (("lf", "\n", "  "), ("crlf", "\r\n", "  "), ("flat", "\n", "")):
            text = eol.join(["---", "tags:", f"{indent}- walrus", "aliases:", f"{indent}- nar{name}",
                             f'{indent}- "quoted{name}"', "sources:", f"{indent}- puffin", "---",
                             "ferret", ""])
            path = os.path.join(self.vault, "wiki", "concepts", f"p{name}.md")
            with open(path, "wb") as f:
                f.write(text.encode("utf-8"))
            for method in ("grep", "bm25", "bm25-tr"):
                self.assertEqual(self.pages(f"nar{name}", "--method", method, "--prefix", "0")
                                 if method == "bm25-tr" else self.pages(f"nar{name}", "--method", method),
                                 [f"p{name}"], (name, method))
            self.assertEqual(self.pages(f"quoted{name}", "--method", "bm25"), [f"p{name}"])
        self.assertEqual(self.pages("walrus", "--method", "bm25"), [])
        self.assertEqual(self.pages("puffin", "--method", "bm25"), [])

    def test_byte_order_mark_does_not_expose_frontmatter(self):
        path = os.path.join(self.vault, "wiki", "concepts", "bom.md")
        with open(path, "wb") as f:
            f.write(("﻿" + page(aliases="kiwi", body="mango")).encode("utf-8"))
        self.assertEqual(self.pages("zebra", "--method", "bm25"), [])
        self.assertEqual(self.pages("kiwi", "--method", "bm25"), ["bom"])

    def test_writes_nothing(self):
        self.write("a", page(body="kiwi"))
        before = sorted(os.path.join(d, f) for d, _, fs in os.walk(self.vault) for f in fs)
        self.search("kiwi", "--method", "bm25-tr")
        after = sorted(os.path.join(d, f) for d, _, fs in os.walk(self.vault) for f in fs)
        self.assertEqual(before, after)


class EvalTest(Base):
    def setUp(self):
        super().setUp()
        self.write("kiwi-page", page(body="kiwi fruit"))
        self.write("mango-page", page(body="mango fruit"))
        self.write("plum-page", page(body="plum fruit"))

    def queries(self, rows):
        path = os.path.join(self.tmp.name, "queries.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"queries": rows}, f)
        return path

    def evaluate(self, rows, *args, split="all"):
        result = run(EVAL, "--vault", self.vault, "--queries", self.queries(rows),
                     "--split", split, *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    @staticmethod
    def row(qid, q, gold, split="test"):
        return {"id": qid, "split": split, "q": q, "gold": gold}

    def test_metrics_by_hand(self):
        rows = [self.row("a", "kiwi", ["kiwi-page"]),
                self.row("b", "fruit", ["plum-page", "mango-page"]),
                self.row("c", "absent", ["plum-page"])]
        ranked = os.path.join(self.tmp.name, "ranked.json")
        with open(ranked, "w", encoding="utf-8") as f:
            json.dump({"a": ["kiwi-page"], "b": ["kiwi-page", "plum-page"], "c": []}, f)
        result = self.evaluate(rows, "--ranked", f"D={ranked}")["methods"]["D"]
        self.assertEqual(result["found_at_5"], 2)
        self.assertEqual(result["found"], ["a", "b"])
        self.assertEqual(result["missed"], ["c"])
        self.assertAlmostEqual(result["recall_at_5"], (1 + 0.5 + 0) / 3)
        self.assertAlmostEqual(result["mrr"], (1 + 0.5 + 0) / 3)

    def test_only_the_top_5_count(self):
        ranked = os.path.join(self.tmp.name, "ranked.json")
        with open(ranked, "w", encoding="utf-8") as f:
            json.dump({"a": ["x1", "x2", "x3", "x4", "x5", "kiwi-page"]}, f)
        result = self.evaluate([self.row("a", "kiwi", ["kiwi-page"])], "--ranked", f"D={ranked}")
        self.assertEqual(result["methods"]["D"]["found_at_5"], 0)
        self.assertEqual(result["methods"]["D"]["mrr"], 0)

    def test_split_filter_counts_only_that_split(self):
        rows = [self.row("d", "kiwi", ["kiwi-page"], split="dev"),
                self.row("t", "mango", ["mango-page"], split="test")]
        result = self.evaluate(rows, "--method", "bm25", split="dev")
        self.assertEqual((result["positive"], result["methods"]["bm25"]["found"]), (1, ["d"]))

    def test_negatives_count_apart_from_positives(self):
        rows = [self.row("a", "kiwi", ["kiwi-page"]), self.row("n", "fruit", []),
                self.row("m", "absent", [])]
        result = self.evaluate(rows, "--method", "bm25")
        self.assertEqual((result["positive"], result["negative"]), (1, 2))
        self.assertEqual(result["methods"]["bm25"]["mrr"], 1)
        self.assertEqual(result["methods"]["bm25"]["negatives_returning_pages"], ["n"])

    def test_expanded_queries_replace_the_question(self):
        rows = [self.row("a", "kivi meyvesi", ["kiwi-page"])]
        path = os.path.join(self.tmp.name, "expanded.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"a": "kiwi"}, f)
        result = self.evaluate(rows, "--method", "bm25", "--expanded", f"E=bm25:{path}")
        self.assertEqual(result["methods"]["bm25"]["found_at_5"], 0)
        self.assertEqual(result["methods"]["E"]["found_at_5"], 1)

    def test_a_query_missing_from_a_ranked_file_counts_as_missed_and_is_named(self):
        ranked = os.path.join(self.tmp.name, "ranked.json")
        with open(ranked, "w", encoding="utf-8") as f:
            json.dump({}, f)
        result = self.evaluate([self.row("a", "kiwi", ["kiwi-page"])], "--ranked", f"D={ranked}")
        self.assertEqual(result["methods"]["D"]["missed"], ["a"])
        self.assertEqual(result["methods"]["D"]["no_input_for"], ["a"])

    def test_bad_input_exits_1_and_prints_nothing(self):
        cases = {
            "unknown gold": [self.row("a", "kiwi", ["no-such-page"])],
            "duplicate id": [self.row("a", "kiwi", ["kiwi-page"]), self.row("a", "x", ["kiwi-page"])],
            "missing field": [{"id": "a", "q": "kiwi"}],
        }
        for name, rows in cases.items():
            result = run(EVAL, "--vault", self.vault, "--queries", self.queries(rows),
                         "--split", "all", "--method", "bm25")
            self.assertEqual(result.returncode, 1, name)
            self.assertEqual(result.stdout, "", name)
            self.assertNotIn("Traceback", result.stderr, name)

    def test_wrong_json_shapes_exit_1_without_traceback(self):
        queries = self.queries([self.row("a", "kiwi", ["kiwi-page"])])
        for option, spec, content in (
                ("--ranked", "D={}", ["kiwi-page"]), ("--ranked", "D={}", {"a": "kiwi-page"}),
                ("--expanded", "E=bm25:{}", ["kiwi"]), ("--expanded", "E=bm25:{}", {"a": ["kiwi"]})):
            path = os.path.join(self.tmp.name, "input.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(content, f)
            result = run(EVAL, "--vault", self.vault, "--queries", queries, "--split", "all",
                         option, spec.format(path))
            self.assertEqual(result.returncode, 1, (option, content))
            self.assertEqual(result.stdout, "", (option, content))
            self.assertNotIn("Traceback", result.stderr, (option, content))

    def test_gold_must_be_a_list_of_names(self):
        for gold in ("kiwi-page", {"kiwi-page": 1}, [1]):
            result = run(EVAL, "--vault", self.vault, "--queries",
                         self.queries([self.row("a", "kiwi", gold)]), "--split", "all",
                         "--method", "bm25")
            self.assertEqual(result.returncode, 1, gold)
            self.assertEqual(result.stdout, "", gold)
            self.assertNotIn("Traceback", result.stderr, gold)

    def test_two_methods_with_one_name_are_refused(self):
        path = self.queries([self.row("a", "kiwi", ["kiwi-page"])])
        ranked = os.path.join(self.tmp.name, "ranked.json")
        with open(ranked, "w", encoding="utf-8") as f:
            json.dump({"a": []}, f)
        result = run(EVAL, "--vault", self.vault, "--queries", path, "--split", "all",
                     "--method", "bm25", "--ranked", f"bm25={ranked}")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")

    def test_missing_or_broken_queries_file_exits_1(self):
        broken = os.path.join(self.tmp.name, "broken.json")
        with open(broken, "w", encoding="utf-8") as f:
            f.write("{")
        for path in (broken, os.path.join(self.tmp.name, "absent.json")):
            result = run(EVAL, "--vault", self.vault, "--queries", path, "--split", "all",
                         "--method", "bm25")
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("Traceback", result.stderr)

    def test_bad_arguments_exit_2(self):
        path = self.queries([self.row("a", "kiwi", ["kiwi-page"])])
        for extra in (["--split", "train", "--method", "bm25"], ["--split", "all"],
                      ["--split", "all", "--ranked", "noequals"],
                      ["--split", "all", "--expanded", "E=vector:x"]):
            result = run(EVAL, "--vault", self.vault, "--queries", path, *extra)
            self.assertEqual(result.returncode, 2, extra)
            self.assertEqual(result.stdout, "", extra)


if __name__ == "__main__":
    unittest.main()
