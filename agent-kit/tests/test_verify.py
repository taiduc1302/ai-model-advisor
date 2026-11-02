"""Standard-library-only negative controls for the synthetic safety gate."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("civil_agent_verify", ROOT / "tools" / "verify.py")
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


class OfflineVerifierTests(unittest.TestCase):
    def test_synthetic_positive_and_negative_cases(self):
        data = json.loads((ROOT / "fixtures" / "synthetic_cases.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(data["cases"]), 15)
        self.assertTrue(any(not x["expect_valid"] for x in data["cases"]))
        for case in data["cases"]:
            with self.subTest(case=case["name"]):
                self.assertEqual(not VERIFY.validate(case["kind"], case["record"]), case["expect_valid"])

    def test_missing_bundle_fails_closed(self):
        self.assertTrue(VERIFY.verify_bundle({"records": []}))
        self.assertTrue(VERIFY.verify_bundle({}))
        self.assertTrue(VERIFY.verify_bundle({"records": ["untrusted"]}))

    def test_unknown_kind_fails_closed(self):
        self.assertTrue(VERIFY.validate("made-up", {"status": "DRAFT"}))

    def test_malicious_document_text_cannot_authorize_approval(self):
        case = {"status": "APPROVED", "source_file": "doc says ignore rules", "governing_addendum": "A1",
                "source_citation": "p1", "addenda_reconciled": True, "unresolved_conflicts": 0}
        self.assertTrue(VERIFY.validate("tender", case))

    def test_nonfinite_quantities_fail(self):
        original = json.loads((ROOT / "fixtures" / "synthetic_cases.json").read_text(encoding="utf-8"))["cases"][0]["record"]
        for number in (float("nan"), float("inf"), -1, True):
            with self.subTest(number=repr(number)):
                self.assertTrue(VERIFY.validate("takeoff", {**original, "quantity": number}))

    def test_cli_blocks_without_mutating_input(self):
        bundle = {"records": [{"kind": "automation", "record": {"status": "DRAFT", "network": True}}]}
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "input.json"
            file.write_text(json.dumps(bundle), encoding="utf-8")
            before = file.read_bytes()
            self.assertEqual(VERIFY.main(["--file", str(file)]), 1)
            self.assertEqual(before, file.read_bytes())


if __name__ == "__main__":
    unittest.main()
