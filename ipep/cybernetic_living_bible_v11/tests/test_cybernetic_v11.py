from __future__ import annotations

import json
import unittest
from pathlib import Path

from omega_cybernetic_v11.audio_v4_binding import AudioV4Snapshot, assess_audio_v4_snapshot
from omega_cybernetic_v11.canary import run_privacy_safe_canary
from omega_cybernetic_v11.controller import CyberneticController
from omega_cybernetic_v11.hashing import receipt_hash
from omega_cybernetic_v11.models import ControlTarget, Signal


class CyberneticV11Tests(unittest.TestCase):
    NOW = "2026-08-05T23:35:00+02:00"

    def test_homeostatic_and_unmeasured_state(self) -> None:
        controller = CyberneticController(
            targets=(
                ControlTarget("continuity", 100, 0),
                ControlTarget("future_metric", 90, 10, mandatory=False),
            )
        )
        state = controller.estimate_state(
            [Signal("S1", self.NOW, "STATE_OBSERVATION", "fixture", {"variable": "continuity", "observed": 100})]
        )
        by_name = {item.variable: item for item in state}
        self.assertEqual(by_name["continuity"].status, "HOMEOSTATIC")
        self.assertEqual(by_name["future_metric"].status, "UNMEASURED")

    def test_readback_mismatch_triggers_stop_and_reread(self) -> None:
        decisions = CyberneticController().decide(
            [Signal("S2", self.NOW, "READBACK_MISMATCH", "fixture", {})]
        )
        actions = {item.action for item in decisions}
        self.assertIn("STOP_PROMOTION", actions)
        self.assertIn("REREAD", actions)

    def test_claim_exceeding_proof_is_downgraded(self) -> None:
        decisions = CyberneticController().decide(
            [Signal("S3", self.NOW, "CLAIM_EXCEEDS_PROOF", "fixture", {})]
        )
        actions = {item.action for item in decisions}
        self.assertIn("DOWNGRADE_CLAIM", actions)
        self.assertIn("BLOCK_RELEASE", actions)

    def test_external_effect_is_held_without_owner_authority(self) -> None:
        decisions = CyberneticController().decide(
            [Signal("S4", self.NOW, "EXTERNAL_EFFECT_REQUEST", "fixture", {})]
        )
        self.assertTrue(decisions)
        self.assertTrue(all(item.state == "HELD" for item in decisions))

    def test_audio_unit_accounting_and_human_gate(self) -> None:
        result = assess_audio_v4_snapshot(
            AudioV4Snapshot(
                processed_units=10,
                emitted_segment_units=8,
                zero_segment_units=1,
                failed_units=1,
                transcript_state="NOT_CERTIFIED",
                exact_quote_requested=True,
            ),
            observed_at=self.NOW,
        )
        self.assertTrue(result["unit_accounting_passed"])
        self.assertEqual(result["signals"][0].kind, "HUMAN_GATE_REQUIRED")

    def test_audio_unit_accounting_mismatch_emits_signal(self) -> None:
        result = assess_audio_v4_snapshot(
            AudioV4Snapshot(
                processed_units=10,
                emitted_segment_units=8,
                zero_segment_units=1,
                failed_units=0,
                transcript_state="NOT_CERTIFIED",
            ),
            observed_at=self.NOW,
        )
        self.assertFalse(result["unit_accounting_passed"])
        self.assertEqual(result["signals"][0].kind, "READBACK_MISMATCH")

    def test_canary_passes_and_preserves_constraints(self) -> None:
        receipt = run_privacy_safe_canary(now=self.NOW)
        self.assertEqual(receipt.cycle_state, "VERIFIED_CONTROL_CANARY_PASS")
        self.assertEqual(receipt.terminal_event, "CONSTRAINT")
        self.assertEqual(receipt.mission_delta_before, 4)
        self.assertEqual(receipt.mission_delta_after, 2)
        self.assertEqual(receipt.closure_rate, 0.5)
        self.assertTrue(all(receipt.checks.values()))
        self.assertIn("HUMAN_AUDIO_REVIEW", receipt.open_constraints)
        self.assertIn("OWNER_EXTERNAL_EFFECT_AUTHORITY", receipt.open_constraints)
        self.assertEqual(receipt_hash(receipt.to_dict()), receipt.receipt_hash)

    def test_receipt_hash_detects_tampering(self) -> None:
        receipt = run_privacy_safe_canary(now=self.NOW)
        tampered = receipt.to_dict()
        tampered["mission_delta_after"] = 0
        self.assertNotEqual(receipt_hash(tampered), receipt.receipt_hash)

    def test_contract_files_are_valid_json(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for path in sorted((root / "contracts").glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertIn("required", data)


if __name__ == "__main__":
    unittest.main()
