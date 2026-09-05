import unittest

from evidenceops.maturity_autopilot import CapabilityEvidence, MaturityAutopilot, MaturityLevel


class MaturityAutopilotTests(unittest.TestCase):
    def test_claim_downgrades_when_provider_readback_missing(self):
        capability = CapabilityEvidence(
            capability_id="CAP-1",
            claimed_level=MaturityLevel.M9_OPERATIONAL,
            proofs={
                "spec": True,
                "source": True,
                "tests": True,
                "integration": True,
                "runtime": True,
                "provider_readback": False,
            },
        )
        action = MaturityAutopilot().assess(capability)
        self.assertEqual(action.derived_level, MaturityLevel.M5_BOUNDED_RUNTIME)
        self.assertTrue(action.downgrade_required)
        self.assertEqual(action.gate_id, "provider_readback")

    def test_full_chain_reaches_m11(self):
        proofs = {
            "spec": True,
            "source": True,
            "tests": True,
            "integration": True,
            "runtime": True,
            "provider_readback": True,
            "rollback": True,
            "workflow_calibration": True,
            "slo": True,
            "security_privacy": True,
            "recertification": True,
        }
        capability = CapabilityEvidence("CAP-2", MaturityLevel.M11_CONTINUOUSLY_CERTIFIED, proofs)
        action = MaturityAutopilot().assess(capability)
        self.assertEqual(action.derived_level, MaturityLevel.M11_CONTINUOUSLY_CERTIFIED)
        self.assertFalse(action.downgrade_required)
        self.assertIsNone(action.gate_id)

    def test_drift_ranks_ahead_of_normal_gap(self):
        drift = CapabilityEvidence("DRIFT", MaturityLevel.M10_PRODUCTION_ASSURED, {"spec": True})
        gap = CapabilityEvidence("GAP", MaturityLevel.M1_SPECIFIED, {"spec": True})
        ranked = MaturityAutopilot().rank([gap, drift])
        self.assertEqual(ranked[0].capability_id, "DRIFT")

    def test_external_blocker_is_preserved(self):
        capability = CapabilityEvidence(
            "BLOCKED",
            MaturityLevel.M5_BOUNDED_RUNTIME,
            {"spec": True, "source": True, "tests": True, "integration": True, "runtime": True},
            blocked_external=True,
            blocker="provider-native readback unavailable",
        )
        action = MaturityAutopilot().assess(capability)
        self.assertTrue(action.blocked_external)
        self.assertIn("external blocker", action.action)
        self.assertEqual(action.blocker, "provider-native readback unavailable")


if __name__ == "__main__":
    unittest.main()
