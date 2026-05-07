"""Integration tests for scripts/launchd-helpers/acquire-cycle-lock.sh.

The helper is a thin bash wrapper around an atomic file claim. We exercise
its end-to-end behavior via subprocess so the test contract matches what
launchd cron wrappers actually invoke.

Test matrix (mirrors the LI-8 Fix Spec in
projects/linear-integration-hardening/PLAN.md):
- fresh acquire on an empty lock dir
- acquire while held by a live, recent PID — exits 1 with LOCKED token
- acquire while held by a live PID but past max-age — sweeps + claims
- acquire while held by a definitely-dead PID — sweeps + claims
- acquire while lock file is corrupt — sweeps + claims (defensive)
- release on existing lock — removes file, exits 0
- release on absent lock — idempotent, exits 0
- round-trip: acquire → release → acquire
- argument validation: missing --lock-file, bad --max-age-seconds
"""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER = REPO_ROOT / "scripts" / "launchd-helpers" / "acquire-cycle-lock.sh"


def _run(args: list[str], timeout: float = 10.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(HELPER), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _spawn_long_sleep() -> subprocess.Popen:
    """Spawn a background process whose PID can be used as a "live holder".

    We sleep 60s — well outside the test runtime — so kill -0 sees it alive
    for the full duration of any test that needs a live PID.
    """
    return subprocess.Popen(
        ["sleep", "60"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _write_lock(path: Path, pid: int, iso: str, epoch: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{pid}|{iso}|{epoch}\n")


def _find_dead_pid() -> int:
    """Return a PID we are confident is not currently a process.

    We spawn `true`, wait for it, then return its (now-recycled) PID. There
    is a tiny race where the kernel could reassign the PID before our test
    runs `kill -0`, but in practice the slot stays free for the duration of
    a unit test on macOS / Linux.
    """
    proc = subprocess.Popen(["true"])
    proc.wait()
    return proc.pid


class HelperPresenceTests(unittest.TestCase):
    def test_helper_exists_and_is_executable(self) -> None:
        self.assertTrue(HELPER.is_file(), f"helper missing at {HELPER}")
        self.assertTrue(os.access(HELPER, os.X_OK), f"{HELPER} not executable")


class AcquireTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.lock_dir = Path(self._tmp.name) / "locks"
        self.lock_file = self.lock_dir / "cycle.lock"

    def test_fresh_acquire_creates_lock_with_self_pid(self) -> None:
        result = _run(["--acquire", "--lock-file", str(self.lock_file)])
        self.assertEqual(
            result.returncode, 0,
            msg=f"stderr={result.stderr!r} stdout={result.stdout!r}",
        )
        self.assertIn("ACQUIRED", result.stderr)
        self.assertTrue(self.lock_file.exists())

        line = self.lock_file.read_text().strip()
        parts = line.split("|")
        self.assertEqual(len(parts), 3, msg=f"unexpected format: {line!r}")
        pid, iso, epoch = parts
        self.assertTrue(pid.isdigit(), f"pid not int: {pid!r}")
        self.assertRegex(iso, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertTrue(epoch.isdigit())

    def test_acquire_blocked_by_live_recent_holder(self) -> None:
        holder = _spawn_long_sleep()
        self.addCleanup(self._kill_proc, holder)

        _write_lock(
            self.lock_file,
            pid=holder.pid,
            iso="2026-05-07T16:00:00Z",
            epoch=int(time.time()) - 10,  # 10 s ago — fresh
        )

        result = _run(["--acquire", "--lock-file", str(self.lock_file)])
        self.assertEqual(result.returncode, 1, msg=result.stderr)
        self.assertIn("LOCKED", result.stderr)
        self.assertIn(f"pid={holder.pid}", result.stderr)

        # Lock still owned by holder.
        line = self.lock_file.read_text().strip()
        self.assertTrue(line.startswith(f"{holder.pid}|"))

    def test_acquire_sweeps_stale_by_age(self) -> None:
        holder = _spawn_long_sleep()
        self.addCleanup(self._kill_proc, holder)

        # PID alive but lock recorded an hour ago → past 25-min default.
        _write_lock(
            self.lock_file,
            pid=holder.pid,
            iso="2026-05-07T15:00:00Z",
            epoch=int(time.time()) - 3600,
        )

        result = _run(["--acquire", "--lock-file", str(self.lock_file)])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("STALE-SWEEP", result.stderr)
        self.assertIn("ACQUIRED", result.stderr)
        owner = self.lock_file.read_text().split("|")[0]
        self.assertNotEqual(int(owner), holder.pid)

    def test_acquire_sweeps_dead_pid(self) -> None:
        dead_pid = _find_dead_pid()
        # Recent epoch → "fresh" by age, only PID-aliveness fails.
        _write_lock(
            self.lock_file,
            pid=dead_pid,
            iso="2026-05-07T16:00:00Z",
            epoch=int(time.time()) - 5,
        )

        result = _run(["--acquire", "--lock-file", str(self.lock_file)])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("STALE-SWEEP", result.stderr)
        self.assertIn("ACQUIRED", result.stderr)

    def test_acquire_sweeps_corrupt_lock(self) -> None:
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self.lock_file.write_text("garbage-not-a-valid-lock\n")

        result = _run(["--acquire", "--lock-file", str(self.lock_file)])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("STALE-SWEEP", result.stderr)
        self.assertIn("ACQUIRED", result.stderr)

    def test_max_age_seconds_overrides_default(self) -> None:
        holder = _spawn_long_sleep()
        self.addCleanup(self._kill_proc, holder)

        # Lock is 100s old; default would treat as fresh, but caller passes 60.
        _write_lock(
            self.lock_file,
            pid=holder.pid,
            iso="2026-05-07T16:00:00Z",
            epoch=int(time.time()) - 100,
        )

        result = _run([
            "--acquire", "--lock-file", str(self.lock_file),
            "--max-age-seconds", "60",
        ])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("STALE-SWEEP", result.stderr)

    def _kill_proc(self, proc: subprocess.Popen) -> None:
        try:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=2.0)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


class ReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.lock_file = Path(self._tmp.name) / "cycle.lock"

    def test_release_removes_existing_lock(self) -> None:
        self.lock_file.write_text(f"{os.getpid()}|2026-05-07T16:00:00Z|0\n")
        result = _run(["--release", "--lock-file", str(self.lock_file)])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertFalse(self.lock_file.exists())
        self.assertIn("RELEASED", result.stderr)

    def test_release_is_idempotent_when_absent(self) -> None:
        self.assertFalse(self.lock_file.exists())
        result = _run(["--release", "--lock-file", str(self.lock_file)])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("RELEASE-NOOP", result.stderr)


class RoundTripTests(unittest.TestCase):
    def test_acquire_release_acquire(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_file = Path(tmp) / "cycle.lock"

            r1 = _run(["--acquire", "--lock-file", str(lock_file)])
            self.assertEqual(r1.returncode, 0, msg=r1.stderr)
            self.assertTrue(lock_file.exists())

            r2 = _run(["--release", "--lock-file", str(lock_file)])
            self.assertEqual(r2.returncode, 0, msg=r2.stderr)
            self.assertFalse(lock_file.exists())

            r3 = _run(["--acquire", "--lock-file", str(lock_file)])
            self.assertEqual(r3.returncode, 0, msg=r3.stderr)
            self.assertTrue(lock_file.exists())


class ArgValidationTests(unittest.TestCase):
    def test_missing_mode_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_file = Path(tmp) / "cycle.lock"
            result = _run(["--lock-file", str(lock_file)])
            self.assertEqual(result.returncode, 2, msg=result.stderr)
            self.assertIn("ERR", result.stderr)

    def test_missing_lock_file_errors(self) -> None:
        result = _run(["--acquire"])
        self.assertEqual(result.returncode, 2, msg=result.stderr)
        self.assertIn("ERR", result.stderr)

    def test_bad_max_age_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_file = Path(tmp) / "cycle.lock"
            result = _run([
                "--acquire", "--lock-file", str(lock_file),
                "--max-age-seconds", "not-a-number",
            ])
            self.assertEqual(result.returncode, 2, msg=result.stderr)
            self.assertIn("ERR", result.stderr)

    def test_unknown_arg_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_file = Path(tmp) / "cycle.lock"
            result = _run(["--acquire", "--lock-file", str(lock_file), "--bogus"])
            self.assertEqual(result.returncode, 2, msg=result.stderr)
            self.assertIn("ERR", result.stderr)


if __name__ == "__main__":
    unittest.main()
