from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CognitiveSurfaceBootstrapTests(unittest.TestCase):
    def test_binding_precedes_surface_formation_and_execution(self) -> None:
        cfg = json.loads((ROOT / "config" / "fuse-cognitive-surface-fabric-v1.json").read_text())
        inheritance = json.loads((ROOT / "config" / "fuse-bootstrap-inheritance-v3.json").read_text())
        manifest = json.loads((ROOT / "respawn" / "federation_manifest.json").read_text())
        service = (ROOT / "respawn" / "bootstrap_service.py").read_text(encoding="utf-8")

        self.assertEqual(cfg["contract_id"], "FUSE-COGNITIVE-SURFACE-FABRIC-001")
        self.assertIs(cfg["creates_new_controller"], False)
        self.assertIs(cfg["creates_new_scheduler"], False)
        self.assertIs(cfg["external_effect_authority"], False)
        self.assertIs(cfg["provider_execution_authority"], False)

        binding = inheritance["cognitive_surface_fabric"]
        runtime = manifest["cognitive_surface_fabric"]
        self.assertEqual(binding["contract_id"], "FUSE-COGNITIVE-SURFACE-FABRIC-001")
        self.assertEqual(runtime["contract_id"], "FUSE-COGNITIVE-SURFACE-FABRIC-001")

        order = inheritance["required_order"]
        self.assertIn("COGNITIVE_SURFACE_FABRIC_BINDING", order)
        self.assertLess(
            order.index("COGNITIVE_SURFACE_FABRIC_BINDING"),
            order.index("FORMATION_SURFACE_LOAD_BALANCER"),
        )

        boot = manifest["bootstrap_order"]
        self.assertLess(
            boot.index("compile_cognitive_surface_plan"),
            boot.index("compile_surface_formation"),
        )
        self.assertLess(boot.index("compile_cognitive_surface_plan"), boot.index("execute"))

        for invariant in (
            "ALL_MATERIAL_COGNITIVE_WORK_GETS_SURFACE_INTELLIGENCE_BINDING",
            "COGNITIVE_SURFACE_FABRIC_CANNOT_MINT_AUTHORITY",
            "MISSING_SURFACE_CAPABILITY_TRIGGERS_ALPHA_OMEGA_MINIMUM_RESIDUAL",
            "PROVIDER_MODEL_OUTPUT_IS_CANDIDATE_EVIDENCE_NOT_COMPLETION",
            "CANVA_CREATIVE_OUTPUT_CANNOT_SELF_CERTIFY",
            "APPS_SCRIPT_BOUNDED_QUEUE_IS_NOT_PROVIDER_EFFECT_AUTHORITY",
        ):
            self.assertIn(invariant, manifest["bootstrap_invariants"])

        self.assertIn("def cognitive_surface_fabric_bootstrap_guard", service)
        self.assertIn("FUSE_COGNITIVE_SURFACE_FABRIC_BOOTSTRAP_GUARD_V1", service)
        self.assertIn("cognitive_surface_guard = cognitive_surface_fabric_bootstrap_guard(source_manifest)", service)
        self.assertIn('"cognitive_surface_fabric_guard": cognitive_surface_guard', service)


if __name__ == "__main__":
    unittest.main()
