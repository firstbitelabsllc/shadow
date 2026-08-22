#!/usr/bin/env python3
"""Rerun one owned checkpoint's proof in a clean checkout, then flip it.

This is the only code path that flips a `cmd`-proven checkpoint to completed.
It parses the project PLAN.md, finds the row by its ~hash id, reruns a
``cmd``-classed proof inside a detached clean worktree of HEAD, and — only on
success — rewrites the row's state and appends the paired PROOF Progress line
in one commit. Its path-free ``--entity`` form also reconciles an authenticated,
published ``cmd`` completion whose remote journal remains acquired. ``read`` and
``gate`` proofs are person/agent judgments and are refused here on purpose.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import shadow_root_board as _board  # noqa: E402
import shadow_remote_claim as _remote_claim  # noqa: E402
from shadow_cmd_proof import script_operand_issue  # noqa: E402
import shadow_plan_grammar as _grammar  # noqa: E402
import shadow_plan_store as _plan_store  # noqa: E402

_AMP_SPEC = importlib.util.spec_from_file_location(
    "shadow_accept_amp", ROOT / "scripts" / "shadow-amp.py"
)
_amp = importlib.util.module_from_spec(_AMP_SPEC)
sys.modules.setdefault("shadow_accept_amp", _amp)
_AMP_SPEC.loader.exec_module(_amp)

_LINT_SPEC = importlib.util.spec_from_file_location(
    "shadow_accept_lint", ROOT / "scripts" / "shadow-lint.py"
)
_lint = importlib.util.module_from_spec(_LINT_SPEC)
sys.modules.setdefault("shadow_accept_lint", _lint)
_LINT_SPEC.loader.exec_module(_lint)


ROW_ID_RE = _grammar.ROW_ID_RE
NEEDS_REF_RE = _grammar.NEEDS_REF_RE
FIELD_RE = _grammar.FIELD_RE
ROW_LINE_RE = _grammar.ROW_RE
# Prefix-matched, exactly as lint's `_section` reads a heading: `## Progress —
# the receipts` is a Progress section to the enforcer, so an exact-string match
# here would refuse to append the PROOF line after a proof that already passed.
PROGRESS_HEADING_RE = re.compile(r"^## Progress(?: [^\n]*)?$", re.MULTILINE)
LIFECYCLE_ARCHIVE_RE = re.compile(
    r"^- Archived milestone: \[(?P<slug>[a-z0-9][a-z0-9-]*)\]"
    r"\((?P<path>[^)]+)\) "
    r"<!-- shadow:lifecycle:(?P=slug):sha256:(?P<digest>[0-9a-f]{64}):"
    r"cas:(?P<cas>[0-9a-f]{64}):head:(?P<head>[0-9a-f]{40}):"
    r"blob:(?P<blob>[0-9a-f]{40}):"
    r"successor:(?P<successor>~[0-9a-z]{4}|none) -->$"
)


_shell_script_index = _grammar.shell_script_index
_shell_operators = _grammar.shell_operators


class AcceptError(ValueError):
    """Fail closed; nothing was changed."""


def proof_argv(command: str) -> list[str]:
    try:
        return _grammar.proof_argv(command)
    except ValueError as exc:
        raise AcceptError(f"the proof command cannot be parsed: {exc}") from exc


def blocking_lint_finding(
    text: str,
    plan_path: Path,
    *,
    proof_root: Path | None = None,
) -> dict | None:
    """The first blocking finding this plan text would draw, judged at HEAD.

    Codex (PR #359, P2): accept proves and commits against the committed
    checkout, so the lint must answer in-tree paths from HEAD too. Reading the
    working tree made unrelated local state a veto — deleting a committed
    executable another row's proof names emitted blocking PROOF-ARGV0 and
    refused a flip the clean checkout runs fine.
    """
    return next(
        (
            finding
            for finding in _lint.lint_plan(
                text,
                root=proof_root or plan_path.parent,
                committed=True,
            )
            if finding["severity"] == "blocking"
        ),
        None,
    )


def refuse_lint_blocked_plan(
    text: str,
    plan_path: Path,
    *,
    proof_root: Path | None = None,
    row_id: str | None = None,
) -> None:
    """Refuse a plan the lint would block, saying WHICH row and WHICH root.

    Measured 2026-08-17: accepting `~nx05` refused with `PROOF-ARGV0 on line
    26`. Line 26 was `~gskl`, a row completed weeks earlier and untouched by
    the flip, and nothing said that `--repo` names the root where proofs RUN
    rather than where the plan lives. Re-running with the source checkout
    worked immediately. The message was true and unusable; a refusal that
    cannot be acted on is a defect even when its verdict is right.
    """
    finding = blocking_lint_finding(text, plan_path, proof_root=proof_root)
    if finding is None:
        return
    blocking_row = row_id_at_line(text, finding["line"])
    where = f"line {finding['line']}"
    if blocking_row:
        where = f"{blocking_row} (line {finding['line']})"
        if row_id and blocking_row != row_id:
            where += f" — not the row you are accepting, {row_id}"
    remedy = ""
    if finding["check"] == "PROOF-ARGV0" and "/" in finding["detail"]:
        remedy = (
            "; --repo is the root where proofs RUN, not where the plan lives — "
            "for a machine-local plan pass the source checkout its proofs name"
        )
    raise AcceptError(
        "the completed plan would fail shadow lint "
        f"({finding['check']} on {where}: {finding['detail']}){remedy}; "
        "nothing was changed"
    )


def row_id_at_line(text: str, line: int) -> str | None:
    """The row id on a 1-indexed plan line, when that line is a task row."""
    lines = text.splitlines()
    if not 1 <= line <= len(lines):
        return None
    match = ROW_LINE_RE.match(lines[line - 1].rstrip())
    return match.group("id") if match else None


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


def atomic_write_text(
    path: Path,
    text: str,
) -> _plan_store.PublishReceipt | None:
    """Replace one complete PLAN in its own directory; never leave truncation."""
    try:
        snapshot = _board.open_plan(path)
    except _board.BoardError as exc:
        raise AcceptError(f"project plan could not be opened: {exc}") from exc
    if snapshot.is_tree:
        try:
            return (
                _plan_store.PlanTransaction.begin(
                    path,
                    expected_root=snapshot.root_sha256,
                )
                .replace_content(text.encode("utf-8"))
                .publish()
            )
        except _plan_store.PlanStoreError as exc:
            raise AcceptError(f"project plan tree could not be replaced: {exc}") from exc
    descriptor, temporary = tempfile.mkstemp(prefix=".shadow-accept.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), path.stat().st_mode & 0o777)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except OSError as exc:
        raise AcceptError("project plan could not be replaced atomically") from exc
    finally:
        Path(temporary).unlink(missing_ok=True)
    return None


def restore_plan_index(
    repo: Path,
    plan_path: Path,
    pathspec: str,
    original_text: str,
    index_entry: str,
) -> None:
    atomic_write_text(plan_path, original_text)
    if index_entry:
        mode, blob = index_entry.split()[0], index_entry.split()[1]
        restored = git_completed(
            repo,
            "update-index",
            "--cacheinfo",
            f"{mode},{blob},{pathspec}",
        )
    else:
        restored = git_completed(repo, "rm", "--cached", "--quiet", "--", pathspec)
    if restored.returncode:
        raise AcceptError("the acceptance commit failed and its index could not be restored")


def restore_tree_publication(
    repo: Path,
    plan_path: Path,
    pathspecs: list[str],
    publication: _plan_store.PublishReceipt,
) -> None:
    """Roll back only objects/root created by this failed acceptance commit."""
    try:
        _plan_store.rollback(plan_path, expected_root=publication.root_sha256)
        reset = git_completed(repo, "reset", "--quiet", "HEAD", "--", *pathspecs)
        if reset.returncode:
            raise AcceptError("the tree acceptance index could not be restored")
        _plan_store.discard_unreachable(plan_path, publication.new_objects)
    except (_plan_store.PlanStoreError, AcceptError) as exc:
        raise AcceptError(
            "the acceptance commit failed and its plan tree could not be restored"
        ) from exc


def commit_completed_plan(
    repo: Path,
    plan_path: Path,
    plan_relative: Path,
    row_id: str,
    owner: str,
    plan_token: dict[str, str],
    original_text: str,
    updated_text: str,
    resumes: list[str],
) -> tuple[dict, dict[str, str], str]:
    """Create one exact project commit while preserving unrelated index state."""
    plan_pathspec = str(plan_relative)
    with _board.project_lock(plan_path):
        try:
            locked_token, locked_bytes = _board.committed_plan_snapshot(plan_path)
            locked_text = locked_bytes.decode("utf-8")
        except (_board.BoardError, OSError, UnicodeError) as exc:
            raise AcceptError(f"plan changed before the project commit: {exc}") from exc
        if locked_token != plan_token or locked_text != original_text:
            raise AcceptError("the committed project plan changed before the project commit; retry")
        try:
            claim_token = _board.reserve_completion(
                plan_path,
                row_id,
                owner,
                expected_plan=plan_token,
            )
        except _board.BoardError as exc:
            raise AcceptError(f"the owned claim changed before its proof could land: {exc}") from exc
        index_entry = git_completed(
            repo, "ls-files", "--stage", "--", plan_pathspec
        ).stdout.strip()
        publication = atomic_write_text(plan_path, updated_text)
        pathspecs = [plan_pathspec]
        if publication is not None:
            pathspecs.append(
                (plan_relative.parent / "PLAN.d").as_posix()
            )
        try:
            added = git_completed(repo, "add", "--", *pathspecs)
            committed = (
                git_completed(
                    repo,
                    "-c",
                    "core.hooksPath=/dev/null",
                    "-c",
                    "commit.gpgSign=false",
                    "-c",
                    "maintenance.autoDetach=false",
                    "-c",
                    "gc.autoDetach=false",
                    "commit",
                    "--only",
                    "-m",
                    f"shadow accept: {row_id} proven in a clean checkout",
                    "--",
                    *pathspecs,
                )
                if added.returncode == 0
                else added
            )
        except AcceptError:
            if publication is not None:
                restore_tree_publication(repo, plan_path, pathspecs, publication)
            else:
                restore_plan_index(repo, plan_path, plan_pathspec, original_text, index_entry)
            raise
        if added.returncode or committed.returncode:
            if publication is not None:
                restore_tree_publication(repo, plan_path, pathspecs, publication)
            else:
                restore_plan_index(repo, plan_path, plan_pathspec, original_text, index_entry)
            raise AcceptError("the acceptance commit could not be created; the plan was restored")
        try:
            completed_token, completed_bytes = _board.committed_plan_snapshot(plan_path)
            completed_text = completed_bytes.decode("utf-8")
        except (_board.BoardError, OSError, UnicodeError) as exc:
            raise AcceptError(
                f"the project proof committed, but its exact plan bytes could not be frozen: {exc}"
            ) from exc
        if completed_text != updated_text:
            raise AcceptError("the project proof committed different plan bytes; root claim stays open")
        return claim_token, completed_token, completed_text


def proof_passes(worktree: Path, proof: list[str], timeout_seconds: int) -> bool:
    try:
        result = subprocess.run(
            proof,
            cwd=worktree,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
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


def lead_review_passes(
    worktree: Path,
    proof: list[str],
    timeout_seconds: int,
    proof_directory: Path = Path("."),
) -> bool:
    if not proof_passes(worktree / proof_directory, proof, timeout_seconds):
        return False
    status = git_completed(
        worktree,
        "status",
        "--porcelain=v1",
        "--ignored=matching",
        "--untracked-files=all",
    )
    if status.returncode:
        return False
    return not status.stdout.strip()


def remove_review_worktree(repo: Path, destination: Path) -> None:
    status = git_completed(
        destination,
        "status",
        "--porcelain=v1",
        "--ignored=matching",
        "--untracked-files=all",
        timeout=15,
    )
    if status.returncode or status.stdout:
        raise AcceptError(
            "lead review checkout carries tracked, untracked, ignored, or submodule state; "
            "it was retained for inspection"
        )
    removed = git_completed(
        repo,
        "worktree",
        "remove",
        "--",
        str(destination),
        timeout=30,
    )
    if removed.returncode:
        raise AcceptError("clean lead review checkout could not be retired without force")
    pruned = git_completed(repo, "worktree", "prune", timeout=15)
    if pruned.returncode:
        raise AcceptError("retired lead review checkout could not be pruned")


def accept_local_plan(
    repo: Path,
    plan_path: Path,
    row_id: str,
    owner: str,
    timeout_seconds: int,
) -> int:
    """Accept a private PLAN while reviewing its declared source checkout.

    Local plans are the machine authority, so their flip is an atomic local
    replacement, not a source commit.  Their cmd proofs remain source code:
    run those only from a detached clean checkout of the explicit ``--repo``.
    """
    try:
        plan_token, plan_bytes = _board.frozen_plan_snapshot(plan_path)
        plan_text = plan_bytes.decode("utf-8")
    except (_board.BoardError, OSError, UnicodeError) as exc:
        raise AcceptError(f"local plan cannot be frozen before proof: {exc}") from exc
    _, _, state, proof, needs = find_row(plan_text, row_id)
    claim = owned_claim(_board.entity_state(plan_path), row_id, owner)
    if state == "completed":
        if not proof.startswith("cmd "):
            raise AcceptError("the completed local row was not accepted from a cmd proof")
        argv = proof_argv(proof[4:])
        if not _board.has_accept_proof_receipt(plan_text, row_id, argv):
            raise AcceptError("the local row is completed without a matching accept proof")
        refuse_lint_blocked_plan(plan_text, plan_path, proof_root=repo, row_id=row_id)
        if claim is not None:
            parsed = _amp._parse(plan_text)
            parsed["claimed"] = set()
            _board.release(
                plan_path,
                row_id,
                owner=owner,
                reason="completed",
                resumes=_amp._candidate_ids(parsed),
                expected_plan=plan_token,
                expected_text=plan_text,
                expected_claim=claim,
            )
        print(f"accepted {row_id}: local completion already proven; root claim reconciled")
        return 0
    if claim is None:
        raise AcceptError(f"{row_id} is not claimed; run shadow throw before accepting it")
    blocked_by = unmet_needs(plan_text, needs)
    if blocked_by:
        raise AcceptError(f"{row_id} still needs {', '.join(blocked_by)}")
    challenged = contradiction_challenges(plan_text, row_id, needs)
    if challenged:
        raise AcceptError(f"{row_id} is under a written challenge: {challenged[0]}")
    if not proof.startswith("cmd "):
        raise AcceptError("only cmd proofs are machine-rerunnable")
    argv = proof_argv(proof[4:])
    if not argv:
        raise AcceptError("the proof command is empty")
    offenders = _shell_operators(proof[4:])
    if offenders:
        raise AcceptError(f"the proof passes {' '.join(offenders)} as literal shell operators")
    head = git_completed(repo, "rev-parse", "HEAD")
    if head.returncode or not head.stdout.strip():
        raise AcceptError("source checkout HEAD cannot be read")
    pool = repo.parent / f"{repo.name}-shadow-accept"
    pool.mkdir(exist_ok=True)
    git_completed(repo, "worktree", "prune", timeout=15)
    review = create_lead_review_worktree(repo, pool, row_id.lstrip("~"), head.stdout.strip())
    try:
        issue = script_operand_issue(argv, review)
        if issue:
            raise AcceptError(f"the proof's {issue}; nothing was changed")
        passed = lead_review_passes(review, argv, timeout_seconds)
    finally:
        remove_review_worktree(repo, review)
        try:
            pool.rmdir()
        except OSError:
            pass
    if not passed:
        raise AcceptError("the proof did not pass in a clean source checkout; nothing was changed")
    with _board.project_lock(plan_path):
        fresh_token, fresh_bytes = _board.frozen_plan_snapshot(plan_path)
        try:
            fresh_text = fresh_bytes.decode("utf-8")
        except UnicodeError as exc:
            raise AcceptError("local plan is not UTF-8") from exc
        if fresh_token != plan_token or fresh_text != plan_text:
            raise AcceptError("the local plan changed while the proof ran; retry")
        _, _, fresh_state, fresh_proof, fresh_needs = find_row(fresh_text, row_id)
        if fresh_state != state or fresh_proof != proof:
            raise AcceptError("the local row changed while the proof ran; retry")
        if unmet_needs(fresh_text, fresh_needs) or contradiction_challenges(fresh_text, row_id, fresh_needs):
            raise AcceptError("the local row is no longer ready; nothing was changed")
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        updated = completed_plan_text(fresh_text, row_id, argv, stamp)
        refuse_lint_blocked_plan(updated, plan_path, proof_root=repo, row_id=row_id)
        claim_token = _board.reserve_completion(
            plan_path,
            row_id,
            owner,
            expected_plan=fresh_token,
        )
        atomic_write_text(plan_path, updated)
        completed_token, completed_bytes = _board.frozen_plan_snapshot(plan_path)
        completed_text = completed_bytes.decode("utf-8")
        parsed = _amp._parse(completed_text)
        parsed["claimed"] = set()
        _board.release(
            plan_path,
            row_id,
            owner=owner,
            reason="completed",
            resumes=_amp._candidate_ids(parsed),
            expected_plan=completed_token,
            expected_text=completed_text,
            expected_claim=claim_token,
        )
    print(f"accepted {row_id}: proof passed in a clean source checkout; local row flipped with its PROOF line")
    return 0


def unmet_needs(plan_text: str, needs: str) -> list[str]:
    """Needs-targets in `needs` that are not completed anywhere in the plan.

    The grammar calls this readiness — "a task is ready when it is pending and
    every needs-target is completed" — and `shadow throw` enforced it while
    accept did not, so a row could be flipped to completed over a dependency
    still sitting at pending and lint would call the result clean.
    """
    completed = {
        row.group("id")
        for line in plan_text.splitlines()
        if (row := ROW_LINE_RE.match(line)) is not None and row.group("state") == "completed"
    }
    return [ref for ref in NEEDS_REF_RE.findall(needs) if ref not in completed]


def contradiction_challenges(plan_text: str, row_id: str, needs: str) -> list[str]:
    """Open ## Contradictions entries naming the row or its needs-ancestry.

    A dependent must not flip while its foundation is under a written,
    undelivered challenge — the one coordination behavior that takes three
    roles (challenger, owner, dependent), so no disjoint-claim run ever
    exercises it and only this gate can. Ancestry is the transitive closure
    of needs:, so a challenge two levels down still holds the flip.
    """
    needs_of: dict[str, str] = {}
    for line in plan_text.splitlines():
        row = ROW_LINE_RE.match(line)
        if row is not None:
            fields = dict(FIELD_RE.findall(row.group("tail") or ""))
            needs_of[row.group("id")] = fields.get("needs", "")
    ancestry = {row_id}
    frontier = set(NEEDS_REF_RE.findall(needs))
    while frontier:
        member = frontier.pop()
        if member in ancestry:
            continue
        ancestry.add(member)
        frontier.update(NEEDS_REF_RE.findall(needs_of.get(member, "")))
    hits: list[str] = []
    inside = False
    for line in plan_text.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
            inside = heading == "Contradictions" or heading.startswith("Contradictions ")
            continue
        if not inside or not line.startswith("- "):
            continue
        if line.strip().lower().startswith("- none"):
            continue
        if any(member in line for member in ancestry):
            hits.append(line.strip())
    return hits


def find_row(plan_text: str, row_id: str) -> tuple[int, str, str, str, str]:
    """Return (line index, line, state, proof, needs) for the row carrying row_id.

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
    fields = dict(pairs)
    proof = fields.get("proof", "").strip()
    if not proof:
        raise AcceptError("the row has no proof field")
    return index, line, row.group("state"), proof, fields.get("needs", "").strip()


def owned_claim(state: dict | None, row_id: str, owner: str) -> dict | None:
    """Return one exact owned claim, refusing another seat before any proof runs."""
    if state is None or state["entity"] is None:
        raise AcceptError(
            "this entity is not registered on the computer board; "
            "claim it with shadow throw before accepting work"
        )
    claim = next((item for item in state["claims"] if item["row"] == row_id), None)
    if claim is not None and claim["owner"] != owner:
        raise AcceptError(f"{row_id} is claimed by {claim['owner']}, not {owner}")
    return claim


def completed_plan_text(
    plan_text: str,
    row_id: str,
    argv: list[str],
    stamp: str,
) -> str:
    """Build the only accepted row flip and its canonical Progress receipt."""
    index, _, state, _, _ = find_row(plan_text, row_id)
    if state == "completed":
        raise AcceptError(f"{row_id} is already completed")
    plan_lines = plan_text.splitlines(keepends=True)
    plan_lines[index] = re.sub(
        r"^- \[[a-z_]+\]", "- [completed]", plan_lines[index], count=1
    )
    updated = "".join(plan_lines)
    heading = PROGRESS_HEADING_RE.search(updated)
    if heading is None:
        raise AcceptError("the plan has no Progress section")
    proof_line = (
        f"- {stamp} {row_id} PROOF {shlex.join(argv)} -> pass (accept)\n"
    )
    next_heading = updated.find("\n## ", heading.end())
    if next_heading == -1:
        return updated.rstrip() + "\n" + proof_line
    return updated[: next_heading + 1] + proof_line + updated[next_heading + 1 :]


def _receipt_stamps(plan_text: str, row_id: str, argv: list[str]) -> list[str]:
    expected = shlex.join(argv)
    stamps: list[str] = []
    for line in _board.section_lines(plan_text, "Progress"):
        receipt = _grammar.progress_proof_receipt(line)
        match = _grammar.PROOF_RECEIPT_RE.match(line)
        if (
            receipt is not None
            and match is not None
            and receipt == (row_id, expected, "pass (accept)")
        ):
            stamps.append(match.group("ts"))
    return stamps


def _git_blob_for_bytes(repo: Path, content: bytes) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "hash-object", "--stdin"],
            input=content,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AcceptError("interrupted completion bytes could not be inspected") from exc
    if result.returncode:
        raise AcceptError("interrupted completion bytes could not be inspected")
    return result.stdout.decode("ascii", errors="strict").strip()


def _exact_interrupted_completion(
    head_text: str,
    candidate_text: str,
    row_id: str,
) -> bool:
    """True only for the byte-exact journal written by a killed accept."""
    try:
        _, _, state, proof, _ = find_row(head_text, row_id)
        if state == "completed" or not proof.startswith("cmd "):
            return False
        argv = proof_argv(proof[4:])
        before = _receipt_stamps(head_text, row_id, argv)
        after = _receipt_stamps(candidate_text, row_id, argv)
        extra = list(after)
        for stamp in before:
            extra.remove(stamp)
        return (
            len(extra) == 1
            and candidate_text == completed_plan_text(head_text, row_id, argv, extra[0])
        )
    except (AcceptError, ValueError):
        return False


OBJECT_DIGEST_RE = re.compile(r"[0-9a-f]{64}")


def _interrupted_tree_additions(repo: Path, tree_relative: str) -> list[str]:
    """The object digests an interrupted tree accept added under PLAN.d, or refuse."""
    status = git_completed(
        repo, "status", "--porcelain=v1", "--untracked-files=all", "--", tree_relative
    )
    if status.returncode:
        raise AcceptError(
            "interrupted completion object tree could not be read; its bytes were preserved"
        )
    tree_parts = Path(tree_relative).parts
    digests: list[str] = []
    for line in status.stdout.splitlines():
        if not line.strip():
            continue
        code, path = line[:2], line[3:]
        parts = Path(path).parts if code in {"??", "A ", "AM"} else ()
        if (
            len(parts) != len(tree_parts) + 4
            or parts[: len(tree_parts)] != tree_parts
            or parts[-4] != "objects"
            or parts[-3] != "sha256"
            or OBJECT_DIGEST_RE.fullmatch(parts[-1]) is None
            or parts[-2] != parts[-1][:2]
        ):
            raise AcceptError(
                "interrupted completion changed its object tree unexpectedly; "
                "its bytes were preserved"
            )
        digests.append(parts[-1])
    return digests


def committed_or_recovered_snapshot(
    plan_path: Path,
    row_id: str,
) -> tuple[dict[str, str], bytes]:
    """Freeze clean HEAD, repairing only Shadow's exact interrupted write journal."""
    try:
        return _board.committed_plan_snapshot(plan_path)
    except _board.BoardError as refusal:
        refusal_error = refusal
    with _board.project_lock(plan_path):
        try:
            return _board.committed_plan_snapshot(plan_path)
        except _board.BoardError:
            pass
        try:
            token, head_bytes = _board.head_plan_snapshot(plan_path)
            candidate_bytes = plan_path.read_bytes()
            # Codex (PR #469, P1): a partitioned plan's roots are manifests, not
            # plan text. Judging the journal on those bytes rejected every tree
            # recovery and left the authority wedged, so materialize both
            # generations through the object store first.
            head_snapshot = _plan_store.snapshot_of_root(plan_path, head_bytes)
            candidate_snapshot = _plan_store.snapshot_of_root(plan_path, candidate_bytes)
            head_text = head_snapshot.materialize().decode("utf-8")
            candidate_text = candidate_snapshot.materialize().decode("utf-8")
        except (_board.BoardError, _plan_store.PlanStoreError, OSError, UnicodeError):
            raise refusal_error
        if not _exact_interrupted_completion(head_text, candidate_text, row_id):
            raise refusal_error

        repo = Path(token["repo"])
        relative = token["relative"]
        tree_relative = (Path(relative).parent / "PLAN.d").as_posix()
        partitioned = head_snapshot.is_tree or candidate_snapshot.is_tree
        staged = git_completed(repo, "ls-files", "--stage", "--", relative)
        head_entry = git_completed(repo, "ls-tree", "HEAD", "--", relative)
        staged_lines = [line for line in staged.stdout.splitlines() if line.strip()]
        head_lines = [line for line in head_entry.stdout.splitlines() if line.strip()]
        if staged.returncode or head_entry.returncode or len(staged_lines) != 1 or len(head_lines) != 1:
            raise AcceptError(
                "interrupted completion has an ambiguous index; its bytes were preserved"
            )
        staged_parts = staged_lines[0].split(maxsplit=3)
        head_parts = head_lines[0].split(maxsplit=3)
        if (
            len(staged_parts) != 4
            or len(head_parts) != 4
            or staged_parts[2] != "0"
            or staged_parts[0] != head_parts[0]
            or head_parts[2] != token["blob"]
            or staged_parts[3] != relative
            or head_parts[3] != relative
        ):
            raise AcceptError(
                "interrupted completion has an unexpected staged plan; its bytes were preserved"
            )
        candidate_blob = _git_blob_for_bytes(repo, candidate_bytes)
        if staged_parts[1] not in {token["blob"], candidate_blob}:
            raise AcceptError(
                "interrupted completion has an unexpected staged plan; its bytes were preserved"
            )
        if partitioned:
            added = _interrupted_tree_additions(repo, tree_relative)
            try:
                _plan_store.restore_exact_root(
                    plan_path,
                    expected_current_root=_plan_store.digest_bytes(candidate_bytes),
                    target_root_bytes=head_bytes,
                )
            except _plan_store.PlanStoreError as exc:
                raise AcceptError(
                    f"interrupted completion could not return to its committed root: {exc}"
                ) from exc
            reset = git_completed(
                repo, "reset", "--quiet", "HEAD", "--", relative, tree_relative
            )
            if reset.returncode:
                raise AcceptError(
                    "interrupted completion index could not be restored; its bytes were preserved"
                )
            try:
                _plan_store.discard_unreachable(plan_path, added)
            except _plan_store.PlanStoreError as exc:
                raise AcceptError(
                    f"interrupted completion objects could not be discarded: {exc}"
                ) from exc
        else:
            if staged_parts[1] == candidate_blob:
                restored = git_completed(
                    repo,
                    "update-index",
                    "--cacheinfo",
                    f"{head_parts[0]},{token['blob']},{relative}",
                )
                if restored.returncode:
                    raise AcceptError(
                        "interrupted completion index could not be restored; "
                        "its bytes were preserved"
                    )
            atomic_write_text(plan_path, head_text)
        try:
            return _board.committed_plan_snapshot(plan_path)
        except _board.BoardError as exc:
            raise AcceptError(
                f"interrupted completion could not return to committed authority: {exc}"
            ) from exc


def publish_completion(
    repo: Path, row_id: str, no_push: bool, summary: str, *, announce: bool = True
) -> int:
    """Make an already-committed completion reachable, including on retry."""
    if no_push:
        print(
            f"accepted {row_id}: {summary} — NOT pushed (--no-push); "
            "the flip is invisible to other seats"
        )
        return 0
    try:
        # Read the two upstream fields separately. Splitting an abbreviated
        # `remote/ref` breaks as soon as the remote name itself contains `/`.
        branch = git_completed(repo, "symbolic-ref", "--short", "HEAD")
        upstream = (
            git_completed(
                repo,
                "for-each-ref",
                "--format=%(upstream:remotename) %(upstream:remoteref)",
                f"refs/heads/{branch.stdout.strip()}",
            )
            if branch.returncode == 0 and branch.stdout.strip()
            else branch
        )
        parts = upstream.stdout.strip().split(" ", 1) if upstream.returncode == 0 else []
        if len(parts) != 2 or not parts[0] or not parts[1]:
            print(
                f"accepted {row_id}: {summary} — local only: this branch has no upstream, "
                "so push it yourself or the flip is invisible to other seats"
            )
            return 0
        remote, remote_ref = parts
        pushed = git_completed(repo, "push", remote, f"HEAD:{remote_ref}")
    except AcceptError as exc:
        print(
            f"shadow accept: {row_id} is flipped and committed locally but the push could "
            f"not be attempted: {exc} — other seats cannot see the completion; push the "
            "PLAN.md commit yourself once Git is reachable.",
            file=sys.stderr,
        )
        return 3
    if pushed.returncode != 0:
        # Name WHERE the flip commit is parked. Accept commits at the STORED
        # plan pointer, which may not be the --repo argument the operator
        # typed — an unnamed location reads as a destroyed commit, and the
        # operator hand-duplicates the flip (measured 2026-08-11).
        where = (
            f"{repo} (branch {branch.stdout.strip()})"
            if branch.returncode == 0 and branch.stdout.strip()
            else str(repo)
        )
        print(
            f"shadow accept: {row_id} is flipped and committed in {where} but the push was "
            "REJECTED — other seats cannot see the completion. On a protected trunk, "
            "land that PLAN.md commit through a pull request; on a race, pull there and push again.",
            file=sys.stderr,
        )
        return 3
    if announce:
        print(f"accepted {row_id}: {summary} and pushed to {remote} {remote_ref}")
    return 0


def remote_completion_receipt(
    repo: Path,
    plan_path: Path,
    row_id: str,
    owner: str,
) -> dict | None:
    """Authenticate one acquired journal, including from a detached retry."""
    state = _board.entity_state(plan_path, exact_on_conflict=True)
    if state is None or state["entity"] is None or state["project"] is None:
        raise AcceptError("remote completion recovery cannot resolve its board entity")
    try:
        relative = plan_path.relative_to(repo).as_posix()
        active = _remote_claim.discover_active(
            repo,
            entity=state["entity"]["id"],
            project=state["project"]["id"],
            rows=[row_id],
            relative=relative,
            recover_detached=True,
        )
    except (ValueError, _remote_claim.RemoteClaimError) as exc:
        raise AcceptError(
            "the completed row's remote claim could not be authenticated"
        ) from exc
    if not active:
        return None
    if len(active) != 1:
        raise AcceptError("the completed row has conflicting remote claims")
    receipt = active[0]
    if receipt["owner"] != owner:
        raise AcceptError(
            f"{row_id} has a remote claim owned by {receipt['owner']}, not {owner}"
        )
    return receipt


def ensure_completion_published(
    repo: Path,
    row_id: str,
    plan_token: dict[str, str],
    plan_text: str,
    summary: str,
) -> int | None:
    """Publish on a tracking branch or authenticate an already-merged retry."""
    tracking = _remote_claim.uses_origin_upstream(repo)
    try:
        snapshot = _remote_claim.published_plan_snapshot(repo, plan_token)
    except _remote_claim.RemoteClaimError as exc:
        if tracking:
            result = publish_completion(repo, row_id, False, summary, announce=False)
            return result or None
        raise AcceptError(
            "completion publication could not be authenticated; remote claim retained"
        ) from exc
    if snapshot is None:
        if tracking:
            result = publish_completion(repo, row_id, False, summary, announce=False)
            return result or None
        raise AcceptError(
            "completion is not published on the configured origin; remote claim retained"
        )
    published_bytes, default_tip = snapshot
    try:
        published_text = published_bytes.decode("utf-8")
        _, _, local_state, local_proof, _ = find_row(plan_text, row_id)
    except (UnicodeError, AcceptError) as exc:
        raise AcceptError(
            "current origin default PLAN no longer carries the completed row and "
            "matching accept proof; remote claim retained"
        ) from exc
    if local_state != "completed" or not local_proof.startswith("cmd "):
        raise AcceptError(
            "current origin default PLAN no longer carries the completed row and "
            "matching accept proof; remote claim retained"
        )
    if completion_matches(published_text, row_id, local_proof):
        return None
    if any(
        row.group("id") == row_id
        for line in published_text.splitlines()
        if (row := ROW_LINE_RE.match(line)) is not None
    ):
        raise AcceptError(
            "current origin default PLAN carries a conflicting live row; "
            "remote claim retained"
        )
    if completion_matches_lifecycle_archive(
        repo,
        published_text,
        plan_token,
        default_tip,
        row_id,
        local_proof,
    ):
        return None
    raise AcceptError(
        "current origin default PLAN no longer carries the completed row and "
        "matching accept proof; remote claim retained"
    )


def completion_matches(
    text: str,
    row_id: str,
    local_proof: str,
    *,
    archived: bool = False,
) -> bool:
    """Whether one text carries the exact accepted command completion."""
    matching = [
        row
        for line in text.splitlines()
        if (row := ROW_LINE_RE.match(line)) is not None and row.group("id") == row_id
    ]
    if not matching:
        return False
    _, _, state, proof, _ = find_row(text, row_id)
    if not proof.startswith("cmd "):
        raise AcceptError("published completion proof is not command-classed")
    argv = proof_argv(proof[4:])
    return (
        state == "completed"
        and proof == local_proof
        and (
            has_archive_accept_proof_receipt(text, row_id, argv)
            if archived
            else _board.has_accept_proof_receipt(text, row_id, argv)
        )
    )


def has_archive_accept_proof_receipt(
    text: str,
    row_id: str,
    argv: list[str],
) -> bool:
    """Read lifecycle's non-executable Exact Progress receipt section."""
    active = False
    expected = (shlex.join(argv), "pass (accept)")
    for line in text.splitlines():
        if line.startswith("## "):
            active = line.strip() == "## Exact Progress receipts"
            continue
        if not active:
            continue
        receipt = _board.progress_proof_receipt(line)
        if receipt is not None and receipt[0] == row_id and receipt[1:] == expected:
            return True
    return False


def completion_matches_lifecycle_archive(
    repo: Path,
    published_text: str,
    plan_token: dict[str, str],
    default_tip: str,
    row_id: str,
    local_proof: str,
) -> bool:
    """Authenticate an accepted row moved by current Shadow lifecycle."""
    plan_parent = PurePosixPath(plan_token["relative"]).parent
    matches = 0
    for line in published_text.splitlines():
        marker = LIFECYCLE_ARCHIVE_RE.match(line)
        if marker is None:
            continue
        archive_path = PurePosixPath(marker.group("path"))
        if archive_path.is_absolute() or any(
            part in {"", ".", ".."} for part in archive_path.parts
        ):
            raise AcceptError("published lifecycle archive path is unsafe")
        relative = (plan_parent / archive_path).as_posix()
        try:
            archive_bytes = _remote_claim.published_file_bytes(
                repo, default_tip, relative
            )
        except _remote_claim.RemoteClaimError as exc:
            raise AcceptError("published lifecycle archive could not be authenticated") from exc
        if archive_bytes is None:
            raise AcceptError("published lifecycle archive is missing")
        expected_header = (
            f"<!-- shadow:archive:v1:{marker.group('slug')}:"
            f"sha256:{marker.group('digest')}:cas:{marker.group('cas')}:"
            f"head:{marker.group('head')}:blob:{marker.group('blob')}:"
            f"successor:{marker.group('successor')} -->\n"
        ).encode("ascii")
        if not archive_bytes.startswith(expected_header):
            raise AcceptError("published lifecycle archive identity does not match its marker")
        body = archive_bytes[len(expected_header):]
        if hashlib.sha256(body).hexdigest() != marker.group("digest"):
            raise AcceptError("published lifecycle archive digest does not match its marker")
        try:
            archive_text = body.decode("utf-8")
        except UnicodeError as exc:
            raise AcceptError("published lifecycle archive is not valid UTF-8") from exc
        if completion_matches(archive_text, row_id, local_proof, archived=True):
            matches += 1
    if matches > 1:
        raise AcceptError("published lifecycle archives duplicate the completed row")
    return matches == 1


def claim_from_remote_receipt(receipt: dict) -> dict:
    return {
        "entity": receipt["entity"],
        "row": receipt["row"],
        "owner": receipt["owner"],
        **receipt["claim"],
    }


def completion_reservation_matches(local: dict, remote: dict) -> bool:
    """Allow only the bounded local lease extension made while accepting."""
    identity = ("entity", "row", "owner", "claimed_at", "recovery")
    fields = (*identity, "return_by")
    return (
        all(
            isinstance(local.get(key), str) and isinstance(remote.get(key), str)
            for key in fields
        )
        and all(local.get(key) == remote.get(key) for key in identity)
        and local.get("return_by", "") >= remote.get("return_by", "")
    )


def transition_remote_completion(
    repo: Path,
    plan_path: Path,
    row_id: str,
    owner: str,
    plan_token: dict[str, str],
    claim: dict,
) -> None:
    state = _board.entity_state(plan_path, exact_on_conflict=True)
    remote = _remote_claim.transition(
        repo,
        entity=claim["entity"],
        row=row_id,
        owner=owner,
        project=state["project"]["id"],
        plan_token=plan_token,
        claim=claim,
        state="completed",
        reason="completed",
        recover_detached=True,
    )
    if remote is None or remote["status"] != "acquired":
        raise AcceptError(
            "completion is published but its remote claim transition is ambiguous; "
            "exact local claim retained when present"
        )


def finalize_completion(
    repo: Path,
    plan_path: Path,
    row_id: str,
    owner: str,
    claim: dict,
    plan_token: dict[str, str],
    plan_text: str,
    resumes: list[str],
    no_push: bool,
    summary: str,
) -> int:
    """Publish authority, close its remote journal, then release locally."""
    receipt = remote_completion_receipt(repo, plan_path, row_id, owner)
    managed = _remote_claim.uses_origin_upstream(repo) or receipt is not None
    if no_push and managed:
        return publish_completion(repo, row_id, True, summary)
    if managed:
        published = ensure_completion_published(
            repo, row_id, plan_token, plan_text, summary
        )
        if published:
            return published
        remote_claim = claim_from_remote_receipt(receipt) if receipt is not None else claim
        if receipt is not None and not completion_reservation_matches(claim, remote_claim):
            raise AcceptError(
                "local and remote completion claims disagree; exact local claim retained"
            )
        transition_remote_completion(
            repo, plan_path, row_id, owner, plan_token, remote_claim
        )
    _board.release(
        plan_path,
        row_id,
        owner=owner,
        reason="completed",
        resumes=resumes,
        expected_plan=plan_token,
        expected_text=plan_text,
        expected_claim=claim,
    )
    if managed:
        print(f"accepted {row_id}: {summary}; published and remote claim completed")
        return 0
    return publish_completion(repo, row_id, no_push, summary)


def finalize_completed_retry_without_local_claim(
    repo: Path,
    plan_path: Path,
    row_id: str,
    owner: str,
    plan_token: dict[str, str],
    plan_text: str,
    no_push: bool,
    summary: str,
) -> int:
    receipt = remote_completion_receipt(repo, plan_path, row_id, owner)
    if receipt is None:
        return publish_completion(repo, row_id, no_push, summary)
    if no_push:
        return publish_completion(repo, row_id, True, summary)
    published = ensure_completion_published(
        repo, row_id, plan_token, plan_text, summary
    )
    if published:
        return published
    transition_remote_completion(
        repo,
        plan_path,
        row_id,
        owner,
        plan_token,
        claim_from_remote_receipt(receipt),
    )
    print(f"accepted {row_id}: {summary}; published and remote claim completed")
    return 0


def main(argv: list[str] | None = None) -> int:
    _remote_claim.sanitize_process_git_env()
    parser = argparse.ArgumentParser(prog="shadow accept", description=__doc__)
    location = parser.add_mutually_exclusive_group(required=True)
    location.add_argument("--repo", type=Path)
    location.add_argument(
        "--entity",
        help="computer-board entity id for path-free completed-claim recovery",
    )
    parser.add_argument("--row", required=True)
    parser.add_argument("--by", required=True, help="stable owner of the existing claim")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--no-push", action="store_true",
                        help="commit without pushing (an unpushed flip is invisible to other seats)")
    args = parser.parse_args(argv)
    row_id = args.row.strip()
    try:
        if ROW_ID_RE.fullmatch(row_id) is None:
            raise AcceptError("row must be a ~hash id, four base36 chars")
        try:
            owner = _board.validate_owner(args.by)
        except _board.BoardError as exc:
            raise AcceptError(f"--by is unsafe: {exc}") from exc
        try:
            if args.entity:
                resolved = _board.resolve_entity(args.entity)
                if resolved is None or resolved["plan"] is None:
                    raise _board.BoardError(
                        "this entity is not registered on the computer board"
                    )
                plan_path = resolved["plan"]
                if _board.is_local_plan(plan_path):
                    raise _board.BoardError(
                        "--entity recovery requires a Git-backed project plan"
                    )
            else:
                repo = args.repo.resolve()
                source_top = git_completed(repo, "rev-parse", "--show-toplevel")
                if source_top.returncode or not source_top.stdout.strip():
                    raise AcceptError("--repo must name a Git source checkout")
                requested_plan = repo / "PLAN.md"
                source_root = Path(source_top.stdout.strip()).resolve()
                # A machine-local authority deliberately supersedes the source
                # checkout's PLAN.md. Worktrees do not necessarily share the
                # canonical repository directory name, so resolve through the
                # registered origin identity before treating a present source
                # plan as the entity authority.
                local_plan = (
                    _board.local_plan_for_repo(repo)
                    or _board.local_plan_for_repo(source_root)
                )
                if local_plan is not None:
                    local_state = _board.entity_state(local_plan)
                    owned_claim(local_state, row_id, owner)
                    return accept_local_plan(
                        source_root,
                        local_plan,
                        row_id,
                        owner,
                        args.timeout_seconds,
                    )
                state = _board.entity_state(requested_plan)
                owned_claim(state, row_id, owner)
                plan_path = _board.canonical_plan(requested_plan, repair_missing=True)
                state = _board.entity_state(plan_path)
        except _board.BoardError as exc:
            raise AcceptError(f"the computer board's project pointer is unusable: {exc}") from exc
        top = git_completed(plan_path.parent, "rev-parse", "--show-toplevel")
        if top.returncode or not top.stdout.strip():
            raise AcceptError("the canonical project plan is not inside a Git repository")
        repo = Path(top.stdout.strip()).resolve()
        try:
            plan_relative = plan_path.relative_to(repo)
        except ValueError as exc:
            raise AcceptError("the canonical entity plan is outside its Git repository") from exc
        if git_completed(repo, "ls-files", "-u", "--", str(plan_relative)).stdout.strip():
            raise AcceptError("PLAN.md has unresolved merge conflicts; resolve them first")
        try:
            plan_token, plan_bytes = committed_or_recovered_snapshot(plan_path, row_id)
            plan_text = plan_bytes.decode("utf-8")
        except (_board.BoardError, AcceptError, OSError, UnicodeError) as exc:
            raise AcceptError(f"plan must be one committed authority before proof: {exc}") from exc
        _, row_line, state, proof, needs = find_row(plan_text, row_id)
        claim = owned_claim(_board.entity_state(plan_path), row_id, owner)
        if state == "completed":
            if git_completed(
                repo, "status", "--porcelain", "--", str(plan_relative)
            ).stdout.strip():
                raise AcceptError(
                    "the completed row or its proof is not committed; root claim stays open"
                )
            if not proof.startswith("cmd "):
                raise AcceptError("the completed row was not accepted from a cmd proof")
            completed_argv = proof_argv(proof[4:])
            if not _board.has_accept_proof_receipt(
                plan_text, row_id, completed_argv
            ):
                raise AcceptError("the row is completed without a matching accept proof")
            refuse_lint_blocked_plan(plan_text, plan_path, row_id=row_id)
            if claim is not None:
                parsed = _amp._parse(plan_text)
                parsed["claimed"] = set()
                try:
                    with _board.project_lock(plan_path):
                        return finalize_completion(
                            repo,
                            plan_path,
                            row_id,
                            owner,
                            claim,
                            plan_token,
                            plan_text,
                            _amp._candidate_ids(parsed),
                            args.no_push,
                            "completion already proven; root claim reconciled",
                        )
                except (_board.BoardError, AcceptError) as exc:
                    raise AcceptError(
                        f"the completed row's root claim could not reconcile: {exc}"
                    ) from exc
            return finalize_completed_retry_without_local_claim(
                repo,
                plan_path,
                row_id,
                owner,
                plan_token,
                plan_text,
                args.no_push,
                "completion already proven; root claim reconciled",
            )
        if claim is None:
            raise AcceptError(f"{row_id} is not claimed; run shadow throw before accepting it")
        blocked_by = unmet_needs(plan_text, needs)
        if blocked_by:
            raise AcceptError(
                f"{row_id} still needs {', '.join(blocked_by)} — a row is ready only when "
                "every needs-target is completed; finish those first"
            )
        challenged = contradiction_challenges(plan_text, row_id, needs)
        if challenged:
            raise AcceptError(
                f"{row_id} or its needs-ancestry is under a written challenge and must not "
                f"flip silently; resolve the Contradictions entry first: {challenged[0]}"
            )
        if not proof.startswith("cmd "):
            kind = proof.split(" ", 1)[0]
            raise AcceptError(
                f"only cmd proofs are machine-rerunnable; this row is {kind}-classed — "
                "re-observe it yourself and append the PROOF line with the flip"
            )
        argv_proof = proof_argv(proof[4:])
        if not argv_proof:
            raise AcceptError("the proof command is empty")
        # The same refusal lint makes, made here too. Accept runs the proof
        # with NO shell, so `&&`, `|`, `;` and `$(...)` reach argv[0] as
        # literal arguments: `cmd echo done && shadow --version` would run
        # `echo`, exit 0, and flip the row while `shadow` never ran. Lint alone
        # is not enough — a plan can reach accept without lint having run, and
        # two gates that disagree are how the false green got here.
        offenders = _shell_operators(proof[4:])
        if offenders:
            raise AcceptError(
                f"the proof passes {' '.join(offenders)} to `{argv_proof[0]}` as a literal "
                "argument — accept runs proofs without a shell, so the rest of the command "
                f"would never execute. Wrap it: cmd bash -c '<the whole command>'"
            )
        head = plan_token["head"]
        pool = repo.parent / f"{repo.name}-shadow-accept"
        pool.mkdir(exist_ok=True)
        # A crashed prior run can leave a registered-but-deleted worktree that
        # would wedge every future accept of this row; prune is always safe.
        git_completed(repo, "worktree", "prune", timeout=15)
        review = create_lead_review_worktree(repo, pool, row_id.lstrip("~"), head)
        try:
            script_issue = script_operand_issue(
                argv_proof,
                review / plan_relative.parent,
            )
            if script_issue:
                raise AcceptError(f"the proof's {script_issue}; nothing was changed")
            passed = lead_review_passes(
                review,
                argv_proof,
                args.timeout_seconds,
                plan_relative.parent,
            )
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
            fresh_token, fresh_bytes = _board.committed_plan_snapshot(plan_path)
            plan_text = fresh_bytes.decode("utf-8")
        except (_board.BoardError, OSError, UnicodeError) as exc:
            raise AcceptError(f"plan cannot be frozen after the proof: {exc}") from exc
        if fresh_token != plan_token:
            raise AcceptError("the committed project plan changed while the proof ran; retry")
        _, _, fresh_state, fresh_proof, fresh_needs = find_row(plan_text, row_id)
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
        # Readiness is re-decided against the plan as it stands now, not the
        # pre-run snapshot: a dependency added to this row, or a needs-target
        # reopened, while the proof ran means the row is no longer ready and
        # the flip would record a completion the grammar forbids.
        blocked_now = unmet_needs(plan_text, fresh_needs)
        if blocked_now:
            raise AcceptError(
                f"{row_id} still needs {', '.join(blocked_now)} — its readiness changed while "
                "the proof ran; nothing was changed"
            )
        challenged_now = contradiction_challenges(plan_text, row_id, fresh_needs)
        if challenged_now:
            raise AcceptError(
                f"{row_id} or its needs-ancestry was challenged in writing while the proof "
                f"ran; nothing was changed — resolve the Contradictions entry first: {challenged_now[0]}"
            )
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        updated = completed_plan_text(plan_text, row_id, argv_proof, stamp)
        refuse_lint_blocked_plan(updated, plan_path, row_id=row_id)
        completed_plan = _amp._parse(updated)
        completed_plan["claimed"] = set()
        resumes = _amp._candidate_ids(completed_plan)
        try:
            claim_token, completed_token, completed_text = commit_completed_plan(
                repo,
                plan_path,
                plan_relative,
                row_id,
                owner,
                plan_token,
                plan_text,
                updated,
                resumes,
            )
            return finalize_completion(
                repo,
                plan_path,
                row_id,
                owner,
                claim_token,
                completed_token,
                completed_text,
                resumes,
                args.no_push,
                "proof passed in a clean checkout; row flipped with its PROOF line",
            )
        except _board.BoardError as exc:
            raise AcceptError(
                f"the project proof landed, but the root claim could not close: {exc}; "
                "repair the root board before taking more work"
            ) from exc
    except AcceptError as exc:
        print(f"shadow accept: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
