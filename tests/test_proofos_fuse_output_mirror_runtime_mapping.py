from __future__ import annotations

import unittest
from pathlib import Path

from proofos_omega import ImpactCompiler, ProofPolicy, ProofSelector

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "proofos_omega_policy_v1.json"
BASE = "1" * 40
HEAD = "2" * 40

KNOWN_RUNTIME_PATHS = [
    "benchmarks/developer1000-public-signal-manifest-v1.json",
    "benchmarks/output_mirror_v2_developer1000_court.mjs",
    "benchmarks/output_mirror_v3_developer1000_regression.mjs",
    "benchmarks/output_mirror_v3_power_diary_court.mjs",
    "config/chatgpt-power-diary-v1.json",
    "config/fuse-24x7-autonomy-v1.json",
    "config/fuse-bootstrap-inheritance-v2.json",
    "config/fuse-bootstrap-inheritance-v3.json",
    "config/fuse-bootstrap-memory-snapshot-v1.json",
    "config/fuse-bootstrap-self-improvement-v1.json",
    "config/fuse-chatgpt-failure-repair-v1.json",
    "config/fuse-constraint-routing-v1.json",
    "config/fuse-directive-fidelity-prompts-v1.json",
    "config/fuse-directive-fidelity-v1.json",
    "config/fuse-estate-automation-prompts-v1a.json",
    "config/fuse-failure-repair-prompts-v1.json",
    "config/fuse-forest-first-anticipatory-v1.json",
    "config/fuse-forest-first-prompts-v1.json",
    "config/fuse-forest-first-prompts-v2a.json",
    "config/fuse-forest-first-prompts-v2b1.json",
    "config/fuse-output-mirror-v1.json",
    "config/fuse-output-mirror-v2.json",
    "config/fuse-output-mirror-v3.json",
    "config/fuse-parallel-frontend-continuity-v1.json",
    "config/fuse-sovereign-power-diary-v2.json",
    "config/fuse-unified-capability-fabric-v1.json",
    "fuse_runtime/autonomous_improvement_loop_v1.mjs",
    "fuse_runtime/historical_backfill_runner_v1.mjs",
    "fuse_runtime/output_mirror_v1.mjs",
    "fuse_runtime/output_mirror_v2.mjs",
    "fuse_runtime/output_mirror_v3.mjs",
    "governance/proofos_omega_policy_extension_fuse_output_mirror_runtime_v1.json"
]

class FuseOutputMirrorRuntimeProofOSMappingTests(unittest.TestCase):
    def test_known_output_mirror_autonomy_runtime_paths_are_scoped(self) -> None:
        policy = ProofPolicy.from_path(POLICY)
        impact = ImpactCompiler(policy).assess(KNOWN_RUNTIME_PATHS)
        manifest = ProofSelector(policy).compile_manifest(
            base_sha=BASE, head_sha=HEAD, impact=impact
        )
        selected = {entry.test_id for entry in manifest.selected_tests}

        self.assertIn("FUSE_OUTPUT_MIRROR_RUNTIME", impact.direct_subsystems)
        self.assertFalse(impact.unmapped_production_paths)
        self.assertFalse(manifest.selector_state["fallback_full_suite_activated"])
        self.assertNotIn("full_federation_fallback", selected)
        for required in (
            "fuse_output_mirror_runtime_contract_court",
            "proofos_fuse_output_mirror_runtime_mapping",
        ):
            self.assertIn(required, selected)

    def test_unknown_future_production_path_still_fails_safe(self) -> None:
        policy = ProofPolicy.from_path(POLICY)
        impact = ImpactCompiler(policy).assess(["future_plane/unregistered_runtime.py"])
        manifest = ProofSelector(policy).compile_manifest(
            base_sha=BASE, head_sha=HEAD, impact=impact
        )
        selected = {entry.test_id for entry in manifest.selected_tests}

        self.assertEqual(
            tuple(impact.unmapped_production_paths),
            ("future_plane/unregistered_runtime.py",),
        )
        self.assertTrue(manifest.selector_state["fallback_full_suite_activated"])
        self.assertIn("full_federation_fallback", selected)

if __name__ == "__main__":
    unittest.main()
