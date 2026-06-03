"""Tests for scripts/vidux-plan-bank-audit.py."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-plan-bank-audit.py"

spec = importlib.util.spec_from_file_location("vidux_plan_bank_audit", SCRIPT)
assert spec is not None
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class PlanBankAuditTests(unittest.TestCase):
    def write_plan(self, root: Path, rel: str, body: str) -> Path:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    def issue_codes(self, snapshot: dict) -> set[str]:
        return {issue["code"] for issue in snapshot["issues"]}

    def test_reports_common_closure_and_proof_issues(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_plan(
                root,
                "projects/sample/PLAN.md",
                "\n".join(
                    [
                        "# Sample",
                        "## Purpose",
                        "Keep a lane honest.",
                        "## Tasks",
                        "- [completed] SA-1: Shipped a thing with proof /tmp/proof.md",
                        "- [blocked] SA-2: Waiting on review",
                        "## Verification Gates",
                        "- [ ] real browser smoke",
                    ]
                ),
            )

            snapshot = mod.audit_roots([root])
            codes = self.issue_codes(snapshot)

            self.assertIn("blocked_without_since", codes)
            self.assertIn("temporary_proof_path", codes)
            self.assertIn("unchecked_gate_checkbox", codes)
            self.assertIn("missing_evidence_section", codes)
            self.assertIn("missing_progress_section", codes)
            self.assertIn("missing_terminal_closeout_section", codes)

    def test_archived_non_terminal_rows_are_critical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_plan(
                root,
                "projects/_archive/old-lane/PLAN.md",
                "# Old\n## Tasks\n- [pending] OL-1: still open\n",
            )

            snapshot = mod.audit_roots([root])
            archived_issues = [
                issue
                for issue in snapshot["issues"]
                if issue["code"] == "archived_non_terminal_row"
            ]

            self.assertEqual(len(archived_issues), 1)
            self.assertEqual(archived_issues[0]["severity"], "critical")
            self.assertEqual(snapshot["severity_counts"]["critical"], 1)

    def test_skips_fixture_and_example_plans_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_plan(root, "tests/fixtures/PLAN.md", "# Fixture\n")
            self.write_plan(root, "examples/demo/PLAN.md", "# Example\n")

            snapshot = mod.audit_roots([root])
            included = mod.audit_roots([root], include_fixtures=True)

            self.assertEqual(snapshot["plans_total"], 0)
            self.assertEqual(included["plans_total"], 2)

    def test_skips_agent_mirror_plan_dirs_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_plan(root, ".claude/worktrees/agent-a/PLAN.md", "# Agent\n")
            self.write_plan(root, ".agents/skills/vidux/PLAN.md", "# Mirror\n")
            self.write_plan(root, ".codex/lane/PLAN.md", "# Codex\n")
            self.write_plan(root, "projects/real/PLAN.md", "# Real\n")

            snapshot = mod.audit_roots([root])
            included = mod.audit_roots([root], include_agent_mirrors=True)

            self.assertEqual(snapshot["plans_total"], 1)
            self.assertEqual(included["plans_total"], 4)
            self.assertEqual(snapshot["reports"][0]["path"], "projects/real/PLAN.md")

    def test_fail_on_thresholds_are_observe_only_by_default(self):
        snapshot = {
            "severity_counts": {
                "critical": 0,
                "high": 1,
                "medium": 3,
                "low": 0,
            }
        }

        self.assertEqual(mod.exit_code_for(snapshot, "none"), 0)
        self.assertEqual(mod.exit_code_for(snapshot, "critical"), 0)
        self.assertEqual(mod.exit_code_for(snapshot, "high"), 1)
        self.assertEqual(mod.exit_code_for(snapshot, "medium"), 1)
        self.assertEqual(mod.exit_code_for(snapshot, "any"), 1)

    def test_snapshot_is_json_serializable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_plan(root, "PLAN.md", "# Root\n## Tasks\n")

            snapshot = mod.audit_roots([root])
            encoded = json.dumps(snapshot, sort_keys=True)

            self.assertIn('"plans_total": 1', encoded)

    def test_main_writes_each_watch_iteration_to_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_plan(root, "PLAN.md", "# Root\n## Tasks\n")
            out = root / "smoke" / "audit.jsonl"

            with contextlib.redirect_stdout(io.StringIO()):
                code = mod.main(
                    [
                        str(root),
                        "--watch-iterations",
                        "2",
                        "--watch-interval-seconds",
                        "0",
                        "--output-jsonl",
                        str(out),
                    ]
                )

            lines = out.read_text(encoding="utf-8").splitlines()
            envelopes = [json.loads(line) for line in lines]

            self.assertEqual(code, 0)
            self.assertEqual([item["iteration"] for item in envelopes], [1, 2])
            self.assertEqual(envelopes[0]["snapshot"]["plans_total"], 1)
            self.assertIn("duration_seconds", envelopes[0]["snapshot"])

    def test_summarizes_jsonl_smoke_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            rows = [
                {
                    "iteration": 1,
                    "snapshot": {
                        "audit_at": "2026-06-02T00:00:00Z",
                        "roots": ["/tmp/repo"],
                        "plans_total": 2,
                        "archived_plans": 0,
                        "duration_seconds": 1.2,
                        "severity_counts": {"critical": 1, "high": 2},
                        "status_counts": {"pending": 4},
                        "issue_code_counts": {"blocked_without_since": 2},
                        "reports": [
                            {
                                "path": "PLAN.md",
                                "archived": False,
                                "status_counts": {"pending": 4},
                                "issues": [],
                            }
                        ],
                    },
                },
                {
                    "iteration": 2,
                    "snapshot": {
                        "audit_at": "2026-06-02T00:15:00Z",
                        "roots": ["/tmp/repo"],
                        "plans_total": 3,
                        "archived_plans": 1,
                        "duration_seconds": 1.5,
                        "severity_counts": {"critical": 1, "high": 3},
                        "status_counts": {"pending": 5},
                        "issue_code_counts": {
                            "blocked_without_since": 1,
                            "unchecked_gate_checkbox": 2,
                        },
                        "issues": [
                            {
                                "severity": "high",
                                "code": "unchecked_gate_checkbox",
                                "path": "PLAN.md",
                                "line": 7,
                                "detail": "unchecked gate",
                            },
                            {
                                "severity": "high",
                                "code": "blocked_without_since",
                                "path": "PLAN.md",
                                "line": 3,
                                "detail": "missing marker",
                            },
                        ],
                        "reports": [
                            {
                                "path": "PLAN.md",
                                "archived": True,
                                "status_counts": {"pending": 5},
                                "issues": [
                                    {
                                        "severity": "high",
                                        "code": "unchecked_gate_checkbox",
                                        "path": "PLAN.md",
                                        "line": 7,
                                        "detail": "unchecked gate",
                                    }
                                ],
                            }
                        ],
                    },
                },
            ]
            path.write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )

            summary = mod.summarize_jsonl(path)
            human = mod.render_summary(summary)

            self.assertEqual(summary["iterations"], 2)
            self.assertEqual(summary["plans_total"]["delta"], 1)
            self.assertEqual(summary["archived_plans"]["delta"], 1)
            self.assertEqual(summary["severity_delta"]["high"], 1)
            self.assertEqual(summary["issue_code_delta"]["blocked_without_since"], -1)
            self.assertIn("unchecked_gate_checkbox", summary["sample_issues_by_code"])
            self.assertEqual(summary["root_breakdown"]["repo"]["plans"], 1)
            self.assertEqual(summary["root_breakdown"]["repo"]["archived_plans"], 1)
            self.assertIn("Vidux plan-bank audit smoke summary", human)
            self.assertIn("root breakdown", human)
            self.assertIn("sample issues by code", human)


if __name__ == "__main__":
    unittest.main()
