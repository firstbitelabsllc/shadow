#!/usr/bin/env python3
"""Rerun one owned checkpoint's proof from a detached checkout, then flip it.

This is the only code path that flips a `cmd`-proven checkpoint to completed.
It parses the entity PLAN.md, finds the row by its ~hash id, reruns a
``cmd``-classed proof with a detached checkout of HEAD as its initial working
directory, and — only on success — rewrites the row's state and appends the
paired PROOF Progress line in one commit. This is a source-state boundary, not
filesystem containment: the trusted proof process can still change directory or
access other paths. ``--entity`` plus ``--repo`` selects one registered
machine-local plan. A declared Brief ``Origin:`` must equal that checkout's
normalized identity; the first local-only accept promotes an opaque path-free
identity into ``Origin:``. The path-free ``--entity`` form reconciles an
authenticated, published ``cmd`` completion whose remote journal remains
acquired and still refuses a local plan. ``read`` and ``gate`` proofs are
person/agent judgments and are refused here on purpose.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Iterator


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import shadow_root_board as _board  # noqa: E402
import shadow_remote_claim as _remote_claim  # noqa: E402
import shadow_git as _shadow_git  # noqa: E402
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

_HOST_SPEC = importlib.util.spec_from_file_location(
    "shadow_accept_host", ROOT / "scripts" / "shadow-host.py"
)
_host = importlib.util.module_from_spec(_HOST_SPEC)
sys.modules.setdefault("shadow_accept_host", _host)
_HOST_SPEC.loader.exec_module(_host)


ROW_ID_RE = _grammar.ROW_ID_RE
NEEDS_REF_RE = _grammar.NEEDS_REF_RE
FIELD_RE = _grammar.FIELD_RE
ROW_LINE_RE = _grammar.ROW_RE
# Prefix-matched, exactly as lint's `_section` reads a heading: `## Progress —
# the receipts` is a Progress section to the enforcer, so an exact-string match
# here would refuse to append the PROOF line after a proof that already passed.
PROGRESS_HEADING_RE = re.compile(r"^## Progress(?: [^\n]*)?$", re.MULTILINE)
OBJECT_DIGEST_RE = re.compile(r"[0-9a-f]{64}")


LIFECYCLE_ARCHIVE_RE = re.compile(
    r"^- Archived milestone: \[(?P<slug>[a-z0-9][a-z0-9-]*)\]"
    r"\((?P<path>[^)]+)\) "
    r"<!-- shadow:lifecycle:(?P=slug):sha256:(?P<digest>[0-9a-f]{64}):"
    r"cas:(?P<cas>[0-9a-f]{64}):head:(?P<head>[0-9a-f]{40}):"
    r"blob:(?P<blob>[0-9a-f]{40}):"
    r"successor:(?P<successor>~[0-9a-z]{4}|none) -->$"
)
SOURCE_HEAD_RE = re.compile(r"[0-9a-f]{40}")
PUBLIC_SOURCE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._@:/+-]{0,199}")
SOURCE_RECEIPT_RE = re.compile(
    r"^- (?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) "
    r"(?P<id>~[0-9a-z]{4}) SOURCE "
    r"(?P<source>[A-Za-z0-9][A-Za-z0-9._@:/+-]{0,199}) "
    r"HEAD (?P<head>[0-9a-f]{40}) "
    r"-> proof and final lint \(accept\)$"
)
LEGACY_LOCAL_SOURCE_ID_RE = re.compile(r"local-git@(?P<digest>[0-9a-f]{12})")
OPAQUE_LOCAL_SOURCE_ID_RE = re.compile(
    r"local\.shadow\.invalid/(?P<digest>[0-9a-f]{12})"
)
LOCAL_SOURCE_RECEIPT_CUTOVER = "2026-08-28T04:29:56Z"
PROOF_RESULT_SCHEMA = "shadow.proof-result.v1"
PROOF_MARKER_RE = _grammar.PROOF_MARKER_RE
PROOF_FLOOR_RE = _grammar.PROOF_FLOOR_RE
PROPOSAL_ATTEMPT_MAX_BYTES = _host.MAX_ATTEMPT_BYTES
PROPOSAL_ATTEMPT_FIELDS = {
    "schema",
    "revision",
    "host",
    "authority_proposal_mode",
    "execution_policy",
    "task_id",
    "task_sha256",
    "status",
    "summary",
    "proof_ref",
    "changed_paths",
    "ignored_artifact_paths",
    "tests",
    "host_exit_code",
    "timed_out",
    "duration_s",
    "stdout_bytes",
    "stderr_bytes",
    "command_shape",
    "blocked",
    "unreviewed_claim",
    "accepted_by_lead",
    "projection_is_usage",
    "authority_proposal",
}


_shell_operators = _grammar.shell_operators


class AcceptError(ValueError):
    """Fail closed; nothing was changed."""


def _strict_json_object(content: bytes, label: str) -> dict:
    if len(content) > PROPOSAL_ATTEMPT_MAX_BYTES:
        raise AcceptError(f"{label} exceeds the bounded JSON size")
    try:
        text = content.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=lambda pairs: _unique_json_object(pairs, label),
        )
    except UnicodeError as exc:
        raise AcceptError(f"{label} is not UTF-8 JSON") from exc
    except json.JSONDecodeError as exc:
        raise AcceptError(f"{label} is not one exact JSON object") from exc
    if not isinstance(value, dict):
        raise AcceptError(f"{label} is not one exact JSON object")
    return value


def _strict_json_file(path: Path, label: str) -> dict:
    """Read one bounded regular JSON file without following its final symlink."""
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise AcceptError(f"{label} could not be read") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise AcceptError(f"{label} must be one regular file")
        if metadata.st_size > PROPOSAL_ATTEMPT_MAX_BYTES:
            raise AcceptError(f"{label} exceeds the bounded JSON size")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            content = stream.read(PROPOSAL_ATTEMPT_MAX_BYTES + 1)
    except OSError as exc:
        raise AcceptError(f"{label} could not be read") from exc
    finally:
        os.close(descriptor)
    return _strict_json_object(content, label)


def _unique_json_object(
    pairs: list[tuple[str, object]],
    label: str,
) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise AcceptError(f"{label} repeats JSON field {key}")
        value[key] = item
    return value


def proposal_attempt_path(repo: Path, supplied: Path) -> Path:
    """Resolve one regular attempt below the source checkout's evidence root."""
    state = repo / ".shadow"
    evidence = state / "evidence"
    candidate = supplied.expanduser()
    if not candidate.is_absolute():
        candidate = repo / candidate
    candidate = Path(os.path.abspath(candidate))
    try:
        relative = candidate.relative_to(evidence)
    except ValueError as exc:
        raise AcceptError("proposal attempt must stay inside .shadow/evidence") from exc
    if not relative.parts:
        raise AcceptError("proposal attempt must name one evidence file")
    current = state
    for part in ("evidence", *relative.parts):
        current = current / part
        if current.is_symlink():
            raise AcceptError("proposal attempt path crosses a symlink")
    if not candidate.is_file():
        raise AcceptError("proposal attempt must be one regular file")
    return candidate


def load_authority_proposal(repo: Path, supplied: Path) -> dict[str, object]:
    """Load one successful sealed Codex attempt and revalidate its proposal."""
    path = proposal_attempt_path(repo, supplied)
    raw = _strict_json_file(path, "proposal attempt")
    if set(raw) != PROPOSAL_ATTEMPT_FIELDS:
        raise AcceptError("proposal attempt fields are invalid")
    revision = raw.get("revision")
    if (
        raw.get("schema") != _host.ATTEMPT_SCHEMA
        or isinstance(revision, bool)
        or not isinstance(revision, int)
        or revision != 1
    ):
        raise AcceptError("proposal attempt schema is invalid")
    if raw.get("host") != "codex":
        raise AcceptError("proposal acceptance supports sealed Codex attempts only")
    if raw.get("authority_proposal_mode") is not True:
        raise AcceptError("proposal attempt did not use explicit authority proposal mode")
    policy = raw.get("execution_policy")
    if (
        not isinstance(policy, dict)
        or set(policy)
        != {
            "schema",
            "work_class",
            "requested_model",
            "observed_model",
            "delegation",
            "requested_child_capability",
            "observed_child_spans",
            "observation",
        }
        or policy.get("schema") != _host.POLICY_VERSION
    ):
        raise AcceptError("proposal attempt execution policy is invalid")
    work_class = policy.get("work_class")
    delegation = policy.get("delegation")
    if (
        work_class not in _host.WORK_CLASSES
        or delegation not in _host.DELEGATION_MODES
    ):
        raise AcceptError("proposal attempt execution policy is invalid")
    try:
        route = _host.resolve_route("codex", work_class)
        capability = _host.delegation_capability("codex", delegation)
    except _host.ExecutionPolicyError as exc:
        raise AcceptError("proposal attempt execution policy is invalid") from exc
    if (
        policy.get("requested_model") != route.model
        or policy.get("observed_model") is not None
        or policy.get("requested_child_capability") != capability
        or policy.get("observed_child_spans") is not None
        or policy.get("observation") != "owner-local-gauntlet-required"
    ):
        raise AcceptError("proposal attempt execution policy is invalid")
    command_shape = raw.get("command_shape")
    if command_shape != _host.public_command_shape("codex", delegation=delegation):
        raise AcceptError("proposal attempt did not use the workspace-write sandbox")
    tests = raw.get("tests")
    host_exit_code = raw.get("host_exit_code")
    if (
        raw.get("status") != "ok"
        or isinstance(host_exit_code, bool)
        or not isinstance(host_exit_code, int)
        or host_exit_code != 0
        or raw.get("timed_out") is not False
        or raw.get("blocked") is not None
        or raw.get("unreviewed_claim") is not True
        or raw.get("accepted_by_lead") is not False
        or raw.get("projection_is_usage") is not False
        or not isinstance(tests, list)
        or not tests
        or any(
            not isinstance(item, dict)
            or set(item) != {"name", "status"}
            or item.get("status") != "pass"
            for item in tests
        )
    ):
        raise AcceptError("proposal attempt is not one successful unreviewed result")
    try:
        proposal = _host.validate_authority_proposal(raw["authority_proposal"])
    except _host.HostError as exc:
        raise AcceptError(f"proposal attempt is invalid: {exc.detail}") from exc
    return proposal


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


def proof_source_checkout(repo: Path) -> Path:
    """Resolve ``--repo`` to the Git toplevel where cmd proofs run."""
    repo = repo.resolve()
    source_top = git_completed(repo, "rev-parse", "--show-toplevel")
    if source_top.returncode or not source_top.stdout.strip():
        raise AcceptError("--repo must name a Git source checkout")
    return Path(source_top.stdout.strip()).resolve()


def bind_local_plan_to_proof_repo(
    plan_text: str,
    source_root: Path,
) -> str:
    """Bind one frozen local-plan snapshot to its explicit proof checkout."""
    values = _grammar.brief_origin_values(plan_text)
    declared = local_plan_source_identity(plan_text)
    checkout = public_source_identity(source_root)
    if declared is None:
        if (
            OPAQUE_LOCAL_SOURCE_ID_RE.fullmatch(checkout)
            or has_unbound_legacy_local_acceptance(plan_text)
        ):
            return checkout
        raise AcceptError("the local plan has no Origin")
    if checkout != declared:
        if not values:
            raise AcceptError(
                "the explicit source checkout does not match the machine-local "
                "plan's SOURCE binding"
            )
        raise AcceptError("--repo origin does not match the plan Origin")
    return checkout


def frozen_source_head(repo: Path) -> str:
    """Resolve one exact commit before creating the detached proof checkout."""
    result = git_completed(repo, "rev-parse", "--verify", "HEAD^{commit}")
    head = result.stdout.strip()
    if result.returncode or SOURCE_HEAD_RE.fullmatch(head) is None:
        raise AcceptError("source checkout HEAD cannot be resolved to one commit")
    return head


def require_frozen_review_head(review: Path, expected_head: str) -> None:
    """Refuse a detached proof checkout that moved away from its source commit."""
    if frozen_source_head(review) != expected_head:
        raise AcceptError(
            "detached source checkout moved away from the frozen HEAD; "
            "nothing was changed"
        )


def public_source_identity(repo: Path) -> str:
    """Name the proof source without writing its private checkout path."""
    try:
        identity = _board.origin_of(repo)
    except _board.BoardError as exc:
        raise AcceptError(f"source checkout identity cannot be read: {exc}") from exc
    if (
        identity.startswith(("local-git:", "local-remote:"))
        or PUBLIC_SOURCE_ID_RE.fullmatch(identity) is None
    ):
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
        return f"local.shadow.invalid/{digest}"
    return canonical_source_identity(identity)


def canonical_source_identity(identity: str) -> str:
    """Normalize legacy opaque receipts into the one durable Brief identity."""
    legacy = LEGACY_LOCAL_SOURCE_ID_RE.fullmatch(identity)
    if legacy is not None:
        return f"local.shadow.invalid/{legacy.group('digest')}"
    try:
        return _board.well_formed_proof_origin(identity)
    except ValueError as exc:
        raise AcceptError("SOURCE identity is not one public normalized identity") from exc


def local_source_receipt(
    plan_text: str,
    row_id: str,
    argv: list[str],
) -> tuple[str, str]:
    """Return the one source identity and commit bound to a local completion."""
    receipts: list[tuple[str, str, str]] = []
    for line in _board.section_lines(plan_text, "Progress"):
        if f" {row_id} SOURCE " not in line:
            continue
        match = SOURCE_RECEIPT_RE.fullmatch(line)
        if match is None:
            raise AcceptError(
                f"{row_id} has a malformed SOURCE receipt; root claim stays open"
            )
        receipts.append(
            (match.group("ts"), match.group("source"), match.group("head"))
        )
    if len(receipts) != 1:
        raise AcceptError(
            f"{row_id} has {len(receipts)} canonical SOURCE receipts; "
            "root claim stays open"
        )
    proof_stamps = _receipt_stamps(plan_text, row_id, argv)
    if proof_stamps != [receipts[0][0]]:
        raise AcceptError(
            f"{row_id} SOURCE is not paired with one canonical PROOF receipt; "
            "root claim stays open"
        )
    return canonical_source_identity(receipts[0][1]), receipts[0][2]


def has_unbound_legacy_local_acceptance(plan_text: str) -> bool:
    """Whether a current completed row has one exact pre-cutover acceptance."""
    progress_lines = _board.section_lines(plan_text, "Progress")
    task_rows = {
        row.group("id")
        for line in _board.section_lines(plan_text, "Tasks")
        if (row := ROW_LINE_RE.fullmatch(line)) is not None
    }
    for line in progress_lines:
        receipt = _grammar.progress_proof_receipt(line)
        match = _grammar.PROOF_RECEIPT_RE.fullmatch(line)
        if (
            receipt is not None
            and match is not None
            and receipt[2] == "pass (accept)"
            and match.group("ts") < LOCAL_SOURCE_RECEIPT_CUTOVER
            and receipt[0] in task_rows
        ):
            _, _, state, proof, _ = find_row(plan_text, receipt[0])
            if state != "completed" or not proof.startswith("cmd "):
                continue
            argv = proof_argv(proof[4:])
            source_lines = [
                candidate
                for candidate in progress_lines
                if f" {receipt[0]} SOURCE " in candidate
            ]
            if (
                receipt[1] == shlex.join(argv)
                and not source_lines
                and _receipt_stamps(plan_text, receipt[0], argv)
                == [match.group("ts")]
            ):
                return True
    return False


def local_plan_source_identity(plan_text: str) -> str | None:
    """Return the plan-owned source identity, including after lifecycle archive."""
    values = _grammar.brief_origin_values(plan_text)
    if len(values) > 1:
        raise AcceptError("the local plan has more than one Origin")
    declared: str | None = None
    if values:
        try:
            declared = _board.well_formed_proof_origin(values[0])
        except ValueError as exc:
            raise AcceptError(
                "the local plan Origin is not a normalized Git identity"
            ) from exc
    accepted_receipts: list[tuple[str, str, str]] = []
    for line in _board.section_lines(plan_text, "Progress"):
        receipt = _grammar.progress_proof_receipt(line)
        match = _grammar.PROOF_RECEIPT_RE.fullmatch(line)
        if (
            receipt is not None
            and match is not None
            and receipt[2] == "pass (accept)"
        ):
            accepted_receipts.append(
                (match.group("ts"), receipt[0], receipt[1])
            )
    task_rows = {
        row.group("id")
        for line in _board.section_lines(plan_text, "Tasks")
        if (row := ROW_LINE_RE.fullmatch(line)) is not None
    }
    identities = {declared} if declared is not None else set()
    for accepted_at, row_id, accepted_proof in accepted_receipts:
        if row_id not in task_rows:
            continue
        _, _, state, proof, _ = find_row(plan_text, row_id)
        if state != "completed" or not proof.startswith("cmd "):
            raise AcceptError(
                f"{row_id} accept PROOF no longer belongs to a completed cmd row"
            )
        argv = proof_argv(proof[4:])
        if accepted_proof != shlex.join(argv):
            raise AcceptError(
                f"{row_id} task proof no longer matches its canonical accept PROOF"
            )
        source_lines = [
            line
            for line in _board.section_lines(plan_text, "Progress")
            if f" {row_id} SOURCE " in line
        ]
        if not source_lines and accepted_at < LOCAL_SOURCE_RECEIPT_CUTOVER:
            if _receipt_stamps(plan_text, row_id, argv) != [accepted_at]:
                raise AcceptError(
                    f"{row_id} has no single canonical legacy accept PROOF"
                )
            continue
        source_identity, _ = local_source_receipt(
            plan_text,
            row_id,
            argv,
        )
        identities.add(source_identity)
    if len(identities) > 1:
        raise AcceptError("the machine-local plan has conflicting SOURCE bindings")
    return next(iter(identities), None)


def local_plan_with_origin(plan_text: str, source_identity: str) -> str:
    """Persist the one path-free source binding in the plan's Brief."""
    source_identity = canonical_source_identity(source_identity)
    values = _grammar.brief_origin_values(plan_text)
    if len(values) > 1:
        raise AcceptError("the local plan has more than one Origin")
    if values:
        try:
            declared = _board.well_formed_proof_origin(values[0])
        except ValueError as exc:
            raise AcceptError(
                "the local plan Origin is not a normalized Git identity"
            ) from exc
        if declared != source_identity:
            raise AcceptError(
                "the explicit source checkout does not match the machine-local "
                "plan's Origin"
            )
        return plan_text

    lines = plan_text.splitlines(keepends=True)
    brief_start: int | None = None
    brief_end: int | None = None
    insert_at: int | None = None
    for index, line in enumerate(lines):
        if not line.startswith("## "):
            continue
        heading = line[3:].strip()
        if brief_start is None:
            if heading == "Brief" or heading.startswith("Brief "):
                brief_start = index + 1
            continue
        brief_end = index
        break
    if brief_start is None:
        raise AcceptError("the local plan has no Brief section")
    brief_end = len(lines) if brief_end is None else brief_end
    for index in range(brief_start, brief_end):
        if lines[index].startswith("- Mode:"):
            insert_at = index + 1
            break
    if insert_at is None:
        raise AcceptError("the local plan Brief has no Mode")
    lines.insert(insert_at, f"- Origin: {source_identity}\n")
    return "".join(lines)


def proposal_row_contract(
    plan_text: str,
    row_id: str,
) -> tuple[str, str, str, str, str, int]:
    """Return the exact canonical row contract used by proposal acceptance."""
    _, row_line, state, proof, needs = find_row(plan_text, row_id)
    row = ROW_LINE_RE.fullmatch(row_line)
    if row is None:
        raise AcceptError(f"{row_id} does not match the task-row grammar")
    fields = dict(FIELD_RE.findall(row.group("tail") or ""))
    marker = fields.get("marker")
    floor_text = fields.get("floor")
    if marker is None and floor_text is None:
        raise AcceptError(
            f"{row_id} is not proposal-enabled; its canonical row needs marker and floor"
        )
    if marker is None or floor_text is None:
        raise AcceptError(
            f"{row_id} must declare both marker and floor for proposal acceptance"
        )
    marker = marker.strip()
    floor_text = floor_text.strip()
    if PROOF_MARKER_RE.fullmatch(marker) is None:
        raise AcceptError(f"{row_id} has an invalid proposal proof marker")
    if PROOF_FLOOR_RE.fullmatch(floor_text) is None:
        raise AcceptError(f"{row_id} has an invalid proposal execution floor")
    return row_line, state, proof, needs, marker, int(floor_text)


def row_requires_proposal(plan_text: str, row_id: str) -> bool:
    """Whether either proposal-only authority field is present on the row."""
    _, row_line, _, _, _ = find_row(plan_text, row_id)
    row = ROW_LINE_RE.fullmatch(row_line)
    if row is None:
        return False
    fields = dict(FIELD_RE.findall(row.group("tail") or ""))
    return "marker" in fields or "floor" in fields


def local_plan_root_snapshot(plan_path: Path) -> _plan_store.PlanSnapshot:
    try:
        return _board.open_plan(plan_path)
    except _board.BoardError as exc:
        raise AcceptError(f"local plan root cannot be opened: {exc}") from exc


def plan_object_digests(plan_path: Path) -> set[str]:
    root = plan_path.parent / "PLAN.d" / "objects" / "sha256"
    if not root.exists():
        return set()
    if root.is_symlink() or not root.is_dir():
        raise AcceptError("local plan object store is unsafe")
    digests: set[str] = set()
    for path in root.glob("*/*"):
        if path.is_symlink() or not path.is_file():
            raise AcceptError("local plan object store contains an unsafe entry")
        if OBJECT_DIGEST_RE.fullmatch(path.name) is None:
            raise AcceptError("local plan object store contains a malformed digest")
        digests.add(path.name)
    return digests


def restore_local_authority(
    plan_path: Path,
    root_bytes: bytes,
    object_digests: set[str],
) -> None:
    """CAS-restore exact local plan bytes and remove only new unreachable objects."""
    try:
        current = plan_path.read_bytes()
        if current != root_bytes:
            _plan_store.restore_exact_root(
                plan_path,
                expected_current_root=hashlib.sha256(current).hexdigest(),
                target_root_bytes=root_bytes,
            )
        added = plan_object_digests(plan_path) - object_digests
        if added:
            _plan_store.discard_unreachable(plan_path, added)
        restored = local_plan_root_snapshot(plan_path)
        if restored.root_bytes != root_bytes:
            raise AcceptError("local authority rollback readback did not match")
        restored.materialize()
        if plan_object_digests(plan_path) != object_digests:
            raise AcceptError("local authority rollback left object-store drift")
    except (OSError, _plan_store.PlanStoreError, AcceptError) as exc:
        raise AcceptError("local authority could not be restored exactly") from exc


def atomic_write_text(
    path: Path,
    text: str,
) -> _plan_store.PublishReceipt | None:
    """Replace one complete PLAN in its own directory; never leave truncation."""
    try:
        snapshot = _board.open_plan(path)
    except _board.BoardError as exc:
        raise AcceptError(f"entity plan could not be opened: {exc}") from exc
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
            raise AcceptError(f"entity plan tree could not be replaced: {exc}") from exc
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
        raise AcceptError("entity plan could not be replaced atomically") from exc
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
    """Create one exact source commit while preserving unrelated index state."""
    plan_pathspec = str(plan_relative)
    with _board.project_lock(plan_path):
        try:
            locked_token, locked_bytes = _board.committed_plan_snapshot(plan_path)
            locked_text = locked_bytes.decode("utf-8")
        except (_board.BoardError, OSError, UnicodeError) as exc:
            raise AcceptError(f"plan changed before the source commit: {exc}") from exc
        if locked_token != plan_token or locked_text != original_text:
            raise AcceptError("the committed entity plan changed before the source commit; retry")
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


def run_proof(
    worktree: Path,
    proof: list[str],
    timeout_seconds: int,
    *,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes] | None:
    proof_environment = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        **(environment or {}),
    }
    try:
        return subprocess.run(
            proof,
            cwd=worktree,
            env=proof_environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def proof_passes(worktree: Path, proof: list[str], timeout_seconds: int) -> bool:
    result = run_proof(worktree, proof, timeout_seconds)
    return result is not None and result.returncode == 0


def review_checkout_is_clean(worktree: Path, expected_head: str) -> bool:
    status = git_completed(
        worktree,
        "status",
        "--porcelain=v1",
        "--ignored=matching",
        "--untracked-files=all",
    )
    if status.returncode or status.stdout.strip():
        return False
    try:
        require_frozen_review_head(worktree, expected_head)
    except AcceptError:
        return False
    return True


def grade_proof_result(
    result: subprocess.CompletedProcess[bytes],
    marker: str,
    floor: int,
) -> None:
    if result.returncode != 0:
        raise AcceptError("the proposal proof exited non-zero; nothing was changed")
    proof_result = _strict_json_object(result.stdout, "proposal proof result")
    if set(proof_result) != {"schema", "result", "marker", "executed"}:
        raise AcceptError("proposal proof result fields are invalid")
    executed = proof_result.get("executed")
    if (
        proof_result.get("schema") != PROOF_RESULT_SCHEMA
        or proof_result.get("result") != "pass"
        or proof_result.get("marker") != marker
        or isinstance(executed, bool)
        or not isinstance(executed, int)
        or executed < floor
    ):
        raise AcceptError(
            "proposal proof result did not satisfy the canonical marker and floor"
        )


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
    *,
    expected_head: str | None = None,
) -> bool:
    if not proof_passes(worktree / proof_directory, proof, timeout_seconds):
        return False
    return expected_head is None or review_checkout_is_clean(
        worktree,
        expected_head,
    )


def require_accept_ready_row(
    plan_path: Path,
    plan_text: str,
    row_id: str,
    owner: str,
) -> tuple[dict, str, str, str, list[str]]:
    """The one readiness gate every accept path must pass verbatim.

    Claim, needs, written challenge, cmd-only proof, non-empty argv, and no
    unwrapped shell operators. Three accept paths used to carry three copies
    of this gate with three different refusal texts; a gate that drifts
    between paths is how a false green slips through one of them.
    """
    _, _, state, proof, needs = find_row(plan_text, row_id)
    claim = owned_claim(_board.entity_state(plan_path), row_id, owner)
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
            f"{row_id} or its needs-ancestry is under a written challenge scoped as an "
            "acceptance challenge and must not "
            f"flip silently; resolve the Contradictions entry first: {challenged[0]}"
        )
    if not proof.startswith("cmd "):
        kind = proof.split(" ", 1)[0]
        raise AcceptError(
            f"only cmd proofs are machine-rerunnable; this row is {kind}-classed — "
            "re-observe it yourself and append the PROOF line with the flip"
        )
    argv = proof_argv(proof[4:])
    if not argv:
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
            f"the proof passes {' '.join(offenders)} to `{argv[0]}` as a literal "
            "argument — accept runs proofs without a shell, so the rest of the command "
            f"would never execute. Wrap it: cmd bash -c '<the whole command>'"
        )
    return claim, state, proof, needs, argv


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


@contextmanager
def completed_proof_review(
    repo: Path,
    plan_path: Path,
    plan_text: str,
    row_id: str,
    argv: list[str],
    source_head: str,
    timeout_seconds: int,
    proof_directory: Path = Path("."),
) -> Iterator[Path]:
    """Rerun one recorded completion before any retry can publish or release it."""
    pool = repo.parent / f"{repo.name}-shadow-accept"
    pool.mkdir(exist_ok=True)
    git_completed(repo, "worktree", "prune", timeout=15)
    review = create_lead_review_worktree(
        repo,
        pool,
        row_id.lstrip("~"),
        source_head,
    )
    try:
        require_frozen_review_head(review, source_head)
        proof_root = review / proof_directory
        issue = script_operand_issue(argv, proof_root)
        if issue:
            raise AcceptError(
                f"the completed proof's {issue}; root claim stays open"
            )
        refuse_lint_blocked_plan(
            plan_text,
            plan_path,
            proof_root=proof_root,
            row_id=row_id,
        )
        if not lead_review_passes(
            review,
            argv,
            timeout_seconds,
            proof_directory,
            expected_head=source_head,
        ):
            raise AcceptError(
                "the completed proof did not pass from the detached source "
                "checkout; root claim stays open"
            )
        require_frozen_review_head(review, source_head)
        yield review
    finally:
        remove_review_worktree(repo, review)
        try:
            pool.rmdir()
        except OSError:
            pass


def require_clean_source_checkout(repo: Path) -> None:
    try:
        _host.local_state_snapshot(repo)
    except _host.HostError as exc:
        raise AcceptError(
            "proposal acceptance requires one clean committed source checkout"
        ) from exc
    status = git_completed(
        repo,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--ignored=traditional",
    )
    dirt = [
        line
        for line in status.stdout.splitlines()
        if not (
            line[:2] in {"??", "!!"}
            and line[3:].startswith(".shadow/evidence/")
        )
    ]
    if status.returncode or dirt:
        raise AcceptError(
            "proposal acceptance requires one clean committed source checkout"
        )


def accept_local_proposal(
    repo: Path,
    plan_path: Path,
    entity_id: str,
    row_id: str,
    owner: str,
    proposal_path: Path,
    timeout_seconds: int,
) -> int:
    """Accept one untrusted completion proposal against machine-local authority."""
    proposal = load_authority_proposal(repo, proposal_path)
    if proposal["entity_id"] != entity_id:
        raise AcceptError("proposal entity does not match --entity")
    if proposal["row_id"] != row_id:
        raise AcceptError("proposal row does not match --row")
    if proposal["owner"] != owner:
        raise AcceptError("proposal owner does not match --by")
    try:
        plan_path.resolve().relative_to(repo.resolve())
    except ValueError:
        pass
    else:
        raise AcceptError(
            "proposal acceptance requires machine-local authority outside the source checkout"
        )

    with _board.project_lock(plan_path):
        try:
            resolved = _board.resolve_entity(entity_id)
        except _board.BoardError as exc:
            raise AcceptError(f"proposal entity cannot be resolved: {exc}") from exc
        if (
            resolved is None
            or resolved["plan"] is None
            or resolved["plan"].resolve() != plan_path.resolve()
            or not _board.is_local_plan(plan_path)
        ):
            raise AcceptError("proposal entity no longer resolves to this machine-local plan")

        root_snapshot = local_plan_root_snapshot(plan_path)
        root_bytes = root_snapshot.root_bytes
        original_objects = plan_object_digests(plan_path)
        try:
            plan_token, plan_bytes = _board.frozen_plan_snapshot(plan_path)
            plan_text = plan_bytes.decode("utf-8")
        except (_board.BoardError, OSError, UnicodeError) as exc:
            raise AcceptError(f"local plan cannot be frozen before proposal proof: {exc}") from exc
        if root_snapshot.materialize() != plan_bytes:
            raise AcceptError("local plan root and logical content disagree")
        if proposal["base"]["plan_root_sha256"] != root_snapshot.root_sha256:
            raise AcceptError("proposal plan root is stale")

        source_identity = bind_local_plan_to_proof_repo(plan_text, repo)
        source_head = frozen_source_head(repo)
        if proposal["base"]["source_head"] != source_head:
            raise AcceptError("proposal source HEAD is stale")
        require_clean_source_checkout(repo)

        contract = proposal_row_contract(plan_text, row_id)
        row_line, state, proof, needs, marker, floor = contract
        if state not in {"pending", "in_progress"}:
            raise AcceptError("proposal transition requires a pending or in-progress row")
        claim, _, _, _, argv = require_accept_ready_row(
            plan_path, plan_text, row_id, owner
        )

        pool = repo.parent / f"{repo.name}-shadow-accept"
        pool.mkdir(exist_ok=True)
        git_completed(repo, "worktree", "prune", timeout=15)
        review = create_lead_review_worktree(
            repo,
            pool,
            row_id.lstrip("~"),
            source_head,
        )
        updated: str | None = None
        try:
            issue = script_operand_issue(argv, review)
            if issue:
                raise AcceptError(f"the proposal proof's {issue}; nothing was changed")
            with tempfile.TemporaryDirectory(
                prefix=".shadow-proof-home.",
                dir=pool,
            ) as proof_home:
                proof_root = Path(proof_home) / ".shadow"
                proof_root.mkdir()
                proof_board = proof_root / "board.json"
                proof_board.write_text("{}\n", encoding="utf-8")
                os.chmod(proof_board, 0o400)
                os.chmod(proof_root, 0o500)
                try:
                    proof_result = run_proof(
                        review,
                        argv,
                        timeout_seconds,
                        environment={"HOME": proof_home},
                    )
                finally:
                    os.chmod(proof_root, 0o700)
                    os.chmod(proof_board, 0o600)
            if proof_result is None:
                raise AcceptError("the proposal proof could not finish; nothing was changed")
            grade_proof_result(proof_result, marker, floor)
            if not review_checkout_is_clean(review, source_head):
                raise AcceptError(
                    "the proposal proof changed its detached checkout; nothing was changed"
                )
            if frozen_source_head(repo) != source_head:
                raise AcceptError("the source HEAD changed while proposal proof ran")
            require_clean_source_checkout(repo)

            fresh_root = local_plan_root_snapshot(plan_path)
            fresh_token, fresh_bytes = _board.frozen_plan_snapshot(plan_path)
            fresh_text = fresh_bytes.decode("utf-8")
            if (
                fresh_root.root_sha256 != root_snapshot.root_sha256
                or fresh_root.root_bytes != root_bytes
                or fresh_token != plan_token
                or fresh_text != plan_text
            ):
                raise AcceptError("the local plan changed while proposal proof ran")
            try:
                fresh_resolved = _board.resolve_entity(entity_id)
            except _board.BoardError as exc:
                raise AcceptError(f"proposal entity changed while proof ran: {exc}") from exc
            if (
                fresh_resolved is None
                or fresh_resolved["plan"] is None
                or fresh_resolved["plan"].resolve() != plan_path.resolve()
            ):
                raise AcceptError("proposal entity changed while proof ran")
            fresh_claim = owned_claim(_board.entity_state(plan_path), row_id, owner)
            if fresh_claim != claim:
                raise AcceptError("the owned claim changed while proposal proof ran")
            fresh_contract = proposal_row_contract(fresh_text, row_id)
            if fresh_contract != contract or fresh_contract[0] != row_line:
                raise AcceptError("the canonical row changed while proposal proof ran")
            if unmet_needs(fresh_text, fresh_contract[3]) or contradiction_challenges(
                fresh_text,
                row_id,
                fresh_contract[3],
            ):
                raise AcceptError("the canonical row is no longer ready")

            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            updated = completed_local_plan_text(
                fresh_text,
                row_id,
                argv,
                stamp,
                source_identity,
                source_head,
            )
            refuse_lint_blocked_plan(
                updated,
                plan_path,
                proof_root=review,
                row_id=row_id,
            )
            require_frozen_review_head(review, source_head)
        except BaseException:
            restore_local_authority(plan_path, root_bytes, original_objects)
            raise
        finally:
            remove_review_worktree(repo, review)
            try:
                pool.rmdir()
            except OSError:
                pass

        if updated is None:
            raise AcceptError("proposal acceptance produced no canonical transition")
        if frozen_source_head(repo) != source_head:
            raise AcceptError("the source HEAD changed before proposal publication")
        require_clean_source_checkout(repo)
        try:
            atomic_write_text(plan_path, updated)
            completed_token, completed_bytes = _board.frozen_plan_snapshot(plan_path)
            completed_text = completed_bytes.decode("utf-8")
            if completed_text != updated:
                raise AcceptError("proposal publication readback did not match")
            completed_plan = _amp._parse(completed_text)
            completed_plan["claimed"] = set()
            _board.release(
                plan_path,
                row_id,
                owner=owner,
                reason="completed",
                resumes=_amp._candidate_ids(completed_plan),
                expected_plan=completed_token,
                expected_text=completed_text,
                expected_claim=claim,
            )
        except BaseException as exc:
            restore_local_authority(plan_path, root_bytes, original_objects)
            if isinstance(exc, KeyboardInterrupt):
                raise
            raise AcceptError(
                "proposal completion could not finalize; prior authority was restored"
            ) from exc

    print(
        f"accepted {row_id}: sealed Codex proposal proved marker {marker} "
        f"at floor {floor}; machine-local authority flipped at source HEAD {source_head}"
    )
    return 0


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
    launch those from a detached checkout of the explicit ``--repo`` and keep
    that exact commit alive through final lint, local publication, and release.
    """
    try:
        plan_token, plan_bytes = _board.frozen_plan_snapshot(plan_path)
        plan_text = plan_bytes.decode("utf-8")
    except (_board.BoardError, OSError, UnicodeError) as exc:
        raise AcceptError(f"local plan cannot be frozen before proof: {exc}") from exc
    source_identity = bind_local_plan_to_proof_repo(
        plan_text,
        repo,
    )
    _, _, state, proof, needs = find_row(plan_text, row_id)
    if row_requires_proposal(plan_text, row_id):
        raise AcceptError(
            f"{row_id} declares proposal-only proof authority; rerun with --proposal"
        )
    claim = owned_claim(_board.entity_state(plan_path), row_id, owner)
    if state == "completed":
        if not proof.startswith("cmd "):
            raise AcceptError("the completed local row was not accepted from a cmd proof")
        argv = proof_argv(proof[4:])
        if not _board.has_accept_proof_receipt(plan_text, row_id, argv):
            raise AcceptError("the local row is completed without a matching accept proof")
        recorded_source_identity, source_head = local_source_receipt(
            plan_text,
            row_id,
            argv,
        )
        if source_identity != recorded_source_identity:
            raise AcceptError(
                "the explicit source checkout does not match the completion's "
                "SOURCE receipt"
            )
        with completed_proof_review(
            repo,
            plan_path,
            plan_text,
            row_id,
            argv,
            source_head,
            timeout_seconds,
        ) as review:
            require_frozen_review_head(review, source_head)
            if claim is not None:
                parsed = _amp._parse(plan_text)
                parsed["claimed"] = set()
                try:
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
                except _board.BoardError as exc:
                    raise AcceptError(
                        f"local claim could not close after the proof review: {exc}"
                    ) from exc
        print(
            f"accepted {row_id}: completed proof reran at its recorded source; "
            "root claim reconciled"
        )
        return 0
    _, _, _, _, argv = require_accept_ready_row(plan_path, plan_text, row_id, owner)
    source_head = frozen_source_head(repo)
    pool = repo.parent / f"{repo.name}-shadow-accept"
    pool.mkdir(exist_ok=True)
    git_completed(repo, "worktree", "prune", timeout=15)
    review = create_lead_review_worktree(
        repo,
        pool,
        row_id.lstrip("~"),
        source_head,
    )
    try:
        issue = script_operand_issue(argv, review)
        if issue:
            raise AcceptError(f"the proof's {issue}; nothing was changed")
        if not lead_review_passes(
            review,
            argv,
            timeout_seconds,
            expected_head=source_head,
        ):
            raise AcceptError(
                "the proof did not pass from the detached source checkout; "
                "nothing was changed"
            )
        with _board.project_lock(plan_path):
            fresh_token, fresh_bytes = _board.frozen_plan_snapshot(plan_path)
            try:
                fresh_text = fresh_bytes.decode("utf-8")
            except UnicodeError as exc:
                raise AcceptError("local plan is not UTF-8") from exc
            if fresh_token != plan_token or fresh_text != plan_text:
                raise AcceptError("the local plan changed while the proof ran; retry")
            locked_source_identity = bind_local_plan_to_proof_repo(
                fresh_text,
                repo,
            )
            if locked_source_identity != source_identity:
                raise AcceptError(
                    "the source checkout identity changed while the proof ran; retry"
                )
            _, _, fresh_state, fresh_proof, fresh_needs = find_row(fresh_text, row_id)
            if fresh_state != state or fresh_proof != proof:
                raise AcceptError("the local row changed while the proof ran; retry")
            if unmet_needs(fresh_text, fresh_needs) or contradiction_challenges(
                fresh_text, row_id, fresh_needs
            ):
                raise AcceptError("the local row is no longer ready; nothing was changed")
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            updated = completed_local_plan_text(
                fresh_text,
                row_id,
                argv,
                stamp,
                source_identity,
                source_head,
            )
            refuse_lint_blocked_plan(
                updated,
                plan_path,
                proof_root=review,
                row_id=row_id,
            )
            require_frozen_review_head(review, source_head)
            try:
                claim_token = _board.reserve_completion(
                    plan_path,
                    row_id,
                    owner,
                    expected_plan=fresh_token,
                )
            except _board.BoardError as exc:
                raise AcceptError(
                    f"local claim could not reserve completion: {exc}"
                ) from exc
            atomic_write_text(plan_path, updated)
            completed_token, completed_bytes = _board.frozen_plan_snapshot(plan_path)
            completed_text = completed_bytes.decode("utf-8")
            parsed = _amp._parse(completed_text)
            parsed["claimed"] = set()
            try:
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
            except _board.BoardError as exc:
                raise AcceptError(
                    "the completed plan is written; the local claim could not "
                    f"close: {exc}"
                ) from exc
    finally:
        remove_review_worktree(repo, review)
        try:
            pool.rmdir()
        except OSError:
            pass
    print(
        f"accepted {row_id}: proof and final lint passed at {source_identity} "
        f"HEAD {source_head}; local row flipped with its PROOF and SOURCE lines"
    )
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
    for line in _board.section_lines(plan_text, "Contradictions"):
        if not line.startswith("- "):
            continue
        if not _grammar.contradiction_is_open(line):
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
    proof_line = (
        f"- {stamp} {row_id} PROOF {shlex.join(argv)} -> pass (accept)\n"
    )
    return append_progress_line(updated, proof_line)


def append_progress_line(plan_text: str, line: str) -> str:
    """Append one canonical receipt to Progress without moving later sections."""
    heading = PROGRESS_HEADING_RE.search(plan_text)
    if heading is None:
        raise AcceptError("the plan has no Progress section")
    next_heading = plan_text.find("\n## ", heading.end())
    if next_heading == -1:
        return plan_text.rstrip() + "\n" + line
    return plan_text[: next_heading + 1] + line + plan_text[next_heading + 1 :]


def completed_local_plan_text(
    plan_text: str,
    row_id: str,
    argv: list[str],
    stamp: str,
    source_identity: str,
    source_head: str,
) -> str:
    """Flip one private row and bind proof plus final lint to one source commit."""
    source_identity = canonical_source_identity(source_identity)
    bound = local_plan_with_origin(plan_text, source_identity)
    completed = completed_plan_text(bound, row_id, argv, stamp)
    return append_progress_line(
        completed,
        f"- {stamp} {row_id} SOURCE {source_identity} HEAD {source_head} "
        "-> proof and final lint (accept)\n",
    )


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
    repo: Path,
    row_id: str,
    no_push: bool,
    summary: str,
    *,
    expected_head: str,
    announce: bool = True,
) -> int:
    """Make an already-committed completion reachable, including on retry."""
    if frozen_source_head(repo) != expected_head:
        raise AcceptError(
            "the source checkout moved away from the frozen completion commit; "
            "root claim stays open"
        )
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
        if frozen_source_head(repo) != expected_head:
            raise AcceptError(
                "the source checkout moved away from the frozen completion commit; "
                "root claim stays open"
            )
        pushed = git_completed(repo, "push", remote, f"{expected_head}:{remote_ref}")
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
    tracking = _remote_claim.uses_remote_upstream(repo)
    try:
        snapshot = _remote_claim.published_plan_snapshot(repo, plan_token)
    except _remote_claim.RemoteClaimError:
        snapshot = None
    if snapshot is None:
        if not tracking:
            raise AcceptError(
                "completion is not published on the tracked upstream; "
                "remote claim retained"
            )
        result = publish_completion(
            repo,
            row_id,
            False,
            summary,
            expected_head=plan_token["head"],
            announce=False,
        )
        if result:
            return result
        try:
            snapshot = _remote_claim.published_plan_snapshot(repo, plan_token)
        except _remote_claim.RemoteClaimError as exc:
            raise AcceptError(
                "completion publication could not be authenticated after push; "
                "remote claim retained"
            ) from exc
        if snapshot is None:
            raise AcceptError(
                "completion is not published on the tracked upstream default; "
                "remote claim retained"
            )
    published_bytes, default_tip = snapshot
    try:
        published_text = published_bytes.decode("utf-8")
        _, _, local_state, local_proof, _ = find_row(plan_text, row_id)
    except (UnicodeError, AcceptError) as exc:
        raise AcceptError(
            "current tracked-upstream default PLAN no longer carries the "
            "completed row and "
            "matching accept proof; remote claim retained"
        ) from exc
    if local_state != "completed" or not local_proof.startswith("cmd "):
        raise AcceptError(
            "current tracked-upstream default PLAN no longer carries the "
            "completed row and "
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
            "current tracked-upstream default PLAN no longer carries the "
            "accepted completion; "
            "it carries a conflicting live row; "
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
        "current tracked-upstream default PLAN no longer carries the completed "
        "row and "
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
    try:
        managed = _remote_claim.managed_for_release(
            repo,
            authenticated_receipt=receipt is not None,
        )
    except _remote_claim.RemoteClaimError as exc:
        raise AcceptError(str(exc)) from exc
    if no_push and managed:
        return publish_completion(
            repo,
            row_id,
            True,
            summary,
            expected_head=plan_token["head"],
        )
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
    else:
        published = publish_completion(
            repo,
            row_id,
            no_push,
            summary,
            expected_head=plan_token["head"],
        )
        if published:
            return published
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
    try:
        _remote_claim.managed_for_release(
            repo,
            authenticated_receipt=receipt is not None,
        )
    except _remote_claim.RemoteClaimError as exc:
        raise AcceptError(str(exc)) from exc
    if receipt is None:
        return publish_completion(
            repo,
            row_id,
            no_push,
            summary,
            expected_head=plan_token["head"],
        )
    if no_push:
        return publish_completion(
            repo,
            row_id,
            True,
            summary,
            expected_head=plan_token["head"],
        )
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
    _shadow_git.sanitize_process_git_env()
    parser = argparse.ArgumentParser(prog="shadow accept", description=__doc__)
    parser.add_argument(
        "--repo",
        type=Path,
        help="Git checkout whose committed HEAD supplies the proof source",
    )
    parser.add_argument(
        "--entity",
        help=(
            "computer-board entity id; combine with --repo to accept one "
            "machine-local entity plan whose Origin matches --repo"
        ),
    )
    parser.add_argument("--row", required=True)
    parser.add_argument("--by", required=True, help="stable owner of the existing claim")
    parser.add_argument(
        "--proposal",
        type=Path,
        help=(
            "sealed Codex attempt below --repo/.shadow/evidence; supported only "
            "with exact --entity and --repo selectors for machine-local authority"
        ),
    )
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--no-push", action="store_true",
                        help="commit without pushing (an unpushed flip is invisible to other seats)")
    args = parser.parse_args(argv)
    if args.repo is None and args.entity is None:
        parser.error("one of --repo or --entity is required")
    row_id = args.row.strip()
    try:
        if ROW_ID_RE.fullmatch(row_id) is None:
            raise AcceptError("row must be a ~hash id, four base36 chars")
        if args.proposal is not None and (
            args.entity is None or args.repo is None
        ):
            raise AcceptError(
                "--proposal requires both exact --entity and --repo selectors"
            )
        if args.proposal is not None and args.no_push:
            raise AcceptError(
                "--proposal accepts machine-local authority and does not take --no-push"
            )
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
                    if args.repo is None:
                        raise _board.BoardError(
                            "--entity recovery requires a Git-backed entity plan; "
                            "machine-local --entity accept also requires "
                            "--repo <proof-source-checkout>"
                        )
                    source_root = proof_source_checkout(args.repo)
                    owned_claim(_board.entity_state(plan_path), row_id, owner)
                    if args.proposal is not None:
                        return accept_local_proposal(
                            source_root,
                            plan_path,
                            args.entity,
                            row_id,
                            owner,
                            args.proposal,
                            args.timeout_seconds,
                        )
                    return accept_local_plan(
                        source_root,
                        plan_path,
                        row_id,
                        owner,
                        args.timeout_seconds,
                    )
                if args.repo is not None:
                    raise AcceptError(
                        "Git-backed --entity recovery does not take --repo; "
                        "--repo may accompany --entity only for a "
                        "machine-local entity plan"
                    )
                if args.proposal is not None:
                    raise AcceptError(
                        "--proposal supports machine-local authority only"
                    )
            else:
                repo = args.repo.resolve()
                source_root = proof_source_checkout(repo)
                requested_plan = repo / "PLAN.md"
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
                    raise AcceptError(
                        "machine-local acceptance requires both exact selectors; "
                        "use `shadow accept --entity ID --repo PATH "
                        f"--row {shlex.quote(row_id)} --by {shlex.quote(owner)}` "
                        "with the entity id printed by `shadow status --by`"
                    )
                state = _board.entity_state(requested_plan)
                owned_claim(state, row_id, owner)
                plan_path = _board.canonical_plan(requested_plan, repair_missing=True)
        except _board.BoardError as exc:
            raise AcceptError(f"the computer board's entity-plan pointer is unusable: {exc}") from exc
        top = git_completed(plan_path.parent, "rev-parse", "--show-toplevel")
        if top.returncode or not top.stdout.strip():
            raise AcceptError("the canonical entity plan is not inside a Git repository")
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
        _, _, state, proof, needs = find_row(plan_text, row_id)
        if row_requires_proposal(plan_text, row_id):
            raise AcceptError(
                f"{row_id} declares proposal-only proof authority, which "
                "Git-backed acceptance does not support"
            )
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
            head = plan_token["head"]
            with completed_proof_review(
                repo,
                plan_path,
                plan_text,
                row_id,
                completed_argv,
                head,
                args.timeout_seconds,
                plan_relative.parent,
            ) as review:
                try:
                    fresh_token, fresh_bytes = _board.committed_plan_snapshot(
                        plan_path
                    )
                    fresh_text = fresh_bytes.decode("utf-8")
                except (_board.BoardError, OSError, UnicodeError) as exc:
                    raise AcceptError(
                        f"plan cannot be frozen after the completed proof: {exc}"
                    ) from exc
                if fresh_token != plan_token or fresh_text != plan_text:
                    raise AcceptError(
                        "the committed entity plan changed while the completed "
                        "proof ran; root claim stays open"
                    )
                if git_completed(
                    repo, "status", "--porcelain", "--", str(plan_relative)
                ).stdout.strip():
                    raise AcceptError(
                        "the completed row or its proof changed while the proof "
                        "ran; root claim stays open"
                    )
                require_frozen_review_head(review, head)
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
                                "completed proof reran in its clean source "
                                "checkout; root claim reconciled",
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
                    "completed proof reran in its clean source checkout; "
                    "root claim reconciled",
                )
        _, _, _, _, argv_proof = require_accept_ready_row(
            plan_path, plan_text, row_id, owner
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
                expected_head=head,
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
            raise AcceptError("the committed entity plan changed while the proof ran; retry")
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
                f"{row_id} or its needs-ancestry gained an acceptance challenge while the proof "
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
