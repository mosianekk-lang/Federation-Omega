"""Exact-package bounded shadow binding for AO-HARMONIC v3.

This uses only redacted structural control state derived from a real mission and
performs no provider mutation or external effect.
"""

import unittest

from ao_harmonic_v3.shadow import SHADOW_ID, run_control_state_shadow


class AOHarmonicV3RealMissionShadowTests(unittest.TestCase):
    def test_real_mission_control_state_shadow(self):
        result = run_control_state_shadow()

        self.assertEqual(result["shadow_id"], SHADOW_ID)
        self.assertEqual(
            result["truth_boundary"],
            "REAL_MISSION_DERIVED_CONTROL_STATE_NO_PRIVATE_PAYLOAD_NO_EXTERNAL_EFFECT",
        )
        self.assertFalse(result["external_effect"])
        self.assertEqual(result["authority_ceiling"], "A1_INTERNAL")
        self.assertEqual(result["blocked_external_lanes"], 2)
        self.assertEqual(result["independent_ready_lanes"], 2)
        self.assertEqual(
            result["ready_node_ids"], ["evidence_prepare", "fallback_prepare"]
        )
        self.assertEqual(result["selected_resource"], "gmail-live")
        self.assertFalse(result["owner_interrupt"])
        self.assertEqual(
            result["proof_dependants_reached"],
            ["action-current", "proposition-current"],
        )
        self.assertEqual(
            result["formal_scope"],
            "AO_HARMONIC_V3_SYSTEM_SPECIFIC_NO_EFFECT_SHADOW",
        )


if __name__ == "__main__":
    unittest.main()
