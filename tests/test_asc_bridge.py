"""Unit tests for `scripts/vidux-asc-bridge.py`.

Covers (per LI-11 Fix Spec):
  (a) ASC-ID regex parser
  (b) injected gh fetcher (merged-PR enumeration)
  (c) injected Linear fetcher with found/missing branches
  (d) dry-run vs live
  (e) idempotency on re-run

Plus orchestration, error handling, CLI parsing, and live-fetcher seams.
"""

from __future__ import annotations

import datetime as _dt
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Module loader (script lives outside the importable package path)
# ---------------------------------------------------------------------------


_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "vidux-asc-bridge.py"


def _load_bridge_module():
    spec = importlib.util.spec_from_file_location("vidux_asc_bridge", _SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["vidux_asc_bridge"] = module
    spec.loader.exec_module(module)
    return module


bridge = _load_bridge_module()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _pr(number: int, title: str, **extra) -> dict:
    base = {
        "number": number,
        "title": title,
        "url": f"https://github.com/firstbitelabsllc/resplit-ios/pull/{number}",
        "mergedAt": "2026-05-08T10:00:00Z",
    }
    base.update(extra)
    return base


FIXED_NOW = _dt.datetime(2026, 5, 8, 16, 33, 56, tzinfo=_dt.timezone.utc)


# ---------------------------------------------------------------------------
# (a) parse_asc_id
# ---------------------------------------------------------------------------


class TestParseAscId(unittest.TestCase):
    def test_extracts_lowercase_id_from_bracketed_token(self):
        self.assertEqual(bridge.parse_asc_id("fix(send) [asc-K72ZM] crash"), "k72zm")

    def test_returns_none_when_no_token(self):
        self.assertIsNone(bridge.parse_asc_id("fix(send) crash on receipt"))

    def test_returns_none_on_empty_or_none_title(self):
        self.assertIsNone(bridge.parse_asc_id(""))
        self.assertIsNone(bridge.parse_asc_id(None))

    def test_case_insensitive_prefix_match(self):
        self.assertEqual(bridge.parse_asc_id("[ASC-abc]"), "abc")
        self.assertEqual(bridge.parse_asc_id("[Asc-Foo123]"), "foo123")

    def test_uses_first_match_when_multiple_present(self):
        self.assertEqual(
            bridge.parse_asc_id("[asc-aaa] then [asc-bbb] later"), "aaa"
        )


# ---------------------------------------------------------------------------
# merged_at_iso + render_description
# ---------------------------------------------------------------------------


class TestMergedAtIso(unittest.TestCase):
    def test_subtracts_since_hours_from_now(self):
        now = _dt.datetime(2026, 5, 8, 12, 0, 0, tzinfo=_dt.timezone.utc)
        self.assertEqual(
            bridge.merged_at_iso(24, now=now), "2026-05-07T12:00:00Z"
        )

    def test_zero_hours_returns_now(self):
        now = _dt.datetime(2026, 5, 8, 12, 0, 0, tzinfo=_dt.timezone.utc)
        self.assertEqual(bridge.merged_at_iso(0, now=now), "2026-05-08T12:00:00Z")


class TestRenderDescription(unittest.TestCase):
    def test_includes_asc_id_pr_number_url_and_merged_at(self):
        pr = _pr(623, "fix [asc-k72zm] crash")
        body = bridge.render_description("k72zm", pr)
        self.assertIn("ASC ID: k72zm", body)
        self.assertIn("#623", body)
        self.assertIn(pr["url"], body)
        self.assertIn("2026-05-08T10:00:00Z", body)

    def test_drops_merged_line_when_missing(self):
        pr = {"number": 1, "title": "x", "url": "https://example.com"}
        body = bridge.render_description("abc", pr)
        self.assertNotIn("Merged:", body)


# ---------------------------------------------------------------------------
# (b) + (c) + (d) + (e) — orchestrator with injected fetchers
# ---------------------------------------------------------------------------


class TestRunBridge(unittest.TestCase):
    def _run(self, *, prs, existing=None, dry_run=False, fail_create_for=None):
        existing = existing or {}
        created_log: list[tuple[str, dict]] = []

        def fetch_merged_prs(_repo: str, _hours: int) -> list[dict]:
            return prs

        def find_existing_eve(asc_id: str) -> dict | None:
            return existing.get(asc_id)

        def create_eve(asc_id: str, pr: dict) -> dict:
            if fail_create_for and asc_id in fail_create_for:
                raise RuntimeError("synthetic failure")
            created_log.append((asc_id, pr))
            return {
                "id": f"linear-{asc_id}",
                "identifier": f"EVE-{asc_id.upper()}",
            }

        result = bridge.run_bridge(
            repo="firstbitelabsllc/resplit-ios",
            since_hours=24,
            dry_run=dry_run,
            fetch_merged_prs=fetch_merged_prs,
            find_existing_eve=find_existing_eve,
            create_eve=create_eve,
            now=FIXED_NOW,
        )
        return result, created_log

    def test_skips_prs_without_asc_id(self):
        result, log = self._run(
            prs=[_pr(1, "feat(home): polish hero"), _pr(2, "chore: deps")]
        )
        self.assertEqual(result.scanned_prs, 2)
        self.assertEqual(result.asc_prs, 0)
        self.assertEqual(result.created, [])
        self.assertEqual(log, [])

    def test_creates_when_no_existing_eve(self):
        prs = [_pr(623, "fix(send) [asc-k72zm] crash")]
        result, log = self._run(prs=prs, existing={})
        self.assertEqual(result.asc_prs, 1)
        self.assertEqual(len(result.created), 1)
        self.assertEqual(result.created[0]["asc_id"], "k72zm")
        self.assertEqual(result.created[0]["identifier"], "EVE-K72ZM")
        self.assertEqual(result.skipped, [])
        self.assertEqual(log[0][0], "k72zm")

    def test_skips_when_existing_eve_found(self):
        prs = [_pr(623, "fix [asc-k72zm] crash")]
        existing = {"k72zm": {"id": "linear-existing", "identifier": "EVE-200"}}
        result, log = self._run(prs=prs, existing=existing)
        self.assertEqual(result.created, [])
        self.assertEqual(len(result.skipped), 1)
        self.assertEqual(result.skipped[0]["reason"], "linear-issue-exists")
        self.assertEqual(result.skipped[0]["match_id"], "linear-existing")
        self.assertEqual(log, [])

    def test_dry_run_collects_would_create_no_mutation(self):
        prs = [_pr(623, "[asc-k72zm] fix")]
        result, log = self._run(prs=prs, dry_run=True)
        self.assertTrue(result.dry_run)
        self.assertEqual(len(result.would_create), 1)
        self.assertEqual(result.would_create[0]["asc_id"], "k72zm")
        self.assertEqual(result.created, [])
        self.assertEqual(log, [], "create_eve must not be called in dry-run")

    def test_idempotency_on_re_run_simulated_via_existing_lookup(self):
        prs = [_pr(623, "[asc-k72zm] fix")]
        # First pass: nothing exists, so we create.
        first, _ = self._run(prs=prs)
        self.assertEqual(len(first.created), 1)
        # Second pass: same ASC ID now found.
        existing = {"k72zm": {"id": "linear-x", "identifier": "EVE-1"}}
        second, log = self._run(prs=prs, existing=existing)
        self.assertEqual(second.created, [])
        self.assertEqual(len(second.skipped), 1)
        self.assertEqual(log, [])

    def test_dedupes_duplicate_asc_id_within_one_run(self):
        prs = [
            _pr(1, "[asc-foo] first PR"),
            _pr(2, "[asc-foo] second PR with same ASC"),
        ]
        result, log = self._run(prs=prs)
        # Both PRs counted as ASC, but only one creation attempt.
        self.assertEqual(result.asc_prs, 2)
        self.assertEqual(len(result.created), 1)
        self.assertEqual(len(result.skipped), 1)
        self.assertEqual(result.skipped[0]["reason"], "duplicate-asc-id-in-run")
        self.assertEqual(len(log), 1)

    def test_create_failure_recorded_as_error(self):
        prs = [
            _pr(1, "[asc-good] ok"),
            _pr(2, "[asc-bad] fails"),
        ]
        result, _ = self._run(prs=prs, fail_create_for={"bad"})
        self.assertEqual(len(result.created), 1)
        self.assertEqual(result.created[0]["asc_id"], "good")
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0]["asc_id"], "bad")
        self.assertIn("synthetic failure", result.errors[0]["error"])

    def test_envelope_carries_metadata(self):
        prs = [_pr(1, "[asc-x] y")]
        result, _ = self._run(prs=prs)
        env = result.as_dict()
        self.assertEqual(env["bridge_at"], "2026-05-08T16:33:56Z")
        self.assertEqual(env["repo"], "firstbitelabsllc/resplit-ios")
        self.assertEqual(env["since_hours"], 24)
        self.assertFalse(env["dry_run"])
        self.assertEqual(env["scanned_prs"], 1)
        self.assertEqual(env["asc_prs"], 1)
        for key in ("would_create", "created", "skipped", "errors"):
            self.assertIn(key, env)


# ---------------------------------------------------------------------------
# CLI tests — exercise main() with stdin/argv injection
# ---------------------------------------------------------------------------


class TestCli(unittest.TestCase):
    def _run_main(self, argv):
        buf = io.StringIO()
        with patch.object(sys, "stdout", buf):
            rc = bridge.main(argv)
        return rc, buf.getvalue()

    def test_no_network_emits_empty_envelope_exit_zero(self):
        rc, out = self._run_main(["--no-network", "--dry-run"])
        self.assertEqual(rc, 0)
        envelope = json.loads(out)
        self.assertEqual(envelope["skipped_reason"], "no-network")
        self.assertEqual(envelope["scanned_prs"], 0)
        self.assertEqual(envelope["created"], [])
        self.assertTrue(envelope["dry_run"])

    def test_missing_token_file_in_live_mode_returns_2(self):
        with patch.object(bridge, "_load_token") as mock_load:
            mock_load.side_effect = RuntimeError("token file not found: /nope")
            rc, _ = self._run_main(["--token-file", "/nope"])
        self.assertEqual(rc, 2)

    def test_default_repo_and_project(self):
        ns = bridge._parse_args([])
        self.assertEqual(ns.repo, bridge.DEFAULT_REPO)
        self.assertEqual(ns.project_name, bridge.DEFAULT_PROJECT_NAME)
        self.assertEqual(ns.since_hours, bridge.DEFAULT_SINCE_HOURS)
        self.assertFalse(ns.dry_run)
        self.assertFalse(ns.no_network)


# ---------------------------------------------------------------------------
# Live-fetcher seams — exercise injection points without hitting the network.
# ---------------------------------------------------------------------------


class TestLiveFetchMergedPrs(unittest.TestCase):
    def test_returns_empty_on_subprocess_failure(self):
        class _P:
            returncode = 1
            stdout = ""

        with patch.object(bridge.subprocess, "run", return_value=_P()):
            self.assertEqual(
                bridge._live_fetch_merged_prs("firstbitelabsllc/resplit-ios", 24),
                [],
            )

    def test_returns_empty_on_invalid_json(self):
        class _P:
            returncode = 0
            stdout = "not json"

        with patch.object(bridge.subprocess, "run", return_value=_P()):
            self.assertEqual(
                bridge._live_fetch_merged_prs("firstbitelabsllc/resplit-ios", 24),
                [],
            )

    def test_returns_parsed_prs_on_success(self):
        prs = [{"number": 623, "title": "[asc-x] y", "url": "u", "mergedAt": "z"}]

        class _P:
            returncode = 0
            stdout = json.dumps(prs)

        with patch.object(bridge.subprocess, "run", return_value=_P()):
            self.assertEqual(
                bridge._live_fetch_merged_prs("firstbitelabsllc/resplit-ios", 24),
                prs,
            )


class TestLiveFinderAndCreator(unittest.TestCase):
    def test_find_returns_first_match_or_none(self):
        responses = iter([
            {"issues": {"nodes": [{"id": "id1", "identifier": "EVE-1", "title": "t"}]}},
            {"issues": {"nodes": []}},
        ])

        def fake_post(_q, _v, *, token):
            return next(responses)

        with patch.object(bridge, "_post_linear", side_effect=fake_post):
            find = bridge.make_live_find_existing_eve(token="t", project_name="p")
            self.assertEqual(find("foo"), {"id": "id1", "identifier": "EVE-1", "title": "t"})
            self.assertIsNone(find("bar"))

    def test_create_uses_resolved_project_team_state_label(self):
        calls: list[tuple[str, dict]] = []

        def fake_post(query, variables, *, token):
            calls.append((query, variables))
            if "projects(" in query:
                return {"projects": {"nodes": [{"id": "P1", "name": "resplit-ios"}]}}
            if "project(id" in query:
                return {
                    "project": {
                        "id": "P1",
                        "teams": {
                            "nodes": [
                                {
                                    "id": "T1",
                                    "states": {
                                        "nodes": [
                                            {"id": "S1", "name": "Done", "type": "completed"},
                                        ]
                                    },
                                }
                            ]
                        },
                    }
                }
            if "issueLabels" in query:
                return {"issueLabels": {"nodes": [{"id": "L1", "name": "pr-merged"}]}}
            if "issueCreate" in query:
                return {
                    "issueCreate": {
                        "success": True,
                        "issue": {"id": "I1", "identifier": "EVE-100"},
                    }
                }
            raise AssertionError(f"unexpected query: {query[:40]!r}")

        with patch.object(bridge, "_post_linear", side_effect=fake_post):
            create = bridge.make_live_create_eve(
                token="t", project_name="resplit-ios"
            )
            issue = create("k72zm", _pr(623, "fix [asc-k72zm] crash"))
        self.assertEqual(issue["identifier"], "EVE-100")
        # Verify the create input carries projectId, teamId, stateId, labelIds.
        create_call = next(c for c in calls if "issueCreate" in c[0])
        input_obj = create_call[1]["input"]
        self.assertEqual(input_obj["projectId"], "P1")
        self.assertEqual(input_obj["teamId"], "T1")
        self.assertEqual(input_obj["stateId"], "S1")
        self.assertEqual(input_obj["labelIds"], ["L1"])
        self.assertIn("k72zm", input_obj["description"])


if __name__ == "__main__":
    unittest.main()
