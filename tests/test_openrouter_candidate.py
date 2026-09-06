"""Real installed-container tests for isolated candidates, not provider proof."""
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "openrouter_candidate", Path(__file__).resolve().parents[1] / "scripts/dev/openrouter-candidate.py")
candidate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(candidate)



class ContainerProtocolTests(unittest.TestCase):
    """Portable fault injection for control flow, not kernel containment proof."""

    def attempt(self, *, changed=None, lost_create=False, recovery=True):
        cid = 'a' * 64
        calls = []
        state = {}
        original_is_file = Path.is_file
        original_tempdir = tempfile.TemporaryDirectory
        original_popen = subprocess.Popen

        def run(command, **kwargs):
            calls.append(command)
            if 'create' in command:
                self.assertIn('--memory=64m', command)
                self.assertIn('--memory-swap=64m', command)
                self.assertIn('--pull=never', command)
                self.assertFalse(any(arg.startswith('--pid=') for arg in command))
                self.assertEqual(command[-5:], [candidate.IMAGE, '-I', '-B', '/bootstrap.py', '/candidate/check.py'])
                root = Path(command[command.index('--cidfile') + 1]).parent
                state['root'] = root
                if lost_create:
                    # The daemon created it, but the client got no cidfile.
                    raise subprocess.TimeoutExpired(command, 10)
                (root / 'container-id').write_text(cid)
                return subprocess.CompletedProcess(command, 0, cid, '')
            if 'inspect' in command:
                root = state['root']
                config = {'Memory': 67108864, 'MemorySwap': 67108864, 'PidsLimit': 1,
                          'ReadonlyRootfs': True, 'NetworkMode': 'none', 'IpcMode': 'none',
                          'PidMode': '', 'CgroupnsMode': 'private',
                          'LogConfig': {'Type': 'none'}, 'CapDrop': ['ALL'],
                          'SecurityOpt': ['no-new-privileges'],
                          'Mounts': [{'BindOptions': {'NonRecursive': True}}] * 2}
                if changed:
                    config[changed[0]] = changed[1]
                spec = {'HostConfig': config, 'Image': candidate.IMAGE,
                        'Config': {'User': '65534:65534', 'Healthcheck': {'Test': ['NONE']}},
                        'Mounts': [{'Type': 'bind', 'Source': str(root / source),
                                    'Destination': destination, 'RW': False}
                                   for source, destination in [('candidate', '/candidate'),
                                                               ('bootstrap.py', '/bootstrap.py')]]}
                return subprocess.CompletedProcess(command, 0, json.dumps([spec]), '')
            if 'ls' in command:
                if command[-1].startswith('label='):
                    self.assertEqual(command[-1], 'label=' + calls[0][calls[0].index('--label') + 1])
                    return subprocess.CompletedProcess(command, 0, cid + '\n' if recovery else '', '')
                self.assertEqual(command[-1], 'id=' + cid)
                return subprocess.CompletedProcess(command, 0, b'', b'')
            self.assertEqual(command[-3:], ['rm', '--force', cid])
            return subprocess.CompletedProcess(command, 0, b'', b'')

        def popen(command, **kwargs):
            calls.append(command)
            self.assertEqual(command[-3:], ['start', '--attach', cid])
            # Simulate only a completed attach stream; never execute proposals.
            return original_popen(['/bin/sh', '-c',
                                   "printf 'OPENROUTER_CANDIDATE_READY\\n'"], **kwargs)

        with ExitStack() as stack:
            stack.enter_context(patch.object(candidate.sys, 'platform', 'darwin'))
            stack.enter_context(patch.object(Path, 'is_file', lambda path:
                True if str(path) == '/Applications/Docker.app/Contents/Resources/bin/docker'
                else original_is_file(path)))
            stack.enter_context(patch.object(Path, 'is_socket', return_value=True))
            stack.enter_context(patch.object(candidate.tempfile, 'TemporaryDirectory',
                                            side_effect=lambda **kwargs: original_tempdir()))
            stack.enter_context(patch.object(candidate.subprocess, 'run', side_effect=run))
            stack.enter_context(patch.object(candidate.subprocess, 'Popen', side_effect=popen))
            try:
                result = candidate.evaluate({'answer.py': '', 'check.py': 'pass'}, {'answer.py'},
                                            'check.py', '{"answer.py":"pass"}')
                return result, calls
            except (candidate.Refused, subprocess.TimeoutExpired) as error:
                return error, calls

    def test_missing_runtime_refuses_without_native_fallback(self):
        with patch.object(candidate.sys, 'platform', 'darwin'), \
                patch.object(Path, 'is_socket', return_value=False), \
                patch.object(candidate.subprocess, 'run') as run, \
                patch.object(candidate.subprocess, 'Popen') as popen:
            with self.assertRaisesRegex(candidate.Refused, 'runtime is unavailable'):
                candidate.evaluate({'answer.py': '', 'check.py': 'pass'}, {'answer.py'},
                                   'check.py', '{"answer.py":"pass"}')
        run.assert_not_called()
        popen.assert_not_called()

    def test_private_pid_default_and_checked_limits_allow_attach(self):
        result, calls = self.attempt()
        self.assertEqual(result['test_process_exit_code'], 0)
        self.assertFalse(result['accepted'])
        self.assertEqual(sum('start' in command for command in calls), 1)
        self.assertEqual(sum('rm' in command for command in calls), 1)

    def test_changed_controls_never_start_candidate(self):
        for change in [('Memory', 0), ('MemorySwap', -1), ('PidsLimit', 0),
                       ('PidMode', 'host'), ('CgroupnsMode', 'host'),
                       ('ReadonlyRootfs', False), ('NetworkMode', 'default')]:
            with self.subTest(change=change):
                result, calls = self.attempt(changed=change)
                self.assertIsInstance(result, candidate.Refused)
                self.assertIn('controls differ', str(result))
                self.assertFalse(any('start' in command for command in calls))
                self.assertEqual(sum('rm' in command for command in calls), 1)

    def test_lost_create_response_recovers_only_exact_label_and_removes(self):
        result, calls = self.attempt(lost_create=True)
        self.assertIsInstance(result, subprocess.TimeoutExpired)
        self.assertFalse(any('start' in command for command in calls))
        self.assertEqual(sum('rm' in command for command in calls), 1)

    def test_unconfirmed_create_retains_recovery_handle_and_never_guesses(self):
        result, calls = self.attempt(lost_create=True, recovery=False)
        self.assertIsInstance(result, candidate.Refused)
        self.assertRegex(str(result), 'recovery unconfirmed: org.shadow.openrouter-candidate=[0-9a-f]{32}')
        self.assertFalse(any('start' in command or 'rm' in command for command in calls))


@unittest.skipUnless(sys.platform == "darwin", "native proof requires characterized Docker Desktop")
class CandidateTests(unittest.TestCase):
    def test_failed_resource_or_filter_admission_never_runs_candidate(self):
        for broken in (candidate.BOOTSTRAP.replace('LIMIT = 64', 'LIMIT = 32', 1),
                       candidate.BOOTSTRAP.replace('assert lib.seccomp_load(ctx) == 0',
                                                   "raise RuntimeError('filter load failed')")):
            with self.subTest(bootstrap=broken[:30]), patch.object(candidate, 'BOOTSTRAP', broken):
                with self.assertRaisesRegex(candidate.Refused, 'admission did not complete'):
                    candidate.evaluate({'answer.py': '', 'check.py': "print('UNEXPECTED')"},
                                       {'answer.py'}, 'check.py', '{"answer.py":"pass"}')

    def test_timeout_and_output_flood_remove_only_the_owned_container(self):
        original_run = subprocess.run
        for code, deadline in (('while True: pass', 0.5),
                               ("import os\nwhile True: os.write(1, b'x' * 65536)", 5)):
            removed = []
            output_sizes = []
            roots = []

            def observe_run(command, **kwargs):
                result = original_run(command, **kwargs)
                if '--cidfile' in command:
                    roots.append(Path(command[command.index('--cidfile') + 1]).parent)
                if 'rm' in command:
                    self.assertEqual(command[-3:-1], ['rm', '--force'])
                    removed.append((command, kwargs['env']))
                    output_sizes.append((roots[0] / 'test-output').stat().st_size)
                return result

            before = time.monotonic()
            with self.subTest(code=code), patch.object(candidate, 'WALL_SECONDS', deadline), \
                    patch.object(candidate.subprocess, 'run', side_effect=observe_run):
                result = candidate.evaluate({'answer.py': '', 'check.py': 'import answer'},
                                            {'answer.py'}, 'check.py', json.dumps({'answer.py': code}))
            self.assertNotEqual(result['test_process_exit_code'], 0, result)
            self.assertLess(time.monotonic() - before, 12)
            self.assertEqual(len(removed), 1)
            self.assertLessEqual(output_sizes[0], candidate.OUTPUT_BYTES)
            if 'os.write' in code:
                self.assertEqual(output_sizes[0], candidate.OUTPUT_BYTES)
            command, env = removed[0]
            absent = original_run(command[:-3] + ['inspect', command[-1]], env=env,
                                  capture_output=True, text=True, timeout=10)
            self.assertNotEqual(absent.returncode, 0, absent.stdout)

    def test_create_response_lost_after_real_creation_removes_owned_container(self):
        original_run = subprocess.run
        created = []
        removed = []

        def lose_response(command, **kwargs):
            if 'create' in command:
                result = original_run(command, **kwargs)
                self.assertEqual(result.returncode, 0, result.stderr)
                cidfile = Path(command[command.index('--cidfile') + 1])
                created.append(cidfile.read_text().strip())
                cidfile.unlink()
                raise subprocess.TimeoutExpired(command, 10)
            if 'rm' in command:
                removed.append(command[-1])
            return original_run(command, **kwargs)

        with patch.object(candidate.subprocess, 'run', side_effect=lose_response):
            with self.assertRaises(subprocess.TimeoutExpired):
                candidate.evaluate({'answer.py': '', 'check.py': 'pass'}, {'answer.py'},
                                   'check.py', '{"answer.py":"pass"}')
        self.assertEqual(len(created), 1)
        self.assertEqual(removed, created)

    def test_cgroup_memory_ceiling_kills_oversized_resident_allocation(self):
        original_run = subprocess.run
        oom = []

        def inspect_before_removal(command, **kwargs):
            if 'rm' in command:
                state = original_run(command[:-3] + ['inspect', command[-1]], env=kwargs['env'],
                                     capture_output=True, text=True, timeout=10, check=True)
                oom.append(json.loads(state.stdout)[0]['State']['OOMKilled'])
            return original_run(command, **kwargs)

        # Only this fixture raises AS so that the independent cgroup ceiling,
        # rather than the address-space ceiling, receives the bounded attack.
        bootstrap = candidate.BOOTSTRAP.replace('resource.RLIMIT_AS, (LIMIT, LIMIT)',
                                                'resource.RLIMIT_AS, (4 * LIMIT, 4 * LIMIT)')
        with patch.object(candidate, 'BOOTSTRAP', bootstrap), \
                patch.object(candidate.subprocess, 'run', side_effect=inspect_before_removal):
            result = candidate.evaluate({'answer.py': '', 'check.py': 'import answer'}, {'answer.py'},
                                        'check.py', json.dumps({'answer.py': 'bytearray(80 * 1024 * 1024)'}))
        self.assertNotEqual(result['test_process_exit_code'], 0)
        self.assertEqual(oom, [True])

    def test_cleanup_retries_transient_failure_and_refuses_persistent_failure(self):
        original_run = subprocess.run
        for failures in (1, 2):
            removals = []

            def fail_removal(command, **kwargs):
                if 'rm' in command:
                    removals.append((command, kwargs['env']))
                    if len(removals) <= failures:
                        return subprocess.CompletedProcess(command, 1, b'', b'synthetic daemon failure')
                return original_run(command, **kwargs)

            try:
                with patch.object(candidate.subprocess, 'run', side_effect=fail_removal):
                    if failures == 1:
                        result = candidate.evaluate({'answer.py': '', 'check.py': 'pass'}, {'answer.py'},
                                                    'check.py', '{"answer.py":"pass"}')
                        self.assertEqual(result['test_process_exit_code'], 0)
                    else:
                        with self.assertRaisesRegex(candidate.Refused, 'cleanup unconfirmed: [0-9a-f]{64}'):
                            candidate.evaluate({'answer.py': '', 'check.py': 'pass'}, {'answer.py'},
                                               'check.py', '{"answer.py":"pass"}')
                self.assertEqual(len(removals), 2)
                self.assertEqual(removals[0][0][-1], removals[1][0][-1])
            finally:
                # Remove our one real fixture container after the simulated
                # persistent control failure; never leave a test orphan.
                if removals:
                    command, env = removals[-1]
                    original_run(command, env=env, capture_output=True, timeout=10)

    def test_changed_container_readback_refuses_before_start(self):
        original_run = subprocess.run
        original_popen = subprocess.Popen
        for change in ('unchanged', 'memory', 'source', 'recursive', 'logging'):
            started = []

            def observe_popen(command, **kwargs):
                if 'start' in command:
                    started.append(command)
                return original_popen(command, **kwargs)

            def change_inspect(command, **kwargs):
                result = original_run(command, **kwargs)
                if 'inspect' in command and change != 'unchanged':
                    data = json.loads(result.stdout)
                    if change == 'memory': data[0]['HostConfig']['Memory'] = 0
                    elif change == 'source': data[0]['Mounts'][0]['Source'] = '/unexpected'
                    elif change == 'recursive': data[0]['HostConfig']['Mounts'][0]['BindOptions']['NonRecursive'] = False
                    else: data[0]['HostConfig']['LogConfig']['Type'] = 'json-file'
                    result.stdout = json.dumps(data)
                return result

            with self.subTest(change=change), patch.object(candidate.subprocess, 'run', side_effect=change_inspect), \
                    patch.object(candidate.subprocess, 'Popen', side_effect=observe_popen):
                if change == 'unchanged':
                    result = candidate.evaluate({'answer.py': '', 'check.py': 'pass'}, {'answer.py'},
                                                'check.py', '{"answer.py":"pass"}')
                    self.assertEqual(result['test_process_exit_code'], 0)
                else:
                    with self.assertRaisesRegex(candidate.Refused, 'controls differ'):
                        candidate.evaluate({'answer.py': '', 'check.py': 'pass'}, {'answer.py'},
                                           'check.py', '{"answer.py":"pass"}')
            self.assertEqual(len(started), 1 if change == 'unchanged' else 0)

    def test_edit_then_test_process_leaves_input_unchanged(self):
        files = {"answer.py": "VALUE = 0\n", "tests/check.py": "from answer import VALUE\nassert VALUE == 42\n"}
        before = dict(files)
        result = candidate.evaluate(files, {"answer.py"}, "tests/check.py",
                                    json.dumps({"answer.py": "VALUE = 42\n"}))
        self.assertEqual(result["test_process_exit_code"], 0)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["candidate"], {"answer.py": "VALUE = 42\n"})
        self.assertEqual(files, before)

    def test_unfixed_candidate_fails_real_test(self):
        result = candidate.evaluate({"answer.py": "VALUE = 0\n", "check.py": "from answer import VALUE\nassert VALUE == 42\n"},
                                    {"answer.py"}, "check.py", '{"answer.py":"VALUE = 1\\n"}')
        self.assertNotEqual(result["test_process_exit_code"], 0)

    def test_untrusted_proposals_refuse_before_execution(self):
        files = {"answer.py": "VALUE = 0\n", "check.py": "raise RuntimeError('must not run')\n"}
        for proposal in ('{"../escape":"x"}', '{".git/config":"x"}', '{"check.py":"pass"}',
                         '{"answer.py":null}', '{"answer.py":"x","answer.py":"y"}',
                         '{"command":"/bin/sh"}', '{"answer.py":"x","extra.py":"x"}'):
            with self.subTest(proposal=proposal), self.assertRaises(candidate.Refused):
                candidate.evaluate(files, {"answer.py"}, "check.py", proposal)

    def test_early_exit_zero_is_not_acceptance(self):
        for exit_call in ("os._exit(0)", "sys.exit(0)"):
            result = candidate.evaluate(
                {"answer.py": "VALUE = 0", "check.py": "from answer import VALUE\nassert VALUE == 42"},
                {"answer.py"}, "check.py",
                json.dumps({"answer.py": "import os, sys\nVALUE = 0\n" + exit_call}))
            self.assertEqual(result["test_process_exit_code"], 0)
            self.assertFalse(result["accepted"])
            self.assertEqual(result["requires"], "independent ordinary-seat diff review")

    def test_keychain_framework_query_is_denied(self):
        # The host framework is not mounted into the Linux container. No real
        # item, credential, or Keychain service is accessed by this probe.
        hostile = '''import ctypes
try:
    ctypes.CDLL("/System/Library/Frameworks/Security.framework/Security")
except OSError:
    pass
else:
    raise AssertionError("host Keychain framework became accessible")
VALUE = 42
'''
        result = candidate.evaluate(
            {"answer.py": "VALUE = 0", "check.py": "from answer import VALUE\nassert VALUE == 42"},
            {"answer.py"}, "check.py", json.dumps({"answer.py": hostile}))
        self.assertEqual(result["test_process_exit_code"], 0, result)

    def test_hard_memory_limit_refuses_bounded_oversized_allocation(self):
        hostile = '''from pathlib import Path
limits = Path('/proc/self/limits').read_text().splitlines()
address_space = next(line for line in limits if line.startswith('Max address space'))
assert address_space.split()[3:5] == ['67108864', '67108864']
try:
    bytearray(80 * 1024 * 1024)
except MemoryError:
    pass
else:
    raise AssertionError("allocation exceeded the hard limit")
VALUE = 42
'''
        result = candidate.evaluate(
            {"answer.py": "VALUE = 0", "check.py": "from answer import VALUE\nassert VALUE == 42"},
            {"answer.py"}, "check.py", json.dumps({"answer.py": hostile}))
        self.assertEqual(result["test_process_exit_code"], 0, result)

    def test_syscall_aliases_and_hard_limit_changes_refuse(self):
        hostile = '''import ctypes, errno, os, resource
lib = ctypes.CDLL('libseccomp.so.2')
lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
libc = ctypes.CDLL(None, use_errno=True)
for name in ('execve', 'execveat', 'clone', 'clone3', 'socket', 'socketpair',
             'mount', 'ptrace', 'process_vm_writev', 'io_uring_setup',
             'bpf', 'memfd_create', 'unlinkat', 'renameat', 'writev'):
    number = lib.seccomp_syscall_resolve_name(name.encode())
    assert number >= 0, name
    assert libc.syscall(number, 0, 0, 0, 0, 0, 0) == -1, name
    assert ctypes.get_errno() in (errno.EPERM, errno.ENOSYS), (name, ctypes.get_errno())
for action in (lambda: resource.setrlimit(resource.RLIMIT_AS, (-1, -1)),
               lambda: os.open('/tmp/forbidden', os.O_CREAT | os.O_WRONLY, 0o600),
               lambda: os.dup(1)):
    try:
        action()
    except (OSError, ValueError):
        pass
    else:
        raise AssertionError('forbidden mutation succeeded')
fd = os.open('/candidate/check.py', os.O_RDONLY)
try:
    os.write(fd, b'pass')
except OSError as error:
    assert error.errno == errno.EPERM
else:
    raise AssertionError('write to non-output fd allowed')
VALUE = 42
'''
        result = candidate.evaluate(
            {"answer.py": "VALUE = 0", "check.py": "from answer import VALUE\nassert VALUE == 42"},
            {"answer.py"}, "check.py", json.dumps({"answer.py": hostile}))
        self.assertEqual(result["test_process_exit_code"], 0, result)

    def test_inventory_file_directory_collision_refuses(self):
        with self.assertRaises(candidate.Refused):
            candidate.evaluate({"a": "x", "a/b.py": "x", "check.py": "pass"},
                               {"a"}, "check.py", '{"a":"y"}')

    def test_native_denials_precede_effects(self):
        with tempfile.TemporaryDirectory(prefix="openrouter-candidate-denials-") as temp:
            external = Path(temp) / "private.txt"
            external.write_text("PRIVATE_SENTINEL")
            marker = Path(temp) / "escaped"
            hostile = f'''import errno, os, pathlib, socket, subprocess
def denied(action):
    try:
        action()
    except OSError as error:
        assert error.errno in (errno.EPERM, errno.EACCES, errno.ENOENT, errno.EROFS), error
        return
    raise AssertionError("forbidden operation succeeded")
denied(lambda: pathlib.Path({str(external)!r}).read_text())
denied(lambda: pathlib.Path({str(external)!r}).stat())
denied(lambda: os.listdir("/private/tmp"))
denied(lambda: pathlib.Path({str(marker)!r}).write_text("escape"))
denied(lambda: pathlib.Path("answer.py").unlink())
denied(lambda: pathlib.Path("check.py").write_text("pass"))
denied(lambda: subprocess.run(["/bin/sh", "-c", "exit 0"], check=True))
denied(lambda: subprocess.run(["/usr/bin/security", "help"], check=True))
denied(lambda: subprocess.run(["/usr/bin/git", "--version"], check=True))
denied(lambda: socket.create_connection(("127.0.0.1", 9), timeout=1))
VALUE = 42
'''
            result = candidate.evaluate({"answer.py": "VALUE = 0\n", "check.py": "from answer import VALUE\nassert VALUE == 42\n"},
                                        {"answer.py"}, "check.py", json.dumps({"answer.py": hostile}))
            self.assertEqual(result["test_process_exit_code"], 0, result)
            self.assertFalse(marker.exists())
            self.assertEqual(external.read_text(), "PRIVATE_SENTINEL")


if __name__ == "__main__":
    unittest.main()
