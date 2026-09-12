from __future__ import annotations

import unittest
from pathlib import Path

from proofos_omega import ImpactCompiler, ProofPolicy, ProofSelector


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "proofos_omega_policy_v1.json"
BASE = "1" * 40
HEAD = "2" * 40


class SingleMindCollectiveCognitionProofOSBindingTests(unittest.TestCase):
    def test_single_mind_surface_selects_scoped_courts_without_full_fallback(self) -> None:
        policy = ProofPolicy.from_path(POLICY)
        changed = [
            "federation/single_mind_collective_cognition_v1.py",
            "tests/test_single_mind_collective_cognition_v1.py",
            "tests/test_single_mind_collective_cognition_proofos_v1.py",
            "governance/proofos_omega_policy_extension_single_mind_collective_cognition_v1.json",
            "docs/FUSE_ONE_SINGLE_MIND_COLLECTIVE_COGNITION_V1.md",
        ]
        impact = ImpactCompiler(policy).assess(changed)
        manifest = ProofSelector(policy).compile_manifest(
            base_sha=BASE,
            head_sha=HEAD,
            impact=impact,
        )
        selected = {entry.test_id for entry in manifest.selected_tests}
        self.assertIn("FUSE_ONE_SINGLE_MIND_V1", impact.direct_subsystems)
        self.assertFalse(impact.unmapped_production_paths)
        self.assertIn("fuse_one_single_mind_collective_cognition_v1", selected)
        self.assertIn("fuse_one_single_mind_collective_cognition_proofos_v1", selected)
        self.assertNotIn("full_federation_fallback", selected)
        self.assertFalse(manifest.selector_state["fallback_full_suite_activated"])
        self.assertTrue(manifest.selector_state["omission_proof_complete"])


if __name__ == "__main__":
    unittest.main()
