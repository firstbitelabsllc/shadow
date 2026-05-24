"""Tests for scripts/vidux-linear-audit.py."""

from __future__ import annotations

import datetime as _dt
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-linear-audit.py"

spec = importlib.util.spec_from_file_location("vidux_linear_audit", SCRIPT)
assert spec is not None
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Check 1: repo_config
# ---------------------------------------------------------------------------


class RepoConfigTests(unittest.TestCase):
    def test_green_when_all_repos_have_project_pair(self):
        configs = {
            "vidux": {
                "linear": {
                    "sources": [
                        {"project_id": "p1", "project_name": "Vidux"}
                    ]
                }
            },
            "strongyes-web": {
                "linear": {
                    "sources": [
                        {"project_id": "p2", "project_name": "StrongYes"}
                    ]
                }
            },
        }
        result = mod.assess_repo_config(
            load_config=lambda r: configs.get(r),
            repos=["vidux", "strongyes-web"],
        )
        self.assertEqual(result.status, mod.GREEN)

    def test_red_when_source_missing_project_id(self):
        configs = {
            "vidux": {
                "linear": {
                    "sources": [
                        {"project_id": "", "project_name": "Vidux"}
                    ]
                }
            }
        }
        result = mod.assess_repo_config(
            load_config=lambda r: configs.get(r),
            repos=["vidux"],
        )
        self.assertEqual(result.status, mod.RED)
        self.assertIn("missing project_id/project_name", result.details)

    def test_yellow_when_team_wide_undeclared(self):
        configs = {
            "fcp-workflow": {
                "linear": {"sources": [{"name": "team-wide-feed"}]}
            }
        }
        result = mod.assess_repo_config(
            load_config=lambda r: configs.get(r),
            repos=["fcp-workflow"],
        )
        self.assertEqual(result.status, mod.YELLOW)

    def test_green_when_team_wide_explicit_flag(self):
        configs = {
            "fcp-workflow": {
                "linear": {
                    "sources": [
                        {"name": "team-wide-feed", "team_wide_intake": True}
                    ]
                }
            }
        }
        result = mod.assess_repo_config(
            load_config=lambda r: configs.get(r),
            repos=["fcp-workflow"],
        )
        self.assertEqual(result.status, mod.GREEN)

    def test_handles_missing_config_file(self):
        result = mod.assess_repo_config(
            load_config=lambda r: None,
            repos=["nonexistent"],
        )
        # No sources at all; not red (we don't punish absent configs)
        self.assertEqual(result.status, mod.GREEN)


# ---------------------------------------------------------------------------
# Check 2: no_project_issues
# ---------------------------------------------------------------------------


class NoProjectIssuesTests(unittest.TestCase):
    def test_green_when_zero(self):
        result = mod.assess_no_project_issues(
            fetch_no_project_issues=lambda: [],
        )
        self.assertEqual(result.status, mod.GREEN)

    def test_red_when_any_present(self):
        result = mod.assess_no_project_issues(
            fetch_no_project_issues=lambda: [
                {"identifier": "EVE-301", "title": "stray", "team": "FBL"},
            ],
        )
        self.assertEqual(result.status, mod.RED)
        self.assertEqual(len(result.evidence), 1)


# ---------------------------------------------------------------------------
# Check 3: label_taxonomy
# ---------------------------------------------------------------------------


class LabelTaxonomyTests(unittest.TestCase):
    def test_red_when_managed_label_missing(self):
        result = mod.assess_label_taxonomy(
            fetch_labels=lambda: ["pr-open", "pr-merged", "blocked"],
            fetch_open_issues=lambda: [],
        )
        self.assertEqual(result.status, mod.RED)

    def test_green_when_all_labels_present_no_open_issues(self):
        result = mod.assess_label_taxonomy(
            fetch_labels=lambda: list(mod.MANAGED_LABELS),
            fetch_open_issues=lambda: [],
        )
        self.assertEqual(result.status, mod.GREEN)

    def test_yellow_when_coverage_below_50_pct(self):
        result = mod.assess_label_taxonomy(
            fetch_labels=lambda: list(mod.MANAGED_LABELS),
            fetch_open_issues=lambda: [
                {"id": 1, "labels": []},
                {"id": 2, "labels": []},
                {"id": 3, "labels": ["pr-open"]},
                {"id": 4, "labels": []},
            ],
        )
        self.assertEqual(result.status, mod.YELLOW)
        self.assertIn("25%", result.details)

    def test_green_when_coverage_at_or_above_50_pct(self):
        result = mod.assess_label_taxonomy(
            fetch_labels=lambda: list(mod.MANAGED_LABELS),
            fetch_open_issues=lambda: [
                {"id": 1, "labels": ["pr-open"]},
                {"id": 2, "labels": ["blocked"]},
                {"id": 3, "labels": []},
            ],
        )
        self.assertEqual(result.status, mod.GREEN)


# ---------------------------------------------------------------------------
# Check 4: pr_linear_links
# ---------------------------------------------------------------------------


class PrLinearLinksTests(unittest.TestCase):
    def test_green_when_all_prs_carry_linear_ref_in_body(self):
        prs = {
            "vidux": [
                {
                    "number": 1,
                    "title": "fix",
                    "body": "Linear: EVE-300",
                    "headRefName": "x",
                }
            ]
        }
        result = mod.assess_pr_linear_links(
            fetch_open_prs=lambda r: prs.get(r, []),
            fetch_linear_attachment=lambda r, n: False,
            repos=["vidux"],
        )
        self.assertEqual(result.status, mod.GREEN)

    def test_green_when_attachment_present_without_body_ref(self):
        prs = {
            "vidux": [
                {
                    "number": 2,
                    "title": "feat",
                    "body": "no linear ref here",
                    "headRefName": "y",
                }
            ]
        }
        result = mod.assess_pr_linear_links(
            fetch_open_prs=lambda r: prs.get(r, []),
            fetch_linear_attachment=lambda r, n: True,
            repos=["vidux"],
        )
        self.assertEqual(result.status, mod.GREEN)

    def test_yellow_when_pr_missing_both(self):
        prs = {
            "vidux": [
                {
                    "number": 3,
                    "title": "chore",
                    "body": "no link",
                    "headRefName": "z",
                }
            ]
        }
        result = mod.assess_pr_linear_links(
            fetch_open_prs=lambda r: prs.get(r, []),
            fetch_linear_attachment=lambda r, n: False,
            repos=["vidux"],
        )
        self.assertEqual(result.status, mod.YELLOW)
        self.assertEqual(len(result.evidence), 1)


# ---------------------------------------------------------------------------
# Check 5: draft_age
# ---------------------------------------------------------------------------


class DraftAgeTests(unittest.TestCase):
    def setUp(self):
        self.now = _dt.datetime(2026, 5, 7, 18, 0, tzinfo=_dt.timezone.utc)

    def _draft(self, login: str, hours_old: float, number: int = 1) -> dict:
        created = self.now - _dt.timedelta(hours=hours_old)
        return {
            "number": number,
            "createdAt": created.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "author": {"login": login},
        }

    def test_green_when_drafts_under_24h(self):
        drafts = {"vidux": [self._draft("claude-bot", 12)]}
        result = mod.assess_draft_age(
            fetch_open_drafts=lambda r: drafts.get(r, []),
            repos=["vidux"],
            now=self.now,
        )
        self.assertEqual(result.status, mod.GREEN)

    def test_yellow_when_draft_over_24h_under_72h(self):
        drafts = {"vidux": [self._draft("codex", 30)]}
        result = mod.assess_draft_age(
            fetch_open_drafts=lambda r: drafts.get(r, []),
            repos=["vidux"],
            now=self.now,
        )
        self.assertEqual(result.status, mod.YELLOW)

    def test_red_when_draft_over_72h(self):
        drafts = {"vidux": [self._draft("cursor-bot", 100)]}
        result = mod.assess_draft_age(
            fetch_open_drafts=lambda r: drafts.get(r, []),
            repos=["vidux"],
            now=self.now,
        )
        self.assertEqual(result.status, mod.RED)
        self.assertEqual(result.evidence[0]["hours_old"], 100)

    def test_human_authored_drafts_are_ignored(self):
        drafts = {"vidux": [self._draft("leojkwan", 200)]}
        result = mod.assess_draft_age(
            fetch_open_drafts=lambda r: drafts.get(r, []),
            repos=["vidux"],
            now=self.now,
        )
        self.assertEqual(result.status, mod.GREEN)


# ---------------------------------------------------------------------------
# Check 6: description_format
# ---------------------------------------------------------------------------


class DescriptionFormatTests(unittest.TestCase):
    def test_green_when_no_offending_issues(self):
        result = mod.assess_description_format(
            fetch_issues_with_pr_markdown_no_attachment=lambda: [],
        )
        self.assertEqual(result.status, mod.GREEN)

    def test_yellow_when_some_present(self):
        result = mod.assess_description_format(
            fetch_issues_with_pr_markdown_no_attachment=lambda: [
                {"identifier": "EVE-275", "title": "x"},
            ],
        )
        self.assertEqual(result.status, mod.YELLOW)

    def test_red_when_more_than_10(self):
        offenders = [{"identifier": f"EVE-{i}"} for i in range(11)]
        result = mod.assess_description_format(
            fetch_issues_with_pr_markdown_no_attachment=lambda: offenders,
        )
        self.assertEqual(result.status, mod.RED)


# ---------------------------------------------------------------------------
# Check 7: sync_deltas
# ---------------------------------------------------------------------------


class SyncDeltasTests(unittest.TestCase):
    def test_green_when_all_zeros(self):
        result = mod.assess_sync_deltas(
            run_dry_sync=lambda r: {
                "results": [
                    {"pushed": 0, "inbox_appended": 0, "errors": []}
                ]
            },
            repos=["vidux"],
        )
        self.assertEqual(result.status, mod.GREEN)

    def test_yellow_when_drift_present(self):
        result = mod.assess_sync_deltas(
            run_dry_sync=lambda r: {
                "results": [
                    {"pushed": 3, "inbox_appended": 0, "errors": []}
                ]
            },
            repos=["vidux"],
        )
        self.assertEqual(result.status, mod.YELLOW)

    def test_red_when_errors_present(self):
        result = mod.assess_sync_deltas(
            run_dry_sync=lambda r: {
                "results": [
                    {
                        "plan": "/x",
                        "pushed": 0,
                        "inbox_appended": 0,
                        "errors": ["adapter timeout"],
                    }
                ]
            },
            repos=["vidux"],
        )
        self.assertEqual(result.status, mod.RED)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


class OverallStatusTests(unittest.TestCase):
    def test_worst_of_red_beats_yellow(self):
        results = [
            mod.CheckResult("a", mod.GREEN),
            mod.CheckResult("b", mod.YELLOW),
            mod.CheckResult("c", mod.RED),
        ]
        self.assertEqual(mod.overall_status(results), mod.RED)

    def test_worst_of_yellow_when_no_red(self):
        results = [
            mod.CheckResult("a", mod.GREEN),
            mod.CheckResult("b", mod.YELLOW),
        ]
        self.assertEqual(mod.overall_status(results), mod.YELLOW)

    def test_worst_of_green_when_all_green(self):
        results = [mod.CheckResult("a", mod.GREEN)]
        self.assertEqual(mod.overall_status(results), mod.GREEN)

    def test_skipped_does_not_dominate(self):
        results = [
            mod.CheckResult("a", mod.SKIPPED),
            mod.CheckResult("b", mod.GREEN),
        ]
        self.assertEqual(mod.overall_status(results), mod.GREEN)

    def test_envelope_shape(self):
        results = [
            mod.CheckResult("a", mod.GREEN, "ok"),
            mod.CheckResult("b", mod.YELLOW, "drift"),
        ]
        envelope = mod.build_envelope(results)
        self.assertEqual(set(envelope.keys()), {"audit_at", "overall", "summary", "checks"})
        self.assertEqual(envelope["overall"], mod.YELLOW)
        self.assertEqual(envelope["summary"][mod.GREEN], 1)
        self.assertEqual(envelope["summary"][mod.YELLOW], 1)
        self.assertEqual(len(envelope["checks"]), 2)


class RunAuditCliTests(unittest.TestCase):
    def _full_fetchers(self) -> dict:
        return {
            "load_config": lambda r: {
                "linear": {
                    "sources": [
                        {"project_id": "p", "project_name": "n"}
                    ]
                }
            },
            "fetch_no_project_issues": lambda: [],
            "fetch_labels": lambda: list(mod.MANAGED_LABELS),
            "fetch_open_issues": lambda: [],
            "fetch_open_prs": lambda r: [],
            "fetch_linear_attachment": lambda r, n: False,
            "fetch_open_drafts": lambda r: [],
            "fetch_issues_with_pr_markdown_no_attachment": lambda: [],
            "run_dry_sync": lambda r: {
                "results": [
                    {"pushed": 0, "inbox_appended": 0, "errors": []}
                ]
            },
        }

    def test_check_filter_runs_only_selected(self):
        envelope = mod.run_audit(
            selected=["repo_config"],
            repos=["vidux"],
            fetchers=self._full_fetchers(),
        )
        self.assertEqual(len(envelope["checks"]), 1)
        self.assertEqual(envelope["checks"][0]["name"], "repo_config")

    def test_unknown_check_raises(self):
        with self.assertRaises(ValueError):
            mod.run_audit(selected=["bogus"])

    def test_repo_filter_scopes_repo_level_checks(self):
        envelope = mod.run_audit(
            selected=["repo_config"],
            repos=["vidux"],
            fetchers=self._full_fetchers(),
        )
        self.assertEqual(envelope["checks"][0]["status"], mod.GREEN)

    def test_no_network_skips_linear_only_checks(self):
        envelope = mod.run_audit(
            selected=["no_project_issues", "label_taxonomy", "description_format"],
            no_network=True,
        )
        statuses = {c["name"]: c["status"] for c in envelope["checks"]}
        self.assertEqual(statuses["no_project_issues"], mod.SKIPPED)
        self.assertEqual(statuses["label_taxonomy"], mod.SKIPPED)
        self.assertEqual(statuses["description_format"], mod.SKIPPED)
        # Skipped does not dominate; overall should reflect remaining results.
        self.assertEqual(envelope["overall"], mod.SKIPPED)

    def test_full_run_produces_seven_checks(self):
        envelope = mod.run_audit(
            repos=["vidux"],
            fetchers=self._full_fetchers(),
        )
        self.assertEqual(len(envelope["checks"]), len(mod.CHECK_NAMES))
        self.assertEqual(envelope["overall"], mod.GREEN)

    def test_summary_counts_match_check_count(self):
        envelope = mod.run_audit(
            repos=["vidux"],
            fetchers=self._full_fetchers(),
        )
        total = sum(envelope["summary"].values())
        self.assertEqual(total, len(envelope["checks"]))

    def test_main_returns_zero_on_green(self):
        # Inject fetchers via run_audit; main wraps it. We test the run_audit
        # exit-code surface directly because main reads from real fetchers.
        envelope = mod.run_audit(
            repos=["vidux"],
            fetchers=self._full_fetchers(),
        )
        self.assertEqual(envelope["overall"], mod.GREEN)

    def test_main_returns_one_on_red(self):
        fetchers = self._full_fetchers()
        fetchers["fetch_no_project_issues"] = lambda: [
            {"identifier": "EVE-301", "title": "x", "team": "FBL"}
        ]
        envelope = mod.run_audit(repos=["vidux"], fetchers=fetchers)
        self.assertEqual(envelope["overall"], mod.RED)


# ---------------------------------------------------------------------------
# LI-16: per-repo gh-owner resolution
# ---------------------------------------------------------------------------


class GhOwnerResolutionTests(unittest.TestCase):
    def setUp(self):
        # Avoid leaking env state between tests; restore on tearDown.
        self._saved = mod.os.environ.pop("VIDUX_GH_OWNER", None)

    def tearDown(self):
        if self._saved is None:
            mod.os.environ.pop("VIDUX_GH_OWNER", None)
        else:
            mod.os.environ["VIDUX_GH_OWNER"] = self._saved

    def test_mapped_repo_resolves_to_its_owner(self):
        self.assertEqual(mod._gh_owner("vidux"), "firstbitelabsllc")
        self.assertEqual(mod._gh_owner("resplit-ios"), "firstbitelabsllc")
        self.assertEqual(mod._gh_owner("strongyes-web"), "leojkwan")
        self.assertEqual(mod._gh_owner("resplit-web"), "leojkwan")
        self.assertEqual(mod._gh_owner("fcp-workflow"), "leojkwan")

    def test_unknown_repo_falls_back_to_default(self):
        self.assertEqual(
            mod._gh_owner("nonexistent-repo"), mod.DEFAULT_GH_OWNER
        )

    def test_env_override_wins_over_mapping(self):
        mod.os.environ["VIDUX_GH_OWNER"] = "test-org"
        # Env override applies to mapped repos too.
        self.assertEqual(mod._gh_owner("vidux"), "test-org")
        self.assertEqual(mod._gh_owner("strongyes-web"), "test-org")
        self.assertEqual(mod._gh_owner("nonexistent-repo"), "test-org")

    def test_env_override_empty_string_does_not_short_circuit(self):
        # Empty string is falsy; should fall through to REPO_OWNERS mapping.
        mod.os.environ["VIDUX_GH_OWNER"] = ""
        self.assertEqual(mod._gh_owner("vidux"), "firstbitelabsllc")
        self.assertEqual(mod._gh_owner("strongyes-web"), "leojkwan")


if __name__ == "__main__":
    unittest.main()
