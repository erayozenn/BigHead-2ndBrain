---
name: init
description: Create a new vault from the kit's templates — folders, CLAUDE.md schema, hot cache, index, log and settings — in an empty folder or an existing Obsidian vault, without overwriting anything; then fill the identity card and point to the Obsidian setup. Use when the user asks to set up, create, initialize or start a new vault / second brain, or to add the vault structure to an existing folder.
argument-hint: "[target folder]"
allowed-tools:
  - Bash(python ${CLAUDE_SKILL_DIR}/scripts/*)
  - Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)
  - Bash(py -3 ${CLAUDE_SKILL_DIR}/scripts/*)
---

# Create a vault

Arguments: `$ARGUMENTS` — optional target folder. Default: the current directory.

This skill runs before a vault exists, so there is no vault CLAUDE.md to defer to yet; the
templates it copies become that CLAUDE.md. Talk to the user in the language they write in.

**Python.** `init_vault.py` lives in `${CLAUDE_SKILL_DIR}/scripts/` and is standard library only.
Use the first interpreter that works (`python3`, `python`, `py -3`). It reads the kit's
`templates/manifest.json`, never overwrites a file, and writes UTF-8 / LF.

**Never** in this skill: touch `.obsidian/`, delete or move anything, run git (unless the user
asks — step 6), or push.

## 1. Ask

One question round (choice-style where possible):
- **Target folder** — the argument, else the current directory. A pasted path can arrive
  wrapped (a line break plus indentation inside it): join the pieces without the whitespace and
  show the joined path in this question so the user confirms it. If it is the kit itself or
  inside it, the script refuses; ask for another folder.
- **Chat language** — the language Claude talks to the user in (default: the one they write in).
- **Wiki language** — the language of wiki pages (suggest English: most sources are English; the
  chat language still goes into `aliases` for search).

## 2. Dry run

```
python ${CLAUDE_SKILL_DIR}/scripts/init_vault.py --target "<dir>" --chat-language "<lang>" --wiki-language "<lang>" --dry-run
```

Use forward slashes in paths. Show the user a short summary of the output: the TARGET line
(empty / not empty, with its entries), dirs to create, files to write, and every SKIP line.
- Empty target: one confirmation ("create the vault here?").
- Not empty: explain that existing files stay untouched and SKIP files keep their current
  content (a skipped `CLAUDE.md` means the folder already has its own schema — the vault rules
  will not be installed; say so plainly). Existing notes are not given frontmatter or moved.
  Ask for explicit approval.
- Target already looks like a vault (CLAUDE.md + hot.md + index.md exist): init only adds what
  is missing — say so, ask whether that repair is what they want.

## 3. Create

Run the same command without `--dry-run`. Exit code 2 means nothing was written — show the
ERROR line and stop. Otherwise report the SUMMARY line.

## 4. Identity card

Only if `CRITICAL_FACTS.md` was written in step 3 (not SKIP). Ask, in one round, all optional:
name, role / school or work, timezone, 1–3 current goals. Remind: no ID numbers, finance,
health or passwords — this file is loaded every session. Then Read the file and Write it with
the answers in place of the `<...>` placeholders, keeping the `(as of <date>)` on goals
(freshness rule) and adding one to the role line. Leave a placeholder line as is if the user skipped it. Keep it ~120 tokens.

## 5. Obsidian

Read `${CLAUDE_SKILL_DIR}/../../docs/obsidian-setup.md` and give the user its steps (wikilinks,
shortest-path links, `notes/` and `raw/assets` folders, daily notes in `notes/daily` with the
`notes/templates/daily` template that init wrote). They do these inside Obsidian; Claude never creates or edits `.obsidian/`.

## 6. Git (optional, only on request)

Do not run git on your own. In the close, ask it as a choice (see step 7). Only if the user says
yes: check whether
the target is already inside a git repo (`git -C "<dir>" rev-parse --show-toplevel`) — if so,
say which repo and ask before going on; otherwise `git init`, `git add -A`, and commit with
`chore: vault created from your-2ndbrain template`. Never push, never add a remote.

## 7. Close

Report in a few lines:
- what was created (SUMMARY line) and anything skipped;
- the identity card status (filled / placeholders left);
- **next step:** open a new Claude Code session *in the vault folder* — CLAUDE.md, hot.md and
  `.claude/settings.json` load only at session start;
- then the first ingest: `/your-2ndbrain:ingest <path-or-url>`.

Then ask one choice question (not a line buried in the report): **"Put the vault under git
now?"** — yes (recommended: every Claude edit becomes reviewable and reversible; the vault's
rules assume commits; the repo stays local and private) / no, later. On yes, do step 6.
