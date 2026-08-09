"""Extension buckets: a declaration that resolves, never a store that drifts.

The owner's ask was "shadow will have buckets and the method open for
superpowers... as well as honcho... and the repo on install will default to
these and mark them as dependencies."

The npm-shaped reading of that dies on two shipped facts, and these tests pin
both. honcho is uninstallable BY LAW — `docs/reference/honcho.md` rules it "a
pattern Shadow implements, not a service Shadow installs" — so a slot that
installs its filler is self-contradictory for one of the three named buckets.
And M6 deleted the package manager on purpose, so an install-that-fetches
reverses a shipped decision.

So a bucket declares what the method assumes it can reach, and doctor derives
the answer at read time. Nothing is fetched, stamped, or cached.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "shadow-buckets.py"
SHADOW = ROOT / "bin" / "shadow"

_SPEC = importlib.util.spec_from_file_location("shadow_buckets", SCRIPT)
buckets = importlib.util.module_from_spec(_SPEC)
sys.modules["shadow_buckets"] = buckets
_SPEC.loader.exec_module(buckets)


def plugin(home: Path, name: str, version: str, manifest_name: str | None = None) -> None:
    path = home / ".claude" / "plugins" / "cache" / "market" / name / version / ".claude-plugin"
    path.mkdir(parents=True)
    (path / "plugin.json").write_text(
        json.dumps({"name": manifest_name or name, "version": version}), encoding="utf-8")


def skill(home: Path, name: str) -> None:
    path = home / ".claude" / "skills" / name
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")


class TheDeclaration(unittest.TestCase):
    def test_every_line_parses_in_fixed_order(self) -> None:
        found = buckets.declared()
        self.assertTrue(found, "no buckets parsed from docs/reference/buckets.md")
        for bucket in found:
            self.assertIn(bucket["kind"], buckets.KINDS)
            for field in ("name", "default", "fills", "absent"):
                self.assertTrue(bucket[field].strip(), f"{bucket['name']}: empty {field}")

    def test_the_three_named_buckets_ship(self) -> None:
        # Dropping one becomes a deliberate test edit, never a silent removal.
        names = {b["name"] for b in buckets.declared()}
        self.assertEqual(names, {"superpowers", "honcho", "taste"})

    def test_names_are_unique(self) -> None:
        names = [b["name"] for b in buckets.declared()]
        self.assertEqual(len(names), len(set(names)))

    def test_nothing_stores_resolved_state(self) -> None:
        # The whole Boundaries argument: a file that stamps nothing cannot
        # drift from reality. If a version, timestamp, or installed-flag ever
        # appears in the declaration, it has become the thing plugin managers
        # keep and Shadow bans.
        # Scan the DECLARATION lines only. The prose deliberately names these
        # keys while explaining why they are absent, and a scan of the whole
        # file flagged its own explanation — a guard that fires on the sentence
        # describing the rule is noise, not enforcement.
        lines = [
            line for line in (ROOT / "docs" / "reference" / "buckets.md")
            .read_text(encoding="utf-8").splitlines()
            if line.startswith("- bucket ")
        ]
        self.assertTrue(lines)
        for line in lines:
            for stamped in ("installed:", "last_checked", "installedAt", "lastUpdated",
                            "version:", "resolved:"):
                self.assertNotIn(stamped, line, f"a bucket line stores resolved state: {line[:60]}")


class AbsentNeverFails(unittest.TestCase):
    """~w1re's DoD runs `shadow doctor` under a scratch HOME and expects exit 0.

    A required tier would fail the very milestone that introduces buckets, so
    every shipped bucket is optional and absence is always a warning.
    """

    def test_an_empty_home_warns_and_the_command_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(SCRIPT)], capture_output=True, text=True,
                check=False, env={**buckets.os.environ, "HOME": tmp},
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("[WARN] bucket: superpowers", result.stdout)
            self.assertIn("[WARN] bucket: taste", result.stdout)
            self.assertNotIn("[FAIL]", result.stdout)

    def test_every_warning_carries_its_next_move(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            for check, declaration in zip(buckets.checks(home), buckets.declared()):
                if check["state"] == "warn":
                    self.assertIn(declaration["absent"], check["detail"])


class KindIsTheCheck(unittest.TestCase):
    def _state(self, name: str, home: Path) -> tuple[str, str]:
        bucket = next(b for b in buckets.declared() if b["name"] == name)
        return buckets.resolve(bucket, home)

    def test_a_present_pack_reports_its_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            plugin(home, "superpowers", "9.9.9")
            state, detail = self._state("superpowers", home)
            self.assertEqual(state, "pass")
            self.assertIn("9.9.9", detail)

    def test_a_pack_answering_to_another_name_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            plugin(home, "superpowers", "1.0.0", manifest_name="notsuperpowers")
            state, detail = self._state("superpowers", home)
            self.assertEqual(state, "fail")
            self.assertIn("notsuperpowers", detail)

    def test_a_mounted_skill_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            skill(home, "taste")
            self.assertEqual(self._state("taste", home)[0], "pass")


class TheBuiltinRefusesAnInstalledNamesake(unittest.TestCase):
    """honcho's ruling, made mechanical.

    `docs/reference/honcho.md` says honcho is a pattern Shadow implements and
    never a service Shadow installs. Prose nobody re-reads cannot enforce that.
    This bucket's check is a NEGATIVE, and it is the design's proof of honesty:
    the one bucket that can never be "installed" is the one whose check fires
    when someone installs it.
    """

    def test_a_clean_machine_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bucket = next(b for b in buckets.declared() if b["name"] == "honcho")
            state, detail = buckets.resolve(bucket, Path(tmp))
            self.assertEqual(state, "pass")
            self.assertIn("ruling intact", detail)

    def test_an_installed_skill_named_honcho_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            skill(home, "honcho")
            bucket = next(b for b in buckets.declared() if b["name"] == "honcho")
            state, detail = buckets.resolve(bucket, home)
            self.assertEqual(state, "fail")
            self.assertIn("never a service", detail)

    def test_an_installed_plugin_named_honcho_also_fails(self) -> None:
        # Both surfaces, not just the one that was easy to check.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".claude" / "plugins" / "cache" / "market" / "honcho").mkdir(parents=True)
            bucket = next(b for b in buckets.declared() if b["name"] == "honcho")
            self.assertEqual(buckets.resolve(bucket, home)[0], "fail")

    def test_it_is_never_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bucket = next(b for b in buckets.declared() if b["name"] == "honcho")
            self.assertNotEqual(buckets.resolve(bucket, Path(tmp))[0], "warn")


class Overrides(unittest.TestCase):
    def _with(self, variable: str, value: str, name: str) -> tuple[str, str]:
        bucket = next(b for b in buckets.declared() if b["name"] == name)
        buckets.os.environ[variable] = value
        try:
            with tempfile.TemporaryDirectory() as tmp:
                return buckets.resolve(bucket, Path(tmp))
        finally:
            del buckets.os.environ[variable]

    def test_off_is_a_deliberate_emptiness_not_a_warning(self) -> None:
        state, detail = self._with("SHADOW_BUCKET_TASTE", "off", "taste")
        self.assertEqual(state, "pass")
        self.assertIn("deliberate", detail)

    def test_a_path_that_exists_binds(self) -> None:
        with tempfile.TemporaryDirectory() as real:
            self.assertEqual(self._with("SHADOW_BUCKET_TASTE", real, "taste")[0], "pass")

    def test_a_path_that_does_not_exist_fails_loudly(self) -> None:
        state, _ = self._with("SHADOW_BUCKET_TASTE", "/nowhere/at/all", "taste")
        self.assertEqual(state, "fail")


class WiredIntoTheProduct(unittest.TestCase):
    def test_doctor_reports_one_check_per_bucket(self) -> None:
        result = subprocess.run([str(SHADOW), "doctor", "--json"],
                                capture_output=True, text=True, check=False)
        names = {c["name"] for c in json.loads(result.stdout)["checks"]}
        for bucket in buckets.declared():
            self.assertIn(f"bucket: {bucket['name']}", names)

    def test_the_verb_and_its_help_exist(self) -> None:
        for argv in (["buckets"], ["help", "buckets"]):
            result = subprocess.run([str(SHADOW), *argv], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout.strip())

    def test_no_plan_verb_reads_the_declaration(self) -> None:
        # A bucket holds no rows, no proof, no status. If throw/accept/amp/status
        # ever read it, it has become a second queue.
        for name in ("shadow-throw.py", "shadow-accept.py", "shadow-amp.py", "shadow-status.py"):
            source = (ROOT / "scripts" / name).read_text(encoding="utf-8")
            self.assertNotIn("buckets", source, f"{name} reads the bucket declaration")


if __name__ == "__main__":
    unittest.main()
