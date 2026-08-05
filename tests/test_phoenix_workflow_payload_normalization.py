from pathlib import Path
import unittest


class PhoenixWorkflowPayloadNormalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = Path(
            ".github/workflows/phoenix-emergency-freeze.yml"
        ).read_text(encoding="utf-8")

    def test_ambiguous_brace_default_is_prohibited(self) -> None:
        self.assertNotIn("${payload:-{}}", self.workflow)

    def test_empty_payload_is_normalized_before_jq(self) -> None:
        empty_guard = 'if [[ -z "${payload}" ]]; then'
        fallback = "payload='{}'"
        first_jq = 'workflow_id="$(jq -r \' .id // 0\''
        self.assertIn(empty_guard, self.workflow)
        self.assertIn(fallback, self.workflow)
        self.assertLess(self.workflow.index(empty_guard), self.workflow.index(fallback))
        self.assertLess(
            self.workflow.index(fallback),
            self.workflow.index('workflow_id="$(jq -r'),
        )

    def test_all_jq_reads_use_normalized_payload(self) -> None:
        self.assertIn('<<< "${payload}"', self.workflow)
        self.assertNotIn('<<< "${payload:-', self.workflow)

    def test_convergence_helper_and_fail_closed_receipt_remain(self) -> None:
        self.assertIn("python phoenix/workflow_freeze_convergence.py", self.workflow)
        self.assertIn("--required-readback /tmp/phoenix-required-readback.tsv", self.workflow)
        self.assertIn("--errors /tmp/phoenix-freeze-errors.txt", self.workflow)


if __name__ == "__main__":
    unittest.main()
