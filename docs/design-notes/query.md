# Design notes — query (end-to-end tests, 2026-10-30)

Skill: `skills/query/SKILL.md`. Decisions before writing it: log only gaps and saved answers;
when the wiki is not enough, read raw/ and propose an ingest (no web search); find pages with
index + Grep over `aliases`, no new script (real search is Phase 3).

Test vault: 9 concept/synthesis pages, 6 source pages.

| # | Question (Turkish) | Budget | Path tested | Read | Result |
|---|---|---|---|---|---|
| 1 | a definition from course notes | quick | TR terms → EN expansion, (disputed) carried over | 3.8 / 12 KiB | correct; marker kept |
| 2 | when to prefer LLM Wiki vs RAG | deep | multi-page, existing synthesis | 19.7 / 128 KiB | correct; synthesis alone was enough |
| 3 | where to put information in a long context | standard | alias hit in one step | 4.3 / 48 KiB | correct |
| 4 | how transformer attention works | standard | gap → raw/ → ingest proposal → log | ~1 / 48 KiB | gap stated, raw mentions cited, general knowledge labelled |

## Findings

- **Query expansion carries Turkish questions.** "öğrenme oranı" was not in any `aliases`; the page
  was found through the English terms (learning rate, step size). Missing aliases are
  worth adding when a query exposes them (done for that page).
- **An existing synthesis makes extra reads redundant.** Test 2 read 3 more pages (~11.7 KiB) that
  added two details. Added to the skill: read a matching synthesis first, other pages only to check
  or fill gaps.
- **Save offer vs existing synthesis.** Added: if the answer restates a synthesis, say so; offer to
  extend it instead of a new page.
- **Pages already read in the session** are not re-read but still count toward the budget. Fine.
- **raw/ PDFs cannot be grepped.** Test 4 searched PDF text that happened to be in the scratchpad
  from earlier work. In a fresh session the gap step would have to run `pdf_pages.py text` on every
  raw PDF. Proposal (not decided): a gitignored text cache, e.g. `.cache/raw-text/<path>.txt`,
  written by ingest and grepped by query; Phase 3 BM25 could index the same cache.
- **General knowledge in a gap answer** was given, clearly labelled "(not in the vault)". The skill
  allows it; keep it short and always pair it with a source to ingest.
  **Done 2026-10-30:** `pdf_pages.py cache` → `.cache/raw-text/<path under raw>.txt` + manifest
  (size, mtime). Safeguards: `--all` caches only PDFs cited in `wiki/` (uncited = not ingested =
  not checked for sensitive data → reported, never cached); orphans (raw file gone, e.g. archived)
  reported, deleted only with `--prune` after the user agrees. Tested on a throwaway vault:
  uncited PDF skipped, stale cache (mtime change) falls back to pypdf and is rewritten, path
  outside raw/ and missing args exit 2, orphan reported then pruned. Real vault: cache text
  byte-identical to `text` output; whole-wiki verify 1.5 s → 0.34 s. Grep finds the cache only
  with `.cache/raw-text` as explicit path (gitignored + hidden), which the query skill now says.
- **allowed-tools** only pre-approves `wc -c`. Grep/Read/Glob need no Bash. Searching raw PDF
  text through Bash would prompt — another argument for the cache.
