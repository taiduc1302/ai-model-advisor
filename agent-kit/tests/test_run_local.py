"""Local runner guardrails (do not recursively execute the suite from these tests)."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("civil_agent_run_local", ROOT / "tools" / "run_local.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class RunnerGuardsTests(unittest.TestCase):
    def test_reports_cannot_be_written_to_repo(self):
        for path in (RUNNER.REPO_ROOT / "evidence.json", ROOT / "report.json",
                     RUNNER.REPO_ROOT / ".git" / "report.json"):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    RUNNER.safe_report_path(path)

    def test_reports_can_be_written_outside_repo(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "evidence.json"
            self.assertEqual(RUNNER.safe_report_path(target), target.resolve())

    def test_hash_inventory_covers_active_files(self):
        self.assertEqual(len(RUNNER.CHECKED_FILES), len(set(RUNNER.CHECKED_FILES)))
        for path in RUNNER.CHECKED_FILES:
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file())


if __name__ == "__main__":
    unittest.main()
