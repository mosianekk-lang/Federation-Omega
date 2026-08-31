from __future__ import annotations

import json
import unittest

from benchmarking.cfbe_omega.bible_memory_capture_adapter_v1 import (
    BibleMemoryCaptureAdapter,
    MissionResultCapture,
)
from federation.mission_ir import MissionIR


class CFBEBibleMemoryCaptureAdapterV1Tests(unittest.TestCase):
    def mission(self, *, effect_class: str = "NO_EFFECT", privacy_class: str = "INTERNAL") -> MissionIR:
        authority = () if effect_class in {"NO_EFFECT", "READ_ONLY"} else ("exact_route_authority",)
        return MissionIR(
            mission_id="MISSION-CAPTURE-001",
            objective="private owner objective should not be persisted raw",
            domain="CFBE",
            outcome_contract="private desired outcome should also remain behind its hash",
            source_frontier="CURRENT_VERIFIED_STATE",
            privacy_class=privacy_class,
            rights_state="OWNER_CONTROLLED",
            effect_class=effect_class,
            owner_approval_required=effect_class == "CONSEQUENTIAL_EFFECT",
            rollback_required=effect_class not in {"NO_EFFECT", "READ_ONLY"},
            authority_requirements=authority,
            proof_requirements=("source_provenance", "terminal_readback"),
            value_metrics=("owner_burden", "proof_completeness"),
            metadata={
                "directive_id": "DIRECTIVE-CAPTURE-001",
                "workstream_id": "BMF_CAPTURE_TEST",
                "private_note": "sensitive metadata should be hash-only",
            },
        ).normalized()

    def test_compiled_mission_is_deterministic_and_privacy_minimal(self) -> None:
        mission = self.mission()
        first = BibleMemoryCaptureAdapter.capture_mission_compiled(
            mission,
            stream_version=1,
            recorded_at="2026-08-31T21:00:00Z",
            source_refs=("missionir:test",),
        )
        second = BibleMemoryCaptureAdapter.capture_mission_compiled(
            mission,
            stream_version=1,
            recorded_at="2026-08-31T21:00:00Z",
            source_refs=("missionir:test",),
        )
        self.assertEqual(first.event_id, second.event_id)
        self.assertEqual(first.idempotency_key, second.idempotency_key)
        serialized = json.dumps(first.payload, sort_keys=True)
        self.assertNotIn("private owner objective", serialized)
        self.assertNotIn("private desired outcome", serialized)
        self.assertNotIn("sensitive metadata", serialized)
        self.assertIn("objective_sha256", first.payload)
        self.assertIn("outcome_contract_sha256", first.payload)
        self.assertFalse(first.payload["provider_effect_authorized"])
        self.assertFalse(first.payload["publication_authorized"])
        self.assertEqual("INTERNAL", first.privacy_class)
        self.assertEqual("DIRECTIVE-CAPTURE-001", first.directive_id)
        self.assertEqual("BMF_CAPTURE_TEST", first.workstream_id)

    def test_stream_version_changes_event_identity(self) -> None:
        mission = self.mission()
        one = BibleMemoryCaptureAdapter.capture_mission_compiled(
            mission, stream_version=1, recorded_at="2026-08-31T21:00:00Z", source_refs=("missionir:test",)
        )
        two = BibleMemoryCaptureAdapter.capture_mission_compiled(
            mission, stream_version=2, recorded_at="2026-08-31T21:00:00Z", source_refs=("missionir:test",)
        )
        self.assertNotEqual(one.event_id, two.event_id)
        self.assertNotEqual(one.idempotency_key, two.idempotency_key)

    def test_no_effect_success_requires_proof_but_not_provider_authority(self) -> None:
        mission = self.mission()
        result = MissionResultCapture(
            state="SUCCESS",
            observed_at="2026-08-31T21:01:00Z",
            source_refs=("bubbles:receipt/1",),
            proof_refs=("proof:1", "proof:2"),
            result_ref="artifact://result-1",
            result_sha256="a" * 64,
            next_action="continue-value-court",
        )
        event = BibleMemoryCaptureAdapter.capture_result(mission, result, stream_version=2)
        self.assertEqual("RESULT_VERIFIED", event.event_type)
        self.assertEqual(("proof:1", "proof:2"), event.proof_refs)
        self.assertEqual("SUCCESS", event.payload["mission_state"])
        self.assertFalse(event.payload["provider_effect_authorized"])
        self.assertFalse(event.payload["authority_receipt_present"])
        self.assertFalse(event.payload["receiver_readback_present"])

    def test_success_without_proof_fails_closed(self) -> None:
        mission = self.mission()
        result = MissionResultCapture(
            state="SUCCESS",
            observed_at="2026-08-31T21:01:00Z",
            source_refs=("bubbles:receipt/1",),
            result_ref="artifact://result-1",
            result_sha256="a" * 64,
        )
        with self.assertRaisesRegex(ValueError, "BMF_CAPTURE_SUCCESS_PROOF_REQUIRED"):
            BibleMemoryCaptureAdapter.capture_result(mission, result, stream_version=2)

    def test_bounded_effect_success_requires_receiver_readback(self) -> None:
        mission = self.mission(effect_class="BOUNDED_EFFECT")
        result = MissionResultCapture(
            state="SUCCESS",
            observed_at="2026-08-31T21:01:00Z",
            source_refs=("bubbles:receipt/1",),
            proof_refs=("proof:1",),
            result_ref="artifact://result-1",
            result_sha256="a" * 64,
        )
        with self.assertRaisesRegex(ValueError, "BMF_CAPTURE_EFFECT_READBACK_REQUIRED"):
            BibleMemoryCaptureAdapter.capture_result(mission, result, stream_version=2)

    def test_consequential_success_requires_exact_authority_receipt(self) -> None:
        mission = self.mission(effect_class="CONSEQUENTIAL_EFFECT")
        result = MissionResultCapture(
            state="SUCCESS",
            observed_at="2026-08-31T21:01:00Z",
            source_refs=("bubbles:receipt/1",),
            proof_refs=("proof:1",),
            result_ref="artifact://result-1",
            result_sha256="a" * 64,
            receiver_readback_ref="receiver:readback/1",
        )
        with self.assertRaisesRegex(ValueError, "BMF_CAPTURE_CONSEQUENTIAL_AUTHORITY_RECEIPT_REQUIRED"):
            BibleMemoryCaptureAdapter.capture_result(mission, result, stream_version=2)

    def test_consequential_success_preserves_receipts_without_inheriting_authority(self) -> None:
        mission = self.mission(effect_class="CONSEQUENTIAL_EFFECT")
        result = MissionResultCapture(
            state="SUCCESS",
            observed_at="2026-08-31T21:01:00Z",
            source_refs=("bubbles:receipt/1",),
            proof_refs=("proof:1",),
            result_ref="artifact://result-1",
            result_sha256="a" * 64,
            receiver_readback_ref="receiver:readback/1",
            authority_receipt_ref="authority:receipt/1",
        )
        event = BibleMemoryCaptureAdapter.capture_result(mission, result, stream_version=2)
        self.assertTrue(event.payload["receiver_readback_present"])
        self.assertTrue(event.payload["authority_receipt_present"])
        self.assertEqual("receiver:readback/1", event.payload["receiver_readback_ref"])
        self.assertEqual("authority:receipt/1", event.payload["authority_receipt_ref"])
        self.assertFalse(event.payload["provider_effect_authorized"])
        self.assertFalse(event.payload["publication_authorized"])

    def test_blocked_result_compiles_to_blocker_event_and_requires_blocker_code(self) -> None:
        mission = self.mission()
        missing = MissionResultCapture(
            state="BLOCKED",
            observed_at="2026-08-31T21:01:00Z",
            source_refs=("bubbles:receipt/blocked",),
        )
        with self.assertRaisesRegex(ValueError, "BMF_CAPTURE_BLOCKER_CODE_REQUIRED"):
            BibleMemoryCaptureAdapter.capture_result(mission, missing, stream_version=2)
        result = MissionResultCapture(
            state="BLOCKED",
            observed_at="2026-08-31T21:01:00Z",
            source_refs=("bubbles:receipt/blocked",),
            blocker_code="PROVIDER_GATE",
            next_action="continue-safe-lanes",
        )
        event = BibleMemoryCaptureAdapter.capture_result(mission, result, stream_version=2)
        self.assertEqual("BLOCKER_SET", event.event_type)
        self.assertEqual("PROVIDER_GATE", event.payload["blocker_code"])
        self.assertEqual("continue-safe-lanes", event.payload["next_action"])

    def test_result_metadata_is_digest_only(self) -> None:
        mission = self.mission()
        result = MissionResultCapture(
            state="SUCCESS",
            observed_at="2026-08-31T21:01:00Z",
            source_refs=("bubbles:receipt/1",),
            proof_refs=("proof:1",),
            result_ref="artifact://result-1",
            result_sha256="a" * 64,
            metadata={"private_runtime_note": "do not persist this raw"},
        )
        event = BibleMemoryCaptureAdapter.capture_result(mission, result, stream_version=2)
        serialized = json.dumps(event.payload, sort_keys=True)
        self.assertNotIn("do not persist this raw", serialized)
        self.assertIn("metadata_sha256", event.payload)

    def test_invalid_version_and_missing_source_fail_closed(self) -> None:
        mission = self.mission()
        with self.assertRaisesRegex(ValueError, "BMF_CAPTURE_STREAM_VERSION_INVALID"):
            BibleMemoryCaptureAdapter.capture_mission_compiled(
                mission, stream_version=0, recorded_at="2026-08-31T21:00:00Z", source_refs=("missionir:test",)
            )
        with self.assertRaisesRegex(ValueError, "BMF_CAPTURE_SOURCE_REF_REQUIRED"):
            BibleMemoryCaptureAdapter.capture_mission_compiled(
                mission, stream_version=1, recorded_at="2026-08-31T21:00:00Z", source_refs=()
            )

    def test_adapter_has_no_storage_or_provider_execution_surface(self) -> None:
        forbidden = {"append", "persist", "send", "publish", "deploy", "execute_provider", "write_provider"}
        self.assertTrue(forbidden.isdisjoint(set(dir(BibleMemoryCaptureAdapter))))


if __name__ == "__main__":
    unittest.main()
