import json
from pathlib import Path
import subprocess
import unittest

from bubbles.jarvis_benchmark_task import (
    ALLOWED_ACTIONS,
    JarvisBenchmarkTaskError,
    TASK_ROOT,
    run_jarvis_benchmark_task,
)


class JarvisBenchmarkTaskTests(unittest.TestCase):
    def test_source_module_has_no_runtime_permit_database_or_committed_ledger(self):
        self.assertFalse((TASK_ROOT / "governance" / "formation_permits.json").exists())
        self.assertFalse((TASK_ROOT / "data" / "learning-ledger.jsonl").exists())
        self.assertFalse((TASK_ROOT / ".github" / "workflows").exists())

    def test_validate_runs_inside_bounded_ephemeral_state(self):
        result = run_jarvis_benchmark_task("jarvis_benchmark_validate")
        self.assertEqual("LOCAL_JARVIS_BENCHMARK_CONTROL_PLANE", result["kind"])
        self.assertTrue(result["result"]["valid"])
        self.assertFalse(result["providerEffects"])
        self.assertFalse(result["networkUsed"])
        self.assertFalse(result["runtimeLedgerPersisted"])

    def test_snapshot_preserves_conservative_public_truth_boundary(self):
        result = run_jarvis_benchmark_task("jarvis_benchmark_snapshot")
        evaluation = result["result"]["evaluation"]
        self.assertEqual("INITIAL", evaluation["readiness"])
        self.assertLess(evaluation["overallScore"], evaluation["targetScore"])
        self.assertIn("public fixture", result["truthBoundary"])

    def test_arbitrary_inputs_and_write_routes_are_not_exposed(self):
        with self.assertRaisesRegex(JarvisBenchmarkTaskError, "unknown fields"):
            run_jarvis_benchmark_task(
                "jarvis_benchmark_snapshot",
                {"state": {"private": "must-not-enter-public-command-bus"}},
            )
        with self.assertRaisesRegex(JarvisBenchmarkTaskError, "Unsupported"):
            run_jarvis_benchmark_task("jarvis_benchmark_cycle_commit")
        self.assertNotIn("jarvis_benchmark_cycle_commit", ALLOWED_ACTIONS)

    def test_full_node_regression_suite_passes_without_network_or_source_state(self):
        process = subprocess.run(
            ["node", "--test", "--test-reporter=spec"],
            cwd=TASK_ROOT,
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)
        self.assertIn("tests 24", process.stdout)
        self.assertFalse((TASK_ROOT / "data" / "learning-ledger.jsonl").exists())

    def test_public_registry_remains_fixed_https_only(self):
        registry = json.loads((TASK_ROOT / "data" / "sources.json").read_text(encoding="utf-8"))
        self.assertTrue(registry)
        self.assertTrue(all(item["canonicalUrl"].startswith("https://") for item in registry))


if __name__ == "__main__":
    unittest.main()
