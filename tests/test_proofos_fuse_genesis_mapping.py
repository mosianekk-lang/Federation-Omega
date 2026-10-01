from __future__ import annotations

import unittest
from pathlib import Path

from proofos_omega import ImpactCompiler, ProofPolicy, ProofSelector

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "proofos_omega_policy_v1.json"
BASE = "1" * 40
HEAD = "2" * 40

GENESIS_PATHS = [
    "fuse_genesis/currentness.py",
    "fuse_genesis/resident_host.py",
    "fuse_genesis/runtime_continuity.py",
]

def compile_for(paths):
    policy = ProofPolicy.from_path(POLICY)
    impact = ImpactCompiler(policy).assess(paths)
    manifest = ProofSelector(policy).compile_manifest(
        base_sha=BASE, head_sha=HEAD, impact=impact
    )
    return policy, impact, manifest

class FuseGenesisProofOSMappingTests(unittest.TestCase):
    def test_genesis_paths_use_bounded_court_without_full_fallback(self):
        _, impact, manifest = compile_for(GENESIS_PATHS)
        selected = {item.test_id for item in manifest.selected_tests}
        self.assertIn("FUSE_GENESIS", impact.direct_subsystems)
        self.assertFalse(impact.unmapped_production_paths)
        self.assertIn("genesis_runtime_contracts", selected)
        self.assertNotIn("full_federation_fallback", selected)
        self.assertFalse(manifest.selector_state["fallback_full_suite_activated"])

    def test_genesis_court_is_registered_and_authority_neutral(self):
        policy, _, _ = compile_for(GENESIS_PATHS)
        self.assertIn("genesis_runtime_contracts", policy.tests)
        self.assertEqual("A1_INTERNAL", policy.raw["authority_ceiling"])
        self.assertFalse(policy.raw["external_effect_default"])

    def test_unknown_future_runtime_still_falls_back(self):
        unknown = "future_genesis_unknown/runtime.py"
        _, impact, manifest = compile_for([unknown])
        self.assertEqual((unknown,), impact.unmapped_production_paths)
        self.assertIn("full_federation_fallback", {x.test_id for x in manifest.selected_tests})

if __name__ == "__main__":
    unittest.main()
