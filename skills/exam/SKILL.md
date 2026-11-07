---
name: exam
description: Practice exam from the vault — build a mixed set of questions (definitions, calculations from the page's own worked examples, why/when, comparisons) from a source or topic page and its linked concept pages, take the user's answers, grade them with a rubric citing the pages, and list weak topics with follow-ups. Two more modes - "defense" runs a viva on one project from its hub and project pages (why this choice, what was measured, threats to validity, what is next), one question at a time with a follow-up, and lists decisions whose reasons are not on the pages; "interview" asks technical-interview questions in English (concepts, trade-offs, tell me about a project) from wiki pages and project hubs. Writes nothing except a log line. Use when the user wants a mock exam, practice test, exam readiness check, thesis or project defense practice, or interview practice.
argument-hint: "<page> [n] [one-by-one] | <project> defense [n] | <topic> interview [n] [tr]"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(wc -c *)
---

# Practice exam

Arguments: `$ARGUMENTS`. Three modes. The first word `defense` or `interview` picks the mode;
the words before it are the project or topic (it may be several words, or none), the words after
it are the options. Without either word it is exam mode.

| Mode | Arguments | Default / max questions |
|---|---|---|
| Exam | `<page> [n] [one-by-one]` | 6 / 12 |
| Defense | `<project> defense [n]` | 5 / 8 |
| Interview | `<topic> interview [n] [tr]` | 5 / 8 |

The vault's `CLAUDE.md` is the authority for rules (citation, markers). Talk in the vault's chat
language (if it names none, the language the user writes in). This skill **writes nothing except one log line**, in every mode.

**Preconditions.** Use the vault that encloses the current directory: a folder whose `CLAUDE.md`
starts with `# Vault Schema & Rules` and that holds `index.md`. If there is none, use the
configured vault folder `${user_config.vault_path}`; if that is empty, an unreplaced placeholder or
not such a folder, stop and say so (the user can set it in `/config`, under this plugin's options).

**Outside the vault** (the current directory is not inside it): every vault path below, such as
`index.md`, `log.md` or `projects/`, means that path under the vault folder, written as an
absolute path with forward slashes. `hot.md` is not loaded there; read it first. Read the vault's
`CLAUDE.md` before writing the log line. Never copy vault content into the current repo, its
commits, PRs or issues unless the user asks.

## Rules for all modes

- Questions come only from the pages read in scope, never from general knowledge. If the pages are
  thin, say so and lower the count.
- Read budget 48 KiB over the scope pages (`wc -c` first); read the most central pages first and
  say what was left out.
- Write a hidden rubric per question: the 1–3 points a full answer must contain, each with its
  `[[page]]`. Never show it before grading.
- (disputed) claims: skip them or ask for both sides; never grade one side as the only answer.
- No hints during the session; hints come after grading. "-" skips a question; "stop" ends the
  session and grades what was answered.
- Grade strictly against the rubric; accept equivalent wording and notation.
- Points: one per rubric point. A question skipped with "-" scores 0 and stays in the total;
  questions not reached after "stop" leave the total. A follow-up answer can earn the points the
  first answer missed.
- If no session runs (no vault, no pages on the topic), say so, offer a route (ingest,
  research-deep, another topic) and write no log line.

## Exam mode

### 1. Scope
Find the page (index.md, then Grep). Read it and the concept pages it links (one hop). Questions
are in the language the user studies in (ask once if unclear).

### 2. Build the exam
Mix types; each question tests one idea and has a known answer on a page:

| Type | Example shape |
|---|---|
| Definition | "What is X?" / "Define X in one sentence." |
| Calculation | redo a worked example from a page with its own numbers (or a slight variation you can recompute) |
| Why / when | "Why does X fail on Y?", "When would you choose X over Y?" |
| Compare | "Difference between X and Y?" |
| Apply | a short scenario: "Which metric / method here, and why?" |

At least one calculation if the pages contain worked numbers; recompute every expected answer
yourself before asking.

### 3. Sit the exam
- Default: show all questions numbered, with the point value of each; the user answers in one
  message (numbered).
- `one-by-one`: one question per message, feedback after each (as in step 4), then the next.

### 4. Grade
Per question: **full / partial / wrong / skipped**, the points scored, the model answer in
≤ 3 sentences with its `[[page]]`, and for partial/wrong one sentence on what was missing. Then
the closing report (below).

## Defense mode

A viva on one project: the examiner has the project's pages and asks the user to defend it.

### 1. Scope
- Find the hub `projects/<project>/<project>.md` (match the folder name or the hub's `aliases`).
  With no project named, use the hub this session already points to (the plugin's session note
  names one, or the user opened one earlier in this conversation) and say which; otherwise list
  the projects and ask.
- Read the hub, then the pages it links that live in its own folder `projects/<project>/`:
  overview and status pages first, then plans, then history. Pages of other projects and wiki
  pages are out of scope.
- Questions are in the language the user will defend in (ask once if unclear).

### 2. Build the questions
Spread them over these types; each question is about one decision, measurement or step that is
on the pages:

| Type | Example shape | Comes from |
|---|---|---|
| Choice | "Why X? What was the alternative, and why not that?" | Decisions |
| Evidence | "What did you measure, and what does that result prove — and not prove?" | Current state, status, Milestones |
| Validity | "What could make this result wrong or not generalise?" | Lessons, Open items, Risks |
| Next | "What is next, and why that before anything else?" | Next step |

- Prefer the decisions and results the project's goal rests on.
- While reading, list every **gap** in the scope pages: a decision with no written reason, a result
  with no number, a plan with no why. This list goes into the closing report whether or not a
  question reached it.
- You may still ask about a gap. Its rubric is then "not on the pages": never invent the reason or
  the number.
- With fewer questions than types, prefer Choice and Evidence.

### 3. Sit the defense (one question at a time)
For each question:
1. Ask it; wait for the answer.
2. Ask **one follow-up** that pushes on the weakest part of that answer, grounded in the pages:
   the missing alternative, a missing number, a limitation the pages name, or a gap between the
   claim and the evidence. If the answer was full and nothing is left to push, say so and skip it.
3. Grade the answer and follow-up together (step 4), in at most five lines, then go on.

### 4. Grade
Per question: **full / partial / wrong / skipped / not on the pages**, the points, the model
answer in ≤ 3 sentences with its `[[page]]`, and for partial/wrong one sentence on what was
missing. **Not on the pages**: say the pages hold no reason or number for it, do not score it
(it leaves the total), and keep the user's own answer as a candidate addition. A candidate that
claims a result without its numbers or source carries `(unsupported)`. A user claim that
contradicts the pages is a conflict, not a gap: name both sides and never present it as on the
pages.

## Interview mode

Technical-interview practice for job applications.

### 1. Scope
- Find the topic page (index.md, then Grep) and the wiki pages it links (one hop). Then Grep the
  hubs `projects/*/<name>.md` for the topic and its aliases and read at most two matching hubs
  (hub only, not their other pages).
- Language: English by default, or Turkish with `tr`. Questions, follow-ups and model answers use
  it; the closing report is in the vault's chat language.

### 2. Build the questions
| Type | Example shape | Comes from |
|---|---|---|
| Concept | "Explain X to a colleague." / "How does X work?" | wiki pages |
| Trade-off | "When would you pick X over Y? What does it cost?" | wiki pages |
| Project | "Tell me about a project where you used X: the situation, what you did, the result." | hubs |

At least one Project question when a hub matched; none if no hub did (say so). A Project rubric
holds the hub's situation, the user's action or decision and a result, with a number if the hub
has one.

### 3. Sit and grade
As in defense mode: one question at a time, one follow-up, then a short grade. For Project
questions also say which of situation, action and result was missing or had no number. Only the
hub was read, so a user claim the hub lacks is "not checked" (it may be on the project's other
pages), never a gap in the pages.

## Closing report (all modes)

- **Score**: total and percent (not-on-the-pages questions left out, with their count).
- **Weak topics**: the ideas behind the lost points, grouped.
- **Gaps in the pages** (defense mode only): every gap found in step 2, each marked asked or not
  asked, with the user's own answer as a draft line for that page where there is one. Offer to add
  them through a project update, which shows the change for approval before anything is written;
  `projects/` is ask-first in the vault, so this skill never writes them itself, even after a yes.
- **Follow-ups**: for each weak topic, offer one of: cards from a page (review `make`), a
  teach-back on the topic, or re-reading a named section of a page. Start it if the user agrees.

## Log

Append one line to `log.md` (`<n>` = questions asked; add ", stopped" after an early stop):

    ## [YYYY-MM-DD] query | exam: <page> (<n> questions) → <score>%; weak: <topics>
    ## [YYYY-MM-DD] query | exam defense: <project> (<n> questions) → <score>%; gaps: <count>; weak: <topics>
    ## [YYYY-MM-DD] query | exam interview: <topic> (<n> questions) → <score>%; weak: <topics>
