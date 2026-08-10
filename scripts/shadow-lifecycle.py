#!/usr/bin/env python3
"""Measure a hot plan and archive one proven milestone without losing history."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import unicodedata


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import shadow_root_board as _board  # noqa: E402


MAX_PLAN_BYTES = 256 * 1024
MAX_TASK_ROWS = 128
MAX_MILESTONES = 32
ROW_RE = re.compile(
    r"^- \[(?P<state>pending|in_progress|blocked|completed)\] "
    r"(?P<text>.+?) (?P<id>~[0-9a-z]{4})(?P<dod> \(DoD\))?"
    r"(?P<tail>(?: \| [a-z]+:.*)?)$"
)
ROW_LOOSE_RE = re.compile(r"^- \[[^\]]*\] ")
FIELD_RE = re.compile(r"\| (?P<key>[a-z]+): (?P<value>[^|]+?)(?= \||$)")
HASH_RE = re.compile(r"~[0-9a-z]{4}\b")
PROOF_LINE_RE = re.compile(r"^- \S+ (?P<id>~[0-9a-z]{4}) PROOF\b")
STAMP_RE = re.compile(r"^- (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) ", re.MULTILINE)


class LifecycleError(ValueError):
    """A requested compaction is unsafe or not mechanically proven."""


@dataclass(frozen=True)
class Milestone:
    heading: str
    start: int
    end: int
    rows: tuple[dict[str, str], ...]


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "Git command failed"
        raise LifecycleError(detail)
    return result


def safe_slug(heading: str) -> str:
    plain = unicodedata.normalize("NFKD", heading).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")[:64].strip("-")
    if not slug:
        raise LifecycleError("milestone heading cannot produce a safe archive name")
    return slug


def milestones(lines: list[str]) -> list[Milestone]:
    found: list[Milestone] = []
    in_tasks = False
    starts: list[tuple[int, str]] = []
    tasks_end = len(lines)
    for index, line in enumerate(lines):
        if line.startswith("## "):
            if in_tasks:
                tasks_end = index
                break
            heading = line[3:].strip()
            in_tasks = heading == "Tasks" or heading.startswith("Tasks ")
            continue
        if in_tasks and line.startswith("### "):
            starts.append((index, line[4:].strip()))
    for position, (start, heading) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else tasks_end
        parsed: list[dict[str, str]] = []
        malformed = False
        for line in lines[start + 1 : end]:
            raw = line.rstrip("\r\n")
            match = ROW_RE.match(raw)
            if match:
                row = match.groupdict()
                fields = FIELD_RE.findall(row["tail"] or "")
                if (
                    "".join(f" | {key}: {value}" for key, value in fields) != (row["tail"] or "")
                    or len(fields) != len({key for key, _ in fields})
                ):
                    malformed = True
                row["fields"] = dict(fields)  # type: ignore[assignment]
                parsed.append(row)
            elif ROW_LOOSE_RE.match(raw):
                malformed = True
        if malformed:
            parsed.append({"malformed": "true"})
        found.append(Milestone(heading, start, end, tuple(parsed)))
    return found


def measure(text: str) -> dict:
    lines = text.splitlines(keepends=True)
    values = {
        "bytes": len(text.encode("utf-8")),
        "task_rows": sum(1 for line in lines if ROW_RE.match(line.rstrip("\r\n"))),
        "milestones": len(milestones(lines)),
    }
    limits = {
        "bytes": MAX_PLAN_BYTES,
        "task_rows": MAX_TASK_ROWS,
        "milestones": MAX_MILESTONES,
    }
    exceeded = [name for name, value in values.items() if value > limits[name]]
    return {**values, "limits": limits, "exceeded": exceeded, "within_limits": not exceeded}


def progress_items(lines: list[str]) -> list[tuple[int, int, str]]:
    starts = [
        index
        for index, line in enumerate(lines)
        if line.rstrip("\r\n") == "## Progress"
        or line.startswith("## Progress ")
    ]
    if len(starts) != 1:
        raise LifecycleError("plan must have exactly one Progress section")
    start = starts[0] + 1
    end = next(
        (index for index in range(start, len(lines)) if lines[index].startswith("## ")),
        len(lines),
    )
    bullets = [index for index in range(start, end) if lines[index].startswith("- ")]
    return [
        (
            item_start,
            bullets[position + 1] if position + 1 < len(bullets) else end,
            "".join(lines[item_start : bullets[position + 1] if position + 1 < len(bullets) else end]),
        )
        for position, item_start in enumerate(bullets)
    ]


def validate_milestone(
    milestone: Milestone,
    lines: list[str],
) -> tuple[set[str], list[tuple[int, int, str]]]:
    rows = milestone.rows
    if any("malformed" in row for row in rows) or not 2 <= len(rows) <= 7:
        raise LifecycleError("milestone must contain 2-7 well-formed task rows")
    ids = {row["id"] for row in rows}
    if len(ids) != len(rows):
        raise LifecycleError("milestone task ids must be unique")
    if sum(bool(row.get("dod")) for row in rows) != 1:
        raise LifecycleError("milestone must contain exactly one definition-of-done row")
    if any(row["state"] != "completed" for row in rows):
        raise LifecycleError("milestone is not fully completed")
    for row in rows:
        proof = row["fields"].get("proof", "").strip()  # type: ignore[union-attr]
        if re.match(r"^(?:cmd|read|gate) \S", proof) is None:
            raise LifecycleError(f"{row['id']} has no typed proof")

    all_ids = {
        match.group("id")
        for line in lines
        if (match := ROW_RE.match(line.rstrip("\r\n")))
    }
    selected = []
    proven: set[str] = set()
    for start, end, item in progress_items(lines):
        refs = set(HASH_RE.findall(item))
        if not refs.intersection(ids):
            continue
        foreign = refs.intersection(all_ids - ids)
        if foreign:
            raise LifecycleError(
                "a Progress receipt is shared with a live task: " + ", ".join(sorted(foreign))
            )
        selected.append((start, end, item))
        for line in item.splitlines():
            if match := PROOF_LINE_RE.match(line):
                proven.add(match.group("id"))
    missing = sorted(ids - proven)
    if missing:
        raise LifecycleError("completed milestone lacks PROOF receipts: " + ", ".join(missing))
    return ids, selected


def fold_dependencies(line: str, archived_ids: set[str]) -> tuple[str, int]:
    ending = "\n" if line.endswith("\n") else ""
    raw = line.rstrip("\r\n")
    match = ROW_RE.match(raw)
    if not match:
        if "needs:" in raw and archived_ids.intersection(HASH_RE.findall(raw)):
            raise LifecycleError("a malformed live dependency points at the milestone")
        return line, 0
    fields = FIELD_RE.findall(match.group("tail") or "")
    values = dict(fields)
    if "needs" not in values:
        return line, 0
    before = HASH_RE.findall(values["needs"])
    after = [row_id for row_id in before if row_id not in archived_ids]
    if after == before:
        return line, 0
    old = f" | needs: {values['needs']}"
    replacement = f" | needs: {', '.join(after)}" if after else ""
    return raw.replace(old, replacement, 1) + ending, len(before) - len(after)


def append_rotation_receipt(text: str, slug: str) -> tuple[str, str]:
    remaining = milestones(text.splitlines(keepends=True))
    successor = next(
        (
            item.heading
            for item in remaining
            if any(row.get("state") != "completed" for row in item.rows)
        ),
        "none — no open milestone remains",
    )
    stamp = max(STAMP_RE.findall(text), default="1970-01-01T00:00:00Z")
    receipt = (
        f"- {stamp} STRUCT archived milestone {slug} | successor: {successor} "
        "| trigger: proven lifecycle compaction\n"
    )
    lines = text.splitlines(keepends=True)
    progress = next(
        index
        for index, line in enumerate(lines)
        if line.rstrip("\r\n") == "## Progress" or line.startswith("## Progress ")
    )
    end = next(
        (index for index in range(progress + 1, len(lines)) if lines[index].startswith("## ")),
        len(lines),
    )
    if end and lines[end - 1].strip():
        receipt = "\n" + receipt
    lines.insert(end, receipt)
    return "".join(lines), successor


def archive_candidate(text: str, wanted: str, archive_link: Path) -> dict:
    lines = text.splitlines(keepends=True)
    matching = [item for item in milestones(lines) if item.heading == wanted]
    if len(matching) != 1:
        if matching:
            raise LifecycleError("milestone heading is ambiguous")
        raise LifecycleError("milestone was not found in the live Tasks section")
    milestone = matching[0]
    archived_ids, receipts = validate_milestone(milestone, lines)
    slug = safe_slug(wanted)
    marker = f"<!-- shadow:lifecycle:{slug} -->"
    tombstone = (
        f"- Archived milestone: [{slug}]({archive_link.as_posix()}) {marker}\n\n"
    )

    removed = set(range(milestone.start, milestone.end))
    for start, end, _ in receipts:
        removed.update(range(start, end))
    output: list[str] = []
    dependency_folds = 0
    for index, line in enumerate(lines):
        if index == milestone.start:
            output.append(tombstone)
        if index in removed:
            continue
        rewritten, count = fold_dependencies(line, archived_ids)
        dependency_folds += count
        output.append(rewritten)
    block = "".join(lines[milestone.start : milestone.end])
    receipt_text = "".join(item for _, _, item in receipts)
    compacted_plan, successor = append_rotation_receipt("".join(output), slug)
    archive = (
        f"<!-- shadow:archive:v1:{slug} -->\n"
        f"# Archived milestone: {slug}\n\n"
        "Source: `PLAN.md`\n\n"
        "## Exact milestone block\n\n"
        f"{block}"
        "## Exact Progress receipts\n\n"
        f"{receipt_text}"
    )
    if not archive.endswith("\n"):
        archive += "\n"
    return {
        "slug": slug,
        "archive_link": archive_link,
        "marker": marker,
        "plan": compacted_plan,
        "archive": archive,
        "ids": sorted(archived_ids),
        "receipt_count": len(receipts),
        "dependency_folds": dependency_folds,
        "successor": successor,
    }


def ensure_no_symlink(root: Path, relative: Path) -> None:
    current = root
    for part in relative.parts:
        current = current / part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            raise LifecycleError(f"refusing symlinked lifecycle path: {relative.as_posix()}")


def ensure_clean(repo: Path, paths: list[Path]) -> None:
    status = git(
        repo,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        *(path.as_posix() for path in paths),
    ).stdout
    if status.strip():
        raise LifecycleError("PLAN/archive target has uncommitted or staged state")


def atomic_write(path: Path, payload: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), mode)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def committed_snapshot(repo_value: Path) -> tuple[Path, Path, dict[str, str], str]:
    expanded = repo_value.expanduser()
    if expanded.is_symlink():
        raise LifecycleError("repository path must not be a symlink")
    plan = expanded.resolve() / "PLAN.md"
    try:
        token, payload = _board.committed_plan_snapshot(plan)
    except _board.BoardError as exc:
        raise LifecycleError(str(exc)) from None
    repo = Path(token["repo"]).resolve()
    relative = Path(token["relative"])
    if relative.is_absolute() or ".." in relative.parts or (repo / relative).resolve() != plan:
        raise LifecycleError("entity PLAN.md does not resolve inside its Git repository")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise LifecycleError("PLAN.md must be valid UTF-8") from None
    return repo, plan, token, text


def retirement_boundary() -> dict:
    return {
        "supported": False,
        "action": "none",
        "reason": (
            "no Shadow-owned worktree/snapshot manifest with deletion provenance is defined; "
            "lifecycle never guesses deletion targets"
        ),
    }


def inspect(repo_value: Path, wanted: str | None) -> tuple[dict, dict | None]:
    repo, plan, token, text = committed_snapshot(repo_value)
    before = measure(text)
    base = {
        "schema": "shadow.lifecycle.v1",
        "repo": str(repo),
        "plan": str(plan),
        "plan_relative": token["relative"],
        "head": token["head"],
        "budget": {"before": before, "after": before},
        "retirement": retirement_boundary(),
    }
    if wanted is None:
        eligible = []
        for item in milestones(text.splitlines(keepends=True)):
            try:
                validate_milestone(item, text.splitlines(keepends=True))
            except LifecycleError:
                continue
            eligible.append(item.heading)
        base.update(
            {
                "ok": before["within_limits"],
                "action": "report",
                "changed": False,
                "eligible_milestones": eligible,
            }
        )
        return base, None

    slug = safe_slug(wanted)
    plan_relative = Path(token["relative"])
    archive_link = Path("docs") / "plan-archive" / f"{slug}.md"
    archive_relative = plan_relative.parent / archive_link
    archive_path = repo / archive_relative
    ensure_no_symlink(repo, archive_relative)
    ensure_clean(repo, [plan_relative, archive_relative])
    marker = f"<!-- shadow:lifecycle:{slug} -->"
    if archive_path.exists():
        if not archive_path.is_file():
            raise LifecycleError("archive target is not a regular file")
        archive_text = archive_path.read_text(encoding="utf-8")
        if marker in text and f"<!-- shadow:archive:v1:{slug} -->" in archive_text:
            base.update(
                {
                    "ok": before["within_limits"],
                    "action": "already_archived",
                    "changed": False,
                    "milestone": wanted,
                    "archive": str(archive_path),
                }
            )
            return base, None
        raise LifecycleError("archive target already exists with different provenance")
    if marker in text:
        raise LifecycleError("plan tombstone exists but its archive is missing")

    candidate = archive_candidate(text, wanted, archive_link)
    candidate["archive_relative"] = archive_relative
    after = measure(candidate["plan"])
    base.update(
        {
            "ok": after["within_limits"],
            "action": "would_archive",
            "changed": False,
            "milestone": wanted,
            "archive": str(archive_path),
            "receipt_count": candidate["receipt_count"],
            "dependency_folds": candidate["dependency_folds"],
            "successor": candidate["successor"],
            "budget": {"before": before, "after": after},
        }
    )
    return base, candidate


def apply(repo_value: Path, wanted: str) -> dict:
    plan = repo_value.expanduser().resolve() / "PLAN.md"
    try:
        with _board.project_lock(plan):
            return apply_locked(repo_value, wanted, plan)
    except _board.BoardError as exc:
        raise LifecycleError(str(exc)) from None


def apply_locked(repo_value: Path, wanted: str, plan: Path) -> dict:
    report, candidate = inspect(repo_value, wanted)
    if candidate is None:
        return report
    if not report["ok"]:
        raise LifecycleError("archiving this milestone would leave the hot plan over budget")
    repo = Path(report["repo"])
    plan_relative = Path(report["plan_relative"])
    archive_relative: Path = candidate["archive_relative"]
    archive_path = repo / archive_relative
    original = plan.read_bytes()
    plan_mode = stat.S_IMODE(plan.stat().st_mode)
    parent_existed = archive_path.parent.exists()
    try:
        atomic_write(archive_path, candidate["archive"].encode("utf-8"))
        atomic_write(plan, candidate["plan"].encode("utf-8"), plan_mode)
        git(repo, "add", "--", plan_relative.as_posix(), archive_relative.as_posix())
        git(
            repo,
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "user.name=Shadow Lifecycle",
            "-c",
            "user.email=shadow-lifecycle@localhost",
            "commit",
            "--quiet",
            "--no-verify",
            "--no-gpg-sign",
            "--only",
            "-m",
            f"shadow: archive milestone {candidate['slug']}",
            "--",
            plan_relative.as_posix(),
            archive_relative.as_posix(),
        )
    except (OSError, LifecycleError):
        atomic_write(plan, original, plan_mode)
        try:
            archive_path.unlink()
        except FileNotFoundError:
            pass
        subprocess.run(
            ["git", "-C", str(repo), "add", "--", plan_relative.as_posix()],
            capture_output=True,
            check=False,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "rm",
                "--cached",
                "--quiet",
                "--ignore-unmatch",
                "--",
                archive_relative.as_posix(),
            ],
            capture_output=True,
            check=False,
        )
        if not parent_existed:
            try:
                archive_path.parent.rmdir()
            except OSError:
                pass
        raise
    commit = git(repo, "rev-parse", "HEAD").stdout.strip()
    report.update(
        {
            "action": "archived",
            "changed": True,
            "commit": commit,
            "head": commit,
        }
    )
    return report


def print_text(report: dict, *, apply_mode: bool) -> None:
    label = "APPLY" if apply_mode else "DRY RUN"
    print(f"Shadow lifecycle: {label} — {report['action']}")
    before = report["budget"]["before"]
    after = report["budget"]["after"]
    print(
        "Hot plan: "
        f"{before['bytes']}/{before['limits']['bytes']} bytes, "
        f"{before['task_rows']}/{before['limits']['task_rows']} tasks, "
        f"{before['milestones']}/{before['limits']['milestones']} milestones"
    )
    if before != after:
        print(
            "After archive: "
            f"{after['bytes']} bytes, {after['task_rows']} tasks, "
            f"{after['milestones']} milestones"
        )
    if report.get("archive"):
        print(f"Archive: {report['archive']}")
    print(f"Worktree/snapshot retirement: unsupported — {report['retirement']['reason']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--milestone", help="exact milestone heading to archive")
    parser.add_argument("--apply", action="store_true", help="write and commit one archive")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.apply and args.repo is None:
            raise LifecycleError("--apply requires one explicit --repo")
        if args.apply and not args.milestone:
            raise LifecycleError("--apply requires one exact --milestone")
        repo = args.repo or Path.cwd()
        report = apply(repo, args.milestone) if args.apply else inspect(repo, args.milestone)[0]
    except (LifecycleError, OSError, UnicodeError) as exc:
        report = {
            "schema": "shadow.lifecycle.v1",
            "ok": False,
            "action": "refused",
            "changed": False,
            "error": str(exc),
            "retirement": retirement_boundary(),
        }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["action"] == "refused":
        print(f"shadow lifecycle: refused — {report['error']}", file=sys.stderr)
    else:
        print_text(report, apply_mode=args.apply)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
