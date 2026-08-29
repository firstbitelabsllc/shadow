#!/usr/bin/env python3
"""Owner-local observed gauntlet: long Shadow test jobs traced into Langfuse.

This NEVER runs for users and is not part of the product runtime: the ~obsv
decision (Langfuse KILLED as a product dependency — Shadow makes zero network
calls) stands untouched. This is owner tooling behind an explicit local
opt-in, per the owner's 2026-08-11 direction recorded in
docs/reference/telemetry.md § Local sink: a Langfuse instance on the owner's
own machine receives traces of long test jobs for debugging and
observability, and a machine without the three env vars below behaves
exactly as it does today.

Refuses unless ALL of these are set:
    SHADOW_LANGFUSE_HOST         e.g. http://localhost:3000
    SHADOW_LANGFUSE_PUBLIC_KEY   the local project's public key
    SHADOW_LANGFUSE_SECRET_KEY   the local project's secret key

Every round's trace is verified by exact trace-ID readback; accepted HTTP
without readback turns the exit code red. On Langfuse v3 the readback uses
the web API. On Langfuse v4 (`events_only` mode) the web API is gone, so set
these optional vars to read back from ClickHouse `default.events_core`
instead (loopback only):
    SHADOW_LANGFUSE_READBACK_URL       e.g. http://localhost:8123
    SHADOW_LANGFUSE_PROJECT_ID         the local project id
    SHADOW_LANGFUSE_READBACK_USER      ClickHouse user, if the instance requires auth
    SHADOW_LANGFUSE_READBACK_PASSWORD  ClickHouse password

Optionally forwards a Shadow local event file (the SHADOW_TELEMETRY=local
output, already allowlisted and redacted at emission) as spans:
    SHADOW_LANGFUSE_EVENTS       path to a shadow-events.jsonl

Usage:
    scripts/shadow-python.sh scripts/dev/shadow-observed-gauntlet.py \
        [--rounds N] [--jobs name,name,...]
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent.parent
PYTHON = ROOT / "scripts" / "shadow-python.sh"

# Long jobs, heaviest last. Each runs in its own process from the repo root.
JOBS: dict[str, list[str]] = {
    "root-board": ["-m", "unittest", "tests.test_root_board"],
    "lifecycle": ["-m", "unittest", "tests.test_lifecycle"],
    "accept": ["-m", "unittest", "tests.test_shadow_accept"],
    "throw": ["-m", "unittest", "tests.test_throw"],
    "telemetry": ["-m", "unittest", "tests.test_telemetry"],
    "browser": ["-m", "unittest", "tests.test_browser"],
    "verify-host": ["-m", "unittest", "tests.test_verify_host"],
    "gauntlet": ["-m", "unittest", "tests.test_gauntlet"],
    "two-seat-offline": ["-m", "unittest", "tests.test_two_seat_harness"],
    "full-discover": ["-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
}

HOME_PREFIX = str(Path.home())


def _redact(text: str) -> str:
    """The owner's home path never leaves the machine spelled out."""
    return text.replace(HOME_PREFIX, "~")


def _attr(key: str, value: object) -> dict:
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    if isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    return {"key": key, "value": {"stringValue": str(value)}}


class Sink:
    def __init__(self) -> None:
        host = os.environ.get("SHADOW_LANGFUSE_HOST", "")
        public = os.environ.get("SHADOW_LANGFUSE_PUBLIC_KEY", "")
        secret = os.environ.get("SHADOW_LANGFUSE_SECRET_KEY", "")
        if not (host and public and secret):
            print(
                "shadow-observed-gauntlet: owner opt-in only — set "
                "SHADOW_LANGFUSE_HOST, SHADOW_LANGFUSE_PUBLIC_KEY, and "
                "SHADOW_LANGFUSE_SECRET_KEY to run; without them this tool "
                "does nothing, exactly like the product.",
                file=sys.stderr,
            )
            raise SystemExit(2)
        self.host = host.rstrip("/")
        self.endpoint = host.rstrip("/") + "/api/public/otel/v1/traces"
        token = base64.b64encode(f"{public}:{secret}".encode()).decode()
        self.auth = f"Basic {token}"
        self.readback = os.environ.get("SHADOW_LANGFUSE_READBACK_URL", "").strip().rstrip("/")
        if self.readback:
            parsed = urllib.parse.urlparse(self.readback)
            if (
                parsed.scheme not in {"http", "https"}
                or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
            ):
                raise SystemExit("SHADOW_LANGFUSE_READBACK_URL must be an explicit loopback HTTP endpoint")
        self.project_id = os.environ.get("SHADOW_LANGFUSE_PROJECT_ID", "")
        self.readback_user = os.environ.get("SHADOW_LANGFUSE_READBACK_USER", "")
        self.readback_password = os.environ.get("SHADOW_LANGFUSE_READBACK_PASSWORD", "")

    def _readback_query(self, query: str) -> str:
        request = urllib.request.Request(self.readback, data=query.encode(), method="POST")
        if self.readback_user or self.readback_password:
            token = base64.b64encode(
                f"{self.readback_user}:{self.readback_password}".encode()
            ).decode()
            request.add_header("Authorization", f"Basic {token}")
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.read().decode().strip()

    def send_spans(self, spans: list[dict]) -> bool:
        payload = {
            "resourceSpans": [{
                "resource": {"attributes": [_attr("service.name", "shadow-observed-gauntlet")]},
                "scopeSpans": [{"scope": {"name": "shadow"}, "spans": spans}],
            }]
        }
        body = json.dumps(payload).encode()
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={"Content-Type": "application/json", "Authorization": self.auth},
        )
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=30):
                    return True
            except (urllib.error.URLError, OSError) as exc:
                if attempt == 2:
                    print(f"shadow-observed-gauntlet: trace delivery failed: {exc}", file=sys.stderr)
                    return False
                time.sleep(2 * (attempt + 1))

    def verify_trace(self, trace_id: str, *, attempts: int = 8, delay_s: float = 5.0) -> bool:
        """The doc contract: accepted HTTP without an exact trace-ID readback is red."""
        if self.readback and self.project_id:
            return self._verify_trace_clickhouse(trace_id, attempts=attempts, delay_s=delay_s)
        return self._verify_trace_web(trace_id, attempts=attempts, delay_s=delay_s)

    def _verify_trace_clickhouse(self, trace_id: str, *, attempts: int, delay_s: float) -> bool:
        """v4 readback: exact trace id must appear in default.events_core, the
        same path the routing gauntlet uses, so both gauntlets share one sink."""
        if not re.fullmatch(r"[0-9a-f]{32}", trace_id):
            return False
        query = (
            "SELECT count() FROM default.events_core "
            f"WHERE project_id = '{self.project_id}' AND trace_id = '{trace_id}' FORMAT TSV"
        )
        for attempt in range(attempts):
            try:
                if int(self._readback_query(query) or "0") >= 1:
                    return True
            except (ValueError, urllib.error.URLError, OSError):
                pass
            if attempt + 1 < attempts:
                time.sleep(delay_s)
        return False

    def _verify_trace_web(self, trace_id: str, *, attempts: int, delay_s: float) -> bool:
        request = urllib.request.Request(
            f"{self.host}/api/public/traces/{trace_id}",
            headers={"Authorization": self.auth},
        )
        for attempt in range(attempts):
            try:
                with urllib.request.urlopen(request, timeout=15) as response:
                    return response.status == 200
            except urllib.error.HTTPError as exc:
                if exc.code not in (404, 429, 500, 502, 503):
                    return False
            except (urllib.error.URLError, OSError):
                pass
            if attempt + 1 < attempts:
                time.sleep(delay_s)
        return False


def _now_ns() -> int:
    return time.time_ns()


def run_job(name: str, argv: list[str]) -> tuple[int, float, str]:
    started = time.monotonic()
    result = subprocess.run(
        [str(PYTHON), *argv],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    duration = time.monotonic() - started
    tail = _redact((result.stdout + result.stderr)[-600:])
    return result.returncode, duration, tail


def forward_events(sink: Sink, events_path: Path, trace_id: str, parent: str) -> int:
    """Ship allowlisted local events as spans; the emitter already redacted them."""
    try:
        lines = events_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0
    spans = []
    now = _now_ns()
    for line in lines[-200:]:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        spans.append({
            "traceId": trace_id,
            "spanId": secrets.token_hex(8),
            "parentSpanId": parent,
            "name": f"event:{event.get('verb', 'unknown')}",
            "kind": 1,
            "startTimeUnixNano": str(now),
            "endTimeUnixNano": str(now),
            "attributes": [_attr(f"shadow.{key}", value) for key, value in sorted(event.items())],
        })
    if spans:
        sink.send_spans(spans)
    return len(spans)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--jobs", default="", help="comma-separated subset of job names")
    args = parser.parse_args(argv)
    sink = Sink()

    chosen = [j.strip() for j in args.jobs.split(",") if j.strip()] or list(JOBS)
    unknown = [j for j in chosen if j not in JOBS]
    if unknown:
        print(f"unknown jobs: {', '.join(unknown)}; known: {', '.join(JOBS)}", file=sys.stderr)
        return 2

    events_env = os.environ.get("SHADOW_LANGFUSE_EVENTS", "")
    failures = 0
    delivery_failures = 0
    for round_number in range(1, args.rounds + 1):
        trace_id = secrets.token_hex(16)
        root_span = secrets.token_hex(8)
        round_start = _now_ns()
        job_spans: list[dict] = []
        for name in chosen:
            start = _now_ns()
            returncode, duration, tail = run_job(name, JOBS[name])
            end = _now_ns()
            passed = returncode == 0
            if not passed:
                failures += 1
            job_spans.append({
                "traceId": trace_id,
                "spanId": secrets.token_hex(8),
                "parentSpanId": root_span,
                "name": f"job:{name}",
                "kind": 1,
                "startTimeUnixNano": str(start),
                "endTimeUnixNano": str(end),
                "status": {"code": 1 if passed else 2},
                "attributes": [
                    _attr("shadow.job", name),
                    _attr("shadow.rc", returncode),
                    _attr("shadow.passed", passed),
                    _attr("shadow.duration_s", round(duration, 3)),
                    _attr("shadow.output_tail", tail),
                ],
            })
            print(f"[round {round_number}] {name}: {'pass' if passed else f'FAIL rc={returncode}'} in {duration:.1f}s")
        spans = [{
            "traceId": trace_id,
            "spanId": root_span,
            "name": f"gauntlet round {round_number}",
            "kind": 1,
            "startTimeUnixNano": str(round_start),
            "endTimeUnixNano": str(_now_ns()),
            "status": {"code": 2 if failures else 1},
            "attributes": [
                _attr("shadow.rounds", args.rounds),
                _attr("shadow.round", round_number),
                _attr("shadow.jobs", ",".join(chosen)),
                _attr("shadow.failures", failures),
            ],
        }, *job_spans]
        delivered = sink.send_spans(spans)
        if events_env:
            count = forward_events(sink, Path(events_env), trace_id, root_span)
            if count:
                print(f"[round {round_number}] forwarded {count} local event(s)")
        if not delivered:
            delivery_failures += 1
            print(f"[round {round_number}] RED: trace delivery failed; no readback possible", file=sys.stderr)
        elif not sink.verify_trace(trace_id):
            delivery_failures += 1
            print(f"[round {round_number}] RED: accepted but trace {trace_id} never read back", file=sys.stderr)
    return 1 if (failures or delivery_failures) else 0


if __name__ == "__main__":
    raise SystemExit(main())
