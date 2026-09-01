from __future__ import annotations

import unittest
from pathlib import Path

from proofos_omega import ImpactCompiler, ProofPolicy, ProofSelector


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "proofos_omega_policy_v1.json"
BASE = "1" * 40
HEAD = "2" * 40


class Sol62ProofOSBindingTests(unittest.TestCase):
    def test_sol62_surface_selects_scoped_court_without_full_fallback(self) -> None:
        policy = ProofPolicy.from_path(POLICY)
        changed = [
            "sol_61_runtime/sol_62_frontier_primitives.py",
            "sol_61_runtime/sol_62_runtime.py",
            "sol_61_runtime/sol_62_strict_runtime.py",
            "sol_61_runtime/sol_62.py",
            "sol_61_runtime/prove_sol_62_runtime.py",
            "sol_61_runtime/prove_runtime.py",
            "sol_61_runtime/SOL_6_2_PROGRAMME.json",
            "sol_61_runtime/SOL_6_2_ARCHITECTURE.md",
            "governance/proofos_omega_policy_extension_sol62_v1.json",
            "tests/test_sol_62_transactional_runtime.py",
            "tests/test_sol_62_proofos_binding.py",
            "tests/test_sol_62_reference_proof.py",
        ]
        impact = ImpactCompiler(policy).assess(changed)
        manifest = ProofSelector(policy).compile_manifest(
            base_sha=BASE, head_sha=HEAD, impact=impact
        )
        selected = {entry.test_id for entry in manifest.selected_tests}
        self.assertIn("SOL62", impact.direct_subsystems)
        self.assertFalse(impact.unmapped_production_paths)
        self.assertIn("sol_62_transactional_runtime", selected)
        self.assertNotIn("full_federation_fallback", selected)
        self.assertFalse(manifest.selector_state["fallback_full_suite_activated"])
        self.assertTrue(manifest.selector_state["omission_proof_complete"])


if __name__ == "__main__":
    unittest.main()
