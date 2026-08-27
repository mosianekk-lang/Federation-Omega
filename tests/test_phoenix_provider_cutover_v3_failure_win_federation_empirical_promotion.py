from __future__ import annotations

import json
import unittest
from pathlib import Path

from ao_harmonic_v3.behavioral_convergence import (
    BehavioralConvergenceEngine,
    BehavioralConvergenceState,
    BehavioralEvidenceKind,
    BehavioralOrigin,
    BehavioralProofReceipt,
)
from ao_harmonic_v3.failure_win_v2 import RecoveryRoute
from ao_harmonic_v3.models import FederationEvent, PerformanceVector


CONTROL = Path("governance/failure_win_v2_federation_empirical_promotion_20260827.json")


class FederationOmegaEmpiricalPromotionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.control = json.loads(CONTROL.read_text(encoding="utf-8"))

    @staticmethod
    def _vector(payload: dict[str, float]) -> PerformanceVector:
        return PerformanceVector(**payload)

    def test_actual_failure_win_engine_adjudicates_three_real_successes(self):
        control = self.control
        vector = control["performance_vector"]
        root = control["root_failure"]
        threshold = control["derived_thresholds"]

        incumbent = self._vector(vector["incumbent"])
        candidate = self._vector(vector["candidate"])
        route = RecoveryRoute(
            route_id="FEDERATION_MULTI_PROVIDER_RECOVERY_ROUTE_V1",
            route_type="GITHUB_SHEETS_CLOUD_RUN_EMPIRICAL_RECOVERY",
            performance=candidate,
            available=True,
            authorised=True,
            zero_or_included_cost=True,
            rollback_available=True,
            materially_different=True,
            provider_neutral=True,
            proof_strength=1.0,
            reversibility=1.0,
            strategic_value=1.0,
            expected_value=1.0,
            expected_cost=0.0,
            expected_risk=0.0,
        )

        engine = BehavioralConvergenceEngine()
        opening = FederationEvent(
            event_id="FWV2-FEDERATION-ROOT-PROVENANCE-FAILURE-REAL",
            event_type="FAILURE",
            source="Federation Omega",
            workstream="Failure-to-Operational-Win v2 empirical convergence",
            idempotency_key="FWV2-FEDERATION-ROOT-PROVENANCE-FAILURE-REAL",
            timestamp="2026-08-27T03:52:00+00:00",
            proof_class="PROVIDER_RUNTIME_READBACK",
            authority_class="A1_INTERNAL",
            payload={
                "objective": "Recover the Federation source/runtime lane without proof dilution",
                "claim": "The admitted source path should satisfy provenance and preserve the owner objective",
                "observed_fruit": "Airlock provenance admission failed",
                "desired_outcome": "A source-admitted recovery with independent readback and recurrence prevention",
                "failure_code": root["failure_code"],
                "provider": root["failure_provider"],
                "route_id": "FAILED_PROVENANCE_ROUTE",
                "behavioral_origin": "REAL_RUNTIME",
                "proof_refs": [f"Airlock:{root['failed_airlock_run']}:FAILURE"],
                "independent_readback": True,
                "current": True,
                "provider_dependent": True,
                "material": True,
            },
        )
        opened = engine.observe_federation_event(
            opening,
            origin=BehavioralOrigin.REAL_RUNTIME,
            incumbent=incumbent,
            routes=(route,),
            provider_dependent=True,
            required_repeated_successes=threshold["required_distinct_real_successes"],
            required_soak_seconds=threshold["required_soak_seconds"],
        )
        fingerprint = opened.fingerprint
        self.assertTrue(opened.empirical_failure_seen)
        self.assertFalse(opened.behavior_proven)

        proof_kinds = {
            "CAUSAL_MODEL_RECORDED": BehavioralEvidenceKind.CAUSAL_MODEL,
            "FALSIFICATION_EXECUTED": BehavioralEvidenceKind.FALSIFICATION,
            "AUTHORITY_CURRENT": BehavioralEvidenceKind.AUTHORITY_CURRENT,
            "COST_ALLOWED": BehavioralEvidenceKind.COST_ALLOWED,
            "FAILURE_FIRST_TEST": BehavioralEvidenceKind.FAILURE_FIRST,
            "HEALTHY_PATH_TEST": BehavioralEvidenceKind.HEALTHY_PATH,
            "ROLLBACK_TEST": BehavioralEvidenceKind.ROLLBACK,
            "FORWARD_CANARY": BehavioralEvidenceKind.FORWARD_CANARY,
            "INDEPENDENT_SEMANTIC_READBACK": BehavioralEvidenceKind.SEMANTIC_READBACK,
            "POSITIVE_VALUE": BehavioralEvidenceKind.POSITIVE_VALUE,
            "NO_REGRESSION": BehavioralEvidenceKind.NO_REGRESSION,
            "OWNER_BURDEN_NOT_INCREASED": BehavioralEvidenceKind.OWNER_BURDEN_NOT_INCREASED,
            "PROVIDER_RECEIPT": BehavioralEvidenceKind.PROVIDER_RECEIPT,
        }
        mapping = control["proof_mapping"]
        for index, (node, kind) in enumerate(proof_kinds.items(), start=1):
            refs = tuple(mapping[node])
            self.assertTrue(refs, node)
            engine.record_proof(
                fingerprint,
                BehavioralProofReceipt(
                    event_id=f"FWV2-FEDERATION-PROOF-{index:02d}",
                    receiver_id="Federation Omega",
                    kind=kind,
                    origin=BehavioralOrigin.REAL_PROVIDER,
                    observed_at="2026-08-27T10:01:10.046599+00:00",
                    proof_refs=refs,
                    independent_readback=True,
                    current=True,
                    source_version=control["source_frontier"]["signed_main_before_promotion"],
                ),
            )

        for success in control["success_receipts"]:
            engine.record_proof(
                fingerprint,
                BehavioralProofReceipt(
                    event_id=success["success_id"],
                    receiver_id="Federation Omega",
                    kind=BehavioralEvidenceKind.SUCCESS,
                    origin=BehavioralOrigin(success["origin"]),
                    observed_at=success["observed_at"],
                    proof_refs=tuple(success["proof_refs"]),
                    independent_readback=True,
                    current=True,
                    source_version=control["source_frontier"]["signed_main_before_promotion"],
                ),
            )

        result = engine.assess(fingerprint)
        self.assertEqual(result.state, BehavioralConvergenceState.V2_BEHAVIOR_PROVEN)
        self.assertTrue(result.behavior_proven)
        self.assertEqual(result.repeated_successes, 3)
        self.assertAlmostEqual(result.soak_seconds, threshold["soak_seconds"], places=3)
        self.assertEqual(result.kernel_result["state"], "OPERATIONAL_WIN_VERIFIED")
        self.assertTrue(result.kernel_result["proof_graph"]["complete"])
        self.assertEqual(result.kernel_result["proof_graph"]["missing_nodes"], ())
        self.assertTrue(result.kernel_result["vector_gate_passed"])

    def test_third_receipt_is_fresh_real_provider_semantics_not_sovara_private_authority(self):
        third = self.control["success_receipts"][2]
        semantic = third["semantic_readback"]
        currentness = third["source_currentness"]
        scope = self.control["promotion_scope"]

        self.assertEqual(third["provider"], "Google Cloud Run")
        self.assertEqual(semantic["health_http_status"], 200)
        self.assertTrue(semantic["health_ok"])
        self.assertEqual(semantic["health_status"], "OPERATOR_READY")
        self.assertEqual(semantic["contract_http_status"], 200)
        self.assertTrue(semantic["contract_ok"])
        self.assertEqual(semantic["private_execute_http_status"], 403)
        self.assertTrue(semantic["private_access_denied"])
        self.assertFalse(semantic["provider_mutation"])
        self.assertFalse(semantic["repository_mutation"])
        self.assertFalse(semantic["paid_semantic_call"])
        self.assertTrue(currentness["workflow_logic_exact_current_match"])
        self.assertEqual(
            currentness["rerun_workflow_blob_sha"],
            currentness["current_workflow_blob_sha"],
        )
        self.assertFalse(scope["sovara_private_authority_reestablished"])
        self.assertFalse(scope["sovara_behavior_proven"])
        self.assertFalse(scope["estate_operational_win_verified"])

    def test_promotion_is_receiver_local_only(self):
        scope = self.control["promotion_scope"]
        self.assertEqual(scope["federation_omega_receiver_local_candidate"], "OPERATIONAL_WIN_VERIFIED")
        self.assertFalse(scope["estate_scope_claim"])
        self.assertEqual(scope["expected_estate_behavior_proven_after_local_promotion"], 1)
        self.assertEqual(scope["receiver_universe"], 26)


if __name__ == "__main__":
    unittest.main()
