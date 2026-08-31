"""Repeatable, provenance-safe measurements for large Shadow plans."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.plan_tree_fixture import install_plan_tree


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "shadow_plan_scale.py"
CLI = ROOT / "scripts" / "shadow-plan-scale.py"
SPEC = importlib.util.spec_from_file_location("shadow_plan_scale", MODULE)
assert SPEC and SPEC.loader
scale = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = scale
SPEC.loader.exec_module(scale)


def plan(project: str, resume: str, padding: str = "") -> str:
    return f"""# {project}

## Brief

- Project: {project}
- Mode: ship

## Tasks

### Current delivery
- [pending] current work for {project} {resume} | proof: cmd true
- [pending] delivery is proven ~zz99 (DoD) | proof: cmd true | needs: {resume}

- Archived milestone: [old-work](docs/plan-archive/old-work.md)

## Contradictions

- monolith vs shards | provisional winner: measure first | opened 2026-08-12T00:00:00Z

## Progress

- 2026-08-12T00:00:00Z DECISION keep authority in source bytes
- 2026-08-12T00:01:00Z {resume} PROOF true -> observed baseline
{padding}
"""


class PlanScaleBaseline(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.board = self.root / "board.json"
        self.entities = []
        self.claims = []

    def tearDown(self) -> None:
        self.temp.cleanup()

    def add_entity(
        self,
        project: str,
        identity_char: str,
        resume: str,
        *,
        padding: str = "",
        owner: str | None = None,
    ) -> Path:
        directory = self.root / f"{project}-{identity_char}"
        archive = directory / "docs" / "plan-archive"
        archive.mkdir(parents=True)
        path = directory / "PLAN.md"
        path.write_text(plan(project, resume, padding), encoding="utf-8")
        (archive / "old-work.md").write_text(
            "# Archived old work\n\n- exact historical receipt\n", encoding="utf-8"
        )
        identity = identity_char * 64
        self.entities.append(
            {"id": identity, "project": project, "plan": str(path), "resume": resume}
        )
        if owner:
            self.claims.append(
                {
                    "entity": identity,
                    "row": resume,
                    "owner": owner,
                    "claimed_at": "2026-08-12T00:00:00Z",
                    "return_by": "2026-08-13T00:00:00Z",
                    "recovery": "probe-proof-then-adopt-park-or-close",
                }
            )
        return path

    def write_board(self) -> None:
        projects = sorted({entity["project"] for entity in self.entities})
        self.board.write_text(
            json.dumps(
                {
                    "schema": "shadow.root-board.v1",
                    "revision": 42,
                    "projects": [
                        {"id": project, "priority": index + 1}
                        for index, project in enumerate(projects)
                    ],
                    "entities": self.entities,
                    "claims": self.claims,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    def test_largest_entity_per_project_is_profiled_without_private_paths(self) -> None:
        smaller = self.add_entity("alpha", "a", "~aa11")
        larger = self.add_entity("alpha", "b", "~bb22", padding="x" * 200)
        beta = self.add_entity("beta", "c", "~cc33", owner="codex")
        self.write_board()

        report = scale.benchmark_board(
            self.board, projects=("alpha", "beta"), repeats=3
        )

        self.assertEqual(report["schema"], "shadow.plan-scale-baseline.v1")
        self.assertEqual(report["board"]["revision"], 42)
        self.assertEqual(
            [item["entity"] for item in report["plans"]],
            ["entity@bbbbbbbbbbbb/PLAN.md", "entity@cccccccccccc/PLAN.md"],
        )
        self.assertEqual(report["plans"][0]["bytes"], larger.stat().st_size)
        self.assertNotEqual(report["plans"][0]["bytes"], smaller.stat().st_size)
        self.assertEqual(report["plans"][1]["bytes"], beta.stat().st_size)
        encoded = json.dumps(report, sort_keys=True)
        self.assertNotIn(str(self.root), encoded)
        for item in report["plans"]:
            self.assertRegex(item["sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(item["task_rows"], 2)
            self.assertEqual(item["milestones"], 1)
            self.assertGreaterEqual(item["parse_ms"]["p95"], 0)
            self.assertGreaterEqual(item["read_parse_ms"]["p95"], 0)

    def test_profiles_and_queries_count_only_unresolved_plan_contradictions(self) -> None:
        path = self.add_entity("alpha", "a", "~aa11")
        text = path.read_text(encoding="utf-8").replace(
            "## Progress",
            "- older choice | winner: monolith\n"
            "- RESOLVED 2026-08-26: retired choice | winner: shards\n\n"
            "## Progress",
        )
        path.write_text(text, encoding="utf-8")
        self.write_board()

        report = scale.benchmark_board(
            self.board, projects=("alpha",), repeats=1
        )

        self.assertEqual(report["plans"][0]["contradictions_unresolved"], 2)
        self.assertNotIn("contradictions", report["plans"][0])
        contradiction = next(
            item for item in report["queries"] if item["kind"] == "contradiction"
        )
        self.assertTrue(contradiction["found"])

    def test_query_corpus_covers_lookup_classes_and_carries_digests(self) -> None:
        self.add_entity("alpha", "a", "~aa11", owner="codex")
        self.add_entity("beta", "b", "~bb22")
        self.write_board()

        report = scale.benchmark_board(
            self.board, projects=("alpha", "beta"), repeats=3
        )
        queries = report["queries"]
        self.assertEqual(
            {query["kind"] for query in queries},
            {
                "current_work",
                "owner",
                "decision",
                "contradiction",
                "proof",
                "history",
                "cross_entity",
            },
        )
        self.assertTrue(all(query["found"] for query in queries))
        self.assertTrue(all(query["source_bytes"] > 0 for query in queries))
        self.assertTrue(all(query["result_bytes"] > 0 for query in queries))
        self.assertTrue(all(query["hops"] >= 1 for query in queries))
        self.assertTrue(all(query["sources"] for query in queries))
        for query in queries:
            for source in query["sources"]:
                self.assertRegex(source["sha256"], r"^[0-9a-f]{64}$")
                self.assertNotIn(str(self.root), source["ref"])
        owner = next(query for query in queries if query["kind"] == "owner")
        self.assertEqual(owner["result_sha256"], hashlib.sha256(
            b"~aa11:codex"
        ).hexdigest())
        history = next(query for query in queries if query["kind"] == "history")
        self.assertEqual(history["hops"], 2)
        cross = next(query for query in queries if query["kind"] == "cross_entity")
        self.assertEqual(cross["hops"], 3)

    def test_missing_resume_refuses_instead_of_benchmarking_wrong_work(self) -> None:
        self.add_entity("alpha", "a", "~aa11")
        self.entities[0]["resume"] = "~nope"
        self.write_board()

        with self.assertRaisesRegex(scale.PlanScaleError, "resume row is absent"):
            scale.benchmark_board(self.board, projects=("alpha",), repeats=1)

    def test_missing_archive_falls_back_to_plan_history_and_stays_visible(self) -> None:
        path = self.add_entity("alpha", "a", "~aa11")
        (path.parent / "docs" / "plan-archive" / "old-work.md").unlink()
        self.write_board()

        report = scale.benchmark_board(
            self.board, projects=("alpha",), repeats=1
        )
        history = next(query for query in report["queries"] if query["kind"] == "history")
        self.assertTrue(history["found"])
        self.assertEqual(history["hops"], 1)
        self.assertGreater(history["result_bytes"], 0)
        self.assertEqual(report["plans"][0]["archive_links"], 1)
        self.assertEqual(report["plans"][0]["missing_archive_links"], 1)

    def test_cli_emits_the_same_path_free_schema(self) -> None:
        self.add_entity("alpha", "a", "~aa11")
        self.write_board()
        result = subprocess.run(
            [
                sys.executable,
                str(CLI),
                "--board",
                str(self.board),
                "--project",
                "alpha",
                "--repeats",
                "1",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema"], "shadow.plan-scale-baseline.v1")
        self.assertNotIn(str(self.root), result.stdout)

    def test_cold_partitioned_seat_matches_every_answer_with_bounded_provenance(self) -> None:
        path = self.add_entity("alpha", "a", "~aa11", owner="codex")
        self.write_board()
        before = scale.benchmark_board(
            self.board,
            projects=("alpha",),
            repeats=1,
        )
        source = path.read_bytes()
        install_plan_tree(path.parent, source)

        after = scale.benchmark_cold_trees(
            self.board,
            projects=("alpha",),
            repeats=1,
        )
        cli = subprocess.run(
            [
                sys.executable,
                str(CLI),
                "--board",
                str(self.board),
                "--project",
                "alpha",
                "--repeats",
                "1",
                "--cold-tree",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertEqual(json.loads(cli.stdout)["schema"], "shadow.plan-scale-cold-tree.v1")

        before_answers = {
            (item["case_id"], item["kind"]): item["result_sha256"]
            for item in before["queries"]
        }
        after_answers = {
            (item["case_id"], item["kind"]): item["result_sha256"]
            for item in after["queries"]
        }
        self.assertEqual(after_answers, before_answers)
        for query in after["queries"]:
            self.assertTrue(query["sources"])
            if query["kind"] not in {"owner", "cross_entity", "history"}:
                self.assertLessEqual(query["hops"], 10)
                self.assertLessEqual(query["source_bytes"], 168 * 1024)
            for source_receipt in query["sources"]:
                self.assertRegex(source_receipt["sha256"], r"^[0-9a-f]{64}$")


class CandidateLayoutComparison(unittest.TestCase):
    def test_lossless_shards_reassemble_exact_bytes_and_route_frozen_queries(self) -> None:
        content = plan("alpha", "~aa11", padding="x" * 500).encode("utf-8")
        layout = scale.sharded_layout(content)

        self.assertEqual(scale.reassemble_shards(layout), content)
        self.assertEqual(layout["source_sha256"], hashlib.sha256(content).hexdigest())
        self.assertGreater(len(layout["shards"]), 3)
        manifest = json.loads(layout["manifest"])
        self.assertEqual(manifest["schema"], "shadow.plan-shards.v1")
        self.assertEqual(
            [entry["sha256"] for entry in manifest["shards"]],
            [shard["sha256"] for shard in layout["shards"]],
        )
        row = scale.route_shard(layout, row_id="~aa11")
        self.assertIn(b"current work for alpha", row["content"])
        proof = scale.route_shard(layout, tag="proof")
        self.assertIn(b" PROOF ", proof["content"])
        decision = scale.route_shard(layout, tag="decision")
        self.assertIn(b" DECISION ", decision["content"])

    def test_stale_manifest_refuses_before_returning_a_shard(self) -> None:
        content = plan("alpha", "~aa11").encode("utf-8")
        layout = scale.sharded_layout(content)
        layout["shards"][0]["content"] += b"tamper"

        with self.assertRaisesRegex(scale.PlanScaleError, "shard digest mismatch"):
            scale.reassemble_shards(layout)
        with self.assertRaisesRegex(scale.PlanScaleError, "shard digest mismatch"):
            scale.route_shard(layout, row_id="~aa11")

    def test_comparison_keeps_one_authority_and_exposes_write_amplification(self) -> None:
        content = plan("alpha", "~aa11", padding="x" * 20_000).encode("utf-8")
        comparison = scale.compare_layouts(content)

        self.assertEqual(
            [candidate["name"] for candidate in comparison["candidates"]],
            ["monolith-plus-index", "hot-plan-plus-archives", "manifest-plus-shards"],
        )
        monolith, hot, shards = comparison["candidates"]
        self.assertEqual(monolith["authorities"], 1)
        self.assertEqual(hot["authorities"], 1)
        self.assertEqual(shards["authorities"], 1)
        self.assertEqual(monolith["write_amplification_bytes"], len(content))
        self.assertEqual(hot["write_amplification_bytes"], len(content))
        self.assertLess(shards["write_amplification_bytes"], len(content))
        self.assertLess(shards["current_lookup_bytes"], len(content))
        self.assertTrue(shards["exact_reassembly"])
        self.assertEqual(comparison["decision"], "manifest-plus-shards")


class PlanTreeMigrationHarness(unittest.TestCase):
    def test_local_apply_and_rollback_preserve_plan_bytes_and_board(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            home = root / "home"
            plan_path = home / ".shadow" / "plans" / "alpha" / "PLAN.md"
            plan_path.parent.mkdir(parents=True)
            content = plan("alpha", "~aa11")
            plan_path.write_text(content, encoding="utf-8")
            archive = plan_path.parent / "docs" / "plan-archive" / "old-work.md"
            archive.parent.mkdir(parents=True)
            archive.write_text("# Old work\n", encoding="utf-8")
            board = home / ".shadow" / "board.json"
            board.write_text(
                json.dumps(
                    {
                        "schema": "shadow.root-board.v1",
                        "revision": 9,
                        "projects": [{"id": "alpha", "priority": 1}],
                        "entities": [{
                            "id": "a" * 64,
                            "project": "alpha",
                            "plan": str(plan_path),
                            "resume": "~aa11",
                        }],
                        "claims": [{
                            "entity": "a" * 64,
                            "row": "~aa11",
                            "owner": "cold-seat",
                            "claimed_at": "2026-08-12T00:00:00Z",
                            "return_by": "2026-08-13T00:00:00Z",
                            "recovery": "probe-proof-then-adopt-park-or-close",
                        }],
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(home / ".shadow"), "init", "--quiet"], check=True)
            subprocess.run(
                ["git", "-C", str(home / ".shadow"), "config", "user.name", "Board Test"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(home / ".shadow"), "config", "user.email", "board@example.invalid"],
                check=True,
            )
            (home / ".shadow" / ".gitignore").write_text("plans/\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(home / ".shadow"), "add", "board.json", ".gitignore"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(home / ".shadow"), "commit", "--quiet", "-m", "seed board"],
                check=True,
            )
            before_plan = plan_path.read_bytes()
            before_board = board.read_bytes()
            report = scale._store.dry_run_migration(plan_path, board=board)

            applied = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "shadow-plan.py"),
                    "migrate",
                    str(plan_path),
                    "--apply",
                    "--expect",
                    report.source_sha256,
                    "--board",
                    str(board),
                ],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )
            payload = json.loads(applied.stdout or "{}")
            self.assertEqual(applied.returncode, 0, (applied.stderr, payload))
            self.assertEqual(scale._store.PlanSnapshot.open(plan_path).materialize(), before_plan)
            self.assertEqual(board.read_bytes(), before_board)
            self.assertEqual(payload["action"], "migrated")

            rolled_back = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "shadow-plan.py"),
                    "rollback",
                    str(plan_path),
                    "--expect",
                    payload["root_sha256"],
                    "--board",
                    str(board),
                ],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(rolled_back.returncode, 0, rolled_back.stderr)
            self.assertEqual(plan_path.read_bytes(), before_plan)
            self.assertEqual(board.read_bytes(), before_board)

    def test_apply_rechecks_the_exact_source_after_the_dry_run(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "shadow_plan_cli", ROOT / "scripts" / "shadow-plan.py"
        )
        assert spec and spec.loader
        cli = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cli
        spec.loader.exec_module(cli)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            home = root / "home"
            plan_path = home / ".shadow" / "plans" / "alpha" / "PLAN.md"
            plan_path.parent.mkdir(parents=True)
            source = plan("alpha", "~aa11").encode("utf-8")
            plan_path.write_bytes(source)
            archive = plan_path.parent / "docs" / "plan-archive" / "old-work.md"
            archive.parent.mkdir(parents=True)
            archive.write_text("# Old work\n", encoding="utf-8")
            expected = hashlib.sha256(source).hexdigest()
            raced = plan(
                "alpha",
                "~aa11",
                padding="- 2026-08-12T00:02:00Z DECISION race the migration\n",
            ).encode("utf-8")
            self.assertNotEqual(raced, source)
            original = cli.store.dry_run_migration

            def race(target, *, board):
                report = original(target, board=board)
                plan_path.write_bytes(raced)
                return report

            with mock.patch.dict(os.environ, {"HOME": str(home)}), mock.patch.object(
                cli.store, "dry_run_migration", side_effect=race
            ):
                with self.assertRaisesRegex(
                    cli.PlanStoreError, "migration source digest changed"
                ):
                    cli._apply(plan_path, None, expected)

            self.assertEqual(plan_path.read_bytes(), raced)
            self.assertFalse((plan_path.parent / "PLAN.d").exists())

    def test_git_apply_and_rollback_commit_the_root_and_objects_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init", "--quiet"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Plan Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "plan@example.invalid"], check=True)
            plan_path = repo / "PLAN.md"
            before_plan = plan("alpha", "~aa11").encode("utf-8")
            plan_path.write_bytes(before_plan)
            archive = repo / "docs" / "plan-archive" / "old-work.md"
            archive.parent.mkdir(parents=True)
            archive.write_text("# Old work\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "--quiet", "-m", "seed"], check=True)
            report = scale._store.dry_run_migration(plan_path, board=None)

            applied = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "shadow-plan.py"),
                    "migrate",
                    str(plan_path),
                    "--apply",
                    "--expect",
                    report.source_sha256,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            payload = json.loads(applied.stdout or "{}")
            self.assertEqual(applied.returncode, 0, (applied.stderr, payload))
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(repo), "status", "--porcelain=v1"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout,
                "",
            )
            changed = subprocess.run(
                ["git", "-C", str(repo), "show", "--pretty=", "--name-only", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            self.assertIn("PLAN.md", changed)
            self.assertIn("PLAN.d/objects/sha256/", changed)

            rolled_back = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "shadow-plan.py"),
                    "rollback",
                    str(plan_path),
                    "--expect",
                    payload["root_sha256"],
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(rolled_back.returncode, 0, rolled_back.stderr)
            self.assertEqual(plan_path.read_bytes(), before_plan)
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(repo), "status", "--porcelain=v1"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout,
                "",
            )

    def test_dry_run_is_lossless_rebuildable_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "PLAN.md"
            content = plan("alpha", "~aa11", padding="- extra history\n")
            source.write_text(content, encoding="utf-8")
            archive = root / "docs" / "plan-archive" / "old-work.md"
            archive.parent.mkdir(parents=True)
            archive.write_text("# Old work\n", encoding="utf-8")
            before = {
                path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in root.rglob("*") if path.is_file()
            }

            report = scale._store.dry_run_migration(source, board=None)

            after = {
                path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in root.rglob("*") if path.is_file()
            }
            self.assertEqual(after, before)
            self.assertTrue(report.exact_materialization)
            self.assertTrue(report.routes_rebuilt)
            self.assertEqual(report.query_mismatches, ())
            self.assertEqual(report.writes, 0)

    def test_dry_run_refuses_duplicate_and_dangling_row_graphs(self) -> None:
        duplicate = plan("alpha", "~aa11").replace(
            "delivery is proven ~zz99", "delivery is proven ~aa11"
        )
        dangling = plan("alpha", "~aa11").replace(
            "needs: ~aa11", "needs: ~nope"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "PLAN.md"
            archive = root / "docs" / "plan-archive" / "old-work.md"
            archive.parent.mkdir(parents=True)
            archive.write_text("# Old work\n", encoding="utf-8")
            source.write_text(duplicate, encoding="utf-8")
            with self.assertRaisesRegex(scale._store.PlanStoreError, "duplicate row id"):
                scale._store.dry_run_migration(source, board=None)
            source.write_text(dangling, encoding="utf-8")
            with self.assertRaisesRegex(scale._store.PlanStoreError, "needs target ~nope"):
                scale._store.dry_run_migration(source, board=None)


class GitBoundaryIsSanitized(unittest.TestCase):
    """The migration verb's probes and mutations answer about the true repo."""

    def _cli(self):
        spec = importlib.util.spec_from_file_location(
            "shadow_plan_cli", ROOT / "scripts" / "shadow-plan.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def test_git_probe_ignores_a_redirect(self) -> None:
        cli = self._cli()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            decoy = root / "decoy"
            decoy.mkdir()
            subprocess.run(["git", "init", "-q", str(decoy)], check=True)
            with mock.patch.dict(
                os.environ,
                {"GIT_DIR": str(decoy / ".git"), "GIT_WORK_TREE": str(decoy)},
                clear=False,
            ):
                out = cli._git(repo, "rev-parse", "--show-toplevel").stdout.decode().strip()
            self.assertEqual(Path(out), repo)

    def test_a_missing_git_binary_is_a_refusal_not_a_traceback(self) -> None:
        cli = self._cli()
        with mock.patch.object(
            cli.subprocess, "run", side_effect=FileNotFoundError("git")
        ):
            with self.assertRaisesRegex(cli.PlanStoreError, "git is not available"):
                cli._git(Path("/anywhere"), "status")


if __name__ == "__main__":
    unittest.main()
