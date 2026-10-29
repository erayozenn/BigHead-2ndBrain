---
name: save
description: Save a good answer, comparison or discussion from this session into the vault's wiki as a synthesis page (or extend an existing one) — with citations and uncertainty markers kept, sources collected, links from related pages, and index, log and hot cache updated. Use when the user asks to save, keep, file or "wiki" an answer, or accepts a save offer from the query skill.
argument-hint: "[title or what to save]"
---

# Save an answer as a synthesis

Arguments: `$ARGUMENTS` — optional title, or a pointer to what to save ("the RAG comparison").
Default: the last answer in this session that came from the vault (usually a query answer).

The vault's `CLAUDE.md` is the authority for rules (frontmatter, summary callout, freshness,
citation, markers, autonomy). This skill is the procedure; where they differ, the vault's
CLAUDE.md wins. Talk to the user in the vault's chat language; write the page in the wiki
language.

**Preconditions.** The current directory is a vault: `CLAUDE.md` and `index.md` exist. If not,
stop and say so. One synthesis per run.

## 1. Pick the content

- No argument: the last vault-based answer in this session. If the session has several
  candidates, or the last answer is not vault-based, list them in one line each and ask.
- Content can be a query answer, a comparison, or a discussion worth keeping (e.g. a design
  argument). Not: raw source summaries (that is ingest), the user's own notes (author: me),
  or chat that has no claims.

## 2. New page, extension, or nothing

Read `index.md` (Syntheses section and related concepts). First sort the answer's claims by
support: cited wiki pages, cited raw files, (unsupported) / "(not in the vault)".
- **Core is unsupported** (the main answer is general knowledge, the vault only has passing
  mentions) → no synthesis: it would put an unsourced core into the wiki and be rewritten once
  a real source is ingested. Instead add the vault-backed parts that carry lasting value to the
  related concept page(s), cited, and propose ingesting a source for the core.
- **Restates an existing synthesis** → say so, do not save. Mention any small new detail and
  offer to add just that to the existing page.
- **Overlaps an existing synthesis but adds something** (new axis, new evidence, an answered open
  question) → extend that page.
- **New question** → new page `wiki/syntheses/<slug>.md`. Slug: English, ASCII, lowercase
  kebab-case, named after the question (e.g. `metric-choice-by-error-cost`). Check that the
  basename is unique vault-wide (Glob `**/<slug>.md`).

## 3. Plan (wait for approval)

State in a few lines: new page or which page is extended, title, the 1–3 related pages that will
get a link, and the system files (index, log, hot). Wait for the user's approval. Then write.

## 4. Write the page

Frontmatter per CLAUDE.md with `type: synthesis`, `status: draft`, `author: claude`; then the
"For future agent" summary callout. Body:

- **Question.** One sentence, as the user meant it.
- **Short answer.** 2–4 sentences, markers included.
- **Body.** The answer's support, reorganised for reading later (sections, a table for
  comparisons). Not a transcript of the chat.
- **Open questions.** Gaps the answer exposed.

Rules while converting chat into a page:
- **Citations:** keep every `[[link]]`. Cite the wiki pages the answer used; raw files as
  `[[raw/<full path>]]` with page numbers where the answer had them.
- **`sources:` frontmatter:** the union of the `sources:` of every cited wiki page, plus raw files
  cited directly. Read only the frontmatter heads of those pages for this.
- **Markers:** carry (provisional), (disputed), (unsupported) over unchanged; never upgrade one.
- **General knowledge** that the answer labelled "(not in the vault)" stays, marked
  **(unsupported)**, and goes into "Open questions" as something a source should confirm.
- **Freshness:** every changing fact dated ("as of YYYY-MM", or the date of the cited source).
- **Interpretation** (your own reasoning in the answer) is labelled "(interpretation)".
- **Quotes:** only text copied from a source read in this session; otherwise paraphrase
  without quote marks.
- Chat-language search terms go into `aliases`.

Extending an existing synthesis — or, for small additions, a concept page (one bullet or
sentence where the topic is discussed, cited): add a section or rows, update `updated:`, keep its structure,
do not rewrite parts that did not change. If the new content contradicts it, keep both sides,
cite both, mark (disputed).

## 5. Link it

Add a link to the synthesis from the 1–3 most related concept pages (their "Related" section,
or one sentence where the topic is discussed). Read budget: at most 5 existing pages in total,
including any page being extended.

## 6. System files

- `index.md`: one line under Syntheses — `- [[slug]] — <summary from the callout>`; for an
  extension, update that line if its summary changed.
- `log.md`: `## [YYYY-MM-DD] save | <title> → [[slug]] (new | extended)`; when no synthesis was
  written, say why and which page got the addition.
- `hot.md`: "Recent changes" (keep ~5); "Key facts" only if the synthesis settles something
  lasting. Keep hot.md ≤ 500 words.

## 7. Verify and report

Run the ingest skill's verifier (`../ingest/scripts/` next to this skill's directory):

```
python <ingest scripts>/verify_ingest.py --vault . --pages <synthesis> <every page you changed>
```

Fix every ERROR; check each quote WARN (paraphrase in quote marks → remove the marks). Report:
created/changed files, verification result, open questions. Propose a commit in the vault repo
(`save: <title> → <slug>`); do not commit without approval.
