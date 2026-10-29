# Design notes — ingest (from manual test ingests, 2026-10-29)

Input for the Phase 2a `ingest` skill. Written from three manual test ingests (a web idea file,
an arXiv paper, a lecture slide deck) before any skill code existed.

## Capturing sources

- **Web text:** download the original, not a secondary summary. If an API fails (GitHub API
  returned 502), fall back to the raw URL (`gist.githubusercontent.com/<user>/<id>/raw`).
- **Provenance header:** prepend frontmatter to captured markdown in `raw/`:
  `source_url`, `author`, `retrieved`, `captured_by`. Body stays byte-identical (LF normalized).
- **Download to scratch first**, inspect (e.g. `%PDF-` magic bytes), then copy into `raw/` —
  never execute or import anything from the download directory.
- **Binary files bypass the `raw/**` ask rule** when copied by shell. Until the Phase 2b guard hook
  exists, the skill must ask explicitly before any shell copy into `raw/`.
- Course material is usually copyrighted: fine in a private vault, never in demo vaults or this repo.

## Reading PDFs

Findings on Claude Code (Windows, 2026-10-29):

- `Read` with `pages=` routes through poppler's `pdftoppm` and **fails hard** if poppler is missing.
- `Read` without `pages=` works natively for PDFs of **≤ 10 pages**: each page arrives as text +
  rendered image. Highest fidelity, no extra tools.
- So: split long PDFs into ≤ 10-page chunks with **pypdf** (pure Python, BSD, `pip install pypdf`),
  then read chunks natively. pypdf also extracts text. poppler (`pdftotext`) is optional, better text.

### Measured cost (10 slides of a lecture deck, `/context` before/after, noise subtracted)

| Mode | Tokens / page | Notes |
|---|---|---|
| Text only (pypdf) | ~50 (slides) · ~900 (dense paper page) | cheap; loses tables/figures |
| Native PDF (text + image) | ~1,650 | ~30× text on slides; nothing lost |

On the test deck, one page held its entire content in a table image; text extraction returned
only its title.

### Read modes for the skill

- **text** — text only. Papers without important figures.
- **smart (default)** — extract text for all pages; read natively only pages with < 50 chars of
  text, or whose text mentions a figure/table, or whose text looks garbled.
  Estimate for a ~60-page deck: ~35k tokens vs ~100k (full) vs ~3k (text, lossy).
- **full** — every page natively. Visual-heavy material the user marks as important.

Images stay in context for the rest of the session: after a heavy ingest, suggest `/compact`
or a fresh session (hot.md carries the state).

## Verification (run before reporting an ingest)

- Every quoted span on new pages appears verbatim in the source text (caught a paraphrase in quotes).
- Every wikilink resolves; no ambiguous basenames (caught a literal example link in a template).
- Source pages are named `src-<slug>` so they never collide with the raw file's basename.
- hot.md word count ≤ 500.

## Second test ingest (arXiv paper, 19 pages, 2026-10-29)

- **Text mode + targeted native read worked.** pypdf text (~71 KB) for all pages; references
  (pp. 10–16) skimmed only. Native read of 3 pages (6–8) to check tables.
- **Tables break in text mode even on clean papers:** pypdf merged two table rows into one line
  and dropped the structure of shared (multirow) cells. Rule for the skill: pages whose text has
  "Table N:" get a native read when the numbers will be cited.
- **The source can contradict itself.** Body text said "17%", the table said 11.7% / 17.7%.
  The skill should cross-check numbers quoted in prose against tables and mark (disputed).
- **Quote check needs normalization:** ligatures (ﬁ, ﬂ) and curly quotes in PDF text make a
  naive verbatim check fail. Normalize both sides before matching.
- **"Risky claims" rule vs papers:** every benchmark number is single-source. Section-level
  "(provisional)" note was used instead of marking each number. Revisit in the skill spec.
- Read budget: 2 existing pages read (concept + grep on source page).

## Third test ingest (lecture slide deck, 2026-10-29)

- **Smart mode worked, but the < 50-chars rule over-selects.** 17 slides had < 50 chars:
  7 were section-divider slides (title only) and 4 were tool logos/screenshots. Only 8 slides
  were read natively (~13k tokens est.) vs ~28k for all 17. Heuristic for the skill: skip a
  short page whose text equals the title of the next slide (section divider); let the user skip
  pages that are only tool/brand images.
- **Also select slides whose text ends with ":"** — 3 slides ended in "categories:" / "overfitting:"
  / "the task:". Native read showed the follow-up was missing entirely (lost slide animation);
  for one (overfitting) the figure was on the next slide. Record such gaps as "Open questions"
  instead of guessing the content.
- **Extract chosen pages into one ≤ 10-page PDF** with pypdf, then one native Read. Cheaper
  than chunking the whole deck.
- **Course slides contain contestable claims** (model selection on the test set; a cost
  judgement on Type I vs II errors). With no second source in the vault, the pattern used:
  slide's claim cited, other side stated with "(unsupported in this vault)", whole point
  "(disputed)". The user approved this; the skill should offer it as the default.
- **Gate outcome for course material:** source page + concept pages that later lectures will
  extend (`concept-a`, `concept-b`), not one page per lecture topic.
- Read budget: 2 existing pages (heads only) + index/log.

## Cost of the first ingest (web idea file, ~12 KB)

Source read ~3k tokens; no existing pages read (empty wiki). Far under budget.

## How these notes became the skill (Phase 2a)

Implemented in `skills/ingest/` (SKILL.md + `scripts/pdf_pages.py` + `scripts/verify_ingest.py`).

- pypdf became an **optional** dependency (kit rule 4 exception): without it, PDFs ≤ 10 pages
  are read natively; longer ones ask the user to install it.
- `pdf_pages.py candidates` implements smart mode: short text (minus section dividers detected as
  "text equals next page's first line"), table/figure mentions, text ending in ":", garbled text.
  On the test deck it selected 14 pages and skipped 5 dividers; dropping 4 tool-logo
  slides leaves 10 = one native read. Two dividers were not detected (next slide's title differs).
- `verify_ingest.py` checks frontmatter keys, summary callout, BOM/CRLF, link resolution and
  ambiguity, duplicate basenames, hot.md size, and quotes after normalization (NFKC for
  ligatures, one quote-mark kind for nested quotes, dashes, hyphenated line breaks, case).
  Quote misses are WARN, not ERROR: a quote may come from another source.
- First run on the test vault: 0 errors; 3 quote warnings, all in a synthesis page where
  paraphrases were set in quote marks — the check catches exactly that.
- "Risky claims" vs papers resolved as: section-level "(provisional)" for single-paper numbers.

## End-to-end test 1: skill on a course slide PDF (2026-10-29)

`/your-2ndbrain:ingest file:///.../deck.pdf` (smart mode). Worked end to end: copy-into-raw
approval, text extraction, candidates, one 7-page native extract, discussion, gate, write,
verify. Cost ~20k tokens (text ~4k, native ~11.5k, 3 existing pages ~5k).

- **`file:///` URL with percent-encoding** (e.g. `%C3%A9`) was passed as the argument; the
  model decoded it by hand. The skill (or `pdf_pages.py`) should accept and decode `file://` URLs.
- **`candidates` missed table slides without the word "table".** Two slides were pure frequency
  tables (many short numeric tokens, lines like `buy 1 1 can 0 1 2 3`) and were not selected;
  the model added them from reading the text. Heuristic: high ratio of numeric/fraction tokens
  per line → `table-like`.
- **`candidates` missed a screenshot slide ending in "?".** One slide = "The tool produced the following
  result: … What does this tell us?" — the key result was an image. Heuristic: a line ending in
  ":" anywhere on the page (not only at the end) followed by little text.
- **Short GUI-step slides (a run of 12) are mostly selected or noise.** 5 of 12 candidates were tool
  screenshots ("Click Apply"). Heuristic: a run of ≥ 3 consecutive short pages with the same title
  → collapse into one "screenshot run" candidate the user can drop at once.
- **Arithmetic errors on slides are only found by recomputing.** One slide printed a product
  an order of magnitude off; another slide had a count that did not match its own dataset. Add to the
  skill's extract step: recompute every worked example's arithmetic and cross-check tables
  against the data they are derived from.
- **`verify_ingest.py` warns on quotes in system files.** hot.md mentions a paper title in quote
  marks (a paper title) → WARN. Skip the quote check for system files (hot, index, log),
  or only check quotes in pages that cite the given source.
- **Quote check needs every cited source's text.** Extended pages quoting an earlier deck warned until
  that deck's text was also passed. The script could auto-extract text for each `raw/*.pdf` listed
  in a page's `sources:` frontmatter (when pypdf is available).
- **Gate outcome:** source page + 2 new concept pages (`concept-f`, `concept-g`) +
  2 extended concept pages. User approved; matches the "pages later sources extend" rule.

## End-to-end test 2: skill on a web article (2026-10-29)

`/your-2ndbrain:ingest <engineering blog post URL>`. Worked
end to end: scratchpad download, conversion, raw/web/ approval, discussion, gate, write, verify
(0 errors after removing one paraphrase from quote marks). Cost ~25k tokens (article ~4k read,
~4k written back into raw/ via Write, 3 existing pages ~5k, new pages ~8k).

- **HTML is not covered.** Step 2.4 says "keep the body byte-identical", which only fits
  markdown/text downloads. The page came as 220 KB of Next.js HTML; no `html2text`/`markdownify`
  installed, so the model wrote a throwaway stdlib `html.parser` converter (keep `<article>`, drop
  nav/aside/header/button/svg, map h1–h3/p/li/strong/em/a/img/figcaption). Add `html_to_md.py`
  (stdlib only) to `scripts/` and a `format:` provenance key that records the conversion.
- **Writing the capture re-types the whole body.** Rule "write vault files only with Write" means
  the model re-emits every byte of the converted article (~4k tokens) and then diffs it against the
  scratchpad copy (identical here, even zero-width spaces). Either accept that cost, or allow one
  approved shell copy for captures of model-converted text, as already done for binary files.
- **Windows encoding trap.** `python -I` ignores `PYTHONIOENCODING`, so printing non-cp1254
  characters crashed. Use `python -I -X utf8`, or write output with `encoding="utf-8"`. Put this in
  the skill's Python note.
- **Metadata worth capturing:** `article:published_time` and JSON-LD `dateModified` were both
  present; the page had been revised ~2 years after publication (new model names, a "landscape has
  changed" banner). The converter should pull both dates into provenance automatically.
- **No embedded instructions or sensitive data found**; source-as-data rule was not exercised.
- **Gate outcome:** source page + 2 new concept pages (`concept-c`,
  `concept-d`) + short links from 2 existing pages. User picked all four focus
  areas (pattern choice, vault mapping, ACI, practical angle).

## End-to-end test 3: arXiv paper in text mode (2026-10-29)

`/your-2ndbrain:ingest https://arxiv.org/pdf/<id> text` (an arXiv paper, 18 pages).
Worked end to end: download, `%PDF-` check, binary copy into raw/web/ with explicit approval,
`text` extraction, discussion, gate, one 2-page native extract (p. 5, 18) for table numbers, write,
verify. Cost ~40k tokens (text ~28k incl. references, native 2 pages ~3.5k, 1 existing page ~2.5k,
writing ~6k).

- **Read cap hit below the 2,000-line rule.** The text file was 1,557 lines but ~26k tokens, so
  Read truncated at 25k and needed a second call. Size the "read in parts" rule by tokens
  (chars / 4 > ~20k), not by lines; `pdf_pages.py text` could print an estimated token count.
- **References are ~30% of a paper's text.** Pages 11–14 were bibliography. Add
  `pdf_pages.py text --skip-references` (cut from a line equal to "References" up to the first
  appendix heading) — saves ~7k tokens here.
- **Text-mode tables were exact.** Tables 1, 5–7 (single-line rows, no merged cells) matched the
  native read cell for cell. The "native read for cited tables" rule still caught one useful fact:
  Figure 5 visibly lacks a 4K GPT-3.5 series at 30 documents, confirming a prose/table naming
  mismatch. Keep the rule, but say it is a check, not a fix.
- **Prose vs table cross-check worked as designed.** "Drop by more than 20%" = 22.0 / 22.9 points;
  "worst case lower than closed-book in 20- and 30-document settings" mixes the 4K and 16K models.
  Both recorded in the source page, not marked (disputed) because the conclusion holds.
- **Figure-only numbers.** Several numbers (KV worst case 45.6%, Flan-UL2 1.9 points) exist only in
  prose describing figures not read natively. The source page labels them "prose only". Suggest
  this label in the skill's extract step.
- **verify_ingest.py quote check handled line-wrapped and hyphenated PDF text** (quotes across
  line breaks passed). It flagged 2 of my own paraphrases in quote marks — the step works.
- **Pre-existing warnings resurface.** Editing `synthesis-a` re-surfaced its 3 old paraphrase
  warnings. Fine, but the report should separate "new in this ingest" from "already there"
  (e.g. compare against `git stash`/HEAD version).
- **Gate outcome:** source page + 1 new concept (`concept-e`) + 2 extended pages
  (RAG failure modes, wiki-vs-RAG evidence section and eval design). User approved.

## End-to-end test 4: short, low-value web page (2026-10-29/30)

Source: a public ML course web page on classification metrics
(~1,450 words, devsite HTML, 155 KB). Chosen because it mostly duplicates `concept-b`.

- **Gate worked as intended.** Proposed register line + extend the existing concept page; user
  approved. The outcome "no page, but the source still fixes a citation" (precision definition was
  marked unsupported) is a real, useful path — name it in step 6 as a third option:
  *register line + cite `[[raw/...]]` from existing pages*. Today the skill implies register = no
  further writes.
- **HTML converter missing, second time.** The test-2 converter was not kept, so the model wrote
  a new stdlib `html.parser` script (~120 lines). Site-specific body selector this time
  (`div.devsite-article-body`, not `<article>`). Strong case for `scripts/html_to_md.py` with a
  selector list (`article`, `main`, `div.devsite-article-body`, `--selector` override).
  **Done 2026-10-30:** `scripts/html_to_md.py` (stdlib tree builder + renderer). Regression on
  both test pages: The test-2 page output matches the test-2 capture word for word except two places
  where the old converter misplaced bold/link markers; test-4 table and quiz now render properly.
- **Converter limits:** a table with multi-paragraph cells and the interactive quiz block came out
  flattened (text complete, layout lost). Recorded in the capture's `format:` key. Acceptable for
  a register-only source; a real converter should emit cell `<br>` and block-level quiz items.
- **Capture still re-types the body** (~2k tokens here); diff against the scratchpad copy was
  identical. Same trade-off as test 2.
- **Date rollover mid-ingest.** Downloaded on 10-29, written on 10-30. Skill should say:
  `retrieved` = download date; `updated`/log/register = write date.
- **Quote check:** 0 warnings; existing short quotes on the page (< 4 words) are below
  `MIN_QUOTE_WORDS`, so passing only the new source text was enough. Cost: discussion + one
  existing page read, ~10k tokens total — the cheap path is genuinely cheap.

## Cleanup after tests 1–4 (2026-10-30)

Done, with regression runs on the 4 test PDFs and 2 HTML pages:
- `pdf_pages.py`: `file://` URLs (percent-decoded); `text` prints `est_tokens`;
  `text --skip-references` (paper 1: 4 reference pages dropped, 10.6k chars; paper 2: 8 pages, 23k chars;
  both stop at the first appendix heading). `candidates`: `table-like` (≥ 3 mostly-numeric lines)
  caught the frequency tables of deck B and its probability tables; `colon-then-little-text`
  caught the screenshot slide; `screenshot_runs` groups the GUI-step run (5 selected pages) into one item.
  Trade-off: more pages selected (deck B: 12 → 20), offset by dropping runs at once.
- `html_to_md.py`: `meta` from `<title>`, `<meta>`, JSON-LD and a visible "Last updated" date;
  Test-2 page dates match the test-2 capture.
- `verify_ingest.py`: reads each page's `sources:` raw files (md/txt; PDFs with pypdf), skips
  system files, marks warnings already present at git HEAD "(pre-existing)". Tested on a
  throwaway git vault (real md + PDF quotes found, old/new fake quotes told apart, hot.md skipped).
- SKILL.md: token-based read-in-parts, recompute worked examples, "prose only" label, native
  table read = check, new candidates/runs, verify behaviour.
- Windows encoding: no change needed; the scripts already reconfigure stdout to UTF-8 and
  `html_to_md.py` prints ASCII JSON (the test-2 crash came from a throwaway script).

Decided to keep: capture body re-typed via Write (vault rule 8); cost accepted.

Still open: `candidates` misses dividers whose next slide has a different title (Phase 2a note).
