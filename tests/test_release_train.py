"""Release train windows and measured pressure produce one deterministic answer."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("shadow_ci_release", ROOT / "scripts" / "shadow-ci.py")
ci = importlib.util.module_from_spec(SPEC)
sys.modules["shadow_ci_release"] = ci
SPEC.loader.exec_module(ci)


def pressure(**overrides: str) -> dict[str, str]:
    values = {
        "ACCEPTED_CHANGE_COUNT": "1",
        "OLDEST_ACCEPTED_CHANGE_HOURS": "1",
        "SEVERITY": "none",
        "RELEASE_RISK": "none",
    }
    values.update(overrides)
    return values


class ReleaseTrainTriggersAreDeterministic(unittest.TestCase):
    def test_no_accepted_change_never_launches_an_empty_train(self) -> None:
        run, reason = ci.pressure_decision(
            pressure(ACCEPTED_CHANGE_COUNT="0", SEVERITY="critical")
        )
        self.assertFalse(run)
        self.assertIn("no accepted trunk change", reason)

    def test_each_versioned_pressure_dimension_can_trigger_early(self) -> None:
        cases = (
            pressure(ACCEPTED_CHANGE_COUNT="8"),
            pressure(OLDEST_ACCEPTED_CHANGE_HOURS="24"),
            pressure(SEVERITY="high"),
            pressure(RELEASE_RISK="high"),
        )
        for values in cases:
            with self.subTest(values=values):
                first = ci.pressure_decision(values)
                self.assertTrue(first[0])
                self.assertEqual(first, ci.pressure_decision(values))

    def test_pressure_below_every_threshold_waits_for_the_nightly_window(self) -> None:
        run, reason = ci.pressure_decision(pressure())
        self.assertFalse(run)
        self.assertIn("below", reason)

    def test_invalid_measurements_fail_loudly(self) -> None:
        for values in (
            pressure(ACCEPTED_CHANGE_COUNT="eight"),
            pressure(OLDEST_ACCEPTED_CHANGE_HOURS="-1"),
            pressure(SEVERITY="urgent"),
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                ci.pressure_decision(values)

    def test_first_window_runs_and_second_window_is_explicitly_gated(self) -> None:
        first = ci.event_plan({"EVENT_NAME": "schedule", "EVENT_SCHEDULE": ci.FIRST_WINDOW})
        self.assertTrue(first["full_gauntlet"])
        off = ci.event_plan({
            "EVENT_NAME": "schedule", "EVENT_SCHEDULE": ci.SECOND_WINDOW, "TWICE_DAILY": "0",
        })
        on = ci.event_plan({
            "EVENT_NAME": "schedule", "EVENT_SCHEDULE": ci.SECOND_WINDOW, "TWICE_DAILY": "1",
        })
        self.assertFalse(off["run_checks"])
        self.assertTrue(on["full_gauntlet"])

    def test_three_hour_probe_measures_pressure_instead_of_waiting_for_input(self) -> None:
        plan = ci.event_plan(
            {"EVENT_NAME": "schedule", "EVENT_SCHEDULE": ci.PRESSURE_WINDOW},
            pressure(ACCEPTED_CHANGE_COUNT="8"),
        )
        self.assertTrue(plan["full_gauntlet"])
        self.assertIn("automatic pressure probe", plan["reason"])

    def test_repository_pressure_counts_accepted_changes_since_the_release_tag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "T"], check=True)
            env = {**os.environ, "GIT_AUTHOR_DATE": "2026-08-10T00:00:00Z", "GIT_COMMITTER_DATE": "2026-08-10T00:00:00Z"}
            (repo / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "release"], env=env, check=True)
            subprocess.run(["git", "-C", str(repo), "tag", "v1.0.0"], check=True)
            for index, name in enumerate(("feature.txt", "install.sh"), 1):
                (repo / name).write_text(f"{index}\n", encoding="utf-8")
                subprocess.run(["git", "-C", str(repo), "add", name], check=True)
                subprocess.run(["git", "-C", str(repo), "commit", "-qm", f"feature {index}"], env=env, check=True)
            measured = ci.repository_pressure(repo, now=1786352400)
        self.assertEqual(measured["ACCEPTED_CHANGE_COUNT"], "2")
        self.assertGreaterEqual(int(measured["OLDEST_ACCEPTED_CHANGE_HOURS"]), 1)
        self.assertEqual(measured["RELEASE_RISK"], "high")

    def test_manual_run_consumes_explicit_measurements_only(self) -> None:
        event = {
            "EVENT_NAME": "workflow_dispatch",
            **pressure(ACCEPTED_CHANGE_COUNT="8"),
        }
        plan = ci.event_plan(event)
        self.assertTrue(plan["run_all"])
        self.assertTrue(plan["full_gauntlet"])

    def test_workflow_has_two_exact_windows_isolation_and_no_false_green(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertEqual(workflow.count("cron: '17 6 * * *'"), 1)
        self.assertEqual(workflow.count("cron: '17 18 * * *'"), 1)
        self.assertEqual(workflow.count("cron: '47 */3 * * *'"), 1)
        self.assertIn("SHADOW_TWICE_DAILY", workflow)
        self.assertIn("shadow-ci.py gauntlet", workflow)
        self.assertIn("shadow-home", workflow)
        self.assertNotIn("|| true", workflow)
        self.assertNotIn("SHADOW_ACCEPTED_CHANGE_COUNT_THRESHOLD", workflow)
        self.assertNotIn("SHADOW_ACCEPTED_CHANGE_AGE_THRESHOLD_HOURS", workflow)
        self.assertIn("\n  visual-proof:\n", workflow)
        self.assertIn("python -m playwright install --with-deps chromium", workflow)
        self.assertIn("SHADOW_VISUAL: '1'", workflow)
        self.assertIn("tests.test_gallery_visual", workflow)
        self.assertTrue((ROOT / "tests" / "test_gallery_visual.py").is_file())
        self.assertIn("actions/upload-artifact", workflow)
        self.assertIn("if-no-files-found: error", workflow)
        self.assertIn("needs: [plan, test, browser-and-docs, visual-proof]", workflow)

    def test_release_candidate_changes_run_the_gauntlet_before_merge(self) -> None:
        release = ci.select_paths(["VERSION"])
        selector = ci.select_paths(["scripts/shadow-ci.py"])
        workflow = ci.select_paths([".github/workflows/ci.yml"])
        feature = ci.select_paths(["scripts/shadow-status.py"])
        self.assertTrue(release.release_contract)
        self.assertTrue(selector.release_contract)
        self.assertTrue(workflow.release_contract)
        self.assertFalse(workflow.run_all)
        self.assertFalse(feature.release_contract)
        with mock.patch.object(ci, "changed_paths", return_value=["VERSION"]):
            release_plan = ci.event_plan({
                "EVENT_NAME": "pull_request", "PR_BASE_SHA": "a", "HEAD_SHA": "b",
            })
        with mock.patch.object(
            ci, "changed_paths", return_value=["scripts/shadow-status.py"]
        ):
            feature_plan = ci.event_plan({
                "EVENT_NAME": "pull_request", "PR_BASE_SHA": "a", "HEAD_SHA": "b",
            })
        self.assertTrue(release_plan["full_gauntlet"])
        self.assertFalse(feature_plan["full_gauntlet"])

    def test_gauntlet_runs_every_expensive_stage_once_in_order(self) -> None:
        expected = (
            "story-e2e-pass-1", "story-e2e-pass-2", "migration-and-lifecycle",
            "adversarial-and-crash", "capability-and-rotation",
            "rollback-and-upgrade", "release-package-and-install",
        )
        calls = []
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            ci, "_run", side_effect=lambda command, *, home: calls.append((command, home))
        ), mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            ci.run_gauntlet(Path(tmp) / "scratch")
        lines = [
            line.removeprefix("release stage: ")
            for line in stdout.getvalue().splitlines()
            if line.startswith("release stage: ")
        ]
        self.assertEqual(tuple(lines), expected)
        self.assertEqual(len(calls), len(expected))
        self.assertEqual(
            len({call[1].name for call in calls}),
            len(expected),
            "every stage runs in its own scratch home",
        )

    def test_lifecycle_changes_select_their_focused_dependency_closure(self) -> None:
        selected = ci.select_paths(["scripts/shadow-lifecycle.py"])
        self.assertFalse(selected.run_all)
        self.assertIn("tests.test_lifecycle", selected.modules)
        self.assertIn("tests.test_root_board", selected.modules)


class ReleasePressureUsesTheShadowEpoch(unittest.TestCase):
    def test_shadow_release_epoch_wins_and_lightweight_tags_do_not_move_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "release@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Release Test"], check=True)
            env = {
                **os.environ,
                "GIT_AUTHOR_DATE": "2026-08-10T00:00:00Z",
                "GIT_COMMITTER_DATE": "2026-08-10T00:00:00Z",
            }

            for index, subject in enumerate(("legacy", "shadow epoch", "after release")):
                (repo / "state.txt").write_text(f"{index}\n", encoding="utf-8")
                subprocess.run(["git", "-C", str(repo), "add", "state.txt"], check=True)
                subprocess.run(["git", "-C", str(repo), "commit", "-qm", subject], env=env, check=True)
                if subject == "legacy":
                    subprocess.run(["git", "-C", str(repo), "tag", "-a", "v4.0.3", "-m", "legacy"], check=True)
                if subject == "shadow epoch":
                    subprocess.run(["git", "-C", str(repo), "tag", "-a", "shadow-v1.0.0", "-m", "Shadow 1.0"], check=True)

            subprocess.run(["git", "-C", str(repo), "tag", "shadow-v9.9.9"], check=True)
            measured = ci.repository_pressure(repo, now=1786352400)
            shadow_release = subprocess.check_output(
                ["git", "-C", str(repo), "rev-parse", "shadow-v1.0.0^{commit}"],
                text=True,
            ).strip()

        self.assertEqual(measured["ACCEPTED_CHANGE_COUNT"], "1")
        self.assertEqual(measured["RELEASE_RISK"], "none")
        self.assertEqual(measured.get("RELEASE_BASELINE"), "shadow-v1.0.0")
        self.assertEqual(measured.get("RELEASE_BASELINE_COMMIT"), shadow_release)


if __name__ == "__main__":
    unittest.main()


class PublishedNotesMatchTheTaggedChangelog(unittest.TestCase):
    """Release notes come from the tagged CHANGELOG, never a hand cut.

    Measured 2026-08-18: shadow-v1.2.0 published with an EMPTY body because
    the notes were sliced with sed from a checkout that predated the release
    commit — rc was 0, the URL printed, and only reading the body length back
    caught it. The conduct path now generates notes from the checkout being
    released and refuses an empty or missing section outright.
    """

    def _module(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "cw01_release_package",
            Path(__file__).resolve().parent.parent / "scripts" / "shadow-release-package.py",
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("cw01_release_package", module)
        spec.loader.exec_module(module)
        return module

    def test_the_current_version_section_is_extracted_non_empty(self) -> None:
        module = self._module()
        root = Path(__file__).resolve().parent.parent
        version = module.source_version(root)
        notes = module.release_notes(root, version)
        self.assertGreater(len(notes.strip()), 100, notes)
        self.assertNotIn("## Unreleased", notes)
        # The section body, not the heading wrapper.
        self.assertNotIn(f"\n## {version}", notes)

    def test_a_missing_version_section_refuses(self) -> None:
        module = self._module()
        root = Path(__file__).resolve().parent.parent
        with self.assertRaises(ValueError):
            module.release_notes(root, "9.9.9")

    def test_an_empty_section_refuses(self) -> None:
        module = self._module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CHANGELOG.md").write_text(
                "# Changelog\n\n## 3.0.0 — empty on purpose\n\n## 2.9.9 — prior\n\n- real entry\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                module.release_notes(root, "3.0.0")
