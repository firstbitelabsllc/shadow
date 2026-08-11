"""The standing goal is static, has exactly one source, and drifts loudly.

Before this landed the block existed only as prose in a doc: no command emitted
it, and no executable read a host's instruction file. Three semantic mutations
of the block — a renamed flag, a renamed verb, and the proxy stance inverted to
"ask the person which project" — each passed the entire suite and shipped. A
promise nothing checks is a promise that decays silently.
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
SHADOW = ROOT / "bin" / "shadow"
DOC = ROOT / "docs" / "reference" / "host-integration.md"

SPEC = importlib.util.spec_from_file_location("shadow_doctor", ROOT / "scripts" / "shadow-doctor.py")
doctor = importlib.util.module_from_spec(SPEC)
sys.modules["shadow_doctor"] = doctor
SPEC.loader.exec_module(doctor)


def emit() -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(SHADOW), "goal"], capture_output=True, text=True, check=False)


class GoalVerb(unittest.TestCase):
    def test_the_verb_emits_the_block(self) -> None:
        result = emit()
        self.assertEqual(result.returncode, 0, result.stderr)
        first, *rest = result.stdout.splitlines()
        self.assertTrue(first.startswith("## Shadow "), first)
        self.assertTrue(rest, "block has no body")

    def test_it_carries_every_load_bearing_clause(self) -> None:
        # Each of these is a decision a cold host would otherwise get wrong.
        text = emit().stdout
        for clause in (
            "~/.shadow",                      # the computer coordination authority
            "PLAN.md",                        # entity detail and proof authority
            "shadow status --by",             # stable-seat cold resume
            "shadow amp",                     # owned-checkpoint projection
            'Never ask "which project?"',     # the proxy stance
            "shadow accept --by",             # the only cmd-proof flip path
            "mint the successor",             # goal chaining
            "shadow throw",                   # dispatch law: nothing leaves unclaimed
            "not a death certificate",        # and the reading that broke it twice
            "draining every reachable checkpoint", # one checkpoint never caps the goal
            "path-disjoint claims",            # independent lanes rise together
            "nightly",                        # deterministic expensive-proof train
            "accepted-change pressure",       # early train uses accepted trunk evidence
            "stranger-install",               # CI proves only its bounded install surface
            "never infer those from CI",      # merge/deploy/live remain separate receipts
            "native host plans",              # disposable UI, never authority
        ):
            self.assertIn(clause, text, f"standing goal lost: {clause}")

    def test_it_stops_at_the_fence_and_leaks_no_prose(self) -> None:
        # This asserted `"Fifteen lines" not in text` until the block grew and
        # the doc said "Nineteen" — the assertion stayed green while checking a
        # string that no longer existed anywhere. Pin prose that survives an
        # edit to the count, and prove the doc still contains it.
        text = emit().stdout
        after_the_fence = "A host that loads only this block"
        self.assertIn(after_the_fence, DOC.read_text(encoding="utf-8"))
        self.assertNotIn("```", text)
        self.assertNotIn(after_the_fence, text)
        self.assertNotIn("## 3.", text)                  # the next heading

    def test_the_doc_is_the_only_copy(self) -> None:
        # A second copy anywhere is a copy that drifts. The block's first line
        # must appear in exactly one tracked file: the doc it is read from.
        anchor = emit().stdout.splitlines()[0]
        tracked = subprocess.run(
            ["git", "-C", str(ROOT), "grep", "-l", "--fixed-strings", anchor],
            capture_output=True, text=True, check=False,
        ).stdout.split()
        self.assertEqual(
            tracked, [str(DOC.relative_to(ROOT))],
            "the standing goal exists in more than one place; keep the doc as the only source",
        )

    def test_the_extraction_anchor_is_ascii(self) -> None:
        # The heading contains an em-dash. Anchoring on it would make the
        # pattern depend on the runner's awk locale, so bin/shadow anchors on
        # the ASCII prefix only.
        dispatch = SHADOW.read_text(encoding="utf-8")
        self.assertIn("/^## Shadow /{f=1}", dispatch)
        self.assertNotIn("/^## Shadow —", dispatch)

    def test_doctor_and_the_verb_read_the_same_block(self) -> None:
        # Two readers, one text: if they disagree, doctor can pass while the
        # thing a person pastes is different.
        self.assertEqual(doctor.standing_goal(), emit().stdout.strip())


class DoctorReportsDrift(unittest.TestCase):
    """Absent, current, and stale must be three distinguishable answers."""

    def _run(self, contents: str | None) -> tuple[str, str]:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".claude").mkdir()
            (home / ".codex").mkdir()
            if contents is not None:
                canonical = home / "LOCAL_AGENT.md"
                canonical.write_text(contents, encoding="utf-8")
                (home / ".claude" / "CLAUDE.md").symlink_to(canonical)
            original = Path.home
            Path.home = staticmethod(lambda: home)          # type: ignore[assignment]
            try:
                results = {c["name"]: c for c in doctor.host_goal_checks()}
            finally:
                Path.home = original                        # type: ignore[assignment]
        claude = results["standing goal: claude-code"]
        return claude["state"], claude["detail"]

    def test_a_missing_host_file_warns_and_never_fails(self) -> None:
        # The host simply is not configured. Not this install's fault.
        state, detail = self._run(None)
        self.assertEqual(state, "warn")
        self.assertIn("no host instruction file", detail)
        self.assertIn("shadow goal", detail)         # every warning is actionable

    def test_rules_without_the_block_warn_differently(self) -> None:
        # A distinct situation from the above: the person has host rules, they
        # just never pasted this. Same severity, different fix.
        state, detail = self._run("# my rules\n\nno shadow here\n")
        self.assertEqual(state, "warn")
        self.assertIn("not pasted", detail)

    def test_current_passes(self) -> None:
        state, _ = self._run("# my rules\n\n" + doctor.standing_goal() + "\n\nmore rules\n")
        self.assertEqual(state, "pass")

    def test_an_edited_copy_fails_and_says_how_to_refresh(self) -> None:
        # The exact failure that shipped three times: the block is present but
        # its meaning was changed. Absence is a warning; drift is a failure.
        mutated = doctor.standing_goal().replace("shadow accept", "shadow flip")
        state, detail = self._run("# my rules\n\n" + mutated + "\n")
        self.assertEqual(state, "fail")
        self.assertIn("shadow goal", detail)

    def test_the_stance_inversion_is_caught(self) -> None:
        mutated = doctor.standing_goal().replace(
            'Never ask "which project?"', 'Ask the person which project'
        )
        state, _ = self._run("# my rules\n\n" + mutated + "\n")
        self.assertEqual(state, "fail")

    def test_two_copies_fail_even_though_one_is_current(self) -> None:
        # The false green a stranger hit by following doctor's OWN remedy. The
        # old advice was `shadow goal >> <file>`; appending left a stale block
        # above a fresh one, `block in text` matched the fresh copy, doctor said
        # "current" — and the host reads the stale one first.
        stale = doctor.standing_goal().replace("shadow accept", "shadow flip")
        state, detail = self._run(f"# my rules\n\n{stale}\n\n{doctor.standing_goal()}\n")
        self.assertEqual(state, "fail", "a stale copy above a fresh one passed as current")
        self.assertIn("2 copies", detail)
        self.assertIn("reads the first one", detail)

    def test_no_remedy_tells_you_to_append(self) -> None:
        # Every remedy must be replace-shaped. `>>` is what created the bug.
        for contents in (None, "# rules only\n", doctor.standing_goal().replace("Outcome", "Changed")):
            _, detail = self._run(contents)
            self.assertNotIn(">>", detail)
            self.assertIn("shadow goal --install", detail)

    def test_no_private_home_path_reaches_the_detail_text(self) -> None:
        # The public locator makes wiring visible without leaking the temp HOME.
        for contents in (None, doctor.standing_goal(), "## Shadow — edited\n"):
            _, detail = self._run(contents)
            self.assertNotIn("/private/", detail)
            self.assertNotIn("/Users/", detail)
            self.assertNotIn("/var/", detail)


class HostDirectiveOriginIsReported(unittest.TestCase):
    def test_each_supported_file_names_the_file_its_host_actually_reads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            canonical = home / "LOCAL_AGENT.md"
            canonical.write_text(doctor.standing_goal() + "\n", encoding="utf-8")
            for directory, name in ((".claude", "CLAUDE.md"), (".codex", "AGENTS.md")):
                host_dir = home / directory
                host_dir.mkdir()
                (host_dir / name).symlink_to(canonical)
            original = Path.home
            Path.home = staticmethod(lambda: home)          # type: ignore[assignment]
            try:
                results = {item["name"]: item for item in doctor.host_goal_checks()}
            finally:
                Path.home = original                        # type: ignore[assignment]

        for label in ("claude-code", "codex"):
            item = results[f"standing goal: {label}"]
            self.assertEqual(item["state"], "pass")
            self.assertEqual(item["resolved"], "~/LOCAL_AGENT.md")
            self.assertIn("reads ~/LOCAL_AGENT.md", item["detail"])

    def test_a_broken_link_names_its_intended_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            broken_target = home / "missing-canonical.md"
            claude = home / ".claude"
            claude.mkdir()
            (claude / "CLAUDE.md").symlink_to(broken_target)
            original = Path.home
            Path.home = staticmethod(lambda: home)          # type: ignore[assignment]
            try:
                results = {item["name"]: item for item in doctor.host_goal_checks()}
            finally:
                Path.home = original                        # type: ignore[assignment]

        item = results["standing goal: claude-code"]
        self.assertEqual(item["state"], "fail")
        self.assertEqual(item["resolved"], "~/missing-canonical.md")
        self.assertIn("broken host instruction link", item["detail"])

    def test_copies_and_split_links_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            for directory, name in ((".claude", "CLAUDE.md"), (".codex", "AGENTS.md")):
                host_dir = home / directory
                host_dir.mkdir()
                (host_dir / name).write_text(doctor.standing_goal() + "\n", encoding="utf-8")
            original = Path.home
            Path.home = staticmethod(lambda: home)          # type: ignore[assignment]
            try:
                copies = doctor.host_goal_checks()
                for item, target_name in zip(copies, ("claude.md", "codex.md")):
                    Path(item["path"].replace("~/", f"{home}/")).unlink()
                    target = home / target_name
                    target.write_text(doctor.standing_goal() + "\n", encoding="utf-8")
                    Path(item["path"].replace("~/", f"{home}/")).symlink_to(target)
                split = doctor.host_goal_checks()
            finally:
                Path.home = original                        # type: ignore[assignment]

        self.assertTrue(all(item["state"] == "warn" for item in copies))
        self.assertTrue(all("not a symlink" in item["detail"] for item in copies))
        self.assertTrue(all(item["state"] == "warn" for item in split))
        self.assertTrue(all("resolve to different targets" in item["detail"] for item in split))

    def test_an_outside_home_target_is_failed_and_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            home = Path(tmp)
            target = Path(outside) / "private-operator" / "canonical.md"
            target.parent.mkdir()
            target.write_text(doctor.standing_goal() + "\n", encoding="utf-8")
            for directory, name in ((".claude", "CLAUDE.md"), (".codex", "AGENTS.md")):
                host_dir = home / directory
                host_dir.mkdir()
                (host_dir / name).symlink_to(target)
            original = Path.home
            Path.home = staticmethod(lambda: home)          # type: ignore[assignment]
            try:
                results = doctor.host_goal_checks()
            finally:
                Path.home = original                        # type: ignore[assignment]

        self.assertTrue(all(item["state"] == "fail" for item in results))
        rendered = json.dumps(results, sort_keys=True)
        self.assertNotIn(str(target), rendered)
        self.assertNotIn("private-operator", rendered)
        self.assertIn("outside-home@", rendered)


if __name__ == "__main__":
    unittest.main()
