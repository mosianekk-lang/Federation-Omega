from __future__ import annotations

import unittest
from pathlib import Path

from proofos_omega import ImpactCompiler, ProofPolicy, ProofSelector

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "proofos_omega_policy_v1.json"
BASE = "1" * 40
HEAD = "2" * 40

LOGOS_GOVERNED_PATHS = [
    "logos/Build-Logos.ps1",
    "governance/logos_mevs_proof_v1.json",
    "governance/proofos_omega_policy_extension_logos_mevs_v1.json",
]


def compile_for(paths: list[str]):
    policy = ProofPolicy.from_path(POLICY)
    impact = ImpactCompiler(policy).assess(paths)
    manifest = ProofSelector(policy).compile_manifest(base_sha=BASE, head_sha=HEAD, impact=impact)
    return policy, impact, manifest


class LogosMevsProofOSMappingTests(unittest.TestCase):
    def test_logos_governed_paths_have_bounded_owner_without_full_fallback(self):
        _, impact, manifest = compile_for(LOGOS_GOVERNED_PATHS)
        selected = {item.test_id for item in manifest.selected_tests}
        self.assertIn("FUSE_LOGOS_MEVS_V1", impact.direct_subsystems)
        self.assertFalse(impact.unmapped_production_paths)
        self.assertIn("logos_mevs_v1_source_contract", selected)
        self.assertIn("logos_mevs_v1_proofos_mapping", selected)
        self.assertNotIn("full_federation_fallback", selected)
        self.assertFalse(manifest.selector_state["fallback_full_suite_activated"])

    def test_cpp_source_change_still_selects_logos_courts(self):
        _, impact, manifest = compile_for(["logos/src/graph.cpp"])
        selected = {item.test_id for item in manifest.selected_tests}
        self.assertIn("FUSE_LOGOS_MEVS_V1", impact.direct_subsystems)
        self.assertIn("logos_mevs_v1_source_contract", selected)
        self.assertIn("logos_mevs_v1_proofos_mapping", selected)
        self.assertFalse(manifest.selector_state["fallback_full_suite_activated"])

    def test_header_change_still_selects_logos_courts(self):
        _, impact, manifest = compile_for(["logos/include/logos_graph.h"])
        selected = {item.test_id for item in manifest.selected_tests}
        self.assertIn("FUSE_LOGOS_MEVS_V1", impact.direct_subsystems)
        self.assertIn("logos_mevs_v1_source_contract", selected)
        self.assertIn("logos_mevs_v1_proofos_mapping", selected)

    def test_unknown_production_path_still_fails_safe(self):
        unknown = "future_logos_unknown/new_runtime.py"
        _, impact, manifest = compile_for([unknown])
        selected = {item.test_id for item in manifest.selected_tests}
        self.assertEqual((unknown,), impact.unmapped_production_paths)
        self.assertIn("full_federation_fallback", selected)
        self.assertTrue(manifest.selector_state["fallback_full_suite_activated"])

    def test_mapping_is_additive_and_preserves_authority_ceiling(self):
        policy, _, _ = compile_for(LOGOS_GOVERNED_PATHS)
        self.assertEqual("A1_INTERNAL", policy.raw["authority_ceiling"])
        self.assertFalse(policy.raw["external_effect_default"])
        self.assertIn("logos_mevs_v1_source_contract", policy.tests)
        self.assertIn("logos_mevs_v1_proofos_mapping", policy.tests)
        self.assertIn("full_federation_fallback", policy.tests)


if __name__ == "__main__":
    unittest.main()
