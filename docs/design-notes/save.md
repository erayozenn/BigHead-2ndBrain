# Design notes — save (end-to-end tests, 2026-10-30)

Skill: `skills/save/SKILL.md`. Decisions before writing it: general knowledge labelled
"(not in the vault)" stays in the page as (unsupported) and goes to Open questions; any
vault-based answer, comparison or discussion can be saved (default: the last answer); a short
plan is shown and approved before writing.

| # | Content | Expected | Result |
|---|---|---|---|
| 1 | "LLM Wiki vs RAG" query answer | restates `synthesis-a` → no save | refused with a claim-by-claim table; nothing written |
| 2 | "transformer attention" gap answer | unsourced core | no rule covered it; model declined a page and added the one vault-backed point (a remark in one paper) to `concept-e` |
| 3 | "metric choice for a cost-asymmetric classifier" query answer (4 concept pages) | new synthesis | `synthesis-b` + links from 2 concept pages + index/log/hot; verify 0/0 |

## Findings

- **Unsupported core needed its own rule** (test 2). Added to step 2: sort claims by support
  first; if the core is unsupported, no synthesis — add the vault-backed parts to concept pages
  and propose an ingest. Also made concept-page extensions an explicit save outcome.
- **Skill text is loaded at reload time.** The test-3 invocation still showed the pre-fix
  SKILL.md, because `/reload-plugins` had not run after the edit. Worth a line in the kit README:
  after editing a skill, reload.
- **Query → save is cheap when run in one session.** All four source pages and their
  frontmatter were already in context; `sources:` union cost no extra reads. In a fresh session
  save would have to re-read the cited pages' heads (budget 5 covers it).
- **Interpretation labels survived conversion**: two interpretation remarks stayed
  "(interpretation)"; the PR-curve remark became (unsupported) + an open question, as decided.
