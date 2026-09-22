from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_l7_plus_authority_gate_v1 import GOOGLE_WIF_GATE


class KimDataverseLevel7PlusAuthorityGateTests(unittest.TestCase):
    def test_wif_gate_requires_explicit_owner_authorization_and_is_lane_local(self) -> None:
        self.assertTrue(GOOGLE_WIF_GATE.explicit_owner_authorization_required)
        self.assertFalse(GOOGLE_WIF_GATE.generic_continue_sufficient)
        self.assertTrue(GOOGLE_WIF_GATE.lane_local)
        self.assertEqual("AUTHORIZE_SOVARA_WIF_HARDENING", GOOGLE_WIF_GATE.gate_id)


if __name__ == "__main__":
    unittest.main()
