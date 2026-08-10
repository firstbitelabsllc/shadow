#!/usr/bin/env python3
"""Compact a hot plan or retire one exact manifested artifact without losing proof."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import shadow_root_board as _board  # noqa: E402


MAX_PLAN_BYTES = _board.HOT_PLAN_MAX_BYTES
MAX_TASK_ROWS = _board.HOT_PLAN_MAX_TASK_ROWS
MAX_MILESTONES = _board.HOT_PLAN_MAX_MILESTONES
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
TOMBSTONE_RE_TEMPLATE = (
    r"<!-- shadow:lifecycle:{slug}:sha256:(?P<digest>[0-9a-f]{{64}}):"
    r"cas:(?P<cas>[0-9a-f]{{64}}):head:(?P<head>[0-9a-f]{{40,64}}):"
    r"blob:(?P<blob>[0-9a-f]{{40,64}}):"
    r"successor:(?P<successor>~[0-9a-z]{{4}}|none) -->"
)
ARCHIVE_HEADER_TEMPLATE = (
    "<!-- shadow:archive:v1:{slug}:sha256:{digest}:cas:{cas}:"
    "head:{head}:blob:{blob}:successor:{successor} -->\n"
)
MAX_ARCHIVE_BYTES = _board.MAX_PLAN_BYTES + 64 * 1024
MAX_MANIFEST_BYTES = 64 * 1024
RETIREMENT_SCHEMA = "shadow.retirement.v1"
RETIREMENT_RECEIPT_SCHEMA = "shadow.retirement-receipt.v1"
OID_RE = re.compile(r"[0-9a-f]{40,64}")
REF_RE = re.compile(r"refs/(?:heads|tags)/[-A-Za-z0-9._/]+")
_AMP = None


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


def git_bytes(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip() or "Git command failed"
        raise LifecycleError(detail)
    return result.stdout


def safe_slug(heading: str) -> str:
    plain = unicodedata.normalize("NFKD", heading).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")[:64].strip("-")
    if not slug:
        raise LifecycleError("milestone heading cannot produce a safe archive name")
    return slug


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_regular_bounded(path: Path, limit: int, label: str) -> bytes:
    """Read one regular leaf without following a symlink or blocking on a FIFO."""
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise LifecycleError(f"{label} is not a regular file")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            content = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
    except OSError as exc:
        if descriptor >= 0:
            os.close(descriptor)
        raise LifecycleError(f"{label} could not be read safely") from exc
    if len(content) > limit:
        raise LifecycleError(f"{label} exceeds its bounded size limit")
    before_state = (
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
        before.st_dev,
        before.st_ino,
    )
    after_state = (
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
        after.st_dev,
        after.st_ino,
    )
    if before_state != after_state:
        raise LifecycleError(f"{label} changed while it was being read")
    return content


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
    return _board.hot_plan_budget(text.encode("utf-8"))


def monotonic_budget_repair(before: dict, after: dict) -> bool:
    """Permit cleanup that improves every rail which was already exceeded."""
    exceeded = set(before["exceeded"])
    if not exceeded or not set(after["exceeded"]).issubset(exceeded):
        return False
    return all(after[name] <= before[name] for name in exceeded) and any(
        after[name] < before[name] for name in exceeded
    )


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


def first_reachable_row(text: str) -> str | None:
    amp = amp_module()
    try:
        parsed = amp._parse(text)
        parsed["claimed"] = set()
        candidates = amp._candidate_ids(parsed)
    except Exception as exc:
        raise LifecycleError("lifecycle successor could not be projected") from exc
    return candidates[0] if candidates else None


def archive_candidate(
    text: str,
    wanted: str,
    archive_link: Path,
    source_token: dict[str, str],
) -> dict:
    lines = text.splitlines(keepends=True)
    matching = [item for item in milestones(lines) if item.heading == wanted]
    if len(matching) != 1:
        if matching:
            raise LifecycleError("milestone heading is ambiguous")
        raise LifecycleError("milestone was not found in the live Tasks section")
    milestone = matching[0]
    archived_ids, receipts = validate_milestone(milestone, lines)
    slug = safe_slug(wanted)
    block = "".join(lines[milestone.start : milestone.end])
    receipt_text = "".join(item for _, _, item in receipts)
    archive_body = (
        f"# Archived milestone: {slug}\n\n"
        "Source: `PLAN.md`\n\n"
        "## Exact milestone block\n\n"
        f"{block}"
        "## Exact Progress receipts\n\n"
        f"{receipt_text}"
    )
    if not archive_body.endswith("\n"):
        archive_body += "\n"
    digest = hashlib.sha256(archive_body.encode("utf-8")).hexdigest()
    marker_placeholder = "__SHADOW_LIFECYCLE_OPERATION_MARKER__"
    tombstone = (
        f"- Archived milestone: [{slug}]({archive_link.as_posix()}) "
        f"{marker_placeholder}\n\n"
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
    compacted_plan, successor = append_rotation_receipt("".join(output), slug)
    successor_row = first_reachable_row(compacted_plan)
    successor_token = successor_row or "none"
    cas = canonical_sha256(
        {
            "schema": "shadow.lifecycle-archive.v1",
            "relative": source_token["relative"],
            "head": source_token["head"],
            "blob": source_token["blob"],
            "milestone": wanted,
            "archive_sha256": digest,
            "successor": successor_token,
        }
    )
    marker = (
        f"<!-- shadow:lifecycle:{slug}:sha256:{digest}:cas:{cas}:"
        f"head:{source_token['head']}:blob:{source_token['blob']}:"
        f"successor:{successor_token} -->"
    )
    compacted_plan = compacted_plan.replace(marker_placeholder, marker, 1)
    archive = ARCHIVE_HEADER_TEMPLATE.format(
        slug=slug,
        digest=digest,
        cas=cas,
        head=source_token["head"],
        blob=source_token["blob"],
        successor=successor_token,
    )
    archive += archive_body
    return {
        "slug": slug,
        "archive_link": archive_link,
        "marker": marker,
        "digest": digest,
        "cas": cas,
        "plan": compacted_plan,
        "archive": archive,
        "ids": sorted(archived_ids),
        "receipt_count": len(receipts),
        "dependency_folds": dependency_folds,
        "successor": successor,
        "successor_row": successor_row,
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


def assert_archive_immutable(
    repo: Path,
    *,
    plan_relative: Path,
    archive_relative: Path,
    archive_link: Path,
    wanted: str,
    slug: str,
    archive_bytes: bytes,
    tombstone: re.Match[str],
) -> dict:
    introductions = git(
        repo,
        "log",
        "--diff-filter=A",
        "--format=%H",
        "--",
        archive_relative.as_posix(),
    ).stdout.splitlines()
    if len(introductions) != 1:
        raise LifecycleError("archive has no unique lifecycle introduction")
    commit = introductions[0]
    parent = git(repo, "rev-parse", f"{commit}^").stdout.strip()
    if parent != tombstone.group("head"):
        raise LifecycleError("archive source HEAD does not match its introduction")
    source_blob = git(
        repo,
        "rev-parse",
        f"{parent}:{plan_relative.as_posix()}",
    ).stdout.strip()
    if source_blob != tombstone.group("blob"):
        raise LifecycleError("archive source PLAN blob does not match its introduction")
    identity = git(repo, "show", "-s", "--format=%s%n%an%n%ae", commit).stdout.splitlines()
    if identity != [
        f"shadow: archive milestone {slug}",
        "Shadow Lifecycle",
        "shadow-lifecycle@localhost",
    ]:
        raise LifecycleError("archive was not introduced by Shadow lifecycle")
    changed = set(
        git(
            repo,
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            commit,
        ).stdout.splitlines()
    )
    if changed != {plan_relative.as_posix(), archive_relative.as_posix()}:
        raise LifecycleError("archive introduction changed unrelated authority")
    if git_bytes(repo, "show", f"{commit}:{archive_relative.as_posix()}") != archive_bytes:
        raise LifecycleError("archive changed after its lifecycle introduction")
    try:
        source_text = git_bytes(repo, "cat-file", "blob", source_blob).decode("utf-8")
    except UnicodeDecodeError:
        raise LifecycleError("archive source PLAN blob is not valid UTF-8") from None
    candidate = archive_candidate(
        source_text,
        wanted,
        archive_link,
        {
            "relative": plan_relative.as_posix(),
            "head": parent,
            "blob": source_blob,
        },
    )
    if (
        candidate["cas"] != tombstone.group("cas")
        or candidate["digest"] != tombstone.group("digest")
        or candidate["marker"] != tombstone.group(0)
        or candidate["archive"].encode("utf-8") != archive_bytes
        or git_bytes(repo, "show", f"{commit}:{plan_relative.as_posix()}")
        != candidate["plan"].encode("utf-8")
    ):
        raise LifecycleError("archive cannot be regenerated from its recorded source")
    return candidate


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


def optional_index_bytes(repo: Path, relative: Path) -> bytes | None:
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f":{relative.as_posix()}"],
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return result.stdout
    return None


def commit_archive_candidate(
    repo: Path,
    plan_relative: Path,
    archive_relative: Path,
    slug: str,
) -> str:
    git(repo, "add", "--", plan_relative.as_posix(), archive_relative.as_posix())
    git(
        repo,
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "commit.gpgsign=false",
        "-c",
        "maintenance.autoDetach=false",
        "-c",
        "gc.autoDetach=false",
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
        f"shadow: archive milestone {slug}",
        "--",
        plan_relative.as_posix(),
        archive_relative.as_posix(),
    )
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def recover_archive_half_state(
    repo_value: Path,
    wanted: str,
    expected: str,
) -> str | None:
    """Finish only the exact deterministic bytes left by an interrupted apply."""
    expanded = repo_value.expanduser()
    if expanded.is_symlink():
        return None
    plan = expanded.resolve() / "PLAN.md"
    try:
        repo = Path(git(expanded.resolve(), "rev-parse", "--show-toplevel").stdout.strip()).resolve()
        plan_relative = plan.relative_to(repo)
        head = git(repo, "rev-parse", "HEAD").stdout.strip()
        source_blob = git(repo, "rev-parse", f"HEAD:{plan_relative.as_posix()}").stdout.strip()
        source_bytes = git_bytes(repo, "cat-file", "blob", source_blob)
        source_text = source_bytes.decode("utf-8")
        slug = safe_slug(wanted)
        archive_link = Path("docs") / "plan-archive" / f"{slug}.md"
        archive_relative = plan_relative.parent / archive_link
        candidate = archive_candidate(
            source_text,
            wanted,
            archive_link,
            {"relative": plan_relative.as_posix(), "head": head, "blob": source_blob},
        )
    except (LifecycleError, UnicodeDecodeError, ValueError):
        return None
    if candidate["cas"] != expected:
        return None
    archive_path = repo / archive_relative
    ensure_no_symlink(repo, archive_relative)
    candidate_plan = candidate["plan"].encode("utf-8")
    candidate_archive = candidate["archive"].encode("utf-8")
    try:
        working_plan = read_regular_bounded(plan, _board.MAX_PLAN_BYTES, "PLAN.md")
        working_archive = (
            read_regular_bounded(archive_path, MAX_ARCHIVE_BYTES, "archive target")
            if os.path.lexists(archive_path)
            else None
        )
    except LifecycleError:
        raise
    index_plan = optional_index_bytes(repo, plan_relative)
    index_archive = optional_index_bytes(repo, archive_relative)
    interrupted = (
        working_plan != source_bytes
        or working_archive is not None
        or index_plan != source_bytes
        or index_archive is not None
    )
    if not interrupted:
        return None
    if (
        working_plan not in {source_bytes, candidate_plan}
        or working_archive not in {None, candidate_archive}
        or index_plan not in {source_bytes, candidate_plan}
        or index_archive not in {None, candidate_archive}
        or git(repo, "diff", "--name-only", "--diff-filter=U").stdout.strip()
    ):
        raise LifecycleError(
            "interrupted archive bytes do not match the exact lifecycle CAS; preserve and inspect them"
        )
    mode = stat.S_IMODE(plan.stat().st_mode)
    atomic_write(archive_path, candidate_archive)
    atomic_write(plan, candidate_plan, mode)
    return commit_archive_candidate(
        repo,
        plan_relative,
        archive_relative,
        candidate["slug"],
    )


def amp_module():
    global _AMP
    if _AMP is not None:
        return _AMP
    path = ROOT / "scripts" / "shadow-amp.py"
    spec = importlib.util.spec_from_file_location("shadow_lifecycle_amp", path)
    if spec is None or spec.loader is None:
        raise LifecycleError("Shadow plan parser could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise LifecycleError("Shadow plan parser could not be loaded") from exc
    _AMP = module
    return module


def claim_successor(plan: Path, owner: str, target_row: str | None) -> dict:
    """Reconcile the committed entity and claim its first reachable row."""
    from shadow_board_import import reconcile_portfolio

    amp = amp_module()
    try:
        reconcile_portfolio(plan.parent, amp, home=Path.home())
        token, payload = _board.committed_plan_snapshot(plan)
        text = payload.decode("utf-8")
        parsed = amp._parse(text)
        unclean = amp.unclean_note(parsed)
        if unclean:
            raise LifecycleError(f"compacted plan cannot re-enter the board: {unclean}")
        state = _board.entity_state(plan, home=Path.home())
        parsed["claimed"] = set()
        candidates = amp._candidate_ids(parsed)
        if target_row is None:
            return {
                "action": "none",
                "reason": "the lifecycle operation recorded no reachable successor row",
            }
        if target_row not in candidates:
            return {
                "action": "advanced",
                "row": target_row,
                "reason": "the operation-bound successor is no longer reachable",
            }
        winner = next(
            (
                claim
                for claim in (state or {}).get("claims", [])
                if claim["row"] == target_row
            ),
            None,
        )
        if winner is not None:
            return {
                "action": "already_claimed",
                "entity": (state or {})["entity"]["id"],
                "row": winner["row"],
                "owner": winner["owner"],
                "return_by": winner["return_by"],
                "board_revision": (state or {})["revision"],
            }
        project = parsed["brief"].get("Project")
        priority = int(parsed["brief"].get("Priority", "3"))
        receipt = _board.claim(
            plan,
            target_row,
            owner,
            project=project,
            priority=priority,
            expected_plan=token,
            home=Path.home(),
        )
    except (_board.BoardError, KeyError, TypeError, UnicodeError, ValueError) as exc:
        if isinstance(exc, LifecycleError):
            raise
        raise LifecycleError(f"successor claim refused after archive commit: {exc}") from None
    claim = receipt["claim"]
    return {
        "action": "claimed",
        "entity": receipt["entity"]["id"],
        "row": claim["row"],
        "owner": claim["owner"],
        "return_by": claim["return_by"],
        "board_revision": receipt["payload"]["revision"],
    }


def attach_successor(
    report: dict,
    plan: Path,
    owner: str,
    target_row: str | None,
) -> dict:
    """Project the committed lifecycle result and make continuation retryable."""
    if not report["budget"]["after"]["within_limits"]:
        report["successor_claim"] = {
            "action": "deferred",
            "reason": "hot plan still exceeds its budget; archive another proven milestone",
        }
        return report
    try:
        report["successor_claim"] = claim_successor(plan, owner, target_row)
    except LifecycleError as exc:
        report["successor_claim"] = {
            "action": "refused",
            "reason": str(exc),
        }
        report["ok"] = False
        report["action"] = f"{report['action']}_needs_successor"
    return report


def retirement_boundary() -> dict:
    return {
        "supported": True,
        "action": "manifest_required",
        "reason": (
            "retirement requires one strict shadow.retirement.v1 manifest; "
            "lifecycle never discovers or guesses deletion targets"
        ),
    }


def strict_keys(value: object, keys: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise LifecycleError(
            f"{label} must contain exactly: {', '.join(sorted(keys))}"
        )
    return value


def load_retirement_manifest(path: Path) -> tuple[dict, str]:
    if not path.is_absolute():
        raise LifecycleError("retirement manifest path must be absolute")
    content = read_regular_bounded(path, MAX_MANIFEST_BYTES, "retirement manifest")
    try:
        value = json.loads(content.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise LifecycleError("retirement manifest must be one valid UTF-8 JSON object") from exc
    manifest = strict_keys(value, {"schema", "target"}, "retirement manifest")
    if manifest["schema"] != RETIREMENT_SCHEMA:
        raise LifecycleError("retirement manifest schema is not supported")
    target = manifest["target"]
    if not isinstance(target, dict) or target.get("kind") not in {"worktree", "snapshot"}:
        raise LifecycleError("retirement target kind must be worktree or snapshot")
    if target["kind"] == "worktree":
        strict_keys(target, {"kind", "path", "head", "landed_ref"}, "worktree target")
        target_path = target.get("path")
        reference = target.get("landed_ref")
    else:
        strict_keys(
            target,
            {"kind", "root", "name", "head", "entity", "expires_at", "recovery_ref"},
            "snapshot target",
        )
        root = target.get("root")
        name = target.get("name")
        if (
            not isinstance(root, str)
            or not Path(root).is_absolute()
            or not isinstance(name, str)
            or name in {"", ".", ".."}
            or Path(name).name != name
        ):
            raise LifecycleError("snapshot target must be one exact child of an absolute root")
        target_path = str(Path(root) / name)
        reference = target.get("recovery_ref")
        if not isinstance(target.get("entity"), str) or _board.ENTITY_ID.fullmatch(
            target["entity"]
        ) is None:
            raise LifecycleError("snapshot entity must be one logical entity hash")
        parse_utc(target.get("expires_at"), "snapshot expiry")
    if not isinstance(target_path, str) or not Path(target_path).is_absolute():
        raise LifecycleError("retirement target must be an absolute exact path")
    if not isinstance(target.get("head"), str) or OID_RE.fullmatch(target["head"]) is None:
        raise LifecycleError("retirement target head must be one full Git object id")
    if not isinstance(reference, str) or REF_RE.fullmatch(reference) is None:
        raise LifecycleError("retirement recovery ref must be a full refs/heads or refs/tags name")
    return manifest, canonical_sha256(manifest)


def parse_utc(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise LifecycleError(f"{label} must be an RFC3339 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise LifecycleError(f"{label} must be an RFC3339 UTC timestamp") from exc
    return parsed.astimezone(timezone.utc)


def git_common_dir(repo: Path) -> Path:
    raw = git(repo, "rev-parse", "--git-common-dir").stdout.strip()
    common = Path(raw)
    if not common.is_absolute():
        common = (repo / common).resolve()
    if common.is_symlink() or not common.is_dir():
        raise LifecycleError("retirement Git common directory is unsafe")
    return common.resolve()


def git_dir(repo: Path) -> Path:
    raw = git(repo, "rev-parse", "--git-dir").stdout.strip()
    directory = Path(raw)
    if not directory.is_absolute():
        directory = (repo / directory).resolve()
    if directory.is_symlink() or not directory.is_dir():
        raise LifecycleError("retirement Git directory is unsafe")
    return directory.resolve()


def clean_git_target(target: Path) -> tuple[str, str]:
    top = Path(git(target, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    if top != target:
        raise LifecycleError("retirement target must be exactly one Git top-level")
    status = git(
        target,
        "status",
        "--porcelain=v1",
        "--ignored=matching",
        "--untracked-files=all",
    ).stdout
    if status:
        raise LifecycleError(
            "retirement refuses tracked, staged, untracked, ignored, or submodule state"
        )
    head = git(target, "rev-parse", "HEAD").stdout.strip()
    return head, hashlib.sha256(status.encode("utf-8")).hexdigest()


def ref_contains(repo: Path, head: str, reference: str) -> str:
    resolved = git(repo, "rev-parse", "--verify", reference).stdout.strip()
    result = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", head, resolved],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise LifecycleError("retirement target head is not recoverable from its declared ref")
    return resolved


def worktree_paths(repo: Path) -> set[Path]:
    paths: set[Path] = set()
    for line in git(repo, "worktree", "list", "--porcelain").stdout.splitlines():
        if line.startswith("worktree "):
            paths.add(Path(line[9:]).resolve())
    return paths


def target_branch(target: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(target), "symbolic-ref", "--quiet", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    if result.returncode == 1:
        return None
    detail = result.stderr.strip() or result.stdout.strip() or "Git branch probe failed"
    raise LifecycleError(detail)


def retirement_cas(
    *,
    manifest_sha: str,
    token: dict[str, str],
    target: Path,
    metadata: os.stat_result,
    head: str,
    status_sha: str,
    recovery_oid: str,
    common_dir: Path,
    worktree_listing: str,
    successor_row: str | None,
) -> str:
    """Bind a preview to the exact authority and filesystem artifact observed."""
    return canonical_sha256(
        {
            "schema": "shadow.retirement-cas.v1",
            "manifest_sha256": manifest_sha,
            "successor_row": successor_row,
            "authority": {
                "head": token["head"],
                "blob": token["blob"],
                "relative": token["relative"],
            },
            "target": {
                "path": str(target),
                "device": metadata.st_dev,
                "inode": metadata.st_ino,
                "mode": metadata.st_mode,
                "mtime_ns": metadata.st_mtime_ns,
                "ctime_ns": metadata.st_ctime_ns,
                "head": head,
                "branch": target_branch(target),
                "status_sha256": status_sha,
                "recovery_oid": recovery_oid,
                "common_dir": str(common_dir),
                "worktree_listing_sha256": hashlib.sha256(
                    worktree_listing.encode("utf-8")
                ).hexdigest(),
            },
        }
    )


def assert_retirement_receipt_immutable(
    repo: Path,
    path: Path,
    *,
    manifest_sha: str,
    kind: str,
) -> None:
    """Require the current receipt blob to equal its one Git introduction."""
    relative = path.relative_to(repo).as_posix()
    introductions = git(
        repo,
        "log",
        "--format=%H",
        "--diff-filter=A",
        "--",
        relative,
    ).stdout.splitlines()
    if len(introductions) != 1:
        raise LifecycleError("retirement receipt has no unique durable introduction")
    current_blob = git(repo, "rev-parse", f"HEAD:{relative}").stdout.strip()
    introduced_blob = git(
        repo,
        "rev-parse",
        f"{introductions[0]}:{relative}",
    ).stdout.strip()
    if current_blob != introduced_blob:
        raise LifecycleError("retirement receipt changed after it was written")
    commit = introductions[0]
    identity = git(repo, "show", "-s", "--format=%s%n%an%n%ae", commit).stdout.splitlines()
    expected_subject = f"shadow: retire {kind} {manifest_sha[:12]}"
    if identity != [
        expected_subject,
        "Shadow Lifecycle",
        "shadow-lifecycle@localhost",
    ]:
        raise LifecycleError("retirement receipt was not introduced by Shadow lifecycle")
    changed = set(
        git(
            repo,
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            commit,
        ).stdout.splitlines()
    )
    if changed != {relative}:
        raise LifecycleError("retirement receipt introduction changed unrelated authority")


def retirement_paths(
    plan: Path,
    manifest_sha: str,
) -> tuple[Path, Path]:
    receipt = plan.parent / "docs" / "plan-archive" / "retirements" / f"{manifest_sha}.json"
    private_root = Path.home().resolve() / ".shadow" / "retirements"
    if private_root.is_symlink() or (private_root.exists() and not private_root.is_dir()):
        raise LifecycleError("private retirement journal directory is unsafe")
    journal = private_root / f"{manifest_sha}.applying.json"
    return receipt, journal


def expected_retirement_receipt(
    manifest: dict,
    cas: str,
    *,
    successor_row: str | None,
    retired_at: str | None = None,
) -> dict:
    target = manifest["target"]
    return {
        "schema": RETIREMENT_RECEIPT_SCHEMA,
        "kind": target["kind"],
        "target_hash": cas,
        "head": target["head"],
        "ref": target.get("landed_ref") or target.get("recovery_ref"),
        "successor_row": successor_row,
        "retired_at": retired_at
        or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def assert_receipt_shape(receipt: object, manifest: dict) -> dict:
    receipt = strict_keys(
        receipt,
        {
            "schema",
            "kind",
            "target_hash",
            "head",
            "ref",
            "successor_row",
            "retired_at",
        },
        "retirement receipt",
    )
    target = manifest["target"]
    reference = target.get("landed_ref") or target.get("recovery_ref")
    if (
        receipt["schema"] != RETIREMENT_RECEIPT_SCHEMA
        or receipt["kind"] != target["kind"]
        or receipt["head"] != target["head"]
        or receipt["ref"] != reference
        or not isinstance(receipt["target_hash"], str)
        or re.fullmatch(r"[0-9a-f]{64}", receipt["target_hash"]) is None
        or (
            receipt["successor_row"] is not None
            and (
                not isinstance(receipt["successor_row"], str)
                or _board.ROW_ID.fullmatch(receipt["successor_row"]) is None
            )
        )
    ):
        raise LifecycleError("retirement receipt does not match its manifest")
    parse_utc(receipt["retired_at"], "retirement receipt time")
    return receipt


def read_retirement_receipt(
    repo: Path,
    path: Path,
    manifest: dict,
    manifest_sha: str,
    *,
    require_immutable: bool = True,
) -> dict | None:
    if not os.path.lexists(path):
        return None
    content = read_regular_bounded(path, MAX_MANIFEST_BYTES, "retirement receipt")
    try:
        receipt = json.loads(content.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise LifecycleError("retirement receipt is malformed") from exc
    receipt = assert_receipt_shape(receipt, manifest)
    if require_immutable:
        assert_retirement_receipt_immutable(
            repo,
            path,
            manifest_sha=manifest_sha,
            kind=manifest["target"]["kind"],
        )
    return receipt


def read_retirement_journal(
    path: Path,
    *,
    manifest_sha: str,
    manifest: dict,
    target: Path,
    quarantine: Path,
) -> dict | None:
    if not os.path.lexists(path):
        return None
    try:
        journal = json.loads(
            read_regular_bounded(path, MAX_MANIFEST_BYTES, "retirement journal").decode(
                "utf-8"
            )
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise LifecycleError("retirement journal is malformed") from exc
    strict_keys(
        journal,
        {
            "schema",
            "manifest_sha256",
            "cas",
            "target",
            "device",
            "inode",
            "quarantine",
            "receipt",
            "successor_row",
        },
        "retirement journal",
    )
    if (
        journal["schema"] != "shadow.retirement-journal.v1"
        or journal["manifest_sha256"] != manifest_sha
        or journal["target"] != str(target)
        or journal["quarantine"] != str(quarantine)
        or not isinstance(journal["cas"], str)
        or re.fullmatch(r"[0-9a-f]{64}", journal["cas"]) is None
        or isinstance(journal["device"], bool)
        or not isinstance(journal["device"], int)
        or journal["device"] < 0
        or isinstance(journal["inode"], bool)
        or not isinstance(journal["inode"], int)
        or journal["inode"] <= 0
        or (
            journal["successor_row"] is not None
            and (
                not isinstance(journal["successor_row"], str)
                or _board.ROW_ID.fullmatch(journal["successor_row"]) is None
            )
        )
    ):
        raise LifecycleError("retirement journal does not match this manifest")
    receipt = assert_receipt_shape(journal["receipt"], manifest)
    if (
        receipt["target_hash"] != journal["cas"]
        or receipt["successor_row"] != journal["successor_row"]
    ):
        raise LifecycleError("retirement journal receipt does not match its CAS")
    return journal


def inspect_retirement(
    repo_value: Path,
    manifest_path: Path,
) -> tuple[dict, dict | None]:
    repo, plan, token, text = committed_snapshot(repo_value)
    manifest, manifest_sha = load_retirement_manifest(manifest_path)
    target_spec = manifest["target"]
    receipt_path, journal_path = retirement_paths(plan, manifest_sha)
    ensure_no_symlink(repo, Path(token["relative"]).parent / receipt_path.relative_to(plan.parent))
    before = measure(text)
    base = {
        "schema": "shadow.lifecycle.v1",
        "repo": str(repo),
        "plan": str(plan),
        "plan_relative": token["relative"],
        "head": token["head"],
        "budget": {"before": before, "after": before},
        "retirement": {"supported": True, "action": "inspect"},
        "manifest_sha256": manifest_sha,
        "receipt": str(receipt_path),
    }
    target = (
        Path(target_spec["path"])
        if target_spec["kind"] == "worktree"
        else Path(target_spec["root"]) / target_spec["name"]
    )
    target = Path(os.path.abspath(target))
    quarantine = target.parent / f".{target.name}.shadow-retired-{manifest_sha[:12]}"
    journal = read_retirement_journal(
        journal_path,
        manifest_sha=manifest_sha,
        manifest=manifest,
        target=target,
        quarantine=quarantine,
    )
    receipt_relative = receipt_path.relative_to(repo).as_posix()
    receipt_status = git(
        repo,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        receipt_relative,
    ).stdout
    receipt = None
    if os.path.lexists(receipt_path):
        receipt = read_retirement_receipt(
            repo,
            receipt_path,
            manifest,
            manifest_sha,
            require_immutable=not bool(receipt_status),
        )
        if receipt_status and journal is None:
            raise LifecycleError("retirement receipt has uncommitted or staged state")
        if receipt_status and receipt != journal["receipt"]:
            raise LifecycleError("staged retirement receipt does not match its crash journal")
        if journal is not None and receipt != journal["receipt"]:
            raise LifecycleError("retirement receipt does not match its crash journal")
        if os.path.lexists(target):
            raise LifecycleError("retirement receipt exists while its target is still present")
        if not receipt_status:
            base.update(
                {
                    "ok": True,
                    "action": "already_retired",
                    "changed": False,
                    "cas": receipt["target_hash"],
                    "successor_row": receipt["successor_row"],
                    "retirement": {"supported": True, "action": "already_retired"},
                }
            )
            cleanup = (
                {
                    "receipt_complete": True,
                    "journal": journal_path,
                    "successor_row": receipt["successor_row"],
                }
                if journal is not None
                else None
            )
            return base, cleanup
    elif receipt_status and journal is None:
        raise LifecycleError("retirement receipt has uncommitted or staged state")
    if journal is not None:
        if not os.path.lexists(target):
            base.update(
                {
                    "ok": True,
                    "action": "would_finalize_retirement",
                    "changed": False,
                    "cas": journal["cas"],
                    "retirement": {"supported": True, "action": "recover"},
                }
            )
            return base, {
                "manifest": manifest,
                "manifest_sha": manifest_sha,
                "target": target,
                "quarantine": Path(journal["quarantine"]),
                "receipt": receipt_path,
                "journal": journal_path,
                "cas": journal["cas"],
                "device": journal["device"],
                "inode": journal["inode"],
                "receipt_payload": journal["receipt"],
                "successor_row": journal["successor_row"],
                "recover": True,
            }
    if not os.path.lexists(target) or target.is_symlink() or target.resolve() != target:
        raise LifecycleError("retirement target is missing, relocated, or crosses a symlink")
    if target in {Path("/"), Path.home().resolve(), repo, plan.parent}:
        raise LifecycleError("retirement target is an authority or broad protected directory")
    metadata = target.lstat()
    if not stat.S_ISDIR(metadata.st_mode):
        raise LifecycleError("retirement target must be one real directory")
    observed_head, status_sha = clean_git_target(target)
    if observed_head != target_spec["head"]:
        raise LifecycleError("retirement target HEAD changed from its manifest")
    reference = target_spec.get("landed_ref") or target_spec.get("recovery_ref")
    recovery_oid = ref_contains(repo, observed_head, reference)
    if target_spec["kind"] == "worktree":
        if git(target, "submodule", "status", "--recursive").stdout.strip():
            raise LifecycleError("retirement refuses a linked worktree containing submodules")
        common_dir = git_common_dir(target)
        if common_dir != git_common_dir(repo):
            raise LifecycleError("retirement worktree does not share the authority Git store")
        if git_dir(target) == common_dir:
            raise LifecycleError("retirement refuses the shared Git store's primary worktree")
        worktree_listing = git(repo, "worktree", "list", "--porcelain").stdout
        if target not in worktree_paths(repo):
            raise LifecycleError("retirement target is not a registered linked worktree")
    else:
        common_dir = git_common_dir(target)
        worktree_listing = ""
        if target.parent != Path(target_spec["root"]).resolve():
            raise LifecycleError("snapshot is not the exact declared child")
        if parse_utc(target_spec["expires_at"], "snapshot expiry") > datetime.now(timezone.utc):
            raise LifecycleError("snapshot has not reached its declared expiry")
        authority_entity = _board.entity_id(plan)
        if target_spec["entity"] != authority_entity:
            raise LifecycleError("snapshot manifest names another logical entity")
        snapshot_plan = target / "PLAN.md"
        if _board.entity_id(snapshot_plan) != authority_entity:
            raise LifecycleError("snapshot does not resolve to the authority entity")
    successor_row = first_reachable_row(text)
    cas = retirement_cas(
        manifest_sha=manifest_sha,
        token=token,
        target=target,
        metadata=metadata,
        head=observed_head,
        status_sha=status_sha,
        recovery_oid=recovery_oid,
        common_dir=common_dir,
        worktree_listing=worktree_listing,
        successor_row=successor_row,
    )
    if journal is not None and (
        journal["cas"] != cas
        or journal["device"] != metadata.st_dev
        or journal["inode"] != metadata.st_ino
        or journal["successor_row"] != successor_row
    ):
        raise LifecycleError("retirement target changed after its journal was prepared")
    operation = {
        "manifest": manifest,
        "manifest_sha": manifest_sha,
        "target": target,
        "quarantine": quarantine,
        "receipt": receipt_path,
        "journal": journal_path,
        "cas": cas,
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "receipt_payload": journal["receipt"] if journal is not None else None,
        "successor_row": journal["successor_row"] if journal is not None else successor_row,
        "recover": False,
    }
    base.update(
        {
            "ok": True,
            "action": "would_retire",
            "changed": False,
            "cas": cas,
            "target": f"artifact@{manifest_sha[:12]}",
            "retirement": {"supported": True, "action": "would_retire"},
        }
    )
    return base, operation


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def commit_retirement_receipt(repo: Path, plan: Path, operation: dict) -> str:
    target = operation["manifest"]["target"]
    receipt = operation["receipt_payload"]
    if receipt != expected_retirement_receipt(
        operation["manifest"],
        operation["cas"],
        successor_row=operation["successor_row"],
        retired_at=receipt["retired_at"],
    ):
        raise LifecycleError("retirement receipt payload changed after its journal was prepared")
    receipt_path: Path = operation["receipt"]
    relative = receipt_path.relative_to(repo)
    ensure_no_symlink(repo, relative)
    atomic_write(
        receipt_path,
        (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    git(repo, "add", "--", relative.as_posix())
    git(
        repo,
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "commit.gpgsign=false",
        "-c",
        "maintenance.autoDetach=false",
        "-c",
        "gc.autoDetach=false",
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
        f"shadow: retire {target['kind']} {operation['manifest_sha'][:12]}",
        "--",
        relative.as_posix(),
    )
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def apply_retirement(
    repo_value: Path,
    manifest_path: Path,
    *,
    expected: str,
    owner: str,
) -> dict:
    plan = repo_value.expanduser().resolve() / "PLAN.md"
    try:
        with _board.project_lock(plan):
            report, operation = inspect_retirement(repo_value, manifest_path)
            if report.get("cas") != expected:
                raise LifecycleError("lifecycle dry-run CAS changed; rerun without --apply")
            if operation is None:
                report["ok"] = True
                return report
            if operation.get("receipt_complete"):
                journal_path = operation["journal"]
                report["ok"] = True
                report = attach_successor(
                    report,
                    plan,
                    owner,
                    operation["successor_row"],
                )
                if report["ok"]:
                    journal_path.unlink(missing_ok=True)
                    fsync_directory(journal_path.parent)
                return report
            journal_path: Path = operation["journal"]
            journal_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(journal_path.parent, 0o700)
            if operation["receipt_payload"] is None:
                operation["receipt_payload"] = expected_retirement_receipt(
                    operation["manifest"],
                    operation["cas"],
                    successor_row=operation["successor_row"],
                )
            if not os.path.lexists(journal_path):
                journal = {
                    "schema": "shadow.retirement-journal.v1",
                    "manifest_sha256": operation["manifest_sha"],
                    "cas": operation["cas"],
                    "target": str(operation["target"]),
                    "device": operation["device"],
                    "inode": operation["inode"],
                    "quarantine": str(operation["quarantine"]),
                    "receipt": operation["receipt_payload"],
                    "successor_row": operation["successor_row"],
                }
                atomic_write(
                    journal_path,
                    (json.dumps(journal, indent=2, sort_keys=True) + "\n").encode("utf-8"),
                    0o600,
                )
            was_recovery = operation["recover"]
            _, revalidated = inspect_retirement(repo_value, manifest_path)
            if (
                revalidated is None
                or revalidated.get("receipt_complete")
                or revalidated["cas"] != expected
                or (not was_recovery and revalidated["recover"])
            ):
                raise LifecycleError("retirement target changed after its journal was prepared")
            operation = revalidated
            target: Path = operation["target"]
            quarantine: Path = operation["quarantine"]
            if os.path.lexists(target):
                current = target.lstat()
                if (
                    current.st_dev != operation["device"]
                    or current.st_ino != operation["inode"]
                    or target.is_symlink()
                ):
                    raise LifecycleError("retirement target changed after the dry run")
            kind = operation["manifest"]["target"]["kind"]
            if kind == "worktree":
                if os.path.lexists(target):
                    _, final_operation = inspect_retirement(repo_value, manifest_path)
                    if (
                        final_operation is None
                        or final_operation.get("receipt_complete")
                        or final_operation.get("recover")
                        or final_operation["cas"] != expected
                    ):
                        raise LifecycleError(
                            "retirement target changed immediately before removal"
                        )
                    operation = final_operation
                    target = operation["target"]
                    git(Path(report["repo"]), "worktree", "remove", "--", str(target))
                elif operation["recover"]:
                    git(Path(report["repo"]), "worktree", "prune")
                if os.path.lexists(target) or target in worktree_paths(Path(report["repo"])):
                    raise LifecycleError("linked worktree retirement did not remove the exact target")
            else:
                if os.path.lexists(target):
                    if os.path.lexists(quarantine):
                        raise LifecycleError("snapshot retirement quarantine already exists")
                    os.rename(target, quarantine)
                    fsync_directory(target.parent)
                if os.path.lexists(quarantine):
                    pinned = quarantine.lstat()
                    if (
                        pinned.st_dev != operation["device"]
                        or pinned.st_ino != operation["inode"]
                        or quarantine.is_symlink()
                    ):
                        raise LifecycleError("snapshot retirement quarantine changed")
                    try:
                        quarantine_head, _ = clean_git_target(quarantine)
                        target_manifest = operation["manifest"]["target"]
                        if quarantine_head != target_manifest["head"]:
                            raise LifecycleError("snapshot HEAD changed in retirement quarantine")
                        ref_contains(
                            Path(report["repo"]),
                            quarantine_head,
                            target_manifest["recovery_ref"],
                        )
                        if _board.entity_id(quarantine / "PLAN.md") != target_manifest["entity"]:
                            raise LifecycleError("snapshot identity changed in retirement quarantine")
                    except (LifecycleError, _board.BoardError):
                        if not os.path.lexists(target) and os.path.lexists(quarantine):
                            try:
                                os.rename(quarantine, target)
                                fsync_directory(target.parent)
                            except OSError:
                                pass
                        raise
                    shutil.rmtree(quarantine)
                    fsync_directory(quarantine.parent)
                if os.path.lexists(target) or os.path.lexists(quarantine):
                    raise LifecycleError("snapshot retirement did not remove the exact target")
            commit = commit_retirement_receipt(
                Path(report["repo"]),
                Path(report["plan"]),
                operation,
            )
            report.update(
                {
                    "ok": True,
                    "action": "retired",
                    "changed": True,
                    "commit": commit,
                    "head": commit,
                    "retirement": {"supported": True, "action": "retired"},
                }
            )
            report = attach_successor(
                report,
                plan,
                owner,
                operation["successor_row"],
            )
            if report["ok"]:
                journal_path.unlink(missing_ok=True)
                fsync_directory(journal_path.parent)
            return report
    except _board.BoardError as exc:
        raise LifecycleError(str(exc)) from None


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
    tombstone = re.search(
        TOMBSTONE_RE_TEMPLATE.format(slug=re.escape(slug)),
        text,
    )
    if archive_path.exists():
        if tombstone is None:
            raise LifecycleError("archive target already exists with different provenance")
        archive_bytes = read_regular_bounded(
            archive_path,
            MAX_ARCHIVE_BYTES,
            "archive target",
        )
        header, separator, body = archive_bytes.partition(b"\n")
        if not separator:
            raise LifecycleError("archive target has incomplete provenance")
        expected_header = ARCHIVE_HEADER_TEMPLATE.format(
            slug=slug,
            digest=tombstone.group("digest"),
            cas=tombstone.group("cas"),
            head=tombstone.group("head"),
            blob=tombstone.group("blob"),
            successor=tombstone.group("successor"),
        ).rstrip("\n").encode("ascii")
        if header != expected_header or hashlib.sha256(body).hexdigest() != tombstone.group(
            "digest"
        ):
            raise LifecycleError("archive target content does not match its provenance digest")
        regenerated = assert_archive_immutable(
            repo,
            plan_relative=plan_relative,
            archive_relative=archive_relative,
            archive_link=archive_link,
            wanted=wanted,
            slug=slug,
            archive_bytes=archive_bytes,
            tombstone=tombstone,
        )
        base.update(
            {
                "ok": before["within_limits"],
                "action": "already_archived",
                "changed": False,
                "milestone": wanted,
                "archive": str(archive_path),
                "cas": regenerated["cas"],
                "archive_sha256": regenerated["digest"],
                "successor_row": regenerated["successor_row"],
            }
        )
        return base, None
    if f"<!-- shadow:lifecycle:{slug}:" in text:
        raise LifecycleError("plan tombstone exists but its archive is missing")

    candidate = archive_candidate(text, wanted, archive_link, token)
    candidate["archive_relative"] = archive_relative
    after = measure(candidate["plan"])
    monotonic_repair = monotonic_budget_repair(before, after)
    base.update(
        {
            "ok": after["within_limits"] or monotonic_repair,
            "action": "would_archive",
            "changed": False,
            "milestone": wanted,
            "archive": str(archive_path),
            "receipt_count": candidate["receipt_count"],
            "dependency_folds": candidate["dependency_folds"],
            "successor": candidate["successor"],
            "successor_row": candidate["successor_row"],
            "cas": candidate["cas"],
            "archive_sha256": candidate["digest"],
            "budget": {"before": before, "after": after},
        }
    )
    return base, candidate


def apply(repo_value: Path, wanted: str, *, expected: str, owner: str) -> dict:
    plan = repo_value.expanduser().resolve() / "PLAN.md"
    try:
        with _board.project_lock(plan):
            return apply_locked(repo_value, wanted, plan, expected=expected, owner=owner)
    except _board.BoardError as exc:
        raise LifecycleError(str(exc)) from None


def apply_locked(
    repo_value: Path,
    wanted: str,
    plan: Path,
    *,
    expected: str,
    owner: str,
) -> dict:
    recovered_commit = recover_archive_half_state(repo_value, wanted, expected)
    report, candidate = inspect(repo_value, wanted)
    if report.get("cas") != expected:
        raise LifecycleError("lifecycle dry-run CAS changed; rerun without --apply")
    if candidate is None:
        report["ok"] = True
        if report.get("action") == "already_archived":
            if recovered_commit is not None:
                report.update(
                    {
                        "action": "archived",
                        "changed": True,
                        "commit": recovered_commit,
                        "head": recovered_commit,
                    }
                )
            return attach_successor(
                report,
                plan,
                owner,
                report.get("successor_row"),
            )
        return report
    before = report["budget"]["before"]
    after = report["budget"]["after"]
    if not after["within_limits"] and not monotonic_budget_repair(before, after):
        raise LifecycleError(
            "archive must monotonically reduce an over-budget hot plan"
        )
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
        commit = commit_archive_candidate(
            repo,
            plan_relative,
            archive_relative,
            candidate["slug"],
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
    report.update(
        {
            "action": "archived",
            "changed": True,
            "commit": commit,
            "head": commit,
            "ok": True,
        }
    )
    return attach_successor(
        report,
        plan,
        owner,
        report.get("successor_row"),
    )


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
    if report.get("cas"):
        print(f"CAS: {report['cas']}")
    retirement = report["retirement"]
    if retirement.get("action") == "manifest_required":
        print(f"Worktree/snapshot retirement: manifest required — {retirement['reason']}")
    elif report.get("target"):
        print(f"Retirement target: {report['target']} — {retirement['action']}")
    if report.get("successor_claim"):
        successor = report["successor_claim"]
        if successor["action"] == "claimed":
            print(
                f"Successor: {successor['row']} claimed by {successor['owner']} "
                f"until {successor['return_by']}"
            )
        elif successor["action"] == "already_claimed":
            print(
                f"Successor: {successor['row']} already claimed by "
                f"{successor['owner']} until {successor['return_by']}"
            )
        else:
            print(f"Successor: {successor['action']} — {successor['reason']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--milestone", help="exact milestone heading to archive")
    parser.add_argument(
        "--retirement-manifest",
        type=Path,
        help="absolute shadow.retirement.v1 manifest for one exact artifact",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="commit one archive or retire one exact manifested artifact",
    )
    parser.add_argument("--expect", help="CAS emitted by the matching dry run")
    parser.add_argument("--by", help="public-safe seat that owns the successor claim")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.apply and args.repo is None:
            raise LifecycleError("--apply requires one explicit --repo")
        if args.milestone and args.retirement_manifest:
            raise LifecycleError("choose one milestone or one retirement manifest")
        if args.apply and not (args.milestone or args.retirement_manifest):
            raise LifecycleError("--apply requires one exact lifecycle operation")
        if args.apply and not args.expect:
            raise LifecycleError("--apply requires --expect from one matching dry run")
        if args.apply and not args.by:
            raise LifecycleError("--apply requires --by for the successor claim")
        if args.by:
            _board.validate_owner(args.by)
        repo = args.repo or Path.cwd()
        if args.retirement_manifest:
            report = (
                apply_retirement(
                    repo,
                    args.retirement_manifest,
                    expected=args.expect,
                    owner=args.by,
                )
                if args.apply
                else inspect_retirement(repo, args.retirement_manifest)[0]
            )
        else:
            report = (
                apply(repo, args.milestone, expected=args.expect, owner=args.by)
                if args.apply
                else inspect(repo, args.milestone)[0]
            )
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
