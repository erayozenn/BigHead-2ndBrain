# Obsidian setup

Do these once, inside Obsidian, after the vault files exist. Claude never touches `.obsidian/`.

1. **Open folder as vault** → choose your vault folder.
2. **Settings → Files and links**
   - Use [[Wikilinks]]: on
   - New link format: Shortest path when possible
   - Default location for new notes: In the folder specified below → `notes`
   - Default location for new attachments: In the folder specified below → `raw/assets`
3. **Settings → Core plugins → Daily notes**: on
   - New file location: `notes/daily`
   - Date format: `YYYY-MM-DD`
   - Template file location: `notes/templates/daily` (created by init; it contains at least):
     ```
     ---
     type: note
     author: me
     created: {{date:YYYY-MM-DD}}
     ---
     ```
4. **Graph view** → Filters → Search files: `path:wiki`
5. **Obsidian Web Clipper** (optional): set the save folder to `raw/web`.
6. **Spaced Repetition** community plugin (optional, for `/bighead:review`): Settings → Community
   plugins → Browse → "Spaced Repetition" (by Stephen Mwangi) → install, enable. Keep the default
   separators (`::`, `:::`, `?`, `??`) and the default flashcard tag `#flashcards`. Review with
   the command "Review flashcards from all notes"; the plugin writes `<!--SR:…-->` comments under
   reviewed cards — leave them as they are.

Renaming or moving notes: always do it inside Obsidian, which updates links. Claude only proposes it.
