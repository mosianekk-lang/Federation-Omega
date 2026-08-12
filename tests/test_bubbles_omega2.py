from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bubbles.adaptive_organisation import (
    BubblesOmega2,
    CapabilitySurface,
    MissionManifest,
    NodeKind,
    ProofEdge,
    ProofGraph,
    ProofNode,
    ProofState,
    WorkCandidate,
)


class BubblesOmega2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.omega = BubblesOmega2()
        self.manifest = MissionManifest(
            mission_id="M-1",
            objective="Make system demonstrably live",
            current_source_sha="a" * 40,
            current_maturity="LOCAL_RUNTIME_VERIFIED",
            approved_claims=["Local runtime verified"],
            next_gate="provider execution",
        )

    def candidate(self, **overrides):
        values = dict(
            work_id="W-1",
            objective="Deploy canary",
            proof_gap="provider_execution",
            action_type="PROOF_GAP",
            target="CIOS",
            required_disciplines=("provider", "security"),
            value=9,
            proof_gain=10,
            career_or_product_leverage=9,
            unblock_impact=10,
            cost=2,
            risk=2,
            dependency_load=2,
            executable=True,
            source_sha="a" * 40,
        )
        values.update(overrides)
        return WorkCandidate(**values)

    def test_capability_discovery_does_not_invent_provider_authority(self) -> None:
        result = self.omega.discover_capabilities(
            [
                CapabilitySurface("GitHub", connected=True, can_read=True, can_write=True),
                CapabilitySurface("Cloud", connected=True, can_read=True, can_execute=False, authority="UNKNOWN"),
            ]
        )
        self.assertFalse(result["provider_authority_proven"])
        self.assertIn("Cloud:NO_EXECUTE", result["constraints"])

    def test_dynamic_squad_is_minimum_viable_not_full_roster(self) -> None:
        plan = self.omega.select_squad(
            "M-1",
            proof_gaps=("provider_execution", "provider_readback"),
        )
        self.assertEqual("Bubbles", plan.members[0])
        self.assertIn("Sparks", plan.members)
        self.assertIn("Ledger", plan.members)
        self.assertIn("Sentinel", plan.members)
        self.assertLess(len(plan.members), 12)

    def test_proof_graph_requires_verified_kinds(self) -> None:
        graph = ProofGraph()
        graph.add_node(ProofNode("src", NodeKind.SOURCE, ProofState.VERIFIED))
        graph.add_node(ProofNode("test", NodeKind.TEST, ProofState.VERIFIED))
        graph.add_node(ProofNode("claim", NodeKind.CLAIM, ProofState.PRESENT))
        graph.add_edge(ProofEdge("src", "claim", "supports"))
        graph.add_edge(ProofEdge("test", "claim", "supports"))
        self.assertTrue(graph.claim_ready("claim", (NodeKind.SOURCE, NodeKind.TEST)))
        self.assertFalse(graph.claim_ready("claim", (NodeKind.SOURCE, NodeKind.PROVIDER_READBACK)))

    def test_execution_economics_prefers_higher_proof_gain(self) -> None:
        low = self.candidate(work_id="LOW", proof_gain=2)
        high = self.candidate(work_id="HIGH", proof_gain=10)
        self.assertEqual("HIGH", self.omega.choose_next((low, high), self.manifest).work_id)

    def test_duplicate_work_is_removed(self) -> None:
        item = self.candidate()
        self.manifest.completed_fingerprints.append(item.fingerprint)
        self.assertEqual((), self.omega.rank_work((item,), self.manifest))

    def test_stale_source_candidate_is_removed(self) -> None:
        stale = self.candidate(source_sha="b" * 40)
        self.assertTrue(self.omega.is_stale(stale, self.manifest))
        self.assertEqual((), self.omega.rank_work((stale,), self.manifest))

    def test_new_architecture_is_blocked_while_executable_proof_gap_exists(self) -> None:
        architecture = self.candidate(
            work_id="ARCH",
            action_type="NEW_ARCHITECTURE",
            objective="Invent another framework",
            proof_gap="research",
            target="new-system",
            proof_gain=1,
        )
        proof = self.candidate(work_id="PROOF")
        allowed, reason = self.omega.architecture_gate(architecture, (architecture, proof), self.manifest)
        self.assertFalse(allowed)
        self.assertIn("PROOF", reason)

    def test_dual_output_blocks_unapproved_human_claim(self) -> None:
        result = self.omega.dual_output(
            manifest=self.manifest,
            engineering_receipts=("receipt://local-runtime",),
            proposed_human_claims=("Local runtime verified", "Production deployed"),
        )
        self.assertEqual(("Local runtime verified",), result["human_proof"]["approved_claims"])
        self.assertEqual(("Production deployed",), result["human_proof"]["rejected_unproven_claims"])

    def test_manifest_roundtrip_is_persistent_and_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mission.json"
            self.manifest.save(path)
            loaded = MissionManifest.load(path)
        self.assertEqual(self.manifest.to_dict(), loaded.to_dict())


if __name__ == "__main__":
    unittest.main()
