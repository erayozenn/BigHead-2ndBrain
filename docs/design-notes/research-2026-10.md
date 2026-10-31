# Design notes — research review (2026-10)

A deep-research report on Claude Code features, related LLM-wiki projects and learning research
was reviewed against the kit as it stood after Phase 2b. Each finding was checked against the
current Claude Code docs or a primary source before it was adopted. This note records what was
taken, what was not and why, and the input for Phase 3.

## Adopted

| Change | Evidence | Side effects checked |
|---|---|---|
| Vault CLAUDE.md target "under 200 lines" (was 500); lint WARNs above 200 | [Memory docs](https://code.claude.com/docs/en/memory): target under 200 lines per CLAUDE.md; `@imports` do not reduce context cost | Template is ~140 lines; existing vaults unaffected (WARN only, no ERROR) |
| Rule 11: `claude -p` / Agent SDK count against the same subscription limits (as of 2026-10) | A planned 2026-06-15 split into separate credits was paused; reported by several news sites citing Anthropic's help page (help page itself not read) | Dated; tells the user to check `/usage`. Kit rule "works with no API key" unchanged |
| Lint suggests `/doctor prompt-audit` when CLAUDE.md / rules.md changed | [Memory docs](https://code.claude.com/docs/en/memory): built-in, v2.1.283+, proposes edits, changes nothing until asked | Claude cannot run it; a suggestion line only. `git log` added to lint's allowed tools |
| Query routes by question type (lookup / synthesis / multi-part) | [Cochran 2026](https://arxiv.org/abs/2605.18490) (preregistered, 24 papers, 13 questions): the wiki costs ~21× the tokens of single-round RAG per query; its advantage is on synthesis, not on single facts; v3 found no established citation-support advantage | A user-given budget always wins. Multi-part answers keep per-sub-answer citations, since decomposition is where unsupported claims slip in |
| `tutor` output style (opt-in), questions-first offer in ingest, `teach-back` skill | [Bastani et al., PNAS 2025](https://ideas.repec.org/a/nas/journl/v122y2025pe2422633122.html): an unrestricted GPT-4 tutor improved practice scores but hurt later unassisted performance; a hint-based tutor largely removed the harm | Style is never forced (`force-for-plugin` not used) and skips quizzing for vault operations. Questions-first is offered once and skippable (capture friction). Reader questions are written without quote marks so `verify_ingest` does not flag them (tested). `teach-back` writes nothing; `notes/` stays the user's |

Naming: the report called the Feynman skill `/explain`; it ships as `teach-back` so that
"explain X to me" requests do not trigger it.

## Not adopted (and why)

| Idea | Reason |
|---|---|
| Path-scoped `.claude/rules/` for the vault schema | Small gain at ~140 lines; `.claude/` is a protected path, so init and existing vaults would need extra writes. Revisit if the schema passes 200 lines |
| `if` filter on the validator hook (e.g. `Edit(wiki/**)`) | `if` patterns resolve against the working directory; a session whose cwd is not the vault would silently skip validation. Docs call the filter best-effort. Saving ~0.2 s per edit is not worth it |
| Three-label claim classes (extracted / inferred / ambiguous) | The schema already has (provisional) / (disputed) / (unsupported), and "no marker = accepted"; a second scheme would duplicate it and break existing pages and the lint judgment rules |
| `.drafts/` review queue | Review already happens in-session plus git; draft pages would pollute Obsidian's graph and the duplicate-basename check. Revisit with scheduled tasks |
| Per-write auto-commit, writer lock | Subagents are read-only by rule; auto-commits risk half-written Obsidian notes |
| Lint as a fork skill (`context: fork`) | Lint's report → approve → fix flow needs the conversation |
| `prompt`-type Stop hook, `asyncRewake` link checker | A model call on every stop (usage, latency); lint + validator already cover links |
| Scheduled / headless consolidation | Shares the subscription limit; decide together with a `/weekly` skill (Phase 2c) |
| Session-log ingest, Telegram/Whisper capture, IDE items, GraphRAG-style stacks | Privacy (session logs hold file contents), Phase 4–5 scope, or too heavy for personal scale |

Auto mode is the default starting mode since v2.1.283. It does not weaken the kit: deny rules
block in every mode, explicit `ask` rules still prompt, and the guard hook was live-tested in an
auto-mode session.

## Input for Phase 3 (search & eval)

Planned already: BM25 + Turkish stemming, `queries.json`, recall/MRR. Add:

1. **Question types in `queries.json`** — lookup / synthesis / multi-part — and record tokens
   read per answer, so the query routing above can be measured, not assumed.
2. **Claim-level faithfulness** — split an answer into claims; for each ask one binary question:
   does the cited page/source support it? Avoid holistic 1–10 "groundedness" scores; Cochran
   reports low agreement for judged scores, and even the claim-level scorer agreed with human
   annotators on only 65–69% of 100 claims after a fix. Calibrate any LLM judge on a small
   human-labelled set before trusting it.
3. **Embedding bake-off on the user's own TR/EN vault** — candidates named by the report:
   multilingual-e5-large, Qwen3-Embedding-0.6B, bge-m3; reranker bge-reranker-v2-m3.
   Unverified: Turkish retrieval scores for bge-m3 / Qwen3, licences. Measure, do not assume.
4. **Cheap structure signals** — Personalized PageRank over wikilinks (no model call);
   section-level chunks with a heading-path prefix for raw sources.

## Still unverified

- The billing pause rests on secondary reports; check Anthropic's help page and `/usage`.
- Whether HTML comments are stripped from `@imported` files (docs state it for CLAUDE.md only),
  so the template comments in hot.md and CRITICAL_FACTS.md may still cost tokens.
- The "17% worse" figure often quoted from Bastani et al. is from the SSRN working paper; the
  PNAS abstract states the harm qualitatively.

## In-session check (2026-10-31, by hand)

- Query routing: "precision nedir" → Lookup, quick budget, one page read (7.3 KiB), stopped.
  A two-part question → Multi-part, split in two; the existing synthesis read first; each
  sentence cited; general knowledge labelled "(not in the vault)"; the gap logged.
- `/output-style` lists the plugin style as `your-2ndbrain:tutor` (namespaced by plugin name).
- `teach-back` asked for the user's explanation first and wrote nothing.
