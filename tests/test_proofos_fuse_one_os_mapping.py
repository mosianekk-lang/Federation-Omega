from __future__ import annotations

from pathlib import Path
import unittest

from proofos_omega.core import ProofSelector, RiskTier
from proofos_omega.impact import ImpactCompiler
from proofos_omega.policy import ProofPolicy


ROOT = Path(__file__).resolve().parents[1]
FUSE_ONE_SOURCES = (
    "federation/fuse_unified_service_catalog_v1.py",
    "services/sol62_client_runtime/app.py",
    "services/sol62_client_runtime/static/app.js",
    "services/sol62_client_runtime/static/index.html",
    "services/sol62_client_runtime/static/styles.css",
    "scripts/fuse_one_os_browser_test.mjs",
    "scripts/fuse_one_os_ui_fixture.py",
    "scripts/verify_fuse_one_os.py",
    "config/fuse-unified-capability-fabric-v1.json",
    "sol_61_runtime/sol_62_complete_client_runtime.py",
    "sol_61_runtime/sol_62_frontier_primitives.py",
    "tests/test_sol62_atomic_owned_mission.py",
)
COURTS = {
    "fuse_one_os_catalog", "fuse_one_os_integration_court",
    "fuse_one_os_browser_runtime", "proofos_fuse_one_os_mapping",
}


class FuseOneProofMappingTests(unittest.TestCase):
    def setUp(self):
        self.policy = ProofPolicy.from_path(ROOT / "governance/proofos_omega_policy_v1.json")

    def manifest(self, paths):
        return ProofSelector(self.policy).compile_manifest(
            base_sha="a" * 40, head_sha="b" * 40,
            impact=ImpactCompiler(self.policy).assess(paths),
        )

    def test_each_source_selects_actual_api_and_browser_courts(self):
        for path in FUSE_ONE_SOURCES:
            with self.subTest(path=path):
                manifest = self.manifest([path])
                self.assertTrue(COURTS <= {test.test_id for test in manifest.selected_tests})
                self.assertEqual(manifest.impact.unmapped_production_paths, ())
                self.assertGreaterEqual(manifest.impact.risk, RiskTier.R4_CORE)

    def test_pytest_and_browser_targets_are_executable_bridges(self):
        self.assertEqual(self.policy.tests["fuse_one_os_integration_court"].target,
                         "test_fuse_one_os_integration_admission.py")
        self.assertEqual(self.policy.tests["fuse_one_os_browser_runtime"].target,
                         "test_fuse_one_os_browser_admission.py")
        for name in COURTS:
            self.assertFalse(self.policy.tests[name].optional_if_missing)
            self.assertEqual(self.policy.tests[name].block_scope, "GLOBAL")

    def test_unknown_federation_and_script_siblings_still_fall_back(self):
        for path in ("federation/unowned_fuse_one_sibling.py", "scripts/unowned_fuse_one_sibling.mjs"):
            with self.subTest(path=path):
                manifest = self.manifest([path])
                self.assertIn(path, manifest.impact.unmapped_production_paths)
                self.assertTrue(manifest.selector_state["fallback_full_suite_activated"])

    def test_hard_floors_and_additive_selection_remain_required(self):
        manifest = self.manifest(FUSE_ONE_SOURCES)
        selected = {test.test_id for test in manifest.selected_tests}
        for spec in self.policy.tests.values():
            if spec.always:
                self.assertIn(spec.test_id, selected)
        self.assertIn("compileall_shared", selected)
        self.assertTrue(manifest.selector_state["deterministic_selector_floor_may_not_be_removed_by_prediction"])
        self.assertTrue(manifest.selector_state["omission_proof_complete"])


if __name__ == "__main__":
    unittest.main()
