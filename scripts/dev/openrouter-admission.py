#!/usr/bin/env python3
"""Offline admission logic; no host selection, provider I/O or receipt collector.

Inputs belong to the ordinary seat. Before live use, that caller must verify
each referenced native quota/outage observation. A model-supplied digest or
JSON object is not authenticated evidence. This experiment registers no host.
"""
import re
import shadow_execution_policy as policy

FRESHNESS_SECONDS = 300


class Refused(ValueError):
    pass


def admit(work_class, selection, observations, *, now):
    if work_class not in policy.WORK_CLASSES or type(now) is not int or now < 0:
        raise Refused("unknown work class or invalid clock")
    if not isinstance(observations, list):
        raise Refused("invalid ordinary-route observations")
    if selection == "explicit":
        if observations:
            raise Refused("explicit selection cannot be inferred from outages")
        return {"admission": "explicit", "work_class": work_class}
    if selection != "unavailable":
        raise Refused("explicit selection or complete fresh unavailability is required")
    expected = {host: policy.resolve_route(host, work_class).model for host in policy.HOSTS}
    if len(observations) != len(expected):
        raise Refused("every ordinary route needs a fresh observation")
    seen = set()
    fields = {"host", "work_class", "model", "observed_at", "expires_at", "reason", "evidence_sha256"}
    for item in observations:
        if not isinstance(item, dict) or item.keys() != fields:
            raise Refused("invalid observation fields")
        host = item["host"]
        if not isinstance(host, str) or host not in expected or host in seen:
            raise Refused("unknown or duplicate ordinary route")
        if item["work_class"] != work_class or item["model"] != expected[host]:
            raise Refused("observation does not bind the current class and model")
        start, end = item["observed_at"], item["expires_at"]
        if type(start) is not int or type(end) is not int or not 0 <= start <= now < end <= start + FRESHNESS_SECONDS:
            raise Refused("observation is stale, future-dated or overlong")
        digest = item["evidence_sha256"]
        if item["reason"] not in ("quota", "outage") or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise Refused("native quota/outage evidence must be explicitly attributed")
        seen.add(host)
    return {"admission": "unavailable", "work_class": work_class,
            "policy": policy.POLICY_VERSION, "routes": expected,
            "expires_at": min(item["expires_at"] for item in observations),
            "scope": "logic-only; caller must authenticate native evidence"}
