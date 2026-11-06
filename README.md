# BigHead 2ndBrain

![BigHead 2ndBrain — your sources in, a linked, cited wiki out](docs/images/hero.svg)

> **Status: v0.6 — experimental.** Skills and the vault schema may still change between 0.x
> versions. Updates never rewrite an existing vault; the first line of your vault's `CLAUDE.md`
> shows which template it was made from. Tested on Windows so far; macOS and Linux reports are
> welcome.

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

## Install

In your shell:

```
claude plugin marketplace add erayozenn/BigHead-2ndBrain
claude plugin install bighead@bighead
claude plugin list        # bighead@bighead  Status: ✔ enabled
```

Or inside a Claude Code session: `/plugin marketplace add erayozenn/BigHead-2ndBrain`, then
`/plugin install bighead@bighead` — this opens the plugin's panel, where you
confirm the install. Start a new session (or run `/reload-plugins`) afterwards.

Then run `/bighead:init` in an empty folder (or an existing Obsidian vault) and follow [docs/obsidian-setup.md](docs/obsidian-setup.md).

## Update

Auto-update is off by default for this marketplace, so update by hand:

```
claude plugin update bighead@bighead
```

Then start a new session (or run `/reload-plugins`). To update automatically, open `/plugin`, go to
**Marketplaces**, select `bighead` and choose **Enable auto-update**. Your vault is not changed.

## Using it from other project folders

You usually open Claude Code in a code repo, not in the vault. To use the same memory there, set
the plugin's **Vault folder** option to your vault's folder: `/plugin configure bighead@bighead` in
a session, or `claude plugin install bighead@bighead --config vault_path=<vault folder>`.
Leave it empty to use the kit only inside the vault. Because Claude Code may block reads outside
the folder you start in, also add the vault to your user settings
(`"permissions": {"additionalDirectories": ["<vault folder>"]}`) or start with
`claude --add-dir <vault folder>`.

Then, in a session opened in a project folder:

- **A short note at session start** (about 500 tokens) gives the vault location, the project hub
  whose `**Repo.**` path contains the folder (or whose optional `**Remote.**` matches the repo's
  remote), and the rules for working from outside the vault: research before building, show hub
  changes before writing them, check dated wiki claims, read no other project's hub unless asked,
  no vault content in the repo, its commits or PRs. With several matching hubs Claude asks; with
  none it names no hub.
- **project, save, handoff, playbook, query, ingest and research-deep** work there; the other
  skills stay vault-only.
- **"Save this"** works without a slash command: project decisions go to the hub (after you approve
  the change), general knowledge to the wiki, where the next project can find it.
- **Protection:** writes to `wiki/`, `cards/`, `index.md`, `log.md` and `hot.md` go through; every
  other vault path asks first, even in accept-edits mode. Shell deletes and moves into the vault
  are denied.

Tested in an acceptance test with a copy of a real vault, two repos and a folder without a hub,
judged blind against a spec frozen before the run: memory 14/14 facts with no invention, research
before building, saving without slash commands, knowledge saved in one project found from another
(after a hint), dated wiki claims checked against PyPI, no vault text in commits, shell deletes
blocked. The first run failed five scenarios because project sessions never load the vault's
`CLAUDE.md`; the session note now carries those rules. One vault, one model, Windows only.

## Requirements

- Claude Code (Pro or Max subscription)
- Obsidian
- Git
- Python 3.10+ (for hooks and skill scripts)
- Windows: Git for Windows (Git Bash) — the hooks run through bash. Without it, Claude Code runs
  them in PowerShell, where they can fail and Write/Edit calls can be blocked
- Optional: pypdf (`pip install pypdf`) for PDFs longer than 10 pages and for cheap text-only
  reads. Without it, `ingest` reads PDFs of up to 10 pages natively.

## Skills

| Skill | What it does |
|---|---|
| `/bighead:init [target folder]` | Create a vault from the templates — folders, `CLAUDE.md` schema, hot cache, index, log, settings — in an empty folder or an existing Obsidian vault. Dry run first; never overwrites. |
| `/bighead:ingest <path-or-url> [text\|smart\|full]` | Capture one source into `raw/`, read it at the right cost, discuss it with you, write wiki pages (or one register line, for a source that does not pass the value gate), update index/log/hot cache, verify links and quotes. |
| `/bighead:query <question> [quick\|standard\|deep]` | Answer from the wiki — hot cache, index, then the most relevant pages within a read budget — with every claim cited and an explicit note when the wiki is not enough. |
| `/bighead:save [title or what to save]` | Save a good answer or comparison from the session as a synthesis page (or extend one), keeping citations and uncertainty markers. When you ask it to save, it writes wiki files at once and tells you how to undo; it asks first for anything else. |
| `/bighead:handoff [note for the next session]` | End-of-session handoff: rewrite the hot cache's "Now", keep it within its word limit, flag uncommitted work, propose rules learned from your corrections. |
| `/bighead:lint [quick\|standard\|deep]` | Health-check the wiki: a script pass (schema, broken links, duplicates, orphans, index coverage, sizes, stale pages) plus judgment checks within a read budget (contradictions, undated facts, citation gaps, missing concept pages). Reports first; fixes only what you approve. |
| `/bighead:teach-back <topic or notes/ file>` | Check your understanding: you explain a topic in your own words, Claude compares it with the wiki and returns gaps, errors and vague spots as questions. Writes nothing. |
| `/bighead:review make <page> \| quiz [deck]` | Flashcards: draft recall cards from a wiki page and append the ones you approve to `cards/` (Obsidian [Spaced Repetition](https://github.com/st3v3nmw/obsidian-spaced-repetition) format), or quiz you in the chat, due cards first. Never edits existing cards or their schedule. |
| `/bighead:exam <page> [n] [one-by-one]` | Practice exam from a source or topic page and its linked concepts: mixed questions (definitions, calculations, why/when, comparisons), graded with a rubric citing the pages, weak topics and follow-ups. Writes nothing but a log line. |
| `/bighead:research-deep <question> [quick\|deep]` | Research beyond the vault: wiki first, then the web for the gaps within a search budget; returns a cited brief with sources ranked by authority. Writes nothing itself — you pick sources to ingest and can save the brief. |
| `/bighead:project new <name> \| open [name] \| update <name>` | Project memory: one hub page per project (goal, repo pointer, current state, next step, decisions, lessons) that a cold session can continue from. `open` writes nothing and counts repo commits the hub has not seen; changes are written only after you approve them. |
| `/bighead:playbook save <slug> \| use [slug] \| record <slug> \| retire <slug>` | Tested procedures: one page per reusable way of doing a job, with evidence tags on each step, the contexts it was tested in and its version history. `use` checks the procedure against its sources and gives a verdict first; only outcomes you approve are counted; it can propose promoting a playbook to a skill, but you decide. Nothing is deleted. |
| `/bighead:today [focus]` | Start-of-day brief: hot cache, open threads, recent log, today's daily note and due cards → a short plan and one recall question. Writes nothing. |
| `/bighead:weekly [YYYY-Www]` | Weekly review: what was added, changed and decided, gaps, threads, cards, three suggestions for next week; saved to `archive/` if you approve. |

Claude also picks these skills up on its own when your request matches (e.g. "ingest this paper").

**Lint limit.** A code span across several lines, or a fence inside a blockquote, is read as prose,
so a link in one can be reported as broken.

**Study mode.** The plugin also ships a `tutor` [output style](https://code.claude.com/docs/en/output-styles):
for study questions Claude asks for your guess first, gives hints in steps and the full answer
only when you ask; vault operations (ingest, lint, …) run as usual. Turn it on with
`/output-style bighead:tutor`, and back with `/output-style default`. It is never on
by default. Ingest also offers (once, skippable) to take 2–5 of your questions before reading a
paper or course source and answers them on the source page.

> **Editing a skill?** Run `/reload-plugins` afterwards — otherwise the old text keeps running in
> the current session.

## Hooks

**Guard.** The plugin ships a `PreToolUse` hook that runs before every `Write`, `Edit` and `NotebookEdit`
inside a vault (a folder with `raw/` and a `CLAUDE.md` starting with `# Vault Schema & Rules`).
It denies:

- changes to existing files under `raw/`, and new raw files outside `raw/web/`
- edits to notes whose frontmatter says `author: me`
- anything under a `.obsidian/` folder

Outside a vault it does nothing. If the guard itself fails inside a vault, it blocks the edit
rather than letting it through. From a session opened outside the vault (see "Using it from other
project folders"), every vault path except `wiki/`, `cards/`, `index.md`, `log.md` and `hot.md`
asks first.

**Shell commands.** The guard also reads `Bash` and `PowerShell` commands. It denies deletes,
moves and `>` redirections that name the vault (or the **Vault folder** option), and any such
command run inside a vault, including `git rm`, `git mv`, `git clean` and `git reset --hard`. It
adds about 0.2 s per shell command.

**Limits:** the shell check is a text heuristic, not a parser. Variables, globs, relative paths
from outside the vault and indirect deletes (`python -c "os.remove(...)"`) are not seen; git makes
the rest reversible. Inside a vault it can also refuse a harmless command whose text only mentions
`rm` (for example in a `git commit -F -` message; quoted text and `cat <<EOF` bodies are skipped).
A hard link to a raw file made outside `raw/` looks like an ordinary file, so it is not protected.

**Session start.** A `SessionStart` hook adds the short note described in "Using it from other
project folders". It is silent with no **Vault folder** set, inside a vault, or on any error.

**Validator.** A `PostToolUse` hook checks every vault page Claude just wrote or edited against
the schema: required frontmatter keys and allowed values, valid dates (`updated` not before
`created`, not in the future), the "For future agent" summary callout, a past "Goes stale" month,
BOM/CRLF. Problems go straight back to Claude, which fixes the page in the same turn. `raw/`,
`notes/`, system files and `author: me` notes are skipped. The validator never blocks on its own
errors.

If no Python 3 is found, the guard and the validator print a warning and stay inactive; the
session-start hook stays silent.

## Does it need search?

Not yet, on the author's own wiki. `/bighead:query` finds pages by reading `index.md`, with no
search engine. Two tests on a 31-page wiki, mostly Turkish questions over English pages, compared
grep, BM25, BM25 with Turkish normalisation, an agent reading only the index, and an agent that
rewrites the question for BM25. The rule, committed before any search code: connect search only if
the rewrite method finds at least 3 more questions than the index agent. It did not: both found 22
of 22 in the first test and 15 of 15 in the second, whose questions came from page details not
shown in the index. Scripts alone found 8 to 13 of 22. So search is not connected; the scripts ship
so you can measure your own vault (see "Measuring page finding" in
[docs/architecture.md](docs/architecture.md)). Limits: one small wiki, page finding only, 37
questions in all.

A later answer test on the same vault (15 sources, 28 fact questions) asked how well each method
answers, not only finds pages: grep over the raw sources answered 26, BM25 over raw chunks 23,
`/bighead:query` 22, the wiki pages alone 20, at similar token costs (grep ~11.6k, query ~10.2k per
question). No method invented answers; the wiki lost details by compressing them.
`/bighead:query` falls back to the raw sources when it notices the wiki is short, which recovers
some of that detail, not all. One small corpus, so treat this as a hint, not a benchmark.

## Credits

- Andrej Karpathy — the [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
  idea: raw sources, an LLM-maintained wiki and a schema file; ingest, query and lint.
- [claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian) by AgriciDaniel (MIT) —
  ideas for a session hot cache read before the index, read-only helpers that hand back drafts,
  and keeping weak or conflicting evidence visible.

Ideas only: no code or text was copied from either; the rules and scripts here are written from
scratch.

## License

[MIT](LICENSE)
