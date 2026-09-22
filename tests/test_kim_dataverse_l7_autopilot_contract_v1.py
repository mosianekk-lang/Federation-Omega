from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_l7_autopilot_contract_v1 import default_autopilot_contract


class KimDataverseLevel7AutopilotContractTests(unittest.TestCase):
    def test_internal_maintenance_repair_and_resume_are_autopilot_authorized(self) -> None:
        contract = default_autopilot_contract()
        self.assertTrue(contract.internal_reversible_maintenance)
        self.assertTrue(contract.internal_recovery)
        self.assertTrue(contract.exact_head_restack)
        self.assertTrue(contract.regression_repair)
        self.assertTrue(contract.evidence_collection)
        self.assertTrue(contract.mission_resume)

    def test_consequential_owner_boundaries_are_not_autopilot_authorized(self) -> None:
        contract = default_autopilot_contract()
        self.assertFalse(contract.iam_wif_mutation)
        self.assertFalse(contract.provider_authority_expansion)
        self.assertFalse(contract.financial_transaction)
        self.assertFalse(contract.external_publish_send)
        self.assertFalse(contract.destructive_external_mutation)
        self.assertFalse(contract.owner_intent_change)


if __name__ == "__main__":
    unittest.main()
