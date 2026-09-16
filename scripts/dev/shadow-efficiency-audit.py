#!/usr/bin/env python3
"""On-demand native metadata inventory. No provider, network or authority writes.

This is consumption evidence, not a task/acceptance join or model leaderboard.
Only explicitly selected regular JSONL files are read; no discovery is performed.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import shadow_plan_grammar as _grammar  # noqa: E402
import shadow_plan_store as _plan_store  # noqa: E402

MAX_LINE = 1024 * 1024
MAX_BYTES = 64 * 1024 * 1024
MAX_SOURCES = 64
HOSTS = ("codex", "codex-zai", "claude", "grok")
FIELDS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "reasoning_tokens")
MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,95}\Z")
MAX_MARKERS_PER_SOURCE = 4096
MAX_JOIN_ROWS = 1024
ENTITY_RE = re.compile(r"[0-9a-f]{64}\Z")
# Credit markers only from structured command records; free text stays provenance.
SHADOW_VERB_RE = re.compile(
    r"(?:^|[\s`])shadow(?:-plan\.py)? (?P<verb>accept|throw|return|amp)(?:\.py)?\b"
)
ROW_ARG_RE = re.compile(r"--(?:task|row)[ =][`\"']?(~[0-9a-z]{4})\b")
ENTITY_ARG_RE = re.compile(r"--entity[ =]([0-9a-f]{64})\b")
SEAT_ARG_RE = re.compile(r"--by[ =]([A-Za-z0-9._-]{1,64})\b")
# A credited marker far before the row's accept proof (backdated >7d) or far
# after (>48h) is flagged for human eyes; never an automatic refusal.
DRIFT_BACK = timedelta(days=7)
DRIFT_FORWARD = timedelta(hours=48)


class Refusal(ValueError):
    """Only fixed reason codes may leave the reader on error."""


def utc(value):
    if not isinstance(value, str):
        return None
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return t.astimezone(timezone.utc) if t.tzinfo else None
    except ValueError:
        return None


def label(value):
    return value if isinstance(value, str) and MODEL.fullmatch(value) else None


def opaque(value):
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def read_source(path):
    """Reject symlink components, bound reads, and fingerprint the bytes read."""
    path = Path(os.path.abspath(path))
    try:
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise Refusal("symlink_input")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise Refusal("regular_file_required")
            if before.st_size > MAX_BYTES:
                raise Refusal("source_byte_limit")
            digest = hashlib.sha256()
            records, size = [], 0
            while True:
                line = stream.readline(MAX_LINE + 1)
                if not line:
                    break
                if len(line) > MAX_LINE:
                    raise Refusal("line_limit")
                size += len(line)
                if size > MAX_BYTES:
                    raise Refusal("source_byte_limit")
                digest.update(line)
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except (ValueError, UnicodeError, RecursionError):
                    raise Refusal("malformed_json") from None
                if not isinstance(item, dict):
                    raise Refusal("object_required")
                records.append(item)
            after = os.fstat(stream.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_ino) != (
                    after.st_size, after.st_mtime_ns, after.st_ino):
                raise Refusal("source_changed_during_read")
            return digest.hexdigest(), records, size
    except OSError:
        raise Refusal("source_unreadable") from None


def usage(raw, codex=False):
    if not isinstance(raw, dict):
        return None
    aliases = {"cache_read_tokens": "cached_input_tokens" if codex else "cache_read_input_tokens",
               "cache_write_tokens": "cache_creation_input_tokens",
               "reasoning_tokens": "reasoning_output_tokens"}
    result = {k: raw.get(aliases.get(k, k)) for k in FIELDS}
    if any(v is not None and (type(v) is not int or v < 0) for v in result.values()):
        return None
    return result if result["input_tokens"] is not None and result["output_tokens"] is not None else None


def decrease(previous, current):
    return any(previous.get(k) is not None and current.get(k) is not None
               and current[k] < previous[k] for k in FIELDS)


def _tool_use_commands(node, out, depth=0):
    """Collect command strings from structured tool_use blocks only, bounded."""
    if depth > 6 or len(out) >= 64:
        return
    if isinstance(node, dict):
        if node.get("type") == "tool_use" and isinstance(node.get("input"), dict) \
                and isinstance(node["input"].get("command"), str):
            out.append(node["input"]["command"])
        elif node.get("type") == "function_call" and isinstance(node.get("arguments"), str):
            out.append(node["arguments"])
        else:
            for value in node.values():
                _tool_use_commands(value, out, depth + 1)
    elif isinstance(node, list):
        for value in node[:64]:
            _tool_use_commands(value, out, depth + 1)


def marker_from_record(host, record, payload, kind, t, markers):
    """Credit candidates come only from structured command records.

    Claude: assistant ``tool_use`` blocks with a ``command`` input (Bash).
    Codex family: ``function_call`` records and exec event payloads.
    Prose that merely quotes a command never becomes a marker.
    """
    if len(markers) >= MAX_MARKERS_PER_SOURCE:
        raise Refusal("marker_limit")
    texts = []
    prose = []
    if host == "claude" and kind == "assistant":
        message = record.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), list):
            for block in message["content"]:
                if (isinstance(block, dict) and block.get("type") == "tool_use"
                        and isinstance(block.get("input"), dict)
                        and isinstance(block["input"].get("command"), str)):
                    texts.append(block["input"]["command"])
                elif isinstance(block, dict) and block.get("type") == "text" \
                        and isinstance(block.get("text"), str):
                    prose.append(block["text"])
    elif host in ("codex", "codex-zai"):
        if kind == "function_call":
            args = payload.get("arguments") or payload.get("command")
            if isinstance(args, str):
                texts.append(args)
        elif kind == "event_msg" and payload.get("type") in ("exec_command_begin", "exec_command_end"):
            command = payload.get("command")
            if isinstance(command, str):
                texts.append(command)
            elif isinstance(command, list):
                texts.append(" ".join(str(part) for part in command))
        elif kind == "model_io":
            # Harness model-call transcripts: tool calls live in the request
            # messages and response content; only structured tool_use blocks count.
            _tool_use_commands(record.get("request"), texts)
            _tool_use_commands(record.get("response"), texts)
    for via, batch in (("tool_call", texts), ("text", prose)):
        for text in batch:
            verb = SHADOW_VERB_RE.search(text)
            if verb is None:
                continue
            row = ROW_ARG_RE.search(text)
            if row is None:
                continue
            entity = ENTITY_ARG_RE.search(text)
            seat = SEAT_ARG_RE.search(text)
            markers.append({
                "ts": t.isoformat() if t else None,
                "verb": verb.group("verb"),
                "row": row.group(1),
                "entity": entity.group(1) if entity else None,
                "seat": seat.group(1) if seat else None,
                "via": via,
            })


def dedupe_markers(markers):
    """API-request payloads replay prior turns, so one real marker recurs per
    turn. Keep the first occurrence (the creating turn) per identity; the cap
    then guards volume, not history length."""
    seen, deduped = set(), []
    for marker in markers:
        key = (marker.get("via"), marker["verb"], marker["row"],
               marker.get("entity"), marker.get("seat"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(marker)
    return deduped


def load_plan_eligibility(plan_path, entity, start, end):
    """Completed rows whose last dated accept-proof timestamp falls in the window."""
    if entity is None or ENTITY_RE.fullmatch(entity) is None:
        raise Refusal("plan_entity_unresolved")
    try:
        snapshot = _plan_store.PlanSnapshot.open(Path(plan_path))
        text = snapshot.materialize().decode("utf-8")
    except (_plan_store.PlanStoreError, OSError, UnicodeError):
        raise Refusal("plan_unreadable") from None
    last_proof = {}
    completed = set()
    in_progress_section = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_progress_section = line.strip() == "## Progress"
            continue
        row = _grammar.ROW_RE.match(line)
        if row is not None:
            if row.group("state") == "completed":
                completed.add(row.group("id"))
            continue
        if not in_progress_section:
            continue
        receipt = _grammar.PROOF_RECEIPT_PREFIX_RE.match(line)
        if receipt is None or receipt.group("id") not in completed:
            continue
        ts = utc(receipt.group("ts"))
        if ts is None:
            continue
        rid = receipt.group("id")
        if rid not in last_proof or ts > last_proof[rid]:
            last_proof[rid] = ts
    eligible, undated = {}, []
    for rid in sorted(completed):
        ts = last_proof.get(rid)
        if ts is None:
            undated.append(rid)
        elif (start is None or ts >= start) and (end is None or ts < end):
            eligible[rid] = ts
    reader_digests = {
        module.__name__: hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
        for module in (_grammar, _plan_store)
    }
    return {
        "entity": entity,
        "generation": snapshot.root["generation"] if snapshot.root else 0,
        "root_sha256": snapshot.root_sha256,
        "reader_digests": reader_digests,
        "eligible": eligible,
        "undated": undated,
    }


def join_roots(plan_info, sessions):
    """Credit accepts to the transcript session; --by is provenance, never credit."""
    eligible = plan_info["eligible"]
    credit = {}       # row -> set of session_ref
    unmatched = []    # accepts that do not resolve to an eligible row/entity
    provenance = []   # non-accept markers, capped detail
    disagreements = []
    for session in sessions:
        for marker in session.get("markers", ()):
            if marker["verb"] != "accept" or marker.get("via") != "tool_call":
                if len(provenance) < MAX_JOIN_ROWS:
                    provenance.append({"session": session["session_ref"], **marker})
                continue
            row = marker["row"]
            if row not in eligible:
                unmatched.append({"session": session["session_ref"], "reason": "row_not_eligible", **marker})
                continue
            if marker["entity"] != plan_info["entity"]:
                unmatched.append({"session": session["session_ref"], "reason": "entity_mismatch", **marker})
                continue
            credit.setdefault(row, set()).add(session["session_ref"])
            if marker["ts"] is not None:
                marker_ts = utc(marker["ts"])
                proof_ts = eligible[row]
                if marker_ts < proof_ts - DRIFT_BACK or marker_ts > proof_ts + DRIFT_FORWARD:
                    disagreements.append({"session": session["session_ref"], "row": row,
                                          "marker_ts": marker["ts"], "proof_ts": proof_ts.isoformat()})
            if len(credit) > MAX_JOIN_ROWS:
                raise Refusal("join_limit")
    mapped = sorted(credit)
    unmapped = [{"row": rid, "reason": "no_accept_marker"} for rid in eligible if rid not in credit]
    allocation = {}
    for harness in HOSTS:
        members = [s for s in sessions if s["harness"] == harness]
        credited_sessions = [s for s in members
                             if any(s["session_ref"] in credit[row] for row in eligible if row in credit)]
        if not credited_sessions:
            continue
        allocation[harness] = {
            "credited_sessions": len(credited_sessions),
            "sessions_with_known_usage": sum(s["usage"] is not None for s in credited_sessions),
            "credited_rows": len({row for row in credit for s in credited_sessions if s["session_ref"] in credit[row]}),
        }
    return {
        "plan_snapshot": {"entity": plan_info["entity"], "generation": plan_info["generation"],
                          "root_sha256": plan_info["root_sha256"]},
        "eligible_root_tasks": len(eligible),
        "undated_completed_rows": plan_info["undated"],
        "mapped_root_tasks": len(mapped),
        "mapped_rows": mapped,
        "unmapped": unmapped,
        "unmatched_accepts": unmatched,
        "split_unknown_rows": sorted(row for row, refs in credit.items() if len(refs) > 1),
        "marker_disagreements": disagreements,
        "provenance_markers": provenance,
        "real_work_allocation": allocation,
        "accepted_work_rate": (len(mapped) / len(eligible)) if eligible else None,
    }


def parse(host, records, digest, start, end):
    requested, native, gaps = set(), set(), set()
    ids, messages, snapshots = set(), {}, []
    included = ignored = 0
    markers = []
    is_codex = host in ("codex", "codex-zai")
    for record in records:
        payload = record.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        kind = record.get("type")
        sid = payload.get("id") if kind == "session_meta" and is_codex else record.get("sessionId")
        if isinstance(sid, str) and sid:
            ids.add(sid)
        marker_from_record(host, record, payload, kind,
                           utc(record.get("timestamp") or record.get("completedAt")), markers)
        if is_codex and kind == "turn_context":
            model = label(payload.get("model"))
            if model:
                requested.add(model)
        if is_codex and kind == "event_msg" and payload.get("type") == "token_count":
            info = payload.get("info")
            if not isinstance(info, dict) or info.get("total_token_usage") is None:
                ignored += 1
                continue
            value = usage(info["total_token_usage"], True)
            if value is None:
                gaps.add("invalid_usage")
            else:
                snapshots.append((utc(record.get("timestamp")), value))
            included += 1
        elif host == "claude" and kind == "assistant":
            message = record.get("message")
            if not isinstance(message, dict):
                gaps.add("unrecognized_response")
                continue
            sid = record.get("sessionId")
            if not isinstance(sid, str) or not sid:
                gaps.add("session_identity_missing")
            t = utc(record.get("timestamp"))
            if (start or end) and t is None:
                gaps.add("timestamp_missing")
                continue
            if (start and t < start) or (end and t >= end):
                continue
            mid = message.get("id")
            if not isinstance(mid, str) or not mid:
                gaps.add("message_identity_missing")
                continue
            model = label(message.get("model"))
            if model and model not in ("Auto", "auto", "unknown"):
                native.add(model)
            value = usage(message.get("usage"))
            if value is None:
                gaps.add("invalid_usage")
                continue
            if mid in messages and decrease(messages[mid], value):
                gaps.add("message_usage_conflict")
            messages[mid] = value
            included += 1
        else:
            ignored += 1
    if len(ids) > 1:
        gaps.add("multiple_session_ids")
    elif not ids:
        gaps.add("session_identity_missing")
    result_usage = None
    if is_codex and snapshots:
        previous = baseline = final = None
        seen_in_window = False
        last_time = None
        for t, value in snapshots:
            if previous is not None and decrease(previous, value):
                gaps.add("cumulative_reset")
            previous = value
            if t is not None and last_time is not None and t < last_time:
                gaps.add("timestamp_order")
            last_time = t if t is not None else last_time
            if (start or end) and t is None:
                gaps.add("timestamp_missing")
                continue
            if start and t < start:
                baseline = value
            elif not end or t < end:
                final = value
                seen_in_window = True
        if start and baseline is None:
            gaps.add("window_baseline_missing")
        if final is not None and seen_in_window:
            result_usage = {k: (final[k] - baseline[k] if start and baseline is not None
                               and baseline[k] is not None and final[k] is not None
                               else final[k] if not start else None) for k in FIELDS}
    elif messages:
        result_usage = {k: sum(v[k] for v in messages.values())
                        if all(v[k] is not None for v in messages.values()) else None for k in FIELDS}
    if gaps:
        result_usage = None
    if host == "grok":
        gaps.add("grok_native_usage_adapter_unverified")
    if result_usage is None and not gaps:
        gaps.add("usage_not_exposed")
    if not native:
        gaps.add("native_response_model_not_exposed")
    gaps.update(("canonical_task_join_missing", "native_lineage_join_missing",
                 "cost_not_exposed", "attention_not_measured"))
    session_key = next(iter(ids)) if len(ids) == 1 else digest
    return {"session_ref": opaque(host + ":" + session_key), "harness": host,
            "source_digests": [digest], "requested_models": sorted(requested),
            "native_response_models": sorted(native),
            "model_witness": "native_response_label_not_provider_attestation" if native else None,
            "usage": result_usage,
            "usage_basis": "session_cumulative_inclusive_cache_and_reasoning" if is_codex else
                           "distinct_message_usage_cache_separate" if host == "claude" else None,
            "accepted_root_task": None, "confirmed_delegation": None,
            "cost_usd": None, "attention_minutes": None,
            "markers": dedupe_markers(markers),
            "partial_window": bool(start or end), "metadata_records": included,
            "uninterpreted_records": ignored, "gaps": sorted(gaps)}


def audit(sources, since=None, until=None, plan_path=None, entity=None):
    if not sources or len(sources) > MAX_SOURCES:
        raise Refusal("sources_required_or_limit")
    if (plan_path is None) != (entity is None):
        raise Refusal("plan_entity_unresolved")
    start, end = utc(since), utc(until)
    if (since and start is None) or (until and end is None) or (start and end and start >= end):
        raise Refusal("invalid_utc_window")
    sessions, fingerprints, seen = {}, [], set()
    duplicate = parsed = total_bytes = 0
    for host, path in sources:
        if host not in HOSTS:
            raise Refusal("unsupported_harness")
        digest, records, size = read_source(path)
        total_bytes += size
        if total_bytes > MAX_BYTES:
            raise Refusal("aggregate_byte_limit")
        fingerprints.append({"harness": host, "sha256": digest, "bytes": size, "records": len(records)})
        parsed += len(records)
        if (host, digest) in seen:
            duplicate += 1
            continue
        seen.add((host, digest))
        session = parse(host, records, digest, start, end)
        key = session["session_ref"]
        if key in sessions:
            existing = sessions[key]
            existing["usage"] = None
            existing["source_digests"].append(digest)
            existing["requested_models"] = sorted(set(existing["requested_models"] + session["requested_models"]))
            existing["native_response_models"] = sorted(set(existing["native_response_models"] + session["native_response_models"]))
            existing["gaps"] = sorted(set(existing["gaps"] + session["gaps"] + ["conflicting_session_copies"]))
        else:
            sessions[key] = session
    rows = sorted(sessions.values(), key=lambda s: s["session_ref"])
    join = None
    coverage_mapped, coverage_eligible = 0, None
    allocation, rate = None, None
    if plan_path is not None:
        plan_info = load_plan_eligibility(plan_path, entity, start, end)
        join = join_roots(plan_info, rows)
        coverage_mapped = join["mapped_root_tasks"]
        coverage_eligible = join["eligible_root_tasks"]
        allocation, rate = join["real_work_allocation"], join["accepted_work_rate"]
    return {"schema": "shadow.efficiency-inventory.v1", "query_version": 2,
            "scope": "explicit_local_sources_only_not_a_representative_sample",
            "window": {"since": start.isoformat() if start else None, "until": end.isoformat() if end else None},
            "coverage": {"selected_sources": len(sources), "duplicate_sources": duplicate,
                         "parsed_records": parsed, "malformed_records": 0,
                         "reported_sessions": len(rows), "sessions_with_input_output_counters": sum(r["usage"] is not None for r in rows),
                         "sessions_with_native_response_model": sum(bool(r["native_response_models"]) for r in rows),
                         "mapped_root_tasks": coverage_mapped, "total_eligible_root_tasks": coverage_eligible},
            "session_counts_by_harness": dict(sorted(Counter(r["harness"] for r in rows).items())),
            "real_work_allocation": allocation, "accepted_work_rate": rate,
            "join": join,
            "sources": fingerprints,
            "sessions": [{k: v for k, v in r.items() if k != "markers"} for r in rows]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", required=True, metavar="HARNESS=JSONL")
    parser.add_argument("--since", help="inclusive timezone-aware timestamp")
    parser.add_argument("--until", help="exclusive timezone-aware timestamp")
    parser.add_argument("--plan", help="machine-local entity PLAN.md for the eligible-root join")
    parser.add_argument("--entity", help="board entity id that owns --plan (64 hex)")
    args = parser.parse_args()
    try:
        sources = []
        for value in args.source:
            host, sep, path = value.partition("=")
            if not sep or not path:
                raise Refusal("source_format")
            sources.append((host, Path(path)))
        result = audit(sources, args.since, args.until, args.plan, args.entity)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except Refusal as exc:
        print(json.dumps({"schema": "shadow.efficiency-inventory.v1", "result": "refused", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
