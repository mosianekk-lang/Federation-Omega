from __future__ import annotations

import unittest

from superior_logic.hypercube_adaptive_response import AdaptiveAction, AdaptiveBottleneckRuntime
from superior_logic.hypercube_bottleneck_resolver import BottleneckKind, BottleneckSignal
from superior_logic.hyperperformance import HyperperformanceController


def signal() -> BottleneckSignal:
    return BottleneckSignal(
        bottleneck_id="BN-1",
        kind=BottleneckKind.CI_FEEDBACK,
        summary="Repeated no-delta provider polling slows useful work",
        evidence_refs=("proof:1",),
        throughput_drag=0.7,
        latency_share=0.8,
        queue_wait_share=0.6,
        failure_recurrence=0.7,
        dependency_centrality=0.6,
        owner_burden=0.8,
        cost_pressure=0.3,
        proof_gap=0.4,
        risk=0.2,
        commercial_leverage=0.6,
        differentiation_potential=0.5,
        internal_coverage=0.4,
        affected_missions=3,
        internal_capabilities=("FAILURE_QUEUE","ROUTE_MEMORY","LEARNING_LEDGER"),
    )


class AdaptiveResponseTests(unittest.TestCase):
    def test_no_delta_negative_cache_suppresses_retry(self):
        rt=AdaptiveBottleneckRuntime()
        rt.load_memory(route_memory=[{
            "RouteId":"R1","FailureFingerprint":"FP1","State":"NEGATIVE_CACHED",
            "InvalidationKey":"STATE-A"
        }])
        d=rt.decide(
            signal=signal(),fingerprint="FP1",current_state_signature="STATE-A",
            previous_state_signature="STATE-A",same_semantic_failures=1
        )
        self.assertEqual(AdaptiveAction.SUPPRESS_NO_DELTA,d.action)
        self.assertTrue(d.negative_cache_hit)
        self.assertTrue(d.work_while_waiting)
        self.assertFalse(d.external_effect_authorized)

    def test_champion_is_reused_when_not_negative_cached(self):
        rt=AdaptiveBottleneckRuntime()
        rt.load_memory(route_memory=[{
            "RouteId":"R-CHAMP","FailureFingerprint":"FP2","State":"CHAMPION","Confidence":"HIGH"
        }])
        d=rt.decide(signal=signal(),fingerprint="FP2",current_state_signature="STATE-B")
        self.assertEqual(AdaptiveAction.REUSE_CHAMPION,d.action)
        self.assertEqual("R-CHAMP",d.selected_route_id)

    def test_second_same_semantic_failure_forces_changed_mechanism(self):
        d=AdaptiveBottleneckRuntime().decide(
            signal=signal(),fingerprint="FP3",current_state_signature="S3",
            same_semantic_failures=2
        )
        self.assertEqual(AdaptiveAction.CHANGED_MECHANISM_REQUIRED,d.action)
        self.assertTrue(d.changed_mechanism_required)
        self.assertTrue(d.harvest_required)
        self.assertIsNotNone(d.resolution)

    def test_third_failure_forces_clean_sheet_residual(self):
        d=AdaptiveBottleneckRuntime().decide(
            signal=signal(),fingerprint="FP4",current_state_signature="S4",
            same_semantic_failures=3
        )
        self.assertEqual(AdaptiveAction.HARVEST_BUILD_RESIDUAL,d.action)
        self.assertTrue(d.build_residual_required)
        self.assertEqual(3,d.formation_routes_required)

    def test_unseen_gap_triggers_harvest_compose(self):
        d=AdaptiveBottleneckRuntime().decide(
            signal=signal(),fingerprint="FP5",current_state_signature="S5"
        )
        self.assertEqual(AdaptiveAction.HARVEST_COMPOSE,d.action)
        self.assertTrue(d.harvest_required)
        self.assertIsNotNone(d.resolution)

    def test_hard_gate_does_not_inflate_authority(self):
        d=AdaptiveBottleneckRuntime().decide(
            signal=signal(),fingerprint="FP6",current_state_signature="S6",hard_gate=True
        )
        self.assertEqual(AdaptiveAction.HARD_GATE_WAIT,d.action)
        self.assertTrue(d.work_while_waiting)
        self.assertFalse(d.external_effect_authorized)

    def test_external_wait_routes_to_productive_disjoint_work(self):
        d=AdaptiveBottleneckRuntime().decide(
            signal=signal(),fingerprint="FP7",current_state_signature="S7",external_wait=True
        )
        self.assertEqual(AdaptiveAction.WORK_WHILE_WAITING,d.action)
        self.assertIn("EXECUTE_DEPENDENCY_SAFE_DISJOINT_WORK",d.next_actions)

    def test_learning_success_promotes_champion_record(self):
        rt=AdaptiveBottleneckRuntime()
        d=rt.decide(signal=signal(),fingerprint="FP8",current_state_signature="S8")
        learned=rt.learn_outcome(
            decision=d,success=True,state_signature="S8",evidence_refs=("receipt:8",)
        )
        self.assertEqual("CHAMPION",learned["route_memory"]["State"])
        self.assertEqual("RESOLVED_PROVEN",learned["failure_queue"]["State"])
        self.assertTrue(learned["learning_ledger"]["promotable"])

    def test_learning_failure_negative_caches_exact_state(self):
        rt=AdaptiveBottleneckRuntime()
        d=rt.decide(signal=signal(),fingerprint="FP9",current_state_signature="S9")
        learned=rt.learn_outcome(
            decision=d,success=False,state_signature="S9",evidence_refs=("receipt:9",),
            route_id="R-FAILED"
        )
        self.assertEqual("NEGATIVE_CACHED",learned["route_memory"]["State"])
        self.assertEqual("S9",learned["route_memory"]["InvalidationKey"])
        self.assertFalse(learned["learning_ledger"]["promotable"])

    def test_decision_receipt_is_deterministic(self):
        rt=AdaptiveBottleneckRuntime()
        a=rt.decide(signal=signal(),fingerprint="FP10",current_state_signature="S10")
        b=rt.decide(signal=signal(),fingerprint="FP10",current_state_signature="S10")
        self.assertEqual(a.receipt_sha256,b.receipt_sha256)

    def test_hyperperformance_controller_binds_runtime(self):
        controller=HyperperformanceController()
        d=controller.adaptive_bottleneck_response(
            signal=signal(),fingerprint="FP11",current_state_signature="S11",
            route_memory=[{"RouteId":"R11","FailureFingerprint":"FP11","State":"CHAMPION"}],
        )
        self.assertEqual(AdaptiveAction.REUSE_CHAMPION,d.action)
        self.assertEqual("R11",d.selected_route_id)


if __name__=="__main__":
    unittest.main()
