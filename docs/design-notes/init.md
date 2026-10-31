# Design notes — init (tests, 2026-10-30)

Skill: `skills/init/SKILL.md`, script `skills/init/scripts/init_vault.py`. Decisions before
writing it: a stdlib script does the copying (deterministic, no tokens per file); a non-empty
target gets a dry run and explicit approval, then only missing files are added; the identity
card is filled from one question round; git is never run unless the user asks (no push, no remote).

## Script tests (scratch folders)

| # | Case | Expected | Result |
|---|---|---|---|
| 1 | empty folder, `--dry-run` | plan printed, nothing written | 10 dirs + 21 files listed; folder still empty |
| 2 | empty folder | vault created | 10 dirs, 21 files; no CR, no BOM, no manifest placeholder left |
| 3 | rerun on the same folder | nothing changed | 11 SKIP, 0 written |
| 4 | folder with `.obsidian/`, own `CLAUDE.md`, a note | existing files untouched | CLAUDE.md SKIP; note and `.obsidian/` unchanged |
| 5 | target inside the kit | refused | ERROR, exit 2 |
| 6 | bad `--date` | refused, nothing written | ERROR, exit 2; folder not created |
| 7 | missing target, `--dry-run` | nothing created | TARGET says "does not exist, will be created"; folder not created |
| 8 | existing vault after the daily template was added | repair adds only the new file | 1 written, 11 SKIP |

## End-to-end skill test

`/bighead:init <scratchpad>/vault-test`: language question → dry run → approval →
create → identity card (fictional data) → Obsidian steps → close. No git run. Works.

## Findings

- **Wrapped path argument.** The pasted path arrived split by a line break plus indentation.
  Step 1 now joins the pieces and shows the joined path for confirmation.
- **Daily-notes template was missing.** `obsidian-setup.md` asked for a template file the kit did
  not ship. Added `templates/vault/notes/templates/daily.md` to the manifest; Obsidian's
  `{{date:YYYY-MM-DD}}` survives rendering because only manifest placeholders are replaced.
- **TARGET line** said "empty" for a folder that did not exist; it now says it will be created.
- **Two question rounds** (languages, then approval) for an empty target. Kept: the approval
  shows the dry-run result, which the first round cannot.
- Shell `rm` is denied in this environment, so scratch folders stay behind after tests.
