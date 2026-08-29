"""Keep the share-ready README and public help tied to real Shadow surfaces."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHADOW = ROOT / "bin" / "shadow"


class ShareReadyDocumentationTests(unittest.TestCase):
    def test_readme_leads_with_authority_loop_and_install(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        required = (
            "assets/shadow-banner.svg",
            "PLAN.md",
            "shadow init --here",
            "shadow status",
            "shadow accept",
            "--proposal",
            "shadow doctor",
            "install.sh",
            "--branch shadow-v1.3.0",
        )
        for phrase in required:
            self.assertIn(phrase, text)
        # The board's authority is per computer, and the work is durable across
        # a killed chat: the two claims a stranger must read before installing.
        self.assertRegex(text, r"one\s+board per computer")
        self.assertIn("one authoritative `PLAN.md` per independently", text)
        self.assertIn("project map", text)
        self.assertNotIn("one `PLAN.md` per project", text)
        self.assertIn("durable", text)
        self.assertIn("2-7 tasks", text)
        self.assertNotIn("one task with its proof", text)
        self.assertNotIn("npm test", text)
        self.assertNotIn("/Users/", text)
        config = (ROOT / "docs" / ".vitepress" / "config.ts").read_text(
            encoding="utf-8"
        )
        self.assertIn("authoritative PLAN.md per entity", config)
        self.assertIn("/reference/project-maps", config)
        self.assertNotIn("PLAN.md per project", config)
        generation = (ROOT / "claudux.json").read_text(encoding="utf-8")
        self.assertIn("authoritative PLAN.md per entity", generation)
        self.assertIn("project maps", generation)
        self.assertNotIn("PLAN.md per project", generation)

        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Every Shadow chat response ends with a compact `Ongoing tasks` projection", skill)
        self.assertIn("shadow status --in-flight --json", skill)

    def test_every_shipped_install_tag_tracks_version(self) -> None:
        """The guide pages pinned shadow-v1.0.1 — a tag that never existed —
        for two releases because only the README's tag was contract-tested.
        Every install tag in the shipped doc set must name the current
        VERSION; historical dev docs (plan-archive, superpowers) are exempt."""
        import re as _re

        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        expected = f"shadow-v{version}"
        shipped = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
        for path in shipped:
            relative = path.relative_to(ROOT).as_posix()
            if relative.startswith(("docs/plan-archive/", "docs/superpowers/")):
                continue
            for tag in _re.findall(r"--branch (shadow-v[0-9][0-9.]*)", path.read_text(encoding="utf-8")):
                self.assertEqual(tag, expected, f"{relative} pins {tag}, VERSION is {version}")

    def test_the_footer_projection_contract_stays_written_down(self) -> None:
        """The README sends detail to the docs site, so the host-facing footer
        contract must stay stated where hosts and strangers actually read it."""
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        quickstart = (ROOT / "docs" / "guide" / "quickstart.md").read_text(encoding="utf-8")
        for text in (skill, quickstart):
            self.assertIn("shadow status --in-flight --json", text)
            self.assertIn("Ongoing tasks", text)
            self.assertIn("Active tasks: none", text)
            self.assertIn("one bounded next move", text)
            self.assertIn("does not enumerate every reachable or waiting row", text)
        self.assertNotIn("group other reachable or waiting work", skill)

    def test_project_map_contract_keeps_one_authority_per_fact(self) -> None:
        text = (ROOT / "docs" / "reference" / "project-maps.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "Board membership is the project map",
            "`needs:` is deliberately plan-local",
            "Do not split a live authority in place",
            "There is no project-map file",
            "`- Plans: plans/*/PLAN.md`",
            "`shadow lint PLAN.md plans/<entity>/PLAN.md`",
            "`shadow status --root <portfolio-root> --by <seat>`",
            "shadow plan map-migrate /ABS/PLAN.md --dry-run",
            "shadow plan map-rollback /ABS/PLAN.md --apply",
            "verified local-only",
            "Routing is derived from that target-plan membership",
            "receipt remains byte-identical after success",
            "rerun the same apply command",
            "rerun the same rollback command",
            "remain only in the producer plan",
        ):
            self.assertIn(phrase, text)
        self.assertNotIn("project-map.json` is canonical", text)
        self.assertNotIn("shadow lint --repo . PLAN.md", text)
        self.assertNotIn("--row-map", text)

        commands = (ROOT / "docs" / "reference" / "commands.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "`--root` instead changes the bounded discovery root and reconciles "
            "those entity-plan pointers into the board",
            commands,
        )
        self.assertIn("Routing derives from exact target-plan membership", commands)

        help_text = (ROOT / "bin" / "shadow").read_text(encoding="utf-8")
        self.assertNotIn("--row-map", help_text)
        self.assertIn("same apply command resumes safely", help_text)
        self.assertIn("same rollback command also resumes", help_text)
        self.assertNotIn("never bypasses or writes the board", commands)

        grammar = (ROOT / "docs" / "reference" / "grammar.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("only dependency edge and dependency-readiness", grammar)
        self.assertIn("not agent-takeable", grammar)
        self.assertNotIn("`needs: ~hash[, ~hash]` is the only readiness gate", grammar)

    def test_the_two_seat_harness_stays_written_down(self) -> None:
        commands = (ROOT / "docs" / "reference" / "commands.md").read_text(encoding="utf-8")
        self.assertIn("scripts/shadow-verify-two-seat.py", commands)
        self.assertIn("--live --goal-file", commands)
        host = (ROOT / "docs" / "reference" / "host-integration.md")
        self.assertTrue(host.is_file(), "host integration detail must have a documented home")

    def test_quickstart_has_a_real_claim_and_close_loop(self) -> None:
        text = (ROOT / "docs" / "guide" / "quickstart.md").read_text(encoding="utf-8")
        for phrase in (
            "shadow init --here",
            # `shadow init --here` writes the machine-local plan under
            # ~/.shadow/plans/<project>/, so the quickstart must open and lint
            # that printed path with this checkout as its source.
            "$EDITOR ~/.shadow/plans/<project>/PLAN.md",
            "shadow lint --repo . ~/.shadow/plans/<project>/PLAN.md",
            "shadow status --by",
            "shadow throw",
            "shadow amp",
            "shadow accept",
            "shadow return",
            "shadow status --in-flight --json",
        ):
            self.assertIn(phrase, text)
        self.assertNotIn("proof: cmd npm test", text)
        # Never send a reader back to a repo-root PLAN.md: no such file exists.
        self.assertNotIn("shadow lint PLAN.md", text)
        host_example = text.split("## 3. Work through a bounded host", 1)[1].split(
            "## 4. Close the loop", 1
        )[0]
        self.assertIn("--work-class coding", host_example)
        self.assertIn("--delegation direct", host_example)

    def test_acceptance_docs_describe_the_proof_boundary(self) -> None:
        quickstart = (ROOT / "docs" / "guide" / "quickstart.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("proof argv cds there itself", quickstart)
        self.assertIn(
            "detached checkout as its initial working directory",
            quickstart,
        )
        self.assertIn(
            "rechecks detached HEAD after the proof",
            " ".join(quickstart.split()),
        )
        skill_text = " ".join(
            (ROOT / "SKILL.md").read_text(encoding="utf-8").split()
        )
        self.assertIn("does not confine the trusted proof process", skill_text)

    def test_public_help_is_quiet_and_advertises_supported_flags(self) -> None:
        top_level = subprocess.run(
            [str(SHADOW), "--help"], cwd=ROOT,
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(top_level.returncode, 0, top_level.stderr)
        self.assertEqual("", top_level.stderr)
        self.assertTrue(
            top_level.stdout.startswith(
                "shadow — one local computer board coordinating entity plans and proof\n"
            ),
            top_level.stdout,
        )
        self.assertNotIn("project plan", top_level.stdout.casefold())
        self.assertNotIn("project-plan", top_level.stdout.casefold())
        self.assertNotIn("project pointer", top_level.stdout.casefold())

        verbs = (
            "browse", "status", "init", "lint", "goal", "amp", "throw",
            "return", "priority", "accept", "lifecycle", "read", "host", "slots",
            "doctor",
        )
        for verb in verbs:
            result = subprocess.run(
                [str(SHADOW), "help", verb], cwd=ROOT,
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, f"{verb}: {result.stderr}")
            self.assertEqual("", result.stderr, f"{verb} wrote noisy help output")
            self.assertTrue(result.stdout.strip(), f"{verb} has no help text")

        status = subprocess.run(
            [str(SHADOW), "help", "status"], cwd=ROOT,
            capture_output=True, text=True, check=False,
        )
        self.assertIn("--shadowed", status.stdout)

        goal = subprocess.run(
            [str(SHADOW), "help", "goal"], cwd=ROOT,
            capture_output=True, text=True, check=False,
        )
        self.assertIn("--install|--remove", goal.stdout)
        self.assertIn("--host HOST", goal.stdout)

        throw = subprocess.run(
            [str(SHADOW), "help", "throw"], cwd=ROOT,
            capture_output=True, text=True, check=False,
        )
        self.assertIn("entity-plan pointer", throw.stdout)
        self.assertIn("entity plan mid-merge", throw.stdout)
        self.assertNotIn("project pointer", throw.stdout)
        self.assertNotIn("project plan", throw.stdout)

        live_throw = subprocess.run(
            [str(SHADOW), "throw", "--help"], cwd=ROOT,
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(live_throw.returncode, 0, live_throw.stderr)
        self.assertIn("checkpoint row from one entity plan", live_throw.stdout)
        self.assertNotIn("project-plan row", live_throw.stdout)

        priority = subprocess.run(
            [str(SHADOW), "help", "priority"], cwd=ROOT,
            capture_output=True, text=True, check=False,
        )
        self.assertIn("without rewriting any entity PLAN.md", priority.stdout)
        self.assertNotIn("project PLAN.md", priority.stdout)

        accept = subprocess.run(
            [str(SHADOW), "help", "accept"], cwd=ROOT,
            capture_output=True, text=True, check=False,
        )
        self.assertIn(
            "--entity ID --repo PATH --row '~hash' --by OWNER",
            accept.stdout,
        )
        self.assertIn("machine-local entity plan", accept.stdout)
        self.assertIn("verified committed HEAD", accept.stdout)
        self.assertIn("does not confine", accept.stdout)
        self.assertIn("--proposal", accept.stdout)

    def test_proposal_acceptance_is_public_and_narrow(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        grammar = (ROOT / "docs" / "reference" / "grammar.md").read_text(
            encoding="utf-8"
        )
        commands = (ROOT / "docs" / "reference" / "commands.md").read_text(
            encoding="utf-8"
        )
        spec = (
            ROOT
            / "docs"
            / "superpowers"
            / "specs"
            / "2026-08-28-proposal-only-acceptance.md"
        ).read_text(encoding="utf-8")

        for text in (readme, grammar, commands):
            self.assertIn("--proposal", text)
            self.assertIn("machine-local", text)
            self.assertIn("sealed Codex", text)
            self.assertIn("Git-backed", text)
        for phrase in (
            "shadow.authority-proposal.v1",
            "shadow.proof-result.v1",
            "marker:",
            "floor:",
            "exact prior plan root",
        ):
            self.assertIn(phrase, grammar)
        for text in (readme, grammar, commands, spec):
            self.assertIn("no-change", text)
            self.assertIn("isolated temporary `HOME`", text)
            self.assertIn("--authority-proposal", text)
        self.assertNotIn('"entity_id": "logical-entity-id"', spec)

    def test_banner_honors_reduced_motion(self) -> None:
        text = (ROOT / "assets" / "shadow-banner.svg").read_text(encoding="utf-8")
        self.assertIn("prefers-reduced-motion: reduce", text)
        self.assertIn("animation: none", text)


class AReadmeAStrangerCanFollow(unittest.TestCase):
    """The README must be followable cold: every word the vocabulary leans on is
    glossed in plain words before the install, and every command it names
    actually exists in the CLI's own help."""

    def test_the_vocabulary_glosses_every_word_it_names(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        section = text.split("## Install", 1)[0]
        for concept in ("board", "plans", "seats", "claim", "proof", "accept"):
            self.assertIn(f"**{concept}**", section, f"the README leans on {concept} but never explains it")
        self.assertIn("claim → work → prove → accept → next", section)

    def test_the_readme_names_only_real_commands(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        help_text = subprocess.run(
            [str(ROOT / "bin" / "shadow"), "--help"], capture_output=True, text=True, check=False
        ).stdout
        import re as _re
        for verb in set(_re.findall(r"(?:`|^|\s)shadow ([a-z-]+)", text, _re.MULTILINE)):
            self.assertIn(f"  {verb} ", help_text, f"README names `shadow {verb}` but the CLI help does not")


if __name__ == "__main__":
    unittest.main()
