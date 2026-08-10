#!/usr/bin/env python3
"""Rerun one owned checkpoint's proof in a clean checkout, then flip it.

This is the only code path that flips a `cmd`-proven checkpoint to completed. It parses
the repo's PLAN.md, finds the row by its ~hash id, reruns a ``cmd``-classed
proof inside a detached clean worktree of HEAD, and — only on success —
rewrites the row's state and appends the paired PROOF Progress line in one
commit. ``read`` and ``gate`` proofs are person/agent judgments and are
refused here on purpose.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import shadow_root_board as _board  # noqa: E402

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


ROW_ID_RE = re.compile(r"^~[0-9a-z]{4}$")
# Unanchored twin for scanning a `needs:` value, which holds several ids.
# ROW_ID_RE cannot do this job: its ^...$ anchors make findall return nothing
# on "~cd34, ~ef56", which would turn the readiness check into a silent no-op.
NEEDS_REF_RE = re.compile(r"~[0-9a-z]{4}")
FIELD_RE = re.compile(r"\| (?P<key>[a-z]+): (?P<value>[^|]+?)(?= \||$)")
# The grammar's row shape, mirrored from scripts/shadow-lint.py: the id is a
# parsed field, never a substring, so a `needs:` reference or trailing prose
# mentioning another row's id cannot stand in for the row itself.
ROW_LINE_RE = re.compile(
    r"^- \[(?P<state>pending|in_progress|blocked|completed)\] "
    r"(?P<text>.+?) (?P<id>~[0-9a-z]{4})(?P<dod> \(DoD\))?(?P<tail>(?: \| [a-z]+:.*)?)$"
)
# Prefix-matched, exactly as lint's `_section` reads a heading: `## Progress —
# the receipts` is a Progress section to the enforcer, so an exact-string match
# here would refuse to append the PROOF line after a proof that already passed.
PROGRESS_HEADING_RE = re.compile(r"^## Progress(?: [^\n]*)?$", re.MULTILINE)


# Kept identical to `scripts/shadow-lint.py`: the enforcer and the only flip
# path must refuse the same proofs, or one of them is decorative.
SHELL_PUNCTUATION = "();<>|&"
SHELLS = frozenset({"bash", "sh", "zsh", "/bin/bash", "/bin/sh", "/usr/bin/env"})


def _shell_script_index(argv: list[str]) -> int:
    """Index of the -c script — the ONE token a deliberate shell interprets.

    Exempting the whole argv here was the same false green one level up:
    `cmd bash -c 'true' && shadow --version` hands `true` to bash and passes
    `&&`, `shadow`, `--version` to it as positional arguments it never runs.
    """
    if argv[0] not in SHELLS:
        return -1
    for index in (1, 2):
        if index < len(argv) and argv[index] == "-c":
            return index + 1
    return -1


def _shell_operators(command: str) -> list[str]:
    """Unquoted shell metacharacters in argument position, worst-first.

    Comparing whole `shlex.split` tokens missed the operator written without a
    space: `echo done&& false` splits to `done&&`, which equals no operator, so
    the check passed while accept still ran `echo` alone. A second parse with
    `punctuation_chars` is the discriminator the plain argv cannot give — it
    breaks an unquoted metacharacter out into its own token and leaves a quoted
    `'a&&b'` whole, which is exactly the difference between an operator a shell
    would have interpreted and a literal the proof means to pass.
    """
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return []  # the caller's own shlex.split already refused this text
    if not tokens:
        return []
    script = _shell_script_index(tokens)
    return sorted({
        token for index, token in enumerate(tokens)
        if index and index != script and all(char in SHELL_PUNCTUATION for char in token)
    })


class AcceptError(ValueError):
    """Fail closed; nothing was changed."""


def enforce_row_grammar(plan_text: str, repo: Path) -> None:
    """Refuse the exact row-law findings the canonical enforcer reports.

    A plan can reach accept without a prior lint invocation.  In particular,
    accept scans every line when it selects a row, so a malformed row outside
    ``## Tasks`` must not be invisible here just because it is not the row the
    caller requested.  Calling the enforcer's projection keeps one grammar
    definition instead of two regex implementations that slowly disagree.
    """
    findings = _lint.row_grammar_findings(plan_text, root=repo)
    if not findings:
        return
    summary = "; ".join(
        f"{finding['check']} on line {finding['line']}: {finding['detail']}"
        for finding in findings
    )
    raise AcceptError(
        "the plan's row grammar blocks acceptance; run shadow lint first: " + summary
    )


def proof_argv(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError as exc:
        raise AcceptError(f"the proof command cannot be parsed: {exc}") from exc


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


def atomic_write_text(path: Path, text: str) -> None:
    """Replace one complete PLAN in its own directory; never leave truncation."""
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
    board_root: Path,
) -> None:
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
                root=board_root,
            )
        except _board.BoardError as exc:
            raise AcceptError(f"the owned claim changed before its proof could land: {exc}") from exc
        index_entry = git_completed(
            repo, "ls-files", "--stage", "--", plan_pathspec
        ).stdout.strip()
        atomic_write_text(plan_path, updated_text)
        try:
            added = git_completed(repo, "add", "--", plan_pathspec)
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
                    plan_pathspec,
                )
                if added.returncode == 0
                else added
            )
        except AcceptError:
            restore_plan_index(repo, plan_path, plan_pathspec, original_text, index_entry)
            raise
        if added.returncode or committed.returncode:
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
        _board.release(
            plan_path,
            row_id,
            owner=owner,
            reason="completed",
            resumes=resumes,
            expected_plan=completed_token,
            expected_text=completed_text,
            expected_claim=claim_token,
            root=board_root,
        )


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


def blocking_lint_findings(plan_text: str, root: Path) -> list[dict]:
    """Return blockers the plan enforcer would reject after this flip.

    Acceptance is the only automated writer of a completed task.  Checking
    the exact candidate text here keeps it from committing a PLAN.md whose
    grammar is already rejected, including a blocker introduced by its new
    receipt.
    """
    return [
        finding
        for finding in _lint.lint_plan(plan_text, root=root)
        if finding["severity"] == "blocking"
    ]


def enforce_plan_lint(plan_text: str, root: Path) -> None:
    """Refuse a PLAN.md before accept can spend proof time or commit it."""
    lint_blocks = blocking_lint_findings(plan_text, root)
    if not lint_blocks:
        return
    checks = ", ".join(
        f"{finding['check']} on line {finding['line']}" for finding in lint_blocks
    )
    raise AcceptError(f"the plan is blocked by shadow lint: {checks}; nothing was changed")


def _receipt_stamps(plan_text: str, row_id: str, argv: list[str]) -> list[str]:
    expected = re.escape(shlex.join(argv))
    pattern = re.compile(
        rf"^- (?P<stamp>\d{{4}}-\d{{2}}-\d{{2}}T\d{{2}}:\d{{2}}:\d{{2}}Z) "
        rf"{re.escape(row_id)} PROOF {expected} -> pass \(accept\)$"
    )
    return [
        match.group("stamp")
        for line in _board.section_lines(plan_text, "Progress")
        if (match := pattern.match(line)) is not None
    ]


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
            head_text = head_bytes.decode("utf-8")
            candidate_text = candidate_bytes.decode("utf-8")
        except (_board.BoardError, OSError, UnicodeError):
            raise refusal_error
        if not _exact_interrupted_completion(head_text, candidate_text, row_id):
            raise refusal_error

        repo = Path(token["repo"])
        relative = token["relative"]
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
        if staged_parts[1] == candidate_blob:
            restored = git_completed(
                repo,
                "update-index",
                "--cacheinfo",
                f"{head_parts[0]},{token['blob']},{relative}",
            )
            if restored.returncode:
                raise AcceptError(
                    "interrupted completion index could not be restored; its bytes were preserved"
                )
        atomic_write_text(plan_path, head_text)
        try:
            return _board.committed_plan_snapshot(plan_path)
        except _board.BoardError as exc:
            raise AcceptError(
                f"interrupted completion could not return to committed authority: {exc}"
            ) from exc


def publish_completion(repo: Path, row_id: str, no_push: bool, summary: str) -> int:
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
        print(
            f"shadow accept: {row_id} is flipped and committed locally but the push was "
            "REJECTED — other seats cannot see the completion. On a protected trunk, "
            "land the PLAN.md commit through a pull request; on a race, pull and push again.",
            file=sys.stderr,
        )
        return 3
    print(f"accepted {row_id}: {summary} and pushed to {remote} {remote_ref}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="shadow accept", description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--row", required=True)
    parser.add_argument("--by", required=True, help="stable owner of the existing claim")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--no-push", action="store_true",
                        help="commit without pushing (an unpushed flip is invisible to other seats)")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    selector = args.row.strip()
    try:
        board_root = _board.configured_root()
        _board.assert_entity_board(repo, root=board_root)
        if not _amp.valid_selector(selector):
            raise AcceptError(
                "row must be a four-character ~hash or an exact leading legacy "
                "label like P9a~formats"
            )
        try:
            owner = _board.validate_owner(args.by)
        except _board.BoardError as exc:
            raise AcceptError(f"--by is unsafe: {exc}") from exc
        try:
            requested_plan = repo / "PLAN.md"
            state = _board.entity_state(requested_plan, root=board_root)
            plan_path = _board.canonical_plan(
                requested_plan, repair_missing=True, root=board_root
            )
            _board.assert_entity_board(plan_path.parent, root=board_root)
            state = _board.entity_state(plan_path, root=board_root)
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
            head_token, head_bytes = _board.head_plan_snapshot(plan_path)
            head_plan = _amp._parse(head_bytes.decode("utf-8"))
            row_id = _amp.resolve_row_selector(head_plan, selector)
        except (_board.BoardError, _amp.SelectorError, OSError, UnicodeError) as exc:
            raise AcceptError(
                f"row selector cannot be resolved from committed authority: {exc}"
            ) from exc
        owned_claim(state, row_id, owner)
        try:
            plan_token, plan_bytes = committed_or_recovered_snapshot(plan_path, row_id)
            plan_text = plan_bytes.decode("utf-8")
        except (_board.BoardError, AcceptError, OSError, UnicodeError) as exc:
            raise AcceptError(f"plan must be one committed authority before proof: {exc}") from exc
        if plan_token != head_token:
            raise AcceptError("the committed project plan changed while resolving the row; retry")
        try:
            resolved_again = _amp.resolve_row_selector(_amp._parse(plan_text), selector)
        except _amp.SelectorError as exc:
            raise AcceptError(f"row selector changed while resolving the plan: {exc}") from exc
        if resolved_again != row_id:
            raise AcceptError("row selector changed canonical identity while resolving the plan")
        enforce_row_grammar(plan_text, repo)
        enforce_plan_lint(plan_text, plan_path.parent)
        _, row_line, state, proof, needs = find_row(plan_text, row_id)
        claim = owned_claim(_board.entity_state(plan_path, root=board_root), row_id, owner)
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
            if claim is not None:
                parsed = _amp._parse(plan_text)
                parsed["claimed"] = set()
                try:
                    with _board.project_lock(plan_path):
                        _board.release(
                            plan_path,
                            row_id,
                            owner=owner,
                            reason="completed",
                            resumes=_amp._candidate_ids(parsed),
                            expected_plan=plan_token,
                            expected_text=plan_text,
                            root=board_root,
                        )
                except _board.BoardError as exc:
                    raise AcceptError(
                        f"the completed row's root claim could not reconcile: {exc}"
                    ) from exc
            return publish_completion(
                repo,
                row_id,
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
        enforce_row_grammar(plan_text, repo)
        enforce_plan_lint(plan_text, plan_path.parent)
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
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        updated = completed_plan_text(plan_text, row_id, argv_proof, stamp)
        enforce_plan_lint(updated, plan_path.parent)
        completed_plan = _amp._parse(updated)
        completed_plan["claimed"] = set()
        resumes = _amp._candidate_ids(completed_plan)
        try:
            commit_completed_plan(
                repo,
                plan_path,
                plan_relative,
                row_id,
                owner,
                plan_token,
                plan_text,
                updated,
                resumes,
                board_root,
            )
        except _board.BoardError as exc:
            raise AcceptError(
                f"the project proof landed, but the root claim could not close: {exc}; "
                "repair the root board before taking more work"
            ) from exc
    except AcceptError as exc:
        print(f"shadow accept: {exc}", file=sys.stderr)
        return 1
    return publish_completion(
        repo,
        row_id,
        args.no_push,
        "proof passed in a clean checkout; row flipped with its PROOF line",
    )


if __name__ == "__main__":
    raise SystemExit(main())
