#!/usr/bin/env python3
"""Measure how well page-finding methods retrieve the right pages. Read-only. Standard library only.

Usage:
  eval_search.py --vault <dir> --queries <file> --split dev|test|all
                 [--method grep|bm25|bm25-tr]... [--ranked NAME=<file>]...
                 [--expanded NAME=<method>:<file>]... [--prefix 4]

--queries     JSON: {"queries": [{"id", "split", "q", "gold": [page stems]}]}. An empty gold list
              marks a question the vault cannot answer.
--ranked      JSON from an outside method: {"<id>": [pages, best first]}.
--expanded    JSON of rewritten queries: {"<id>": "<text>"}, then ranked by the named method.

Prints JSON, per method: found_at_5 (queries with a gold page in the top 5), recall_at_5, mrr (first
gold page within the top 5, else 0), found, missed, negatives_returning_pages, no_input_for and
found_by_lang. Exit codes: 0 reported, 1 bad or unreadable input, 2 bad arguments.

Keep the test split for one final run: settings tuned on it would no longer measure anything.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from search import (DEFAULT_PREFIX, METHODS, load_pages, non_negative_int, rank,  # noqa: E402
                    vault_path)

TOP = 5


def fail(message: str) -> None:
    print(f"eval_search: {message}".replace("\n", "\\n"), file=sys.stderr)
    sys.exit(1)


def read_json(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as error:
        fail(f"cannot read {path}: {error}")


def is_names(value) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def read_ranked(path: str) -> dict[str, list[str]]:
    data = read_json(path)
    if not isinstance(data, dict) or not all(is_names(pages) for pages in data.values()):
        fail(f'{path}: expected {{"<id>": [pages, best first]}}')
    return data


def read_expanded(path: str) -> dict[str, str]:
    data = read_json(path)
    if not isinstance(data, dict) or not all(isinstance(text, str) for text in data.values()):
        fail(f'{path}: expected {{"<id>": "<text>"}}')
    return data


def load_queries(path: str, stems: set[str]) -> list[dict]:
    data = read_json(path)
    rows = data.get("queries") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        fail(f'{path}: expected {{"queries": [...]}}')
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not all(key in row for key in ("id", "split", "q", "gold")):
            fail(f"{path}: every query needs id, split, q and gold: {row}")
        if row["id"] in seen:
            fail(f"{path}: duplicate id {row['id']}")
        seen.add(row["id"])
        if not is_names(row["gold"]):
            fail(f"{path}: {row['id']}: gold must be a list of page names")
        unknown = [page for page in row["gold"] if page not in stems]
        if unknown:
            fail(f"{path}: {row['id']} names pages that do not exist: {unknown}")
    return rows


def score_method(rows: list[dict], ranked_by_id: dict[str, list[str]], no_input: list[str]) -> dict:
    positives = [row for row in rows if row["gold"]]
    found, missed, by_lang = [], [], {}
    recall = reciprocal = 0.0
    for row in positives:
        top = ranked_by_id.get(row["id"], [])[:TOP]
        gold = set(row["gold"])
        hits = [i for i, page in enumerate(top, 1) if page in gold]
        (found if hits else missed).append(row["id"])
        recall += len(gold & set(top)) / len(gold)
        reciprocal += 1 / hits[0] if hits else 0
        if "lang" in row:
            tally = by_lang.setdefault(row["lang"], [0, 0])
            tally[0] += bool(hits)
            tally[1] += 1
    total = len(positives) or 1
    return {
        "found_at_5": len(found),
        "recall_at_5": recall / total,
        "mrr": reciprocal / total,
        "found": found,
        "missed": missed,
        "negatives_returning_pages": [row["id"] for row in rows
                                      if not row["gold"] and ranked_by_id.get(row["id"])],
        "no_input_for": no_input,
        "found_by_lang": by_lang,
    }


def ranked_arg(value: str) -> tuple[str, str]:
    name, sep, path = value.partition("=")
    if not (name and sep and path):
        raise ValueError
    return name, path


def expanded_arg(value: str) -> tuple[str, str, str]:
    name, sep, rest = value.partition("=")
    method, sep2, path = rest.partition(":")
    if not (name and sep and sep2 and path) or method not in METHODS:
        raise ValueError
    return name, method, path


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--queries", required=True)
    parser.add_argument("--split", required=True, choices=("dev", "test", "all"))
    parser.add_argument("--method", action="append", default=[], choices=METHODS)
    parser.add_argument("--ranked", action="append", default=[], type=ranked_arg)
    parser.add_argument("--expanded", action="append", default=[], type=expanded_arg)
    parser.add_argument("--prefix", type=non_negative_int, default=DEFAULT_PREFIX)
    args = parser.parse_args()
    if not (args.method or args.ranked or args.expanded):
        parser.error("name at least one --method, --ranked or --expanded")
    names = [*set(args.method), *(item[0] for item in args.ranked), *(item[0] for item in args.expanded)]
    if len(names) != len(set(names)):
        parser.error("two methods share one name")

    pages = load_pages(vault_path(args.vault))
    rows = load_queries(args.queries, {page.stem for page in pages})
    if args.split != "all":
        rows = [row for row in rows if row["split"] == args.split]

    def run(method: str, text_by_id: dict[str, str]) -> dict[str, list[str]]:
        return {row["id"]: [stem for stem, _ in rank(pages, text_by_id[row["id"]], method, args.prefix)]
                for row in rows if row["id"] in text_by_id}

    original = {row["id"]: row["q"] for row in rows}
    methods = {}
    for method in args.method:
        methods[method] = score_method(rows, run(method, original), [])
    for name, path in args.ranked:
        ranked = read_ranked(path)
        methods[name] = score_method(rows, ranked, [row["id"] for row in rows if row["id"] not in ranked])
    for name, method, path in args.expanded:
        expanded = read_expanded(path)
        methods[name] = score_method(rows, run(method, expanded),
                                     [row["id"] for row in rows if row["id"] not in expanded])
    print(json.dumps({"split": args.split, "prefix": args.prefix,
                      "positive": sum(bool(row["gold"]) for row in rows),
                      "negative": sum(not row["gold"] for row in rows),
                      "methods": methods}, ensure_ascii=False))


if __name__ == "__main__":
    main()
