"""Tests for scripts/vidux-dev.py."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-dev.py"

spec = importlib.util.spec_from_file_location("vidux_dev", SCRIPT)
assert spec is not None
vidux_dev = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = vidux_dev
spec.loader.exec_module(vidux_dev)


class FakeChild:
    """Stands in for subprocess.Popen: always reports itself as already
    exited, matching a child that failed to bind its port and died
    immediately -- the scenario the panel reproduced against a real port
    collision."""

    def __init__(self, returncode: int = 1):
        self.returncode = returncode

    def poll(self):
        return self.returncode

    def send_signal(self, _sig):
        pass

    def wait(self, timeout=None):
        return self.returncode


class LongLivedThenExitChild:
    """Reports as still-running (poll() -> None) for enough polls to exceed
    FAST_FAIL_SECONDS at the test's tiny POLL interval, then exits."""

    def __init__(self, counter: dict, alive_polls: int = 20, returncode: int = 1):
        self._counter = counter
        self._alive_polls = alive_polls
        self.returncode = returncode

    def poll(self):
        self._counter["n"] += 1
        if self._counter["n"] <= self._alive_polls:
            return None
        return self.returncode

    def send_signal(self, _sig):
        pass

    def wait(self, timeout=None):
        return self.returncode


class ViduxDevRestartLoopTests(unittest.TestCase):
    def setUp(self):
        self.original_browse = vidux_dev.BROWSE
        self.original_watch = vidux_dev.WATCH
        self.original_poll = vidux_dev.POLL
        self.original_fast_fail_seconds = vidux_dev.FAST_FAIL_SECONDS
        self.original_start_child = vidux_dev.start_child
        # Real, existing paths so main()'s early existence guards pass --
        # start_child is patched below so BROWSE is never actually exec'd.
        vidux_dev.BROWSE = ROOT / "bin" / "vidux-browse"
        vidux_dev.WATCH = ROOT / "browser"
        vidux_dev.POLL = 0.001

    def tearDown(self):
        vidux_dev.BROWSE = self.original_browse
        vidux_dev.WATCH = self.original_watch
        vidux_dev.POLL = self.original_poll
        vidux_dev.FAST_FAIL_SECONDS = self.original_fast_fail_seconds
        vidux_dev.start_child = self.original_start_child

    def test_gives_up_after_repeated_fast_failures_instead_of_looping_forever(self):
        """Round-1 open-source panel finding: a child that fails immediately
        (e.g. port already in use) used to be respawned every POLL interval
        forever, with no backoff and no give-up condition -- reproduced live
        as 10+ restart attempts in 8 seconds against a real port collision.
        main() must eventually stop and return non-zero with an actionable
        message instead of spinning indefinitely."""
        calls = []

        def fake_start_child():
            calls.append(1)
            return FakeChild(returncode=1)

        vidux_dev.start_child = fake_start_child

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc = vidux_dev.main()

        self.assertEqual(rc, 1)
        self.assertEqual(len(calls), vidux_dev.MAX_FAST_FAILURES)
        output = stderr.getvalue()
        self.assertIn("giving up instead of looping forever", output)
        self.assertIn("port", output.lower())

    def test_long_lived_child_resets_the_failure_counter(self):
        """A child that runs past FAST_FAIL_SECONDS before dying should not
        count toward the give-up threshold -- only rapid, back-to-back
        failures should trip it. Proven by interleaving 2 fast failures, one
        long-lived child, then 5 more fast failures: if the long-lived child
        didn't reset the counter, main() would give up after the 5th fast
        failure overall (7 start_child() calls); with the reset it must run
        past that to the 5 consecutive failures after the reset (8 calls)."""
        vidux_dev.FAST_FAIL_SECONDS = 0.05
        vidux_dev.POLL = 0.01
        # One shared counter of how many times poll() has been asked on the
        # "long-lived" 3rd child -- stays alive (poll -> None) for enough
        # iterations to exceed FAST_FAIL_SECONDS, then reports exited.
        long_lived_polls = {"n": 0}
        calls = []

        def fake_start_child():
            call_index = len(calls)
            calls.append(1)
            if call_index == 2:  # the 3rd start_child() call
                return LongLivedThenExitChild(long_lived_polls)
            return FakeChild(returncode=1)

        vidux_dev.start_child = fake_start_child

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc = vidux_dev.main()

        self.assertEqual(rc, 1)
        # 2 fast fails + 1 long-lived (reset) + 5 fast fails to give up = 8.
        self.assertEqual(len(calls), 8)


if __name__ == "__main__":
    unittest.main()
