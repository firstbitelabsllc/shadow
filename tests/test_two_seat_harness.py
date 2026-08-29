"""Black-box proof for the sealed two-seat acceptance harness.

The harness is valuable only if its cheap default cannot spend host quota and
its live tier proves the same behavior without touching the operator's HOME or
portfolio.  The native hosts below are deterministic test doubles, but they
drive the real Shadow status, throw, and accept verbs against the disposable
portfolio minted by the production harness.
"""

from __future__ import annotations

from contextlib import redirect_stderr
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

HARNESS_SPEC = importlib.util.spec_from_file_location(
    "shadow_verify_two_seat_test",
    Path(__file__).resolve().parent.parent / "scripts" / "shadow-verify-two-seat.py",
)
assert HARNESS_SPEC and HARNESS_SPEC.loader
harness = importlib.util.module_from_spec(HARNESS_SPEC)
sys.modules[HARNESS_SPEC.name] = harness
HARNESS_SPEC.loader.exec_module(harness)


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "shadow-verify-two-seat.py"
GOAL = harness.DEFAULT_GOAL
GOAL_SHA256 = hashlib.sha256(GOAL.encode("utf-8")).hexdigest()


def command(script: Path, *args: str) -> list[str]:
    return [str(script.parent / "shadow-python.sh"), str(script), *args]


def run_harness(
    script: Path,
    home: Path,
    *args: str,
    extra_env: dict[str, str] | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "HOME": str(home),
        "SHADOW_PORTFOLIO_ROOT": str(home / "operator-portfolio"),
    }
    env.update(extra_env or {})
    return subprocess.run(
        command(script, *args),
        cwd=str(script.parent.parent),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def receipt(result: subprocess.CompletedProcess[str]) -> dict:
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise AssertionError(
            f"stdout must be exactly one closed JSON receipt, got:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        ) from error


def assert_closed_receipt(test: unittest.TestCase, data: dict, forbidden: list[str]) -> None:
    test.assertEqual(
        set(data),
        {"schema", "status", "mode", "goal_sha256", "origin_main", "seats", "board", "failure"},
    )
    test.assertEqual(
        set(data["board"]),
        {"initial_revision", "final_revision", "completed", "claims"},
    )
    encoded = json.dumps(data, sort_keys=True)
    for secret in forbidden:
        test.assertNotIn(secret, encoded)
    test.assertNotIn("PLAN.md", encoded)
    test.assertNotIn("[pending]", encoded)
    test.assertNotIn("prompt", encoded.lower())
    test.assertNotIn("transcript", encoded.lower())


class Fixture:
    """One operator HOME plus an isolated source clone with a local origin."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.operator_home = self.root / "operator-home"
        self.operator_home.mkdir()
        self.operator_portfolio = self.operator_home / "operator-portfolio"
        self.operator_portfolio.mkdir()
        self.sentinel = self.operator_home / ".shadow" / "root-board.json"
        self.sentinel.parent.mkdir()
        self.sentinel.write_text('{"operator":"untouched"}\n', encoding="utf-8")
        self.operator_shadow_before = (
            self.sentinel.parent.lstat().st_mode & 0o7777,
            self._tree_snapshot(self.sentinel.parent),
        )
        self.goal = self.root / "frozen-goal.txt"
        self.goal.write_text(GOAL, encoding="utf-8")
        self.checkout = self.root / "source"
        shutil.copytree(ROOT, self.checkout, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        self._git(self.checkout, "init", "-q")
        self._git(self.checkout, "config", "user.name", "Two Seat Fixture")
        self._git(self.checkout, "config", "user.email", "fixture@example.invalid")
        self._git(self.checkout, "add", "-A")
        self._git(self.checkout, "commit", "-qm", "fixture source")
        self.origin = self.root / "origin.git"
        self._git(self.root, "init", "-q", "--bare", str(self.origin))
        canonical = "https://github.com/firstbitelabsllc/shadow.git"
        self._git(self.checkout, "config", f"url.{self.origin}.insteadOf", canonical)
        self._git(self.checkout, "remote", "add", "origin", canonical)
        self._git(self.checkout, "push", "-q", "-u", "origin", "HEAD:main")
        self._git(self.origin, "symbolic-ref", "HEAD", "refs/heads/main")
        self.origin_main = self._git(self.checkout, "rev-parse", "HEAD").stdout.strip()

    @staticmethod
    def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        env = harness.git_environment()
        result = subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", *args],
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return result

    @property
    def script(self) -> Path:
        return self.checkout / "scripts" / SCRIPT.name

    @staticmethod
    def _tree_snapshot(root: Path) -> dict[str, tuple[str, int, bytes | str]]:
        """Capture every operator-board entry without following symlinks."""
        result: dict[str, tuple[str, int, bytes | str]] = {}
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root).as_posix()
            mode = path.lstat().st_mode & 0o7777
            if path.is_symlink():
                result[relative] = ("symlink", mode, os.readlink(path))
            elif path.is_dir():
                result[relative] = ("directory", mode, b"")
            else:
                result[relative] = ("file", mode, path.read_bytes())
        return result

    def assert_operator_state_untouched(self, test: unittest.TestCase) -> None:
        test.assertEqual(
            (
                self.sentinel.parent.lstat().st_mode & 0o7777,
                self._tree_snapshot(self.sentinel.parent),
            ),
            self.operator_shadow_before,
            "the harness mutated the operator's real Shadow board tree",
        )
        test.assertEqual(list(self.operator_portfolio.iterdir()), [])


HOST_BODY = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

SEAT = __SEAT__
MODE = os.environ.get("SHADOW_TEST_HOST_MODE", "complete")
# The host process keeps the operator's real HOME (a live session must be a
# logged-in one); everything scratch-scoped is reached through the portfolio,
# whose parent is the harness scratch root holding the sealed home.
HOME = Path(os.environ["HOME"])
PORTFOLIO = Path(os.environ["SHADOW_PORTFOLIO_ROOT"])
SCRATCH_HOME = PORTFOLIO.parent / "home"
SHADOW = "shadow"
MARKER = Path(os.environ["SHADOW_TEST_INVOCATIONS"])
MARKER.parent.mkdir(parents=True, exist_ok=True)
with MARKER.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps({
        "seat": SEAT,
        "argv": sys.argv[1:],
        "cwd": str(Path.cwd().resolve()),
        "home": str(HOME.resolve()),
        "portfolio": str(PORTFOLIO.resolve()),
        "board_exists": (SCRATCH_HOME / ".shadow").is_dir(),
    }, sort_keys=True) + "\n")

if MODE == "nonzero" and SEAT == "claude":
    raise SystemExit(23)
if MODE == "timeout" and SEAT == "claude":
    child = subprocess.Popen(
        ["sh", "-c", "trap 'printf drained > \"$SHADOW_TEST_DRAINED\"; exit 0' TERM INT; while :; do sleep 1; done"],
        env=os.environ,
    )
    time.sleep(30)
if MODE == "complete_descendant":
    subprocess.Popen(
        ["sh", "-c", "trap 'printf drained >> \"$SHADOW_TEST_DRAINED\"; exit 0' TERM INT; while :; do sleep 1; done"],
        env=os.environ,
    )

if MODE == "denied_ps":
    # Models a real codex host: its sandbox denies `ps`, so the shim's
    # parent-pid walk collapses and attribution must ride the seat token.
    stub_dir = Path.cwd() / ("ps-stub-" + SEAT)
    stub_dir.mkdir(exist_ok=True)
    stub = stub_dir / "ps"
    stub.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    stub.chmod(0o755)
    os.environ["PATH"] = str(stub_dir) + os.pathsep + os.environ["PATH"]

def shadow(*args):
    # new_session models a real Claude host, whose shell tool runs every
    # command as a fresh OS-session leader; denied_ps runs the same way so
    # neither session identity nor ancestry can attribute its commands.
    return subprocess.run(
        [SHADOW, *args], capture_output=True, text=True, check=False,
        env=os.environ, start_new_session=(MODE in ("new_session", "denied_ps")),
    )

all_args = " ".join(sys.argv[1:])
goal = re.search(r"\b[0-9a-f]{64}\b", all_args)
refs = re.findall(r"\b[0-9a-f]{40}\b", all_args)
identity = ((goal.group(0) if goal else "0" * 64) + "\n" + (refs[-1] if refs else "0" * 40) + "\n")

def emit_identity():
    out = None
    for index, arg in enumerate(sys.argv[:-1]):
        if arg == "--output-last-message":
            out = Path(sys.argv[index + 1])
    if out:
        out.write_text(identity, encoding="utf-8")
    else:
        sys.stdout.write(identity)

if MODE == "one_seat" and SEAT == "codex":
    emit_identity()
    raise SystemExit(0)

if MODE == "outside" and SEAT == "claude":
    outside = Path(os.environ["SHADOW_TEST_OUTSIDE_REPO"])
    attempts = (
        shadow("throw", "--repo", str(PORTFOLIO / "alpha"), "--repo", str(outside),
               "--task", "~cc33", "--by", SEAT),
        shadow("status", f"--root={outside}", "--json", "--by", SEAT),
    )
    if any(attempt.returncode == 0 for attempt in attempts):
        raise SystemExit(41)

if MODE == "impersonate" and SEAT == "claude":
    attempts = (
        shadow("status", "--json", "--by", "codex"),
        shadow("status", "--json", "--by", "claude", "--by", "codex"),
    )
    if any(attempt.returncode == 0 for attempt in attempts):
        raise SystemExit(42)

if MODE == "cross_shim":
    if SEAT == "codex":
        emit_identity()
        raise SystemExit(0)
    claude_shadow = Path.cwd() / "bin" / "claude" / "shadow"
    codex_shadow = Path.cwd() / "bin" / "codex" / "shadow"
    commands = (
        (claude_shadow, "throw", "--repo", str(PORTFOLIO / "alpha"), "--task", "~aa11", "--by", "claude"),
        (codex_shadow, "throw", "--repo", str(PORTFOLIO / "beta"), "--task", "~bb22", "--by", "codex"),
        (claude_shadow, "status", "--json", "--by", "claude"),
        (codex_shadow, "status", "--json", "--by", "codex"),
        (claude_shadow, "accept", "--repo", str(PORTFOLIO / "alpha"), "--row", "~aa11", "--by", "claude"),
        (codex_shadow, "accept", "--repo", str(PORTFOLIO / "beta"), "--row", "~bb22", "--by", "codex"),
    )
    for direct in commands:
        if subprocess.run([str(direct[0]), *direct[1:]], env=os.environ).returncode:
            raise SystemExit(43)
    emit_identity()
    raise SystemExit(0)

claimed = None
# CI can spend several seconds scheduling the two fake hosts under load. Keep
# the rendezvous bounded, but leave enough room for both processes to start.
deadline = time.monotonic() + 25
completions = 2 if MODE == "one_seat" and SEAT == "claude" else 1
for completion in range(completions):
    claimed = None
    while claimed is None and time.monotonic() < deadline:
        status = shadow("status", "--json", "--by", SEAT)
        if status.returncode:
            raise SystemExit(31)
        data = json.loads(status.stdout)
        for plan in data["v4_plans"]:
            row = plan.get("next_unclaimed")
            if not row:
                continue
            repo = PORTFOLIO / plan["project"]
            thrown = shadow("throw", "--repo", str(repo), "--task", row, "--by", SEAT)
            if thrown.returncode == 0:
                claimed = (repo, row)
                break
        if claimed is None:
            time.sleep(0.05)
    if claimed is None:
        raise SystemExit(32)

    if MODE != "one_seat":
        (SCRATCH_HOME / ("claimed-" + SEAT)).write_text("yes", encoding="utf-8")
        peer = "codex" if SEAT == "claude" else "claude"
        while not (SCRATCH_HOME / ("claimed-" + peer)).exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        observed = shadow("status", "--json", "--by", SEAT)
        if observed.returncode:
            raise SystemExit(34)

    if MODE not in ("partial", "orphan") or SEAT != "claude":
        accepted = shadow("accept", "--repo", str(claimed[0]), "--row", claimed[1], "--by", SEAT)
        if accepted.returncode:
            raise SystemExit(33)
        (SCRATCH_HOME / ("accepted-" + SEAT)).write_text("yes", encoding="utf-8")

if MODE == "drift" and SEAT == "claude":
    while not (SCRATCH_HOME / "accepted-codex").exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    tampered = subprocess.run(
        [os.environ["SHADOW_TEST_REAL_SHADOW"], "priority", "--repo", str(PORTFOLIO / "alpha"),
         "--value", "5"],
        # Bypassing the shim on purpose to simulate drift — but pinned to the
        # SCRATCH home, or this tamper would edit the operator's real board.
        env={**os.environ, "HOME": str(SCRATCH_HOME)}, capture_output=True, text=True,
    )
    if tampered.returncode:
        raise SystemExit(35)

if MODE == "identity" and SEAT == "claude":
    identity = ("f" * 64) + "\n" + (refs[-1] if refs else "0" * 40) + "\n"
emit_identity()
'''


def fake_hosts(root: Path) -> tuple[Path, Path, Path, Path]:
    bindir = root / "fake-hosts"
    bindir.mkdir()
    marker = root / "host-invocations.txt"
    drained = root / "descendant-drained.txt"
    paths = []
    for seat in ("claude", "codex"):
        path = bindir / seat
        path.write_text(HOST_BODY.replace("__SEAT__", repr(seat)), encoding="utf-8")
        path.chmod(0o755)
        paths.append(path)
    return paths[0], paths[1], marker, drained


class OfflineDefaultIsSealed(unittest.TestCase):
    def test_default_spends_no_host_quota_and_leaves_operator_state_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            fixture = Fixture(root)
            claude, codex, marker, _ = fake_hosts(root)
            result = run_harness(
                fixture.script,
                fixture.operator_home,
                "--goal-file", str(fixture.goal), "--json",
                extra_env={
                    "SHADOW_CLAUDE_CODE_BIN": str(claude),
                    "SHADOW_CODEX_BIN": str(codex),
                    "SHADOW_TEST_INVOCATIONS": str(marker),
                },
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(marker.exists(), "offline default invoked a native host")
            data = receipt(result)
            self.assertEqual(data["status"], "pass")
            self.assertEqual(data["mode"], "offline")
            self.assertEqual(data["goal_sha256"], GOAL_SHA256)
            self.assertEqual(data["board"]["completed"], 2)
            self.assertEqual(data["board"]["claims"], 0)
            self.assertTrue(all(seat["completed"] for seat in data["seats"]))
            fixture.assert_operator_state_untouched(self)
            assert_closed_receipt(self, data, [str(root), GOAL, "fixture source"])

    def test_ambient_shadow_root_cannot_redirect_the_sealed_commands(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            fixture = Fixture(root)
            alternate = root / "alternate-shadow"
            shutil.copytree(fixture.checkout, alternate, ignore=shutil.ignore_patterns(".git"))
            marker = root / "alternate-root-used.txt"
            (alternate / "scripts" / "shadow-status.py").write_text(
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('used', encoding='utf-8')\n"
                "print('{}')\n",
                encoding="utf-8",
            )
            result = run_harness(
                fixture.script,
                fixture.operator_home,
                "--goal-file", str(fixture.goal), "--json",
                extra_env={
                    "SHADOW_ROOT": str(alternate),
                    "SHADOW_DEV_ROOT": str(alternate),
                },
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(marker.exists())
            self.assertEqual(receipt(result)["status"], "pass")
            fixture.assert_operator_state_untouched(self)

    def test_ambient_git_state_cannot_escape_the_scratch_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            fixture = Fixture(root)
            outside = root / "outside-git"
            outside.mkdir()
            Fixture._git(outside, "init", "-q")
            Fixture._git(outside, "config", "user.name", "Outside Git")
            Fixture._git(outside, "config", "user.email", "outside-git@example.invalid")
            sentinel = outside / "sentinel.txt"
            sentinel.write_text("untouched\n", encoding="utf-8")
            Fixture._git(outside, "add", "sentinel.txt")
            Fixture._git(outside, "commit", "-qm", "outside sentinel")
            before_head = Fixture._git(outside, "rev-parse", "HEAD").stdout.strip()
            before_tree = sentinel.read_bytes()
            hook_marker = root / "ambient-hook-ran.txt"
            hooks = root / "ambient-hooks"
            hooks.mkdir()
            hook = hooks / "post-commit"
            hook.write_text(
                "#!/bin/sh\n"
                f"printf used > {str(hook_marker)!r}\n",
                encoding="utf-8",
            )
            hook.chmod(0o755)
            result = run_harness(
                fixture.script,
                fixture.operator_home,
                "--goal-file", str(fixture.goal), "--json",
                extra_env={
                    "GIT_DIR": str(outside / ".git"),
                    "GIT_WORK_TREE": str(outside),
                    "GIT_INDEX_FILE": str(outside / ".git" / "index"),
                    "GIT_CONFIG_COUNT": "1",
                    "GIT_CONFIG_KEY_0": "core.hooksPath",
                    "GIT_CONFIG_VALUE_0": str(hooks),
                },
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(receipt(result)["status"], "pass")
            self.assertEqual(Fixture._git(outside, "rev-parse", "HEAD").stdout.strip(), before_head)
            self.assertEqual(sentinel.read_bytes(), before_tree)
            self.assertEqual(Fixture._git(outside, "status", "--porcelain").stdout, "")
            self.assertFalse(hook_marker.exists())
            fixture.assert_operator_state_untouched(self)


class _NoCleanup:
    """Cleanup handle for guard callers whose with-block owns teardown."""

    def cleanup(self) -> None:
        return


class VerdictAndEvidence(unittest.TestCase):
    def _run_offline(self, home: Path) -> int:
        goal = home / "goal.md"
        goal.write_text(GOAL, encoding="utf-8")
        with mock.patch.dict(os.environ, {"HOME": str(home)}, clear=False):
            return harness.main(["--goal-file", str(goal), "--json"])

    def test_the_cleanup_flag_stays_so_an_orphan_writer_cannot_mask_the_verdict(self) -> None:
        # A drained seat's fresh-session grandchild can keep writing inside
        # the scratch tree; ENOTEMPTY on cleanup must never replace the
        # honest HarnessError with "internal_error". Pin the mechanism.
        seen: dict[str, object] = {}
        real_td = harness.tempfile.TemporaryDirectory

        class Recording(real_td):
            def __init__(self, *args, **kwargs):
                seen.update(kwargs)
                super().__init__(*args, **kwargs)

        with tempfile.TemporaryDirectory() as dirname:
            home = Path(dirname) / "home"
            home.mkdir()
            with mock.patch.object(harness.tempfile, "TemporaryDirectory", Recording):
                code = self._run_offline(home)

        self.assertEqual(code, 0)
        self.assertIs(seen.get("ignore_cleanup_errors"), True)

    def test_a_failure_names_which_seat_never_booted(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            home = Path(dirname) / "home"
            home.mkdir()
            stderr = io.StringIO()
            with (
                mock.patch.object(
                    harness,
                    "final_facts",
                    return_value=(
                        {"initial_revision": 1, "final_revision": 1, "completed": 0, "claims": 0},
                        {},
                    ),
                ),
                redirect_stderr(stderr),
            ):
                code = self._run_offline(home)

        self.assertEqual(code, 1)
        self.assertIn("seat claude produced no output (never booted)", stderr.getvalue())
        self.assertIn("seat codex produced no output (never booted)", stderr.getvalue())


class ThreeSeatsCoordinateOffline(unittest.TestCase):
    """The multi-seat regime is single-vs-multi, not two (owner law,
    2026-08-11): three seats on one board must claim disjoint rows, all
    observe the shared overlap, and complete everything with proof — in the
    free offline tier, so N costs nothing. The live paid tier refuses any
    seat count but the minimal two-seat witness.
    """

    def test_three_offline_seats_complete_three_disjoint_rows(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            fixture = Fixture(root)
            result = run_harness(
                fixture.script,
                fixture.operator_home,
                "--goal-file", str(fixture.goal), "--seats", "3", "--json",
                timeout=120,
            )
            # Same starvation law as the live tier: this walk spawns three seat
            # threads whose CLI subprocesses must all reach a 20-second barrier,
            # so fleet load can produce inconclusive/partial_completion with an
            # empty board before any seat claims (measured 2026-08-18, 2-in-4
            # under a takeoff shake). The harness refuses to grade that; so do we.
            LiveTwoSeatProof._skip_if_host_starved(self, result, _NoCleanup())
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = receipt(result)
            self.assertEqual(data["status"], "pass")
            self.assertEqual(data["mode"], "offline")
            self.assertEqual([seat["name"] for seat in data["seats"]], ["claude", "codex", "seat3"])
            self.assertTrue(all(seat["completed"] for seat in data["seats"]))
            self.assertEqual(data["board"]["completed"], 3)
            self.assertEqual(data["board"]["claims"], 0)
            fixture.assert_operator_state_untouched(self)
            assert_closed_receipt(self, data, [str(root), GOAL, "fixture source"])

    def test_a_starved_offline_walk_skips_instead_of_failing(self) -> None:
        """The wiring itself, pinned behaviorally: feed the offline test a
        canned starved receipt and the test method must SKIP, not fail."""
        canned = subprocess.CompletedProcess(
            args=[], returncode=1,
            stdout=json.dumps({
                "status": "inconclusive", "failure": "partial_completion",
                "mode": "offline", "goal_sha256": "0" * 64, "origin_main": "0" * 40,
                "schema": "shadow.two-seat-verification.v1",
                "seats": [], "board": {"claims": 0, "completed": 0,
                                        "final_revision": 0, "initial_revision": 0},
            }),
            stderr="",
        )
        class _StubFixture:
            # The real Fixture builds a git checkout whose background
            # maintenance raced Linux rmtree during the with-block teardown a
            # SkipTest unwinds through (CI 2026-08-18: OSError Directory not
            # empty: '.git' converted the clean skip into an error). The pin
            # exercises the WIRING, not fixture construction, so it needs only
            # the three attributes read before the guard fires.
            def __init__(self, root: Path) -> None:
                self.script = root / "unused-script"
                self.operator_home = root / "unused-home"
                self.goal = root / "unused-goal"

        real = globals()["run_harness"], globals()["Fixture"]
        globals()["run_harness"] = lambda *a, **k: canned
        globals()["Fixture"] = _StubFixture
        try:
            case = ThreeSeatsCoordinateOffline("test_three_offline_seats_complete_three_disjoint_rows")
            outcome = unittest.TestResult()
            case.run(outcome)
        finally:
            globals()["run_harness"], globals()["Fixture"] = real
        self.assertEqual(len(outcome.skipped), 1, (outcome.failures, outcome.errors))
        self.assertEqual(outcome.failures, [])
        self.assertEqual(outcome.errors, [])

    def test_live_refuses_any_seat_count_but_the_minimal_pair(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            fixture = Fixture(root)
            result = run_harness(
                fixture.script,
                fixture.operator_home,
                "--live", "--goal-file", str(fixture.goal), "--seats", "3", "--json",
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("minimal two-seat witness", result.stderr)


class LiveTwoSeatProof(unittest.TestCase):
    def _run(self, mode: str = "complete", timeout_seconds: int = 30, *, expected_failure: str | None = None):
        context = tempfile.TemporaryDirectory()
        root = Path(context.name).resolve()
        fixture = Fixture(root)
        claude, codex, marker, drained = fake_hosts(root)
        result = run_harness(
            fixture.script,
            fixture.operator_home,
            "--live", "--goal-file", str(fixture.goal),
            "--timeout-seconds", str(timeout_seconds), "--json",
            extra_env={
                "SHADOW_CLAUDE_CODE_BIN": str(claude),
                "SHADOW_CODEX_BIN": str(codex),
                "SHADOW_TEST_REAL_SHADOW": str(fixture.checkout / "bin" / "shadow"),
                "SHADOW_TEST_INVOCATIONS": str(marker),
                "SHADOW_TEST_DRAINED": str(drained),
                "SHADOW_TEST_HOST_MODE": mode,
            },
            timeout=max(30, timeout_seconds + 15),
        )
        self._skip_if_host_starved(result, context, expected_failure=expected_failure)
        return context, root, fixture, marker, drained, result

    def _skip_if_host_starved(self, result, context, *, expected_failure: str | None = None) -> None:
        """Machine contention is not a product failure.

        The harness itself reports ``status: inconclusive`` when a spawned
        host cannot start or drain — it refuses to call that outcome either
        pass or fail. Asserting rc 0 over it turns a busy machine into a
        product red: measured 2026-08-16, two full-suite runs failed here
        while an agent fleet held host capacity, and both passed in ~15s
        isolated at the same ref.

        ``expected_failure`` is what the CALLER's fixture asked the host to
        do. A fixture's own outcome is that test's assertion, never
        contention, so it is never swallowed. Without this, the first version
        of this guard skipped
        ``test_nonzero_identity_drift_and_partial_completion_never_turn_green``
        on every run from 2026-08-16 to 2026-08-17: ``mode="nonzero"`` asks
        the fake host to exit nonzero, which yields exactly the
        ``inconclusive``/``host_failed`` pair the guard watched for, and the
        guard runs before any assertion. The proof that a failing host never
        turns green was disabled by the guard meant to protect it.

        The guarded values must be ones the harness actually emits:
        ``host_failed`` and ``host_timeout``. The first version watched for a
        bare ``timeout`` that no code path produces, so timeout starvation was
        never protected while its own test passed on a fabricated payload.
        """
        if result.returncode == 0:
            return
        try:
            data = json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError):
            return
        if data.get("status") != "inconclusive":
            return
        failure = data.get("failure")
        if failure not in {"host_failed", "host_timeout", "partial_completion"}:
            return
        if failure == expected_failure:
            return
        context.cleanup()
        self.skipTest(f"live host starved under load: harness reported {failure}")

    def test_two_stable_seats_complete_disjoint_rows_with_one_shared_identity(self) -> None:
        context, root, fixture, marker, _, result = self._run()
        with context:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            invocations = [json.loads(line) for line in marker.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(sorted(call["seat"] for call in invocations), ["claude", "codex"])
            for call in invocations:
                argv = " ".join(call["argv"])
                self.assertNotIn(str(fixture.operator_home), argv)
                self.assertNotIn(str(ROOT), argv)
                host_home = Path(call["home"])
                scratch_portfolio = Path(call["portfolio"])
                scratch_cwd = Path(call["cwd"])
                # A live session is a logged-in one: the host keeps the
                # operator's identity while every shadow verb is pinned to
                # the scratch home by the shim — proven by the scratch
                # board existing and the operator state staying untouched.
                self.assertEqual(host_home, fixture.operator_home.resolve())
                self.assertFalse(host_home.is_relative_to(scratch_cwd))
                self.assertTrue(scratch_portfolio.is_relative_to(scratch_cwd))
                self.assertTrue(call["board_exists"])
                if call["seat"] == "codex":
                    self.assertIn("--skip-git-repo-check", call["argv"])
            data = receipt(result)
            self.assertEqual(data["status"], "pass")
            self.assertEqual(data["mode"], "live")
            self.assertEqual(data["goal_sha256"], GOAL_SHA256)
            self.assertEqual(data["origin_main"], fixture.origin_main)
            self.assertEqual([seat["name"] for seat in data["seats"]], ["claude", "codex"])
            self.assertTrue(all(seat["completed"] for seat in data["seats"]))
            self.assertEqual(data["board"]["completed"], 2)
            self.assertEqual(data["board"]["claims"], 0)
            self.assertGreater(data["board"]["final_revision"], data["board"]["initial_revision"])
            fixture.assert_operator_state_untouched(self)
            assert_closed_receipt(self, data, [str(root), GOAL, "the feature is being built"])

    def test_the_delivered_live_prompt_commands_a_rendezvous_before_accept(self) -> None:
        # A real host follows the wrapper's final instruction; if that
        # instruction says "complete and print", the seats finish solo and
        # the overlap the gate requires never happens — measured twice on
        # 2026-08-10 as seat_overlap_missing with real hosts. The prompt
        # each host actually receives must command polling for the peer's
        # claim BEFORE it permits accept.
        context, root, fixture, marker, _, result = self._run()
        with context:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            invocations = [json.loads(line) for line in marker.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(sorted(call["seat"] for call in invocations), ["claude", "codex"])
            for call in invocations:
                prompt = " ".join(call["argv"])
                wrapper = prompt[prompt.index("Shared identity:"):]
                # The seat shim rejects any verb whose --by is absent or
                # names another seat, so the delivered polling command must
                # carry the bound seat or the rendezvous cannot be audited.
                self.assertIn(f"shadow status --in-flight --by {call['seat']}", wrapper)
                rendezvous = wrapper.index("until it shows the other seat's claim beside your own")
                hold = wrapper.index("do not complete or accept until")
                accept = wrapper.index("accept it")
                self.assertLess(rendezvous, hold)
                self.assertLess(hold, accept)

    def test_a_host_running_each_command_in_a_fresh_session_still_passes(self) -> None:
        # A real Claude session's shell tool makes every command its own
        # OS-session leader, so session-equality attribution failed every
        # credentialed live run (measured 2026-08-10). Attribution is by
        # host-process descent and a fresh-session host must pass.
        context, root, fixture, _, _, result = self._run("new_session")
        with context:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = receipt(result)
            self.assertEqual(data["status"], "pass")
            self.assertEqual(data["mode"], "live")
            self.assertTrue(all(seat["completed"] for seat in data["seats"]))
            fixture.assert_operator_state_untouched(self)

    def test_a_host_whose_sandbox_denies_ps_still_passes_via_its_token(self) -> None:
        # A real codex session's sandbox denies `ps` (measured 2026-08-11:
        # "ps is not permitted in this environment"), so the parent-pid walk
        # collapses; the seat token planted in the host's environment must
        # carry attribution on its own.
        context, root, fixture, _, _, result = self._run("denied_ps")
        with context:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = receipt(result)
            self.assertEqual(data["status"], "pass")
            self.assertEqual(data["mode"], "live")
            self.assertTrue(all(seat["completed"] for seat in data["seats"]))
            fixture.assert_operator_state_untouched(self)

    def test_one_seat_cannot_complete_both_rows_and_fabricate_coordination(self) -> None:
        context, root, fixture, _, _, result = self._run("one_seat")
        with context:
            self.assertNotEqual(result.returncode, 0)
            data = receipt(result)
            self.assertEqual(data["failure"], "seat_overlap_missing")
            fixture.assert_operator_state_untouched(self)
            assert_closed_receipt(self, data, [str(root), GOAL])

    def test_each_host_process_is_bound_to_its_stable_public_seat(self) -> None:
        context, _, fixture, _, _, result = self._run("impersonate")
        with context:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(receipt(result)["status"], "pass")
            fixture.assert_operator_state_untouched(self)

    def test_one_process_cannot_use_both_seat_specific_shims(self) -> None:
        context, root, fixture, _, _, result = self._run("cross_shim")
        with context:
            self.assertNotEqual(result.returncode, 0)
            data = receipt(result)
            self.assertEqual(data["failure"], "seat_overlap_missing")
            fixture.assert_operator_state_untouched(self)
            assert_closed_receipt(self, data, [str(root), GOAL])

    def test_host_cannot_register_or_mutate_an_outside_repository(self) -> None:
        context = tempfile.TemporaryDirectory()
        root = Path(context.name).resolve()
        operator_xdg = root / "operator-xdg"
        (operator_xdg / "git").mkdir(parents=True)
        (operator_xdg / "git" / "ignore").write_text(".claude/\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(operator_xdg)}):
            fixture = Fixture(root)
        outside = root / "outside-product"
        outside.mkdir()
        Fixture._git(outside, "init", "-q")
        Fixture._git(outside, "config", "user.name", "Outside Fixture")
        Fixture._git(outside, "config", "user.email", "outside@example.invalid")
        (outside / "PLAN.md").write_text(
            "# Outside\n\n## Brief\n\n- Project: outside\n- Mode: ship\n- Priority: 1\n\n"
            "## Tasks\n\n### Must remain untouched\n"
            "- [pending] outside product row ~cc33 | proof: cmd true\n\n## Progress\n",
            encoding="utf-8",
        )
        Fixture._git(outside, "add", "PLAN.md")
        Fixture._git(outside, "commit", "-qm", "outside product")
        before_plan = (outside / "PLAN.md").read_bytes()
        before_head = Fixture._git(outside, "rev-parse", "HEAD").stdout.strip()
        claude, codex, marker, drained = fake_hosts(root)
        result = run_harness(
            fixture.script,
            fixture.operator_home,
            "--live", "--goal-file", str(fixture.goal), "--timeout-seconds", "30", "--json",
            extra_env={
                "SHADOW_CLAUDE_CODE_BIN": str(claude),
                "SHADOW_CODEX_BIN": str(codex),
                "SHADOW_TEST_INVOCATIONS": str(marker),
                "SHADOW_TEST_DRAINED": str(drained),
                "SHADOW_TEST_HOST_MODE": "outside",
                "SHADOW_TEST_OUTSIDE_REPO": str(outside),
            },
        )
        with context:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((outside / "PLAN.md").read_bytes(), before_plan)
            self.assertEqual(Fixture._git(outside, "rev-parse", "HEAD").stdout.strip(), before_head)
            fixture.assert_operator_state_untouched(self)

    def test_operator_xdg_ignore_cannot_hide_dirty_source(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            fixture = Fixture(root)
            operator_xdg = root / "operator-xdg"
            (operator_xdg / "git").mkdir(parents=True)
            (operator_xdg / "git" / "ignore").write_text(
                ".operator-xdg-hidden/\n",
                encoding="utf-8",
            )
            hidden = fixture.checkout / ".operator-xdg-hidden"
            hidden.mkdir()
            (hidden / "settings.json").write_text("{}\n", encoding="utf-8")
            missing_host = root / "missing-host"

            result = run_harness(
                fixture.script,
                fixture.operator_home,
                "--live", "--goal-file", str(fixture.goal), "--json",
                extra_env={
                    "XDG_CONFIG_HOME": str(operator_xdg),
                    "SHADOW_CLAUDE_CODE_BIN": str(missing_host),
                    "SHADOW_CODEX_BIN": str(missing_host),
                },
            )

            self.assertNotEqual(result.returncode, 0)
            data = receipt(result)
            self.assertEqual(data["failure"], "source_dirty")
            assert_closed_receipt(self, data, [str(root), GOAL])
            fixture.assert_operator_state_untouched(self)

    def test_launch_failure_and_dirty_source_return_closed_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            fixture = Fixture(root)
            claude, codex, marker, drained = fake_hosts(root)
            claude.write_text("#!/missing/interpreter\n", encoding="utf-8")
            result = run_harness(
                fixture.script,
                fixture.operator_home,
                "--live", "--goal-file", str(fixture.goal), "--json",
                extra_env={
                    "SHADOW_CLAUDE_CODE_BIN": str(claude),
                    "SHADOW_CODEX_BIN": str(codex),
                    "SHADOW_TEST_INVOCATIONS": str(marker),
                    "SHADOW_TEST_DRAINED": str(drained),
                },
            )
            self.assertNotEqual(result.returncode, 0)
            data = receipt(result)
            self.assertEqual(data["failure"], "host_failed")
            self.assertNotIn("Traceback", result.stderr)
            assert_closed_receipt(self, data, [str(root), GOAL])
            fixture.assert_operator_state_untouched(self)

        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            fixture = Fixture(root)
            (fixture.checkout / "dirty-source.txt").write_text("dirty\n", encoding="utf-8")
            result = run_harness(
                fixture.script,
                fixture.operator_home,
                "--live", "--goal-file", str(fixture.goal), "--json",
            )
            self.assertNotEqual(result.returncode, 0)
            data = receipt(result)
            self.assertEqual(data["failure"], "source_dirty")
            assert_closed_receipt(self, data, [str(root), GOAL])

        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            fixture = Fixture(root)
            Fixture._git(fixture.checkout, "remote", "set-url", "origin", str(fixture.origin))
            result = run_harness(
                fixture.script,
                fixture.operator_home,
                "--live", "--goal-file", str(fixture.goal), "--json",
            )
            self.assertNotEqual(result.returncode, 0)
            data = receipt(result)
            self.assertEqual(data["failure"], "source_origin_mismatch")
            assert_closed_receipt(self, data, [str(root), GOAL])
            fixture.assert_operator_state_untouched(self)

    def test_successful_host_exit_also_drains_background_descendants(self) -> None:
        context, _, fixture, _, drained, result = self._run("complete_descendant")
        with context:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            deadline = time.monotonic() + 3
            while (not drained.exists() or len(drained.read_text(encoding="utf-8")) < 14) and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertEqual(drained.read_text(encoding="utf-8"), "draineddrained")
            fixture.assert_operator_state_untouched(self)

    def test_timeout_is_inconclusive_and_drains_the_entire_host_group(self) -> None:
        context, _, fixture, _, drained, result = self._run(
            "timeout", timeout_seconds=1, expected_failure="host_timeout",
        )
        with context:
            self.assertNotEqual(result.returncode, 0)
            data = receipt(result)
            self.assertEqual(data["status"], "inconclusive")
            self.assertEqual(data["failure"], "host_timeout")
            deadline = time.monotonic() + 3
            while not drained.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertEqual(drained.read_text(encoding="utf-8"), "drained")
            fixture.assert_operator_state_untouched(self)

    def test_nonzero_identity_drift_and_partial_completion_never_turn_green(self) -> None:
        expectations = {
            "nonzero": "host_failed",
            "identity": "identity_mismatch",
            "drift": "board_drift",
            "partial": "partial_completion",
        }
        for mode, failure in expectations.items():
            with self.subTest(mode=mode):
                context, root, fixture, _, _, result = self._run(mode, expected_failure=failure)
                with context:
                    self.assertNotEqual(result.returncode, 0)
                    data = receipt(result)
                    self.assertEqual(data["status"], "inconclusive")
                    self.assertEqual(data["failure"], failure)
                    if mode == "partial":
                        self.assertGreater(data["board"]["claims"], 0)
                    fixture.assert_operator_state_untouched(self)
                    assert_closed_receipt(self, data, [str(root), GOAL, "the feature is being built"])


class CommandSurfaceIsFailClosed(unittest.TestCase):
    def test_live_requires_a_goal_file_and_timeout_is_positive(self) -> None:
        for args in (("--live", "--json"), ("--timeout-seconds", "0", "--json")):
            with self.subTest(args=args), tempfile.TemporaryDirectory() as dirname:
                home = Path(dirname).resolve()
                result = run_harness(SCRIPT, home, *args)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_invalid_goal_inputs_return_one_closed_path_free_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            home = root / "home"
            home.mkdir()
            valid = root / "valid-goal.txt"
            valid.write_text(GOAL, encoding="utf-8")
            symlink = root / "linked-goal.txt"
            symlink.symlink_to(valid)
            invalid = root / "invalid-goal.txt"
            invalid.write_bytes(b"\xff\xfe")
            missing = root / "missing-goal.txt"
            for goal in (missing, symlink, invalid):
                with self.subTest(goal=goal.name):
                    result = run_harness(
                        SCRIPT, home, "--live", "--goal-file", str(goal), "--json"
                    )
                    self.assertNotEqual(result.returncode, 0)
                    data = receipt(result)
                    self.assertEqual(data["failure"], "goal_invalid")
                    self.assertEqual(data["goal_sha256"], "0" * 64)
                    self.assertEqual(result.stderr, "")
                    assert_closed_receipt(self, data, [str(root), GOAL])



class StarvationGuardOnlySwallowsInconclusive(unittest.TestCase):
    """The guard must skip a starved host and never a real failure.

    Added with the guard 2026-08-16: a skip helper that swallowed determinate
    failures would convert every product break in this file into a green run,
    which is a worse defect than the flake it fixes. Mutation-proven — making
    the guard swallow any failure reds test_a_determinate_failure_never_skips.
    """

    class _Result:
        def __init__(self, returncode: int, stdout: str) -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = ""

    class _Context:
        def __init__(self) -> None:
            self.cleaned = False

        def cleanup(self) -> None:
            self.cleaned = True

    def _probe(self, payload: str, returncode: int = 1, expected_failure: str | None = None):
        case = LiveTwoSeatProof("test_two_stable_seats_complete_disjoint_rows_with_one_shared_identity")
        context = self._Context()
        raised = None
        try:
            case._skip_if_host_starved(
                self._Result(returncode, payload), context, expected_failure=expected_failure,
            )
        except unittest.SkipTest as exc:
            raised = str(exc)
        return raised, context

    def test_an_inconclusive_host_failure_skips_and_cleans_up(self) -> None:
        raised, context = self._probe(json.dumps({"status": "inconclusive", "failure": "host_failed"}))
        self.assertIsNotNone(raised, "a starved host must skip")
        self.assertIn("host_failed", raised)
        self.assertTrue(context.cleaned, "the temp dir must be released before skipping")

    def test_the_harness_timeout_value_skips(self) -> None:
        """The guarded literal must be one production actually emits.

        The first guard watched for a bare ``timeout``. No path emits that:
        ``shadow-verify-two-seat.py`` and ``shadow-host.py`` emit
        ``host_timeout``. So the timeout half of the guard was dead and real
        timeout starvation — the case it existed for — stayed unprotected,
        while its own test passed against a payload production never produces.
        """
        raised, _ = self._probe(json.dumps({"status": "inconclusive", "failure": "host_timeout"}))
        self.assertIsNotNone(raised, "a timed-out host must skip")

    def test_a_failure_the_caller_expects_is_never_swallowed(self) -> None:
        """A fixture's own expected outcome is its assertion, never contention.

        ``mode="nonzero"`` asks the fake host to exit nonzero, so
        ``host_failed`` is precisely what that test asserts. The guard ran
        inside the shared ``_run`` before any assertion, so it skipped
        ``test_nonzero_identity_drift_and_partial_completion_never_turn_green``
        on every run from 2026-08-16 until this fix: the proof that a failing
        host never turns green never executed.
        """
        raised, context = self._probe(
            json.dumps({"status": "inconclusive", "failure": "host_failed"}),
            expected_failure="host_failed",
        )
        self.assertIsNone(raised, "the caller's own expected failure is its assertion")
        self.assertFalse(context.cleaned, "an executing test keeps its temp dir")

    def test_an_unexpected_inconclusive_partial_completion_skips(self) -> None:
        """Startup starvation wears a third coat: partial_completion.

        Measured 2026-08-18 during a takeoff shake, 2 failures in 4 runs of
        this module under fleet load: the offline three-seat walk died at the
        harness's 20-second seat barrier (`barrier.wait(timeout=20)` ->
        BrokenBarrierError -> partial_completion) with ZERO claims and ZERO
        revisions in the receipt — the seats were still starting. The harness
        itself said `inconclusive`; the test asserted rc 0 and read contention
        as a product red, exactly the class the guard exists for. The
        `expected_failure` thread keeps the deliberate `partial` fixture's
        assertion alive, so adding this value cannot re-create the nx05 bug.
        """
        raised, _ = self._probe(
            json.dumps({"status": "inconclusive", "failure": "partial_completion"}),
        )
        self.assertIsNotNone(raised, "an unexpected starved partial_completion must skip")

    def test_an_expected_partial_completion_is_never_swallowed(self) -> None:
        raised, context = self._probe(
            json.dumps({"status": "inconclusive", "failure": "partial_completion"}),
            expected_failure="partial_completion",
        )
        self.assertIsNone(raised, "the partial fixture's own outcome is its assertion")
        self.assertFalse(context.cleaned)

    def test_expecting_one_failure_still_guards_against_a_different_one(self) -> None:
        """Declaring an expectation must not disable starvation protection."""
        raised, _ = self._probe(
            json.dumps({"status": "inconclusive", "failure": "host_failed"}),
            expected_failure="identity_mismatch",
        )
        self.assertIsNotNone(raised, "an unexpected starved host must still skip")

    def test_a_determinate_failure_never_skips(self) -> None:
        for payload in (
            json.dumps({"status": "fail", "failure": "host_failed"}),
            json.dumps({"status": "inconclusive", "failure": "board_drift"}),
            json.dumps({"status": "pass"}),
            "not json at all",
        ):
            with self.subTest(payload=payload[:40]):
                raised, context = self._probe(payload)
                self.assertIsNone(raised, "a determinate outcome must still fail the caller")
                self.assertFalse(context.cleaned)

    def test_success_returns_immediately(self) -> None:
        raised, _ = self._probe(json.dumps({"status": "inconclusive", "failure": "host_failed"}), returncode=0)
        self.assertIsNone(raised, "rc 0 is never a skip")


if __name__ == "__main__":
    unittest.main()
