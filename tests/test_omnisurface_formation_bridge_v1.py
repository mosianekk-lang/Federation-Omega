from __future__ import annotations

import json
import unittest
from pathlib import Path

from federation.omnisurface_fabric_v2 import EffectClass, build_default_registry

ROOT = Path(__file__).resolve().parents[1]


class OmniSurfaceFormationBridgeV1Tests(unittest.TestCase):
    def test_core_formation_surfaces_are_registered(self) -> None:
        registry = build_default_registry()
        required = {
            "GOOGLE-APPS-SCRIPT",
            "GOOGLE-CLOUD",
            "GOOGLE-AI-STUDIO-GEMINI",
            "CANVA",
            "OPENROUTER",
        }
        self.assertTrue(required.issubset(registry.surfaces))

    def test_openrouter_is_internal_provider_neutral_challenger_cell(self) -> None:
        surface = build_default_registry().surfaces["OPENROUTER"]
        self.assertEqual(surface.provider, "OpenRouter")
        self.assertEqual(surface.maximum_effect, EffectClass.INTERNAL)
        for capability in (
            "reasoning",
            "model_diversity",
            "challenger",
            "provider_marketplace",
            "benchmarking",
        ):
            self.assertIn(capability, surface.capabilities)
        self.assertIn("provider_request_id", surface.readback_signals)
        self.assertIn("resolved_model", surface.readback_signals)

    def test_governance_binds_minimum_sufficient_formation(self) -> None:
        governance = json.loads(
            (ROOT / "governance" / "federation_omnisurface_fabric_v2.json").read_text(encoding="utf-8")
        )
        formation = governance["formation_load_balancing"]
        self.assertEqual(formation["contract_id"], "FUSE-FORMATION-SURFACE-LB-001")
        self.assertEqual(formation["applies_to"], "ALL_MATERIAL_MISSIONS")
        self.assertIs(formation["all_surfaces_every_task"], False)
        self.assertIs(formation["provider_diversity_is_not_independence"], True)
        self.assertIs(formation["single_surface_failure_global_stall"], False)
        self.assertEqual(formation["effect_authority_remains"], "FDOF_SICF")


if __name__ == "__main__":
    unittest.main()
