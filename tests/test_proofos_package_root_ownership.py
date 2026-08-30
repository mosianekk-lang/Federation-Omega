from __future__ import annotations

from pathlib import Path
import unittest

from proofos_omega import ImpactCompiler, ProofPolicy, ProofSelector

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "proofos_omega_policy_v1.json"
BASE = "1" * 40
HEAD = "2" * 40


def compile_for(paths: list[str]):
    policy = ProofPolicy.from_path(POLICY)
    impact = ImpactCompiler(policy).assess(paths)
    manifest = ProofSelector(policy).compile_manifest(
        base_sha=BASE,
        head_sha=HEAD,
        impact=impact,
    )
    return impact, manifest


def selected(manifest) -> set[str]:
    return {item.test_id for item in manifest.selected_tests}


class PackageRootOwnershipTests(unittest.TestCase):
    def test_realityguard_package_metadata_infers_unique_owner_without_fallback(self):
        paths = [
            "realityguard_v0.4.0/BUILD_CONTRACT.json",
            "realityguard_v0.4.0/examples/gmail_attachment_failure_execution_guard.json",
            "realityguard_v0.4.0/examples/gmail_attachment_repaired_execution_guard.json",
            "realityguard_v0.4.0/pyproject.toml",
        ]
        impact, manifest = compile_for(paths)
        self.assertIn("REALITYGUARD", impact.direct_subsystems)
        self.assertEqual((), impact.unmapped_production_paths)
        self.assertIn("deployment_safety_spine", selected(manifest))
        self.assertNotIn("full_federation_fallback", selected(manifest))
        self.assertFalse(manifest.selector_state["fallback_full_suite_activated"])

    def test_explicit_realityguard_source_mapping_still_wins(self):
        impact, manifest = compile_for(
            ["realityguard_v0.4.0/src/realityguard/execution_guard.py"]
        )
        self.assertIn("REALITYGUARD", impact.direct_subsystems)
        self.assertEqual((), impact.unmapped_production_paths)
        self.assertIn("deployment_safety_spine", selected(manifest))

    def test_unknown_package_root_still_falls_back(self):
        impact, manifest = compile_for(["future_plane/new_runtime.py"])
        self.assertEqual(("future_plane/new_runtime.py",), impact.unmapped_production_paths)
        self.assertIn("full_federation_fallback", selected(manifest))
        self.assertTrue(manifest.selector_state["fallback_full_suite_activated"])

    def test_ambiguous_shared_root_still_falls_back(self):
        impact, manifest = compile_for(["governance/unmapped_policy.json"])
        self.assertEqual(("governance/unmapped_policy.json",), impact.unmapped_production_paths)
        self.assertIn("full_federation_fallback", selected(manifest))
        self.assertTrue(manifest.selector_state["fallback_full_suite_activated"])

    def test_inference_is_deterministic(self):
        paths = [
            "realityguard_v0.4.0/pyproject.toml",
            "realityguard_v0.4.0/BUILD_CONTRACT.json",
        ]
        first = compile_for(paths)[0]
        second = compile_for(list(reversed(paths)))[0]
        self.assertEqual(first.to_dict(), second.to_dict())


if __name__ == "__main__":
    unittest.main()
