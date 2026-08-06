from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "shadow-public-ready-grep-gate.py"
SPEC = importlib.util.spec_from_file_location("public_ready", SCRIPT)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class PublicReadyTests(unittest.TestCase):
    def test_clean_public_text_passes(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            path = root / "README.md"
            path.write_text("Shadow stores bounded local proof.\n", encoding="utf-8")
            report = mod.scan(root, [path], metadata=False)
        self.assertTrue(report["ok"], report)

    def test_private_home_path_fails(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            path = root / "README.md"
            path.write_text("checkout: /" + "Users/realname/secret\n", encoding="utf-8")
            report = mod.scan(root, [path], metadata=False)
        self.assertFalse(report["ok"])
        self.assertEqual(report["findings"][0]["reason"], "private filesystem path")

    def test_secret_shape_fails(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            path = root / "notes.md"
            path.write_text("token: gh" + "p_12345678901234567890\n", encoding="utf-8")
            report = mod.scan(root, [path], metadata=False)
        self.assertFalse(report["ok"])
        self.assertEqual(report["findings"][0]["reason"], "secret-shaped value")

    def test_evidence_stream_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            path = root / "activity.jsonl"
            path.write_text("{}\n", encoding="utf-8")
            report = mod.scan(root, [path], metadata=False)
        self.assertFalse(report["ok"])
        self.assertEqual(report["findings"][0]["reason"], "forbidden release file")

    def test_current_metadata_is_consistent(self) -> None:
        self.assertEqual(mod.metadata_errors(ROOT), [])


if __name__ == "__main__":
    unittest.main()
