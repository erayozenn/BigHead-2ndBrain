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

Claude also picks these skills up on its own when your request matches (e.g. "ingest this paper").

> **Editing a skill?** Run `/reload-plugins` afterwards — otherwise the old text keeps running in
> the current session.

## Credits

- Andrej Karpathy — the "LLM Wiki" / LLM knowledge base pattern this project is built on.
- Ideas inspired by other open projects in the Claude Code + Obsidian space (TODO before v0.1:
  list each project with a link and verify licenses).

## License

[MIT](LICENSE)
