# Design notes — install test (2026-10-30)

First real install of the plugin from the GitHub marketplace (private repo, before public
release). Environment: Windows 11, Git Bash, Python 3.14 (`python` and `py`, no `python3`),
Claude Code 2.1.312. The install ran with an isolated `CLAUDE_CONFIG_DIR` so the developer's own
setup stayed untouched; all functional checks ran from the installed cache copy, not the repo.

| # | Check | Expected | Result |
|---|---|---|---|
| 1 | `claude plugin validate .` | pass | pass; warnings: no marketplace description (fixed), root `CLAUDE.md` not loaded (intended: kit dev rules), no icon (optional) |
| 2 | `claude plugin marketplace add <owner>/<repo>` | clone + register | cloned via HTTPS with the user's git credentials; registered in user settings |
| 3 | `claude plugin install your-2ndbrain@your-2ndbrain`, `list`, `details` | enabled | enabled, scope user; 6 skills, 2 hooks; ~600 tokens always-on |
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

## Not covered

- macOS and Linux (`python3` branch, path handling).
- In-session flows: `/plugin` panel, `/your-2ndbrain:init` dialogue, a hook firing inside a
  session on a freshly installed copy. To be checked by hand before the public release.
