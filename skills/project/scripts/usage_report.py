#!/usr/bin/env python3
"""How project sessions use their hub, measured from Claude Code transcripts. Read-only, stdlib only.

Usage:
  usage_report.py [--projects-dir <dir>] [--days N] [--human] [--names]

Reads the session transcripts `<projects-dir>/<folder>/<session>.jsonl` (default: the `projects`
folder under CLAUDE_CONFIG_DIR, else ~/.claude/projects). Subagent transcripts are not read. A
session counts when the BigHead SessionStart note is in it; the note says whether a hub matched.

For sessions whose note named a hub, after the first note:
  hub_read             a successful Read, or a Grep whose path is the hub (lower bound)
  hub_read_with_shell  also a Bash/PowerShell command naming the hub (upper bound: naming is not reading)
  edited_project       a successful Write/Edit/NotebookEdit outside the vault
  hub_updated          a successful Write/Edit of the hub (the user approved it)
  edited_without_hub_update  edited_project and not hub_updated
  procedure_reminders  shell calls the procedure hook denied with its checklist (WP7)
  reran_after_reminder reminded commands later run again with success (same command text)

The transcript format is undocumented and may change; lines it cannot read are counted under
`skipped_lines`. Nothing is written anywhere. Output names no project or path unless --names.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

WRITE_TOOLS = {"Write", "Edit", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}
NOTE_START = "[bighead] "
PROCEDURE_TAG = "[bighead procedures]"
MATCH_RE = re.compile(r'^This folder belongs to the project "([^"]+)"\. Hub: (.+)$', re.MULTILINE)
VAULT_RE = re.compile(r"^\[bighead\] Your vault \(second brain\) is at (.+?)\.$", re.MULTILINE)


def norm(path: str) -> str:
    return path.strip().strip('"').replace("\\", "/").rstrip("/").lower()


def default_projects_dir() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    return Path(base) / "projects"


def note_text(record: dict) -> str | None:
    att = record.get("attachment")
    if not isinstance(att, dict) or att.get("hookEvent") != "SessionStart":
        return None
    for field in ("stdout", "content"):
        raw = att.get(field)
        if not isinstance(raw, str) or NOTE_START.strip() not in raw:
            continue
        try:
            ctx = json.loads(raw).get("hookSpecificOutput", {}).get("additionalContext", "")
        except (ValueError, AttributeError):
            ctx = raw
        if isinstance(ctx, str) and ctx.startswith(NOTE_START):
            return ctx
    return None


def is_prompt(record: dict) -> bool:
    if record.get("type") != "user" or record.get("isMeta"):
        return False
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        kinds = {c.get("type") for c in content if isinstance(c, dict)}
        return "text" in kinds and "tool_result" not in kinds
    return False


def result_text(c: dict) -> str:
    content = c.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(str(x.get("text", "")) for x in content if isinstance(x, dict))
    return ""


def scan(path: Path) -> tuple[dict | None, int]:
    """One session's facts, or None if the BigHead note never appears."""
    skipped = 0
    s = None
    calls: dict[str, tuple[str, dict]] = {}
    ok: set[str] = set()
    reminded: set[str] = set()
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except ValueError:
                skipped += 1
                continue
            if not isinstance(rec, dict):
                skipped += 1
                continue
            text = note_text(rec)
            if text is not None:
                if s is None:
                    m = MATCH_RE.search(text)
                    v = VAULT_RE.search(text)
                    kind = "match" if m else ("several" if "Several project hubs" in text else "none")
                    s = {"kind": kind, "project": m.group(1) if m else None,
                         "hub": norm(m.group(2)) if m else None, "vault": norm(v.group(1)) if v else None,
                         "date": str(rec.get("timestamp", ""))[:10], "prompts": 0}
                continue
            if s is None:
                continue
            if is_prompt(rec):
                s["prompts"] += 1
            content = (rec.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for c in content:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "tool_use" and isinstance(c.get("input"), dict):
                    calls[c.get("id", "")] = (c.get("name", ""), c["input"])
                elif c.get("type") == "tool_result":
                    if not c.get("is_error"):
                        ok.add(c.get("tool_use_id", ""))
                    elif PROCEDURE_TAG in result_text(c):
                        reminded.add(c.get("tool_use_id", ""))
    if s is None:
        return None, skipped
    hub, vault = s["hub"], s["vault"]
    read = shell = edited = updated = False
    for tid, (name, inp) in calls.items():
        if tid not in ok:  # counts only with a successful result
            continue
        target = norm(str(inp.get("file_path") or inp.get("notebook_path") or inp.get("path") or ""))
        if name in WRITE_TOOLS:
            if hub and target == hub:
                updated = True
            elif target and not (vault and (target == vault or target.startswith(vault + "/"))):
                edited = True
        elif hub and name in ("Read", "Grep") and target == hub:
            read = True
        elif hub and name in SHELL_TOOLS and hub in norm(str(inp.get("command", ""))):
            shell = True
    order = list(calls)
    reran = 0
    for tid in reminded:
        if tid not in calls:
            continue
        cmd = calls[tid][1].get("command")
        later = order[order.index(tid) + 1:]
        if any(t in ok and calls[t][1].get("command") == cmd for t in later):
            reran += 1
    s.update(hub_read=read, hub_read_with_shell=read or shell, edited_project=edited, hub_updated=updated,
             procedure_reminders=len(reminded), reran_after_reminder=reran)
    return s, skipped


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--projects-dir", type=Path, default=None)
    ap.add_argument("--days", type=int, default=14, help="only transcripts changed in the last N days; 0 = all")
    ap.add_argument("--human", action="store_true", help="a readable table instead of JSON")
    ap.add_argument("--names", action="store_true", help="show project names (check before sharing)")
    args = ap.parse_args()
    root = args.projects_dir or default_projects_dir()
    if not root.is_dir():
        sys.exit(f"no transcript folder: {root}")
    cutoff = time.time() - args.days * 86400 if args.days > 0 else None

    sessions, scanned, skipped = [], 0, 0
    for path in sorted(root.glob("*/*.jsonl")):
        if cutoff is not None and path.stat().st_mtime < cutoff:
            continue
        scanned += 1
        s, bad = scan(path)
        skipped += bad
        if s is not None:
            sessions.append(s)

    notes = {k: sum(1 for s in sessions if s["kind"] == k) for k in ("match", "none", "several")}
    match = [s for s in sessions if s["kind"] == "match"]
    summary = {
        "count": len(match),
        "hub_read": sum(s["hub_read"] for s in match),
        "hub_read_with_shell": sum(s["hub_read_with_shell"] for s in match),
        "edited_project": sum(s["edited_project"] for s in match),
        "hub_updated": sum(s["hub_updated"] for s in match),
        "edited_without_hub_update": sum(s["edited_project"] and not s["hub_updated"] for s in match),
        "procedure_reminders": sum(s["procedure_reminders"] for s in match),
        "reran_after_reminder": sum(s["reran_after_reminder"] for s in match),
    }
    rows = [{"date": s["date"], "kind": s["kind"], "prompts": s["prompts"],
             **{k: s[k] for k in ("hub_read", "hub_read_with_shell", "edited_project", "hub_updated",
                                  "procedure_reminders")},
             **({"project": s["project"]} if args.names else {})} for s in sessions]

    if not args.human:
        print(json.dumps({"days": args.days, "sessions_scanned": scanned,
                          "skipped_lines": skipped, "notes": notes, "match_sessions": summary,
                          "sessions": rows}, indent=2, ensure_ascii=False))
        return
    print(f"Transcripts scanned: {scanned} (last {args.days} days)" if args.days else
          f"Transcripts scanned: {scanned} (all)")
    print(f"BigHead note: hub matched {notes['match']}, no hub {notes['none']}, several {notes['several']}")
    if match:
        print(f"Hub matched ({summary['count']}): read {summary['hub_read']} "
              f"(with shell {summary['hub_read_with_shell']}); edited project files {summary['edited_project']}; "
              f"hub updated {summary['hub_updated']}; edited without hub update {summary['edited_without_hub_update']}; "
              f"procedure reminders {summary['procedure_reminders']} (rerun {summary['reran_after_reminder']})")
    yn = lambda b: "yes" if b else "-"  # noqa: E731
    for r in rows:
        name = f"  {r['project']}" if args.names and r.get("project") else ""
        print(f"{r['date']}  {r['kind']:<7} prompts {r['prompts']:>3}  read {yn(r['hub_read']):<3} "
              f"edited {yn(r['edited_project']):<3} hub updated {yn(r['hub_updated']):<3} "
              f"reminders {r['procedure_reminders']}{name}")
    if skipped:
        print(f"Skipped unreadable lines: {skipped}")


if __name__ == "__main__":
    main()
