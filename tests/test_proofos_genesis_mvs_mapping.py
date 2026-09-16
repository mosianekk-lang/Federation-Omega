from __future__ import annotations

import unittest
from pathlib import Path

from proofos_omega import ImpactCompiler, ProofPolicy, ProofSelector

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "proofos_omega_policy_v1.json"
BASE = "1" * 40
HEAD = "2" * 40

GENESIS_PATHS = [
    "genesis/Build-Genesis.ps1",
    "genesis/admission/admission_court.cpp",
    "genesis/court/court_core.cpp",
    "genesis/court/court_io.cpp",
    "genesis/include/fuse/base.h",
    "genesis/src/fuse_entry.cpp",
    "genesis/src/recovery.cpp",
    "genesis/src/win_process.cpp",
    "governance/proofos_omega_policy_extension_genesis_mvs_v1.json",
]

def compile_for(paths: list[str]):
    policy = ProofPolicy.from_path(POLICY)
    impact = ImpactCompiler(policy).assess(paths)
    manifest = ProofSelector(policy).compile_manifest(
        base_sha=BASE, head_sha=HEAD, impact=impact
    )
    return policy, impact, manifest

class GenesisMvsProofOSMappingTests(unittest.TestCase):
    def test_genesis_is_core_owned_without_repository_fallback(self):
        _, impact, manifest = compile_for(GENESIS_PATHS)
        selected = {x.test_id for x in manifest.selected_tests}
        self.assertIn("GENESIS_MVS", impact.direct_subsystems)
        self.assertEqual("R4_CORE", impact.risk.name)
        self.assertFalse(impact.unmapped_production_paths)
        self.assertIn("genesis_mvs_source_contract", selected)
        self.assertIn("genesis_mvs_proofos_mapping", selected)
        self.assertNotIn("full_federation_fallback", selected)
        self.assertFalse(manifest.selector_state["fallback_full_suite_activated"])

    def test_mapping_extension_is_itself_owned(self):
        _, impact, manifest = compile_for(
            ["governance/proofos_omega_policy_extension_genesis_mvs_v1.json"]
        )
        selected = {x.test_id for x in manifest.selected_tests}
        self.assertIn("GENESIS_MVS", impact.direct_subsystems)
        self.assertFalse(impact.unmapped_production_paths)
        self.assertIn("genesis_mvs_proofos_mapping", selected)
        self.assertNotIn("full_federation_fallback", selected)

    def test_unknown_production_path_still_fails_safe(self):
        _, impact, manifest = compile_for(
            ["future_genesis_unknown/new_runtime.py"]
        )
        selected = {x.test_id for x in manifest.selected_tests}
        self.assertEqual(
            ("future_genesis_unknown/new_runtime.py",),
            impact.unmapped_production_paths,
        )
        self.assertIn("full_federation_fallback", selected)
        self.assertTrue(manifest.selector_state["fallback_full_suite_activated"])

    def test_authority_ceiling_and_external_effect_default_do_not_change(self):
        policy, _, _ = compile_for(GENESIS_PATHS)
        self.assertEqual("A1_INTERNAL", policy.raw["authority_ceiling"])
        self.assertFalse(policy.raw["external_effect_default"])
        self.assertEqual(0, policy.sentinel_percent)

if __name__ == "__main__":
    unittest.main()
