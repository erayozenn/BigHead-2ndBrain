---
name: handoff
description: End-of-session handoff for the vault — rewrite hot.md "Now" so the next session can continue cold, keep hot.md within its word limit, flag uncommitted work, propose rules learned from the user's corrections, and offer the monthly log archive. Use when the user says they are done, wraps up, asks for a handoff or summary of the session, or before /compact or a fresh session.
argument-hint: "[note for the next session]"
---

# Session handoff

Arguments: `$ARGUMENTS` — optional note from the user to carry into "Now" (e.g. what to do first
next time).

The vault's `CLAUDE.md` is the authority for rules (hot.md upkeep, autonomy, git). This skill
is the procedure; where they differ, the vault's CLAUDE.md wins. Talk to the user in the vault's
chat language; write hot.md in the wiki language.

**Preconditions.** The current directory is a vault: `CLAUDE.md` and `hot.md` exist. If not,
stop and say so.

Free to write: `hot.md`. Ask first: `Threads.md`, `rules.md`, `archive/`, any commit.

## 1. Gather the session

- `log.md`: entries dated today (and since the last handoff, if the session crossed midnight).
- Vault git: `git log --since=<session start or today 00:00> --oneline` and `git status --short`.
- Other repos the session worked in (added working directories, paths named in hot.md "Key
  facts"): their `git status --short` and unpushed commits (`git status -sb`). State which repo
  each line belongs to.
- The conversation: decisions made, work left half-done, questions the user still has to
  answer, things promised for "later".

## 2. Rewrite "Now"

Replace the whole "Now" section (do not append). Keep it to what a cold session needs:
- **Done this session** — 1–3 lines, pointing to log.md / commits for detail, not repeating them.
- **State** — anything unfinished or uncommitted, with file paths.
- **NEXT** — ordered, 1–3 concrete steps, each startable without re-reading the chat
  (command, file, or decision to make).
- **Open questions / blockers** — what waits on the user or on a source; keep items that are
  still open from the previous "Now".
- The user's note from the arguments, if given.

Dates: absolute (`2026-10-30`), never "today" or "yesterday".

Keep "Recent changes" (≈ 5 newest) and "Key facts" consistent with what happened: add a key
fact only if the session settled something lasting; correct any key fact the session proved
wrong.

## 3. Size

hot.md ≤ 500 words (count with `wc -w hot.md`). Over the limit, in order:
1. Drop the oldest "Recent changes" lines (they live in log.md).
2. Shorten "Now" (pointers instead of explanations).
3. Move long-lived items from "Now" or "Active threads" to `Threads.md` — ask first, then add
   them as `- [ ] <topic> — <context> (opened YYYY-MM-DD)`.

## 4. Uncommitted and unpushed work

List uncommitted changes per repo. Propose commits with messages in the repo's style
(vault: `chore: hot cache handoff` plus any pending work units). Never commit or push without
approval. Ignore files the vault never commits (e.g. `.obsidian/` state the user manages).

"Now" was written before these commits, so it still describes them as pending. When the user
approves commits: run them, then update "Now" to the post-commit state ("State": committed and
pushed or not; drop NEXT steps that were only "commit X"), and include hot.md in the last vault
commit — or commit it right after — so the committed hot.md is never stale.

## 5. Rules learned

Scan the session for corrections by the user and for rule breaks you caught yourself. For each
that would change future behaviour, draft one line in the `rules.md` format
(`- YYYY-MM-DD: <rule> — why: <reason>`). Propose at most 3; skip anything already in CLAUDE.md
or rules.md. Write only the ones the user approves.

## 6. Month change

If `log.md` contains entries from a previous month, offer the archive step from CLAUDE.md:
copy those entries to `archive/YYYY-MM/log.md`, then remove them from log.md. Ask first.

## 7. Close

Report in a few lines: what "Now" says next, hot.md word count, pending commits, approved
rules. Suggest `/compact` or a fresh session — hot.md carries the state.
