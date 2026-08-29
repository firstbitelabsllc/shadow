"""Extension slots: a declaration that resolves, never a store that drifts.

The owner's ask (2026-08-11) was "shadow will have buckets and the method open for
superpowers... and the repo on install will default to these and mark them as
dependencies."

The npm-shaped reading of that dies on a shipped fact these tests pin: M6
deleted the package manager on purpose, so an install-that-fetches reverses a
shipped decision.

So a slot declares what the method assumes it can reach, and doctor derives
the answer at read time. Nothing is fetched, stamped, or cached — and no slot
asserts anything about tooling Shadow does not itself call. Renamed bucket →
slot 2026-08-15 by owner verdict. The one-train buckets alias and
SHADOW_BUCKET_ fallback were deleted in ~nx01.
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
SCRIPT = ROOT / "scripts" / "shadow-slots.py"
SHADOW = ROOT / "bin" / "shadow"

_SPEC = importlib.util.spec_from_file_location("shadow_slots", SCRIPT)
slots = importlib.util.module_from_spec(_SPEC)
sys.modules["shadow_slots"] = slots
_SPEC.loader.exec_module(slots)


def skill(home: Path, name: str) -> None:
    path = home / ".claude" / "skills" / name
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")


class TheDeclaration(unittest.TestCase):
    def test_every_line_parses_in_fixed_order(self) -> None:
        found = slots.declared()
        self.assertTrue(found, "no slots parsed from docs/reference/slots.md")
        for slot in found:
            self.assertIn(slot["kind"], slots.KINDS)
            for field in ("name", "default", "fills", "absent"):
                self.assertTrue(slot[field].strip(), f"{slot['name']}: empty {field}")

    def test_the_two_named_slots_ship(self) -> None:
        # Dropping or adding one becomes a deliberate test edit, never a
        # silent removal. Set cut to {memory, taste} 2026-08-15 by owner
        # verdict: superpowers' delegation guard is amp core and never
        # depended on the declaration; future's pre-mortem timing is
        # deliberately gone; explain's remit moved into the taste binding;
        # memory added as routed recall — a lead, never authority.
        names = {s["name"] for s in slots.declared()}
        self.assertEqual(names, {"memory", "taste"})

    def test_names_are_unique(self) -> None:
        names = [s["name"] for s in slots.declared()]
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
            line for line in (ROOT / "docs" / "reference" / "slots.md")
            .read_text(encoding="utf-8").splitlines()
            if line.startswith("- slot ")
        ]
        self.assertTrue(lines)
        for line in lines:
            for stamped in ("installed:", "last_checked", "installedAt", "lastUpdated",
                            "version:", "resolved:"):
                self.assertNotIn(stamped, line, f"a slot line stores resolved state: {line[:60]}")


class AbsentNeverFails(unittest.TestCase):
    """~w1re's DoD runs `shadow doctor` under a scratch HOME and expects exit 0.

    A required tier would fail the very milestone that introduces slots, so
    every shipped slot is optional and absence is always a warning.
    """

    def test_an_empty_home_warns_and_the_command_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(SCRIPT)], capture_output=True, text=True,
                check=False, env={**slots.os.environ, "HOME": tmp},
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("[WARN] slot: memory", result.stdout)
            self.assertIn("[WARN] slot: taste", result.stdout)
            self.assertNotIn("[FAIL]", result.stdout)

    def test_every_warning_carries_its_next_move(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            for check, declaration in zip(slots.checks(home), slots.declared()):
                if check["state"] == "warn":
                    self.assertIn(declaration["absent"], check["detail"])


class KindIsTheCheck(unittest.TestCase):
    def _state(self, name: str, home: Path) -> tuple[str, str]:
        slot = next(s for s in slots.declared() if s["name"] == name)
        return slots.resolve(slot, home)

    # Pack-kind resolution died with the superpowers row; ~nx01 removed
    # the leftover _resolve_pack.

    def test_a_mounted_skill_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            skill(home, "taste")
            self.assertEqual(self._state("taste", home)[0], "pass")

    def test_the_memory_routing_file_is_an_ordinary_skill_mount(self) -> None:
        # The routing file IS the mounted skill; existence-only, no schema.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self.assertEqual(self._state("memory", home)[0], "warn")
            skill(home, "memory")
            self.assertEqual(self._state("memory", home)[0], "pass")


class NoSlotPolicesUnrelatedUserTooling(unittest.TestCase):
    """A slot asks only whether Shadow can reach a capability it uses.

    A `builtin` kind once carried a standing ruling that nothing named honcho
    should ever be installed, and failed doctor when it found one. That check
    read a person's own skill roots and went red over software Shadow does not
    call — which is Shadow policing configuration it does not own. Measured
    2026-08-12: `_installed_namesake` used `.exists()`, not `.is_dir()`, so a
    single zero-byte file named honcho in any of three roots hard-failed the
    CLI on any machine.

    These assertions are the deleted check, inverted. They fail if the
    overreach ever returns.
    """

    NAMES = ("honcho", "mem0", "letta")

    def _all_states(self, home: Path) -> list[str]:
        return [slots.resolve(s, home)[0] for s in slots.declared()]

    def test_no_slot_is_named_for_a_vendor(self) -> None:
        # memory is a capability Shadow reaches for (2026-08-15 owner
        # verdict); a vendor name (honcho, mem0, letta, ...) as a slot name
        # would be Shadow policing or endorsing software it does not use.
        names = {s["name"] for s in slots.declared()}
        self.assertFalse(names & set(self.NAMES))

    def test_an_installed_namesake_directory_does_not_make_shadow_red(self) -> None:
        for name in self.NAMES:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                home = Path(tmp)
                skill(home, name)
                self.assertNotIn("fail", self._all_states(home))

    def test_a_bare_namesake_file_does_not_make_shadow_red(self) -> None:
        # The measured shape of the old defect: `.exists()`, not `.is_dir()`.
        for root in slots.SKILL_ROOTS:
            for name in self.NAMES:
                with self.subTest(root=root, name=name), tempfile.TemporaryDirectory() as tmp:
                    home = Path(tmp)
                    (home / root).mkdir(parents=True, exist_ok=True)
                    (home / root / name).write_text("", encoding="utf-8")
                    self.assertNotIn("fail", self._all_states(home))

    def test_an_installed_namesake_plugin_does_not_make_shadow_red(self) -> None:
        for name in self.NAMES:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                home = Path(tmp)
                (home / ".claude" / "plugins" / "cache" / "market" / name).mkdir(parents=True)
                self.assertNotIn("fail", self._all_states(home))


class Overrides(unittest.TestCase):
    def _with(self, variable: str, value: str, name: str) -> tuple[str, str]:
        slot = next(s for s in slots.declared() if s["name"] == name)
        slots.os.environ[variable] = value
        try:
            with tempfile.TemporaryDirectory() as tmp:
                return slots.resolve(slot, Path(tmp))
        finally:
            del slots.os.environ[variable]

    def test_off_is_a_deliberate_emptiness_not_a_warning(self) -> None:
        state, detail = self._with("SHADOW_SLOT_TASTE", "off", "taste")
        self.assertEqual(state, "pass")
        self.assertIn("deliberate", detail)

    def test_a_path_that_exists_binds(self) -> None:
        with tempfile.TemporaryDirectory() as real:
            self.assertEqual(self._with("SHADOW_SLOT_TASTE", real, "taste")[0], "pass")

    def test_a_path_that_does_not_exist_fails_loudly(self) -> None:
        state, _ = self._with("SHADOW_SLOT_TASTE", "/nowhere/at/all", "taste")
        self.assertEqual(state, "fail")


class WiredIntoTheProduct(unittest.TestCase):
    def test_doctor_reports_one_check_per_slot(self) -> None:
        result = subprocess.run([str(SHADOW), "doctor", "--json"],
                                capture_output=True, text=True, check=False)
        names = {c["name"] for c in json.loads(result.stdout)["checks"]}
        for slot in slots.declared():
            self.assertIn(f"slot: {slot['name']}", names)

    def test_the_verb_and_its_help_exist(self) -> None:
        for argv in (["slots"], ["help", "slots"]):
            result = subprocess.run([str(SHADOW), *argv], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout.strip())

    def test_the_json_mode_is_machine_readable(self) -> None:
        result = subprocess.run(
            [str(SHADOW), "slots", "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema"], "shadow.slots.v1")
        self.assertEqual(
            {check["name"] for check in payload["checks"]},
            {f"slot: {slot['name']}" for slot in slots.declared()},
        )

    def test_only_amp_reads_the_declaration_and_never_as_coordination(self) -> None:
        # A slot holds no rows, claims, proof, or status. Amp may resolve a
        # milestone's explicit tools into an optional handoff annotation; the
        # coordination verbs must never treat the declaration as a queue.
        for name in ("shadow-throw.py", "shadow-accept.py", "shadow-status.py"):
            source = (ROOT / "scripts" / name).read_text(encoding="utf-8")
            self.assertNotIn("slots", source, f"{name} reads the slot declaration")
            # Branch B window: the retired string must not creep back either.
            self.assertNotIn("buckets", source, f"{name} reads the retired bucket declaration")
        amp_source = (ROOT / "scripts" / "shadow-amp.py").read_text(encoding="utf-8")
        self.assertIn("capability_block", amp_source)
        self.assertNotIn("write_text", amp_source)



class RetiredBucketCompatIsGone(unittest.TestCase):
    def test_the_old_verb_is_unknown(self) -> None:
        result = subprocess.run([str(SHADOW), "buckets"], capture_output=True, text=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("buckets is now slots", result.stderr)

    def test_the_old_env_name_does_not_bind(self) -> None:
        slot = next(s for s in slots.declared() if s["name"] == "taste")
        slots.os.environ["SHADOW_BUCKET_TASTE"] = "off"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                state, detail = slots.resolve(slot, Path(tmp))
        finally:
            del slots.os.environ["SHADOW_BUCKET_TASTE"]
        self.assertEqual(state, "warn")
        self.assertNotIn("SHADOW_BUCKET_TASTE", detail)


if __name__ == "__main__":
    unittest.main()
