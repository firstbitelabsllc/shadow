#!/usr/bin/env python3
"""On-demand native metadata inventory. No provider, network or authority writes.

This is consumption evidence, not a task/acceptance join or model leaderboard.
Only explicitly selected regular JSONL files are read; no discovery is performed.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

MAX_LINE = 1024 * 1024
MAX_BYTES = 64 * 1024 * 1024
MAX_SOURCES = 64
HOSTS = ("codex", "codex-zai", "claude", "grok")
FIELDS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "reasoning_tokens")
MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,95}\Z")


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


def parse(host, records, digest, start, end):
    requested, native, gaps = set(), set(), set()
    ids, messages, snapshots = set(), {}, []
    included = ignored = 0
    is_codex = host in ("codex", "codex-zai")
    for record in records:
        payload = record.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        kind = record.get("type")
        sid = payload.get("id") if kind == "session_meta" and is_codex else record.get("sessionId")
        if isinstance(sid, str) and sid:
            ids.add(sid)
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
            "partial_window": bool(start or end), "metadata_records": included,
            "uninterpreted_records": ignored, "gaps": sorted(gaps)}


def audit(sources, since=None, until=None):
    if not sources or len(sources) > MAX_SOURCES:
        raise Refusal("sources_required_or_limit")
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
    return {"schema": "shadow.efficiency-inventory.v1", "query_version": 1,
            "scope": "explicit_local_sources_only_not_a_representative_sample",
            "window": {"since": start.isoformat() if start else None, "until": end.isoformat() if end else None},
            "coverage": {"selected_sources": len(sources), "duplicate_sources": duplicate,
                         "parsed_records": parsed, "malformed_records": 0,
                         "reported_sessions": len(rows), "sessions_with_input_output_counters": sum(r["usage"] is not None for r in rows),
                         "sessions_with_native_response_model": sum(bool(r["native_response_models"]) for r in rows),
                         "mapped_root_tasks": 0, "total_eligible_root_tasks": None},
            "session_counts_by_harness": dict(sorted(Counter(r["harness"] for r in rows).items())),
            "real_work_allocation": None, "accepted_work_rate": None,
            "sources": fingerprints, "sessions": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", required=True, metavar="HARNESS=JSONL")
    parser.add_argument("--since", help="inclusive timezone-aware timestamp")
    parser.add_argument("--until", help="exclusive timezone-aware timestamp")
    args = parser.parse_args()
    try:
        sources = []
        for value in args.source:
            host, sep, path = value.partition("=")
            if not sep or not path:
                raise Refusal("source_format")
            sources.append((host, Path(path)))
        result = audit(sources, args.since, args.until)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except Refusal as exc:
        print(json.dumps({"schema": "shadow.efficiency-inventory.v1", "result": "refused", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
