---
name: weekly
description: Weekly review of the vault — what was ingested, saved, linted and decided this week, which wiki pages changed, threads opened and closed, gaps found, flashcard status, and three suggestions for next week; shown in the chat, then saved to archive/YYYY-MM/weekly-YYYY-Www.md on approval. Use when the user asks for a weekly review, summary or retrospective of the vault.
argument-hint: "[YYYY-Www]"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(git status *)
  - Bash(wc -w *)
  - Bash(python ${CLAUDE_SKILL_DIR}/../review/scripts/*)
  - Bash(python3 ${CLAUDE_SKILL_DIR}/../review/scripts/*)
  - Bash(py -3 ${CLAUDE_SKILL_DIR}/../review/scripts/*)
---

# Weekly review

Arguments: `$ARGUMENTS` — optional ISO week (`2026-W44`). Default: the current ISO week
(Monday–Sunday) if today is Friday–Sunday, otherwise the previous week. Say which week and its
dates before gathering.

The vault's `CLAUDE.md` is the authority for rules (freshness, citation, autonomy). Talk in the
vault's chat language; write the file in the wiki language.

**Preconditions.** The current directory is a vault: `CLAUDE.md`, `log.md` and `hot.md` exist.
If not, stop and say so.

Writes: only `archive/YYYY-MM/weekly-YYYY-Www.md` (ask first — `archive/` is not free to write)
and one `log.md` line. Never edits notes, Threads.md or wiki pages from this skill.

## 1. Gather

- `log.md` entries dated in the week (and `archive/YYYY-MM/log-YYYY-MM.md` if the month changed and the
  entries were archived). Group by operation: ingest, save, query (gaps), lint, decision, setup.
- Vault git: `git log --since=<Monday> --until=<Sunday+1> --name-status --format="%h %ad %s"
  --date=short -- wiki/ cards/` → pages created and changed. `git log` is deliberately not
  pre-approved, because its `--output` option can write a file: expect a permission prompt and
  never pass `--output`. If it is declined, use `log.md` alone and say the page list may be
  incomplete.
- `Threads.md`: items whose "(opened …)" or "(closed …)" date falls in the week.
- hot.md "Now": open questions and blockers.
- Flashcards: `cards.py stats --vault .` (from `${CLAUDE_SKILL_DIR}/../review/scripts/`; first
  working interpreter `python3`, `python`, `py -3`): cards, new, due. Skip if no `cards/`.
- Do not read wiki page bodies; titles and log lines are enough. The summary links pages, it
  does not restate them.

## 2. Draft

Show in the chat first:

1. **Week in one paragraph** — what moved, in plain words.
2. **Added** — sources ingested and pages created, as `[[links]]`; saves.
3. **Changed** — pages extended or fixed (lint), with the reason from the log.
4. **Decisions** — from `decision` log lines.
5. **Gaps and open questions** — query gaps, (unsupported) points raised, questions waiting on
   the user or a lecturer.
6. **Threads** — opened / closed this week.
7. **Learning** — cards added, due now, quiz or teach-back sessions mentioned in the log.
8. **Next week** — exactly 3 suggestions, each concrete (a source to ingest, a gap to close, a
   decision to make), drawn from 5 and hot.md NEXT.

Every fact links the log entry's page or says where it came from; nothing from general
knowledge. Dates absolute.

## 3. Save (on approval)

Ask: save to `archive/YYYY-MM/weekly-YYYY-Www.md`? (YYYY-MM = month of the week's Monday.)
On yes, Write it with frontmatter per the vault schema — `type: note`, `status: stable`,
`created`/`updated` today, `tags: [weekly]`, `aliases: []`, `sources: []`, `author: claude`,
`sensitivity: private` — then the summary callout (`What: weekly review YYYY-Www (<Mon> to
<Sun>). Why kept: progress record. Goes stale: never.`), then the draft. An existing file for that
week is never overwritten: show the difference and ask.

Append to `log.md`: `## [YYYY-MM-DD] save | weekly review YYYY-Www → archive/YYYY-MM/weekly-YYYY-Www.md`.

## 4. Close

Offer to turn suggestion 1 into hot.md "Now" NEXT (hot.md is free to write) and to propose a
commit (`chore: weekly review YYYY-Www`). Never commit without approval.
