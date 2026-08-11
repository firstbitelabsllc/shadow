from __future__ import annotations

from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "distribution/chatgpt-app"


class ChatGPTAppContractTests(unittest.TestCase):
    def test_exactly_two_read_only_coaching_tools_ship(self) -> None:
        source = (APP / "src/server.ts").read_text(encoding="utf-8")
        self.assertEqual(source.count("server.registerTool("), 2)
        self.assertIn('"get_shadow_brief_contract"', source)
        self.assertIn('"get_shadow_goal_contract"', source)
        self.assertIn("readOnlyHint: true", source)
        self.assertIn("destructiveHint: false", source)
        for mutation in ("create_task", "update_task", "claim_work", "complete_work"):
            self.assertNotIn(mutation, source)

    def test_bridge_has_no_storage_or_private_board_binding(self) -> None:
        config = (APP / "wrangler.jsonc").read_text(encoding="utf-8")
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((APP / "src").glob("*.ts"))
        )
        for forbidden in (
            "DurableObject",
            "kv_namespaces",
            "d1_databases",
            "r2_buckets",
            "queues",
            "~/.shadow",
            "process.env",
        ):
            self.assertNotIn(forbidden, config + source)

    def test_reader_first_contract_keeps_machine_detail_last(self) -> None:
        contract = (APP / "src/contracts.ts").read_text(encoding="utf-8")
        verdict = contract.index("## Verdict")
        technical = contract.index("technical evidence appendix")
        self.assertLess(verdict, technical)
        for heading in (
            "## Decided for you",
            "## Architecture decisions you need to know about",
            "## Questions to challenge your point of view",
            "## ETAs and confidence",
            "## Lanes that are stalling",
            "## Evidence and blind spots",
        ):
            self.assertIn(heading, contract)

    def test_worker_is_current_stateless_transport(self) -> None:
        package = json.loads((APP / "package.json").read_text(encoding="utf-8"))
        config = (APP / "wrangler.jsonc").read_text(encoding="utf-8")
        source = (APP / "src/server.ts").read_text(encoding="utf-8")
        self.assertEqual(package["dependencies"]["@modelcontextprotocol/server"], "2.0.0")
        self.assertIn('"compatibility_date": "2026-08-11"', config)
        self.assertIn('"nodejs_compat"', config)
        self.assertIn("createMcpHandler", source)
        self.assertNotIn("McpAgent", source)


if __name__ == "__main__":
    unittest.main()
