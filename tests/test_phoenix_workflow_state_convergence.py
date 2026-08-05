from pathlib import Path
import unittest


class PhoenixWorkflowStateConvergenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = Path(
            ".github/workflows/phoenix-emergency-freeze.yml"
        ).read_text(encoding="utf-8")

    def test_fixed_two_second_readback_is_removed(self) -> None:
        self.assertNotIn("\n          sleep 2\n", self.workflow)

    def test_required_workflows_use_bounded_convergence(self) -> None:
        self.assertIn("convergence_max_attempts=10", self.workflow)
        self.assertIn(
            "while (( convergence_attempts < convergence_max_attempts ))",
            self.workflow,
        )
        self.assertIn("sleep $((convergence_attempts * 2))", self.workflow)
        for path in (
            ".github/workflows/github-airlock.yml",
            ".github/workflows/public-repository-leak-guard.yml",
            ".github/workflows/phoenix-emergency-freeze.yml",
        ):
            self.assertIn(path, self.workflow)

    def test_receipt_records_convergence_evidence(self) -> None:
        self.assertIn("'readback_attempts': readback_attempts", self.workflow)
        self.assertIn("'readback_max_attempts': 10", self.workflow)
        self.assertIn(
            "'workflow_state_convergence_wait_seconds_max': 90",
            self.workflow,
        )

    def test_failure_remains_fail_closed(self) -> None:
        self.assertIn("if not verified:", self.workflow)
        self.assertIn("raise SystemExit(1)", self.workflow)
        self.assertIn("missing_required", self.workflow)
        self.assertIn("unexpected_active", self.workflow)


if __name__ == "__main__":
    unittest.main()
