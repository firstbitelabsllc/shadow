from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "dev" / "shadow-acceptance-case.py"
SCHEMA = ROOT / "schemas" / "acceptance-case-manifest.v1.json"


def load_tool():
    spec = importlib.util.spec_from_file_location("shadow_acceptance_case", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("acceptance case tool cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def commitment(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_artifact(root: Path, relative: str, data: bytes) -> dict[str, object]:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {
        "path": relative,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }


def complete_manifest(module, root: Path, case_id: str = "CR-01") -> dict:
    label_codes = ["L01", "L02"]
    document = module.scaffold(case_id)
    document["source"] = {
        "alias": "REPO-001",
        "repository_commitment_sha256": commitment("repository"),
        "immutable_refs_commitment_sha256": commitment("immutable-refs"),
        "license_commitment_sha256": commitment("license"),
        "redistribution_basis_commitment_sha256": commitment(
            "redistribution-basis"
        ),
    }
    document["commitments"] = {
        "eligibility_sha256": commitment("eligibility"),
        "negative_control_sha256": commitment("negative-control"),
        "discriminating_fact_sha256": commitment("discriminating-fact"),
    }
    document["identifiers"] = {
        "action_kinds": [
            {
                "id": "ACTION.HOLD",
                "commitment_sha256": commitment("action-hold"),
            }
        ],
        "target_ids": [],
        "proof_ids": [
            {
                "id": "PROOF.HEAD",
                "commitment_sha256": commitment("proof-head"),
            }
        ],
        "evidence_ids": [
            {
                "id": "EVIDENCE.HEAD",
                "commitment_sha256": commitment("evidence-head"),
            }
        ],
        "risk_ids": [
            {
                "id": "RISK.STALE",
                "commitment_sha256": commitment("risk-stale"),
            }
        ],
    }
    prefix = f"sealed/{case_id}"
    document["source_bundle"] = write_artifact(
        root,
        f"{prefix}/01-source.bin",
        b"\x00source\r\nbytes\xff",
    )
    document["labels"] = [
        {
            "label_code": code,
            "artifact": write_artifact(
                root,
                f"{prefix}/0{index + 2}-label-{code}.bin",
                f"label-{code}".encode("utf-8"),
            ),
        }
        for index, code in enumerate(label_codes)
    ]
    document["adjudication"] = write_artifact(
        root,
        f"{prefix}/04-adjudication.bin",
        b"adjudication",
    )
    document["baselines"] = [
        {
            "condition_code": condition,
            "artifact": write_artifact(
                root,
                f"{prefix}/{index + 5:02}-baseline-{condition}.bin",
                f"baseline-{condition}".encode("utf-8"),
            ),
        }
        for index, condition in enumerate(module.CONDITION_CODES)
    ]
    document["mutation"] = write_artifact(
        root,
        f"{prefix}/11-mutation.bin",
        b"mutation",
    )
    document["mutation_confirmations"] = [
        {
            "label_code": code,
            "artifact": write_artifact(
                root,
                f"{prefix}/{index + 12:02}-confirmation-{code}.bin",
                f"confirmation-{code}".encode("utf-8"),
            ),
        }
        for index, code in enumerate(label_codes)
    ]
    return document


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def snapshot(root: Path) -> dict[str, tuple[str, bytes | str]]:
    result: dict[str, tuple[str, bytes | str]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[relative] = ("symlink", os.readlink(path))
        elif path.is_file():
            result[relative] = ("file", path.read_bytes())
        elif path.is_dir():
            result[relative] = ("directory", b"")
    return result


class AcceptanceCaseManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_tool()

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name).resolve()
        self.document = complete_manifest(self.module, self.root)

    def assert_finding(self, report: dict, code: str) -> None:
        self.assertTrue(
            any(item["code"] == code for item in report["findings"]),
            report,
        )

    def test_complete_case_becomes_ready_and_derives_identity(self) -> None:
        report = self.module.validate_manifest(self.document, self.root)
        self.assertEqual(report["state"], "READY", report)
        self.assertEqual(report["family"], "COLD_RESUME")
        self.assertIsNone(report["critical_attack_class"])
        self.assertEqual(report["scope"], "SEALED_CASE_MECHANICS_ONLY")
        self.assertEqual(report["artifact_count"], 13)
        self.assertEqual(report["findings"], [])

    def test_every_reserved_id_derives_frozen_family_and_attack_class(self) -> None:
        for case_id in self.module.CASE_IDS:
            with self.subTest(case_id=case_id):
                document = complete_manifest(self.module, self.root, case_id)
                report = self.module.validate_manifest(document, self.root)
                self.assertEqual(report["state"], "READY", report)
                self.assertEqual(report["family"], self.module.family_for(case_id))
                self.assertEqual(
                    report["critical_attack_class"],
                    self.module.ATTACK_CLASSES.get(case_id),
                )

    def test_each_required_slot_independently_keeps_the_case_open(self) -> None:
        mutations = [
            (
                "source alias",
                lambda value: value["source"].update(alias=None),
            ),
            *[
                (
                    f"source {key}",
                    lambda value, key=key: value["source"].update({key: None}),
                )
                for key in sorted(self.module.SOURCE_FIELDS - {"alias"})
            ],
            *[
                (
                    f"commitment {key}",
                    lambda value, key=key: value["commitments"].update({key: None}),
                )
                for key in sorted(self.module.COMMITMENT_FIELDS)
            ],
            (
                "source bundle",
                lambda value: value.update(source_bundle=None),
            ),
            (
                "label",
                lambda value: value["labels"].pop(),
            ),
            (
                "adjudication",
                lambda value: value.update(adjudication=None),
            ),
            (
                "baseline",
                lambda value: value["baselines"].pop(),
            ),
            (
                "mutation",
                lambda value: value.update(mutation=None),
            ),
            (
                "mutation confirmation",
                lambda value: value["mutation_confirmations"].pop(),
            ),
        ]
        for name, mutate in mutations:
            with self.subTest(name=name):
                changed = copy.deepcopy(self.document)
                mutate(changed)
                report = self.module.validate_manifest(changed, self.root)
                self.assertEqual(report["state"], "OPEN", report)
                self.assertTrue(report["findings"], report)

    def test_closed_contract_and_duplicate_keys_refuse(self) -> None:
        changes = [
            (
                "missing",
                lambda value: value.pop("mutation"),
                "required",
            ),
            (
                "extra",
                lambda value: value.update(state="READY"),
                "additional",
            ),
            (
                "schema",
                lambda value: value.update(schema="shadow.other"),
                "schema",
            ),
            (
                "corpus",
                lambda value: value.update(corpus_version="acceptance-corpus-v2"),
                "corpus_version",
            ),
            (
                "protocol",
                lambda value: value.update(protocol_commit="0" * 40),
                "protocol_commit",
            ),
            (
                "case",
                lambda value: value.update(case_id="CR-99"),
                "case_id",
            ),
        ]
        for name, mutate, expected in changes:
            with self.subTest(name=name):
                changed = copy.deepcopy(self.document)
                mutate(changed)
                report = self.module.validate_manifest(changed, self.root)
                self.assertEqual(report["state"], "OPEN")
                self.assert_finding(report, expected)

        manifest = self.root / "duplicate.json"
        manifest.write_text('{"schema":"first","schema":"second"}', encoding="utf-8")
        result = run_cli(
            "validate",
            "--manifest",
            str(manifest),
            "--root",
            str(self.root),
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assert_finding(json.loads(result.stdout), "json_duplicate_key")

    def test_malformed_repeated_artifact_paths_refuse_without_crashing(self) -> None:
        changes = [
            lambda value: value["labels"][0]["artifact"].pop("path"),
            lambda value: value["baselines"][0]["artifact"].update(path=None),
            lambda value: value["mutation_confirmations"][0]["artifact"].update(
                path=1
            ),
        ]
        for mutate in changes:
            with self.subTest(mutate=mutate):
                changed = copy.deepcopy(self.document)
                mutate(changed)
                report = self.module.validate_manifest(changed, self.root)
                self.assertEqual(report["state"], "OPEN", report)
                self.assertTrue(report["findings"], report)

    def test_identifiers_codes_and_artifact_paths_are_unique_and_sorted(self) -> None:
        changed = copy.deepcopy(self.document)
        changed["identifiers"]["risk_ids"] = [
            {
                "id": "RISK.Z",
                "commitment_sha256": commitment("risk-z"),
            },
            {
                "id": "RISK.A",
                "commitment_sha256": commitment("risk-a"),
            },
        ]
        self.assert_finding(
            self.module.validate_manifest(changed, self.root),
            "identifier_order",
        )

        changed = copy.deepcopy(self.document)
        changed["labels"].reverse()
        report = self.module.validate_manifest(changed, self.root)
        self.assert_finding(report, "label_order")
        self.assert_finding(report, "artifact_order")

        changed = copy.deepcopy(self.document)
        changed["baselines"][1]["artifact"] = copy.deepcopy(
            changed["baselines"][0]["artifact"]
        )
        self.assert_finding(
            self.module.validate_manifest(changed, self.root),
            "artifact_duplicate",
        )

    def test_mutation_confirmations_match_the_two_label_codes(self) -> None:
        changed = copy.deepcopy(self.document)
        changed["mutation_confirmations"][1]["label_code"] = "L03"
        report = self.module.validate_manifest(changed, self.root)
        self.assertEqual(report["state"], "OPEN")
        self.assert_finding(report, "mutation_confirmation_set")

    def test_unsafe_missing_and_nonregular_artifacts_refuse(self) -> None:
        missing = copy.deepcopy(self.document)
        missing["source_bundle"]["path"] = "sealed/CR-01/missing.bin"
        self.assert_finding(
            self.module.validate_manifest(missing, self.root),
            "artifact_missing",
        )

        for unsafe in (
            "/absolute.bin",
            "../escape.bin",
            "sealed/../escape.bin",
            "sealed\\escape.bin",
        ):
            with self.subTest(path=unsafe):
                changed = copy.deepcopy(self.document)
                changed["source_bundle"]["path"] = unsafe
                self.assert_finding(
                    self.module.validate_manifest(changed, self.root),
                    "artifact_path",
                )

        target = self.root / "real.bin"
        target.write_bytes(b"real")
        symlink = self.root / "sealed" / "CR-01" / "symlink.bin"
        symlink.symlink_to(target)
        changed = copy.deepcopy(self.document)
        changed["source_bundle"] = {
            "path": symlink.relative_to(self.root).as_posix(),
            "sha256": hashlib.sha256(b"real").hexdigest(),
            "bytes": 4,
        }
        self.assert_finding(
            self.module.validate_manifest(changed, self.root),
            "artifact_type",
        )

        directory = self.root / "sealed" / "CR-01" / "directory"
        directory.mkdir()
        changed["source_bundle"] = {
            "path": directory.relative_to(self.root).as_posix(),
            "sha256": hashlib.sha256(b"directory").hexdigest(),
            "bytes": 9,
        }
        self.assert_finding(
            self.module.validate_manifest(changed, self.root),
            "artifact_type",
        )

        if hasattr(os, "mkfifo"):
            fifo = self.root / "sealed" / "CR-01" / "pipe"
            os.mkfifo(fifo)
            changed["source_bundle"] = {
                "path": fifo.relative_to(self.root).as_posix(),
                "sha256": hashlib.sha256(b"pipe").hexdigest(),
                "bytes": 4,
            }
            self.assert_finding(
                self.module.validate_manifest(changed, self.root),
                "artifact_type",
            )

    def test_binary_hashing_uses_raw_bytes_and_checks_size(self) -> None:
        report = self.module.validate_manifest(self.document, self.root)
        self.assertEqual(report["state"], "READY", report)

        changed = copy.deepcopy(self.document)
        changed["source_bundle"]["bytes"] += 1
        self.assert_finding(
            self.module.validate_manifest(changed, self.root),
            "artifact_size",
        )

        changed = copy.deepcopy(self.document)
        changed["source_bundle"]["sha256"] = "f" * 64
        self.assert_finding(
            self.module.validate_manifest(changed, self.root),
            "artifact_digest",
        )

    def test_validation_is_read_only(self) -> None:
        before = snapshot(self.root)
        real_open = self.module.os.open

        def guarded_open(path, flags, *args, **kwargs):
            self.assertEqual(flags & self.module.WRITE_FLAGS, 0, (path, flags))
            return real_open(path, flags, *args, **kwargs)

        with (
            mock.patch.object(self.module.os, "open", side_effect=guarded_open),
            mock.patch.object(
                self.module.os,
                "write",
                side_effect=AssertionError("validation attempted a write"),
            ),
            mock.patch.object(
                self.module.os,
                "unlink",
                side_effect=AssertionError("validation attempted a delete"),
            ),
        ):
            report = self.module.validate_manifest(self.document, self.root)
        self.assertEqual(report["state"], "READY", report)
        self.assertEqual(snapshot(self.root), before)

    def test_validator_imports_no_network_or_subprocess_path(self) -> None:
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        imported = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in (
                node.names
                if isinstance(node, ast.Import)
                else [ast.alias(name=node.module or "")]
            )
        }
        self.assertTrue(
            {"subprocess", "socket", "urllib", "http", "requests"}.isdisjoint(
                imported
            ),
            imported,
        )

    def test_schema_and_runtime_contracts_match(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(set(schema["required"]), self.module.TOP_LEVEL_FIELDS)
        self.assertEqual(set(schema["properties"]), self.module.TOP_LEVEL_FIELDS)
        self.assertEqual(
            schema["properties"]["protocol_commit"]["const"],
            self.module.PROTOCOL_COMMIT,
        )
        self.assertEqual(
            tuple(schema["properties"]["case_id"]["enum"]),
            self.module.CASE_IDS,
        )


class AcceptanceCaseCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_tool()

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name).resolve()

    def test_scaffold_is_deterministic_has_no_derived_state_and_never_overwrites(self) -> None:
        first = self.root / "first.json"
        second = self.root / "second.json"
        for output in (first, second):
            result = run_cli(
                "scaffold",
                "--case-id",
                "AA-03",
                "--output",
                str(output),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)["ok"])
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertFalse(first.read_bytes().endswith(b"\n"))
        document = json.loads(first.read_text(encoding="utf-8"))
        for forbidden in ("state", "family", "critical_attack_class"):
            self.assertNotIn(forbidden, document)

        before = first.read_bytes()
        collision = run_cli(
            "scaffold",
            "--case-id",
            "AA-03",
            "--output",
            str(first),
        )
        self.assertEqual(collision.returncode, 1)
        self.assertEqual(first.read_bytes(), before)

        target = self.root / "target.json"
        target.write_bytes(b"do not touch")
        symlink = self.root / "symlink.json"
        symlink.symlink_to(target)
        symlink_result = run_cli(
            "scaffold",
            "--case-id",
            "AA-03",
            "--output",
            str(symlink),
        )
        self.assertEqual(symlink_result.returncode, 1)
        self.assertEqual(target.read_bytes(), b"do not touch")

        real_parent = self.root / "real-parent"
        real_parent.mkdir()
        parent_symlink = self.root / "parent-symlink"
        parent_symlink.symlink_to(real_parent, target_is_directory=True)
        parent_result = run_cli(
            "scaffold",
            "--case-id",
            "AA-03",
            "--output",
            str(parent_symlink / "manifest.json"),
        )
        self.assertEqual(parent_result.returncode, 2)
        self.assertEqual(list(real_parent.iterdir()), [])

    def test_cli_exit_codes_and_json_output_are_stable(self) -> None:
        document = complete_manifest(self.module, self.root)
        manifest = self.root / "manifest.json"
        manifest.write_bytes(self.module.compact_json(document))
        ready = run_cli(
            "validate",
            "--manifest",
            str(manifest),
            "--root",
            str(self.root),
        )
        self.assertEqual(ready.returncode, 0, ready.stderr)
        self.assertEqual(json.loads(ready.stdout)["state"], "READY")

        incomplete = self.root / "incomplete.json"
        incomplete.write_bytes(self.module.compact_json(self.module.scaffold("CR-01")))
        opened = run_cli(
            "validate",
            "--manifest",
            str(incomplete),
            "--root",
            str(self.root),
        )
        self.assertEqual(opened.returncode, 1, opened.stderr)
        self.assertEqual(json.loads(opened.stdout)["state"], "OPEN")

        missing_root = run_cli(
            "validate",
            "--manifest",
            str(manifest),
            "--root",
            str(self.root / "missing"),
        )
        self.assertEqual(missing_root.returncode, 2, missing_root.stderr)
        self.assertFalse(json.loads(missing_root.stdout)["ok"])

        misuse = run_cli("validate")
        self.assertEqual(misuse.returncode, 2)
        self.assertFalse(json.loads(misuse.stdout)["ok"])

    def test_development_tool_and_schema_are_excluded_from_release_archive(self) -> None:
        for path in (
            "scripts/dev/shadow-acceptance-case.py",
            "schemas/acceptance-case-manifest.v1.json",
        ):
            result = subprocess.run(
                ["git", "check-attr", "export-ignore", "--", path],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(
                result.stdout.strip(),
                f"{path}: export-ignore: set",
            )


if __name__ == "__main__":
    unittest.main()
