from __future__ import annotations

import unittest
from pathlib import Path

from proofos_omega import ImpactCompiler, ProofPolicy, ProofSelector


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "proofos_omega_policy_v1.json"
BASE = "1" * 40
HEAD = "2" * 40
MEMORY_IMPLEMENTATION = ROOT / "federation_consolidation" / "fuseone_memory_continuum.py"
MEMORY_FOCUSED_TEST = ROOT / "tests" / "test_fuseone_memory_continuum.py"

MEMORY_PRODUCTION_PATHS = [
    "federation_consolidation/fuseone_memory_continuum.py",
    "governance/proofos_omega_policy_extension_fuseone_memory_continuum_v1.json",
]


def compile_for(paths: list[str]):
    policy = ProofPolicy.from_path(POLICY)
    impact = ImpactCompiler(policy).assess(paths)
    manifest = ProofSelector(policy).compile_manifest(
        base_sha=BASE,
        head_sha=HEAD,
        impact=impact,
    )
    return policy, impact, manifest


class FuseOneMemoryContinuumProofOSMappingTests(unittest.TestCase):
    def test_memory_production_paths_are_owned_without_repository_fallback(self):
        _, impact, manifest = compile_for(MEMORY_PRODUCTION_PATHS)
        selected = {item.test_id for item in manifest.selected_tests}
        self.assertIn("FUSEONE_MEMORY_CONTINUUM_V1", impact.direct_subsystems)
        self.assertFalse(impact.unmapped_production_paths)
        self.assertIn("fuseone_memory_continuum_v1_source_contract", selected)
        self.assertIn("fuseone_memory_continuum_v1_proofos_mapping", selected)
        self.assertNotIn("full_federation_fallback", selected)
        self.assertFalse(manifest.selector_state["fallback_full_suite_activated"])

    def test_memory_proof_ids_are_registered_in_combined_policy(self):
        policy, _, _ = compile_for(MEMORY_PRODUCTION_PATHS)
        registered = set(policy.tests)
        self.assertIn("fuseone_memory_continuum_v1_source_contract", registered)
        self.assertIn("fuseone_memory_continuum_v1_proofos_mapping", registered)
        self.assertIn("full_federation_fallback", registered)

    def test_memory_source_contract_bootstraps_only_while_target_is_absent(self):
        policy, _, _ = compile_for(MEMORY_PRODUCTION_PATHS)
        source_contract = policy.tests["fuseone_memory_continuum_v1_source_contract"]
        self.assertTrue(source_contract.optional_if_missing)
        if MEMORY_IMPLEMENTATION.exists():
            self.assertTrue(
                MEMORY_FOCUSED_TEST.exists(),
                "Memory implementation must not exist without its focused source contract",
            )

    def test_unknown_production_path_still_fails_safe_to_full_fallback(self):
        unknown = "future_fuseone_memory_unknown/new_runtime.py"
        _, impact, manifest = compile_for([unknown])
        selected = {item.test_id for item in manifest.selected_tests}
        self.assertEqual((unknown,), impact.unmapped_production_paths)
        self.assertIn("full_federation_fallback", selected)
        self.assertTrue(manifest.selector_state["fallback_full_suite_activated"])

    def test_memory_mapping_is_additive_and_keeps_internal_authority_ceiling(self):
        policy, _, _ = compile_for(MEMORY_PRODUCTION_PATHS)
        self.assertEqual("A1_INTERNAL", policy.raw["authority_ceiling"])
        self.assertFalse(policy.raw["external_effect_default"])
        self.assertEqual(0, policy.sentinel_percent)


if __name__ == "__main__":
    unittest.main()
