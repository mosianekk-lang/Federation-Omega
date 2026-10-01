import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UltimateAdaptiveMultisurfaceIntelligenceV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = json.loads(
            (ROOT / "config" / "fuse-ultimate-adaptive-multisurface-intelligence-v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.prompt = (ROOT / self.config["prompt_path"]).read_bytes()
        self.prompt_text = self.prompt.decode("utf-8")

    def test_prompt_is_hash_bound_and_reuses_existing_authority(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.prompt).hexdigest(),
            self.config["prompt_sha256"],
        )
        self.assertEqual(self.config["authority"], "START:FUSE_ONE")
        self.assertEqual(
            self.config["mission_reuse"],
            "MISSION-FUSE-GLOBAL-REROUTE-ALL-WORK-001",
        )
        self.assertFalse(self.config["creates_new_controller"])
        self.assertFalse(self.config["creates_new_scheduler"])
        self.assertFalse(self.config["creates_new_mission_bus"])
        self.assertFalse(self.config["creates_new_authority_root"])
        self.assertFalse(self.config["creates_new_truth_memory_proof_root"])

    def test_prompt_contains_required_adaptive_mechanisms(self) -> None:
        required = (
            "ADAPTIVE RESOURCE MARKET",
            "DYNAMIC LOAD BALANCING",
            "SMARTER-EVERY-CYCLE LEARNING",
            "WINDOWS/ENDPOINT SAFETY",
            "OWNER-BURDEN FIREWALL",
            "UNKNOWN_EFFECT => READBACK_EFFECT",
            "PROMPT_BOUND != RECEIVER_LOADED",
        )
        for marker in required:
            self.assertIn(marker, self.prompt_text)

    def test_all_required_hard_gates_and_modes_are_present(self) -> None:
        gates = set(self.config["hard_gates"])
        self.assertTrue(
            {
                "AUTHORITY",
                "PRIVACY",
                "CURRENTNESS",
                "CAPABILITY",
                "BUDGET",
                "PROOF_FLOOR",
                "RECOVERY_FLOOR",
                "OBSERVABILITY",
            }.issubset(gates)
        )
        self.assertEqual(
            self.config["formation_modes"],
            [
                "FAST",
                "FUSION",
                "ADVERSARIAL",
                "FORMATION",
                "DEEP",
                "LIVE",
                "CHAMPION_TOURNAMENT",
            ],
        )

    def test_windows_route_avoids_trigger_mechanism(self) -> None:
        safety = self.config["windows_endpoint_safety"]
        self.assertTrue(safety["typed_native_preferred"])
        self.assertTrue(safety["encoded_command_normal_path_forbidden"])
        self.assertTrue(safety["broad_execution_policy_bypass_normal_path_forbidden"])
        self.assertTrue(safety["edr_detection_requires_changed_mechanism"])


if __name__ == "__main__":
    unittest.main()
