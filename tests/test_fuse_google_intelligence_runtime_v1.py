from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FuseGoogleIntelligenceRuntimeV1Tests(unittest.TestCase):
    def test_prompt_is_hash_bound_and_sovereign(self) -> None:
        contract = json.loads(
            (ROOT / "config" / "fuse-google-intelligence-runtime-v1.json").read_text(encoding="utf-8")
        )
        prompt_path = ROOT / contract["prompt_path"]
        prompt_bytes = prompt_path.read_bytes()

        self.assertEqual(contract["schema"], "FUSE_GOOGLE_INTELLIGENCE_RUNTIME_V1")
        self.assertEqual(contract["version"], "1.0.0")
        self.assertIs(contract["enabled"], True)
        self.assertEqual(hashlib.sha256(prompt_bytes).hexdigest(), contract["prompt_sha256"])
        self.assertIs(contract["creates_new_controller"], False)
        self.assertIs(contract["creates_new_scheduler"], False)
        self.assertIs(contract["creates_new_mission_bus"], False)
        self.assertIs(contract["creates_new_authority_root"], False)
        self.assertIs(contract["creates_new_truth_memory_proof_root"], False)
        self.assertEqual(
            contract["ai_studio_role"],
            "BUILD_AND_CONTROL_COCKPIT_NOT_SOVEREIGN_RUNTIME",
        )
        self.assertIs(contract["provider_output_can_expand_authority"], False)
        self.assertIs(contract["secret_payload_to_model"], False)
        self.assertEqual(
            contract["live_provider_state"],
            "REQUIRES_PROVIDER_SEMANTIC_READBACK",
        )
        self.assertIn("GOOGLE_GEMINI_INTERACTIONS", contract["google_capability_cells"])
        self.assertIn("GOOGLE_VERTEX_GEMINI", contract["google_capability_cells"])
        self.assertIn("GOOGLE_AI_STUDIO_BUILD", contract["google_capability_cells"])
        self.assertIn("FUSION", contract["formation_modes"])
        self.assertIn("ADVERSARIAL", contract["formation_modes"])

    def test_bootstrap_inheritance_preserves_false_live_boundary(self) -> None:
        bootstrap = json.loads(
            (ROOT / "config" / "fuse-bootstrap-inheritance-v3.json").read_text(encoding="utf-8")
        )
        manifest = json.loads(
            (ROOT / "respawn" / "federation_manifest.json").read_text(encoding="utf-8")
        )
        service = (ROOT / "respawn" / "bootstrap_service.py").read_text(encoding="utf-8")

        binding = bootstrap["google_intelligence_runtime"]
        runtime = manifest["google_intelligence_runtime"]

        self.assertIs(binding["enabled"], True)
        self.assertIs(binding["authority_expansion"], False)
        self.assertIn("GOOGLE_INTELLIGENCE_RUNTIME_BINDING", bootstrap["required_order"])
        self.assertEqual(
            runtime["live_provider_state"],
            "REQUIRES_PROVIDER_SEMANTIC_READBACK",
        )
        self.assertEqual(runtime["prompt_sha256"], binding["prompt_sha256"])

        order = manifest["bootstrap_order"]
        for step in (
            "load_google_intelligence_runtime_contract",
            "compile_google_intelligence_route",
        ):
            self.assertIn(step, order)
            self.assertLess(order.index(step), order.index("execute"))

        for invariant in (
            "GOOGLE_AI_STUDIO_IS_BUILD_CONTROL_PLANE_NOT_SOVEREIGN_AUTHORITY",
            "GOOGLE_PROVIDER_LIVE_CLAIMS_REQUIRE_PROVIDER_SEMANTIC_READBACK",
            "GOOGLE_MODEL_OUTPUT_CANNOT_EXPAND_FUSE_AUTHORITY",
        ):
            self.assertIn(invariant, manifest["bootstrap_invariants"])

        self.assertIn("def google_intelligence_runtime_bootstrap_guard", service)
        self.assertIn('"provider_live_proven": False', service)
        self.assertIn("GOOGLE_INTELLIGENCE_PROMPT_HASH_MISMATCH", service)


if __name__ == "__main__":
    unittest.main()
