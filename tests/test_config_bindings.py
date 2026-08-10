from __future__ import annotations

from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
SHADOW = ROOT / "bin" / "shadow"
BUCKETS_SCRIPT = ROOT / "scripts" / "shadow-buckets.py"

_SPEC = importlib.util.spec_from_file_location("shadow_buckets_for_config", BUCKETS_SCRIPT)
assert _SPEC and _SPEC.loader
buckets = importlib.util.module_from_spec(_SPEC)
sys.modules["shadow_buckets_for_config"] = buckets
_SPEC.loader.exec_module(buckets)

PLAN = """# Config bindings

## Brief

- Project: config-bindings
- Mode: ship
- Priority: 2

## Tasks

### Bindings

- tools: taste
- [pending] Run the binding proof ~bind | proof: read receipt -> visible
- [pending] Bindings close ~done (DoD) | proof: read receipt -> visible | needs: ~bind
"""


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


class ConfigBindsTasteDurabilityAndLeads(unittest.TestCase):
    def test_one_file_reaches_the_three_bounded_consumers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            repo = root / "repo"
            repo.mkdir()
            home.mkdir()
            (repo / "PLAN.md").write_text(PLAN, encoding="utf-8")
            git(repo, "init", "--quiet")
            git(repo, "config", "user.email", "shadow-test@example.invalid")
            git(repo, "config", "user.name", "Shadow Test")
            git(repo, "add", "PLAN.md")
            git(repo, "commit", "--quiet", "-m", "seed")
            initialized = subprocess.run(
                [str(SHADOW), "config", "--init-local", "--repo", str(repo)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            (repo / ".shadow/local.yaml").write_text(
                "version: 1\n"
                "leads:\n"
                "  alice:\n"
                "    display_name: Alice Example\n"
                "    default_lenses:\n"
                "      - privacy\n"
                "buckets:\n"
                "  taste: custom-grade\n"
                "durability:\n"
                "  claim_return_minutes: 30\n",
                encoding="utf-8",
            )

            skill = home / ".claude" / "skills" / "custom-grade"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("# custom grade\n", encoding="utf-8")
            taste = next(item for item in buckets.declared() if item["name"] == "taste")
            self.assertEqual(buckets.resolve(taste, home, repo)[0], "pass")

            result = subprocess.run(
                [str(SHADOW), "throw", "--repo", str(repo), "--task", "~bind", "--by", "alice"],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Seat: Alice Example (alice).", result.stdout)
            self.assertIn("Preferred lenses: privacy.", result.stdout)
            self.assertIn("selected: /custom-grade", result.stdout)
            board = json.loads((home / ".shadow" / "board.json").read_text(encoding="utf-8"))
            claim = board["claims"][0]
            claimed = datetime.fromisoformat(claim["claimed_at"].replace("Z", "+00:00"))
            returned = datetime.fromisoformat(claim["return_by"].replace("Z", "+00:00"))
            self.assertEqual(int((returned - claimed).total_seconds()), 30 * 60)

    def test_unknown_and_mistyped_keys_are_never_silently_ignored(self) -> None:
        cases = (
            ("versoin: 1\n", ".shadow/local.yaml:1: unknown configuration key 'versoin'"),
            ("version: 2\n", ".shadow/local.yaml:1: version must be the integer 1"),
            ("durability:\n  claim_return_minutes: soon\n", ".shadow/local.yaml:2: durability.claim_return_minutes"),
            ("leads:\n  alice:\n    display: Alice\n", ".shadow/local.yaml:3: unknown lead preference 'display'"),
        )
        for source, expected in cases:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as directory:
                repo = Path(directory)
                git(repo, "init", "--quiet")
                initialized = subprocess.run(
                    [str(SHADOW), "config", "--init-local", "--repo", str(repo)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(initialized.returncode, 0, initialized.stderr)
                (repo / ".shadow/local.yaml").write_text(source, encoding="utf-8")
                result = subprocess.run(
                    [str(SHADOW), "config", "--explain", "--repo", str(repo)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn(expected, result.stderr)


if __name__ == "__main__":
    unittest.main()
