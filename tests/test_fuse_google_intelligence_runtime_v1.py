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

    def test_v1_is_preserved_as_v2_rollback_baseline(self) -> None:
        v1 = json.loads(
            (ROOT / "config" / "fuse-google-intelligence-runtime-v1.json").read_text(encoding="utf-8")
        )
        v2 = json.loads(
            (ROOT / "config" / "fuse-google-intelligence-runtime-v2.json").read_text(encoding="utf-8")
        )
        bootstrap = json.loads(
            (ROOT / "config" / "fuse-bootstrap-inheritance-v3.json").read_text(encoding="utf-8")
        )
        manifest = json.loads(
            (ROOT / "respawn" / "federation_manifest.json").read_text(encoding="utf-8")
        )

        self.assertEqual(v2["predecessor"]["version"], "1.0.0")
        self.assertEqual(v2["predecessor"]["main_sha"], "52742a8e32dfe0e246a09e330552150311b4c5cd")
        self.assertEqual(v2["predecessor"]["prompt_sha256"], v1["prompt_sha256"])
        self.assertIs(v2["predecessor"]["rollback_preserved"], True)

        self.assertEqual(
            bootstrap["google_intelligence_runtime"]["contract_id"],
            "FUSE-GOOGLE-INTELLIGENCE-RUNTIME-002",
        )
        self.assertEqual(
            manifest["google_intelligence_runtime"]["contract_id"],
            "FUSE-GOOGLE-INTELLIGENCE-RUNTIME-002",
        )
        self.assertIs(
            manifest["google_intelligence_runtime"]["rollback_v1_preserved"],
            True,
        )


if __name__ == "__main__":
    unittest.main()
