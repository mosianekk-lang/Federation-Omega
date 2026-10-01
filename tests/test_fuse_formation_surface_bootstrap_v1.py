from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FuseFormationSurfaceBootstrapBindingTests(unittest.TestCase):
    def test_global_contract_is_bound_before_execute(self) -> None:
        cfg = json.loads(
            (ROOT / "config" / "fuse-formation-surface-load-balancer-v1.json").read_text(encoding="utf-8")
        )
        inheritance = json.loads(
            (ROOT / "config" / "fuse-bootstrap-inheritance-v3.json").read_text(encoding="utf-8")
        )
        manifest = json.loads(
            (ROOT / "respawn" / "federation_manifest.json").read_text(encoding="utf-8")
        )
        service = (ROOT / "respawn" / "bootstrap_service.py").read_text(encoding="utf-8")

        self.assertEqual(cfg["schema"], "FUSE_FORMATION_SURFACE_LOAD_BALANCER_V1")
        self.assertEqual(cfg["contract_id"], "FUSE-FORMATION-SURFACE-LB-001")
        self.assertEqual(cfg["applies_to"], "ALL_MATERIAL_MISSIONS")
        self.assertEqual(cfg["formation_principle"], "MINIMUM_SUFFICIENT_PROVEN_PORTFOLIO")
        self.assertIs(cfg["all_surfaces_invoked_every_task"], False)
        self.assertIs(cfg["external_effect_authority"], False)
        self.assertIs(cfg["provider_execution_authority"], False)

        binding = inheritance["formation_surface_load_balancer"]
        runtime = manifest["formation_surface_load_balancer"]
        self.assertIs(binding["enabled"], True)
        self.assertIs(binding["authority_expansion"], False)
        self.assertEqual(binding["contract_id"], "FUSE-FORMATION-SURFACE-LB-001")
        self.assertEqual(runtime["contract_id"], "FUSE-FORMATION-SURFACE-LB-001")
        self.assertIn("FORMATION_SURFACE_LOAD_BALANCER", inheritance["required_order"])
        self.assertLess(
            inheritance["required_order"].index("FORMATION_SURFACE_LOAD_BALANCER"),
            inheritance["required_order"].index("ROUTE_COMPILE"),
        )

        order = manifest["bootstrap_order"]
        for step in (
            "load_formation_surface_load_balancer_contract",
            "compile_surface_formation",
        ):
            self.assertIn(step, order)
            self.assertLess(order.index(step), order.index("execute"))

        for invariant in (
            "ALL_MATERIAL_WORK_REQUIRES_SURFACE_FORMATION_COMPILE",
            "MINIMUM_SUFFICIENT_SURFACE_PORTFOLIO_REQUIRED",
            "SURFACE_FAILURE_IS_LOCAL_NOT_GLOBAL_STALL",
            "PROVIDER_DIVERSITY_DOES_NOT_EQUAL_INDEPENDENCE",
            "SURFACE_LOAD_BALANCER_CANNOT_MINT_AUTHORITY",
            "EXTERNAL_EFFECTS_REMAIN_FDOF_SICF_GATED",
        ):
            self.assertIn(invariant, manifest["bootstrap_invariants"])

        self.assertIn("def formation_surface_load_balancer_bootstrap_guard", service)
        self.assertIn("FUSE_FORMATION_SURFACE_LOAD_BALANCER_BOOTSTRAP_GUARD_V1", service)
        self.assertIn("formation_guard = formation_surface_load_balancer_bootstrap_guard(source_manifest)", service)
        self.assertIn('"formation_surface_load_balancer_guard": formation_guard', service)

    def test_required_user_surfaces_are_contract_bound(self) -> None:
        cfg = json.loads(
            (ROOT / "config" / "fuse-formation-surface-load-balancer-v1.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            set(cfg["core_requested_surfaces"]),
            {
                "GOOGLE-APPS-SCRIPT",
                "GOOGLE-CLOUD",
                "GOOGLE-AI-STUDIO-GEMINI",
                "CANVA",
                "OPENROUTER",
            },
        )


if __name__ == "__main__":
    unittest.main()
