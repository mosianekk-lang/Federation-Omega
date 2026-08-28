from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/phoenix-emergency-freeze.yml").read_text(
    encoding="utf-8"
)


class PhoenixPassiveFreezeGuardTests(unittest.TestCase):
    def test_passive_push_records_non_mutating_verified_receipt(self):
        self.assertIn("Record passive verification receipt", WORKFLOW)
        self.assertIn('"workflow_quarantine_performed": False', WORKFLOW)
        self.assertIn('"source_mutation_attempted": False', WORKFLOW)
        self.assertIn('"status": "VERIFIED"', WORKFLOW)

    def test_quarantine_requires_explicit_pst_closure(self):
        marker = "- name: Quarantine legacy workflow execution"
        start = WORKFLOW.index(marker)
        snippet = WORKFLOW[start : start + 240]
        self.assertIn(
            "if: steps.pst_closure.outputs.requested == 'true'",
            snippet,
        )

    def test_passive_status_is_truthful(self):
        self.assertIn(
            "Phoenix passive verification and exports verified; PST not requested",
            WORKFLOW,
        )


if __name__ == "__main__":
    unittest.main()
