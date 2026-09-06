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
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent.parent
PYTHON = ROOT / "scripts" / "shadow-python.sh"
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import shadow_root_board as board

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
    "huddle-lifecycle": [],
}

HUDDLE_JOB = "huddle-lifecycle"
HUDDLE_STEPS = (
    "hold_observed",
    "bids_recorded",
    "settled",
    "held_write_refused",
    "compliance_satisfied",
)
HUDDLE_ATTRIBUTES = (
    "huddle_id",
    "huddle_generation",
    "lifecycle_step",
    "huddle_state",
    "opened_revision",
    "settled_revision",
    "compliance_revision",
)

HOME_PREFIX = str(Path.home())


def _redact(text: str) -> str:
    """The owner's home path never leaves the machine spelled out."""
    return text.replace(HOME_PREFIX, "~")


_FAILURE_HEADER = re.compile(r"^(?:FAIL|ERROR): ", re.MULTILINE)


def _failure_tail(output: str) -> str:
    """Bounded failure detail that names the FIRST failure, not only the last.

    A mass failure ends with the last test's summary; the causative one is
    first. When the output is long, keep the first failure header's block
    ahead of the usual closing tail so a log reader sees the cause.
    """
    if len(output) <= 600:
        return output
    header = _FAILURE_HEADER.search(output)
    closing = output[-600:]
    if header is None or header.start() >= len(output) - 600:
        return closing
    opening = output[max(0, header.start() - 80):header.start() + 400]
    return f"{opening}\n[...]\n{closing}"


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

    def verify_huddle_trace(self, trace_id: str, expected_rows: list[dict], *, attempts: int = 8,
                            delay_s: float = 5.0) -> bool:
        """Require all five owner-local Huddle projections, exactly once each."""
        if (not self.readback or not re.fullmatch(r"[A-Za-z0-9_-]{3,128}", self.project_id)
                or not re.fullmatch(r"[0-9a-f]{32}", trace_id)
                or not _valid_huddle_rows(expected_rows)):
            return False
        columns = ",\n  ".join(
            "toUInt64OrNull(" + f"metadata_values[indexOf(metadata_names, 'attributes.shadow.{key}')]" + ") "
            f"AS {key}" if key in {"huddle_generation", "opened_revision", "settled_revision", "compliance_revision"}
            else f"metadata_values[indexOf(metadata_names, 'attributes.shadow.{key}')] AS {key}"
            for key in HUDDLE_ATTRIBUTES
        )
        query = (
            f"SELECT\n  {columns}\nFROM default.events_core "
            f"WHERE project_id = '{self.project_id}' AND trace_id = '{trace_id}' "
            "AND name = 'huddle.lifecycle' ORDER BY lifecycle_step "
            "SETTINGS output_format_json_quote_64bit_integers = 0 FORMAT JSONEachRow"
        )
        expected = sorted(expected_rows, key=_huddle_row_key)
        for attempt in range(attempts):
            try:
                raw = self._readback_query(query)
                rows = [json.loads(line) for line in raw.splitlines() if line]
                if all(isinstance(row, dict) and set(row) == set(HUDDLE_ATTRIBUTES) for row in rows):
                    normalized = [_normalize_huddle_row(row) for row in rows]
                    if all(row is not None for row in normalized) and sorted(normalized, key=_huddle_row_key) == expected:
                        return True
            except (json.JSONDecodeError, TypeError, urllib.error.URLError, OSError):
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


def _loopback_http_endpoint(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    return (parsed.scheme in {"http", "https"} and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            and parsed.username is None and parsed.password is None and not parsed.query and not parsed.fragment)


def _huddle_row_key(row: dict) -> tuple:
    return tuple(row[key] for key in HUDDLE_ATTRIBUTES)


def _normalize_huddle_row(row: dict) -> dict | None:
    if not isinstance(row, dict) or set(row) != set(HUDDLE_ATTRIBUTES):
        return None
    if not isinstance(row.get("huddle_id"), str) or not re.fullmatch(r"hdl_[0-9a-f]{8}", row["huddle_id"]):
        return None
    if row.get("lifecycle_step") not in HUDDLE_STEPS or row.get("huddle_state") not in {
        "open_round_1", "awaiting_compliance", "resolved"
    }:
        return None
    numeric = ("huddle_generation", "opened_revision", "settled_revision", "compliance_revision")
    if any(type(row.get(key)) is not int or row[key] < 0 for key in numeric):
        return None
    return {key: row[key] for key in HUDDLE_ATTRIBUTES}


def _valid_huddle_rows(rows: object) -> bool:
    if not isinstance(rows, list) or len(rows) != len(HUDDLE_STEPS):
        return False
    normalized = [_normalize_huddle_row(row) for row in rows]
    if any(row is None for row in normalized):
        return False
    if [row["lifecycle_step"] for row in rows] != list(HUDDLE_STEPS) or len({row["huddle_id"] for row in rows}) != 1:
        return False
    if [row["huddle_generation"] for row in rows] != [1, 1, 2, 2, 3]:
        return False
    if [row["huddle_state"] for row in rows] != [
        "open_round_1", "open_round_1", "awaiting_compliance", "awaiting_compliance", "resolved"
    ]:
        return False
    opened = rows[0]["opened_revision"]
    settled = rows[2]["settled_revision"]
    compliance = rows[4]["compliance_revision"]
    return (opened > 0 and all(row["opened_revision"] == opened for row in rows)
            and [row["settled_revision"] for row in rows] == [0, 0, settled, settled, settled]
            and settled > opened and [row["compliance_revision"] for row in rows] == [0, 0, 0, 0, compliance]
            and compliance > settled)


def _huddle_plan(title: str, row: str) -> str:
    return (
        f"# {title}\n\n## Brief\n\n- Project: huddle-observed\n- Mode: ship\n\n"
        f"## Tasks\n\n- [pending] {title} {row} | proof: cmd true\n\n## Progress\n"
    )


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _journal_head(home: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(home / ".shadow"), "rev-parse", "HEAD"], check=True,
        capture_output=True, text=True,
    ).stdout.strip()


def _huddle_span(trace_id: str, row: dict, start_ns: int) -> dict:
    return {
        "traceId": trace_id,
        "spanId": secrets.token_hex(8),
        "name": "huddle.lifecycle",
        "kind": 1,
        "status": {"code": 2},
        "startTimeUnixNano": str(start_ns),
        "endTimeUnixNano": str(start_ns + 1),
        "attributes": [_attr(f"shadow.{key}", row[key]) for key in HUDDLE_ATTRIBUTES],
    }


def _claim_ref(claim: dict) -> dict:
    """Copy the exact public claim identity required by the Huddle API."""
    return {key: claim[key] for key in ("entity", "row", "owner", "claimed_at", "claim_revision")}


def huddle_lifecycle_rows() -> list[dict]:
    """Exercise the public board lifecycle in a disposable Git repository."""
    with tempfile.TemporaryDirectory(prefix="shadow-huddle-observed-") as temporary:
        root = Path(temporary)
        home, repo = root / "home", root / "repo"
        home.mkdir()
        repo.mkdir()
        _git(repo, "init", "-q")
        _git(repo, "config", "user.email", "huddle@example.invalid")
        _git(repo, "config", "user.name", "Huddle observed")
        plan_a, plan_b = repo / "a" / "PLAN.md", repo / "b" / "PLAN.md"
        plan_a.parent.mkdir()
        plan_b.parent.mkdir()
        plan_a.write_text(_huddle_plan("Owner A", "~aa11"), encoding="utf-8")
        plan_b.write_text(_huddle_plan("Owner B", "~bb22"), encoding="utf-8")
        (repo / "shared").write_text("tracked shared scope\n", encoding="utf-8")
        _git(repo, "add", "a/PLAN.md", "b/PLAN.md", "shared")
        _git(repo, "commit", "-qm", "huddle fixture")

        board.ensure(home=home)
        board.reconcile([
            {"plan": str(plan_a), "project": "huddle-observed", "priority": 1, "candidates": ["~aa11"]},
            {"plan": str(plan_b), "project": "huddle-observed", "priority": 1, "candidates": ["~bb22"]},
        ], [], home=home)
        first = board.claim(plan_a, "~aa11", "huddle-a", project="huddle-observed", priority=1,
                            repo=repo, access="write", write_scope=["shared"], home=home)
        second = board.claim(plan_b, "~bb22", "huddle-b", project="huddle-observed", priority=1,
                             repo=repo, access="write", write_scope=["shared"], home=home)
        opened = board.snapshot(home=home)
        huddle = opened["huddles"][0]
        if (len(huddle["claims"]) != 2 or len(huddle["holds"]) != 1
                or huddle["state"] != "open_round_1" or huddle["generation"] != 1):
            raise RuntimeError("Huddle did not open with one real held claim")
        held_ref = huddle["holds"][0]
        claims = {(claim["entity"], claim["row"]): claim for claim in opened["claims"]}
        held = claims[(held_ref["entity"], held_ref["row"])]
        selected = next(claim for claim in opened["claims"] if _claim_ref(claim) != held_ref)
        opened_revision = huddle["opened_revision"]
        rows = [dict(huddle_id=huddle["id"], huddle_generation=1, lifecycle_step="hold_observed",
                     huddle_state="open_round_1", opened_revision=opened_revision,
                     settled_revision=0, compliance_revision=0)]

        for claim, role, reason in ((selected, "own", "existing_claim"), (held, "stand_down", "duplicate_intent")):
            board.submit_huddle_bid(
                huddle_id=huddle["id"], seat=claim["owner"], claim=_claim_ref(claim), role=role,
                scope=claim["write_scope"], reason=reason, target=None, support_claim=None,
                evidence={"kind": "claim", "value": "self"}, round=1,
                expected_huddle_generation=1, now=datetime.now(timezone.utc), home=home,
            )
        after_bids = board.snapshot(home=home)
        bid_huddle = after_bids["huddles"][0]
        for claim in (selected, held):
            receipt = board.bid_receipt(huddle["id"], _claim_ref(claim), 1, home=home)
            if receipt["claim"] != _claim_ref(claim) or receipt["scope"] != claim["write_scope"]:
                raise RuntimeError("Huddle bid receipt changed")
        if (bid_huddle["id"] != huddle["id"] or bid_huddle["opened_revision"] != opened_revision
                or after_bids["claims"] != opened["claims"] or bid_huddle["holds"] != huddle["holds"]
                or bid_huddle["generation"] != 1):
            raise RuntimeError("Huddle bid changed claims, holds, or generation")
        rows.append(dict(huddle_id=huddle["id"], huddle_generation=1, lifecycle_step="bids_recorded",
                         huddle_state="open_round_1", opened_revision=opened_revision,
                         settled_revision=0, compliance_revision=0))

        settled = board.settle_huddle(
            huddle_id=huddle["id"], actor_claim=_claim_ref(selected), expected_generation=1,
            expected_board_revision=after_bids["revision"], now=datetime.now(timezone.utc), home=home,
        ).payload
        settled_huddle = settled["huddles"][0]
        settled_revision = settled["revision"]
        if (settled_huddle["id"] != huddle["id"] or settled_huddle["opened_revision"] != opened_revision
                or settled_huddle["state"] != "awaiting_compliance" or settled_huddle["generation"] != 2
                or settled_huddle["resolution"]["write_owners"] != [_claim_ref(selected)]
                or settled_huddle["resolution"]["settled_revision"] != settled_revision
                or settled_huddle["holds"] != [held_ref]):
            raise RuntimeError("Huddle settlement was not the expected held-owner resolution")
        rows.append(dict(huddle_id=huddle["id"], huddle_generation=2, lifecycle_step="settled",
                         huddle_state="awaiting_compliance", opened_revision=opened_revision,
                         settled_revision=settled_revision, compliance_revision=0))

        before_refusal = ((home / ".shadow" / board.BOARD_NAME).read_bytes(), plan_a.read_bytes(),
                          plan_b.read_bytes(), _journal_head(home))
        held_context = {key: held[key] for key in ("entity", "row", "owner", "claim_revision")}
        held_context["board_revision"] = settled_revision
        try:
            board.authorize_host_attempt(context=held_context, repo=repo, write_scope=["shared"],
                                         authority_proposal=False, now=datetime.now(timezone.utc), home=home)
        except board.BoardError as exc:
            if "held" not in str(exc):
                raise
        else:
            raise RuntimeError("Huddle held public write was authorized")
        if before_refusal != ((home / ".shadow" / board.BOARD_NAME).read_bytes(), plan_a.read_bytes(),
                              plan_b.read_bytes(), _journal_head(home)):
            raise RuntimeError("held Huddle write refusal changed durable state")
        rows.append(dict(huddle_id=huddle["id"], huddle_generation=2, lifecycle_step="held_write_refused",
                         huddle_state="awaiting_compliance", opened_revision=opened_revision,
                         settled_revision=settled_revision, compliance_revision=0))

        plans = {entity["id"]: Path(entity["plan"]) for entity in opened["entities"]}
        held_plan, selected_plan = plans[held["entity"]], plans[selected["entity"]]
        held_text = held_plan.read_text(encoding="utf-8").replace("[pending]", "[blocked]", 1)
        held_plan.write_text(held_text + f"\n## Deferred\n\n- {held['row']} | wake: owner disposition is needed\n", encoding="utf-8")
        released, changed = board.release(held_plan, held["row"], owner=held["owner"], reason="blocked",
                                          expected_claim=held, now=datetime.now(timezone.utc), home=home)
        resolved = released["huddles"][0]
        compliance = resolved["compliance"][0]
        compliance_revision = released["revision"]
        if (not changed or resolved["id"] != huddle["id"] or resolved["opened_revision"] != opened_revision
                or resolved["state"] != "resolved" or resolved["generation"] != 3
                or resolved["holds"] or compliance["status"] != "satisfied"
                or compliance["completion"]["kind"] != "return"
                or compliance["completion"]["board_revision"] != compliance_revision):
            raise RuntimeError("Huddle compliance return did not resolve exactly")
        board.release(selected_plan, selected["row"], owner=selected["owner"], reason="handback", expected_claim=selected,
                      now=datetime.now(timezone.utc), home=home)
        if board.snapshot(home=home)["claims"]:
            raise RuntimeError("Huddle cleanup left a live disposable claim")
        rows.append(dict(huddle_id=huddle["id"], huddle_generation=3, lifecycle_step="compliance_satisfied",
                         huddle_state="resolved", opened_revision=opened_revision,
                         settled_revision=settled_revision, compliance_revision=compliance_revision))
        if not _valid_huddle_rows(rows):
            raise RuntimeError("Huddle lifecycle evidence was incomplete")
        return rows


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
    tail = _redact(_failure_tail(result.stdout + result.stderr))
    return result.returncode, duration, tail


def _event_start_ns(event: dict, fallback: int) -> int:
    """The event's own moment, or the read instant when its clock is unusable."""
    recorded = event.get("recorded_at")
    if isinstance(recorded, str):
        try:
            # Python 3.10 accepts only three or six fractional digits.
            # Normalize valid microsecond precision; retain malformed-clock fallback.
            normalized = re.sub(
                r"(\.\d{1,6})(?=[+-]\d{2}:\d{2}$)",
                lambda match: match.group(1).ljust(7, "0"),
                recorded.replace("Z", "+00:00"),
            )
            parsed = datetime.fromisoformat(normalized)
            return int(parsed.timestamp() * 1_000_000_000)
        except ValueError:
            pass
    return fallback


def forward_events(sink: Sink, events_path: Path, trace_id: str, parent: str) -> tuple[int, bool]:
    """Ship allowlisted local events as spans; the emitter already redacted them.

    Spans carry the event's own recorded_at and duration_ms — stamping every
    event with the upload instant collapses the timeline the trace exists to
    show. Returns (spans sent, delivered): a failed event delivery is the
    caller's red to raise, never a silent skip.
    """
    try:
        lines = events_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print(f"shadow-observed-gauntlet: cannot read events file {events_path}: {exc}", file=sys.stderr)
        return 0, False
    spans = []
    now = _now_ns()
    for line in lines[-200:]:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        start = _event_start_ns(event, now)
        duration = event.get("duration_ms")
        if isinstance(duration, bool) or not isinstance(duration, int) or duration < 0:
            duration = 0
        spans.append({
            "traceId": trace_id,
            "spanId": secrets.token_hex(8),
            "parentSpanId": parent,
            "name": f"event:{event.get('verb', 'unknown')}",
            "kind": 1,
            "startTimeUnixNano": str(start),
            "endTimeUnixNano": str(start + duration * 1_000_000),
            "attributes": [_attr(f"shadow.{key}", value) for key, value in sorted(event.items())],
        })
    if not spans:
        return 0, True
    return len(spans), sink.send_spans(spans)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--jobs", default="", help="comma-separated subset of job names")
    args = parser.parse_args(argv)
    sink = Sink()

    # Huddle is an explicit owner opt-in: existing generic/default calls stay v3-compatible.
    chosen = [j.strip() for j in args.jobs.split(",") if j.strip()] or [
        name for name in JOBS if name != HUDDLE_JOB
    ]
    unknown = [j for j in chosen if j not in JOBS]
    if unknown:
        print(f"unknown jobs: {', '.join(unknown)}; known: {', '.join(JOBS)}", file=sys.stderr)
        return 2

    events_env = os.environ.get("SHADOW_LANGFUSE_EVENTS", "")
    if HUDDLE_JOB in chosen:
        if len(chosen) != 1:
            print("huddle-lifecycle cannot be mixed with generic jobs", file=sys.stderr)
            return 2
        if args.rounds < 1:
            print("huddle-lifecycle requires at least one round", file=sys.stderr)
            return 2
        if events_env:
            print("huddle-lifecycle refuses SHADOW_LANGFUSE_EVENTS; generic event forwarding is not Huddle evidence",
                  file=sys.stderr)
            return 2
        if not (sink.readback and sink.project_id):
            print("huddle-lifecycle requires explicit loopback ClickHouse readback and project ID", file=sys.stderr)
            return 2
        if not _loopback_http_endpoint(sink.host):
            print("huddle-lifecycle requires an explicit loopback OTLP HTTP endpoint", file=sys.stderr)
            return 2
        if not re.fullmatch(r"[A-Za-z0-9_-]{3,128}", sink.project_id):
            print("huddle-lifecycle requires a safely shaped project ID", file=sys.stderr)
            return 2
        failures = 0
        for round_number in range(1, args.rounds + 1):
            trace_id = secrets.token_hex(16)
            try:
                rows = huddle_lifecycle_rows()
            except (board.BoardError, OSError, subprocess.SubprocessError, RuntimeError) as exc:
                print(f"[round {round_number}] huddle-lifecycle: RED: {exc}", file=sys.stderr)
                failures += 1
                continue
            start = _now_ns()
            spans = [_huddle_span(trace_id, row, start + index * 2) for index, row in enumerate(rows)]
            if not sink.send_spans(spans):
                print(f"[round {round_number}] RED: Huddle trace delivery failed; no readback possible", file=sys.stderr)
                failures += 1
            elif not sink.verify_huddle_trace(trace_id, rows):
                print(f"[round {round_number}] RED: Huddle trace {trace_id} did not exactly read back", file=sys.stderr)
                failures += 1
            else:
                print(f"[round {round_number}] huddle-lifecycle: pass")
        return 1 if failures else 0
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
            if not passed and tail:
                # The tail's only other copy is a span attribute: when trace
                # delivery fails (or the trace host is down), that copy is
                # gone. Keep the redacted failure detail in the local log too.
                print(tail)
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
            count, events_delivered = forward_events(sink, Path(events_env), trace_id, root_span)
            if count:
                print(f"[round {round_number}] forwarded {count} local event(s)")
            if not events_delivered:
                # The specific line (read failure, or send_spans' own delivery
                # failure) already went to stderr; the round just turns red.
                delivery_failures += 1
        if not delivered:
            delivery_failures += 1
            print(f"[round {round_number}] RED: trace delivery failed; no readback possible", file=sys.stderr)
        elif not sink.verify_trace(trace_id):
            delivery_failures += 1
            print(f"[round {round_number}] RED: accepted but trace {trace_id} never read back", file=sys.stderr)
    return 1 if (failures or delivery_failures) else 0


if __name__ == "__main__":
    raise SystemExit(main())
