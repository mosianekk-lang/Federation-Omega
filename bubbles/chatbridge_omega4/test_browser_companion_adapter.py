from __future__ import annotations

import os
import tempfile
import unittest

from .browser_companion_adapter import (
    BrowserCompanionAdapter,
    BrowserCompanionEnvelopeError,
    _sha256,
)
from .runtime_omega49 import ChatBridgeOmega49
from .store import ChatBridgeStore


class BrowserCompanionAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.runtime = ChatBridgeOmega49(
            ChatBridgeStore(os.path.join(self.tmp.name, "chatbridge.sqlite3"))
        )
        self.key = "browser-companion-conversation-001"
        self.namespace = "browser-companion-canary"
        self.path_id = "browser-rendered-dom:installation-001"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _message(
        self,
        *,
        sequence: int,
        role: str,
        stream: str,
        text: str,
        source_event_id: str,
        stream_sequence: int | None = 1,
        event_type: str = "MESSAGE",
        execution_state: str = "OBSERVED",
        global_sequence: int | None = None,
    ) -> dict:
        if global_sequence is None and event_type != "CORRECTION":
            global_sequence = sequence
        source_turn_id = f"turn-{sequence}"
        hash_event_type = "MESSAGE" if event_type == "CORRECTION" else event_type
        payload_hash = _sha256(
            {
                "conversation_key": self.key,
                "role": role,
                "event_type": hash_event_type,
                "content": text,
                "source_turn_id": source_turn_id,
                "provider_event_id": "",
                "artifacts": [],
            }
        )
        return {
            "conversation_key": self.key,
            "namespace_key": self.namespace,
            "path_id": self.path_id,
            "stream": stream,
            "role": role,
            "event_type": event_type,
            "content": text,
            "occurred_at": f"2026-08-17T03:20:{sequence:02d}+02:00",
            "global_sequence": global_sequence,
            "stream_sequence": stream_sequence,
            "source_event_id": source_event_id,
            "source_turn_id": source_turn_id,
            "provider_event_id": "",
            "idempotency_key": f"browser:{self.key}:{source_event_id}:{payload_hash}",
            "execution_state": execution_state,
            "payload_availability": "RAW_GOVERNED",
            "sensitivity": "GOVERNED_LOCAL",
            "artifacts": [],
            "metadata": {
                "companion_version": "0.3.0",
                "capture_path_kind": "RENDERED_DOM",
                "payload_hash": payload_hash,
                "rendered_dom_snapshot": True,
            },
        }

    def _terminal(
        self,
        sequence: int,
        *,
        execution_state: str = "NOT_EXECUTED_TERMINAL",
    ) -> dict:
        text = "You've reached the maximum length for this conversation."
        payload_hash = _sha256(
            {
                "conversation_key": self.key,
                "event_type": "TERMINAL_WARNING",
                "content": text,
                "sequence": sequence,
            }
        )
        return {
            "conversation_key": self.key,
            "namespace_key": self.namespace,
            "path_id": self.path_id,
            "stream": "TERMINAL",
            "role": "SYSTEM",
            "event_type": "TERMINAL_WARNING",
            "content": text,
            "occurred_at": "2026-08-17T03:20:10+02:00",
            "global_sequence": sequence,
            "stream_sequence": 1,
            "source_event_id": f"terminal:{payload_hash}",
            "source_turn_id": "",
            "provider_event_id": "",
            "idempotency_key": f"browser:{self.key}:terminal:{payload_hash}",
            "execution_state": execution_state,
            "payload_availability": "RAW_GOVERNED",
            "sensitivity": "NON_SENSITIVE_OPERATIONAL",
            "artifacts": [],
            "metadata": {
                "companion_version": "0.3.0",
                "capture_path_kind": "RENDERED_DOM",
                "payload_hash": payload_hash,
                "terminal_intent_is_not_execution": True,
            },
        }

    def _envelope(
        self,
        observations: list[dict],
        *,
        provider: str = "CHATGPT_WEB",
        source_complete: bool = False,
        terminal: bool = False,
        previous_snapshot: str = "",
        correction_count: int = 0,
    ) -> dict:
        stream_sequences: dict[str, list[int]] = {}
        for item in observations:
            if item.get("stream_sequence") is not None:
                stream_sequences.setdefault(item["stream"], []).append(
                    int(item["stream_sequence"])
                )
        snapshot_sha = _sha256(
            {
                "conversation_key": self.key,
                "path_id": self.path_id,
                "observations": [
                    {
                        "source_event_id": item["source_event_id"],
                        "payload_hash": item["metadata"]["payload_hash"],
                        "global_sequence": item["global_sequence"],
                        "stream": item["stream"],
                    }
                    for item in observations
                ],
            }
        )
        return {
            "schema": "CHATBRIDGE-ALPHA-OMEGA-BROWSER-CAPTURE-1",
            "companion_version": "0.3.0",
            "capture_id": f"cbcap-test-{snapshot_sha[:16]}",
            "captured_at": "2026-08-17T03:20:30+02:00",
            "source": {
                "provider": provider,
                "url": f"https://chatgpt.com/c/{self.key}",
                "title": "Browser canary",
                "conversation_key": self.key,
                "route_key": "",
            },
            "namespace_key": self.namespace,
            "capture_path": {
                "conversation_key": self.key,
                "path_id": self.path_id,
                "kind": "RENDERED_DOM",
                "source_provider": provider,
                "state": "AVAILABLE",
                "priority": 70,
                "proof_strength": 0.72,
                "completeness": 1.0 if source_complete else 0.65,
                "freshness": 1.0,
                "speed": 0.95,
                "reversibility": 1.0,
                "owner_burden": 0.0,
                "privacy_cost": 0.35,
                "maintenance_cost": 0.25,
                "independent_group": "browser-installation:installation-001",
                "authoritative": False,
                "metadata": {
                    "companion_version": "0.3.0",
                    "rendered_dom_snapshot": True,
                    "source_complete_claim": source_complete,
                },
            },
            "observations": list(observations),
            "stream_manifest": [
                {
                    "stream": stream,
                    "observed_first_sequence": min(sequences),
                    "observed_last_sequence": max(sequences),
                    "observed_count": len(sequences),
                    "required_for_exact_restore": source_complete
                    and stream != "TERMINAL",
                    "source_complete_claim": source_complete,
                }
                for stream, sequences in stream_sequences.items()
            ],
            "snapshot": {
                "sha256": snapshot_sha,
                "previous_sha256": previous_snapshot,
                "rendered_message_count": len(
                    [item for item in observations if item["event_type"] == "MESSAGE"]
                ),
                "observation_count": len(observations),
                "first_global_sequence": 1 if observations else None,
                "last_global_sequence": max(
                    (item["global_sequence"] or 0 for item in observations),
                    default=0,
                )
                or None,
                "terminal_observed": terminal,
                "exact_source_completeness_claimed": source_complete,
            },
            "delta": {
                "previous_snapshot_sha256": previous_snapshot,
                "current_snapshot_sha256": snapshot_sha,
                "added_count": len(observations) - correction_count,
                "correction_count": correction_count,
                "removed_from_rendered_dom_count": 0,
                "removed_source_event_ids": [],
                "unchanged_count": 0,
                "no_silent_deletion": True,
            },
            "truth_boundary": {
                "native_hidden_chat_access": False,
                "rendered_dom_may_be_virtualized": True,
                "exact_restore_from_this_path_alone": source_complete,
                "provider_effects_require_readback": True,
                "missing_content_is_never_guessed": True,
            },
        }

    def test_bounded_rendered_path_is_ingested_and_idempotent(self) -> None:
        observations = [
            self._message(
                sequence=1,
                role="USER",
                stream="USER",
                text="start",
                source_event_id="evt-1",
            ),
            self._message(
                sequence=2,
                role="ASSISTANT",
                stream="ASSISTANT",
                text="finish",
                source_event_id="evt-2",
            ),
        ]
        envelope = self._envelope(observations)
        adapter = BrowserCompanionAdapter(self.runtime)
        first = adapter.ingest(envelope)
        second = adapter.ingest(envelope)
        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        self.assertFalse(first["receipt"]["source_complete_claim_trusted"])
        self.assertFalse(first["receipt"]["exact_alpha_omega_complete"])
        verification = self.runtime.verify_conversation_ledger(self.key)
        self.assertEqual(verification["event_count"], 2)
        ranked = self.runtime.rank_capture_paths(self.key)
        self.assertEqual(ranked[0]["kind"], "RENDERED_DOM")
        self.assertFalse(ranked[0]["authoritative"])

    def test_browser_complete_claim_is_ignored_by_default(self) -> None:
        envelope = self._envelope(
            [
                self._message(
                    sequence=1,
                    role="USER",
                    stream="USER",
                    text="one",
                    source_event_id="evt-1",
                )
            ],
            source_complete=True,
        )
        receipt = BrowserCompanionAdapter(self.runtime).ingest(envelope)["receipt"]
        self.assertTrue(receipt["source_complete_claim_received"])
        self.assertFalse(receipt["source_complete_claim_trusted"])
        self.assertFalse(receipt["exact_transcript_complete"])

    def test_explicit_test_complete_claim_can_seal_single_path_transcript(self) -> None:
        observations = [
            self._message(
                sequence=1,
                role="USER",
                stream="USER",
                text="one",
                source_event_id="evt-1",
            ),
            self._message(
                sequence=2,
                role="ASSISTANT",
                stream="ASSISTANT",
                text="two",
                source_event_id="evt-2",
            ),
        ]
        # The trusted-complete mode is a deterministic canary. Use the canonical ledger
        # provider identity so finalization tests the intended single-path boundary rather
        # than a provider-label mismatch that production bounded browser capture never trusts.
        receipt = BrowserCompanionAdapter(
            self.runtime,
            allow_test_source_complete_claim=True,
        ).ingest(
            self._envelope(
                observations,
                provider="CHATGPT",
                source_complete=True,
            )
        )["receipt"]
        self.assertTrue(receipt["source_complete_claim_trusted"])
        self.assertTrue(
            self.runtime.verify_conversation_ledger(self.key)[
                "exact_context_complete"
            ]
        )
        self.assertFalse(receipt["exact_alpha_omega_complete"])

    def test_terminal_intent_cannot_be_called_executed(self) -> None:
        with self.assertRaises(BrowserCompanionEnvelopeError):
            BrowserCompanionAdapter(self.runtime).ingest(
                self._envelope(
                    [self._terminal(1, execution_state="EXECUTED_VERIFIED")],
                    terminal=True,
                )
            )

    def test_payload_hash_conflict_fails_closed(self) -> None:
        observation = self._message(
            sequence=1,
            role="USER",
            stream="USER",
            text="one",
            source_event_id="evt-1",
        )
        envelope = self._envelope([observation])
        envelope["observations"][0]["metadata"]["payload_hash"] = "0" * 64
        with self.assertRaises(BrowserCompanionEnvelopeError):
            BrowserCompanionAdapter(self.runtime).ingest(envelope)

    def test_correction_is_appended_without_rewriting_prior_event(self) -> None:
        adapter = BrowserCompanionAdapter(self.runtime)
        first = self._envelope(
            [
                self._message(
                    sequence=1,
                    role="USER",
                    stream="USER",
                    text="first wording",
                    source_event_id="evt-1",
                )
            ]
        )
        adapter.ingest(first)
        correction = self._message(
            sequence=2,
            role="USER",
            stream="CORRECTION",
            text="corrected wording",
            source_event_id="evt-1:revision:corrected",
            stream_sequence=None,
            event_type="CORRECTION",
            global_sequence=None,
        )
        correction["metadata"].update(
            {
                "correction_of_source_event_id": "evt-1",
                "correction_reason": "RENDERED_TURN_CHANGED_AFTER_PRIOR_STABLE_SNAPSHOT",
            }
        )
        adapter.ingest(
            self._envelope(
                [correction],
                previous_snapshot=first["snapshot"]["sha256"],
                correction_count=1,
            )
        )
        restored = self.runtime.reconstruct_conversation(self.key)
        self.assertEqual(
            [event["event_type"] for event in restored["transcript"]],
            ["MESSAGE", "CORRECTION"],
        )

    def test_transport_secret_field_is_rejected(self) -> None:
        envelope = self._envelope(
            [
                self._message(
                    sequence=1,
                    role="USER",
                    stream="USER",
                    text="one",
                    source_event_id="evt-1",
                )
            ]
        )
        envelope["connector_token"] = "must-not-enter-payload"
        with self.assertRaises(BrowserCompanionEnvelopeError):
            BrowserCompanionAdapter(self.runtime).ingest(envelope)


if __name__ == "__main__":
    unittest.main()
