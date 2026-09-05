"""One closed, side-effect-free decoder for board writes and confined readers.

Mutation and provider I/O modules must never be imported here. Grammar, privacy
shapes and offline Git identity stay with their existing pure owners.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import unicodedata

import shadow_git as _shadow_git
import shadow_plan_grammar as _grammar
from shadow_scrub_lib import PRIVATE_PATH_RE, SECRET_SHAPE_RE


V1_SCHEMA = "shadow.root-board.v1"
V2_SCHEMA = "shadow.root-board.v2"
RECOVERY_ACTION = "probe-proof-then-adopt-park-or-close"
ROW_ID = _grammar.ROW_ID_RE
ENTITY_ID = re.compile(r"[0-9a-f]{64}")
GIT_OBJECT_ID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
PROJECT_ID = re.compile(r"[a-z][a-z0-9-]{1,31}")
CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_HUDDLE_REF_FIELDS = {"entity", "row", "claim_revision", "owner", "claimed_at"}
_HUDDLE_FIELDS = {"id", "state", "reason", "opened_revision", "generation", "opened_at",
                  "reply_by", "round", "claims", "edges", "holds", "bids", "resolution",
                  "compliance", "remote_transition", "replacements", "resolved_at", "retain_until"}
_HUDDLE_REASONS = {"write_scope_overlap", "scope_request", "semantic_suspicion"}
_EDGE_KINDS = {"path_overlap", "scope_unknown", "semantic_suspicion"}
_HUDDLE_STATES = {"awaiting_scope", "open_round_1", "open_round_2", "remote_pending", "awaiting_compliance", "resolved"}
_BID_ROLES = {"own", "disjoint", "review", "prove", "yield", "stand_down", "unavailable"}
_BID_REASONS = {"existing_claim", "path_disjoint", "distinct_outcome", "duplicate_intent", "best_proof_access",
                "blocked", "preserve_existing_diff", "owner_authorized_handoff", "transport_unavailable"}
_BID_REQUEST_FIELDS = {"seat", "claim", "role", "scope", "reason", "target", "support_claim", "evidence",
                       "round", "expected_huddle_generation"}


def claim_ref(entity: str, row: str) -> str:
    """The existing remote coordination ref; full identity stays in its payload."""
    if ENTITY_ID.fullmatch(entity) is None or ROW_ID.fullmatch(row) is None:
        raise ValueError("remote claim identity is invalid")
    return f"refs/heads/shadow/claims/v1/{entity}/{row[1:]}"


class BoardError(ValueError):
    """The local board is unsafe, malformed, or could not be updated."""


def well_formed_proof_origin(value: str) -> str:
    """A plan-owned proof origin is one already-normalized public Git identity."""
    if not value or any(char.isspace() for char in value):
        raise ValueError("not a normalized Git identity")
    if value.startswith(("/", "~", ".", "local-remote:")) or "\\" in value or ".." in value:
        raise ValueError("not a normalized Git identity")
    if PRIVATE_PATH_RE.search(value):
        raise ValueError("not a normalized Git identity")
    identity = normalized_origin(value)
    host, sep, path = identity.partition("/")
    if (
        identity != value
        or not sep
        or not path
        or "." not in host.split(":", 1)[0]
    ):
        raise ValueError("not a normalized Git identity")
    return identity


def normalized_origin(origin: str) -> str:
    return _shadow_git.normalized_origin(origin)


def validate_owner(owner: object) -> str:
    """Return one public-safe seat name or refuse it before persistence."""
    if (
        not isinstance(owner, str)
        or not owner
        or owner != owner.strip()
        or not owner.isprintable()
        or len(owner) > 40
        or CONTROL.search(owner)
        or PRIVATE_PATH_RE.search(owner)
        or SECRET_SHAPE_RE.search(owner)
    ):
        raise BoardError(
            "claim owner must be 1-40 public-safe visible characters"
        )
    return owner


def _validate_v1(payload: object) -> dict:
    if not isinstance(payload, dict) or set(payload) != {
        "schema", "revision", "projects", "entities", "claims"
    }:
        raise BoardError("board has unknown or missing top-level fields")
    if payload["schema"] != V1_SCHEMA:
        raise BoardError("board schema is not supported")
    if isinstance(payload["revision"], bool) or not isinstance(payload["revision"], int):
        raise BoardError("board revision must be an integer")
    if payload["revision"] < 0:
        raise BoardError("board revision cannot be negative")
    if (
        not isinstance(payload["projects"], list)
        or not isinstance(payload["entities"], list)
        or not isinstance(payload["claims"], list)
    ):
        raise BoardError("board projects, entities, and claims must be lists")

    projects: set[str] = set()
    for project in payload["projects"]:
        if not isinstance(project, dict) or set(project) != {"id", "priority"}:
            raise BoardError("projects have unknown or missing fields")
        if not isinstance(project["id"], str) or PROJECT_ID.fullmatch(project["id"]) is None:
            raise BoardError("project id must be a lowercase project slug")
        if project["id"] in projects:
            raise BoardError("a project is listed more than once")
        projects.add(project["id"])
        if isinstance(project["priority"], bool) or project["priority"] not in range(1, 6):
            raise BoardError("project priority must be 1-5")

    plans: set[str] = set()
    entities: set[str] = set()
    for entity in payload["entities"]:
        if not isinstance(entity, dict) or set(entity) != {
            "id", "project", "plan", "resume"
        }:
            raise BoardError("entity pointers have unknown or missing fields")
        if not isinstance(entity["id"], str) or ENTITY_ID.fullmatch(entity["id"]) is None:
            raise BoardError("entity id must be one logical plan hash")
        if entity["id"] in entities:
            raise BoardError("a logical entity is listed more than once")
        entities.add(entity["id"])
        if not isinstance(entity["project"], str) or entity["project"] not in projects:
            raise BoardError("entity points outside the registered projects")
        if (
            not isinstance(entity["plan"], str)
            or CONTROL.search(entity["plan"])
            or not Path(entity["plan"]).is_absolute()
        ):
            raise BoardError("entity plan pointers must be absolute paths")
        if Path(entity["plan"]).name != "PLAN.md":
            raise BoardError("entity pointers must name PLAN.md")
        if entity["plan"] in plans:
            raise BoardError("an entity plan is listed more than once")
        plans.add(entity["plan"])
        if entity["resume"] is not None and (
            not isinstance(entity["resume"], str)
            or ROW_ID.fullmatch(entity["resume"]) is None
        ):
            raise BoardError("entity resume must be one row id or null")

    targets: set[tuple[str, str]] = set()
    for claim in payload["claims"]:
        if not isinstance(claim, dict) or set(claim) != {
            "entity", "row", "owner", "claimed_at", "return_by", "recovery"
        }:
            raise BoardError("claims have unknown or missing fields")
        if not isinstance(claim["entity"], str) or claim["entity"] not in entities:
            raise BoardError("claim points outside the registered entities")
        if not isinstance(claim["row"], str) or ROW_ID.fullmatch(claim["row"]) is None:
            raise BoardError("claim row must be one row id")
        target = (claim["entity"], claim["row"])
        if target in targets:
            raise BoardError("a row has more than one claim")
        targets.add(target)
        validate_owner(claim["owner"])
        claimed_at = _timestamp(claim.get("claimed_at"), "claim time")
        return_by = _timestamp(claim.get("return_by"), "claim return-by")
        if return_by <= claimed_at:
            raise BoardError("claim return-by must be later than its claim time")
        if claim["recovery"] != RECOVERY_ACTION:
            raise BoardError("claim recovery action is not supported")
    return payload


def _validate_write_scope(value: object) -> list[str]:
    if not isinstance(value, list) or len(value) > 256:
        raise BoardError("claim write scope must be a bounded list")
    for prefix in value:
        try:
            encoded_length = len(prefix.encode("utf-8")) if isinstance(prefix, str) else 0
        except UnicodeError as exc:
            raise BoardError("claim write scope must be valid UTF-8") from exc
        if (
            not isinstance(prefix, str)
            or not prefix
            or encoded_length > 1024
            or CONTROL.search(prefix)
            or "\\" in prefix
            or any(character in prefix for character in "*?[]")
            or prefix.startswith("/")
        ):
            raise BoardError("claim write scope contains a noncanonical path")
        components = prefix.split("/")
        if prefix != "." and (
            any(component in {"", ".", ".."} for component in components)
            or ".git" in components
        ):
            raise BoardError("claim write scope contains a noncanonical path")
    if value != sorted(set(value)):
        raise BoardError("claim write scope must be sorted and unique")
    return value


def _validate_repository_binding(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != {
        "common_dir_sha256", "remote_identity"
    }:
        raise BoardError("claim repository binding has unknown or missing fields")
    digest = value["common_dir_sha256"]
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise BoardError("claim repository binding digest must be lowercase SHA-256")
    identity = value["remote_identity"]
    if identity is not None:
        if (
            not isinstance(identity, str)
            or "?" in identity
            or "#" in identity
            or SECRET_SHAPE_RE.search(identity)
            or PRIVATE_PATH_RE.search(identity)
        ):
            raise BoardError("claim remote identity is not a normalized Git identity")
        try:
            well_formed_proof_origin(identity)
        except ValueError as exc:
            raise BoardError(
                "claim remote identity is not a normalized Git identity"
            ) from exc
    return value


def _claim_ref(claim: dict) -> dict:
    return {key: claim[key] for key in _HUDDLE_REF_FIELDS}


def _terminal_ref(huddle: dict, ref: dict) -> dict:
    """Resolve a settled participant's immutable terminal replacement."""
    replacement = next((item for item in huddle["replacements"]
                        if item["original"] == ref), None)
    return replacement["current"] if replacement is not None else ref


def _valid_claim_ref(ref: object) -> bool:
    return (isinstance(ref, dict) and set(ref) == _HUDDLE_REF_FIELDS
            and type(ref["claim_revision"]) is int
            and all(isinstance(ref[k], str) for k in _HUDDLE_REF_FIELDS - {"claim_revision"}))


def _claim_key(claim: dict) -> tuple:
    return (claim["entity"], claim["row"], claim["claim_revision"], claim["owner"])


def _claim_rank(claim: dict) -> tuple:
    if claim["claim_revision"] == 0:
        return (0, claim["claimed_at"], claim["entity"], claim["row"], claim["owner"])
    return (1, claim["claim_revision"], claim["entity"], claim["row"], claim["owner"])


def _path_overlap(left: str, right: str) -> bool:
    # Coordination errs toward holding aliases even on case-sensitive hosts.
    # Keep stored spellings and _scope_subset exact: overlap must not expand
    # the paths that an owner has permission to write.
    left, right = (unicodedata.normalize("NFC", unicodedata.normalize("NFC", p).casefold())
                   for p in (left, right))
    return left == "." or right == "." or left == right or left.startswith(right + "/") or right.startswith(left + "/")


def _same_repository(a: dict, b: dict) -> bool:
    _validate_repository_binding(a)
    _validate_repository_binding(b)
    same_common = a["common_dir_sha256"] == b["common_dir_sha256"]
    same_remote = a["remote_identity"] is not None and a["remote_identity"] == b["remote_identity"]
    if same_common and a["remote_identity"] != b["remote_identity"]:
        raise BoardError("repository bindings contradict one another")
    return same_common or same_remote


def _scope_edge(left: dict, right: dict) -> list[str]:
    a, b = left["repository_binding"], right["repository_binding"]
    if left["access"] == "read_only" or right["access"] == "read_only" or a is None or b is None:
        return []
    if not _same_repository(a, b):
        return []
    if "unscoped" in {left["access"], right["access"]}:
        return ["scope_unknown"]
    return ["path_overlap"] if any(_path_overlap(a, b) for a in left["write_scope"] for b in right["write_scope"]) else []


def claim_holds(huddle: dict) -> list[dict]:
    """Greedy direct-edge selection; connectivity does not serialize writers."""
    conflicts = {frozenset((_claim_key(e["left"]), _claim_key(e["right"]))) for e in huddle["edges"]}
    selected, held = [], []
    for claim in sorted(huddle["claims"], key=_claim_rank):
        key = _claim_key(claim)
        if any(frozenset((key, prior)) in conflicts for prior in selected):
            held.append(claim)
        else:
            selected.append(key)
    return copy.deepcopy(held)


def _validate_huddle_reference(ref: object, revision: int) -> None:
    if (not _valid_claim_ref(ref) or ENTITY_ID.fullmatch(ref["entity"]) is None
        or ROW_ID.fullmatch(ref["row"]) is None or not 0 <= ref["claim_revision"] <= revision):
        raise BoardError("Huddle claim reference is malformed")
    validate_owner(ref["owner"])
    _timestamp(ref["claimed_at"], "Huddle claim time")


def _closed(value: object, fields: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise BoardError(f"{label} has unknown or missing fields")


def _enum(value: object, allowed: set[str], label: str) -> None:
    if not isinstance(value, str) or value not in allowed:
        raise BoardError(f"{label} is unsupported")


def _digest(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _reference_list(value: object, revision: int, label: str, *, limit: int = 64) -> dict:
    if not isinstance(value, list) or len(value) > limit:
        raise BoardError(f"{label} exceeds its bound")
    for ref in value:
        _validate_huddle_reference(ref, revision)
    keys = {_claim_key(ref): ref for ref in value}
    if len(keys) != len(value) or value != sorted(value, key=_claim_rank):
        raise BoardError(f"{label} is duplicated or unordered")
    return keys


def _bid_digest(huddle_id: str, bid: dict) -> str:
    request = {"huddle_id": huddle_id, **{key: bid[key] for key in _BID_REQUEST_FIELDS}}
    return hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _scope_subset(scope: list[str], authority: list[str]) -> bool:
    return all(any(old == "." or path == old or path.startswith(old + "/") for old in authority) for path in scope)


def _validate_bids(h: dict, payload: dict) -> None:
    bids = h["bids"]
    if not isinstance(bids, list) or len(bids) > 128:
        raise BoardError("Huddle bid cap exceeded")
    current = {_claim_key(c): c for c in payload["claims"]}
    keys = set()
    held = {_claim_key(c) for c in claim_holds(h)}
    for bid in bids:
        _closed(bid, _BID_REQUEST_FIELDS | {"bid_digest", "submitted_at"}, "Huddle bid")
        _validate_huddle_reference(bid["claim"], payload["revision"])
        if bid["claim"] not in h["claims"] or bid["seat"] != bid["claim"]["owner"]:
            raise BoardError("Huddle bid does not name its exact participant owner")
        _enum(bid["role"], _BID_ROLES, "Huddle bid role")
        _enum(bid["reason"], _BID_REASONS, "Huddle bid reason")
        if (type(bid["round"]) is not int or bid["round"] not in (1, 2) or bid["round"] > h["round"]
            or type(bid["expected_huddle_generation"]) is not int
            or not 1 <= bid["expected_huddle_generation"] <= h["generation"]):
            raise BoardError("Huddle bid round or generation is invalid")
        key = (_claim_key(bid["claim"]), bid["round"])
        if key in keys:
            raise BoardError("Huddle contains a duplicate bid key")
        keys.add(key)
        submitted = _timestamp(bid["submitted_at"], "Huddle bid time")
        if submitted < _timestamp(h["opened_at"], "Huddle opening time"):
            raise BoardError("Huddle bid predates opening")
        _validate_write_scope(bid["scope"])
        _closed(bid["evidence"], {"kind", "value"}, "Huddle evidence")
        _enum(bid["evidence"]["kind"], {"claim", "plan_row", "progress_receipt", "source_commit", "none"}, "Huddle evidence kind")
        evidence = bid["evidence"]["value"]
        if not isinstance(evidence, str) or not (evidence == "self" or _digest(evidence)
            or (bid["evidence"]["kind"] == "source_commit" and GIT_OBJECT_ID.fullmatch(evidence))
            or (bid["evidence"]["kind"] == "plan_row" and ROW_ID.fullmatch(evidence))):
            raise BoardError("Huddle evidence must be a path-free identifier")
        if bid["role"] == "yield":
            _validate_huddle_reference(bid["target"], payload["revision"])
            if (bid["target"] not in h["claims"] or bid["target"] == bid["claim"]
                or bid["target"]["owner"] == bid["seat"] or bid["reason"] != "owner_authorized_handoff"):
                raise BoardError("Huddle yield target is incompatible")
        elif bid["target"] is not None:
            raise BoardError("only yield may name a target")
        if bid["role"] in {"review", "prove"}:
            _validate_huddle_reference(bid["support_claim"], payload["revision"])
            if bid["support_claim"]["owner"] != bid["seat"] or bid["support_claim"] in h["claims"]:
                raise BoardError("Huddle support must be a distinct same-owner claim")
        elif bid["support_claim"] is not None:
            raise BoardError("only support roles may name a support claim")
        if bid["role"] in {"own", "disjoint"} and not bid["scope"]:
            raise BoardError("continuing bid requires nonempty write scope")
        active = h["state"] in {"open_round_1", "open_round_2"} and bid["expected_huddle_generation"] == h["generation"]
        if active:
            claim = current.get(key[0])
            if claim is None or _claim_ref(claim) != bid["claim"]:
                raise BoardError("active bid participant is not current")
            selected = key[0] not in held
            if (selected and bid["role"] not in {"own", "disjoint", "yield", "unavailable"}
                or not selected and bid["role"] == "yield"):
                raise BoardError("Huddle bid role disagrees with graph authority")
            if h["reply_by"] is not None and submitted >= _timestamp(h["reply_by"], "Huddle deadline"):
                raise BoardError("active bid is at or beyond its deadline")
            if bid["role"] in {"review", "prove"}:
                support = current.get(_claim_key(bid["support_claim"]))
                if (support is None or _claim_ref(support) != bid["support_claim"]
                    or bid["scope"] != support["write_scope"]
                    or bid["role"] == "review" and support["access"] != "read_only"):
                    raise BoardError("Huddle support access or scope is invalid")
            elif bid["role"] == "disjoint":
                if not _scope_subset(bid["scope"], claim["write_scope"]):
                    raise BoardError("Huddle disjoint bid expands scope")
            elif bid["scope"] != claim["write_scope"]:
                raise BoardError("Huddle bid must repeat current scope")
        if not _digest(bid["bid_digest"]) or bid["bid_digest"] != _bid_digest(h["id"], bid):
            raise BoardError("Huddle bid digest disagrees with its request")


def _validate_transfer(value: dict, h: dict, revision: int) -> None:
    for field in ("source_claim", "successor_claim", "target_prior_claim"):
        _validate_huddle_reference(value[field], revision)
    source, successor, target = (value[k] for k in ("source_claim", "successor_claim", "target_prior_claim"))
    if (source not in h["claims"] or target not in h["claims"] or source == target
        or source["owner"] == target["owner"] or successor != {**source, "owner": target["owner"]}
        or value["target_prior_action"] != "return_required"):
        raise BoardError("Huddle handoff identities or disposition are inconsistent")
    paired = any(a["claim"] == source and a["role"] == "yield" and a["target"] == target and a["round"] == h["round"]
        and a["reason"] == "owner_authorized_handoff" and any(b["claim"] == target and b["role"] == "own"
            and b["reason"] == "owner_authorized_handoff" and b["round"] == a["round"] for b in h["bids"])
        for a in h["bids"])
    if not paired or source in claim_holds(h) or target not in claim_holds(h):
        raise BoardError("Huddle handoff lacks a selected-owner and target bid pair")


def _validate_remote_transition(h: dict, revision: int) -> None:
    remote = h["remote_transition"]
    if remote is None:
        return
    _closed(remote, {"source_claim", "successor_claim", "target_prior_claim", "target_prior_action",
        "remote_ref", "expected_remote_version", "readback", "attempt_receipt"}, "Huddle remote transition")
    _validate_transfer(remote, h, revision)
    source = remote["source_claim"]
    if (remote["remote_ref"] != claim_ref(source["entity"], source["row"])
        or not isinstance(remote["expected_remote_version"], str)
        or GIT_OBJECT_ID.fullmatch(remote["expected_remote_version"]) is None):
        raise BoardError("Huddle remote claim reference or version is invalid")
    _enum(remote["readback"], {"not_attempted", "ambiguous", "predecessor", "successor"}, "Huddle remote readback")
    if ((remote["readback"] == "not_attempted" and remote["attempt_receipt"] is not None)
        or remote["readback"] != "not_attempted" and not _digest(remote["attempt_receipt"])):
        raise BoardError("Huddle remote attempt receipt is inconsistent")


def _validate_resolution(h: dict, payload: dict) -> set:
    revision = payload["revision"]
    resolution = h["resolution"]
    fields = {"settled_revision", "settled_at", "rule", "handoff", "write_owners", "actions", "support_actions"}
    _closed(resolution, fields, "Huddle resolution")
    if (type(resolution["settled_revision"]) is not int
        or not h["opened_revision"] <= resolution["settled_revision"] <= revision):
        raise BoardError("Huddle settlement revision is inconsistent")
    _enum(resolution["rule"], {"exact_claim_owner", "path_disjoint", "earliest_valid_claim",
        "owner_authorized_handoff", "proof_first_stale_recovery"}, "Huddle resolution rule")
    settled = _timestamp(resolution["settled_at"], "Huddle settlement time")
    if settled < _timestamp(h["opened_at"], "Huddle opening time"):
        raise BoardError("Huddle settlement predates opening")
    if h["state"] == "resolved":
        resolved = _timestamp(h["resolved_at"], "Huddle resolution time")
        if resolved < settled or _timestamp(h["retain_until"], "Huddle retention") != resolved + timedelta(hours=24):
            raise BoardError("Huddle resolution or retention time is inconsistent")
    if not isinstance(resolution["actions"], list) or len(resolution["actions"]) != len(h["claims"]):
        raise BoardError("Huddle resolution must dispose every participant exactly once")
    actions = {}
    for action in resolution["actions"]:
        _closed(action, {"claim", "action"}, "Huddle participant action")
        _validate_huddle_reference(action["claim"], revision)
        _enum(action["action"], {"continue", "continue_disjoint", "handoff_complete", "return_required"}, "Huddle participant action")
        key = _claim_key(action["claim"])
        if action["claim"] not in h["claims"] or key in actions:
            raise BoardError("Huddle action names an absent or duplicated participant")
        actions[key] = action["action"]
    owners = _reference_list(resolution["write_owners"], revision, "Huddle write owners")
    handoff = resolution["handoff"]
    if resolution["rule"] == "owner_authorized_handoff":
        _closed(handoff, {"source_claim", "successor_claim", "target_prior_claim", "target_prior_action", "mode", "remote_readback"}, "Huddle handoff")
        _validate_transfer(handoff, h, revision)
        _enum(handoff["mode"], {"local", "remote"}, "Huddle handoff mode")
        if ((handoff["mode"] == "local" and (handoff["remote_readback"] is not None or h["remote_transition"] is not None))
            or handoff["mode"] == "remote" and (handoff["remote_readback"] != "successor"
                or h["remote_transition"] is None or h["remote_transition"]["readback"] != "successor"
                or any(handoff[k] != h["remote_transition"][k] for k in
                    ("source_claim", "successor_claim", "target_prior_claim", "target_prior_action")))):
            raise BoardError("Huddle handoff mode and remote readback disagree")
        if (actions[_claim_key(handoff["source_claim"])] != "handoff_complete"
            or actions[_claim_key(handoff["target_prior_claim"])] != "return_required"):
            raise BoardError("Huddle handoff dispositions disagree")
    elif handoff is not None or "handoff_complete" in actions.values():
        raise BoardError("non-handoff resolution cannot transfer authority")
    selected = {_claim_key(c) for c in h["claims"]} - {_claim_key(c) for c in claim_holds(h)}
    selected -= {_claim_key(b["claim"]) for b in h["bids"] if b["round"] == h["round"]
                 and b["role"] in {"stand_down", "review", "prove"}}
    continuing = {key for key, action in actions.items() if action != "return_required"}
    if continuing != selected:
        raise BoardError("Huddle dispositions disagree with graph selection")
    if resolution["rule"] == "path_disjoint" and (h["edges"] or set(actions.values()) != {"continue_disjoint"}):
        raise BoardError("path-disjoint resolution retains conflicts or wrong dispositions")
    if resolution["rule"] == "exact_claim_owner" and len(h["claims"]) != 1:
        raise BoardError("exact-owner resolution requires one surviving participant")
    allowed = {key: ref for ref in h["claims"] if (key := _claim_key(ref)) in continuing}
    if handoff:
        allowed.pop(_claim_key(handoff["source_claim"]))
        allowed[_claim_key(handoff["successor_claim"])] = handoff["successor_claim"]
    current = {_claim_key(c): c for c in payload["claims"]}
    if handoff and _claim_key(handoff["source_claim"]) in current:
        raise BoardError("completed handoff source cannot be a current claim")
    if any(allowed.get(key) != ref for key, ref in owners.items()):
        raise BoardError("Huddle writer lacks a continuing disposition")
    for key, ref in allowed.items():
        terminal = _terminal_ref(h, ref)
        terminal_key = _claim_key(terminal)
        if h["state"] != "resolved" and terminal_key in current and (
            _claim_ref(current[terminal_key]) != terminal
            or (current[terminal_key]["access"] == "write") != (key in owners)):
            raise BoardError("Huddle write owners disagree with current access")
    support = resolution["support_actions"]
    if not isinstance(support, list) or len(support) > 64:
        raise BoardError("Huddle support action cap exceeded")
    support_keys = set()
    for action in support:
        _closed(action, {"participant_claim", "support_claim", "action"}, "Huddle support action")
        for field in ("participant_claim", "support_claim"):
            _validate_huddle_reference(action[field], revision)
        _enum(action["action"], {"review_claim", "prove_claim"}, "Huddle support action")
        key = _claim_key(action["participant_claim"])
        if (key in support_keys or action["participant_claim"] not in h["claims"]
            or action["support_claim"] in h["claims"]
            or action["participant_claim"]["owner"] != action["support_claim"]["owner"]
            or not any(b["claim"] == action["participant_claim"] and b["support_claim"] == action["support_claim"]
                and b["role"] + "_claim" == action["action"] and b["round"] == h["round"] for b in h["bids"])):
            raise BoardError("Huddle support action lacks its exact matching bid")
        support_keys.add(key)
    compliance = h["compliance"]
    if not isinstance(compliance, list) or len(compliance) > 64:
        raise BoardError("Huddle compliance cap exceeded")
    required = {key for key, action in actions.items() if action == "return_required"}
    entries, pending = set(), set()
    for entry in compliance:
        _closed(entry, {"claim", "required", "plan_root_at_settlement", "status", "completion"}, "Huddle compliance")
        _validate_huddle_reference(entry["claim"], revision)
        key = _claim_key(entry["claim"])
        if (entry["claim"] not in h["claims"] or key in entries or key not in required
            or entry["required"] != "canonical_disposition_then_return" or not _digest(entry["plan_root_at_settlement"])):
            raise BoardError("Huddle compliance identity or plan root is inconsistent")
        entries.add(key)
        _enum(entry["status"], {"pending", "satisfied"}, "Huddle compliance status")
        if entry["status"] == "pending":
            terminal = _terminal_ref(h, entry["claim"])
            terminal_key = _claim_key(terminal)
            if (entry["completion"] is not None or terminal_key not in current
                    or _claim_ref(current[terminal_key]) != terminal):
                raise BoardError("pending compliance lacks its exact current claim")
            pending.add(key)
        else:
            completion = entry["completion"]
            _closed(completion, {"kind", "board_revision", "receipt"}, "Huddle compliance completion")
            _enum(completion["kind"], {"return", "proof_first_stale_recovery"}, "Huddle completion kind")
            if (_claim_key(_terminal_ref(h, entry["claim"])) in current
                or type(completion["board_revision"]) is not int
                or not resolution["settled_revision"] < completion["board_revision"] <= revision
                or not (completion["receipt"] == "self" or _digest(completion["receipt"]))):
                raise BoardError("Huddle compliance completion is inconsistent")
    if entries != required:
        raise BoardError("every required return needs exactly one compliance entry")
    return pending


def _validate_huddles(payload: dict, *, pending_retention: bool = False) -> None:
    """Decode all lifecycle states without advancing deadlines or pruning history."""
    records = payload["huddles"]
    if not isinstance(records, list) or len(records) > 80:
        raise BoardError("Huddle record cap exceeded")
    current = {_claim_key(c): c for c in payload["claims"]}
    ids, members = set(), set()
    live_count = retained_count = 0
    for h in records:
        if not isinstance(h, dict) or set(h) != _HUDDLE_FIELDS:
            raise BoardError("Huddle has unknown or missing fields")
        if not isinstance(h["id"], str) or re.fullmatch(r"hdl_[0-9a-f]{8}", h["id"]) is None or h["id"] in ids:
            raise BoardError("Huddle id is invalid or duplicated")
        ids.add(h["id"])
        _enum(h["state"], _HUDDLE_STATES, "Huddle state")
        resolved = h["state"] == "resolved"
        settled = h["state"] in {"awaiting_compliance", "resolved"}
        open_state = h["state"] in {"awaiting_scope", "open_round_1", "open_round_2"}
        retained_count += int(resolved)
        live_count += int(not resolved)
        if live_count > 16 or retained_count > (65 if pending_retention else 64):
            raise BoardError("live or retained Huddle cap exceeded")
        if not isinstance(h["reason"], str) or h["reason"] not in _HUDDLE_REASONS:
            raise BoardError("Huddle reason is invalid")
        for field in ("opened_revision", "generation"):
            if type(h[field]) is not int or not 1 <= h[field] <= payload["revision"]:
                raise BoardError("Huddle revision or generation is invalid")
        opened = _timestamp(h["opened_at"], "Huddle open time")
        if open_state:
            if _timestamp(h["reply_by"], "Huddle deadline") <= opened:
                raise BoardError("Huddle deadline must follow opening")
        elif h["reply_by"] is not None:
            raise BoardError("Huddle terminal or pending state cannot have a deadline")
        if type(h["round"]) is not int or h["round"] not in (0, 1, 2):
            raise BoardError("Huddle round is invalid")
        if not isinstance(h["claims"], list) or not (1 if settled else 2) <= len(h["claims"]) <= 64:
            raise BoardError("Huddle participant cap or minimum violated")
        refs = {}
        for ref in h["claims"]:
            _validate_huddle_reference(ref, payload["revision"])
            key = _claim_key(ref)
            if key in refs or (not resolved and key in members):
                raise BoardError("claim belongs to more than one live Huddle")
            refs[key] = ref
        if not resolved:
            members.update(refs)
        if h["claims"] != sorted(h["claims"], key=_claim_rank):
            raise BoardError("Huddle claims are not canonically ordered")
        replacements = h["replacements"]
        if not isinstance(replacements, list) or len(replacements) > 64:
            raise BoardError("Huddle replacement mapping is invalid")
        if not settled and replacements:
            raise BoardError("only settled Huddles may retain replacements")
        replacement_originals, replacement_currents = set(), set()
        for replacement in replacements:
            _closed(replacement, {"original", "current"}, "Huddle replacement")
            original, terminal = replacement["original"], replacement["current"]
            _validate_huddle_reference(original, payload["revision"])
            _validate_huddle_reference(terminal, payload["revision"])
            key = _claim_key(original)
            terminal_key = _claim_key(terminal)
            if (key in replacement_originals or terminal_key in replacement_currents
                    or original["entity"] != terminal["entity"]
                    or original["row"] != terminal["row"]
                    or terminal["claim_revision"] <= original["claim_revision"]
                    or _timestamp(terminal["claimed_at"], "replacement time") <= _timestamp(original["claimed_at"], "original time")
                    or key in current or terminal_key in refs
                    or not resolved and terminal_key in members):
                raise BoardError("Huddle replacement identity is invalid")
            replacement_originals.add(key)
            replacement_currents.add(terminal_key)
            if not resolved:
                members.add(terminal_key)
        if replacements != sorted(replacements, key=lambda item: _claim_rank(item["original"])):
            raise BoardError("Huddle replacements are not canonically ordered")
        # Graph evidence keeps its frozen endpoints. Declaration checks use
        # the settled operating role, including an exact handoff successor.
        edge_refs = dict(refs)
        if settled and isinstance(h["resolution"], dict):
            handoff = h["resolution"].get("handoff")
            if isinstance(handoff, dict):
                source, successor = handoff.get("source_claim"), handoff.get("successor_claim")
                _validate_huddle_reference(source, payload["revision"])
                _validate_huddle_reference(successor, payload["revision"])
                edge_refs[_claim_key(source)] = successor
        edge_current = {key: current[terminal] for key, ref in edge_refs.items()
                        if (terminal := _claim_key(_terminal_ref(h, ref))) in current}
        if not isinstance(h["edges"], list) or not (0 if settled else 1) <= len(h["edges"]) <= 2016:
            raise BoardError("Huddle edge cap or minimum violated")
        pairs = set()
        for edge in h["edges"]:
            if not isinstance(edge, dict) or set(edge) != {"left", "right", "kinds"}:
                raise BoardError("Huddle edge fields are invalid")
            if any(not _valid_claim_ref(edge[k]) or edge[k] not in h["claims"] for k in ("left", "right")):
                raise BoardError("Huddle edge points outside its claims")
            if _claim_rank(edge["left"]) >= _claim_rank(edge["right"]):
                raise BoardError("Huddle edge endpoints are not ordered")
            pair = (_claim_key(edge["left"]), _claim_key(edge["right"]))
            kinds = edge["kinds"]
            if (not isinstance(kinds, list) or not kinds or any(not isinstance(k, str) or k not in _EDGE_KINDS for k in kinds)
                or kinds != sorted(set(kinds)) or pair in pairs):
                raise BoardError("Huddle edge kinds or uniqueness are invalid")
            pairs.add(pair)
            if not resolved and all(key in edge_current for key in pair):
                actual = _scope_edge(edge_current[pair[0]], edge_current[pair[1]])
                if sorted(k for k in kinds if k != "semantic_suspicion") != actual:
                    raise BoardError("Huddle path edges disagree with current declarations")
        ordered_refs = h["claims"]
        for index, left in enumerate(ordered_refs):
            for right in ordered_refs[index + 1:]:
                pair = (_claim_key(left), _claim_key(right))
                if (not resolved and all(key in edge_current for key in pair)
                    and _scope_edge(edge_current[pair[0]], edge_current[pair[1]]) and pair not in pairs):
                    raise BoardError("Huddle is missing a current scope edge")
        ordered = sorted(h["edges"], key=lambda e: (_claim_rank(e["left"]), _claim_rank(e["right"])))
        if h["edges"] != ordered:
            raise BoardError("Huddle edges are not canonically ordered")
        _reference_list(h["holds"], payload["revision"], "Huddle holds", limit=65 if h["state"] == "remote_pending" else 64)
        unknown = any("scope_unknown" in e["kinds"] for e in h["edges"])
        if (h["state"] == "awaiting_scope" and (not unknown or h["round"] != 0 or h["bids"] != [])
            or h["state"] in {"open_round_1", "open_round_2"} and (unknown or h["round"] != int(h["state"][-1]))
            or h["state"] == "remote_pending" and h["round"] not in (1, 2)):
            raise BoardError("Huddle state disagrees with round or scope edges")
        _validate_bids(h, payload)
        _validate_remote_transition(h, payload["revision"])
        if not resolved and (h["resolved_at"] is not None or h["retain_until"] is not None):
            raise BoardError("live Huddle cannot have resolution timestamps")
        if not settled:
            if h["resolution"] is not None or h["compliance"] != []:
                raise BoardError("unsettled Huddle has resolution or compliance")
            expected_holds = claim_holds(h)
            if h["state"] == "remote_pending":
                remote = h["remote_transition"]
                if remote is None or remote["readback"] not in {"not_attempted", "ambiguous"}:
                    raise BoardError("pending remote Huddle needs unresolved readback")
                # The successor is not installed locally yet. Its exact transfer
                # reference is nevertheless held alongside the predecessor.
                held = {_claim_key(c): c for c in expected_holds}
                for field in ("source_claim", "successor_claim"):
                    held[_claim_key(remote[field])] = remote[field]
                expected_holds = sorted(held.values(), key=_claim_rank)
            elif h["remote_transition"] is not None:
                raise BoardError("open Huddle cannot have a remote transition")
        else:
            if h["remote_transition"] is not None and h["remote_transition"]["readback"] not in {"successor", "predecessor"}:
                raise BoardError("settled Huddle cannot have unresolved remote ownership")
            pending = _validate_resolution(h, payload)
            roles = dict(refs)
            handoff = h["resolution"]["handoff"]
            if handoff:
                roles.pop(_claim_key(handoff["source_claim"]))
                roles[_claim_key(handoff["successor_claim"])] = handoff["successor_claim"]
            if any(roles.get(_claim_key(item["original"])) != item["original"]
                   for item in replacements):
                raise BoardError("Huddle replacement must name one frozen operating role")
            if any(item["current"]["claim_revision"] <= h["resolution"]["settled_revision"]
                   for item in replacements):
                raise BoardError("Huddle replacement must follow settlement")
            if bool(pending) != (h["state"] == "awaiting_compliance"):
                raise BoardError("Huddle state disagrees with pending compliance")
            expected_holds = sorted((refs[key] for key in pending), key=_claim_rank)
        if h["holds"] != expected_holds:
            raise BoardError("Huddle holds disagree with state authority")
        if not resolved:
            historical = set()
            if settled:
                historical.update(_claim_key(e["claim"]) for e in h["compliance"] if e["status"] == "satisfied")
                resolution = h["resolution"]
                actions = {_claim_key(action["claim"]): action["action"]
                           for action in resolution["actions"]}
                writer_keys = {_claim_key(ref) for ref in resolution["write_owners"]}
                # A proof-first stale close can remove only a continuing writer
                # while a different participant remains pending compliance.
                historical.update(
                    key for key in writer_keys
                    if key in refs and _claim_key(_terminal_ref(h, refs[key])) not in current and actions.get(key) in {
                        "continue", "continue_disjoint", "handoff_complete",
                    }
                )
                handoff = resolution["handoff"]
                if handoff:
                    historical.add(_claim_key(handoff["source_claim"]))
                    successor = _terminal_ref(h, handoff["successor_claim"])
                    key = _claim_key(successor)
                    if key in current and (_claim_ref(current[key]) != successor
                                           or key in members and key not in replacement_currents):
                        raise BoardError("Huddle successor is not its unique current source claim")
                    if key in current:
                        members.add(key)
                    elif _claim_key(handoff["successor_claim"]) not in writer_keys:
                        raise BoardError("Huddle successor is not an authorized continuing writer")
            for key, ref in refs.items():
                terminal = _terminal_ref(h, ref)
                terminal_key = _claim_key(terminal)
                if (key not in historical and (terminal_key not in current
                        or _claim_ref(current[terminal_key]) != terminal
                        or current[terminal_key]["access"] == "read_only")):
                    raise BoardError("Huddle reference is not a current source claim")
        if len(json.dumps(h, sort_keys=True, separators=(",", ":")).encode("utf-8")) > 4 * 1024 * 1024:
            raise BoardError("Huddle encoded size cap exceeded")
    for h in records:
        if h["state"] == "resolved":
            continue
        for bid in h["bids"]:
            support = bid["support_claim"]
            if support is not None and bid["round"] == h["round"]:
                key = _claim_key(support)
                if key in members or key not in current or _claim_ref(current[key]) != support:
                    raise BoardError("Huddle support must remain current outside every live Huddle")


def _validate_v2(payload: object, *, pending_retention: bool = False) -> dict:
    if not isinstance(payload, dict) or set(payload) != {
        "schema", "revision", "projects", "entities", "claims", "huddles"
    }:
        raise BoardError("board has unknown or missing top-level fields")
    if payload["schema"] != V2_SCHEMA:
        raise BoardError("board schema is not supported")
    if not isinstance(payload["claims"], list):
        raise BoardError("board projects, entities, and claims must be lists")
    claim_fields = {
        "entity", "row", "owner", "claimed_at", "return_by", "recovery",
        "claim_revision", "access", "repository_binding", "write_scope",
    }
    old_claim_fields = {
        "entity", "row", "owner", "claimed_at", "return_by", "recovery",
    }
    for claim in payload["claims"]:
        if not isinstance(claim, dict) or set(claim) != claim_fields:
            raise BoardError("claims have unknown or missing fields")

    v1_projection = {
        "schema": V1_SCHEMA,
        "revision": payload["revision"],
        "projects": payload["projects"],
        "entities": payload["entities"],
        "claims": [
            {key: claim[key] for key in old_claim_fields}
            for claim in payload["claims"]
        ],
    }
    _validate_v1(v1_projection)

    for claim in payload["claims"]:
        claim_revision = claim["claim_revision"]
        if (
            isinstance(claim_revision, bool)
            or not isinstance(claim_revision, int)
            or claim_revision < 0
            or claim_revision > payload["revision"]
        ):
            raise BoardError("claim revision must be a current nonnegative integer")
        access = claim["access"]
        if not isinstance(access, str) or access not in {"unscoped", "read_only", "write"}:
            raise BoardError("claim access is not supported")
        scope = _validate_write_scope(claim["write_scope"])
        binding = claim["repository_binding"]

        if access == "read_only":
            if binding is not None or scope:
                raise BoardError("read-only claims must be unbound with empty scope")
        elif access == "unscoped":
            if binding is not None:
                _validate_repository_binding(binding)
            if scope:
                raise BoardError("unscoped claims must have empty scope")
        else:
            _validate_repository_binding(binding)
            if not scope:
                raise BoardError("write claims must have nonempty scope")

    _validate_huddles(payload, pending_retention=pending_retention)
    return payload


def _validate(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise BoardError("board has unknown or missing top-level fields")
    schema = payload.get("schema")
    if schema == V1_SCHEMA:
        return _validate_v1(payload)
    if schema == V2_SCHEMA:
        return _validate_v2(payload)
    raise BoardError("board schema is not supported")


def _strict_json_object(pairs: list[tuple[str, object]]) -> dict:
    value: dict = {}
    for key, item in pairs:
        if key in value:
            raise BoardError("board JSON contains duplicate object keys")
        value[key] = item
    return value


def _timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise BoardError(f"{label} must be an ISO8601 Z timestamp")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise BoardError(f"{label} must be an ISO8601 Z timestamp") from exc
    return parsed.replace(tzinfo=timezone.utc)


validate_board = _validate


def decode_board_bytes(data: bytes) -> dict:
    """Decode exact bytes with duplicate-key refusal and the complete schema."""
    if not isinstance(data, bytes):
        raise BoardError("board decoder requires bytes")
    try:
        return validate_board(json.loads(data, object_pairs_hook=_strict_json_object))
    except (UnicodeError, ValueError) as exc:
        raise BoardError("board file is unreadable or malformed") from exc
