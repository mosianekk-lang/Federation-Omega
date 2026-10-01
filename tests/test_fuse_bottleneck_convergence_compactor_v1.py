import hashlib
import unittest

from benchmarking.cfbe_omega.mission_execution_kernel_vnext.convergence import (
    CausalInvalidationGraph,
    ConvergenceError,
    EffectState,
    FastPathRequest,
    GraphRecord,
    LeaseProjection,
    LeaseState,
    NegativeRouteFact,
    NegativeRouteMemory,
    ProjectionState,
    ProofState,
    ScopedFence,
    ScopedFenceSet,
    TransitionEnvelope,
    audit_cross_plane_invariants,
    compact_active_graph,
    evaluate_fast_path,
    evaluate_transition,
    scopes_overlap,
)


def h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def transition(**overrides):
    values = dict(
        transition_id="T-1",
        mission_id="MISSION-1",
        mission_version=1,
        lease_id="F1",
        fencing_token=1,
        scopes=("repo:omega/pkg/a",),
        source_before="a" * 40,
        source_after="b" * 40,
        source_admitted=True,
        lease_state=LeaseState.RELEASED,
        effect_state=EffectState.NONE,
        proof_state=ProofState.PASS,
        reducer_state=ProjectionState.APPLIED,
        required_receivers=("work-plane", "kdv"),
        receiver_states={
            "work-plane": ProjectionState.ACKED,
            "kdv": ProjectionState.ACKED,
        },
    )
    values.update(overrides)
    return TransitionEnvelope.create(**values)


class ConvergenceTests(unittest.TestCase):
    def test_committed_transition_requires_released_lease(self):
        with self.assertRaisesRegex(ConvergenceError, "SOURCE_ADMISSION_REQUIRES_RELEASED_LEASE"):
            transition(lease_state=LeaseState.ACTIVE)

    def test_commit_fan_in_passes_only_when_all_receivers_ack(self):
        item = transition()
        self.assertTrue(item.coordination_complete)
        self.assertEqual("COMMIT_READY", evaluate_transition(item).state)

    def test_missing_receiver_ack_holds_transition(self):
        item = transition(receiver_states={"work-plane": ProjectionState.ACKED})
        self.assertFalse(item.coordination_complete)
        self.assertIn("RECEIVER_ACK:kdv", item.pending_predicates())

    def test_unknown_effect_blocks_release(self):
        with self.assertRaisesRegex(ConvergenceError, "UNKNOWN_EFFECT_BLOCKS_RELEASE"):
            transition(effect_state=EffectState.UNKNOWN)

    def test_transition_hash_is_deterministic(self):
        self.assertEqual(transition().transition_sha256, transition().transition_sha256)

    def test_scope_overlap_is_prefix_aware(self):
        self.assertTrue(scopes_overlap("repo:omega/pkg", "repo:omega/pkg/a.py"))
        self.assertFalse(scopes_overlap("repo:omega/pkg/a", "repo:omega/pkg/b"))

    def test_disjoint_scoped_fences_can_run_concurrently(self):
        fences = ScopedFenceSet((ScopedFence("F1", 1, ("repo:omega/a",)),))
        fences.acquire(ScopedFence("F2", 2, ("repo:omega/b",)))
        self.assertEqual(("F1", "F2"), tuple(item.lease_id for item in fences.active))

    def test_overlapping_scoped_fence_is_rejected(self):
        fences = ScopedFenceSet((ScopedFence("F1", 1, ("repo:omega/a",)),))
        with self.assertRaisesRegex(ConvergenceError, "FENCE_SCOPE_CONFLICT"):
            fences.acquire(ScopedFence("F2", 2, ("repo:omega/a/file.py",)))

    def test_stale_fencing_token_is_rejected(self):
        fences = ScopedFenceSet((ScopedFence("F10", 10, ("repo:omega/a",), LeaseState.RELEASED),))
        with self.assertRaisesRegex(ConvergenceError, "NON_MONOTONIC_FENCING_TOKEN"):
            fences.acquire(ScopedFence("F9", 9, ("repo:omega/b",)))

    def test_negative_route_suppresses_unchanged_failure(self):
        fact = NegativeRouteFact("R1", "publish", h("ctx"), "AUTHORITY_ABSENT", ("AUTHORITY_CHANGE",))
        memory = NegativeRouteMemory((fact,))
        self.assertTrue(memory.is_suppressed("R1", "publish", context_sha256=h("ctx")))

    def test_negative_route_wakes_on_material_signal(self):
        fact = NegativeRouteFact("R1", "publish", h("ctx"), "AUTHORITY_ABSENT", ("AUTHORITY_CHANGE",))
        memory = NegativeRouteMemory((fact,))
        self.assertFalse(memory.is_suppressed(
            "R1", "publish", context_sha256=h("ctx"), material_signals=("AUTHORITY_CHANGE",)
        ))

    def test_negative_route_wakes_when_context_changes(self):
        fact = NegativeRouteFact("R1", "publish", h("ctx"), "AUTHORITY_ABSENT", ("AUTHORITY_CHANGE",))
        memory = NegativeRouteMemory((fact,))
        self.assertFalse(memory.is_suppressed("R1", "publish", context_sha256=h("new")))

    def test_causal_invalidation_only_hits_descendants(self):
        graph = CausalInvalidationGraph(
            {
                "proof:a": ("source:a",),
                "proof:b": ("policy:b",),
                "receiver:a": ("proof:a",),
                "receiver:b": ("proof:b",),
            }
        )
        self.assertEqual(("proof:a", "receiver:a"), graph.descendants(("source:a",)))

    def test_compaction_removes_history_from_live_graph_but_preserves_digest(self):
        receipt = compact_active_graph(
            (
                GraphRecord("A", "ACTIVE", h("a")),
                GraphRecord("B", "COMPLETE_VERIFIED", h("b")),
                GraphRecord("C", "DORMANT", h("c")),
            )
        )
        self.assertEqual(("A",), receipt.active_ids)
        self.assertEqual(("C",), receipt.dormant_ids)
        self.assertEqual(("B",), receipt.historical_ids)
        self.assertEqual(64, len(receipt.history_sha256))

    def test_fast_path_allows_exact_current_callable_route(self):
        decision = evaluate_fast_path(FastPathRequest("A1", "CAP1", True, True, True, True, True))
        self.assertTrue(decision.direct)

    def test_fast_path_rejects_uncallable_route(self):
        decision = evaluate_fast_path(FastPathRequest("A1", "CAP1", True, False, True, True, True))
        self.assertFalse(decision.direct)
        self.assertIn("CALLABILITY_REQUIRED", decision.reasons)

    def test_effect_fast_path_requires_rollback(self):
        decision = evaluate_fast_path(
            FastPathRequest("A1", "CAP1", True, True, True, True, True, effectful=True, rollback_supported=False)
        )
        self.assertFalse(decision.direct)
        self.assertIn("ROLLBACK_REQUIRED_FOR_EFFECT_FAST_PATH", decision.reasons)

    def test_active_lease_without_mission_is_detected(self):
        audit = audit_cross_plane_invariants(
            ("MISSION-1",),
            (LeaseProjection("F1", "MISSION-UNKNOWN", 1, LeaseState.ACTIVE, ("repo:omega/a",)),),
        )
        self.assertFalse(audit.clean)
        self.assertTrue(any(item.startswith("ACTIVE_LEASE_WITHOUT_MISSION") for item in audit.defects))

    def test_overlapping_active_fences_are_detected_cross_plane(self):
        audit = audit_cross_plane_invariants(
            ("MISSION-1", "MISSION-2"),
            (
                LeaseProjection("F1", "MISSION-1", 1, LeaseState.ACTIVE, ("repo:omega/a",)),
                LeaseProjection("F2", "MISSION-2", 2, LeaseState.ACTIVE, ("repo:omega/a/x",)),
            ),
        )
        self.assertTrue(any(item.startswith("OVERLAPPING_ACTIVE_FENCES") for item in audit.defects))

    def test_clean_cross_plane_invariants(self):
        audit = audit_cross_plane_invariants(
            ("MISSION-1", "MISSION-2"),
            (
                LeaseProjection("F1", "MISSION-1", 1, LeaseState.ACTIVE, ("repo:omega/a",)),
                LeaseProjection("F2", "MISSION-2", 2, LeaseState.ACTIVE, ("repo:omega/b",)),
            ),
        )
        self.assertTrue(audit.clean)


if __name__ == "__main__":
    unittest.main()
