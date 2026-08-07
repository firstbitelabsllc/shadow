#!/usr/bin/env python3
"""Rerun one task's proof in a clean checkout, then flip it.

This is the only code path that flips a task to completed. It parses
the repo's PLAN.md, finds the row by its ~hash id, reruns a ``cmd``-classed
proof inside a detached clean worktree of HEAD, and — only on success —
rewrites the row's state and appends the paired PROOF Progress line in one
commit. ``read`` and ``gate`` proofs are person/agent judgments and are
refused here on purpose.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import re
import shlex
import subprocess
import sys
from pathlib import Path


ROW_ID_RE = re.compile(r"^~[0-9a-z]{4}$")
FIELD_RE = re.compile(r"\| (?P<key>[a-z]+): (?P<value>[^|]+?)(?= \||$)")
# The grammar's row shape, mirrored from scripts/shadow-lint.py: the id is a
# parsed field, never a substring, so a `needs:` reference or trailing prose
# mentioning another row's id cannot stand in for the row itself.
ROW_LINE_RE = re.compile(
    r"^- \[(?P<state>pending|in_progress|blocked|completed)\] "
    r"(?P<text>.+?) (?P<id>~[0-9a-z]{4})(?P<dod> \(DoD\))?(?P<tail>(?: \| [a-z]+:.*)?)$"
)
PROGRESS_HEADING_RE = re.compile(r"^## Progress\s*$", re.MULTILINE)


class AcceptError(ValueError):
    """Fail closed; nothing was changed."""


def git_completed(repo: Path, *args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AcceptError(f"project Git state cannot be read: {exc}") from exc


def proof_passes(worktree: Path, proof: list[str], timeout_seconds: int) -> bool:
    try:
        result = subprocess.run(
            proof,
            cwd=worktree,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


# Moved verbatim from the retired Drive engine (scripts/shadow-drive.py):
# the clean-checkout review is the mechanical trust boundary and survives
# every simplification of the vocabulary around it.
def create_lead_review_worktree(repo: Path, attempt: Path, lane_id: str, commit: str) -> Path:
    destination = attempt / lane_id
    if destination.is_symlink() or destination.exists():
        raise AcceptError("lead review location is unsafe")
    result = git_completed(repo, "worktree", "add", "--detach", str(destination), commit, timeout=30)
    if result.returncode:
        raise AcceptError("a clean lead review checkout could not be created")
    return destination


def lead_review_passes(worktree: Path, proof: list[str], timeout_seconds: int) -> bool:
    if not proof_passes(worktree, proof, timeout_seconds):
        return False
    status = git_completed(worktree, "status", "--porcelain=v1", "--untracked-files=all")
    if status.returncode:
        return False
    dirt = [
        line
        for line in status.stdout.splitlines()
        if line.strip() and not line[3:].startswith((".shadow/", ".pilot-puppy/"))
        and not line[3:].startswith("__pycache__/") and "/__pycache__/" not in line[3:]
    ]
    return not dirt


def remove_review_worktree(repo: Path, destination: Path) -> None:
    git_completed(repo, "worktree", "remove", "--force", str(destination), timeout=30)
    git_completed(repo, "worktree", "prune", timeout=15)


def find_row(plan_text: str, row_id: str) -> tuple[int, str, str, str]:
    """Return (line index, line, state, proof) for the one row carrying row_id.

    The proof comes from the parsed tail group only — prose in the row text may
    legally contain "| proof:" and must never stand in for the real field.
    """
    matches = [
        (index, line, row)
        for index, line in enumerate(plan_text.splitlines())
        if (row := ROW_LINE_RE.match(line)) is not None and row.group("id") == row_id
    ]
    if not matches:
        raise AcceptError(f"no task carries {row_id}")
    if len(matches) > 1:
        raise AcceptError(f"{row_id} is carried by {len(matches)} rows; fix the duplicate first")
    index, line, row = matches[0]
    tail = row.group("tail") or ""
    pairs = FIELD_RE.findall(tail)
    # The same two tail checks shadow lint makes, because accept must not be a
    # softer gate than the linter: an embedded " | " inside a value silently
    # truncates the cmd this rerun executes, and a repeated key lets a second
    # `proof:` shadow the first. Fail closed instead of running the remnant.
    if "".join(f" | {key}: {value}" for key, value in pairs) != tail:
        raise AcceptError("the row's tail has residue outside `| key: value` fields; run shadow lint")
    if len(pairs) != len({key for key, _ in pairs}):
        raise AcceptError("the row repeats a tail field key; run shadow lint")
    proof = dict(pairs).get("proof", "").strip()
    if not proof:
        raise AcceptError("the row has no proof field")
    return index, line, row.group("state"), proof


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--row", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    row_id = args.row.strip()
    try:
        if ROW_ID_RE.fullmatch(row_id) is None:
            raise AcceptError("row must be a ~hash id, four base36 chars")
        plan_path = repo / "PLAN.md"
        try:
            plan_text = plan_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise AcceptError(f"plan cannot be read: {exc}") from exc
        _, row_line, state, proof = find_row(plan_text, row_id)
        if state == "completed":
            raise AcceptError("the row is already completed")
        if not proof.startswith("cmd "):
            kind = proof.split(" ", 1)[0]
            raise AcceptError(
                f"only cmd proofs are machine-rerunnable; this row is {kind}-classed — "
                "re-observe it yourself and append the PROOF line with the flip"
            )
        argv_proof = shlex.split(proof[4:])
        if not argv_proof:
            raise AcceptError("the proof command is empty")
        head = git_completed(repo, "rev-parse", "--verify", "HEAD").stdout.strip()
        if not head:
            raise AcceptError("the project has no HEAD commit")
        # A conflicted PLAN.md has three index stages; the single-entry restore
        # below would collapse them to the ancestor and destroy the merge state.
        if git_completed(repo, "ls-files", "-u", "--", "PLAN.md").stdout.strip():
            raise AcceptError("PLAN.md has unresolved merge conflicts; resolve them first")
        pool = repo.parent / f"{repo.name}-shadow-accept"
        pool.mkdir(exist_ok=True)
        # A crashed prior run can leave a registered-but-deleted worktree that
        # would wedge every future accept of this row; prune is always safe.
        git_completed(repo, "worktree", "prune", timeout=15)
        review = create_lead_review_worktree(repo, pool, row_id.lstrip("~"), head)
        try:
            passed = lead_review_passes(review, argv_proof, args.timeout_seconds)
        finally:
            remove_review_worktree(repo, review)
            try:
                pool.rmdir()
            except OSError:
                pass
        if not passed:
            raise AcceptError("the proof did not pass in a clean checkout; nothing was changed")
        # The proof may have run for minutes; a write derived from the pre-run
        # snapshot would silently revert anything appended to the plan since.
        try:
            plan_text = plan_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise AcceptError(f"plan cannot be re-read after the proof: {exc}") from exc
        index, _, fresh_state, fresh_proof = find_row(plan_text, row_id)
        # Any state move during the run is somebody else's judgment about this
        # row — completed, or blocked because the work is not done. Overwriting
        # it with completed would erase that record, so only an unchanged row
        # may be flipped.
        if fresh_state != state:
            raise AcceptError(
                f"the row moved from {state} to {fresh_state} while the proof ran; nothing was changed"
            )
        if fresh_proof != proof:
            raise AcceptError("the row's proof changed while it ran; rerun accept against the new proof")
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        plan_lines = plan_text.splitlines(keepends=True)
        plan_lines[index] = re.sub(r"^- \[[a-z_]+\]", "- [completed]", plan_lines[index], count=1)
        updated = "".join(plan_lines)
        heading = PROGRESS_HEADING_RE.search(updated)
        if heading is None:
            raise AcceptError("the plan has no Progress section")
        proof_line = f"- {stamp} {row_id} PROOF {shlex.join(argv_proof)} -> pass (accept)\n"
        # Insert at the end of the Progress section, not end-of-file: a section
        # after Progress would otherwise swallow the audit line.
        next_heading = updated.find("\n## ", heading.end())
        if next_heading == -1:
            updated = updated.rstrip() + "\n" + proof_line
        else:
            updated = updated[: next_heading + 1] + proof_line + updated[next_heading + 1 :]
        # The exact index entry, not a "was it staged" flag: a staged snapshot
        # that differs from the working tree must come back byte-for-byte.
        index_entry = git_completed(repo, "ls-files", "--stage", "--", "PLAN.md").stdout.strip()
        plan_path.write_text(updated, encoding="utf-8")
        added = git_completed(repo, "add", "--", "PLAN.md")
        # --only with a pathspec keeps unrelated already-staged files out of the
        # acceptance commit: the flip and its PROOF line travel alone.
        committed = (
            git_completed(
                repo,
                "commit",
                "--only",
                "-m",
                f"shadow accept: {row_id} proven in a clean checkout",
                "--",
                "PLAN.md",
            )
            if added.returncode == 0
            else added
        )
        if added.returncode or committed.returncode:
            # A flipped row with no acceptance commit would read as completed
            # and refuse the rerun, so the plan goes back exactly as it was.
            plan_path.write_text(plan_text, encoding="utf-8")
            if index_entry:
                mode, blob = index_entry.split()[0], index_entry.split()[1]
                git_completed(repo, "update-index", "--cacheinfo", f"{mode},{blob},PLAN.md")
            else:
                git_completed(repo, "rm", "--cached", "--quiet", "--", "PLAN.md")
            raise AcceptError("the acceptance commit could not be created; the plan was restored")
    except AcceptError as exc:
        print(f"shadow accept: {exc}", file=sys.stderr)
        return 1
    print(f"accepted {row_id}: proof passed in a clean checkout; row flipped with its PROOF line")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
