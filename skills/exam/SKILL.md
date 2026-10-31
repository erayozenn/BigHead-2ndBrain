---
name: exam
description: Practice exam from the vault — build a mixed set of questions (definitions, calculations from the page's own worked examples, why/when, comparisons) from a source or topic page and its linked concept pages, take the user's answers, grade them with a rubric citing the pages, and list weak topics with follow-ups. Writes nothing except a log line. Use when the user wants a mock exam, practice test or to check exam readiness on a course, lecture or topic.
argument-hint: "<source or topic page> [number of questions] [one-by-one]"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(wc -c *)
---

# Practice exam

Arguments: `$ARGUMENTS` — a page (e.g. a course source page or a concept), optionally the
number of questions (default 6, max 12) and `one-by-one` to get feedback after each answer
instead of all at once.

The vault's `CLAUDE.md` is the authority for rules (citation, markers). Talk in the vault's chat
language; questions in the language the user studies in (ask once if unclear). This skill
**writes nothing except one log line**.

**Preconditions.** The current directory is a vault: `CLAUDE.md` and `index.md` exist. If not,
stop and say so.

## 1. Scope

Find the page (index.md, then Grep). Read it and the concept pages it links (one hop), within
48 KiB (`wc -c` first). Questions come only from these pages — no general knowledge. If the
pages are thin (a few facts), say so and lower the count.

## 2. Build the exam

Mix types; each question tests one idea and has a known answer on a page:

| Type | Example shape |
|---|---|
| Definition | "What is X?" / "Define X in one sentence." |
| Calculation | redo a worked example from a page with its own numbers (or a slight variation you can recompute) |
| Why / when | "Why does X fail on Y?", "When would you choose X over Y?" |
| Compare | "Difference between X and Y?" |
| Apply | a short scenario: "Which metric / method here, and why?" |

- At least one calculation if the pages contain worked numbers; recompute every expected answer
  yourself before asking.
- (disputed) claims: either skip them or ask for both sides explicitly; never grade one side as
  the only right answer.
- Write a hidden rubric per question (the 1–3 points a full answer must contain, with the page).
  Do not show it before grading.

## 3. Sit the exam

- Default: show all questions numbered, with the point value of each; the user answers in one
  message (numbered). Say they can skip a question with "-".
- `one-by-one`: one question per message, feedback after each (as in step 4), then the next.
- No hints during the exam. If asked, say hints are available after grading.

## 4. Grade

Per question: **full / partial / wrong / skipped**, the points scored, the model answer in
≤ 3 sentences with its `[[page]]`, and for partial/wrong one sentence on what was missing.
Be strict and consistent with the rubric; accept equivalent wording and notation.

Then:
- **Score** — total and percent.
- **Weak topics** — ideas behind the lost points, grouped.
- **Follow-ups** — for each weak topic one of: `/bighead:review make <page>` (cards),
  `/bighead:teach-back <topic>`, or re-reading a named section of a page.

## 5. Log

Append to `log.md`:

    ## [YYYY-MM-DD] query | exam: <page> (<n> questions) → <score>%; weak: <topics>
