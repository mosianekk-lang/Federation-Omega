from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.bubbles_work_graph_adapter_v1 import BubblesWorkNode
from benchmarking.cfbe_omega.formation_mesh_v1 import CFBEPathSpec, compile_cfbe_formation_mesh, reconcile_cfbe_formation_mesh
from federation.fuse_ai_bot_multistream_fabric_v1 import PathOutcome, PathState


class CFBEFormationMeshV1Tests(unittest.TestCase):
    def nodes(self):
        return (
            BubblesWorkNode("STATE-LEASE", "Current State Lease", "STATE", "prove freshness", priority=1),
            BubblesWorkNode("PROOF-READBACK", "Provider Readback", "PROOF", "prove semantic readback", priority=2),
        )

    def paths(self):
        return (
            CFBEPathSpec("lease-primary", "STATE-LEASE", "DIRECT", "prove lease via direct provider read", "STATE-A", closure_leverage=.95, mutation_domain="state-read"),
            CFBEPathSpec("lease-alt", "STATE-LEASE", "ALT", "prove lease via independent snapshot", "STATE-B", closure_leverage=.80, mutation_domain="state-read"),
            CFBEPathSpec("proof-primary", "PROOF-READBACK", "DIRECT", "prove semantic provider readback", "PROOF-A", closure_leverage=.90, mutation_domain="provider-read"),
            CFBEPathSpec("proof-alt", "PROOF-READBACK", "ALT", "prove readback through independent verifier", "PROOF-B", closure_leverage=.75, mutation_domain="verifier-read"),
        )

    def test_cfbe_selected_work_becomes_required_streams(self):
        plan = compile_cfbe_formation_mesh(mission_id="M1", objective="close state and proof", nodes=self.nodes(), paths=self.paths(), max_parallel=4)
        self.assertEqual({"STATE-LEASE", "PROOF-READBACK"}, set(plan.stream_coverage))
        self.assertEqual({"STATE-LEASE", "PROOF-READBACK"}, set(plan.formation_plan.required_streams))

    def test_coverage_first_selects_one_route_per_stream_before_extras(self):
        plan = compile_cfbe_formation_mesh(mission_id="M2", objective="coverage first", nodes=self.nodes(), paths=self.paths(), max_parallel=2)
        selected_work = {next(p.work_id for p in self.paths() if p.path_id == pid) for pid in plan.selected_path_ids}
        self.assertEqual({"STATE-LEASE", "PROOF-READBACK"}, selected_work)

    def test_shared_mutation_domain_serializes_alternate_path(self):
        plan = compile_cfbe_formation_mesh(mission_id="M3", objective="serialize collisions", nodes=self.nodes(), paths=self.paths(), max_parallel=4)
        self.assertTrue(set(plan.collision_serialized) & {"lease-primary", "lease-alt"})
        self.assertFalse({"lease-primary", "lease-alt"}.issubset(set(plan.selected_path_ids)))

    def test_semantic_duplicates_are_suppressed(self):
        paths = self.paths() + (CFBEPathSpec("proof-dup", "PROOF-READBACK", "DIRECT", "prove semantic provider readback", "PROOF-C", closure_leverage=.99),)
        plan = compile_cfbe_formation_mesh(mission_id="M4", objective="dedup", nodes=self.nodes(), paths=paths, max_parallel=5)
        self.assertIn("proof-primary", plan.duplicate_suppressed)
        self.assertNotIn("proof-primary", plan.selected_path_ids)
        self.assertIn("proof-dup", plan.selected_path_ids)

    def test_packets_include_specialists_and_recovery_is_dormant(self):
        plan = compile_cfbe_formation_mesh(mission_id="M5", objective="specialists", nodes=self.nodes(), paths=self.paths(), max_parallel=2)
        roles = {p.bot_role for p in plan.work_packets}
        self.assertTrue({"ROUTE", "BUILDER", "FALSIFIER", "EVIDENCE", "WITNESS", "RECOVERY", "SENTINEL"}.issubset(roles))
        recovery = [p for p in plan.work_packets if p.bot_role == "RECOVERY"]
        self.assertTrue(recovery and all(p.held_until_failure for p in recovery))

    def test_effect_authority_remains_false(self):
        plan = compile_cfbe_formation_mesh(mission_id="M6", objective="no effects", nodes=self.nodes(), paths=self.paths(), max_parallel=2)
        self.assertFalse(plan.provider_effect_authorized)
        self.assertFalse(plan.financial_effect_authorized)
        self.assertEqual(0, plan.provider_native_worker_count)

    def test_failure_opens_only_matching_recovery_packet_and_other_stream_can_finish(self):
        plan = compile_cfbe_formation_mesh(mission_id="M7", objective="recover one path", nodes=self.nodes(), paths=self.paths(), max_parallel=2)
        state_pid = next(pid for pid in plan.selected_path_ids if pid.startswith("lease-"))
        proof_pid = next(pid for pid in plan.selected_path_ids if pid.startswith("proof-"))
        witness = reconcile_cfbe_formation_mesh(plan, (
            PathOutcome(state_pid, "STATE-LEASE", "STATE-A" if state_pid == "lease-primary" else "STATE-B", PathState.FAILED, failure_fingerprint="LEASE_ROUTE_FAIL", retry_after_predicate="SOURCE_REFRESHED"),
            PathOutcome(proof_pid, "PROOF-READBACK", "PROOF-A" if proof_pid == "proof-primary" else "PROOF-B", PathState.VERIFIED, evidence_refs=("proof:ok",)),
        ))
        self.assertFalse(witness.completion_allowed)
        self.assertTrue(any(state_pid in item for item in witness.recovery_packet_ids))
        self.assertIn("PROOF-READBACK", witness.completed_streams)

    def test_all_streams_verified_reaches_alpha_omega(self):
        plan = compile_cfbe_formation_mesh(mission_id="M8", objective="reach omega", nodes=self.nodes(), paths=self.paths(), max_parallel=2)
        outcomes = []
        for pid in plan.selected_path_ids:
            spec = next(p for p in self.paths() if p.path_id == pid)
            outcomes.append(PathOutcome(pid, spec.work_id, spec.independent_group, PathState.VERIFIED, evidence_refs=(f"proof:{pid}",)))
        witness = reconcile_cfbe_formation_mesh(plan, tuple(outcomes))
        self.assertTrue(witness.completion_allowed)
        self.assertEqual("CFBE_FORMATION_OMEGA_VERIFIED", witness.state)
        self.assertEqual("OMEGA", witness.alpha_omega_state)

    def test_missing_path_for_selected_stream_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "CFBE_SELECTED_STREAM_WITHOUT_PATH"):
            compile_cfbe_formation_mesh(mission_id="M9", objective="missing", nodes=self.nodes(), paths=(self.paths()[0],), max_parallel=2)


if __name__ == "__main__":
    unittest.main()
