import tempfile
import unittest
from pathlib import Path

from superior_logic.runtime import SuperiorLogicRuntime
from superior_logic.slrk import (
    AssessmentState,
    CapabilityContract,
    CapabilityState,
    EngineEnvironment,
    EnginePromotionRequest,
    FaultRecord,
    FaultSeverity,
    ProofLevel,
    PromotionDecision,
    RouteState,
)


class SLRKTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.runtime = SuperiorLogicRuntime(Path(self.tmp.name) / "runtime.db")

    def tearDown(self):
        self.runtime.close()
        self.tmp.cleanup()

    def test_empty_capability_requirement_fails_closed(self):
        result = self.runtime.assess_capabilities(())
        self.assertEqual(AssessmentState.UNSUPPORTED, result.state)
        self.assertIn("No required capabilities", result.claim_limit)

    def test_incomplete_does_not_trigger_complete_claim_rule(self):
        result = self.runtime.govern_claim(
            "The archive analysis is incomplete.",
            ProofLevel.NONE,
        )
        self.assertTrue(result.allowed)
        self.assertEqual((), result.blocked_terms)

    def test_capability_truth_blocks_missing_contract(self):
        result = self.runtime.assess_capabilities(("CAP-NOT-REGISTERED",))
        self.assertEqual(AssessmentState.UNSUPPORTED, result.state)
        self.assertEqual(("CAP-NOT-REGISTERED",), result.missing_capabilities)

    def test_capability_truth_detects_authority_gate(self):
        self.runtime.register_capability(
            CapabilityContract(
                capability_id="CAP-IAM",
                name="IAM mutation",
                state=CapabilityState.AUTHORITY_REQUIRED,
                authority_required=True,
                fallback_route="authority-pack",
            )
        )
        result = self.runtime.assess_capabilities(("CAP-IAM",))
        self.assertEqual(AssessmentState.AUTHORITY_REQUIRED, result.state)
        self.assertIn("authority", result.claim_limit.lower())

    def test_claim_governor_blocks_ledger_only_live_claim(self):
        result = self.runtime.govern_claim(
            "The system is live, complete and fully automated.",
            ProofLevel.LEDGER_READBACK,
            execution_verified=False,
            gap_scan_complete=False,
            lifecycle_complete=False,
        )
        self.assertFalse(result.allowed)
        self.assertIn("runtime execution is not proven", result.safe_wording)
        self.assertIn("execution_verified", result.missing_conditions)
        self.assertIn("gap_scan_complete", result.missing_conditions)

    def test_claim_governor_allows_scoped_verified_readback(self):
        result = self.runtime.govern_claim(
            "The selected sheet range is verified.",
            ProofLevel.CONNECTOR_READBACK,
        )
        self.assertTrue(result.allowed)

    def test_fault_bans_route_until_material_change(self):
        self.runtime.register_fault(
            FaultRecord(
                fault_id="ROUTE_REPEATED_FAILED_DEPLOY_FAULT",
                layer_type="ROUTE_LAYER",
                detected_problem="Known route failed twice",
                banned_pattern="Blind retry",
                bypass_rule="Use image deployment",
                severity=FaultSeverity.BLOCK,
                proof_required="New service-state proof",
                route_id="gcloud-source-deploy",
            )
        )
        self.assertEqual(
            RouteState.BANNED_UNLESS_CLEARED.value,
            self.runtime.route_state("gcloud-source-deploy")["state"],
        )
        with self.assertRaises(ValueError):
            self.runtime.clear_route(
                "gcloud-source-deploy",
                "no change",
                conditions_changed=False,
            )
        cleared = self.runtime.clear_route(
            "gcloud-source-deploy",
            "builder repaired",
            conditions_changed=True,
        )
        self.assertEqual(RouteState.AVAILABLE.value, cleared["state"])

    def test_engine_production_promotion_fails_closed(self):
        result = self.runtime.evaluate_engine_promotion(
            EnginePromotionRequest(
                engine_id="ENG-1",
                target_environment=EngineEnvironment.PRODUCTION,
                objective="Protect claims",
                risk_class="HIGH",
                profile_complete=True,
                governor_attached=True,
                fault_rules_attached=True,
                proof_rules_attached=True,
                tests_passed=True,
                proof_ledger_written=True,
                risk_accepted=True,
                rollback_ready=False,
                status_path_ready=True,
                last_known_good_registered=True,
                approval_granted=False,
                live_readback_plan_ready=True,
            )
        )
        self.assertEqual(PromotionDecision.BLOCKED, result.decision)
        self.assertIn("rollback_ready", result.missing_gates)
        self.assertIn("approval_granted", result.missing_gates)

    def test_engine_staging_promotion_passes(self):
        result = self.runtime.evaluate_engine_promotion(
            EnginePromotionRequest(
                engine_id="ENG-2",
                target_environment=EngineEnvironment.STAGING,
                objective="Test engine",
                risk_class="MEDIUM",
                profile_complete=True,
                governor_attached=True,
                fault_rules_attached=True,
                proof_rules_attached=True,
                tests_passed=True,
                proof_ledger_written=True,
                risk_accepted=True,
                rollback_ready=False,
                status_path_ready=False,
                last_known_good_registered=False,
            )
        )
        self.assertEqual(PromotionDecision.STAGING_READY, result.decision)
        self.assertTrue(self.runtime.verify_event_chain())


if __name__ == "__main__":
    unittest.main()
