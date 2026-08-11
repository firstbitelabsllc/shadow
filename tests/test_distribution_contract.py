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
        self.assertIn("never create a second task list", portable)

    def test_distribution_does_not_publish_a_placeholder_transport(self) -> None:
        forbidden_names = {"server.json", "mcp.json"}
        distributed = {
            path.name
            for root in (ROOT / "plugins", ROOT / "distribution")
            for path in root.rglob("*")
            if path.is_file()
        }
        self.assertTrue(forbidden_names.isdisjoint(distributed))

    def test_human_brief_hides_machine_detail_until_requested(self) -> None:
        skill = (ROOT / "plugins/shadow/skills/shadow/SKILL.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "What are we trying to change for a person?",
            "What is already moving, including work happening in parallel?",
            "technical evidence on demand",
            "Distinguish the next evidence checkpoint from product",
        ):
            self.assertIn(phrase, skill)


if __name__ == "__main__":
    unittest.main()
