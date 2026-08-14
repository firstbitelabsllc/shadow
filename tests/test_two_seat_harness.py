"""Black-box proof for the sealed two-seat acceptance harness.

The harness is valuable only if its cheap default cannot spend host quota and
its live tier proves the same behavior without touching the operator's HOME or
portfolio.  The native hosts below are deterministic test doubles, but they
drive the real Shadow status, throw, and accept verbs against the disposable
portfolio minted by the production harness.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import time
import unittest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "shadow-verify-two-seat.py"
PYTHON = ROOT / "scripts" / "shadow-python.sh"
GOAL = """Outcome: prove two seats share one root board.
Authority: the scratch repositories and board created by the sealed harness.
Resume: claim the highest reachable unclaimed checkpoint with your stable seat.
Proof: run the row proof and accept it; do not leave an orphan claim.
"""
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
        result = subprocess.run(
            ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False
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
    def _run(self, mode: str = "complete", timeout_seconds: int = 30):
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
        return context, root, fixture, marker, drained, result

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
            "--live", "--goal-file", str(fixture.goal), "--timeout-seconds", "10", "--json",
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
        context, _, fixture, _, drained, result = self._run("timeout", timeout_seconds=1)
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
                context, root, fixture, _, _, result = self._run(mode)
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


if __name__ == "__main__":
    unittest.main()
