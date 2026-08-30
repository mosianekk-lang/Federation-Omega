from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from omega_one.cli import main


class CliTests(unittest.TestCase):
    def run_cli(self, argv):
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = main(argv)
        return code, json.loads(stream.getvalue())

    def test_demo_completes_and_is_resumable(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "demo"
            code, first = self.run_cli(["demo", "--state-dir", str(state)])
            self.assertEqual(code, 0)
            self.assertEqual(first["status"]["state"], "PROVEN")
            self.assertTrue(first["integrity"])
            _, second = self.run_cli(["demo", "--state-dir", str(state)])
            self.assertEqual(second["status"], first["status"])

    def test_provider_inventory_is_non_effect(self):
        _, result = self.run_cli(["providers"])
        self.assertEqual(len(result["providers"]), 3)
        self.assertTrue(all(not item["live_execution_authorized"] for item in result["providers"]))

    def test_benchmark_is_hash_bound_and_truth_limited(self):
        _, result = self.run_cli(["benchmark"])
        self.assertEqual(result["empirical_scope"], "DETERMINISTIC_LOCAL_SIMULATION_ONLY")
        self.assertIn("report_sha256", result)
        self.assertNotEqual(result["release_decision"], "CFBE_GOLD_V1")


if __name__ == "__main__":
    unittest.main()
