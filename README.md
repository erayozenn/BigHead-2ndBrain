# Your 2ndBrain

![Your 2ndBrain — your sources in, a linked, cited wiki out](docs/images/hero.svg)

> Status: v0.1 in preparation.

A personal second brain for **Claude Code + Obsidian**, built on Andrej Karpathy's
"LLM Wiki" pattern: you collect immutable raw sources, Claude compiles and maintains a linked
wiki from them, and a short schema file keeps both of you on the same rules.

[Türkçe](README.tr.md)

## Why

- **The wiki is compiled, not chatted.** Knowledge accumulates in linked, sourced pages instead of
  disappearing in chat history.
- **Honest by design.** Every claim cites a source; unsupported, provisional and disputed claims are
  marked; dated facts carry their date.
- **Lives with Obsidian.** Plain Markdown, wikilinks, no lock-in. Claude never renames your notes
  or touches your Obsidian config.
- **Subscription-friendly.** Built for a Claude Pro/Max plan; no API key required.

![Anatomy of a wiki page: frontmatter, summary for future agents, cited claims, dated facts, disputed and provisional markers](docs/images/page-anatomy.svg)

## How it works

![How it works: raw sources are compiled into the wiki by /ingest, answered from by /query, extended by /save; session memory is kept by /handoff](docs/images/how-it-works.svg)

Details: [docs/architecture.md](docs/architecture.md).

```
raw/     your sources (read-only for Claude)
wiki/    pages Claude writes: sources, concepts, entities, syntheses
notes/   your own notes (never edited by Claude)
```

## Install (planned for v0.1)

```
/plugin marketplace add erayozenn/Your-2ndBrain
/plugin install your-2ndbrain@your-2ndbrain
```

Then run `/your-2ndbrain:init` in an empty folder (or an existing Obsidian vault) and follow [docs/obsidian-setup.md](docs/obsidian-setup.md).

## Requirements

- Claude Code (Pro or Max subscription)
- Obsidian
- Git
- Python 3.10+ (for hooks and skill scripts)
- Windows: Git for Windows (Git Bash) — the guard hook runs through bash
- Optional: pypdf (`pip install pypdf`) for PDFs longer than 10 pages and for cheap text-only
  reads. Without it, `ingest` reads PDFs of up to 10 pages natively.

## Skills

| Skill | What it does |
|---|---|
| `/your-2ndbrain:init [target folder]` | Create a vault from the templates — folders, `CLAUDE.md` schema, hot cache, index, log, settings — in an empty folder or an existing Obsidian vault. Dry run first; never overwrites. |
| `/your-2ndbrain:ingest <path-or-url> [text\|smart\|full]` | Capture one source into `raw/`, read it at the right cost, discuss it with you, write wiki pages, update index/log/hot cache, verify links and quotes. |
| `/your-2ndbrain:query <question> [quick\|standard\|deep]` | Answer from the wiki — hot cache, index, then the most relevant pages within a read budget — with every claim cited and an explicit note when the wiki is not enough. |
| `/your-2ndbrain:save [title or what to save]` | Save a good answer or comparison from the session as a synthesis page (or extend one), keeping citations and uncertainty markers. |
| `/your-2ndbrain:handoff [note for the next session]` | End-of-session handoff: rewrite the hot cache's "Now", keep it within its word limit, flag uncommitted work, propose rules learned from your corrections. |
| `/your-2ndbrain:lint [quick\|standard\|deep]` | Health-check the wiki: a script pass (schema, broken links, duplicates, orphans, index coverage, sizes, stale pages) plus judgment checks within a read budget (contradictions, undated facts, citation gaps, missing concept pages). Reports first; fixes only what you approve. |

Claude also picks these skills up on its own when your request matches (e.g. "ingest this paper").

> **Editing a skill?** Run `/reload-plugins` afterwards — otherwise the old text keeps running in
> the current session.

## Hooks

**Guard.** The plugin ships a `PreToolUse` hook that runs before every `Write`, `Edit` and `NotebookEdit`
inside a vault (a folder with `raw/` and a `CLAUDE.md` starting with `# Vault Schema & Rules`).
It denies:

- changes to existing files under `raw/`, and new raw files outside `raw/web/`
- edits to notes whose frontmatter says `author: me`
- anything under `.obsidian/`

Outside a vault it does nothing. If the guard itself fails inside a vault, it blocks the edit
rather than letting it through.

**Limit:** the guard sees file tools only. Shell commands (`rm`, `del`, `python -c "os.remove(...)"`,
`>` redirection) are not inspected; the vault's permission rules deny the common ones, and git
makes the rest reversible.

**Validator.** A `PostToolUse` hook checks every vault page Claude just wrote or edited against
the schema: required frontmatter keys and allowed values, valid dates (`updated` not before
`created`, not in the future), the "For future agent" summary callout, a past "Goes stale" month,
BOM/CRLF. Problems go straight back to Claude, which fixes the page in the same turn. `raw/`,
`notes/`, system files and `author: me` notes are skipped. The validator never blocks on its own
errors.

If no Python 3 is found, both hooks print a warning and stay inactive.

## Credits

- Andrej Karpathy — the "LLM Wiki" / LLM knowledge base pattern this project is built on.
- Ideas inspired by other open projects in the Claude Code + Obsidian space (TODO before v0.1:
  list each project with a link and verify licenses).

## License

[MIT](LICENSE)
