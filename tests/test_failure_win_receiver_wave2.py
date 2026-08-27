from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ao_harmonic_v3.failure_win_v2 import (
    FailureEventType,
    FailureObservation,
    FailureToOperationalWinKernelV2,
    FailureWinRequest,
    FailureWinState,
    RecoveryRoute,
)
from ao_harmonic_v3.models import PerformanceVector
from ao_harmonic_v3.science_and_routes import Hypothesis, OmegaScientia
from federation_consolidation.sovara_event_broker import SovaraEventBroker
from superior_logic.oops_acme import ContinuationContext, ContinuationDecision, evaluate_continuation


class FailureWinReceiverWave2Tests(unittest.TestCase):
    @staticmethod
    def _evaluate(system_id: str, failure_code: str, route_id: str):
        incumbent = PerformanceVector(quality=8, reliability=8, proof=8, speed=2, owner_burden=1)
        candidate = PerformanceVector(
            quality=8,
            reliability=8,
            proof=8,
            speed=5,
            owner_time_recovered=2,
            recovery_gain=2,
            owner_burden=0,
        )
        return FailureToOperationalWinKernelV2().evaluate(
            FailureWinRequest(
                observation=FailureObservation(
                    event_id=f"FWV2-{failure_code}-CANARY",
                    event_type=FailureEventType.PRECURSOR_RISK,
                    system_id=system_id,
                    objective="preempt a synthetic control-plane drift risk",
                    claim="a bounded internal control may become stale",
                    observed_fruit="synthetic no-effect native control evidence only",
                    desired_outcome="prewarm a current reversible proof/readback route",
                    failure_code=failure_code,
                    material=False,
                    precursor_signals=("synthetic-drift-fixture",),
                ),
                incumbent=incumbent,
                routes=(
                    RecoveryRoute(
                        route_id=route_id,
                        route_type="REROUTE",
                        performance=candidate,
                        proof_strength=1.0,
                        reversibility=1.0,
                        strategic_value=1.0,
                        expected_value=2.0,
                    ),
                ),
            )
        )

    def assert_invocation_open(self, result, route_id: str) -> None:
        self.assertEqual(FailureWinState.PREEMPTION_READY, result.state)
        self.assertTrue(result.vector_gate_passed)
        self.assertIn(route_id, result.selected_route_ids)
        self.assertFalse(result.proof_graph.complete)
        self.assertNotEqual(FailureWinState.OPERATIONAL_WIN_VERIFIED, result.state)

    def test_superior_logic_continuation_governor_then_v2(self) -> None:
        native = evaluate_continuation(
            ContinuationContext(
                work_authorized=True,
                material_work_available=True,
                authority_available=True,
                credible_routes_remaining=True,
                mission_complete=False,
                current_turn_active=True,
                persistent_runtime_proven=False,
            )
        )
        self.assertEqual(ContinuationDecision.CONTINUE_ACTIVE_TURN, native.decision)
        self.assertTrue(native.continue_active_turn)
        self.assertFalse(native.background_execution_allowed)
        route_id = "superior-current-continuation-fixture"
        result = self._evaluate(
            "Superior Logic Doctrine",
            "SYNTHETIC_SUPERIOR_CONTINUATION_DRIFT",
            route_id,
        )
        self.assert_invocation_open(result, route_id)

    def test_sovara_cloudevent_contract_then_v2(self) -> None:
        broker = SovaraEventBroker(project_id="synthetic-project", publisher=object())
        event = broker.create_cloudevent(
            "failure_win.precursor",
            "failure-win-v2-canary",
            {"receiver": "SOVARA", "external_effect": False},
            event_id="FWV2-SOVARA-CLOUDEVENT-CANARY",
            event_time="2026-08-27T03:00:00Z",
        )
        self.assertEqual("1.0", event["specversion"])
        self.assertEqual("com.sovara.failure_win.precursor", event["type"])
        self.assertEqual(64, len(event["data_sha256"]))
        route_id = "sovara-current-event-envelope-fixture"
        result = self._evaluate("SOVARA Ω", "SYNTHETIC_SOVARA_EVENT_DRIFT", route_id)
        self.assert_invocation_open(result, route_id)

    def test_reality_guard_fault_manager_then_v2(self) -> None:
        # RealityGuard is intentionally imported from its package root at runtime
        # so the existing subpackage remains independently source-scoped.
        import sys
        root = Path(__file__).resolve().parents[1] / "realityguard_v0.4.0" / "src"
        sys.path.insert(0, str(root))
        try:
            from realityguard.faultbook import FaultBookManager, FaultRecord
            with tempfile.TemporaryDirectory() as tmp:
                manager = FaultBookManager(Path(tmp) / "registry.json")
                record = FaultRecord(
                    fault_id="FWV2-REALITY-GUARD-CANARY",
                    title="synthetic receiver canary",
                    scope="Reality Guard",
                    status="OPEN",
                    source_kind="SYNTHETIC_TEST",
                    source_ref="in-memory-canary",
                    source_sha256="a" * 64,
                    event_count=1,
                    chain_head="b" * 64,
                    owner_authority="A1_INTERNAL",
                    truth_state="TEST_ONLY",
                    lifecycle_state="TESTING",
                    registered_at="2026-08-27T03:00:00Z",
                    fault_classes=("RECEIVER_CANARY",),
                    open_requirements=("real_failure_proof",),
                )
                receipt = manager.register(record)
                self.assertEqual("REGISTERED", receipt["decision"])
                state = manager.state()
                self.assertEqual(1, state["active_fault_books"])
                self.assertEqual("ADAPTER_REQUIRED", state["provider_binding"])
        finally:
            if sys.path and sys.path[0] == str(root):
                sys.path.pop(0)
        route_id = "reality-guard-current-faultbook-fixture"
        result = self._evaluate("Reality Guard", "SYNTHETIC_REALITY_GUARD_DRIFT", route_id)
        self.assert_invocation_open(result, route_id)

    def test_omega_scientia_falsification_then_v2(self) -> None:
        challenge = OmegaScientia().challenge(
            Hypothesis(
                hypothesis_id="FWV2-SCIENTIA-H1",
                statement="A route is stale because its dependency changed",
                supporting_observations=["dependency fixture changed"],
                conflicting_observations=["transport still responds"],
                predicted_evidence=["fresh dependency hash differs"],
                falsifiers=["fresh dependency hash is unchanged"],
                confidence=0.6,
            )
        )
        self.assertTrue(challenge["falsifiers"])
        self.assertTrue(challenge["contradictions"])
        route_id = "scientia-current-falsification-fixture"
        result = self._evaluate(
            "Next Frontier AI Bible / Ω-SCIENTIA",
            "SYNTHETIC_SCIENTIA_CAUSAL_DRIFT",
            route_id,
        )
        self.assert_invocation_open(result, route_id)


if __name__ == "__main__":
    unittest.main()
