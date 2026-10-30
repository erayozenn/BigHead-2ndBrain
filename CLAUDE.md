# Your 2ndBrain — Kit Development Rules

This repo is the open-source ENGINE: a Claude Code plugin (skills, hooks) plus vault
templates. It is NOT a vault. Personal vaults are separate, private repos.

## Language
- Talk to the maintainer in Turkish; code, docs, file names and commits in English.
- Turkish is the first supported vault language (README.tr.md mirrors README.md).

## Layout
| Path | Purpose |
|---|---|
| .claude-plugin/plugin.json | Plugin manifest. |
| .claude-plugin/marketplace.json | Single-plugin marketplace (`/plugin marketplace add <owner>/<repo>`). |
| skills/ | Workflows (ingest, query, save, handoff, lint, ...) — Phase 2. |
| hooks/ | Validation + guard hooks (Python, stdlib only) — Phase 2b. |
| templates/manifest.json | Maps template files to their vault destinations; lists vault dirs. |
| templates/vault/ | Files copied into a new vault. Live config names carry `.tmpl` so they don't act on this repo. |
| docs/ | architecture.md, obsidian-setup.md. |

## Hard rules
1. Never copy content from a personal vault into this repo. Examples and the demo vault are fictional.
2. No personal data in committed files: no home paths (C:\Users\<name>, /home/<name>),
   no personal emails, no tokens. Machine-specific settings go in .claude/settings.local.json (gitignored).
3. Before any push that makes this repo public: run the opensource-sanitizer agent; fix every CRITICAL.
4. Hooks and scripts: Python 3.10+, standard library only, must run on Windows, macOS and Linux.
   Resolve the interpreter defensively (python3 / python / py -3).
   Exception: skill scripts may use an OPTIONAL dependency (currently pypdf) if the skill has a
   documented fallback without it. Hooks never use third-party packages.
5. Template files that Claude Code or git would otherwise interpret (CLAUDE.md, settings.json,
   .gitignore, .gitattributes) end in `.tmpl`; destinations live in templates/manifest.json.
6. Plugin, skill and hook formats change between Claude Code versions — check current docs before
   writing or changing a manifest, skill frontmatter or hooks.json.
7. Credit ideas from other projects in README; never copy text or code without a compatible license.
8. The kit must work on a Claude Pro/Max subscription with no API key. Anything that needs
   `claude -p`, the Agent SDK or an API key is optional and documented as such.
9. Before each git operation, state which repo you are in (kit vs vault).

## Roadmap (current: Phase 2a)
0 Prep (done) · 1a Kit skeleton + templates · 1b Personal vault from templates, permission tests ·
2a Skills: ingest, query, save, handoff + init → v0.1, sanitizer (done; stays private) ·
2b lint + PostToolUse validation hook + PreToolUse guard hook → install test, credits, public ·
2c On demand: today, weekly, research-deep, challenge ·
3 Search & eval (BM25 + Turkish stemming, queries.json, recall/MRR) · 4 Custom IDE (form TBD) · 5 Advanced.

## Commits
Conventional Commits (feat:, fix:, docs:, chore:). One logical change per commit.
