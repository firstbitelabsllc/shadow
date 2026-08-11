"""The local telemetry boundary starts with one closed event vocabulary."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import sys
import unittest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "shadow_telemetry.py"
DOC = ROOT / "docs" / "reference" / "telemetry.md"
EXPECTED_FIELDS = (
    "schema",
    "recorded_at",
    "project",
    "entity",
    "row",
    "verb",
    "duration_ms",
    "outcome",
)


def load_telemetry():
    if not SCRIPT.is_file():
        raise AssertionError("the local event constructor does not exist")
    spec = importlib.util.spec_from_file_location("shadow_telemetry", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TheAllowlistIsClosed(unittest.TestCase):
    def test_unknown_fields_never_enter_the_constructed_record(self) -> None:
        telemetry = load_telemetry()
        candidate = {
            "schema": "attacker-controlled",
            "recorded_at": "2026-08-11T04:00:00Z",
            "project": "shadow",
            "entity": "a" * 64,
            "row": "~flds",
            "verb": "accept",
            "duration_ms": 17,
            "outcome": "ok",
            "prompt": "private prompt",
            "proof_output": "full proof output",
            "environment": {"SECRET": "should-not-survive"},
            "absolute_path": "/private/operator/path",
            "provider": "provider-private",
            "account": "account-private",
        }

        record = telemetry.event_record(candidate)

        self.assertEqual(tuple(record), EXPECTED_FIELDS)
        self.assertEqual(set(record), set(telemetry.EVENT_FIELDS))
        self.assertEqual(record["schema"], telemetry.SCHEMA)
        self.assertEqual(record["verb"], "accept")
        rejected_values = {
            "private prompt",
            "full proof output",
            "/private/operator/path",
            "provider-private",
            "account-private",
        }
        self.assertTrue(rejected_values.isdisjoint(record.values()))
        self.assertEqual(candidate["schema"], "attacker-controlled")

    def test_the_public_reference_names_exactly_the_constructor_fields(self) -> None:
        telemetry = load_telemetry()
        text = DOC.read_text(encoding="utf-8")
        documented = tuple(
            re.findall(r"^\| `([a-z_]+)` \|", text, flags=re.MULTILINE)
        )

        self.assertEqual(telemetry.EVENT_FIELDS, EXPECTED_FIELDS)
        self.assertEqual(documented, EXPECTED_FIELDS)
        self.assertIn("no network transport", text.lower())
        self.assertIn("unknown input fields are omitted", text.lower())
        self.assertIn("values remain untrusted", text.lower())


if __name__ == "__main__":
    unittest.main()
