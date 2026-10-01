from __future__ import annotations

from pathlib import Path
import unittest

from proofos_omega.core import ProofSelector, RiskTier
from proofos_omega.impact import ImpactCompiler
from proofos_omega.policy import ProofPolicy


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance/proofos_omega_policy_v1.json"
COGNITIVE_PATHS = (
    "apps_script/cognitive_surface_bridge/FuseCognitiveSurfaceBridge.gs",
    "config/fuse-bootstrap-inheritance-v3.json",
    "config/fuse-cognitive-surface-fabric-v1.json",
    "federation/cognitive_surface_fabric_v1.py",
    "respawn/bootstrap_service.py",
    "respawn/federation_manifest.json",
)
COGNITIVE_COURTS = {
    "cognitive_surface_fabric_v1",
    "cognitive_surface_bootstrap_v1",
    "cognitive_surface_apps_script_bridge_v1",
    "proofos_cognitive_surface_mapping",
}
HARD_FLOORS = {
    "airlock_kernel", "frontier_manifest_integrity", "stale_base_guard",
    "source_provenance", "provider_airlock_activator", "proofos_self",
}


class CognitiveProofMappingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = ProofPolicy.from_path(POLICY)

    def manifest(self, paths):
        return ProofSelector(self.policy).compile_manifest(
            base_sha="a" * 40, head_sha="b" * 40,
            impact=ImpactCompiler(self.policy).assess(paths),
        )

    def test_each_real_cognitive_source_selects_behavior_and_guard_courts(self):
        for path in COGNITIVE_PATHS:
            with self.subTest(path=path):
                manifest = self.manifest([path])
                selected = {test.test_id for test in manifest.selected_tests}
                self.assertTrue(COGNITIVE_COURTS <= selected)
                self.assertGreaterEqual(manifest.impact.risk, RiskTier.R4_CORE)
                self.assertEqual(manifest.impact.unmapped_production_paths, ())
                self.assertFalse(manifest.selector_state["fallback_full_suite_activated"])

    def test_unknown_siblings_still_require_full_fallback(self):
        for path in ("federation/unmapped_cognitive_sibling.py", "config/unmapped-cognitive-sibling.json"):
            with self.subTest(path=path):
                manifest = self.manifest([path])
                self.assertIn(path, manifest.impact.unmapped_production_paths)
                self.assertTrue(manifest.selector_state["fallback_full_suite_activated"])
                self.assertIn("full_federation_fallback", {t.test_id for t in manifest.selected_tests})

    def test_existing_hard_floors_cannot_be_replaced_by_new_courts(self):
        manifest = self.manifest(COGNITIVE_PATHS)
        self.assertTrue(HARD_FLOORS <= {t.test_id for t in manifest.selected_tests})
        for test_id in HARD_FLOORS:
            with self.subTest(test_id=test_id):
                self.assertTrue(self.policy.tests[test_id].always)
                self.assertTrue(self.policy.tests[test_id].hard_always_run)
        self.assertTrue(manifest.selector_state["predictive_selector_may_only_add_tests"])
        self.assertTrue(manifest.selector_state["omission_proof_complete"])

    def test_actual_dependency_change_runs_cognitive_consumer_regression(self):
        for path in ("federation/formation_surface_load_balancer_v1.py", "superior_logic/hypercube_bottleneck_resolver.py"):
            with self.subTest(path=path):
                manifest = self.manifest([path])
                self.assertTrue(COGNITIVE_COURTS <= {t.test_id for t in manifest.selected_tests})

    def test_deleted_source_path_cannot_escape_its_courts(self):
        manifest = self.manifest(["federation/cognitive_surface_fabric_v1.py"])
        self.assertTrue(COGNITIVE_COURTS <= {t.test_id for t in manifest.selected_tests})
        for test_id in COGNITIVE_COURTS:
            self.assertFalse(self.policy.tests[test_id].optional_if_missing)
            self.assertEqual(self.policy.tests[test_id].block_scope, "GLOBAL")


if __name__ == "__main__":
    unittest.main()
