from __future__ import annotations

import unittest
from pathlib import Path

from proofos_omega import ImpactCompiler, ProofPolicy, ProofSelector


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "proofos_omega_policy_v1.json"
BASE = "1" * 40
HEAD = "2" * 40

WOAF_PRODUCTION_PATHS = [
    ".github/workflows/fuse-windows-relay-cloud-run-v1.yml",
    "governance/fuse_windows_execution_plane_v1.json",
    "governance/proofos_omega_policy_extension_woaf_v21.json",
    "windows_federation_plane/src/federation_windows_plane/mcp_service.py",
    "windows_federation_plane/src/federation_windows_plane/trust_spine_v21.py",
    "phoenix/export_policy.json",
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


class WoafV21ProofOSMappingTests(unittest.TestCase):
    def test_woaf_production_paths_are_owned_without_repository_fallback(self):
        _, impact, manifest = compile_for(WOAF_PRODUCTION_PATHS)
        selected = {item.test_id for item in manifest.selected_tests}
        self.assertIn("WOAF_V21", impact.direct_subsystems)
        self.assertFalse(impact.unmapped_production_paths)
        self.assertIn("woaf_v21_source_contract", selected)
        self.assertIn("woaf_v21_proofos_mapping", selected)
        self.assertNotIn("full_federation_fallback", selected)
        self.assertFalse(manifest.selector_state["fallback_full_suite_activated"])

    def test_unknown_production_path_still_fails_safe_to_full_fallback(self):
        _, impact, manifest = compile_for(["future_woaf_unknown/new_runtime.py"])
        selected = {item.test_id for item in manifest.selected_tests}
        self.assertEqual(
            ("future_woaf_unknown/new_runtime.py",),
            impact.unmapped_production_paths,
        )
        self.assertIn("full_federation_fallback", selected)
        self.assertTrue(manifest.selector_state["fallback_full_suite_activated"])

    def test_woaf_mapping_is_additive_and_keeps_internal_authority_ceiling(self):
        policy, _, _ = compile_for(WOAF_PRODUCTION_PATHS)
        self.assertEqual("A1_INTERNAL", policy.raw["authority_ceiling"])
        self.assertFalse(policy.raw["external_effect_default"])
        self.assertEqual(0, policy.sentinel_percent)


if __name__ == "__main__":
    unittest.main()
