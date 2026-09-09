"""Controller observations in the existing opt-in local telemetry stream.

The controller and its evidence directory share the board's cooperative local
trust boundary. This is not a provider identity or hostile-same-user sandbox.
Only the launched CLI's top-level transport may supply native usage.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
from datetime import datetime, timezone
import uuid

import shadow_telemetry as telemetry
from shadow_execution_policy import HOSTS, WORK_CLASSES

SCHEMA = 'shadow.host-observation.v1'
LOG_PATH = '.shadow/evidence/' + telemetry.EVENT_FILE
MAX_LOG_BYTES = 4 * 1024 * 1024
MAX_RECORDS = 4096
COMMON = ('schema', 'recorded_at', 'event', 'run_id', 'entity', 'row',
          'claim_revision', 'owner_sha256', 'worktree_sha256', 'task_sha256',
          'host', 'work_class')
TERMINAL = ('receipt_sha256', 'receipt_path_sha256', 'status', 'duration_ms')
CLASSES = set(WORK_CLASSES)


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate field')
        result[key] = value
    return result


def integer(value):
    return type(value) is int and 0 <= value <= 10**12


def validate(candidate):
    keys = COMMON + (TERMINAL if candidate.get('event') == 'host_finish' else ())
    if set(candidate) != set(keys) or candidate.get('schema') != SCHEMA:
        raise telemetry.TelemetryError('invalid host observation shape')
    if candidate.get('event') not in {'host_start', 'host_finish'}:
        raise telemetry.TelemetryError('invalid host observation phase')
    for key in ('run_id', 'entity', 'owner_sha256', 'worktree_sha256', 'task_sha256'):
        if not isinstance(candidate[key], str) or not telemetry.ID_RE.fullmatch(candidate[key]):
            raise telemetry.TelemetryError('invalid host observation identity')
    if (not isinstance(candidate['row'], str) or not telemetry.ROW_RE.fullmatch(candidate['row'])
            or not integer(candidate['claim_revision']) or candidate['claim_revision'] == 0
            or candidate['host'] not in HOSTS or candidate['work_class'] not in CLASSES
            or not isinstance(candidate['recorded_at'], str)
            or not telemetry.UTC_RE.fullmatch(candidate['recorded_at'])):
        raise telemetry.TelemetryError('invalid host observation vocabulary')
    if candidate['event'] == 'host_finish':
        if (any(not isinstance(candidate[k], str) or not telemetry.ID_RE.fullmatch(candidate[k])
                for k in ('receipt_sha256', 'receipt_path_sha256'))
                or candidate['status'] not in {'ok', 'blocked', 'failed'}
                or not integer(candidate['duration_ms'])):
            raise telemetry.TelemetryError('invalid host observation terminal')
    return dict(candidate)


def start(repo, claim, task_sha256, host, work_class):
    event = dict(schema=SCHEMA, recorded_at=stamp(), event='host_start',
                 run_id=sha(uuid.uuid4().bytes), entity=claim['entity'], row=claim['row'],
                 claim_revision=claim['claim_revision'], owner_sha256=sha(claim['owner']),
                 worktree_sha256=sha(str(repo.resolve())), task_sha256=task_sha256,
                 host=host, work_class=work_class)
    telemetry.append_record(repo, validate(event), max_bytes=2048)
    return event


def finish(repo, event, destination, payload):
    terminal = dict(event, recorded_at=stamp(), event='host_finish',
                    receipt_sha256=sha(destination.read_bytes()),
                    receipt_path_sha256=sha(destination.relative_to(repo).as_posix()),
                    status=payload['status'], duration_ms=round(payload['duration_s'] * 1000))
    telemetry.append_record(repo, validate(terminal), max_bytes=2048)


def stamp():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def unknown_usage(reason='transport_unavailable'):
    return dict(state='unknown', reason=reason, scope='unknown', input_tokens=None,
                cached_input_tokens=None, cache_creation_input_tokens=None,
                output_tokens=None, reasoning_output_tokens=None,
                native_cost_usd=None, cost_basis='unknown', observed_models=None,
                provider_identity=None)


class UsageStream:
    """Discard payloads while reading bounded, complete native JSONL records."""
    MAX_LINE = 1024 * 1024
    MAX_BYTES = 32 * 1024 * 1024
    MAX_RECORDS = 10000
    MAX_RETAINED = 64 * 1024

    def __init__(self):
        self.pending = bytearray()
        self.records = []
        self.count = self.total = self.retained = 0
        self.invalid = self.closed = False

    def refuse(self):
        self.invalid = True
        self.pending.clear()
        self.records.clear()

    def feed(self, chunk):
        if self.invalid or self.closed:
            return
        self.total += len(chunk)
        if self.total > self.MAX_BYTES:
            self.refuse(); return
        self.pending.extend(chunk)
        while (end := self.pending.find(b'\n')) >= 0:
            if end > self.MAX_LINE:
                self.refuse(); return
            line = bytes(self.pending[:end])
            del self.pending[:end + 1]
            self.record(line)
            if self.invalid:
                return
        if len(self.pending) > self.MAX_LINE:
            self.refuse()

    def record(self, line):
        if not line.strip():
            return
        self.count += 1
        try:
            if self.count > self.MAX_RECORDS:
                raise ValueError('too many records')
            value = json.loads(line.decode('utf-8'), object_pairs_hook=unique_object)
            if not isinstance(value, dict):
                raise ValueError('non-object record')
            kind = value.get('type')
            if kind in ('thread.started', 'turn.started', 'turn.failed', 'error'):
                selected = {'type': kind}
            elif kind == 'turn.completed':
                usage = value.get('usage')
                if isinstance(usage, dict):
                    usage = {k: usage[k] if integer(usage[k]) else None for k in ('input_tokens', 'cached_input_tokens',
                        'output_tokens', 'reasoning_output_tokens') if k in usage}
                else:
                    usage = None
                selected = {'type': kind, 'usage': usage}
            elif kind == 'result':
                models = value.get('modelUsage')
                if (isinstance(models, dict) and 1 <= len(models) <= 16
                        and all(isinstance(k, str) and re.fullmatch(r'claude-[a-z0-9.-]{1,64}', k)
                                and isinstance(v, dict) for k, v in models.items())):
                    models = {model: {k: counters.get(k) if integer(counters.get(k)) else None
                        for k in ('inputTokens', 'outputTokens', 'cacheReadInputTokens',
                                  'cacheCreationInputTokens')} for model, counters in models.items()}
                else:
                    models = None
                cost = value.get('total_cost_usd')
                cost = cost if type(cost) in (int, float) and 0 <= cost <= 10**6 and math.isfinite(cost) else None
                selected = dict(type=kind, subtype='success' if value.get('subtype') == 'success' else None,
                    is_error=value.get('is_error') if type(value.get('is_error')) is bool else None,
                    total_cost_usd=cost, modelUsage=models)
            else:
                return
            encoded = json.dumps(selected, separators=(',', ':')).encode() + b'\n'
            self.retained += len(encoded)
            if self.retained > self.MAX_RETAINED:
                raise ValueError('usage metadata exceeds bound')
            self.records.append(encoded)
        except (ValueError, UnicodeError, RecursionError):
            self.refuse()

    def finish(self):
        if not self.invalid and self.pending:
            self.record(bytes(self.pending))
        self.pending.clear()
        self.closed = True

    def snapshot(self):
        complete = self.closed and not self.invalid
        return (b''.join(self.records) if complete else b''), complete


def native_usage(host, process):
    """No recursive traversal, text extraction, requested model or price lookup."""
    unknown = unknown_usage()
    raw = process.get('stdout', b'')
    streamed = 'usage_transport' in process
    if streamed:
        raw = process['usage_transport']
    if (process.get('timed_out') or process.get('launch_error')
            or process.get('returncode') != 0
            or (not process.get('usage_transport_complete') if streamed
                else process.get('stdout_bytes', len(raw)) != len(raw))):
        return unknown_usage('incomplete_process_or_capture')
    try:
        records = [json.loads(line, object_pairs_hook=unique_object)
                   for line in raw.decode('utf-8').splitlines() if line.strip()]
        if not records or any(not isinstance(x, dict) for x in records):
            return unknown
        if host in {'codex', 'codex-zai'}:
            types = [x.get('type') for x in records]
            if (types.count('thread.started') != 1 or types.count('turn.started') != 1
                    or types.count('turn.completed') != 1
                    or 'turn.failed' in types or 'error' in types
                    or not types.index('thread.started') < types.index('turn.started') < types.index('turn.completed')):
                return unknown
            usage = records[types.index('turn.completed')].get('usage')
            if not isinstance(usage, dict):
                return unknown
            mapping = {'input_tokens': 'input_tokens', 'cached_input_tokens': 'cached_input_tokens',
                       'output_tokens': 'output_tokens', 'reasoning_output_tokens': 'reasoning_output_tokens'}
            if any(not integer(usage.get(k)) for k in ('input_tokens', 'output_tokens')):
                return unknown
            if any(k in usage and not integer(usage[k]) for k in mapping):
                return unknown
            if usage.get('cached_input_tokens', 0) > usage['input_tokens']:
                return unknown
            return dict(unknown, state='known', reason=None, scope='native_parent_turn',
                        **{out: usage.get(key) for out, key in mapping.items()})
        if host == 'claude-code':
            results = [x for x in records if x.get('type') == 'result']
            if len(results) != 1 or results[0].get('subtype') != 'success' or results[0].get('is_error') is not False:
                return unknown
            result = results[0]
            models = result.get('modelUsage')
            if not isinstance(models, dict) or not 1 <= len(models) <= 16:
                return unknown
            totals = dict(input_tokens=0, output_tokens=0, cached_input_tokens=0, cache_creation_input_tokens=0)
            mapping = dict(input_tokens='inputTokens', output_tokens='outputTokens',
                           cached_input_tokens='cacheReadInputTokens', cache_creation_input_tokens='cacheCreationInputTokens')
            for model, usage in models.items():
                if not re.fullmatch(r'claude-[a-z0-9.-]{1,64}', model) or not isinstance(usage, dict):
                    return unknown
                for output, key in mapping.items():
                    if not integer(usage.get(key)):
                        return unknown
                    totals[output] += usage[key]
            cost = result.get('total_cost_usd')
            if type(cost) not in (int, float) or not 0 <= cost <= 10**6 or not math.isfinite(cost):
                return unknown
            return dict(unknown, state='known', reason=None, scope='native_whole_tree', **totals,
                        native_cost_usd=cost, cost_basis='native_reported_estimate', observed_models=sorted(models))
    except (ValueError, UnicodeError, TypeError):
        pass
    return unknown


def read_log(repo):
    """Read only the selected repository's existing stream; retain partial tails."""
    path = repo / LOG_PATH
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError('observation stream unavailable')
    with path.open('rb') as stream:
        raw = stream.read(MAX_LOG_BYTES + 1)
    if len(raw) > MAX_LOG_BYTES or len(raw.splitlines()) > MAX_RECORDS:
        raise ValueError('observation stream exceeds bound')
    events, errors = [], 0
    for line in raw.splitlines(keepends=True):
        try:
            if not line.endswith(b'\n') or len(line) > 2048:
                raise ValueError('partial record')
            value = json.loads(line, object_pairs_hook=unique_object)
            if not isinstance(value, dict):
                raise ValueError('not object')
            if value.get('schema') == telemetry.SCHEMA:
                if telemetry._validated_record(value) != value:
                    raise ValueError('invalid legacy event')
                continue
            events.append(validate(value))
        except (ValueError, telemetry.TelemetryError, TypeError, KeyError):
            errors += 1
    return events, errors, sha(raw)
