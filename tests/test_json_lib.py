"""The canonical JSON form: sorted, indented, one trailing newline."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from shadow_json_lib import json_text  # noqa: E402


class JsonTextTests(unittest.TestCase):
    def test_canonical_form_is_stable(self) -> None:
        self.assertEqual(
            json_text({"b": 1, "a": [2, {"z": True, "y": None}]}),
            '{\n  "a": [\n    2,\n    {\n      "y": null,\n      "z": true\n    }\n  ],\n  "b": 1\n}\n',
        )

    def test_keys_are_sorted_at_every_depth(self) -> None:
        text = json_text({"b": {"d": 1, "c": 2}, "a": 0})
        self.assertLess(text.index('"a"'), text.index('"b"'))
        self.assertLess(text.index('"c"'), text.index('"d"'))


if __name__ == "__main__":
    unittest.main()
