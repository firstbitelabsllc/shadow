"""Contract tests for proposal-only Shadow authority acceptance."""

from __future__ import annotations

from contextlib import contextmanager, redirect_stderr, redirect_stdout
import copy
from dataclasses import dataclass
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Callable, Iterator
import unittest
from unittest import mock

from tests.plan_tree_fixture import install_plan_tree
from tests.proc_fixture import git
from tests.test_shadow_host import make_host, make_repo, run_host


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "shadow-host.py"
ACCEPT_SCRIPT = ROOT / "scripts" / "shadow-accept.py"
CLI = ROOT / "bin" / "shadow"
if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))

SPEC = importlib.util.spec_from_file_location("shadow_host_authority_proposal", SCRIPT)
assert SPEC and SPEC.loader
shadow_host = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(shadow_host)

ACCEPT_SPEC = importlib.util.spec_from_file_location(
    "shadow_accept_authority_proposal",
    ACCEPT_SCRIPT,
)
assert ACCEPT_SPEC and ACCEPT_SPEC.loader
shadow_accept = importlib.util.module_from_spec(ACCEPT_SPEC)
sys.modules[ACCEPT_SPEC.name] = shadow_accept
ACCEPT_SPEC.loader.exec_module(shadow_accept)

import shadow_plan_store as plan_store  # noqa: E402
import shadow_root_board as board  # noqa: E402


TARGET_ROW = "~a502"
PREREQUISITE_ROW = "~p001"
FOLLOWUP_ROW = "~b603"
OWNER = "codexdk"
MARKER = "authority-proposal-pass"
FLOOR = 12
SOURCE_REMOTE = "https://github.com/example/proposal-source.git"
SOURCE_IDENTITY = "github.com/example/proposal-source"
PROOF_COMMAND = "python3 proof.py"


def proposal_plan() -> str:
    return f"""# Proposal acceptance

## Brief

- Project: proposal-acceptance
- Mode: ship
- Priority: 1
- Origin: {SOURCE_IDENTITY}

## Tasks

### Protected authority
- [completed] prerequisite is accepted {PREREQUISITE_ROW} | proof: cmd true
- [in_progress] accept the worker proposal {TARGET_ROW} | proof: cmd {PROOF_COMMAND} | marker: {MARKER} | floor: {FLOOR} | needs: {PREREQUISITE_ROW}
- [pending] continue after acceptance {FOLLOWUP_ROW} (DoD) | proof: gate owner review | needs: {TARGET_ROW}

## Contradictions

- none recorded yet.

## Progress

- 2026-08-28T12:00:00Z {PREREQUISITE_ROW} PROOF true -> pass
- 2026-08-28T12:01:00Z NOTE proposal acceptance fixture created
"""


@dataclass
class ProposalWorld:
    root: Path
    home: Path
    source_repo: Path
    plan_path: Path
    board_path: Path
    attempt_path: Path
    proof_sentinel: Path
    entity_id: str
    row_id: str
    owner: str
    marker: str
    floor: int
    source_head: str
    plan_root_sha256: str
    attempt_template: dict[str, object]


@dataclass(frozen=True)
class AuthoritySnapshot:
    plan_root_bytes: bytes
    plan_content: bytes
    board_bytes: bytes
    claim: dict[str, object] | None
    source_head: str
    source_status: str
    plan_objects: dict[str, bytes]


def valid_proof_result(world: ProposalWorld) -> dict[str, object]:
    return {
        "schema": "shadow.proof-result.v1",
        "result": "pass",
        "marker": world.marker,
        "executed": world.floor,
    }


def _proof_script_text(
    sentinel: Path,
    *,
    result: object,
    exit_code: int,
    during_proof: str = "",
    extra_stdout: tuple[str, ...] = (),
) -> str:
    lines = [
        "import json",
        "import os",
        "from pathlib import Path",
        "sentinel = Path(os.environ['SHADOW_PROPOSAL_TEST_SENTINEL'])",
        "with sentinel.open('a', encoding='utf-8') as stream:",
        "    stream.write('ran\\n')",
    ]
    if during_proof:
        lines.append(during_proof.rstrip())
    lines.extend(f"print({line!r})" for line in extra_stdout)
    if result is not None:
        encoded = json.dumps(result, sort_keys=True, separators=(",", ":"))
        lines.append(f"print({encoded!r})")
    lines.append(f"raise SystemExit({exit_code})")
    return "\n".join(lines) + "\n"


def proposal_for(world: ProposalWorld) -> dict[str, object]:
    return {
        "schema": "shadow.authority-proposal.v1",
        "entity_id": world.entity_id,
        "row_id": world.row_id,
        "owner": world.owner,
        "base": {
            "plan_root_sha256": world.plan_root_sha256,
            "source_head": world.source_head,
        },
        "request": {"transition": "complete"},
    }


def attempt_for(world: ProposalWorld) -> dict[str, object]:
    payload = copy.deepcopy(world.attempt_template)
    payload["authority_proposal"] = proposal_for(world)
    return payload


def write_attempt(
    world: ProposalWorld,
    payload: dict[str, object] | None = None,
) -> None:
    value = attempt_for(world) if payload is None else payload
    world.attempt_path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_raw_attempt(world: ProposalWorld, raw: str) -> None:
    world.attempt_path.write_text(raw + "\n", encoding="utf-8")


def _current_plan_root_sha256(world: ProposalWorld) -> str:
    return plan_store.PlanSnapshot.open(world.plan_path).root_sha256


def current_plan_text(world: ProposalWorld) -> str:
    return plan_store.PlanSnapshot.open(world.plan_path).materialize().decode("utf-8")


def publish_plan_text(world: ProposalWorld, text: str) -> None:
    snapshot = plan_store.PlanSnapshot.open(world.plan_path)
    (
        plan_store.PlanTransaction.begin(
            world.plan_path,
            expected_root=snapshot.root_sha256,
        )
        .replace_content(text.encode("utf-8"))
        .publish()
    )


def install_proof(
    world: ProposalWorld,
    *,
    result: object,
    exit_code: int = 0,
    during_proof: str = "",
    extra_stdout: tuple[str, ...] = (),
) -> None:
    proof = world.source_repo / "proof.py"
    proof.write_text(
        _proof_script_text(
            world.proof_sentinel,
            result=result,
            exit_code=exit_code,
            during_proof=during_proof,
            extra_stdout=extra_stdout,
        ),
        encoding="utf-8",
    )
    git(world.source_repo, "add", "proof.py")
    git(world.source_repo, "commit", "-qm", f"proof variant {git(world.source_repo, 'rev-list', '--count', 'HEAD')}")
    world.source_head = git(world.source_repo, "rev-parse", "HEAD")
    world.plan_root_sha256 = _current_plan_root_sha256(world)
    write_attempt(world)


def snapshot_authority(world: ProposalWorld) -> AuthoritySnapshot:
    state = board.entity_state(world.plan_path, home=world.home)
    claims = [] if state is None else state["claims"]
    claim = next(
        (
            copy.deepcopy(item)
            for item in claims
            if item["row"] == world.row_id
        ),
        None,
    )
    object_root = world.plan_path.parent / "PLAN.d" / "objects" / "sha256"
    objects = {
        str(path.relative_to(object_root)): path.read_bytes()
        for path in sorted(object_root.rglob("*"))
        if path.is_file()
    }
    return AuthoritySnapshot(
        plan_root_bytes=world.plan_path.read_bytes(),
        plan_content=plan_store.PlanSnapshot.open(world.plan_path).materialize(),
        board_bytes=world.board_path.read_bytes(),
        claim=claim,
        source_head=git(world.source_repo, "rev-parse", "HEAD"),
        source_status=git(
            world.source_repo,
            "status",
            "--porcelain",
            "--untracked-files=all",
        ),
        plan_objects=objects,
    )


def proof_run_count(world: ProposalWorld) -> int:
    if not world.proof_sentinel.exists():
        return 0
    return len(world.proof_sentinel.read_text(encoding="utf-8").splitlines())


def run_proposal_accept(
    world: ProposalWorld,
    *,
    entity_id: str | None = None,
    row_id: str | None = None,
    owner: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(CLI),
            "accept",
            "--entity",
            entity_id or world.entity_id,
            "--repo",
            str(world.source_repo),
            "--row",
            row_id or world.row_id,
            "--by",
            owner or world.owner,
            "--proposal",
            str(world.attempt_path),
        ],
        env={
            **os.environ,
            "HOME": str(world.home),
            "PYTHONDONTWRITEBYTECODE": "1",
            "SHADOW_PROPOSAL_TEST_SENTINEL": str(world.proof_sentinel),
        },
        capture_output=True,
        text=True,
        check=False,
    )


def plan_replacement_code(
    world: ProposalWorld,
    old: str,
    new: str,
) -> str:
    return "\n".join(
        [
            "import sys",
            f"sys.path.insert(0, {str(ROOT / 'scripts')!r})",
            "import shadow_plan_store as mutation_store",
            f"mutation_plan = Path({str(world.plan_path)!r})",
            "mutation_snapshot = mutation_store.PlanSnapshot.open(mutation_plan)",
            "mutation_text = mutation_snapshot.materialize().decode('utf-8')",
            f"assert {old!r} in mutation_text",
            f"mutation_text = mutation_text.replace({old!r}, {new!r}, 1)",
            "mutation_store.PlanTransaction.begin(",
            "    mutation_plan,",
            "    expected_root=mutation_snapshot.root_sha256,",
            ").replace_content(mutation_text.encode('utf-8')).publish()",
        ]
    )


def claim_release_code(world: ProposalWorld) -> str:
    return "\n".join(
        [
            "import sys",
            f"sys.path.insert(0, {str(ROOT / 'scripts')!r})",
            "import shadow_root_board as mutation_board",
            "mutation_board.release(",
            f"    Path({str(world.plan_path)!r}),",
            f"    {world.row_id!r},",
            f"    owner={world.owner!r},",
            "    reason='handback',",
            "    home=Path(os.environ['HOME']),",
            ")",
        ]
    )


def make_proposal_acceptance(root: Path) -> ProposalWorld:
    home = root / "home"
    home.mkdir()
    source_root = root / "source"
    source_root.mkdir()
    source_repo = make_repo(source_root, ignore_evidence=False)
    git(source_repo, "remote", "add", "origin", SOURCE_REMOTE)
    proof_sentinel = root / "proof-runs.log"
    (source_repo / "proof.py").write_text(
        _proof_script_text(
            proof_sentinel,
            result={
                "schema": "shadow.proof-result.v1",
                "result": "pass",
                "marker": MARKER,
                "executed": FLOOR,
            },
            exit_code=0,
        ),
        encoding="utf-8",
    )
    git(source_repo, "add", "proof.py")
    git(source_repo, "commit", "-qm", "seed structured proof")

    plan_root = home / ".shadow" / "plans" / "proposal-acceptance"
    plan_root.mkdir(parents=True)
    plan_path = install_plan_tree(plan_root, proposal_plan().encode("utf-8"))
    board.reconcile(
        [
            {
                "plan": str(plan_path),
                "project": "proposal-acceptance",
                "priority": 1,
                "candidates": [TARGET_ROW],
            }
        ],
        [],
        home=home,
    )
    board.claim(
        plan_path,
        TARGET_ROW,
        OWNER,
        project="proposal-acceptance",
        priority=1,
        home=home,
    )
    state = board.entity_state(plan_path, home=home)
    assert state is not None and state["entity"] is not None
    source_head = git(source_repo, "rev-parse", "HEAD")
    plan_root_sha256 = plan_store.PlanSnapshot.open(plan_path).root_sha256
    exact_proposal = {
        "schema": "shadow.authority-proposal.v1",
        "entity_id": state["entity"]["id"],
        "row_id": TARGET_ROW,
        "owner": OWNER,
        "base": {
            "plan_root_sha256": plan_root_sha256,
            "source_head": source_head,
        },
        "request": {"transition": "complete"},
    }
    host_root = root / "host"
    host_root.mkdir()
    host = make_host(
        host_root,
        mode="proposal",
        proposal=exact_proposal,
    )
    task = root / "proposal-task.txt"
    task.write_text("Return one bounded authority proposal.\n", encoding="utf-8")
    attempt_path = source_repo / ".shadow" / "evidence" / "attempt.json"
    host_result = run_host(
        source_repo,
        host,
        task,
        attempt_path,
        host="codex",
        authority_proposal=True,
    )
    if host_result.returncode:
        raise AssertionError(host_result.stderr)
    attempt_template = json.loads(attempt_path.read_text(encoding="utf-8"))
    if attempt_template.get("authority_proposal") != exact_proposal:
        raise AssertionError("fake Codex host did not emit the exact bound proposal")

    world = ProposalWorld(
        root=root,
        home=home,
        source_repo=source_repo,
        plan_path=plan_path,
        board_path=home / ".shadow" / "board.json",
        attempt_path=attempt_path,
        proof_sentinel=proof_sentinel,
        entity_id=state["entity"]["id"],
        row_id=TARGET_ROW,
        owner=OWNER,
        marker=MARKER,
        floor=FLOOR,
        source_head=source_head,
        plan_root_sha256=plan_root_sha256,
        attempt_template=attempt_template,
    )
    return world


@contextmanager
def proposal_acceptance() -> Iterator[ProposalWorld]:
    with tempfile.TemporaryDirectory() as dirname:
        yield make_proposal_acceptance(Path(dirname).resolve())


def set_attempt_field(field: str, value: object) -> Callable[[dict[str, object]], None]:
    def mutate(payload: dict[str, object]) -> None:
        payload[field] = value

    return mutate


def remove_attempt_field(field: str) -> Callable[[dict[str, object]], None]:
    def mutate(payload: dict[str, object]) -> None:
        payload.pop(field)

    return mutate


def set_execution_policy_field(
    field: str,
    value: object,
) -> Callable[[dict[str, object]], None]:
    def mutate(payload: dict[str, object]) -> None:
        policy = payload["execution_policy"]
        assert isinstance(policy, dict)
        policy[field] = value

    return mutate


def valid_proposal() -> dict[str, object]:
    return {
        "schema": "shadow.authority-proposal.v1",
        "entity_id": "a" * 64,
        "row_id": "~a502",
        "owner": "codexdk",
        "base": {
            "plan_root_sha256": "b" * 64,
            "source_head": "c" * 40,
        },
        "request": {"transition": "complete"},
    }


def host_receipt(*, proposal: object = None, include_proposal: bool = True) -> dict[str, object]:
    receipt: dict[str, object] = {
        "schema": "shadow.host-receipt.v1",
        "task_id": "bounded-task",
        "status": "ok",
        "summary": "bounded task completed",
        "proof_ref": "bounded-proof",
        "changed_paths": [] if include_proposal else ["result.txt"],
        "tests": [{"name": "bounded test", "status": "pass"}],
    }
    if include_proposal:
        receipt["authority_proposal"] = valid_proposal() if proposal is None else proposal
    return receipt


class AuthorityProposalContract(unittest.TestCase):
    def validate(
        self,
        receipt: dict[str, object],
        *,
        host: str = "codex",
        authority_proposal: bool = True,
    ) -> dict[str, object]:
        return shadow_host.validate_host_receipt(
            receipt,
            "bounded-task",
            [] if authority_proposal else ["result.txt"],
            host,
            authority_proposal=authority_proposal,
        )

    def assert_invalid(self, receipt: dict[str, object]) -> None:
        with self.assertRaises(shadow_host.HostError) as raised:
            self.validate(receipt)
        self.assertEqual(raised.exception.kind, "host_receipt_invalid")

    def test_duplicate_keys_are_refused_at_every_json_extraction_path(self) -> None:
        raw = json.dumps(
            host_receipt(),
            sort_keys=True,
            separators=(",", ":"),
        )
        replacements = (
            (
                '"schema":"shadow.host-receipt.v1"',
                '"schema":"duplicate","schema":"shadow.host-receipt.v1"',
            ),
            (
                '"owner":"codexdk"',
                '"owner":"other-seat","owner":"codexdk"',
            ),
            (
                f'"plan_root_sha256":"{"b" * 64}"',
                f'"plan_root_sha256":"{"d" * 64}",'
                f'"plan_root_sha256":"{"b" * 64}"',
            ),
            (
                '"transition":"complete"',
                '"transition":"blocked","transition":"complete"',
            ),
        )

        wrappers = {
            "fenced": lambda value: f"```json\n{value}\n```",
            "line": lambda value: f"not json\n{value}\nnot json",
            "document": lambda value: value,
            "raw decoder": lambda value: f"prefix {value} suffix",
        }

        for needle, replacement in replacements:
            duplicated = raw.replace(needle, replacement, 1)
            for extraction, wrap in wrappers.items():
                with self.subTest(duplicate=needle, extraction=extraction):
                    with self.assertRaises(shadow_host.HostError):
                        shadow_host.extract_host_receipt([wrap(duplicated)])

    def test_exact_proposal_is_normalized_and_preserved(self) -> None:
        proposal = valid_proposal()

        normalized = self.validate(host_receipt(proposal=proposal))

        self.assertEqual(normalized["authority_proposal"], proposal)

    def test_legacy_receipt_contract_is_unchanged_when_proposal_is_absent(self) -> None:
        normalized = self.validate(
            host_receipt(include_proposal=False),
            authority_proposal=False,
        )

        self.assertEqual(
            normalized,
            {
                "status": "ok",
                "summary": "bounded task completed",
                "proof_ref": "bounded-proof",
                "changed_paths": ["result.txt"],
                "tests": [{"name": "bounded test", "status": "pass"}],
            },
        )

    def test_non_codex_hosts_cannot_emit_authority_proposals(self) -> None:
        for host in shadow_host.HOSTS - {"codex"}:
            with self.subTest(host=host), self.assertRaises(
                shadow_host.HostError
            ) as raised:
                self.validate(host_receipt(), host=host)
            self.assertEqual(raised.exception.kind, "host_receipt_invalid")

    def test_codex_cannot_emit_a_proposal_without_explicit_proposal_mode(self) -> None:
        with self.assertRaises(shadow_host.HostError) as raised:
            self.validate(
                host_receipt(),
                authority_proposal=False,
            )
        self.assertEqual(raised.exception.kind, "host_receipt_invalid")

    def test_attempt_receipt_carries_only_a_present_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            proposal_root = root / "proposal"
            proposal_root.mkdir()
            proposal_repo = make_repo(proposal_root)
            proposal_host = make_host(proposal_root, mode="proposal")
            task = root / "proposal-task.txt"
            task.write_text("Do the bounded task.\n", encoding="utf-8")
            proposal_output = proposal_repo / ".shadow" / "evidence" / "attempt.json"

            proposal_result = run_host(
                proposal_repo,
                proposal_host,
                task,
                proposal_output,
                host="codex",
                authority_proposal=True,
            )

            legacy_root = root / "legacy"
            legacy_root.mkdir()
            legacy_repo = make_repo(legacy_root)
            legacy_host = make_host(legacy_root)
            legacy_output = legacy_repo / ".shadow" / "evidence" / "attempt.json"
            legacy_result = run_host(
                legacy_repo,
                legacy_host,
                task,
                legacy_output,
            )

            proposal_attempt = json.loads(proposal_output.read_text(encoding="utf-8"))
            legacy_attempt = json.loads(legacy_output.read_text(encoding="utf-8"))

        self.assertEqual(proposal_result.returncode, 0, proposal_result.stderr)
        self.assertEqual(legacy_result.returncode, 0, legacy_result.stderr)
        self.assertEqual(proposal_attempt["authority_proposal"], valid_proposal())
        self.assertIs(proposal_attempt["authority_proposal_mode"], True)
        self.assertIs(legacy_attempt["authority_proposal_mode"], False)
        self.assertNotIn("authority_proposal", legacy_attempt)

    def test_unknown_or_missing_fields_are_refused_at_every_level(self) -> None:
        cases: list[dict[str, object]] = []

        unknown_top = valid_proposal()
        unknown_top["proof"] = "cmd true"
        cases.append(unknown_top)
        missing_top = valid_proposal()
        missing_top.pop("owner")
        cases.append(missing_top)

        unknown_base = valid_proposal()
        assert isinstance(unknown_base["base"], dict)
        unknown_base["base"]["marker"] = "worker-chosen"
        cases.append(unknown_base)
        missing_base = valid_proposal()
        assert isinstance(missing_base["base"], dict)
        missing_base["base"].pop("source_head")
        cases.append(missing_base)

        unknown_request = valid_proposal()
        assert isinstance(unknown_request["request"], dict)
        unknown_request["request"]["floor"] = 0
        cases.append(unknown_request)
        missing_request = valid_proposal()
        assert isinstance(missing_request["request"], dict)
        missing_request["request"].pop("transition")
        cases.append(missing_request)

        for proposal in cases:
            with self.subTest(proposal=proposal):
                self.assert_invalid(host_receipt(proposal=proposal))

    def test_hashes_and_row_id_are_exact_lowercase_shapes(self) -> None:
        mutations = (
            ("entity_id", "a" * 63),
            ("entity_id", "A" * 64),
            ("entity_id", "g" * 64),
            ("row_id", "~a50"),
            ("row_id", "~A502"),
            ("plan_root_sha256", "b" * 63),
            ("plan_root_sha256", "B" * 64),
            ("source_head", "c" * 39),
            ("source_head", "C" * 40),
        )

        for field, value in mutations:
            with self.subTest(field=field, value=value):
                proposal = valid_proposal()
                if field in {"plan_root_sha256", "source_head"}:
                    assert isinstance(proposal["base"], dict)
                    proposal["base"][field] = value
                else:
                    proposal[field] = value
                self.assert_invalid(host_receipt(proposal=proposal))

    def test_private_secret_or_control_owner_values_are_refused(self) -> None:
        for owner in (
            "/Users/person/private",
            "token=" + "gh" + "p_12345678901234567890",
            "codex\nseat",
            " codexdk",
        ):
            with self.subTest(owner=owner):
                proposal = valid_proposal()
                proposal["owner"] = owner
                self.assert_invalid(host_receipt(proposal=proposal))

    def test_only_complete_transition_is_allowed(self) -> None:
        for transition in ("completed", "blocked", "return", "reopen", "publish"):
            with self.subTest(transition=transition):
                proposal = copy.deepcopy(valid_proposal())
                assert isinstance(proposal["request"], dict)
                proposal["request"]["transition"] = transition
                self.assert_invalid(host_receipt(proposal=proposal))


class ProposalAcceptance(unittest.TestCase):
    def assert_refused_unchanged(
        self,
        world: ProposalWorld,
        result: subprocess.CompletedProcess[str],
        before: AuthoritySnapshot,
        *,
        proof_runs: int,
        expected_state: str = "in_progress",
    ) -> None:
        self.assertEqual(proof_run_count(world), proof_runs)
        self.assertEqual(snapshot_authority(world), before)
        plan_text = current_plan_text(world)
        self.assertIn(
            f"- [{expected_state}] accept the worker proposal {world.row_id}",
            plan_text,
        )
        self.assertNotIn(f"{world.row_id} PROOF ", plan_text)
        self.assertNotIn(f"{world.row_id} SOURCE ", plan_text)
        self.assertEqual(
            result.returncode,
            1,
            result.stdout + result.stderr,
        )

    def test_strict_codex_ok_attempt_is_required_before_proof(self) -> None:
        mutations = (
            ("schema", set_attempt_field("schema", "shadow.host-attempt.v0")),
            ("revision", set_attempt_field("revision", 2)),
            ("boolean revision", set_attempt_field("revision", True)),
            ("host", set_attempt_field("host", "cursor")),
            (
                "proposal mode",
                set_attempt_field("authority_proposal_mode", False),
            ),
            ("status", set_attempt_field("status", "blocked")),
            ("host exit", set_attempt_field("host_exit_code", 1)),
            ("boolean host exit", set_attempt_field("host_exit_code", False)),
            ("timeout", set_attempt_field("timed_out", True)),
            ("reviewed", set_attempt_field("accepted_by_lead", True)),
            ("reviewable", set_attempt_field("unreviewed_claim", False)),
            ("projection", set_attempt_field("projection_is_usage", True)),
            (
                "blocked detail",
                set_attempt_field(
                    "blocked",
                    {"kind": "host_failed", "detail": "host failed"},
                ),
            ),
            ("missing proposal", remove_attempt_field("authority_proposal")),
            ("unknown field", set_attempt_field("worker_markdown", "completed")),
            (
                "wrong work class",
                set_execution_policy_field("work_class", "authority"),
            ),
            (
                "wrong requested model",
                set_execution_policy_field("requested_model", "worker-selected"),
            ),
            (
                "claimed observed model",
                set_execution_policy_field("observed_model", "gpt-5.6-sol"),
            ),
            (
                "wrong delegation",
                set_execution_policy_field("delegation", "optional"),
            ),
            (
                "wrong child capability",
                set_execution_policy_field(
                    "requested_child_capability",
                    "multi_agent",
                ),
            ),
            (
                "claimed child spans",
                set_execution_policy_field("observed_child_spans", []),
            ),
            (
                "wrong observation",
                set_execution_policy_field("observation", "worker-verified"),
            ),
            (
                "wrong command shape",
                set_attempt_field(
                    "command_shape",
                    [
                        "exec",
                        "--disable",
                        "multi_agent",
                        "--model",
                        "--json",
                        "--ephemeral",
                        "--sandbox",
                        "danger-full-access",
                        "-C",
                        "--output-last-message",
                    ],
                ),
            ),
        )

        for label, mutate in mutations:
            with self.subTest(mutant=label), proposal_acceptance() as world:
                payload = attempt_for(world)
                mutate(payload)
                write_attempt(world, payload)
                before = snapshot_authority(world)

                result = run_proposal_accept(world)

                self.assert_refused_unchanged(
                    world,
                    result,
                    before,
                    proof_runs=0,
                )

    def test_duplicate_key_codex_attempt_is_refused_before_proof(self) -> None:
        with proposal_acceptance() as world:
            raw = json.dumps(
                attempt_for(world),
                sort_keys=True,
                separators=(",", ":"),
            )
            duplicated = raw.replace(
                '"status":"ok"',
                '"status":"blocked","status":"ok"',
                1,
            )
            write_raw_attempt(world, duplicated)
            before = snapshot_authority(world)

            result = run_proposal_accept(world)

            self.assert_refused_unchanged(
                world,
                result,
                before,
                proof_runs=0,
            )

    def test_proposal_binding_mutants_refuse_before_proof(self) -> None:
        cases = (
            "proposal entity",
            "proposal row",
            "proposal owner",
            "command entity",
            "command row",
            "command owner",
            "unclaimed row",
        )
        for case in cases:
            with self.subTest(mutant=case), proposal_acceptance() as world:
                payload = attempt_for(world)
                proposal = payload["authority_proposal"]
                assert isinstance(proposal, dict)
                run_arguments: dict[str, str] = {}
                if case == "proposal entity":
                    proposal["entity_id"] = "f" * 64
                elif case == "proposal row":
                    proposal["row_id"] = FOLLOWUP_ROW
                elif case == "proposal owner":
                    proposal["owner"] = "other-seat"
                elif case == "command entity":
                    run_arguments["entity_id"] = "f" * 64
                elif case == "command row":
                    run_arguments["row_id"] = FOLLOWUP_ROW
                elif case == "command owner":
                    run_arguments["owner"] = "other-seat"
                else:
                    board.release(
                        world.plan_path,
                        world.row_id,
                        owner=world.owner,
                        reason="handback",
                        home=world.home,
                    )
                write_attempt(world, payload)
                before = snapshot_authority(world)

                result = run_proposal_accept(world, **run_arguments)

                self.assert_refused_unchanged(
                    world,
                    result,
                    before,
                    proof_runs=0,
                )

    def test_stale_plan_root_refuses_before_proof(self) -> None:
        with proposal_acceptance() as world:
            changed = current_plan_text(world).replace(
                "proposal acceptance fixture created",
                "proposal acceptance fixture changed",
                1,
            )
            publish_plan_text(world, changed)
            before = snapshot_authority(world)

            result = run_proposal_accept(world)

            self.assert_refused_unchanged(
                world,
                result,
                before,
                proof_runs=0,
            )

    def test_source_head_change_after_proposal_refuses_before_proof(self) -> None:
        with proposal_acceptance() as world:
            (world.source_repo / "after-proposal.txt").write_text(
                "new committed head\n",
                encoding="utf-8",
            )
            git(world.source_repo, "add", "after-proposal.txt")
            git(world.source_repo, "commit", "-qm", "advance after proposal")
            before = snapshot_authority(world)

            result = run_proposal_accept(world)

            self.assert_refused_unchanged(
                world,
                result,
                before,
                proof_runs=0,
            )

    def test_non_evidence_source_dirt_still_refuses_before_proof(self) -> None:
        for kind in ("untracked", "tracked", "ignored"):
            with self.subTest(kind=kind), proposal_acceptance() as world:
                if kind == "untracked":
                    (world.source_repo / "ordinary-dirt.txt").write_text(
                        "not proposal evidence\n",
                        encoding="utf-8",
                    )
                elif kind == "tracked":
                    (world.source_repo / "result.txt").write_text(
                        "tracked dirt\n",
                        encoding="utf-8",
                    )
                else:
                    (world.source_repo / ".env").write_text(
                        "ignored dirt\n",
                        encoding="utf-8",
                    )
                before = snapshot_authority(world)

                result = run_proposal_accept(world)

                self.assert_refused_unchanged(
                    world,
                    result,
                    before,
                    proof_runs=0,
                )

    def test_proposal_requires_exact_machine_local_selectors(self) -> None:
        with proposal_acceptance() as world:
            commands = (
                (
                    "missing entity",
                    [
                        str(CLI),
                        "accept",
                        "--repo",
                        str(world.source_repo),
                        "--row",
                        world.row_id,
                        "--by",
                        world.owner,
                        "--proposal",
                        str(world.attempt_path),
                    ],
                ),
                (
                    "missing repo",
                    [
                        str(CLI),
                        "accept",
                        "--entity",
                        world.entity_id,
                        "--row",
                        world.row_id,
                        "--by",
                        world.owner,
                        "--proposal",
                        str(world.attempt_path),
                    ],
                ),
                (
                    "no push",
                    [
                        str(CLI),
                        "accept",
                        "--entity",
                        world.entity_id,
                        "--repo",
                        str(world.source_repo),
                        "--row",
                        world.row_id,
                        "--by",
                        world.owner,
                        "--proposal",
                        str(world.attempt_path),
                        "--no-push",
                    ],
                ),
            )
            for label, command in commands:
                with self.subTest(mutant=label):
                    before = snapshot_authority(world)
                    result = subprocess.run(
                        command,
                        env={
                            **os.environ,
                            "HOME": str(world.home),
                            "PYTHONDONTWRITEBYTECODE": "1",
                            "SHADOW_PROPOSAL_TEST_SENTINEL": str(
                                world.proof_sentinel
                            ),
                        },
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assert_refused_unchanged(
                        world,
                        result,
                        before,
                        proof_runs=0,
                    )

    def test_legacy_local_accept_cannot_downgrade_a_proposal_row(self) -> None:
        with proposal_acceptance() as world:
            before = snapshot_authority(world)
            result = subprocess.run(
                [
                    str(CLI),
                    "accept",
                    "--entity",
                    world.entity_id,
                    "--repo",
                    str(world.source_repo),
                    "--row",
                    world.row_id,
                    "--by",
                    world.owner,
                ],
                env={
                    **os.environ,
                    "HOME": str(world.home),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "SHADOW_PROPOSAL_TEST_SENTINEL": str(world.proof_sentinel),
                },
                capture_output=True,
                text=True,
                check=False,
            )

            self.assert_refused_unchanged(
                world,
                result,
                before,
                proof_runs=0,
            )

    def test_git_backed_authority_refuses_proposal_enabled_rows(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            home = root / "home"
            home.mkdir()
            source_root = root / "source"
            source_root.mkdir()
            repo = make_repo(source_root)
            git(repo, "remote", "add", "origin", SOURCE_REMOTE)
            sentinel = root / "git-proof-runs.log"
            (repo / "proof.py").write_text(
                _proof_script_text(
                    sentinel,
                    result={
                        "schema": "shadow.proof-result.v1",
                        "result": "pass",
                        "marker": MARKER,
                        "executed": FLOOR,
                    },
                    exit_code=0,
                ),
                encoding="utf-8",
            )
            plan_path = repo / "PLAN.md"
            plan_path.write_text(proposal_plan(), encoding="utf-8")
            git(repo, "add", "PLAN.md", "proof.py")
            git(repo, "commit", "-qm", "seed proposal-enabled Git plan")
            board.reconcile(
                [
                    {
                        "plan": str(plan_path),
                        "project": "proposal-git",
                        "priority": 1,
                        "candidates": [TARGET_ROW],
                    }
                ],
                [],
                home=home,
            )
            board.claim(
                plan_path,
                TARGET_ROW,
                OWNER,
                project="proposal-git",
                priority=1,
                home=home,
            )
            state = board.entity_state(plan_path, home=home)
            assert state is not None and state["entity"] is not None
            attempt_path = repo / ".shadow" / "evidence" / "attempt.json"
            attempt_path.parent.mkdir(parents=True)
            attempt_path.write_text("{}\n", encoding="utf-8")
            before_plan = plan_path.read_bytes()
            before_board = (home / ".shadow" / "board.json").read_bytes()
            commands = (
                [
                    str(CLI),
                    "accept",
                    "--repo",
                    str(repo),
                    "--row",
                    TARGET_ROW,
                    "--by",
                    OWNER,
                ],
                [
                    str(CLI),
                    "accept",
                    "--entity",
                    state["entity"]["id"],
                    "--repo",
                    str(repo),
                    "--row",
                    TARGET_ROW,
                    "--by",
                    OWNER,
                    "--proposal",
                    str(attempt_path),
                ],
            )
            for command in commands:
                with self.subTest(command=command):
                    result = subprocess.run(
                        command,
                        env={
                            **os.environ,
                            "HOME": str(home),
                            "PYTHONDONTWRITEBYTECODE": "1",
                            "SHADOW_PROPOSAL_TEST_SENTINEL": str(sentinel),
                        },
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(
                        result.returncode,
                        1,
                        result.stdout + result.stderr,
                    )
                    self.assertFalse(sentinel.exists())
                    self.assertEqual(plan_path.read_bytes(), before_plan)
                    self.assertEqual(
                        (home / ".shadow" / "board.json").read_bytes(),
                        before_board,
                    )
                    current = board.entity_state(plan_path, home=home)
                    assert current is not None
                    self.assertEqual(
                        [claim["row"] for claim in current["claims"]],
                        [TARGET_ROW],
                    )

    def test_blocked_or_completed_rows_cannot_enter_proposal_acceptance(self) -> None:
        for state in ("blocked", "completed"):
            with self.subTest(state=state), proposal_acceptance() as world:
                changed = current_plan_text(world).replace(
                    f"- [in_progress] accept the worker proposal {world.row_id}",
                    f"- [{state}] accept the worker proposal {world.row_id}",
                    1,
                )
                publish_plan_text(world, changed)
                world.plan_root_sha256 = _current_plan_root_sha256(world)
                write_attempt(world)
                before = snapshot_authority(world)

                result = run_proposal_accept(world)

                self.assert_refused_unchanged(
                    world,
                    result,
                    before,
                    proof_runs=0,
                    expected_state=state,
                )

    def test_attempt_path_must_stay_under_regular_evidence_files(self) -> None:
        with proposal_acceptance() as world:
            outside = world.root / "outside-attempt.json"
            outside.write_text(
                world.attempt_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            link = world.source_repo / ".shadow" / "evidence" / "attempt-link.json"
            link.symlink_to(outside)
            for label, path in (("outside", outside), ("symlink", link)):
                with self.subTest(mutant=label):
                    before = snapshot_authority(world)
                    original = world.attempt_path
                    world.attempt_path = path
                    try:
                        result = run_proposal_accept(world)
                    finally:
                        world.attempt_path = original
                    self.assert_refused_unchanged(
                        world,
                        result,
                        before,
                        proof_runs=0,
                    )

    def test_proposal_cannot_choose_authority_evidence(self) -> None:
        evidence = {
            "markdown": "- [completed] forged",
            "proof": "cmd true",
            "marker": "worker-marker",
            "floor": 0,
            "timestamp": "2026-08-28T12:02:00Z",
        }
        for field, value in evidence.items():
            with self.subTest(field=field), proposal_acceptance() as world:
                payload = attempt_for(world)
                proposal = payload["authority_proposal"]
                assert isinstance(proposal, dict)
                proposal[field] = value
                write_attempt(world, payload)
                before = snapshot_authority(world)

                result = run_proposal_accept(world)

                self.assert_refused_unchanged(
                    world,
                    result,
                    before,
                    proof_runs=0,
                )

    def test_proof_process_and_result_schema_mutants_preserve_authority(self) -> None:
        cases = (
            "nonzero exit",
            "missing result object",
            "wrong schema",
            "failed result",
            "missing field",
            "extra field",
            "boolean executed",
            "string executed",
            "float executed",
            "prose plus result",
            "two result objects",
        )
        for case in cases:
            with self.subTest(mutant=case), proposal_acceptance() as world:
                proof_result: object = valid_proof_result(world)
                exit_code = 0
                extra_stdout: tuple[str, ...] = ()
                if case == "nonzero exit":
                    exit_code = 1
                elif case == "missing result object":
                    proof_result = None
                elif case == "wrong schema":
                    assert isinstance(proof_result, dict)
                    proof_result["schema"] = "shadow.proof-result.v0"
                elif case == "failed result":
                    assert isinstance(proof_result, dict)
                    proof_result["result"] = "fail"
                elif case == "missing field":
                    assert isinstance(proof_result, dict)
                    proof_result.pop("executed")
                elif case == "extra field":
                    assert isinstance(proof_result, dict)
                    proof_result["summary"] = "worker-selected evidence"
                elif case == "boolean executed":
                    assert isinstance(proof_result, dict)
                    proof_result["executed"] = True
                elif case == "string executed":
                    assert isinstance(proof_result, dict)
                    proof_result["executed"] = str(world.floor)
                elif case == "float executed":
                    assert isinstance(proof_result, dict)
                    proof_result["executed"] = float(world.floor)
                elif case == "prose plus result":
                    extra_stdout = ("proof passed",)
                else:
                    extra_stdout = (
                        json.dumps(
                            proof_result,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    )
                install_proof(
                    world,
                    result=proof_result,
                    exit_code=exit_code,
                    extra_stdout=extra_stdout,
                )
                before = snapshot_authority(world)

                result = run_proposal_accept(world)

                self.assert_refused_unchanged(
                    world,
                    result,
                    before,
                    proof_runs=1,
                )

    def test_marker_and_floor_are_authority_owned(self) -> None:
        cases = ("wrong marker", "zero executed", "below floor")
        for case in cases:
            with self.subTest(mutant=case), proposal_acceptance() as world:
                proof_result = valid_proof_result(world)
                if case == "wrong marker":
                    proof_result["marker"] = "worker-marker"
                elif case == "zero executed":
                    proof_result["executed"] = 0
                else:
                    proof_result["executed"] = world.floor - 1
                install_proof(world, result=proof_result)
                before = snapshot_authority(world)

                result = run_proposal_accept(world)

                self.assert_refused_unchanged(
                    world,
                    result,
                    before,
                    proof_runs=1,
                )

    def test_exact_floor_accepts_and_synthesizes_canonical_receipts(self) -> None:
        with proposal_acceptance() as world:
            before = snapshot_authority(world)

            result = run_proposal_accept(world)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(proof_run_count(world), 1)
            after = snapshot_authority(world)
            self.assertNotEqual(after.plan_root_bytes, before.plan_root_bytes)
            self.assertNotEqual(after.board_bytes, before.board_bytes)
            self.assertEqual(after.source_head, before.source_head)
            self.assertEqual(
                after.source_status,
                "?? .shadow/evidence/attempt.json",
            )
            self.assertIsNone(after.claim)
            text = after.plan_content.decode("utf-8")
            self.assertIn(
                f"- [completed] accept the worker proposal {world.row_id}",
                text,
            )
            proof_receipts = [
                line
                for line in text.splitlines()
                if f"{world.row_id} PROOF " in line
            ]
            source_receipts = [
                line
                for line in text.splitlines()
                if f"{world.row_id} SOURCE " in line
            ]
            self.assertEqual(len(proof_receipts), 1)
            self.assertIn(
                f"{world.row_id} PROOF {PROOF_COMMAND} -> pass (accept)",
                proof_receipts[0],
            )
            self.assertEqual(len(source_receipts), 1)
            self.assertIn(
                f"{world.row_id} SOURCE {SOURCE_IDENTITY} HEAD "
                f"{before.source_head} -> proof and final lint (accept)",
                source_receipts[0],
            )

    def test_proof_time_authority_weakening_is_refused_and_restored(self) -> None:
        cases = (
            "proof command",
            "marker",
            "floor",
            "dependency",
            "contradiction",
            "claim",
        )
        for case in cases:
            with self.subTest(mutant=case), proposal_acceptance() as world:
                proof_result = valid_proof_result(world)
                if case == "proof command":
                    mutation = plan_replacement_code(
                        world,
                        f"proof: cmd {PROOF_COMMAND}",
                        "proof: cmd true",
                    )
                elif case == "marker":
                    mutation = plan_replacement_code(
                        world,
                        f"marker: {world.marker}",
                        "marker: worker-marker",
                    )
                    proof_result["marker"] = "worker-marker"
                elif case == "floor":
                    mutation = plan_replacement_code(
                        world,
                        f"floor: {world.floor}",
                        "floor: 0",
                    )
                    proof_result["executed"] = 0
                elif case == "dependency":
                    mutation = plan_replacement_code(
                        world,
                        f"- [completed] prerequisite is accepted {PREREQUISITE_ROW}",
                        f"- [pending] prerequisite is accepted {PREREQUISITE_ROW}",
                    )
                elif case == "contradiction":
                    mutation = plan_replacement_code(
                        world,
                        "- none recorded yet.",
                        f"- {world.row_id} proof authority changed during execution",
                    )
                else:
                    mutation = claim_release_code(world)
                install_proof(
                    world,
                    result=proof_result,
                    during_proof=mutation,
                )
                before = snapshot_authority(world)

                result = run_proposal_accept(world)

                self.assert_refused_unchanged(
                    world,
                    result,
                    before,
                    proof_runs=1,
                )

    def test_second_authority_write_failure_restores_exact_root_and_claim(self) -> None:
        with proposal_acceptance() as world:
            before = snapshot_authority(world)

            def fail_after_plan_publication(*args: object, **kwargs: object) -> None:
                self.assertNotEqual(world.plan_path.read_bytes(), before.plan_root_bytes)
                raise shadow_accept._board.BoardError("injected board finalization failure")

            output = io.StringIO()
            argv = [
                "--entity",
                world.entity_id,
                "--repo",
                str(world.source_repo),
                "--row",
                world.row_id,
                "--by",
                world.owner,
                "--proposal",
                str(world.attempt_path),
            ]
            with (
                mock.patch.dict(
                    os.environ,
                    {
                        "HOME": str(world.home),
                        "PYTHONDONTWRITEBYTECODE": "1",
                        "SHADOW_PROPOSAL_TEST_SENTINEL": str(world.proof_sentinel),
                    },
                ),
                mock.patch.object(
                    shadow_accept._board,
                    "release",
                    side_effect=fail_after_plan_publication,
                ) as release,
                redirect_stdout(output),
                redirect_stderr(output),
            ):
                try:
                    result = shadow_accept.main(argv)
                except SystemExit as exc:
                    result = int(exc.code)

            self.assertEqual(proof_run_count(world), 1)
            self.assertEqual(snapshot_authority(world), before)
            self.assertEqual(release.call_count, 1)
            self.assertEqual(result, 1, output.getvalue())
