import unittest

from ao_harmonic_v3.failure_win_v2 import (
    FailureEventType,
    FailureObservation,
    FailureToOperationalWinKernelV2,
    FailureWinRequest,
    FailureWinState,
    ReceiverAttestation,
    RecoveryRoute,
    StageBudget,
    WinEvidence,
)
from ao_harmonic_v3.models import FederationEvent, PerformanceVector


class FailureToOperationalWinV2Tests(unittest.TestCase):
    def setUp(self):
        self.kernel = FailureToOperationalWinKernelV2()
        self.observation = FailureObservation(
            event_id="E1",
            event_type=FailureEventType.TIMEOUT,
            system_id="Bubbles",
            objective="complete mission",
            claim="mission should complete",
            observed_fruit="TIME_BUDGET_EXCEEDED",
            desired_outcome="operational completion",
            failure_code="TIMEOUT",
            provider="fixture",
            failed_route_id="route-a",
            recent_route_history=("route-a",),
            stage_budgets=(
                StageBudget("provider", 5.0, observed_seconds=8.0),
                StageBudget("mission", 300.0, observed_seconds=400.0, hard_commitment=True),
            ),
        )
        self.incumbent = PerformanceVector(
            quality=5,
            reliability=5,
            proof=5,
            speed=1,
        )
        self.good_candidate = PerformanceVector(
            quality=5,
            reliability=5,
            proof=5,
            speed=5,
            owner_time_recovered=2,
            recovery_gain=2,
        )
        self.good_route = RecoveryRoute(
            "route-b",
            "REROUTE",
            self.good_candidate,
            proof_strength=1.0,
            reversibility=1.0,
            strategic_value=1.0,
        )

    def full_evidence(self):
        return WinEvidence(
            failure_fact_preserved=True,
            causal_model_recorded=True,
            falsification_executed=True,
            authority_current=True,
            cost_allowed=True,
            failure_first_test_passed=True,
            healthy_path_test_passed=True,
            rollback_test_passed=True,
            forward_canary_passed=True,
            independent_semantic_readback=True,
            positive_value=True,
            no_regression=True,
            owner_burden_not_increased=True,
            provider_receipt_present=True,
            repeated_successes=3,
            soak_seconds=300,
            proof_refs=("proof:1",),
        )

    def test_material_failure_opens_repair_cycle_and_generates_falsifiers(self):
        result = self.kernel.evaluate(FailureWinRequest(observation=self.observation))
        self.assertEqual(result.state, FailureWinState.REPAIR_CYCLE_OPEN)
        self.assertTrue(result.next_falsification_test)
        self.assertEqual(result.ranked_hypothesis_ids[0], "H-ROUTE")
        self.assertIn("provider", result.time_budget_breaches)
        self.assertEqual(result.horizon_depth, 50)
        self.assertTrue(result.portable_fingerprint.startswith("fwp-"))

    def test_vector_gate_rejects_faster_candidate_that_loses_quality(self):
        unsafe = PerformanceVector(
            quality=4,
            reliability=5,
            proof=5,
            speed=20,
        )
        route = RecoveryRoute(
            "fast-but-worse",
            "REROUTE",
            unsafe,
            proof_strength=1.0,
            reversibility=1.0,
            strategic_value=1.0,
        )
        result = self.kernel.evaluate(
            FailureWinRequest(
                observation=self.observation,
                incumbent=self.incumbent,
                routes=(route,),
            )
        )
        self.assertFalse(result.vector_gate_passed)
        self.assertEqual(result.selected_route_ids, ())
        self.assertIn("quality", result.protected_regressions)

    def test_provider_dependent_win_requires_provider_receipt(self):
        evidence = self.full_evidence()
        evidence = WinEvidence(**{**evidence.__dict__, "provider_receipt_present": False})
        result = self.kernel.evaluate(
            FailureWinRequest(
                observation=self.observation,
                incumbent=self.incumbent,
                routes=(self.good_route,),
                evidence=evidence,
                provider_dependent=True,
            )
        )
        self.assertNotEqual(result.state, FailureWinState.OPERATIONAL_WIN_VERIFIED)
        self.assertIn("PROVIDER_RECEIPT", result.proof_graph.missing_nodes)

    def test_complete_proof_graph_can_reach_operational_win(self):
        result = self.kernel.evaluate(
            FailureWinRequest(
                observation=self.observation,
                incumbent=self.incumbent,
                routes=(self.good_route,),
                evidence=self.full_evidence(),
            )
        )
        self.assertEqual(result.state, FailureWinState.OPERATIONAL_WIN_VERIFIED)
        self.assertTrue(result.proof_graph.complete)
        self.assertEqual(result.selected_route_ids, ("route-b",))

    def test_estate_scope_requires_dynamic_receiver_native_attestation(self):
        result = self.kernel.evaluate(
            FailureWinRequest(
                observation=self.observation,
                incumbent=self.incumbent,
                routes=(self.good_route,),
                evidence=self.full_evidence(),
                estate_scope_claim=True,
                receiver_manifest_complete=False,
            )
        )
        self.assertNotEqual(result.state, FailureWinState.OPERATIONAL_WIN_VERIFIED)
        self.assertIn("DYNAMIC_RECEIVER_MANIFEST_COMPLETE", result.proof_graph.missing_nodes)
        self.assertIn("RECEIVER_NATIVE_BEHAVIOR_PROOF", result.proof_graph.missing_nodes)

        attestations = (
            ReceiverAttestation(
                "Bubbles",
                kernel_invoked=True,
                behavior_proven=True,
                current=True,
                independent_readback=True,
                evidence_refs=("att:1",),
            ),
            ReceiverAttestation(
                "CFBE",
                kernel_invoked=True,
                behavior_proven=True,
                current=True,
                independent_readback=True,
                evidence_refs=("att:2",),
            ),
        )
        promoted = self.kernel.evaluate(
            FailureWinRequest(
                observation=self.observation,
                incumbent=self.incumbent,
                routes=(self.good_route,),
                evidence=self.full_evidence(),
                estate_scope_claim=True,
                receiver_manifest_complete=True,
                receiver_attestations=attestations,
            )
        )
        self.assertEqual(promoted.state, FailureWinState.OPERATIONAL_WIN_VERIFIED)

    def test_repair_oscillation_quarantines_thrash(self):
        observation = FailureObservation(
            event_id="E-OSC",
            event_type=FailureEventType.FAILURE,
            system_id="Bubbles",
            objective="repair",
            claim="route should work",
            observed_fruit="repeated failure",
            desired_outcome="stable success",
            failure_code="REPAIR_THRASH",
            recent_route_history=("route-a", "route-b", "route-a", "route-b"),
        )
        result = self.kernel.evaluate(FailureWinRequest(observation=observation))
        self.assertEqual(result.state, FailureWinState.QUARANTINED)
        self.assertTrue(result.oscillation_detected)

    def test_precursor_risk_prewarms_without_claiming_failure(self):
        observation = FailureObservation(
            event_id="E-PRE",
            event_type=FailureEventType.PRECURSOR_RISK,
            system_id="Sentinel",
            objective="avoid timeout",
            claim="latency should stay under SLO",
            observed_fruit="latency drift",
            desired_outcome="preempt failure",
            failure_code="LATENCY_DRIFT",
            material=False,
            precursor_signals=("p95 rising",),
        )
        result = self.kernel.evaluate(
            FailureWinRequest(
                observation=observation,
                incumbent=self.incumbent,
                routes=(self.good_route,),
            )
        )
        self.assertEqual(result.state, FailureWinState.PREEMPTION_READY)
        self.assertEqual(result.prewarm_route_ids, ("route-b",))

    def test_hard_time_commitment_is_not_relaxed(self):
        result = self.kernel.evaluate(FailureWinRequest(observation=self.observation))
        suggestions = result.kpis["adaptive_budget_suggestions"]
        self.assertIn("provider", suggestions)
        self.assertNotIn("mission", suggestions)
        self.assertTrue(
            any("PRESERVE_HARD_TIME_COMMITMENT" in item for item in result.next_actions)
        )

    def test_failure_genome_tracks_recurrence_and_portable_class(self):
        first = self.kernel.evaluate(FailureWinRequest(observation=self.observation))
        second = self.kernel.evaluate(FailureWinRequest(observation=self.observation))
        self.assertEqual(first.portable_fingerprint, second.portable_fingerprint)
        self.assertEqual(second.recurrence, first.recurrence + 1)
        snapshot = self.kernel.genome_snapshot()
        self.assertEqual(len(snapshot), 1)
        self.assertIn("route-a", snapshot[0]["quarantined_routes"])

    def test_event_adapter_is_source_level_and_fail_closed(self):
        event = FederationEvent(
            event_id="EV",
            event_type="OWNER_CORRECTION",
            source="Bubbles",
            workstream="TEST",
            idempotency_key="idempotent",
            timestamp="2026-08-27T00:00:00Z",
            payload={
                "objective": "correct result",
                "claim": "prior result was correct",
                "observed_fruit": "owner correction",
                "desired_outcome": "corrected state",
                "failure_code": "OWNER_CORRECTION",
            },
        )
        result = self.kernel.observe_federation_event(event)
        self.assertEqual(result["state"], "REPAIR_CYCLE_OPEN")
        self.assertFalse(result["proof_graph"]["complete"])
        self.assertIn("does not itself execute provider mutations", result["truth_boundary"])


if __name__ == "__main__":
    unittest.main()
