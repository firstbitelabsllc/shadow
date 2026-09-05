"""Admission logic fixtures do not claim real quota exhaustion."""
import importlib.util
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import shadow_execution_policy as policy

SPEC = importlib.util.spec_from_file_location(
    "openrouter_admission", Path(__file__).resolve().parents[1] / "scripts/dev/openrouter-admission.py")
admission = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(admission)


class AdmissionTests(unittest.TestCase):
    def evidence(self, work_class="coding"):
        return [{"host": host, "work_class": work_class, "model": policy.resolve_route(host, work_class).model,
                 "observed_at": 1000, "expires_at": 1100, "reason": "quota", "evidence_sha256": "a" * 64}
                for host in policy.HOSTS]

    def test_explicit_selection_and_complete_unavailability(self):
        self.assertEqual(admission.admit("coding", "explicit", [], now=1010)["admission"], "explicit")
        records = self.evidence()
        random.Random(42).shuffle(records)
        self.assertEqual(admission.admit("coding", "unavailable", records, now=1010)["admission"], "unavailable")

    def test_every_missing_route_refuses(self):
        records = self.evidence()
        for i in range(len(records)):
            with self.subTest(host=records[i]["host"]), self.assertRaises(admission.Refused):
                admission.admit("coding", "unavailable", records[:i] + records[i+1:], now=1010)

    def test_stale_wrong_class_wrong_model_and_unattributed_evidence_refuse(self):
        for field, value in (("observed_at", 1011), ("observed_at", True), ("expires_at", 1009),
                             ("expires_at", 99999), ("work_class", "planning"), ("model", "wrong"),
                             ("reason", "host_failed"), ("evidence_sha256", "")):
            records = self.evidence()
            records[0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(admission.Refused):
                admission.admit("coding", "unavailable", records, now=1010)
        with self.assertRaises(admission.Refused):
            admission.admit("coding", "unavailable", self.evidence() + [self.evidence()[0]], now=1010)

    def test_evidence_does_not_change_explicit_user_selection(self):
        with self.assertRaises(admission.Refused):
            admission.admit("coding", "explicit", self.evidence(), now=1010)
        with self.assertRaises(admission.Refused):
            admission.admit("unknown", "explicit", [], now=1010)


if __name__ == "__main__":
    unittest.main()
