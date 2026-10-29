# Your_2ndBRAIN

> Status: pre-alpha (Phase 1a — skeleton). Not usable yet. Working name; the final name is chosen before v0.1.

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

## How it works

See [docs/architecture.md](docs/architecture.md).

```
raw/     your sources (read-only for Claude)
wiki/    pages Claude writes: sources, concepts, entities, syntheses
notes/   your own notes (never edited by Claude)
```

## Install (planned for v0.1)

```
/plugin install your-2ndbrain --marketplace <owner>/<repo>
```

Then run the init skill in an empty folder and follow [docs/obsidian-setup.md](docs/obsidian-setup.md).

## Requirements

- Claude Code (Pro or Max subscription)
- Obsidian
- Git
- Python 3.10+ (for hooks)
- pypdf (`pip install pypdf`) for PDF sources; poppler optional for better text extraction

## Credits

- Andrej Karpathy — the "LLM Wiki" / LLM knowledge base pattern this project is built on.
- Ideas inspired by other open projects in the Claude Code + Obsidian space (TODO before v0.1:
  list each project with a link and verify licenses).

## License

[MIT](LICENSE)
