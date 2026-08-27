import json
import tempfile
import unittest
from pathlib import Path

from ao_harmonic_v3.behavioral_binding import (
    BehavioralStoreConflict,
    InMemoryBehavioralRecordStore,
    JsonlBehavioralRecordStore,
)
from ao_harmonic_v3.behavioral_convergence import (
    BehavioralEvidenceKind,
    BehavioralOrigin,
    BehavioralProofReceipt,
)
from ao_harmonic_v3.models import FederationEvent
from ao_harmonic_v3.runtime import AOHarmonicV3


def failure_event(
    event_id: str,
    *,
    idempotency_key: str | None = None,
    origin: str = "REAL_RUNTIME",
    observed_fruit: str = "Airlock rejected direct-main provenance",
) -> FederationEvent:
    return FederationEvent(
        event_id=event_id,
        event_type="FAILURE",
        source="Federation Omega",
        workstream="Failure-Win behavioral binding",
        idempotency_key=idempotency_key or f"idem-{event_id}",
        timestamp="2026-08-27T07:47:00+02:00",
        proof_class="INDEPENDENT_READBACK",
        authority_class="A1_INTERNAL",
        payload={
            "behavioral_origin": origin,
            "proof_refs": [f"proof:{event_id}"],
            "independent_readback": True,
            "current": True,
            "objective": "Preserve governed source admission",
            "claim": "A governed source change should pass current admission",
            "observed_fruit": observed_fruit,
            "desired_outcome": "Current source admitted without weakening controls",
            "failure_code": "SOURCE_PROVENANCE_REJECTED",
            "provider": "GitHub",
            "material": True,
        },
    )


class FailureWinBehavioralRuntimeBindingTests(unittest.TestCase):
    def test_real_failure_routes_through_behavioral_binding_once(self):
        store = InMemoryBehavioralRecordStore()
        runtime = AOHarmonicV3(behavioral_store=store)

        outputs = runtime.events.emit(failure_event("REAL-001"))

        self.assertEqual(1, len(outputs))
        behavioral = outputs[0]["behavioral_convergence"]
        self.assertEqual("BEHAVIOR_PROOF_OPEN", behavioral["state"])
        self.assertTrue(behavioral["empirical_failure_seen"])
        self.assertFalse(behavioral["behavior_proven"])
        self.assertEqual("IN_MEMORY_NON_DURABLE", behavioral["persistence"]["store_kind"])
        self.assertTrue(behavioral["persistence"]["record_stored"])
        self.assertEqual(1, len(store.records()))
        self.assertEqual(behavioral["kernel_result"], outputs[0]["failure_to_operational_win_v2"])

    def test_synthetic_failure_cannot_promote_behavior(self):
        runtime = AOHarmonicV3(behavioral_store=InMemoryBehavioralRecordStore())

        outputs = runtime.events.emit(failure_event("SYN-001", origin="SYNTHETIC_TEST"))

        behavioral = outputs[0]["behavioral_convergence"]
        self.assertEqual("INVOCATION_ONLY_NON_EMPIRICAL", behavioral["state"])
        self.assertFalse(behavioral["empirical_failure_seen"])
        self.assertFalse(behavioral["behavior_proven"])

    def test_jsonl_store_replays_real_event_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "behavioral.jsonl"
            first_store = JsonlBehavioralRecordStore(path)
            first = AOHarmonicV3(behavioral_store=first_store)
            result = first.events.emit(failure_event("REAL-RESTART-001"))[0]["behavioral_convergence"]
            fingerprint = result["fingerprint"]

            second_store = JsonlBehavioralRecordStore(path)
            second = AOHarmonicV3(behavioral_store=second_store)
            restored = second.behavioral.assess(fingerprint)

            self.assertEqual(1, second.behavioral_binding.replayed_records)
            self.assertTrue(restored.empirical_failure_seen)
            self.assertFalse(restored.behavior_proven)
            self.assertEqual("JSONL_LOCAL_DURABLE", second.behavioral_binding.store.kind)

    def test_proof_receipt_is_persisted_and_replayed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "behavioral.jsonl"
            runtime = AOHarmonicV3(behavioral_store=JsonlBehavioralRecordStore(path))
            event_result = runtime.events.emit(failure_event("REAL-PROOF-001"))[0]["behavioral_convergence"]
            fingerprint = event_result["fingerprint"]
            receipt = BehavioralProofReceipt(
                event_id="PROOF-CAUSAL-001",
                receiver_id="Federation Omega",
                kind=BehavioralEvidenceKind.CAUSAL_MODEL,
                origin=BehavioralOrigin.REAL_RUNTIME,
                observed_at="2026-08-27T07:48:00+02:00",
                proof_refs=("proof:causal-model",),
                independent_readback=True,
                current=True,
            )

            proof_result = runtime.record_behavioral_proof(fingerprint, receipt)
            self.assertTrue(proof_result["persistence"]["record_stored"])
            self.assertEqual(2, len(runtime.behavioral_binding.store.records()))

            restored = AOHarmonicV3(behavioral_store=JsonlBehavioralRecordStore(path))
            assessment = restored.behavioral.assess(fingerprint)
            self.assertEqual(2, restored.behavioral_binding.replayed_records)
            self.assertEqual(1, assessment.qualifying_receipts)
            self.assertFalse(assessment.behavior_proven)

    def test_store_rejects_same_record_id_with_different_payload(self):
        store = InMemoryBehavioralRecordStore()
        runtime = AOHarmonicV3(behavioral_store=store)
        runtime.events.emit(failure_event("CONFLICT-001"))

        with self.assertRaises(Exception):
            runtime.events.emit(
                failure_event(
                    "CONFLICT-001",
                    idempotency_key="different-idempotency-key",
                    observed_fruit="Different fruit under same event id",
                )
            )

    def test_jsonl_store_fails_closed_on_payload_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "behavioral.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "schema": "failure-win.behavioral-binding.v1",
                        "record_id": "TAMPER-001",
                        "record_type": "FEDERATION_EVENT",
                        "payload_sha256": "not-the-real-hash",
                        "payload": {"event": {}},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                JsonlBehavioralRecordStore(path)


if __name__ == "__main__":
    unittest.main()
