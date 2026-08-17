from __future__ import annotations

from dataclasses import replace
import unittest

from ao_harmonic_v3.jarvis_ao5 import (
    CapabilityRealityState,
    CapabilityRecord,
    ChallengeState,
    ConclusionRecord,
    DAGNode,
    DAGEdge,
    DecisionDAG,
    ExecutionState,
    FailureEvent,
    JarvisAO5Engine,
    JarvisAO5Error,
    PathRecord,
    PathState,
    PreflightInput,
    TruthState,
)
from verification.jarvis_ao5_public_safe_canary import build_public_safe_request


class StateMachineTests(unittest.TestCase):
    def test_execution_requires_preflight(self) -> None:
        engine = JarvisAO5Engine()
        engine.state = ExecutionState.S10_SCHEDULING
        with self.assertRaisesRegex(JarvisAO5Error, "PREFLIGHT"):
            engine.transition(ExecutionState.S11_EXECUTION)

    def test_release_requires_all_gates(self) -> None:
        engine = JarvisAO5Engine()
        engine.state = ExecutionState.S20_READBACK_VERIFY
        engine.preflight_passed = True
        with self.assertRaisesRegex(JarvisAO5Error, "ALL_GATES"):
            engine.transition(ExecutionState.S21_RELEASE)

    def test_external_release_requires_owner_approval(self) -> None:
        engine = JarvisAO5Engine()
        engine.state = ExecutionState.S20_READBACK_VERIFY
        engine.adversarial_gate = ChallengeState.PASS
        engine.neutral_gate = ChallengeState.PASS
        engine.semantic_gate = ChallengeState.PASS
        with self.assertRaisesRegex(JarvisAO5Error, "OWNER_APPROVAL"):
            engine.transition(
                ExecutionState.S21_RELEASE,
                consequential_external_action=True,
                owner_approval=False,
            )

    def test_invalid_state_skip_fails(self) -> None:
        engine = JarvisAO5Engine()
        with self.assertRaisesRegex(JarvisAO5Error, "INVALID_STATE_TRANSITION"):
            engine.transition(ExecutionState.S03_RECONCILE)


class CapabilityAndDAGTests(unittest.TestCase):
    def test_capability_overclaim_fails(self) -> None:
        cap = CapabilityRecord(
            "CAP-1",
            "Current-turn analysis",
            CapabilityRealityState.C1_ACTIVE_TURN,
        )
        with self.assertRaisesRegex(JarvisAO5Error, "CAPABILITY_OVERCLAIM"):
            cap.assert_claim(CapabilityRealityState.C4_PROVIDER_VERIFIED)

    def test_dag_cycle_fails(self) -> None:
        dag = DecisionDAG()
        dag.add_node(DAGNode("A", "FACT_NODE", "A"))
        dag.add_node(DAGNode("B", "DECISION_NODE", "B"))
        dag.add_edge(DAGEdge("A", "B", "SUPPORTS"))
        with self.assertRaisesRegex(JarvisAO5Error, "DAG_CYCLE"):
            dag.add_edge(DAGEdge("B", "A", "DEPENDS_ON"))

    def test_hidden_spof_is_detected(self) -> None:
        paths = [
            PathRecord("P1", "O1", "EVIDENCE", "one", dependencies=["X"]),
            PathRecord("P2", "O1", "MERITS", "two", dependencies=["X"]),
            PathRecord("P3", "O1", "REBUTTAL", "three", dependencies=["X"]),
        ]
        findings = JarvisAO5Engine.hidden_spof_scan(paths)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["priority"], "CRITICAL")


class BudgetAndQualityTests(unittest.TestCase):
    def test_path_budget_is_three_active_three_shadow(self) -> None:
        paths = []
        for index in range(8):
            paths.append(
                PathRecord(
                    f"P{index}",
                    "O1",
                    "EVIDENCE",
                    f"path {index}",
                    legal_viability=1 - index * 0.05,
                    factual_strength=0.9,
                    evidence_strength=0.9,
                    decision_impact=0.9,
                    remedy_value=0.9,
                    timeliness=0.9,
                    risk=0.2,
                    dependency_cost=0.3,
                    execution_cost=0.3,
                )
            )
        active, shadow, pruned = JarvisAO5Engine.rank_paths(paths)
        self.assertEqual(len(active), 3)
        self.assertEqual(len(shadow), 3)
        self.assertEqual(len(pruned), 2)
        self.assertTrue(all(path.status is PathState.ACTIVE for path in active))

    def test_preflight_auto_decomposes_large_corpus(self) -> None:
        result = JarvisAO5Engine.preflight_assess(
            "T1",
            PreflightInput(page_count=51, file_count=9, domain_count=4),
            path_ids=["P1"],
            stream_ids=["S1"],
            persistence_target="TEST",
        )
        self.assertTrue(result.auto_decompose)
        self.assertIn(result.complexity.value, {"C4_VERY_LARGE", "C5_EXTREME"})

    def test_semantic_firewall_blocks_absolute_inference(self) -> None:
        bad = ConclusionRecord(
            "C1",
            "This definitively proves intent.",
            "T1",
            "MOTIVE",
            ("F1",),
            "P1",
            ("S1",),
            TruthState.INFERENCE,
        )
        result = JarvisAO5Engine.semantic_firewall([bad])
        self.assertEqual(result["state"], "BLOCKED")

    def test_replay_requires_source_and_fact_lineage(self) -> None:
        bad = ConclusionRecord(
            "C1", "bounded", "T1", "E1", (), "P1", (), TruthState.VERIFIED
        )
        result = JarvisAO5Engine.replay_test([bad])
        self.assertEqual(result["state"], "NOT_DURABLY_VERIFIED")


class FailureLearningTests(unittest.TestCase):
    def test_recurrence_three_requires_redesign(self) -> None:
        failure = FailureEvent(
            "F1",
            "RESTORE",
            "wrong",
            "right",
            "root",
            "signal",
            "detector",
            "repair",
            "test",
            recurrence_count=3,
        )
        self.assertEqual(failure.required_response, "REDESIGN_OR_ROLLBACK")

    def test_owner_correction_becomes_failure_telemetry(self) -> None:
        engine = JarvisAO5Engine()
        event = engine.record_owner_correction(
            failure_id="F-OWNER-1",
            observed_state="generic system restore",
            expected_state="exact workstream restore",
            available_signal="dedicated workstream artifacts",
            repair="exact namespace gate",
            regression_test="generic alias must fail",
        )
        self.assertEqual(event.failure_class, "OWNER_DETECTED")
        self.assertEqual(len(engine.failures), 1)


class PublicSafeForensicCanaryTests(unittest.TestCase):
    def test_bounded_public_safe_forensic_run(self) -> None:
        engine = JarvisAO5Engine()
        result = engine.run(build_public_safe_request())
        self.assertEqual(result.execution_state, ExecutionState.S22_NEXT_ACTION.value)
        self.assertEqual(len(result.active_paths), 3)
        self.assertEqual(result.replay_state, "PASS")
        self.assertEqual(result.semantic_qa["state"], "PASS")
        self.assertFalse(result.truth_boundary["external_effect"])
        self.assertIn("G2", result.next_action)
        self.assertEqual(len(result.receipt_sha256), 64)
        self.assertTrue(result.hidden_spofs)

    def test_external_effect_is_blocked_without_approval(self) -> None:
        request = replace(build_public_safe_request(), external_action_requested=True)
        with self.assertRaisesRegex(JarvisAO5Error, "OWNER_APPROVAL"):
            JarvisAO5Engine().run(request)


if __name__ == "__main__":
    unittest.main()
