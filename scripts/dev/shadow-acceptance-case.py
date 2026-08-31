#!/usr/bin/env python3
"""Scaffold and validate one sealed independent-acceptance case."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any
import unicodedata


MANIFEST_SCHEMA = "shadow.acceptance-case-manifest.v1"
VALIDATION_SCHEMA = "shadow.acceptance-case-validation.v1"
SCAFFOLD_SCHEMA = "shadow.acceptance-case-scaffold.v1"
COMMAND_ERROR_SCHEMA = "shadow.acceptance-case-command-error.v1"
CORPUS_VERSION = "acceptance-corpus-v1"
PROTOCOL_COMMIT = "225c5a6f963381ff71284cef01fb6c5847977b06"
CASE_IDS = tuple(
    [
        *(f"CR-{index:02}" for index in range(1, 13)),
        *(f"PR-{index:02}" for index in range(1, 13)),
        *(f"AA-{index:02}" for index in range(1, 13)),
    ]
)
ATTACK_CLASSES = {
    "AA-01": "STALE_EVIDENCE",
    "AA-02": "FORGED_EVIDENCE",
    "AA-03": "SELF_MODIFYING_POLICY",
    "AA-04": "WRONG_SUBJECT_SHA",
    "AA-05": "UNTRUSTED_WORKFLOW_CHANGE",
    "AA-06": "PATH_SCOPE_BYPASS",
    "AA-07": "SYMLINK_OR_SUBMODULE_ESCAPE",
    "AA-08": "SKIPPED_REQUIRED_GATE",
    "AA-09": "WRONG_PROOF_SURFACE",
    "AA-10": "STALE_BASE_POLICY",
    "AA-11": "PARTIAL_OR_TRUNCATED_RECEIPT",
    "AA-12": "AMBIGUOUS_REPOSITORY_IDENTITY",
}
TOP_LEVEL_FIELDS = {
    "schema",
    "corpus_version",
    "protocol_commit",
    "case_id",
    "source",
    "commitments",
    "identifiers",
    "source_bundle",
    "labels",
    "adjudication",
    "baselines",
    "mutation",
    "mutation_confirmations",
}
SOURCE_FIELDS = {
    "alias",
    "repository_commitment_sha256",
    "immutable_refs_commitment_sha256",
    "license_commitment_sha256",
    "redistribution_basis_commitment_sha256",
}
COMMITMENT_FIELDS = {
    "eligibility_sha256",
    "negative_control_sha256",
    "discriminating_fact_sha256",
}
IDENTIFIER_FIELDS = {
    "action_kinds",
    "target_ids",
    "proof_ids",
    "evidence_ids",
    "risk_ids",
}
MAX_MANIFEST_BYTES = 1_000_000
MAX_ARTIFACT_BYTES = 32_000_000
MAX_JSON_DEPTH = 24
READ_CHUNK_BYTES = 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SOURCE_ALIAS_RE = re.compile(r"^REPO-[0-9]{3}$")
OPAQUE_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_-]{2,31}$")
IDENTIFIER_RE = re.compile(r"^[A-Z][A-Z0-9._:-]{0,63}$")
CONDITION_CODES = tuple(f"C{index:02}" for index in range(1, 7))
WRITE_FLAGS = (
    os.O_WRONLY
    | os.O_RDWR
    | os.O_APPEND
    | os.O_CREAT
    | os.O_TRUNC
    | getattr(os, "O_EXCL", 0)
)


class DuplicateKeyError(ValueError):
    pass


class CommandError(RuntimeError):
    def __init__(self, code: str, message: str, *, exit_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CommandError("cli", message, exit_code=2)


@dataclass(frozen=True)
class Artifact:
    path: str
    sha256: str
    size: int
    pointer: str


def compact_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def emit(value: Any) -> None:
    sys.stdout.buffer.write(compact_json(value) + b"\n")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def finding(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def unique_findings(values: list[dict[str, str]]) -> list[dict[str, str]]:
    keyed = {
        (value["path"], value["code"], value["message"]): value for value in values
    }
    return sorted(
        keyed.values(),
        key=lambda value: (value["path"], value["code"], value["message"]),
    )


def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(key)
        result[key] = value
    return result


def json_depth(value: Any, level: int = 0) -> int:
    if level > MAX_JSON_DEPTH:
        return level
    if type(value) is dict:
        return max(
            [level, *(json_depth(child, level + 1) for child in value.values())]
        )
    if type(value) is list:
        return max([level, *(json_depth(child, level + 1) for child in value)])
    return level


def exact_object(
    value: Any,
    fields: set[str],
    path: str,
    findings: list[dict[str, str]],
) -> bool:
    if type(value) is not dict:
        findings.append(finding("type", path, "expected object"))
        return False
    missing = fields - set(value)
    extra = set(value) - fields
    for key in sorted(missing):
        findings.append(finding("required", f"{path}/{key}", "field is required"))
    for key in sorted(extra):
        findings.append(
            finding("additional", f"{path}/{key}", "field is outside the contract")
        )
    return not missing and not extra


def validate_json_subset(
    value: Any,
    path: str,
    findings: list[dict[str, str]],
) -> None:
    if value is None or type(value) in {str, int, bool}:
        return
    if type(value) is list:
        for index, child in enumerate(value):
            validate_json_subset(child, f"{path}/{index}", findings)
        return
    if type(value) is dict:
        for key, child in value.items():
            if type(key) is not str:
                findings.append(finding("json_type", path, "object key must be text"))
                continue
            validate_json_subset(child, f"{path}/{key}", findings)
        return
    findings.append(
        finding("json_type", path, "only null, text, integer, boolean, arrays, and objects are allowed")
    )


def family_for(case_id: str) -> str | None:
    if case_id not in CASE_IDS:
        return None
    if case_id.startswith("CR-"):
        return "COLD_RESUME"
    if case_id.startswith("PR-"):
        return "PULL_REQUEST_DISPOSITION"
    return "ACCEPTANCE_ATTACK"


def attack_class_for(case_id: str) -> str | None:
    return ATTACK_CLASSES.get(case_id)


def validate_text(
    value: Any,
    path: str,
    findings: list[dict[str, str]],
    *,
    pattern: re.Pattern[str],
    incomplete_when_null: bool = False,
) -> str | None:
    if value is None and incomplete_when_null:
        findings.append(finding("incomplete", path, "value is not frozen"))
        return None
    if type(value) is not str or pattern.fullmatch(value) is None:
        findings.append(finding("format", path, "value has an invalid opaque format"))
        return None
    if unicodedata.normalize("NFC", value) != value:
        findings.append(finding("unicode", path, "value must be NFC-normalized"))
        return None
    return value


def validate_sha256(
    value: Any,
    path: str,
    findings: list[dict[str, str]],
    *,
    incomplete_when_null: bool = False,
) -> str | None:
    if value is None and incomplete_when_null:
        findings.append(finding("incomplete", path, "commitment is not frozen"))
        return None
    if type(value) is not str or SHA256_RE.fullmatch(value) is None:
        findings.append(finding("sha256", path, "expected 64 lowercase hex characters"))
        return None
    return value


def validate_relative_path(
    value: Any,
    path: str,
    findings: list[dict[str, str]],
) -> str | None:
    if type(value) is not str:
        findings.append(finding("artifact_path", path, "artifact path must be text"))
        return None
    if (
        not value
        or len(value) > 512
        or value.startswith("/")
        or "\\" in value
        or "\x00" in value
        or unicodedata.normalize("NFC", value) != value
    ):
        findings.append(
            finding("artifact_path", path, "artifact path must be relative NFC POSIX text")
        )
        return None
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        findings.append(
            finding("artifact_path", path, "artifact path cannot contain empty, dot, or parent components")
        )
        return None
    return value


def validate_artifact_reference(
    value: Any,
    path: str,
    findings: list[dict[str, str]],
    *,
    incomplete_when_null: bool,
) -> Artifact | None:
    if value is None and incomplete_when_null:
        findings.append(finding("incomplete", path, "artifact is not frozen"))
        return None
    if not exact_object(value, {"path", "sha256", "bytes"}, path, findings):
        return None
    relative = validate_relative_path(value.get("path"), f"{path}/path", findings)
    expected = validate_sha256(value.get("sha256"), f"{path}/sha256", findings)
    size = value.get("bytes")
    if type(size) is not int or type(size) is bool or not 1 <= size <= MAX_ARTIFACT_BYTES:
        findings.append(
            finding(
                "artifact_bytes",
                f"{path}/bytes",
                f"bytes must be an integer between 1 and {MAX_ARTIFACT_BYTES}",
            )
        )
        size = None
    if relative is None or expected is None or size is None:
        return None
    return Artifact(relative, expected, size, path)


def validate_identifier_registry(
    value: Any,
    path: str,
    findings: list[dict[str, str]],
) -> None:
    if type(value) is not list:
        findings.append(finding("type", path, "expected array"))
        return
    identifiers: list[str] = []
    for index, item in enumerate(value):
        pointer = f"{path}/{index}"
        if not exact_object(item, {"id", "commitment_sha256"}, pointer, findings):
            continue
        identifier = validate_text(
            item.get("id"),
            f"{pointer}/id",
            findings,
            pattern=IDENTIFIER_RE,
        )
        validate_sha256(
            item.get("commitment_sha256"),
            f"{pointer}/commitment_sha256",
            findings,
        )
        if identifier is not None:
            identifiers.append(identifier)
    if identifiers != sorted(identifiers):
        findings.append(
            finding("identifier_order", path, "identifier entries must be sorted by id")
        )
    if len(identifiers) != len(set(identifiers)):
        findings.append(
            finding("identifier_duplicate", path, "identifier ids must be unique")
        )


def repeated_artifact_paths(value: list[Any]) -> list[str]:
    result: list[str] = []
    for item in value:
        if type(item) is not dict:
            continue
        artifact = item.get("artifact")
        if type(artifact) is not dict:
            continue
        path = artifact.get("path")
        if type(path) is str:
            result.append(path)
    return result


def _directory_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )


def _open_absolute_directory(path: Path) -> int:
    if not path.is_absolute():
        raise CommandError("absolute_path", "path must be absolute", exit_code=2)
    parts = path.parts
    if any(part in {"", ".", ".."} for part in parts[1:]):
        raise CommandError(
            "absolute_path",
            "absolute path cannot contain empty, dot, or parent components",
            exit_code=2,
        )
    descriptor = os.open(path.anchor, _directory_flags())
    try:
        for part in parts[1:]:
            next_descriptor = os.open(
                part,
                _directory_flags(),
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = next_descriptor
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise NotADirectoryError(str(path))
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _read_descriptor(
    descriptor: int,
    *,
    maximum: int,
) -> tuple[bytes, os.stat_result, os.stat_result]:
    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode):
        raise OSError("path is not a regular file")
    if before.st_nlink != 1:
        raise OSError("hard-linked files are not accepted")
    if before.st_size > maximum:
        raise OSError(f"file exceeds {maximum} bytes")
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(descriptor, min(READ_CHUNK_BYTES, maximum + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > maximum:
            raise OSError(f"file exceeds {maximum} bytes")
    after = os.fstat(descriptor)
    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    identity_after = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if identity_before != identity_after:
        raise OSError("file changed while it was read")
    return b"".join(chunks), before, after


def read_manifest_bytes(path: Path) -> bytes:
    parent_descriptor = _open_absolute_directory(path.parent)
    descriptor = -1
    try:
        descriptor = os.open(
            path.name,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
            dir_fd=parent_descriptor,
        )
        data, _, _ = _read_descriptor(descriptor, maximum=MAX_MANIFEST_BYTES)
        return data
    except OSError as exc:
        raise CommandError("manifest_io", f"manifest is unreadable: {exc}", exit_code=2) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent_descriptor)


def parse_manifest(raw: bytes) -> tuple[Any | None, list[dict[str, str]]]:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=object_pairs)
    except UnicodeDecodeError as exc:
        return None, [finding("json_encoding", "", str(exc))]
    except json.JSONDecodeError as exc:
        return None, [finding("json", "", str(exc))]
    except DuplicateKeyError as exc:
        return None, [finding("json_duplicate_key", "", f"duplicate key: {exc}")]
    return value, []


def _artifact_open_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )


def validate_artifact_bytes(
    root_descriptor: int,
    artifact: Artifact,
    findings: list[dict[str, str]],
) -> tuple[int, int] | None:
    directory_descriptor = os.dup(root_descriptor)
    file_descriptor = -1
    try:
        parts = artifact.path.split("/")
        for part in parts[:-1]:
            next_descriptor = os.open(
                part,
                _directory_flags(),
                dir_fd=directory_descriptor,
            )
            os.close(directory_descriptor)
            directory_descriptor = next_descriptor
        file_descriptor = os.open(
            parts[-1],
            _artifact_open_flags(),
            dir_fd=directory_descriptor,
        )
        data, before, _ = _read_descriptor(
            file_descriptor,
            maximum=MAX_ARTIFACT_BYTES,
        )
        if before.st_size != artifact.size or len(data) != artifact.size:
            findings.append(
                finding(
                    "artifact_size",
                    f"{artifact.pointer}/bytes",
                    "declared byte count does not match the stable file",
                )
            )
        if sha256_bytes(data) != artifact.sha256:
            findings.append(
                finding(
                    "artifact_digest",
                    f"{artifact.pointer}/sha256",
                    "declared digest does not match the raw file bytes",
                )
            )
        return before.st_dev, before.st_ino
    except FileNotFoundError:
        findings.append(
            finding("artifact_missing", artifact.pointer, "artifact is missing")
        )
    except NotADirectoryError:
        findings.append(
            finding(
                "artifact_type",
                artifact.pointer,
                "artifact path crosses a non-directory",
            )
        )
    except OSError as exc:
        message = str(exc)
        code = "artifact_unstable" if "changed while" in message else "artifact_type"
        findings.append(finding(code, artifact.pointer, message))
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)
        os.close(directory_descriptor)
    return None


def validation_report(
    raw: bytes,
    value: Any,
    findings: list[dict[str, str]],
    *,
    artifact_count: int | None = None,
) -> dict[str, Any]:
    case_id = value.get("case_id") if type(value) is dict else None
    ordered = unique_findings(findings)
    return {
        "schema": VALIDATION_SCHEMA,
        "case_id": case_id if case_id in CASE_IDS else None,
        "family": family_for(case_id) if type(case_id) is str else None,
        "critical_attack_class": (
            attack_class_for(case_id) if type(case_id) is str else None
        ),
        "scope": "SEALED_CASE_MECHANICS_ONLY",
        "state": "READY" if not ordered else "OPEN",
        "manifest_bytes_sha256": sha256_bytes(raw),
        "artifact_count": artifact_count,
        "findings": ordered,
    }


def validate_manifest(value: Any, root: Path, *, raw: bytes | None = None) -> dict[str, Any]:
    encoded = raw if raw is not None else compact_json(value)
    findings: list[dict[str, str]] = []
    artifacts: list[Artifact] = []
    if json_depth(value) > MAX_JSON_DEPTH:
        findings.append(
            finding("json_depth", "", f"manifest exceeds depth {MAX_JSON_DEPTH}")
        )
    validate_json_subset(value, "", findings)
    if not exact_object(value, TOP_LEVEL_FIELDS, "", findings):
        return validation_report(encoded, value, findings, artifact_count=0)
    assert type(value) is dict
    if value.get("schema") != MANIFEST_SCHEMA:
        findings.append(finding("schema", "/schema", f"must equal {MANIFEST_SCHEMA}"))
    if value.get("corpus_version") != CORPUS_VERSION:
        findings.append(
            finding(
                "corpus_version",
                "/corpus_version",
                f"must equal {CORPUS_VERSION}",
            )
        )
    if value.get("protocol_commit") != PROTOCOL_COMMIT:
        findings.append(
            finding(
                "protocol_commit",
                "/protocol_commit",
                f"must equal {PROTOCOL_COMMIT}",
            )
        )
    case_id = value.get("case_id")
    if case_id not in CASE_IDS:
        findings.append(
            finding("case_id", "/case_id", "case id is outside the frozen registry")
        )

    source = value.get("source")
    if exact_object(source, SOURCE_FIELDS, "/source", findings):
        validate_text(
            source.get("alias"),
            "/source/alias",
            findings,
            pattern=SOURCE_ALIAS_RE,
            incomplete_when_null=True,
        )
        for key in sorted(SOURCE_FIELDS - {"alias"}):
            validate_sha256(
                source.get(key),
                f"/source/{key}",
                findings,
                incomplete_when_null=True,
            )

    commitments = value.get("commitments")
    if exact_object(commitments, COMMITMENT_FIELDS, "/commitments", findings):
        for key in sorted(COMMITMENT_FIELDS):
            validate_sha256(
                commitments.get(key),
                f"/commitments/{key}",
                findings,
                incomplete_when_null=True,
            )

    identifiers = value.get("identifiers")
    if exact_object(identifiers, IDENTIFIER_FIELDS, "/identifiers", findings):
        for key in sorted(IDENTIFIER_FIELDS):
            validate_identifier_registry(
                identifiers.get(key),
                f"/identifiers/{key}",
                findings,
            )

    source_bundle = validate_artifact_reference(
        value.get("source_bundle"),
        "/source_bundle",
        findings,
        incomplete_when_null=True,
    )
    if source_bundle is not None:
        artifacts.append(source_bundle)

    label_codes: list[str] = []
    labels = value.get("labels")
    if type(labels) is not list:
        findings.append(finding("type", "/labels", "expected array"))
    else:
        for index, label in enumerate(labels):
            pointer = f"/labels/{index}"
            if not exact_object(label, {"label_code", "artifact"}, pointer, findings):
                continue
            code = validate_text(
                label.get("label_code"),
                f"{pointer}/label_code",
                findings,
                pattern=OPAQUE_CODE_RE,
            )
            artifact = validate_artifact_reference(
                label.get("artifact"),
                f"{pointer}/artifact",
                findings,
                incomplete_when_null=False,
            )
            if code is not None:
                label_codes.append(code)
            if artifact is not None:
                artifacts.append(artifact)
        if len(label_codes) != 2 or len(set(label_codes)) != 2:
            findings.append(
                finding(
                    "label_set",
                    "/labels",
                    "exactly two distinct opaque label codes are required",
                )
            )
        if label_codes != sorted(label_codes):
            findings.append(
                finding("label_order", "/labels", "labels must be sorted by label_code")
            )
        label_paths = repeated_artifact_paths(labels)
        if label_paths != sorted(label_paths):
            findings.append(
                finding(
                    "artifact_order",
                    "/labels",
                    "label artifact paths must be sorted",
                )
            )

    adjudication = validate_artifact_reference(
        value.get("adjudication"),
        "/adjudication",
        findings,
        incomplete_when_null=True,
    )
    if adjudication is not None:
        artifacts.append(adjudication)

    condition_codes: list[str] = []
    baselines = value.get("baselines")
    if type(baselines) is not list:
        findings.append(finding("type", "/baselines", "expected array"))
    else:
        for index, baseline in enumerate(baselines):
            pointer = f"/baselines/{index}"
            if not exact_object(
                baseline,
                {"condition_code", "artifact"},
                pointer,
                findings,
            ):
                continue
            code = baseline.get("condition_code")
            if code not in CONDITION_CODES:
                findings.append(
                    finding(
                        "condition_code",
                        f"{pointer}/condition_code",
                        "condition code is outside C01-C06",
                    )
                )
            else:
                condition_codes.append(code)
            artifact = validate_artifact_reference(
                baseline.get("artifact"),
                f"{pointer}/artifact",
                findings,
                incomplete_when_null=False,
            )
            if artifact is not None:
                artifacts.append(artifact)
        if condition_codes != list(CONDITION_CODES):
            findings.append(
                finding(
                    "baseline_set",
                    "/baselines",
                    "baselines must contain C01-C06 exactly once in order",
                )
            )
        baseline_paths = repeated_artifact_paths(baselines)
        if baseline_paths != sorted(baseline_paths):
            findings.append(
                finding(
                    "artifact_order",
                    "/baselines",
                    "baseline artifact paths must be sorted",
                )
            )

    mutation = validate_artifact_reference(
        value.get("mutation"),
        "/mutation",
        findings,
        incomplete_when_null=True,
    )
    if mutation is not None:
        artifacts.append(mutation)

    confirmation_codes: list[str] = []
    confirmations = value.get("mutation_confirmations")
    if type(confirmations) is not list:
        findings.append(finding("type", "/mutation_confirmations", "expected array"))
    else:
        for index, confirmation in enumerate(confirmations):
            pointer = f"/mutation_confirmations/{index}"
            if not exact_object(
                confirmation,
                {"label_code", "artifact"},
                pointer,
                findings,
            ):
                continue
            code = validate_text(
                confirmation.get("label_code"),
                f"{pointer}/label_code",
                findings,
                pattern=OPAQUE_CODE_RE,
            )
            artifact = validate_artifact_reference(
                confirmation.get("artifact"),
                f"{pointer}/artifact",
                findings,
                incomplete_when_null=False,
            )
            if code is not None:
                confirmation_codes.append(code)
            if artifact is not None:
                artifacts.append(artifact)
        if confirmation_codes != sorted(label_codes) or len(confirmation_codes) != 2:
            findings.append(
                finding(
                    "mutation_confirmation_set",
                    "/mutation_confirmations",
                    "confirmations must match the two label codes exactly",
                )
            )
        if confirmation_codes != sorted(confirmation_codes):
            findings.append(
                finding(
                    "confirmation_order",
                    "/mutation_confirmations",
                    "confirmations must be sorted by label_code",
                )
            )
        confirmation_paths = repeated_artifact_paths(confirmations)
        if confirmation_paths != sorted(confirmation_paths):
            findings.append(
                finding(
                    "artifact_order",
                    "/mutation_confirmations",
                    "confirmation artifact paths must be sorted",
                )
            )

    artifact_paths = [artifact.path for artifact in artifacts]
    if len(artifact_paths) != len(set(artifact_paths)):
        findings.append(
            finding(
                "artifact_duplicate",
                "",
                "one artifact path is assigned to more than one semantic slot",
            )
        )

    try:
        root_descriptor = _open_absolute_directory(root)
    except OSError as exc:
        raise CommandError("root_io", f"root is unreadable: {exc}", exit_code=2) from exc
    try:
        artifact_identities: dict[tuple[int, int], str] = {}
        for artifact in artifacts:
            identity = validate_artifact_bytes(root_descriptor, artifact, findings)
            if identity is None:
                continue
            previous = artifact_identities.get(identity)
            if previous is not None:
                findings.append(
                    finding(
                        "artifact_identity_duplicate",
                        artifact.pointer,
                        f"artifact reuses the file assigned to {previous}",
                    )
                )
            else:
                artifact_identities[identity] = artifact.pointer
    finally:
        os.close(root_descriptor)
    return validation_report(
        encoded,
        value,
        findings,
        artifact_count=len(artifacts),
    )


def scaffold(case_id: str) -> dict[str, Any]:
    if case_id not in CASE_IDS:
        raise CommandError(
            "case_id",
            "case id is outside the frozen registry",
            exit_code=1,
        )
    return {
        "schema": MANIFEST_SCHEMA,
        "corpus_version": CORPUS_VERSION,
        "protocol_commit": PROTOCOL_COMMIT,
        "case_id": case_id,
        "source": {
            "alias": None,
            "repository_commitment_sha256": None,
            "immutable_refs_commitment_sha256": None,
            "license_commitment_sha256": None,
            "redistribution_basis_commitment_sha256": None,
        },
        "commitments": {
            "eligibility_sha256": None,
            "negative_control_sha256": None,
            "discriminating_fact_sha256": None,
        },
        "identifiers": {
            "action_kinds": [],
            "target_ids": [],
            "proof_ids": [],
            "evidence_ids": [],
            "risk_ids": [],
        },
        "source_bundle": None,
        "labels": [],
        "adjudication": None,
        "baselines": [],
        "mutation": None,
        "mutation_confirmations": [],
    }


def write_new_file(path: Path, data: bytes) -> None:
    if not path.is_absolute() or not path.name:
        raise CommandError("output_path", "output must be an absolute file path", exit_code=2)
    try:
        parent_descriptor = _open_absolute_directory(path.parent)
    except OSError as exc:
        raise CommandError("output_parent", f"output parent is unsafe: {exc}", exit_code=2) from exc
    descriptor = -1
    created = False
    try:
        descriptor = os.open(
            path.name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_descriptor,
        )
        created = True
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short write")
            view = view[written:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.fsync(parent_descriptor)
    except FileExistsError as exc:
        raise CommandError("output_exists", "output already exists", exit_code=1) from exc
    except OSError as exc:
        if created:
            try:
                os.unlink(path.name, dir_fd=parent_descriptor)
            except OSError:
                pass
        raise CommandError("output_write", f"output was not created: {exc}", exit_code=2) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent_descriptor)


def parser() -> argparse.ArgumentParser:
    result = JsonArgumentParser(description=__doc__)
    commands = result.add_subparsers(
        dest="command",
        required=True,
        parser_class=JsonArgumentParser,
    )
    scaffold_parser = commands.add_parser(
        "scaffold",
        help="create one deterministic incomplete case manifest",
    )
    scaffold_parser.add_argument("--case-id", required=True)
    scaffold_parser.add_argument("--output", required=True, type=Path)
    validate_parser = commands.add_parser(
        "validate",
        help="derive OPEN or READY from one case manifest and sealed artifacts",
    )
    validate_parser.add_argument("--manifest", required=True, type=Path)
    validate_parser.add_argument("--root", required=True, type=Path)
    return result


def command_error(command: str | None, exc: CommandError) -> dict[str, Any]:
    return {
        "schema": COMMAND_ERROR_SCHEMA,
        "command": command,
        "ok": False,
        "findings": [finding(exc.code, "", str(exc))],
    }


def main(argv: list[str] | None = None) -> int:
    command: str | None = None
    try:
        args = parser().parse_args(argv)
        command = args.command
        if args.command == "scaffold":
            encoded = compact_json(scaffold(args.case_id))
            write_new_file(args.output, encoded)
            emit(
                {
                    "schema": SCAFFOLD_SCHEMA,
                    "ok": True,
                    "case_id": args.case_id,
                    "bytes": len(encoded),
                    "sha256": sha256_bytes(encoded),
                }
            )
            return 0
        try:
            root_descriptor = _open_absolute_directory(args.root)
        except OSError as exc:
            raise CommandError(
                "root_io",
                f"root is unreadable: {exc}",
                exit_code=2,
            ) from exc
        else:
            os.close(root_descriptor)
        raw = read_manifest_bytes(args.manifest)
        value, parse_findings = parse_manifest(raw)
        if value is None:
            result = validation_report(raw, {}, parse_findings)
        else:
            result = validate_manifest(value, args.root, raw=raw)
            if parse_findings:
                result = validation_report(
                    raw,
                    value,
                    [*parse_findings, *result["findings"]],
                )
        emit(result)
        return 0 if result["state"] == "READY" else 1
    except CommandError as exc:
        emit(command_error(command, exc))
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
