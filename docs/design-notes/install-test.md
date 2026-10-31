# Design notes — install test (2026-10-30)

First real install of the plugin from the GitHub marketplace (private repo, before public
release). Environment: Windows 11, Git Bash, Python 3.14 (`python` and `py`, no `python3`),
Claude Code 2.1.312. The install ran with an isolated `CLAUDE_CONFIG_DIR` so the developer's own
setup stayed untouched; all functional checks ran from the installed cache copy, not the repo.

| # | Check | Expected | Result |
|---|---|---|---|
| 1 | `claude plugin validate .` | pass | pass; warnings: no marketplace description (fixed), root `CLAUDE.md` not loaded (intended: kit dev rules), no icon (optional) |
| 2 | `claude plugin marketplace add <owner>/<repo>` | clone + register | cloned via HTTPS with the user's git credentials; registered in user settings |
| 3 | `claude plugin install bighead@bighead`, `list`, `details` | enabled | enabled, scope user; 6 skills, 2 hooks; ~600 tokens always-on |
| 4 | Shipped files | no personal data, no build output | clean; no home paths, no `__pycache__` |
| 5 | Unit tests from the installed copy | pass | hooks, lib, lint: all pass |
| 6 | `init_vault.py` dry-run / real / re-run | nothing written / full vault / nothing overwritten | 0 written / 22 files + 10 dirs / 12 files skipped, 10 dirs kept |
| 7 | Fresh vault content | placeholders filled, LF, no BOM, valid JSON | yes; the only `{{…}}` left is Obsidian's own `{{date:…}}` in the daily template |
| 8 | Fresh vault git | `.obsidian/`, `.cache/` ignored; LF | yes |
| 9 | Lint + verify on the fresh vault | clean | one WARN for missing `.cache/raw-text/` (fixed: lint skips `.cache/`) |
| 10 | Hook decisions via the `hooks.json` command, installed copy, fresh vault | 7 guard + 3 validator cases | 10/10 |
| 11 | Interpreter chain | `python3` → `python` → `py -3`; none → warning | `python` and `py -3` branches pass; no Python → warning, exit 1; `python3` branch not testable here |
| 12 | Hook latency | small | ~195 ms per call on Windows, including the interpreter probe |

## Findings

- **In-session `/plugin install` opens a panel** where the user confirms; it does not install
  directly. The shell commands (`claude plugin …`) install directly and are now the primary
  path in the README; the in-session flow is described as the alternative.
- **Fresh vaults have no `.cache/`.** It is derived and created on first PDF cache, so the lint
  Layout check now skips it instead of warning every new user.
- **Test harness pitfalls, not kit bugs.** (a) Shell-quoted Windows paths in a bash loop made the
  guard look inert — a Python harness driving `subprocess` fixed the test. (b) On Windows,
  `bash` on PATH can be WSL's `bash.exe`; Claude Code runs hooks with Git Bash, so a harness
  must call Git Bash explicitly.

## In-session test (2026-10-31, by hand)

Plugin installed at user scope, `/bighead:init` in an empty folder, then a new session in
the new vault. Prompts asked Claude to really call the tool (otherwise the vault's CLAUDE.md
makes it refuse before any hook runs).

| # | Action | Expected | Result |
|---|---|---|---|
| 1 | `/bighead:init` | vault created | created; identity card skipped by the tester |
| 2 | Write `raw/test.md` | guard denies | denied ("New raw files may only be added under raw/web/") |
| 3 | Write `raw/web/deneme.md` | permission prompt, then written | prompted (settings `ask` rule), written |
| 4 | Edit `raw/web/deneme.md` | guard denies | denied |
| 5 | Write `wiki/concepts/test-page.md` without frontmatter | written, validator reports, Claude fixes | "missing frontmatter" reported; Claude added frontmatter + summary in the same turn; second write silent |
| 6 | Edit `notes/benim.md` (`author: me`, frontmatter indented by a terminal copy) | guard denies | denied — guard tolerates leading spaces |
| 7 | `/bighead:lint quick` | runs, reports | 4 correct WARNs (indented user note, leftover test raw file, empty identity card, no git); one wrong claim, see below |

Findings, fixed in the same commit:
- **Lint called a design choice a blind spot.** The script skips `raw/` and `notes/` by design;
  SKILL.md did not say so, so the model reported "the script misses broken frontmatter" and tried
  to read the script (outside the vault, blocked). SKILL.md now states the scope and says not to
  read the script.
- **Hook messages were noisy.** Claude Code prefixes a hook's feedback with its full command, so the
  interpreter loop filled the message. The loop moved to `hooks/run.sh`; the command is now
  `bash "${CLAUDE_PLUGIN_ROOT}/hooks/run.sh" guard|validate`. Same behaviour; 10/10 cases re-run.
- **Init's git offer was easy to miss** (lint flagged "not a git repository"). Init now closes with
  an explicit yes/no question.
- Code blocks copied from the terminal keep their indentation — a user pasting a frontmatter
  snippet gets invalid frontmatter. Same root cause as the daily-note template issue; docs should
  prefer files over pasted snippets.

## Not covered

- macOS and Linux (`python3` branch, path handling).
- In-session `/plugin marketplace add` + install panel from GitHub (the CLI path is covered; the
  developer machine already has a same-named local marketplace).
