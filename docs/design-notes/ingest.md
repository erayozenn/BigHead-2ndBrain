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

## Cost of the first ingest (web idea file, ~12 KB)

Source read ~3k tokens; no existing pages read (empty wiki). Far under budget.
