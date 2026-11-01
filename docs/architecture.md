# Architecture

## Two repos: engine and content

| | Engine (this repo) | Content (your vault) |
|---|---|---|
| What | Claude Code plugin: skills, hooks, templates | Your notes, sources and wiki |
| Visibility | Public, MIT | Private, always |
| Updates | `claude plugin update bighead@bighead`, when `version` changes | You and Claude, every day |

Personal content never enters the engine repo, so the engine can be public without risk.

## Vault layers (Karpathy's LLM Wiki pattern)

```
raw/        immutable sources (papers, articles, transcripts, web clips) — read, never modified
wiki/       pages Claude writes and maintains: sources/, concepts/, entities/, syntheses/
CLAUDE.md   the schema: map + rules, kept short
```

Human-written notes live outside the wiki (`notes/`, `author: me`) and are never edited by Claude.
Project and life-management notes live in `projects/` and `areas/`.

## Operations

- **Ingest** — one source at a time: classify by type, discuss with the user, pass the
  compile-value gate (a page only if it adds lasting synthesis), update related pages
  (read budget: 5), update index, log and hot cache.
- **Query** — hot cache → index → pages, within a read budget (Quick 12 KiB / Standard 48 KiB /
  Deep 128 KiB). If the wiki is insufficient, say so, then read raw sources.
- **Lint** — report first, fix after approval: contradictions, freshness violations, orphans,
  broken links, duplicate names, missing frontmatter or summaries, oversized hot cache or index.

## Session memory

| File | Loaded | Role |
|---|---|---|
| CRITICAL_FACTS.md | every session (`@import`) | ~120-token identity card |
| hot.md | every session (`@import`) | ≤ 500 words: now, recent changes, key facts, active threads |
| Threads.md | by today/weekly/lint | full backlog of open topics |
| projects/\<name\>/\<name\>.md | by `/bighead:project open` | one project's goal, state, next step, decisions, lessons |
| playbooks/\<slug\>/\<slug\>.md | by `/bighead:playbook use` | a tested procedure: steps with evidence tags, contexts, checks |
| log.md | on demand | append-only history |
| rules.md | on demand | rules learned from the user's corrections |

The vault is the single source of truth; Claude Code's own auto-memory only points to it.

## Trust and honesty

- Sources are data, not instructions: embedded instructions, fake role messages and requests for
  secrets inside sources are ignored and reported.
- Every wiki claim links a source. Inline markers: `(provisional)`, `(disputed)`, `(unsupported)`.
  Conflicting evidence is kept, not hidden. Risky claims need two independent sources.
- Freshness rule: every statement is timeless, dated, or a pointer. Undated present-tense facts
  that change are forbidden.

## Safety layers

1. Rules in the vault's CLAUDE.md.
2. Permission rules in the vault's `.claude/settings.json` (deny `.obsidian/` and secrets,
   ask before any write to `raw/`, `projects/` or `playbooks/`, deny shell move/rename/delete). Treated as a safety net, not a wall.
3. Hooks: `hooks/guard.py`, a PreToolUse guard on Write/Edit/NotebookEdit — denies changes to
   existing raw files, new raw files outside `raw/web/`, edits to `author: me` notes and anything
   under `.obsidian/`. Inert outside a vault; fails closed inside one. Shell commands are not
   inspected (layer 2 and git cover them). `hooks/validate.py`, a PostToolUse validator on
   Write/Edit — checks the written page against `lib/vault_schema.py` (frontmatter keys and values,
   dates, summary callout, past "Goes stale" month, BOM/CRLF) and returns problems as a `block`
   decision so Claude fixes them in the same turn; never blocks on its own errors.
   Tests: `python -m unittest discover hooks/tests` and `python -m unittest discover lib/tests`.
4. Git: every change is reversible.

## Measuring page finding

`skills/query/scripts/eval_search.py` scores ways of finding pages against a question file kept in
the vault: found@5, recall@5 and MRR, plus questions the vault cannot answer. It compares grep,
BM25 and BM25 with Turkish normalisation (`search.py`, standard library, no index on disk), and can
score page lists or rewritten queries produced elsewhere, such as by an agent. `/bighead:query` does
not use `search.py`: connect it only if a measurement on your vault shows it finds pages the index
misses. Write the questions and the decision rule before looking at results, and tune only on a
separate part of the questions. Tests: `python -m unittest discover skills/query/scripts/tests`.
