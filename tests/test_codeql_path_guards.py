from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "vidux_browser_server_codeql_guards", ROOT / "browser" / "server.py"
)
browser_server = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(browser_server)


class CodeQLPathGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.dev_root = self.root / "Development"
        self.dev_root.mkdir()
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir()
        self.static = self.root / "static"
        self.static.mkdir()

        self.originals = {
            "DEV_ROOT": browser_server.DEV_ROOT,
            "ARTIFACTS_DIR": browser_server.ARTIFACTS_DIR,
            "STATIC_DIR": browser_server.STATIC_DIR,
            "PLAN_GLOBS": browser_server.PLAN_GLOBS,
            "PLANS_CACHE_TTL_SECONDS": browser_server.PLANS_CACHE_TTL_SECONDS,
        }
        browser_server.DEV_ROOT = self.dev_root
        browser_server.ARTIFACTS_DIR = self.artifacts
        browser_server.STATIC_DIR = self.static
        browser_server.PLAN_GLOBS = ["*/projects/*/PLAN.md"]
        browser_server.PLANS_CACHE_TTL_SECONDS = 0
        browser_server.clear_plans_cache()

        self.plan = self.dev_root / "demo" / "projects" / "current" / "PLAN.md"
        self.plan.parent.mkdir(parents=True)
        self.plan.write_text("# Current\n", encoding="utf-8")

    def tearDown(self) -> None:
        for name, value in self.originals.items():
            setattr(browser_server, name, value)
        browser_server.clear_plans_cache()
        self.tmp.cleanup()

    def test_request_text_only_selects_exact_cockpit_discovered_files(self) -> None:
        evidence = self.plan.parent / "evidence" / "receipt.md"
        evidence.parent.mkdir()
        evidence.write_text("# Receipt\n", encoding="utf-8")
        inbox = self.plan.parent / "INBOX.md"
        inbox.write_text("# Inbox\n", encoding="utf-8")

        self.assertEqual(browser_server.safe_resolve(str(self.plan)), self.plan)
        self.assertEqual(browser_server.safe_resolve(str(inbox)), inbox)
        self.assertEqual(browser_server.safe_resolve(str(evidence)), evidence)
        self.assertIsNone(browser_server.safe_resolve("demo/projects/current/PLAN.md"))
        self.assertIsNone(
            browser_server.safe_resolve(
                str(self.plan.parent / ".." / "current" / "PLAN.md")
            )
        )

        alias_dir = self.dev_root / "alias" / "projects" / "current"
        alias_dir.parent.mkdir(parents=True)
        alias_dir.symlink_to(self.plan.parent, target_is_directory=True)
        self.assertIsNone(browser_server.safe_resolve(str(alias_dir / "PLAN.md")))

    def test_catalog_rejects_hard_links_and_static_aliases(self) -> None:
        evidence = self.plan.parent / "evidence" / "receipt.md"
        evidence.parent.mkdir()
        evidence.write_text("# Receipt\n", encoding="utf-8")
        os.link(evidence, evidence.with_name("receipt-copy.md"))
        self.assertIsNone(browser_server.safe_resolve(str(evidence)))

        script = self.static / "app.js"
        script.write_text("export {};\n", encoding="utf-8")
        outside = self.root / "outside.js"
        outside.write_text("outside\n", encoding="utf-8")
        (self.static / "linked.js").symlink_to(outside)
        (self.static / "inside-link.js").symlink_to(script)

        catalog = browser_server._static_file_catalog()
        self.assertEqual(catalog["app.js"], script)
        self.assertNotIn("../outside.js", catalog)
        self.assertNotIn("linked.js", catalog)
        self.assertNotIn("inside-link.js", catalog)

    def test_missing_target_classification_is_lexical_and_canonical(self) -> None:
        missing = self.plan.parent / "evidence" / "missing.md"
        self.assertTrue(browser_server.is_allowed_file_target(str(missing)))
        self.assertFalse(
            browser_server.is_allowed_file_target(
                str(self.plan.parent / "evidence" / ".." / "missing.md")
            )
        )
        self.assertFalse(
            browser_server.is_allowed_file_target(str(self.plan.parent / ".env"))
        )
        self.assertTrue(
            browser_server.is_allowed_file_target(str(self.artifacts / "missing.html"))
        )

    def test_proof_path_regex_handles_long_non_match_without_nested_backtracking(self) -> None:
        adversarial = ("segment/" * 20_000) + "not-a-proof.txt"
        self.assertIsNone(browser_server.PROOF_FILE_RE.search(adversarial))


if __name__ == "__main__":
    unittest.main()
