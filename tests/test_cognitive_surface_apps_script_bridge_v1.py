from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "apps_script" / "cognitive_surface_bridge" / "FuseCognitiveSurfaceBridge.gs"


class CognitiveSurfaceAppsScriptBridgeTests(unittest.TestCase):
    def test_bridge_is_bounded_internal_and_secret_free(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("FUSE_COGNITIVE_ALLOWED_SURFACES", source)
        self.assertIn("fuseCognitiveNormalizePacket_", source)
        self.assertIn("fuseCognitiveQueueInternal", source)
        self.assertIn("fuseCognitiveHeartbeat", source)
        self.assertIn("LockService.getScriptLock", source)
        self.assertIn("idempotency_key", source)
        self.assertIn("provider_effect_authorized: false", source)
        self.assertNotIn("UrlFetchApp", source)
        self.assertNotIn("eval(", source)
        self.assertNotIn("new Function(", source)
        self.assertNotIn("ScriptApp.newTrigger", source)
        self.assertNotIn("API_KEY", source)
        self.assertNotIn("SECRET", source)

    def test_all_requested_surfaces_are_explicitly_allowlisted(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        for surface in (
            "GOOGLE-APPS-SCRIPT",
            "GOOGLE-AI-STUDIO-GEMINI",
            "CANVA",
            "OPENROUTER",
            "HYPERCUBE",
        ):
            self.assertIn("'" + surface + "': true", source)


if __name__ == "__main__":
    unittest.main()
