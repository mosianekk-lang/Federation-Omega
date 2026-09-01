from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_l7_plus_ci_contract_v1 import blocking_checks


class KimDataverseLevel7PlusCIContractTests(unittest.TestCase):
    def test_required_admission_checks_are_registered(self) -> None:
        checks = blocking_checks()
        self.assertIn("Federation Omega Airlock", checks)
        self.assertIn("Bubbles Command Bus", checks)
        self.assertIn("Public Repository Leak Guard", checks)


if __name__ == "__main__":
    unittest.main()
