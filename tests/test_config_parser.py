from __future__ import annotations

import sys
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import shadow_config


def write_local_config(root: Path, text: str) -> Path:
    subprocess.run(["git", "-C", str(root), "init", "--quiet"], check=True)
    exclude = root / ".git/info/exclude"
    with exclude.open("a", encoding="utf-8") as stream:
        stream.write("/.shadow/local.yaml\n")
    config = root / ".shadow/local.yaml"
    config.parent.mkdir(exist_ok=True)
    config.write_text(text, encoding="utf-8")
    return config


class ConfigParserTests(unittest.TestCase):
    def test_absent_config_returns_a_fresh_behavior_equivalent_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = shadow_config.load_config(root)
            second = shadow_config.load_config(root)
        self.assertEqual(first, shadow_config.DEFAULT_CONFIG)
        self.assertIsNot(first, shadow_config.DEFAULT_CONFIG)
        self.assertIsNot(first["method"], shadow_config.DEFAULT_CONFIG["method"])
        self.assertEqual(second, shadow_config.DEFAULT_CONFIG)

    def test_subset_parses_reviewed_nested_mapping_list_and_scalar_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_local_config(
                root,
                """version: 1
leads:
  codex:
    display_name: Codex
    default_lenses:
      - integration
      - crash_recovery
method:
  adversarial_lenses:
    - assumptions
    - privacy
buckets:
  taste: taste
durability:
  claim_return_minutes: 120
""",
            )
            loaded = shadow_config.load_config(root)
        self.assertEqual(loaded["version"], 1)
        self.assertEqual(loaded["leads"]["codex"]["display_name"], "Codex")
        self.assertEqual(
            loaded["leads"]["codex"]["default_lenses"],
            ["integration", "crash_recovery"],
        )
        self.assertEqual(loaded["method"]["adversarial_lenses"], ["assumptions", "privacy"])
        self.assertEqual(loaded["buckets"]["taste"], "taste")
        self.assertEqual(loaded["durability"]["claim_return_minutes"], 120)

    def test_repo_root_config_is_found_from_a_nested_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = write_local_config(root, "version: 1\n")
            nested = root / "a" / "b"
            nested.mkdir(parents=True)
            self.assertEqual(shadow_config.find_config(nested), config.resolve())
            self.assertEqual(shadow_config.load_config(nested)["version"], 1)

    def test_unknown_keys_are_available_to_the_later_schema_validator(self) -> None:
        parsed = shadow_config.parse_config("provider: forbidden-later\n", Path("fixture.yaml"))
        self.assertEqual(parsed, {"provider": "forbidden-later"})

    def test_subset_refuses_unsupported_or_malformed_yaml_with_file_and_line(self) -> None:
        cases = {
            "flow.yaml": ("method: [assumptions]\n", 1),
            "indent.yaml": ("method:\n   adversarial_lenses:\n    - assumptions\n", 2),
            "list-map.yaml": ("leads:\n  - name: codex\n", 2),
            "duplicate.yaml": ("version: 1\nversion: 2\n", 2),
            "missing.yaml": ("method:\n", 1),
            "tab.yaml": ("method:\n\tadversarial_lenses: no\n", 2),
        }
        for name, (text, line) in cases.items():
            with self.subTest(name=name):
                path = Path(name)
                with self.assertRaises(shadow_config.ConfigError) as raised:
                    shadow_config.parse_config(text, path)
                self.assertEqual(raised.exception.path, path)
                self.assertEqual(raised.exception.line, line)
                self.assertTrue(str(raised.exception).startswith(f"{path}:{line}: "))


if __name__ == "__main__":
    unittest.main()
