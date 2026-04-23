#!/usr/bin/env python3
"""vidux-plan-gc.py — Mechanical GC for a vidux plan directory.

Replaces the aspirational "archive when the plan feels heavy — agent decides"
rule with measurable triggers so plan GC actually fires.

Three operations on a plan dir (default cwd):
  1. Archive oldest [completed] tasks when count exceeds soft cap (30 → 20).
     Hard cap (50) adds a loud warning.
  2. Archive investigations/*.md that haven't been touched in 180+ days to
     investigations/archive/.
  3. Trim INBOX.md to CAP (20) entries. Removed entries append to
     evidence/YYYY-MM-DD-inbox-archive.md so nothing is lost.

Usage:
  vidux-plan-gc.py                        # live, human output, cwd
  vidux-plan-gc.py --dry-run              # probe only
  vidux-plan-gc.py --json                 # machine output
  vidux-plan-gc.py path/to/plan-dir       # explicit target

Exits 0 always on success; exits 2 on hard-cap violation (so coordinator lanes
can gate ACT on this).
"""
import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

COMPLETED_SOFT = 30
COMPLETED_TARGET = 20
COMPLETED_HARD = 50
INVESTIGATION_AGE_DAYS = 180
INBOX_CAP = 20


def archive_completed_tasks(plan_path, archive_path, dry_run):
    if not plan_path.exists():
        return {"target": "completed-tasks", "archived": 0, "reason": "no PLAN.md"}

    text = plan_path.read_text()
    lines = text.splitlines(keepends=True)

    # Locate ## Tasks section
    task_start = task_end = None
    for i, line in enumerate(lines):
        if re.match(r"^## Tasks\s*$", line):
            task_start = i + 1
        elif task_start is not None and re.match(r"^## ", line):
            task_end = i
            break
    if task_start is None:
        return {"target": "completed-tasks", "archived": 0, "reason": "no ## Tasks section"}
    if task_end is None:
        task_end = len(lines)

    section = lines[task_start:task_end]

    # Group: a task starts with '- [' and owns following indented/blank lines
    # until the next '- ' or a non-indented non-blank line.
    groups = []
    current = None
    for line in section:
        if re.match(r"^- \[", line):
            if current is not None:
                groups.append(current)
            current = [line]
        elif current is not None and (line.startswith((" ", "\t")) or line.strip() == ""):
            current.append(line)
        else:
            if current is not None:
                groups.append(current)
                current = None
            groups.append([line])  # standalone prose line
    if current is not None:
        groups.append(current)

    completed_groups = [g for g in groups if g and re.match(r"^- \[completed\]", g[0])]
    completed_count = len(completed_groups)

    if completed_count <= COMPLETED_SOFT:
        return {"target": "completed-tasks", "archived": 0, "completed_count": completed_count}

    to_archive_count = completed_count - COMPLETED_TARGET
    to_archive = completed_groups[:to_archive_count]
    archived_ids = {id(g) for g in to_archive}

    if not dry_run:
        header_needed = not archive_path.exists()
        with archive_path.open("a") as f:
            if header_needed:
                f.write("# Archived Tasks\n\n"
                        "Archived by `vidux-plan-gc.py`. Append-only — do not edit.\n"
                        "Tasks here are historical record; they were [completed] when archived.\n\n")
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
            f.write(f"## Archived {stamp}\n\n")
            for g in to_archive:
                f.writelines(g)
            f.write("\n")

        new_section = []
        for g in groups:
            if id(g) in archived_ids:
                continue
            new_section.extend(g)
        new_lines = lines[:task_start] + new_section + lines[task_end:]
        plan_path.write_text("".join(new_lines))

    return {
        "target": "completed-tasks",
        "archived": len(to_archive),
        "completed_before": completed_count,
        "completed_after": completed_count - len(to_archive),
        "hard_cap_exceeded": completed_count > COMPLETED_HARD,
    }


def archive_stale_investigations(plan_dir, dry_run):
    inv_dir = plan_dir / "investigations"
    if not inv_dir.is_dir():
        return {"target": "investigations", "archived": 0, "reason": "no investigations/"}

    archive_dir = inv_dir / "archive"
    cutoff = datetime.now().timestamp() - (INVESTIGATION_AGE_DAYS * 86400)
    archived = []
    for f in inv_dir.glob("*.md"):
        if f.stat().st_mtime < cutoff:
            target = archive_dir / f.name
            if not dry_run:
                archive_dir.mkdir(exist_ok=True)
                shutil.move(str(f), str(target))
            archived.append(f.name)
    return {"target": "investigations", "archived": len(archived), "files": archived}


def trim_inbox(plan_dir, dry_run):
    inbox = plan_dir / "INBOX.md"
    if not inbox.exists():
        return {"target": "inbox", "trimmed": 0, "reason": "no INBOX.md"}

    text = inbox.read_text()
    lines = text.splitlines(keepends=True)

    # Group inbox entries the same way as tasks: a line starting '- ' owns
    # following indented/blank lines until the next '- ' or a non-indented
    # non-blank line.
    preamble = []
    groups = []
    current = None
    in_list = False
    for line in lines:
        if line.startswith("- "):
            in_list = True
            if current is not None:
                groups.append(current)
            current = [line]
        elif in_list and current is not None and (line.startswith((" ", "\t")) or line.strip() == ""):
            current.append(line)
        elif in_list:
            if current is not None:
                groups.append(current)
                current = None
            # trailing non-entry content after the list ends — preserve in place
            # by attaching to the most recent group.
            if groups:
                groups[-1].append(line)
            else:
                preamble.append(line)
        else:
            preamble.append(line)
    if current is not None:
        groups.append(current)

    if len(groups) <= INBOX_CAP:
        return {"target": "inbox", "trimmed": 0, "entry_count": len(groups)}

    to_remove = len(groups) - INBOX_CAP
    dropped = groups[:to_remove]
    kept = groups[to_remove:]

    if not dry_run:
        evidence_dir = plan_dir / "evidence"
        evidence_dir.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        archive_file = evidence_dir / f"{stamp}-inbox-archive.md"
        with archive_file.open("a") as f:
            if not archive_file.exists() or archive_file.stat().st_size == 0:
                f.write(f"# INBOX archive {stamp}\n\n"
                        f"Oldest {to_remove} inbox entries rolled off the 20-entry cap.\n\n")
            for g in dropped:
                f.writelines(g)
            f.write("\n")

        new_text = "".join(preamble) + "".join(l for g in kept for l in g)
        inbox.write_text(new_text)

    return {"target": "inbox", "trimmed": to_remove, "entry_count_after": INBOX_CAP}


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("plan_dir", nargs="?", default=".", help="Directory containing PLAN.md (default: cwd)")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change; don't write")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args()

    plan_dir = Path(args.plan_dir).expanduser().resolve()
    plan_path = plan_dir / "PLAN.md"
    archive_path = plan_dir / "ARCHIVE.md"

    results = [
        archive_completed_tasks(plan_path, archive_path, args.dry_run),
        archive_stale_investigations(plan_dir, args.dry_run),
        trim_inbox(plan_dir, args.dry_run),
    ]

    hard_cap_hit = any(r.get("hard_cap_exceeded") for r in results)

    if args.json:
        print(json.dumps({
            "plan_dir": str(plan_dir),
            "dry_run": args.dry_run,
            "targets": results,
            "hard_cap_exceeded": hard_cap_hit,
        }))
    else:
        mode = "DRY-RUN" if args.dry_run else "LIVE"
        print(f"vidux-plan-gc [{mode}] — {plan_dir}")
        for r in results:
            t = r["target"]
            if t == "completed-tasks":
                if "reason" in r:
                    print(f"  completed-tasks: skipped ({r['reason']})")
                elif r["archived"]:
                    warn = "  [!! HARD CAP EXCEEDED]" if r.get("hard_cap_exceeded") else ""
                    print(f"  completed-tasks: archived {r['archived']} "
                          f"({r['completed_before']} → {r['completed_after']}){warn}")
                else:
                    print(f"  completed-tasks: {r['completed_count']} completed, under cap ({COMPLETED_SOFT})")
            elif t == "investigations":
                if r["archived"]:
                    print(f"  investigations: archived {r['archived']} files >{INVESTIGATION_AGE_DAYS}d")
                elif "reason" in r:
                    print(f"  investigations: skipped ({r['reason']})")
                else:
                    print(f"  investigations: nothing over {INVESTIGATION_AGE_DAYS}d")
            elif t == "inbox":
                if r.get("trimmed"):
                    print(f"  inbox: trimmed {r['trimmed']} entries (kept newest {INBOX_CAP})")
                elif "reason" in r:
                    print(f"  inbox: skipped ({r['reason']})")
                else:
                    print(f"  inbox: {r['entry_count']} entries, under cap ({INBOX_CAP})")

    sys.exit(2 if hard_cap_hit else 0)


if __name__ == "__main__":
    main()
