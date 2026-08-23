from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import sys
import unittest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from shadow_version import read_version  # noqa: E402

VERSION = read_version(ROOT)


def read_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class DistributionContractTests(unittest.TestCase):
    def test_portable_manifests_share_one_identity_and_version(self) -> None:
        for relative in (
            "plugins/shadow/plugin.json",
            "plugins/shadow/.codex-plugin/plugin.json",
            "plugins/shadow/.claude-plugin/plugin.json",
        ):
            manifest = read_json(relative)
            self.assertEqual(manifest["name"], "shadow", relative)
            self.assertEqual(manifest["version"], VERSION, relative)

    def test_marketplaces_resolve_to_the_portable_package(self) -> None:
        codex = read_json(".agents/plugins/marketplace.json")
        codex_path = codex["plugins"][0]["source"]["path"]
        self.assertEqual(PurePosixPath(codex_path).as_posix(), "plugins/shadow")
        self.assertTrue((ROOT / codex_path).is_dir())

        claude = read_json(".claude-plugin/marketplace.json")
        claude_path = claude["plugins"][0]["source"]
        self.assertEqual(PurePosixPath(claude_path).as_posix(), "plugins/shadow")
        self.assertTrue((ROOT / claude_path).is_dir())

    def test_portable_package_ships_the_front_door_and_the_goal_compiler(self) -> None:
        # One install of the shadow plugin carries both skills; the goal
        # compiler is not a second package or a loose mount.
        skills_root = ROOT / "plugins/shadow/skills"
        skills = sorted(
            path.relative_to(skills_root).as_posix()
            for path in skills_root.rglob("SKILL.md")
        )
        self.assertEqual(skills, ["amplify/SKILL.md", "shadow/SKILL.md"])
        self.assertTrue((skills_root / "amplify/references/amplify.md").is_file())

    def test_hosted_coach_never_claims_local_authority(self) -> None:
        coach = (ROOT / "distribution/custom-gpt/instructions.md").read_text(
            encoding="utf-8"
        ).lower()
        portable = (ROOT / "plugins/shadow/skills/shadow/SKILL.md").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("cannot see the person's local shadow board", coach)
        self.assertIn("do not add an action or app", coach)
        self.assertIn("coach mode", portable)
        self.assertIn("do not create a parallel task list", portable)

    def test_portable_skill_keeps_cold_resume_on_the_bounded_seat_view(self) -> None:
        portable = (ROOT / "plugins/shadow/skills/shadow/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("`shadow status --by <seat>`", portable)
        self.assertIn("Do not request `--json`", portable)
        self.assertIn("full portfolio", " ".join(portable.split()))
        operator = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`shadow status --by <seat>`", operator)
        self.assertNotIn("shadow status --json --by <seat>", operator)

    def test_distribution_does_not_publish_a_placeholder_transport(self) -> None:
        forbidden_names = {"server.json", "mcp.json"}
        distributed = {
            path.name
            for root in (ROOT / "plugins", ROOT / "distribution")
            for path in root.rglob("*")
            if path.is_file()
        }
        self.assertTrue(forbidden_names.isdisjoint(distributed))

    def test_front_door_keeps_machinery_backstage_and_never_templates(self) -> None:
        # The portable skill talks like a teammate: machinery stays backstage,
        # no fixed response shape, protected moves pause conversationally,
        # and a done claim is separated from the next useful proof.
        skill = (ROOT / "plugins/shadow/skills/shadow/SKILL.md").read_text(
            encoding="utf-8"
        )
        normalized = " ".join(skill.split())
        for phrase in (
            "Keep routing, rows, receipts, and tool mechanics backstage",
            "never a fixed response template",
            "one durable board per computer",
            "the exact reply that unlocks it",
            "Do not make them pick from a ritualized menu",
            "Separate a useful next proof from a claim that the work is done",
        ):
            self.assertIn(phrase, normalized)
        for template_tell in ("1. What are we trying to change", "status card template"):
            self.assertNotIn(template_tell, normalized)


if __name__ == "__main__":
    unittest.main()
