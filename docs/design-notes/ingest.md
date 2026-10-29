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
