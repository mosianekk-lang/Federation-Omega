from __future__ import annotations

from pathlib import Path
import unittest

from proofos_omega.core import ImpactCompiler, ProofPolicy, ProofSelector


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "proofos_omega_policy_v1.json"


class ProofOSBubblesMappingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = ProofPolicy.from_path(POLICY)

    def test_agent_fabric_paths_are_owned_by_bubbles_without_full_fallback(self) -> None:
        impact = ImpactCompiler(self.policy).assess(
            (
                "bubbles/agent_fabric.py",
                "bubbles/__init__.py",
                "governance/bubbles_omega_agent_fabric_v1.json",
            )
        )
        self.assertIn("BUBBLES", impact.direct_subsystems)
        self.assertEqual((), impact.unmapped_production_paths)

        manifest = ProofSelector(self.policy).compile_manifest(
            base_sha="1" * 40,
            head_sha="2" * 40,
            impact=impact,
        )
        selected = {item.test_id for item in manifest.selected_tests}
        self.assertIn("bubbles_agent_fabric", selected)
        self.assertNotIn("full_federation_fallback", selected)

    def test_unknown_production_path_still_fails_safe_to_full_fallback(self) -> None:
        impact = ImpactCompiler(self.policy).assess(("unregistered_runtime/new_engine.py",))
        self.assertEqual(("unregistered_runtime/new_engine.py",), impact.unmapped_production_paths)

        manifest = ProofSelector(self.policy).compile_manifest(
            base_sha="3" * 40,
            head_sha="4" * 40,
            impact=impact,
        )
        selected = {item.test_id for item in manifest.selected_tests}
        self.assertIn("full_federation_fallback", selected)


if __name__ == "__main__":
    unittest.main()
