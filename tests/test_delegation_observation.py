"""Exercise native admission, real Git, current acceptance and false joins.

Only the paid CLI is substituted. No acceptance/credit function is mocked in
this lifecycle. The proof command is frozen before the worker can edit source.
"""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.test_shadow_host import make_repo, run_host, shadow_host, board_api
from tests.test_efficiency_acceptance import reader
from tests.test_shadow_accept import local_authority_plan
from tests.proc_fixture import git
import shadow_host_observation as observation
import shadow_plan_store as plan_store
import shadow_telemetry as telemetry

CANARY = 'PRIVATE_PROMPT_CANARY'
FAKE = r'''#!/usr/bin/env python3
import json, pathlib, subprocess, sys
if '--version' in sys.argv:
    print('fixture'); raise SystemExit()
sys.stdin.read()
repo = pathlib.Path.cwd()
mode = pathlib.Path(__file__).with_suffix('.mode').read_text()
if mode == 'fail':
    raise SystemExit(1)
if mode in {'tamper', 'tamper-valid'}:
    with (repo / '.shadow/evidence/shadow-events.jsonl').open('a') as f:
        if mode == 'tamper':
            f.write('{}\n')
        else:
            source = json.loads((repo / '.shadow/evidence/shadow-events.jsonl').read_text().splitlines()[0])
            f.write(json.dumps(dict(schema='shadow.telemetry.event.v1', recorded_at=source['recorded_at'], project='observation', entity=source['entity'], row=source['row'], verb='throw', duration_ms=0, outcome='claimed')) + '\n')
repo.joinpath('result.txt').write_text('useful\n' if mode == 'ok' else 'useful ' + mode + '\n')
subprocess.run(['git','add','result.txt'], check=True, capture_output=True)
subprocess.run(['git','commit','-qm','useful bounded work'], check=True, capture_output=True)
receipt = dict(schema='shadow.host-receipt.v1', task_id='add-proof', status='ok',
               summary='bounded result', proof_ref='check-passed', changed_paths=['result.txt'],
               tests=[dict(name='check',status='pass')])
if '--output-last-message' in sys.argv:
    pathlib.Path(sys.argv[sys.argv.index('--output-last-message') + 1]).write_text(json.dumps(receipt))
else:
    print(json.dumps(receipt))
if mode == 'claude-zero':
    print(json.dumps(dict(type='result', subtype='success', is_error=False, total_cost_usd=0.01,
        modelUsage={'claude-sonnet-4-6': dict(inputTokens=2, outputTokens=3,
            cacheReadInputTokens=0, cacheCreationInputTokens=4)})))
    raise SystemExit()
usage = dict(input_tokens=100, cached_input_tokens=20, output_tokens=30)
if mode == 'usage-partial':
    usage.update(input_tokens=5, cached_input_tokens=0, cache_creation_input_tokens=7,
                 output_tokens=6, reasoning_output_tokens=8)
for event in [dict(type='thread.started',thread_id='PRIVATE_SESSION_CANARY'),
              dict(type='turn.started'),
              dict(type='item.completed',item=dict(type='agent_message',text=json.dumps(receipt))),
              dict(type='turn.completed',usage=usage)]:
    print(json.dumps(event))
'''


class DelegationLifecycle(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name).resolve()
        self.repo = make_repo(self.home)
        git(self.repo, 'remote', 'add', 'origin', 'git@github.com:example/observation.git')
        (self.repo / 'check.py').write_text("from pathlib import Path\nassert Path('result.txt').read_text() == 'useful\\n'\n")
        git(self.repo, 'add', 'check.py')
        git(self.repo, 'commit', '-qm', 'independent acceptance')
        self.plan = self.home / '.shadow/plans/observation/PLAN.md'
        self.plan.parent.mkdir(parents=True)
        text = local_authority_plan('Observation', 'observation', 'M1 - Useful work',
            'Do useful work', '~aa11', '~aa12', origins=('github.com/example/observation',))
        text = text.replace('~aa11 | proof: cmd true', '~aa11 | proof: cmd python3 check.py')
        self.plan.write_text(text)
        board_api.reconcile([dict(plan=str(self.plan), project='observation', priority=1, candidates=['~aa11'])], [], home=self.home)
        state = board_api.claim(self.plan, '~aa11', 'fixture-worker', project='observation', priority=1,
             repo=self.repo, access='write', write_scope=['result.txt'], home=self.home)
        self.claim = board_api.snapshot(home=self.home)['claims'][0]
        self.binary = self.home / 'fake-cli'
        self.binary.write_text(FAKE)
        self.binary.chmod(0o755)
        self.binary.with_suffix('.mode').write_text('ok')
        self.task = self.home / 'task.txt'
        self.task.write_text('Produce the useful result. ' + CANARY)
        self.environment = patch.dict(os.environ, {'HOME': str(self.home), 'SHADOW_TELEMETRY': 'local'})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def invoke(self, name='attempt.json', *, host='codex'):
        context = {k: self.claim[k] for k in ('entity','row','owner','claim_revision')}
        context['board_revision'] = board_api.snapshot()['revision']
        self.output = self.repo / '.shadow/evidence' / name
        return run_host(self.repo, self.binary, self.task, self.output, host=host,
                        extra=('--claim-context', json.dumps(context)))

    def report(self):
        return reader.audit_observed([self.repo])

    def accept(self):
        with contextlib.redirect_stdout(io.StringIO()):
            code, released = reader.accept.accept_local_plan(self.repo, self.plan, '~aa11', 'fixture-worker', 30)
        self.assertEqual(code, 0)
        self.assertTrue(released)

    def test_launch_retry_accept_reopen_and_resource_denominators(self):
        self.binary.with_suffix('.mode').write_text('fail')
        failed = self.invoke('failed.json')
        self.assertNotEqual(failed.returncode, 0)
        self.binary.with_suffix('.mode').write_text('ok')
        passed = self.invoke()
        self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
        payload = json.loads(self.output.read_text())
        self.assertTrue(payload['execution_binding']['execution_candidate'])
        pending = self.report()
        self.assertEqual(pending['accepted_worker_tasks'], 0)
        self.accept()
        report = self.report()
        self.assertEqual(report['accepted_worker_tasks'], 1)
        self.assertEqual(report['known_roots'], 1)
        self.assertEqual(report['observed_attempts'], 2)
        self.assertEqual(report['failed_attempts'], 1)
        known = [x for x in report['resource_totals'] if x['known_usage_attempts']]
        self.assertEqual((known[0]['input_tokens'], known[0]['output_tokens']), (100, 30))
        self.assertIsNone(report['cost_per_accepted_task'])
        self.assertIsNone(report['attention_per_accepted_task'])
        for secret in (CANARY, 'PRIVATE_SESSION_CANARY', str(self.home), 'fixture-worker'):
            self.assertNotIn(secret, json.dumps(report))
            self.assertNotIn(secret, (self.repo / observation.LOG_PATH).read_text())
        transaction = plan_store.PlanTransaction.begin(self.plan)
        transaction.replace_content(transaction.original_content.replace(b'[completed]', b'[pending]', 1)).publish()
        self.assertEqual(self.report()['accepted_worker_tasks'], 0)

    def test_optional_token_coverage_zero_and_scope_groups(self):
        self.binary.with_suffix('.mode').write_text('fail')
        self.assertNotEqual(self.invoke('failed.json').returncode, 0)
        self.binary.with_suffix('.mode').write_text('ok')
        self.assertEqual(self.invoke('cached-only.json').returncode, 0)
        self.binary.with_suffix('.mode').write_text('usage-partial')
        self.assertEqual(self.invoke('mixed.json').returncode, 0)
        self.binary.with_suffix('.mode').write_text('claude-zero')
        tree = self.invoke('tree.json', host='claude-code')
        self.assertEqual(tree.returncode, 0, tree.stdout + tree.stderr)

        report = self.report()
        self.assertEqual(report['failed_attempts'], 1)
        groups = {group['usage_scope']: group for group in report['resource_totals']}
        unknown = groups['unknown']
        self.assertEqual((unknown['attempts'], unknown['known_usage_attempts']), (1, 0))
        self.assertEqual(unknown['token_field_coverage'], {
            'input_tokens': 0, 'cached_input_tokens': 0,
            'cache_creation_input_tokens': 0, 'output_tokens': 0,
            'reasoning_output_tokens': 0})
        self.assertIsNone(unknown['input_tokens'])
        self.assertIsNone(unknown['reasoning_output_tokens'])

        parent = groups['native_parent_turn']
        self.assertEqual(parent['known_usage_attempts'], 2)
        self.assertEqual(parent['token_field_coverage'], {
            'input_tokens': 2, 'cached_input_tokens': 2,
            'cache_creation_input_tokens': 0, 'output_tokens': 2,
            'reasoning_output_tokens': 1})
        self.assertEqual((parent['input_tokens'], parent['cached_input_tokens']), (105, 20))
        self.assertIsNone(parent['cache_creation_input_tokens'])
        self.assertEqual((parent['output_tokens'], parent['reasoning_output_tokens']), (36, 8))

        tree = groups['native_whole_tree']
        self.assertEqual(tree['token_field_coverage'], {
            'input_tokens': 1, 'cached_input_tokens': 1,
            'cache_creation_input_tokens': 1, 'output_tokens': 1,
            'reasoning_output_tokens': 0})
        self.assertEqual((tree['input_tokens'], tree['cached_input_tokens']), (2, 0))
        self.assertEqual((tree['cache_creation_input_tokens'], tree['output_tokens']), (4, 3))
        self.assertIsNone(tree['reasoning_output_tokens'])

    def test_copied_receipt_cannot_acquire_observed_credit(self):
        self.assertEqual(self.invoke().returncode, 0)
        self.accept()
        value = json.loads(self.output.read_text())
        legacy = reader.audit([self.output])
        self.assertIsNone(legacy['accepted_worker_tasks'])
        self.assertEqual(self.report()['accepted_worker_tasks'], 1)
        for field in ('head_after', 'task_sha256'):
            changed = copy.deepcopy(value)
            changed['execution_binding'][field] = 'f' * len(changed['execution_binding'][field])
            self.output.write_text(json.dumps(changed))
            report = self.report()
            self.assertEqual(report['accepted_worker_tasks'], 0)
            self.assertIsNone(report['attempts'][0]['usage_join'])
        self.output.write_text(json.dumps(value))
        # Restoring equivalent JSON is not the original digest-bound bytes.
        self.assertEqual(self.report()['accepted_worker_tasks'], 0)

    def test_exact_replay_deduplicates_conflict_and_partial_tail_refuse(self):
        self.assertEqual(self.invoke().returncode, 0)
        self.accept()
        path = self.repo / observation.LOG_PATH
        original = path.read_bytes()
        path.write_bytes(original + original)
        self.assertEqual(self.report()['observed_attempts'], 1)
        self.assertEqual(self.report()['accepted_worker_tasks'], 1)
        path.write_bytes(original + b'{"partial":')
        self.assertIsNone(self.report()['accepted_worker_tasks'])
        events = original.splitlines()
        changed = json.loads(events[1]); changed['receipt_sha256'] = 'f' * 64
        path.write_bytes(original + json.dumps(changed).encode() + b'\n')
        self.assertEqual(self.report()['accepted_worker_tasks'], 0)

    def test_missing_terminal_and_wrong_repository_do_not_earn_credit(self):
        self.assertEqual(self.invoke().returncode, 0)
        self.accept()
        path = self.repo / observation.LOG_PATH
        original = path.read_bytes()
        path.write_bytes(original.splitlines(keepends=True)[0])
        report = self.report()
        self.assertEqual(report['unfinished_attempts'], 1)
        self.assertEqual(report['accepted_worker_tasks'], 0)
        path.write_bytes(original)
        other = self.home / 'copied'; other.mkdir()
        import shutil
        shutil.copytree(self.repo / '.shadow', other / '.shadow')
        self.assertEqual(reader.audit_observed([other])['accepted_worker_tasks'], 0)

    def test_worker_log_append_invalidates_candidate(self):
        self.binary.with_suffix('.mode').write_text('tamper')
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        value = json.loads(self.output.read_text())
        self.assertEqual(value['blocked']['kind'], 'observation_incomplete')
        self.assertFalse(value['execution_binding']['execution_candidate'])
        self.assertIsNone(self.report()['accepted_worker_tasks'])

    def test_controller_terminal_failure_retains_unfinished_attempt(self):
        context = {k: self.claim[k] for k in ('entity','row','owner','claim_revision')}
        context['board_revision'] = board_api.snapshot()['revision']
        self.output = self.repo / '.shadow/evidence/terminal-failure.json'
        args = shadow_host.parser().parse_args(['run', '--host', 'codex', '--work-class', 'coding',
            '--delegation', 'direct', '--repo', str(self.repo), '--binary', str(self.binary),
            '--task-id', 'add-proof', '--task-file', str(self.task), '--out', str(self.output),
            '--allowed-path', 'result.txt', '--claim-context', json.dumps(context)])
        with patch.object(observation, 'finish', side_effect=telemetry.TelemetryError('fixture write failure')):
            value, code = shadow_host.run_attempt(args)
        self.assertNotEqual(code, 0)
        self.assertEqual(value['controller_observation']['state'], 'incomplete')
        self.assertFalse(value['execution_binding']['execution_candidate'])
        report = self.report()
        self.assertEqual(report['unfinished_attempts'], 1)
        self.assertEqual(report['accepted_worker_tasks'], 0)
        self.assertIsNone(report['attempts'][0]['usage_join'])

    def test_swapped_row_claim_and_receipt_identity_refuse(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.accept()
        log = self.repo / observation.LOG_PATH
        original = log.read_bytes()
        start, finish = [json.loads(line) for line in original.splitlines()]
        for field, bad in (('row', '~aa12'), ('claim_revision', start['claim_revision'] + 1),
                           ('task_sha256', 'f' * 64), ('owner_sha256', 'f' * 64)):
            changed = dict(finish, **{field: bad})
            log.write_text(json.dumps(start) + '\n' + json.dumps(changed) + '\n')
            report = self.report()
            self.assertEqual(report['accepted_worker_tasks'], 0, field)
            self.assertIsNone(report['attempts'][0]['usage_join'])
        log.write_bytes(original)

    def test_conflicting_start_and_valid_worker_append_cannot_hide(self):
        self.binary.with_suffix('.mode').write_text('tamper-valid')
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        value = json.loads(self.output.read_text())
        self.assertFalse(value['execution_binding']['execution_candidate'])
        self.assertEqual(value['blocked']['kind'], 'observation_incomplete')
        path = self.repo / observation.LOG_PATH
        first = json.loads(path.read_text().splitlines()[0])
        conflicting = dict(first, claim_revision=first['claim_revision'] + 1)
        path.write_text(json.dumps(first) + '\n' + json.dumps(conflicting) + '\n')
        report = self.report()
        self.assertEqual(report['observed_attempts'], 1)
        self.assertEqual(report['accepted_worker_tasks'], 0)
        self.assertEqual(report['unknown_attempts'], 1)
        self.assertIsNone(report['attempts'][0]['usage_join'])

    def test_off_mode_creates_no_stream(self):
        with patch.dict(os.environ, {'SHADOW_TELEMETRY': ''}):
            self.assertEqual(self.invoke().returncode, 0)
        self.assertFalse((self.repo / observation.LOG_PATH).exists())


class NativeUsage(unittest.TestCase):
    def process(self, events, **changes):
        raw = ('\n'.join(json.dumps(x) for x in events) + '\n').encode()
        return dict(stdout=raw, stdout_bytes=len(raw), returncode=0, timed_out=False, **changes)

    def events(self):
        return [dict(type='thread.started'), dict(type='turn.started'),
                dict(type='turn.completed', usage=dict(input_tokens=10, output_tokens=4))]

    def test_model_and_tool_text_cannot_supply_usage(self):
        events = [dict(type='item.completed', item=dict(text=json.dumps(x))) for x in self.events()]
        self.assertEqual(observation.native_usage('codex', self.process(events))['state'], 'unknown')
        events = self.events()
        events.insert(2, dict(type='item.completed', item=dict(text=json.dumps(dict(type='turn.completed', usage=dict(input_tokens=99999,output_tokens=99999))))))
        usage = observation.native_usage('codex', self.process(events))
        self.assertEqual(usage['input_tokens'], 10)
        self.assertIsNone(usage['observed_models'])
        self.assertIsNone(usage['provider_identity'])

    def test_partial_duplicate_failed_invalid_usage_stays_unknown(self):
        for mutation in ('truncated', 'duplicate', 'failed', 'boolean', 'negative'):
            events = self.events()
            process = self.process(events)
            if mutation == 'truncated': process['stdout_bytes'] += 1
            elif mutation == 'duplicate': process = self.process(events + [events[-1]])
            elif mutation == 'failed': process['returncode'] = 1
            else:
                events[-1]['usage']['input_tokens'] = True if mutation == 'boolean' else -1
                process = self.process(events)
            self.assertEqual(observation.native_usage('codex', process)['state'], 'unknown', mutation)

    def test_claude_tree_usage_is_separate_from_parent_and_billing(self):
        event = dict(type='result', subtype='success', is_error=False, total_cost_usd=0.03,
            usage=dict(input_tokens=999999),
            modelUsage={'claude-sonnet-4-6': dict(inputTokens=20, outputTokens=10, cacheReadInputTokens=3, cacheCreationInputTokens=5)})
        usage = observation.native_usage('claude-code', self.process([event]))
        self.assertEqual((usage['scope'], usage['input_tokens']), ('native_whole_tree', 20))
        self.assertEqual(usage['cost_basis'], 'native_reported_estimate')
        event['subtype'] = 'error_during_execution'
        event['total_cost_usd'] = 0
        self.assertEqual(observation.native_usage('claude-code', self.process([event]))['state'], 'unknown')


if __name__ == '__main__':
    unittest.main()
