---
name: today
description: Start-of-day brief for the vault — read the hot cache, open threads, recent log lines, today's daily note and due flashcards, then propose a short plan for the day and one recall question. Read-only. Use when the user starts the day or a session and asks what to do today, what is next, what is pending or due.
argument-hint: "[focus for today]"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(git status *)
  - Bash(git log *)
  - Bash(python ${CLAUDE_SKILL_DIR}/../review/scripts/*)
  - Bash(python3 ${CLAUDE_SKILL_DIR}/../review/scripts/*)
  - Bash(py -3 ${CLAUDE_SKILL_DIR}/../review/scripts/*)
---

# Today

Arguments: `$ARGUMENTS` — optional focus the user wants today (e.g. "exam prep", "kit").

The vault's `CLAUDE.md` is the authority for rules. Talk in the vault's chat language. This
skill **writes nothing** — the plan lives in the chat; the user's daily note in `notes/daily/` is
theirs (Claude never edits it).

**Preconditions.** The current directory is a vault: `CLAUDE.md` and `hot.md` exist. If not,
stop and say so.

## 1. Gather (small reads only)

- hot.md (already loaded): "Now" — NEXT steps, open questions, blockers.
- `Threads.md`: the "Open" list only.
- Project hubs: Glob `projects/*/*.md` and keep files whose stem equals their folder name. Grep
  each for `^status:` and, on `status: active` hubs, the first line under `## Next step`.
- `log.md`: entries of the last 2 days (Grep `^## \[` and take the newest).
- `notes/daily/<today>.md` if it exists (Obsidian names it by date): what the user wrote for
  today. Read it; quote nothing private back unless the user asks.
- Vault git: `git status --short` — uncommitted work from the last session.
- Flashcards: `python ${CLAUDE_SKILL_DIR}/../review/scripts/cards.py stats --vault .` (first
  working interpreter: `python3`, `python`, `py -3`). Skip silently if there is no `cards/`.

Do not read wiki pages for this; the brief is about state, not content.

## 2. Brief

Keep it under ~15 lines:
1. **Carry-over** — uncommitted work, half-done items from "Now" (one line each).
2. **Plan for today** — 3–5 items, ordered, each startable now (a command such as
   `/bighead:ingest <path>`, a file, or a decision to make). Put the user's focus (argument or
   daily note) first; then hot.md NEXT; then active projects' next steps not already listed
   (`/bighead:project open <name>`); then due cards (`/bighead:review quiz`, with the count); then
   at most one Thread worth moving.
3. **Waiting on the user** — open questions and decisions from "Now" / Threads, if any.
4. **One recall question** — from the newest log entry with a wiki page (ingest or save): one
   question about that page's main idea, without the answer. If the user answers, check it
   against the page and cite it.

Dates absolute (`2026-10-31`), never "yesterday".

## 3. Close

Ask which item to start with (a choice question). Do not start any of them unasked.
