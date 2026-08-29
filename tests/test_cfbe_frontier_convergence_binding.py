import unittest

from benchmarking.cfbe_omega.frontier_convergence_profile import (
    CURRENT_EVIDENCE_FACTOR,
    FrontierProof,
    compile_dimensions,
    evaluate,
)
from benchmarking.cfbe_omega.v4_data_readiness import (
    MissionTelemetryEvidence,
    evaluate_objective_ecology_readiness,
)


class FrontierConvergenceBindingTests(unittest.TestCase):
    def test_current_internal_runtime_does_not_promote_provider_live(self):
        report = evaluate()
        self.assertEqual(CURRENT_EVIDENCE_FACTOR, 0.70)
        self.assertFalse(report.gemini_canary_verified)
        self.assertFalse(report.workspace_bidirectional_verified)
        self.assertFalse(report.production_qualified)
        self.assertNotEqual(report.leadership, "FRONTIER_LEADER")

    def test_provider_dimensions_start_at_claimed_factor(self):
        dims = {item.dimension_id: item for item in compile_dimensions()}
        self.assertEqual(dims["mission_sovereignty"].evidence_factor, 0.70)
        self.assertEqual(dims["gemini_provider"].evidence_factor, 0.30)
        self.assertEqual(dims["workspace_bidirectional"].evidence_factor, 0.30)

    def test_aggregate_sibling_claim_cannot_be_inherited_as_provider_live(self):
        proof = FrontierProof(
            proof_id="aggregate-sovara-status-only",
            state="PROVIDER_LIVE_INDEPENDENT_READBACK",
            receiver="gemini_provider",
            provider_native=False,
            independent_readback=False,
        )
        with self.assertRaises(ValueError):
            evaluate([proof])

    def test_exact_receiver_live_readback_promotes_only_that_receiver(self):
        gemini = FrontierProof(
            proof_id="gemini-native-receipt",
            state="PROVIDER_LIVE_INDEPENDENT_READBACK",
            receiver="gemini_provider",
            provider_native=True,
            independent_readback=True,
        )
        report = evaluate([gemini])
        self.assertTrue(report.gemini_canary_verified)
        self.assertFalse(report.workspace_bidirectional_verified)
        self.assertFalse(report.production_qualified)

    def test_production_qualification_requires_both_live_receivers(self):
        proofs = [
            FrontierProof(
                proof_id="gemini-native-receipt",
                state="PROVIDER_LIVE_INDEPENDENT_READBACK",
                receiver="gemini_provider",
                provider_native=True,
                independent_readback=True,
            ),
            FrontierProof(
                proof_id="workspace-native-receipt",
                state="PROVIDER_LIVE_INDEPENDENT_READBACK",
                receiver="workspace_bidirectional",
                provider_native=True,
                independent_readback=True,
            ),
        ]
        report = evaluate(proofs)
        self.assertTrue(report.gemini_canary_verified)
        self.assertTrue(report.workspace_bidirectional_verified)
        self.assertTrue(report.production_qualified)
        # Independent replication is still separately required for a leader claim.
        self.assertNotEqual(report.leadership, "FRONTIER_LEADER")

    def test_duplicate_receiver_proofs_fail_closed(self):
        proof = FrontierProof("p1", "CONTROL_PLANE_OR_SOURCE_ONLY", "gemini_provider")
        duplicate = FrontierProof("p2", "CONTROL_PLANE_OR_SOURCE_ONLY", "gemini_provider")
        with self.assertRaises(ValueError):
            evaluate([proof, duplicate])


class V4ObjectiveEcologyReadinessTests(unittest.TestCase):
    def _record(self, **overrides):
        telemetry = overrides.pop(
            "telemetry",
            {
                "sovara.outcome.accepted": True,
                "sovara.mission.value": 0.9,
                "sovara.mission.cost": 0.1,
                "sovara.mission.risk": 0.2,
            },
        )
        return MissionTelemetryEvidence(
            mission_id=overrides.pop("mission_id", "MSN-REAL-001"),
            telemetry=telemetry,
            evidence_refs=overrides.pop("evidence_refs", ("receipt:real-001",)),
            evidence_class=overrides.pop("evidence_class", "REAL_MISSION"),
        )

    def test_existing_sovara_telemetry_aliases_can_reach_data_ready(self):
        report = evaluate_objective_ecology_readiness((self._record(),))
        self.assertEqual(report.state, "DATA_READY")
        self.assertEqual(report.qualifying_mission_ids, ("MSN-REAL-001",))
        self.assertEqual(report.missing_fields, ())
        self.assertEqual(report.conflict_fields, ())

    def test_synthetic_canary_never_promotes_data_ready(self):
        report = evaluate_objective_ecology_readiness(
            (self._record(evidence_class="PUBLIC_SYNTHETIC"),)
        )
        self.assertEqual(report.state, "INSTRUMENTED_REAL_MISSION_DATA_REQUIRED")
        self.assertEqual(report.qualifying_mission_ids, ())

    def test_real_mission_without_provenance_fails_closed(self):
        report = evaluate_objective_ecology_readiness((self._record(evidence_refs=()),))
        self.assertEqual(report.state, "HELD_PROVENANCE_REQUIRED")

    def test_missing_required_field_fails_closed(self):
        telemetry = {
            "sovara.outcome.accepted": True,
            "sovara.mission.value": 0.9,
            "sovara.mission.cost": 0.1,
        }
        report = evaluate_objective_ecology_readiness(
            (self._record(telemetry=telemetry),)
        )
        self.assertEqual(report.state, "INSTRUMENTED_MISSING_REQUIRED_DATA")
        self.assertIn("mission.risk", report.missing_fields)

    def test_conflicting_aliases_fail_closed(self):
        telemetry = {
            "mission.accepted": False,
            "sovara.outcome.accepted": True,
            "sovara.mission.value": 0.9,
            "sovara.mission.cost": 0.1,
            "sovara.mission.risk": 0.2,
        }
        report = evaluate_objective_ecology_readiness(
            (self._record(telemetry=telemetry),)
        )
        self.assertEqual(report.state, "HELD_FIELD_CONFLICT")
        self.assertIn("mission.accepted", report.conflict_fields)

    def test_invalid_negative_value_telemetry_fails_closed(self):
        telemetry = {
            "sovara.outcome.accepted": True,
            "sovara.mission.value": -1.0,
            "sovara.mission.cost": 0.1,
            "sovara.mission.risk": 0.2,
        }
        report = evaluate_objective_ecology_readiness(
            (self._record(telemetry=telemetry),)
        )
        self.assertEqual(report.state, "HELD_INVALID_VALUE_TELEMETRY")


if __name__ == "__main__":
    unittest.main()
