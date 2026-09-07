from __future__ import annotations

from dataclasses import replace
import unittest

from benchmarking.cfbe_omega.bubbles_work_graph_adapter_v1 import BubblesWorkNode
from benchmarking.cfbe_omega.formation_mesh_v1 import CFBEPathSpec, compile_cfbe_formation_mesh, reconcile_cfbe_formation_mesh
from federation.aurora_cfbe_bridge_v1 import ROLE_MAP, compile_bindings, completion_gate
from federation.aurora_omega_v1 import SpecialistRole
from federation.fuse_ai_bot_multistream_fabric_v1 import PathOutcome, PathState


class AuroraCFBEBridgeV1Tests(unittest.TestCase):
    def omega_witness(self, mission_id="A1"):
        nodes = (BubblesWorkNode("P1", "Proof", "PROOF", "verify proof", priority=1),)
        paths = (CFBEPathSpec("p1", "P1", "DIRECT", "verify proof", "G1"),)
        plan = compile_cfbe_formation_mesh(mission_id=mission_id, objective="finish", nodes=nodes, paths=paths, max_parallel=1)
        return reconcile_cfbe_formation_mesh(plan, (PathOutcome("p1", "P1", "G1", PathState.VERIFIED, evidence_refs=("proof:p1",)),))

    def test_every_aurora_role_has_formation_binding(self):
        bindings = compile_bindings()
        self.assertEqual(set(SpecialistRole), set(ROLE_MAP))
        self.assertEqual(len(SpecialistRole), len(bindings))

    def test_challenger_and_verifier_are_independent_and_never_self_certify(self):
        by_role = {b.aurora_role: b for b in compile_bindings()}
        for role in (SpecialistRole.CHALLENGER, SpecialistRole.VERIFIER):
            item = by_role[role.value]
            self.assertEqual("INDEPENDENT_VERIFICATION", item.independence_domain)
            self.assertFalse(item.may_self_certify)

    def test_complete_requires_both_aurora_and_cfbe_omega(self):
        witness = self.omega_witness("A3")
        held = completion_gate(mission_id="A3", aurora_complete_verified=False, cfbe_witness=witness)
        self.assertFalse(held.completion_allowed)
        complete = completion_gate(mission_id="A3", aurora_complete_verified=True, cfbe_witness=witness)
        self.assertTrue(complete.completion_allowed)
        self.assertEqual("COMPLETE_VERIFIED", complete.state)

    def test_cfbe_not_omega_blocks_even_if_aurora_says_complete(self):
        witness = self.omega_witness("A4")
        held_witness = replace(witness, state="CFBE_FORMATION_CONTINUE", alpha_omega_state="ALPHA_TO_OMEGA_IN_PROGRESS", completion_allowed=False)
        receipt = completion_gate(mission_id="A4", aurora_complete_verified=True, cfbe_witness=held_witness)
        self.assertFalse(receipt.completion_allowed)

    def test_bridge_creates_no_provider_workers_or_effects(self):
        witness = self.omega_witness("A5")
        receipt = completion_gate(mission_id="A5", aurora_complete_verified=True, cfbe_witness=witness)
        self.assertEqual(0, receipt.provider_native_worker_count)
        self.assertFalse(receipt.external_effect)


if __name__ == "__main__":
    unittest.main()
