from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_l7_plus_failure_prevention_v1 import failure_prevention_rules


class KimDataverseLevel7PlusFailurePreventionTests(unittest.TestCase):
    def test_known_phoenix_export_failure_is_prevented(self) -> None:
        by_class = {rule.failure_class: rule for rule in failure_prevention_rules()}
        rule = by_class["WORKFLOW_ONLY_TEST_IN_WORKFLOW_FREE_EXPORT"]
        self.assertIn("skip", rule.prevention)
        self.assertTrue(rule.regression_required)

    def test_owner_as_scheduler_is_encoded_as_failure_class(self) -> None:
        by_class = {rule.failure_class: rule for rule in failure_prevention_rules()}
        self.assertIn("OWNER_AS_MAINTENANCE_SCHEDULER", by_class)
        self.assertIn("Maintenance event", by_class["OWNER_AS_MAINTENANCE_SCHEDULER"].prevention)


if __name__ == "__main__":
    unittest.main()
