#!/usr/bin/env python3
"""Small, local-only Drive Packet parsing and preparation primitives.

Drive Packets live in a project's existing ``PLAN.md``.  They are deliberate
input to a foreground Pilot Puppy session, not a queue or a second plan.  This
module validates the packet block and selects at most three path-disjoint work
items without choosing a different host on the user's behalf.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Final


DRIVE_SCHEMA: Final = "pilot-puppy.drive.v1"
DRIVE_MARKER: Final = "pilot-puppy-drive.v1"
MAX_LANES: Final = 3
MAX_PACKET_LANES: Final = 24
MAX_TASK_CHARS: Final = 12_000
MAX_SUMMARY_CHARS: Final = 280
MAX_PROOF_ARGS: Final = 16
MAX_ALLOWED_PATHS: Final = 64
ID_RE: Final = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
CONTROL_RE: Final = re.compile(r"[\x00-\x1f\x7f]")
PRIVATE_PATH_RE: Final = re.compile(
    r"(?:~/|/Users/|/home/|/private/var/|file:///|[A-Za-z]:[\\/]|\\\\)", re.IGNORECASE
)
SECRET_SHAPE_RE: Final = re.compile(
    r"(?:sk-(?:ant-)?[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|"
    r"AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|Bearer\s+[A-Za-z0-9._\-/+=]{20,}|"
    r"-----BEGIN[ A-Z]*PRIVATE KEY-----)",
    re.IGNORECASE,
)
DRIVE_BLOCK_RE: Final = re.compile(
    r"<!--\s*pilot-puppy-drive\.v1\s*\n(?P<payload>.*?)\n\s*-->", re.DOTALL
)
TASK_KINDS: Final = frozenset({"dev", "debug", "hard-dev"})
STATES: Final = frozenset({"ready", "paused", "blocked", "done"})
MERGE_MODES: Final = frozenset({"ordinary", "manual"})
FORBIDDEN_PROOF_EXECUTABLES: Final = frozenset({"gh", "git", "curl", "wget", "ssh", "scp", "rsync", "osascript"})
FORBIDDEN_PROOF_ACTION_RE: Final = re.compile(r"(?:^|[-_:])(?:deploy|publish|release|push|merge|upload)(?:$|[-_:])")


class DrivePacketError(ValueError):
    """A PLAN-owned Drive Packet is incomplete, unsafe, or ambiguous."""


def _exact_object(value: object, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise DrivePacketError(f"Drive Packet has an invalid {label}")
    return value


def _text(value: object, label: str, *, maximum: int, multiline: bool = False) -> str:
    if not isinstance(value, str):
        raise DrivePacketError(f"Drive Packet {label} must be text")
    text = value.strip() if multiline else " ".join(value.split())
    if not text or len(text) > maximum:
        raise DrivePacketError(f"Drive Packet {label} is invalid")
    if CONTROL_RE.search(text.replace("\n", "")) or PRIVATE_PATH_RE.search(text) or SECRET_SHAPE_RE.search(text):
        raise DrivePacketError(f"Drive Packet {label} is not safe for a local handoff")
    return text


def _identifier(value: object, label: str) -> str:
    identifier = _text(value, label, maximum=64)
    if ID_RE.fullmatch(identifier) is None:
        raise DrivePacketError(f"Drive Packet {label} must be a public identifier")
    return identifier


def _relative_path(value: object) -> str:
    path = _text(value, "allowed path", maximum=512)
    parts = path.split("/")
    if path.startswith("/") or any(part in {"", ".", ".."} for part in parts):
        raise DrivePacketError("Drive Packet allowed path must be a safe relative path")
    return path


def _argv(value: object) -> list[str]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_PROOF_ARGS:
        raise DrivePacketError("Drive Packet proof must be one argv array")
    args = [_text(item, "proof argument", maximum=280) for item in value]
    if any("\n" in item or "\r" in item for item in args):
        raise DrivePacketError("Drive Packet proof argument is invalid")
    if args[0].lower() in FORBIDDEN_PROOF_EXECUTABLES or any(
        FORBIDDEN_PROOF_ACTION_RE.search(item.lower()) for item in args
    ):
        raise DrivePacketError("Drive Packet proof must be a local check, not a delivery action")
    return args


def _lane(value: object) -> dict[str, Any]:
    lane = _exact_object(
        value,
        {"id", "state", "task_kind", "summary", "task", "allowed_paths", "proof", "merge"},
        "lane",
    )
    state = lane["state"]
    task_kind = lane["task_kind"]
    merge = lane["merge"]
    if not isinstance(state, str) or state not in STATES:
        raise DrivePacketError("Drive Packet lane state is invalid")
    if not isinstance(task_kind, str) or task_kind not in TASK_KINDS:
        raise DrivePacketError("Drive Packet lane task kind is invalid")
    if not isinstance(merge, str) or merge not in MERGE_MODES:
        raise DrivePacketError("Drive Packet lane merge mode is invalid")
    raw_paths = lane["allowed_paths"]
    if not isinstance(raw_paths, list) or not 1 <= len(raw_paths) <= MAX_ALLOWED_PATHS:
        raise DrivePacketError("Drive Packet lane needs bounded allowed paths")
    allowed_paths = [_relative_path(path) for path in raw_paths]
    if len(set(allowed_paths)) != len(allowed_paths):
        raise DrivePacketError("Drive Packet lane repeats an allowed path")
    return {
        "id": _identifier(lane["id"], "lane id"),
        "state": state,
        "task_kind": task_kind,
        "summary": _text(lane["summary"], "summary", maximum=MAX_SUMMARY_CHARS),
        "task": _text(lane["task"], "task", maximum=MAX_TASK_CHARS, multiline=True),
        "allowed_paths": allowed_paths,
        "proof": _argv(lane["proof"]),
        "merge": merge,
    }


def extract_document(plan_text: str) -> dict[str, Any] | None:
    """Extract one exact JSON Drive Packet block from its owning PLAN.md."""

    matches = list(DRIVE_BLOCK_RE.finditer(plan_text))
    if not matches:
        return None
    if len(matches) != 1:
        raise DrivePacketError("PLAN.md has more than one Drive Packet block")
    try:
        raw = json.loads(matches[0].group("payload"))
    except json.JSONDecodeError as exc:
        raise DrivePacketError("Drive Packet block is not valid JSON") from exc
    root = _exact_object(raw, {"schema", "revision", "lanes"}, "document")
    if root["schema"] != DRIVE_SCHEMA:
        raise DrivePacketError("Drive Packet schema is invalid")
    if type(root["revision"]) is not int or not 1 <= root["revision"] <= 2_147_483_647:
        raise DrivePacketError("Drive Packet revision is invalid")
    raw_lanes = root["lanes"]
    if not isinstance(raw_lanes, list) or not 1 <= len(raw_lanes) <= MAX_PACKET_LANES:
        raise DrivePacketError("Drive Packet lanes are invalid")
    lanes = [_lane(item) for item in raw_lanes]
    if len({lane["id"] for lane in lanes}) != len(lanes):
        raise DrivePacketError("Drive Packet lane IDs must be unique")
    return {"schema": DRIVE_SCHEMA, "revision": root["revision"], "lanes": lanes}


def plan_sha256(plan_text: str) -> str:
    return hashlib.sha256(plan_text.encode("utf-8")).hexdigest()


def paths_overlap(first: list[str], second: list[str]) -> bool:
    for left in first:
        for right in second:
            if left == right or left.startswith(f"{right}/") or right.startswith(f"{left}/"):
                return True
    return False


def select_disjoint_ready_lanes(document: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Choose up to three declared ready lanes without changing their host choice.

    The caller routes candidates first and supplies the selected host in
    ``selection``.  This function deliberately skips, rather than reroutes,
    a same-host or overlapping candidate.
    """

    selected: list[dict[str, Any]] = []
    notices: list[dict[str, str]] = []
    used_paths: list[str] = []
    used_hosts: set[str] = set()
    for lane in document["lanes"]:
        if lane["state"] != "ready":
            continue
        selection = lane.get("selection")
        if not isinstance(selection, dict) or not isinstance(selection.get("host"), str):
            notices.append({"id": lane["id"], "reason": "needs_a_ready_coding_tool"})
            continue
        host = selection["host"]
        if host in used_hosts:
            notices.append({"id": lane["id"], "reason": "shares_a_coding_tool"})
            continue
        if paths_overlap(used_paths, lane["allowed_paths"]):
            notices.append({"id": lane["id"], "reason": "overlaps_another_piece_of_work"})
            continue
        if len(selected) >= MAX_LANES:
            notices.append({"id": lane["id"], "reason": "three_ready_lanes_are_already_prepared"})
            continue
        selected.append(lane)
        used_hosts.add(host)
        used_paths.extend(lane["allowed_paths"])
    return selected, notices


def public_preview(document: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a task-content-free preview suitable for the local browser."""

    if document is None:
        return None
    return {
        "schema": "pilot-puppy.drive-preview.v1",
        "revision": document["revision"],
        "ready_count": sum(1 for lane in document["lanes"] if lane["state"] == "ready"),
        "lanes": [
            {"state": lane["state"], "summary": lane["summary"]}
            for lane in document["lanes"]
        ],
    }


__all__ = [
    "DRIVE_MARKER",
    "DRIVE_SCHEMA",
    "DrivePacketError",
    "MAX_LANES",
    "extract_document",
    "paths_overlap",
    "plan_sha256",
    "public_preview",
    "select_disjoint_ready_lanes",
]
