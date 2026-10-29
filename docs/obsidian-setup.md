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
   - Template file: a note containing at least:
     ```
     ---
     type: note
     author: me
     created: {{date:YYYY-MM-DD}}
     ---
     ```
4. **Graph view** → Filters → Search files: `path:wiki`
5. **Obsidian Web Clipper** (optional): set the save folder to `raw/web`.

Renaming or moving notes: always do it inside Obsidian, which updates links. Claude only proposes it.
