---
name: teach-back
description: Check the user's understanding by having THEM explain a topic in their own words (Feynman technique) — compare their explanation with the vault's wiki and return gaps, errors and vague spots as questions, without writing anything. Use when the user wants to test themselves, says they will explain or teach a topic back, or shares their own explanation or note for feedback. Not for requests where the user wants Claude to explain something.
argument-hint: "<topic or notes/ file>"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(wc -c *)
---

# Teach-back

Arguments: `$ARGUMENTS` — a topic, or the path of the user's own note under `notes/`.

The vault's `CLAUDE.md` is the authority for rules (citation, markers, autonomy). Talk in the
vault's chat language. This skill **writes nothing**: the explanation is the user's work, and
`notes/` / `author: me` files are never edited (the guard hook also blocks it).

**Preconditions.** The current directory is a vault: `CLAUDE.md` and `index.md` exist. If not,
stop and say so.

## 1. Get the explanation

- A `notes/` path: Read it. That is the explanation.
- A topic: ask the user to explain it in the chat, in their own words, as if to a classmate —
  without looking at the wiki first. Suggest 5–10 sentences. Wait.
- Do not explain the topic yourself before they have tried.

## 2. Find the reference

Read `index.md`, then find the wiki pages for the topic as the query skill does (terms in both
languages, `aliases:`, then body). Budget: 48 KiB over the pages read (`wc -c` first). If the
wiki has no page for the topic, say so: feedback is then "(not in the vault)" general knowledge
only, and suggest a source to ingest.

## 3. Compare

Check the explanation against the pages. Collect at most 5 findings, most important first:

| Kind | Meaning |
|---|---|
| Error | contradicts a wiki claim (cite the page) |
| Gap | a key idea from the pages is missing |
| Vague | a term used without saying what it means, a step skipped, "it just works" |
| Beyond the vault | a claim the wiki does not cover — not wrong, just unchecked |

A claim the wiki marks (disputed) or (provisional) is not an error if the user states one side;
mention the marker instead.

## 4. Feedback

1. One or two sentences on what the explanation gets right (specific, not generic praise).
2. The findings, each phrased as a **question** that leads them to fix it themselves
   ("What happens to training when the learning rate is too large?"), with the page to
   check (`[[page]]`). Do not write the corrected explanation.
3. Ask them to answer or revise. On the second round, confirm what is now right and give the
   direct answer for anything still missing, cited.

## 5. Close

- Offer: if they want to keep the improved version, they write or update their own note in
  `notes/` (Claude does not).
- A gap in the **wiki** itself (topic missing or thin) → suggest an ingest; offer to add it to
  `Threads.md` (ask first — it is not free to write).
- No log line; nothing is written.
