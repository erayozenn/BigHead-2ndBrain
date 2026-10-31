---
name: review
description: Spaced-repetition flashcards for the vault in the Obsidian Spaced Repetition plugin format — "make <page>" drafts atomic recall cards from a wiki page and appends the approved ones to cards/; "quiz [deck]" runs a recall session in the chat, due cards first. Use when the user wants flashcards, wants to review, practise or be quizzed on what the vault holds, or asks what is due.
argument-hint: "make <wiki page> | quiz [deck]"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(wc -c *)
  - Bash(python ${CLAUDE_SKILL_DIR}/scripts/*)
  - Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)
  - Bash(py -3 ${CLAUDE_SKILL_DIR}/scripts/*)
---

# Review with flashcards

Arguments: `$ARGUMENTS` — `make <wiki page>` or `quiz [deck]`. No argument: show the stats
(step 1) and ask which mode.

The vault's `CLAUDE.md` is the authority for rules (citation, markers, autonomy). Talk in the
vault's chat language; cards are written in the wiki language unless the user asks otherwise.

**Preconditions.** The current directory is a vault: `CLAUDE.md` and `index.md` exist. If not,
stop and say so.

**Format.** Cards live in `cards/cards-<slug>.md` (the `cards-` prefix keeps basenames unique
next to the wiki page `<slug>.md`). The user reviews them with the Obsidian Spaced Repetition
plugin, which appends a scheduling comment `<!--SR:!YYYY-MM-DD,interval,ease-->` under each card
it has seen. **Those comments and every existing card line belong to the plugin's schedule:
never edit, reorder, reword or delete them** — a changed card loses its history. Claude only
appends new cards at the end of a file. Scheduling is the plugin's job; Claude never writes it.

**Python.** `cards.py` (standard library, read-only) lives in `${CLAUDE_SKILL_DIR}/scripts/`.
Use the first interpreter that works (`python3`, `python`, `py -3`).

## 1. Stats

    python ${CLAUDE_SKILL_DIR}/scripts/cards.py stats --vault . [--deck <deck>]

JSON: cards, new (never reviewed), due (scheduled date ≤ today) per file, and the due cards.

## 2. make <page>

1. Find the wiki page (as the query skill does: index.md, then Grep). Read it whole. Cards come
   only from what the page says — no general knowledge.
2. Draft 3–8 cards. Rules:
   - **Atomic:** one fact, definition, cause or contrast per card.
   - **Recall, not recognition:** no yes/no, no "true or false", no answer hidden in the
     question. Prefer "why" and "when" cards over trivia; formulas are fine.
   - **Own words:** no copied sentences, no quote marks. Answer ≤ 25 words, ending with the
     page link `[[<page>]]`.
   - Keep markers: a (disputed) or (provisional) claim says so in the answer, or is skipped.
   - **Syntax:** single-line `Question::Answer [[page]]`. A question or answer that needs line
     breaks uses the multi-line form (question lines, a line with `?`, answer lines) with a blank
     line before and after. Never put `::` or a lone `?` line anywhere else in the text.
3. Show the drafts numbered; the user keeps, edits or drops each. Write only the approved ones.
4. File `cards/cards-<slug>.md`:
   - **New file** (Write): frontmatter per the vault schema (`type: note`, `status: active`,
     `tags: [flashcards]`, `aliases: []`, `sources: ["[[<page>]]"]`, `author: claude`,
     `sensitivity` as the page's), the summary callout
     (`What: flashcards for [[<page>]]. Why kept: spaced-repetition review. Goes stale: when
     [[<page>]] changes.`), a blank line, `#flashcards/<slug>`, then the cards.
   - **Existing file:** first `cards.py prefix --file <file>` (note `lines` and `sha256`). Read
     the file, then Write it back with the new cards appended at the end — every existing byte
     unchanged. Then `cards.py prefix --file <file> --lines <old lines>`: the hash must match.
     If it does not, say so at once and restore the previous content (from git or the Read).
   - Update `updated:` in the frontmatter only for a new file; on append leave the frontmatter
     alone (it is above the plugin's comments, but keep edits minimal).
5. Append to `log.md`: `## [YYYY-MM-DD] save | cards from [[<page>]] → cards/cards-<slug>.md (+N)`.
   The vault Layout may not list `cards/` yet: if CLAUDE.md does not mention it, tell the user
   that adding a Layout row is their call (CLAUDE.md is ask-first).

## 3. quiz [deck]

1. Run stats (with `--deck` if given). Order: due cards (earliest first), then new cards, at
   most 10 per session unless the user asks for more.
2. One card at a time: show the question only. Wait for the answer. Then: correct / partly /
   wrong in one line, the card's answer, and — if wrong or partly — one sentence on the gap with
   the page link. No hints before the attempt; if the user asks for one, give the first step only.
3. Keep a tally. At the end: score, the cards missed, and the advice to review them in Obsidian
   (that is where the schedule updates). Offer `/bighead:teach-back <topic>` for a topic with
   several misses.
4. Quiz mode writes nothing.

## 4. Report

make: file written, cards added, prefix check result. quiz: score and missed cards. Propose a
commit for written cards (`chore: cards from <page>`); never commit without approval.
