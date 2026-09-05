from __future__ import annotations

import os
from pathlib import Path
import sys
import sysconfig
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from shadow_process_lib import run_bounded_pipes


class BoundedPipeProcessTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.cwd = Path(temporary.name)
        # setup-python's shared Linux interpreter needs its installed library
        # directory even in a deliberately minimal child environment. Do not
        # forward ambient loader settings or the rest of the host environment.
        self.child_env = {}
        if sys.platform.startswith("linux") and sysconfig.get_config_var("Py_ENABLE_SHARED"):
            self.child_env["LD_LIBRARY_PATH"] = str(Path(sys.base_prefix) / "lib")

    def execute(self, body: str, **kwargs):
        return run_bounded_pipes((sys.executable, "-c", body), cwd=self.cwd,
                                 env={"PATH": os.environ.get("PATH", ""), **self.child_env}, stdin=b"", **kwargs)

    def test_success_has_bounded_stdout_and_stderr(self):
        result = self.execute("import sys; print('out'); print('err', file=sys.stderr)")
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertFalse(result.timed_out)
        self.assertFalse(result.output_limited)
        self.assertEqual(result.stdout, b"out\n")
        self.assertEqual(result.stderr, b"err\n")

    def test_oversized_output_is_killed_without_retaining_unbounded_output(self):
        result = self.execute("import sys; sys.stdout.write('x'*20000); sys.stdout.flush()", max_output_bytes=1024)
        self.assertTrue(result.output_limited)
        self.assertLessEqual(len(result.stdout), 1024)

    def test_fast_exit_cap_plus_one_is_detected_not_silently_truncated(self):
        result = self.execute("import sys; sys.stdout.buffer.write(b'x'*16385)")
        self.assertTrue(result.output_limited)
        self.assertEqual(len(result.stdout), 16384)

    def test_fast_exit_exact_cap_and_two_streams_are_fully_retained(self):
        result = self.execute("import sys; sys.stdout.buffer.write(b'o'*16384); sys.stderr.buffer.write(b'e'*16384)")
        self.assertFalse(result.output_limited)
        self.assertEqual(result.stdout, b"o" * 16384)
        self.assertEqual(result.stderr, b"e" * 16384)

    def test_oversized_stderr_is_killed_without_retaining_unbounded_output(self):
        result = self.execute("import sys; sys.stderr.write('x'*20000); sys.stderr.flush()", max_output_bytes=1024)
        self.assertTrue(result.output_limited)
        self.assertLessEqual(len(result.stderr), 1024)

    def test_oversized_stdin_refuses_before_launch(self):
        with self.assertRaises(ValueError):
            run_bounded_pipes((sys.executable, "-c", "raise SystemExit(9)"), cwd=self.cwd,
                              env={}, stdin=b"x" * 1025, max_output_bytes=1024)

    def test_explicit_pass_fd_is_the_only_extra_inherited_descriptor(self):
        secret = self.cwd / "fd-data"
        secret.write_text("ok")
        fd = os.open(secret, os.O_RDONLY)
        self.addCleanup(os.close, fd)
        result = run_bounded_pipes((sys.executable, "-c", "import os; print(os.read(int(os.environ['FD']), 2).decode())"),
                                   cwd=self.cwd, env={**self.child_env, "FD": str(fd)}, stdin=b"", pass_fds=(fd,))
        self.assertEqual(result.stdout, b"ok\n")

    def test_unlisted_inheritable_sentinel_fd_is_closed(self):
        sentinel = self.cwd / "sentinel"
        sentinel.write_text("nope")
        fd = os.open(sentinel, os.O_RDONLY)
        self.addCleanup(os.close, fd)
        os.set_inheritable(fd, True)
        body = "import os; fd=int(os.environ['FD']);\ntry: os.fstat(fd)\nexcept OSError: print('closed')\nelse: print('leaked')"
        result = run_bounded_pipes((sys.executable, "-c", body), cwd=self.cwd,
                                   env={**self.child_env, "FD": str(fd)}, stdin=b"")
        self.assertEqual(result.stdout, b"closed\n")

    def test_strict_argument_types_refuse_before_launch(self):
        for changes in ({"stdin": bytearray()}, {"timeout": float("nan")}, {"timeout": True},
                        {"max_output_bytes": True}, {"pass_fds": (True,)}):
            values = {"stdin": b"", "timeout": 1, "max_output_bytes": 1024, "pass_fds": ()} | changes
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                run_bounded_pipes((sys.executable, "-c", "print('bad')"), cwd=self.cwd, env={}, **values)

    def test_timeout_is_bounded(self):
        start = time.monotonic()
        result = self.execute("import time; time.sleep(30)")
        self.assertTrue(result.timed_out)
        self.assertLess(time.monotonic() - start, 4)

    def assert_dead(self, pid: int):
        """A process-group kill must not leave a live (or zombie) descendant."""
        for _ in range(20):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.05)
        self.fail(f"descendant PID {pid} remains after group reap")

    def test_timeout_kills_term_ignoring_descendant_group(self):
        pid_file = self.cwd / "descendant-pid"
        body = (
            "import os,signal,time; p=os.fork(); "
            "\nif p: open('descendant-pid','w').write(str(p)); time.sleep(30)"
            "\nelse: signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"
        )
        result = self.execute(body)
        self.assertTrue(result.timed_out)
        self.assert_dead(int(pid_file.read_text()))

    def test_normal_parent_exit_still_reaps_pipe_holding_descendant(self):
        pid_file = self.cwd / "orphan-pid"
        body = (
            "import os,time; p=os.fork(); "
            "\nif p: open('orphan-pid','w').write(str(p))"
            "\nelse: time.sleep(30)"
        )
        result = self.execute(body)
        # Pipe closure is part of containment: a delayed close is reported as
        # timeout rather than being silently treated as a successful run.
        self.assertTrue(result.timed_out)
        self.assert_dead(int(pid_file.read_text()))

    def test_escaped_session_descendant_cannot_extend_absolute_deadline(self):
        pid_file = self.cwd / "escaped-pid"
        body = (
            "import os,time; p=os.fork(); "
            "\nif p: open('escaped-pid','w').write(str(p))"
            "\nelse: os.setsid(); time.sleep(3)"
        )
        start = time.monotonic()
        try:
            result = run_bounded_pipes((sys.executable, "-c", body), cwd=self.cwd,
                                       env=self.child_env, stdin=b"", timeout=.1)
            self.assertTrue(result.timed_out)
            self.assertLess(time.monotonic() - start, 1)
        finally:
            if pid_file.exists():
                pid = int(pid_file.read_text())
                try:
                    os.kill(pid, 9)
                except ProcessLookupError:
                    pass
