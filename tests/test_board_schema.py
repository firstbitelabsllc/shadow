"""One closed board decoder shared by mutation and confined read-only consumers."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import shadow_board_schema as schema


class BoardSchemaTests(unittest.TestCase):
    def test_decoder_refuses_duplicate_keys_unknown_fields_and_invalid_utf8(self):
        value = {"schema": "shadow.root-board.v2", "revision": 0,
                 "projects": [], "entities": [], "claims": [], "huddles": []}
        self.assertEqual(schema.decode_board_bytes(json.dumps(value).encode()), value)
        for data in (b'{"schema":"shadow.root-board.v2","schema":"shadow.root-board.v1"}',
                     b"\xff", json.dumps(value | {"secret": "no"}).encode()):
            with self.subTest(data=data), self.assertRaises(schema.BoardError):
                schema.decode_board_bytes(data)

    def test_decoder_imports_no_mutation_modules(self):
        result = subprocess.run([sys.executable, "-I", "-B", "-c",
            "import sys; sys.path.insert(0, sys.argv[1]); import shadow_board_schema; "
            "assert not any(name in sys.modules for name in "
            "('shadow_root_board','shadow_remote_claim','shadow_plan_store','subprocess'))",
            str(ROOT / "scripts")], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_root_reuses_the_decoder_instead_of_a_parallel_validator(self):
        import shadow_root_board as board
        self.assertIs(board._validate, schema.validate_board)
        self.assertIs(board.BoardError, schema.BoardError)
        self.assertIs(board._validate_huddles, schema._validate_huddles)
        tree = ast.parse((ROOT / "scripts" / "shadow_root_board.py").read_text())
        functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        schema_owned = {
            "well_formed_proof_origin", "normalized_origin", "validate_owner",
            "_validate_v1", "_validate_write_scope", "_validate_repository_binding",
            "_claim_ref", "_terminal_ref", "_valid_claim_ref", "_claim_key",
            "_claim_rank", "_path_overlap", "_same_repository", "_scope_edge",
            "claim_holds", "_validate_huddle_reference", "_closed", "_enum",
            "_digest", "_reference_list", "_bid_digest", "_scope_subset",
            "_validate_bids", "_validate_transfer", "_validate_remote_transition",
            "_validate_resolution", "_validate_huddles", "_validate_v2", "_validate",
            "_strict_json_object", "_timestamp", "decode_board_bytes",
        }
        self.assertFalse(functions & schema_owned, functions & schema_owned)
        self.assertFalse({name for name in functions if name.startswith("_legacy_")})

    def test_remote_ref_uses_same_single_formatter(self):
        import shadow_remote_claim as remote
        self.assertIs(remote.claim_ref, schema.claim_ref)
        self.assertEqual(schema.claim_ref("a" * 64, "~ab12"),
                         "refs/heads/shadow/claims/v1/" + "a" * 64 + "/ab12")
        with self.assertRaises(ValueError):
            schema.claim_ref("a" * 64, "~AB12")
