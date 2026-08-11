from __future__ import annotations

import asyncio
import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from evidenceops_ai_ict_durable.bridge import DurableAgentsBridge, StrictCanaryError
from evidenceops_ai_ict_durable.store import DurableRunStore

TRACE_AUTH_PLACEHOLDER = "contract-" + "auth-placeholder"


class TestProtector:
    key_id = "test-only-key"

    def encrypt(self, plaintext: bytes, *, aad: bytes) -> bytes:
        mask = hashlib.sha256(aad).digest()
        return bytes(b ^ mask[i % len(mask)] for i, b in enumerate(plaintext))

    def decrypt(self, ciphertext: bytes, *, aad: bytes) -> bytes:
        return self.encrypt(ciphertext, aad=aad)


class FakeRunConfig:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeAgent:
    def __init__(self, **kwargs):
        self.name = kwargs["name"]


class FakeState:
    approved: list[str] = []
    rejected: list[str] = []

    def to_json(self, **kwargs):
        assert kwargs["include_tracing_api_key"] is False
        assert kwargs["strict_context"] is True
        return {"context": {}, "trace": {"trace_id": "trace-safe"}}

    def approve(self, item):
        self.approved.append(item.call_id)

    def reject(self, item, rejection_message):
        assert rejection_message == "Action rejected by policy authority."
        self.rejected.append(item.call_id)


class FakeRunState:
    call = None

    @staticmethod
    async def from_json(**kwargs):
        FakeRunState.call = kwargs
        return FakeState()


class FakeResult:
    def __init__(self, output="EVIDENCEOPS_MODEL_CANARY_OK", interruptions=None):
        self.final_output = output
        self.interruptions = interruptions or []
        self.last_response_id = "resp_model_canary"
        self.context_wrapper = SimpleNamespace(
            usage=SimpleNamespace(requests=1, input_tokens=9, output_tokens=4)
        )

    def to_state(self):
        return FakeState()


class FakeRunner:
    result = FakeResult()
    calls = []
    error = None

    @classmethod
    async def run(cls, *args, **kwargs):
        if cls.error:
            raise cls.error
        rc = kwargs["run_config"]
        assert rc.kwargs["trace_include_sensitive_data"] is False
        assert rc.kwargs["model_provider"] == "run-scoped-provider"
        assert rc.kwargs["tracing"] == {"api_key": TRACE_AUTH_PLACEHOLDER}
        assert not callable(rc.kwargs["tracing"])
        assert rc.kwargs["trace_id"] == "trace_01234567890123456789012345678901"
        cls.calls.append((args, kwargs))
        return cls.result


class DurableOverlayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = DurableRunStore(
            str(Path(self.tmp.name) / "runs.db"), TestProtector()
        )
        self.flush_count = 0

        def flush_traces():
            self.flush_count += 1

        self.sdk = lambda: {
            "Agent": FakeAgent,
            "RunConfig": FakeRunConfig,
            "RunState": FakeRunState,
            "Runner": FakeRunner,
            "flush_traces": flush_traces,
            "gen_trace_id": lambda: "trace_01234567890123456789012345678901",
        }
        self.bridge = DurableAgentsBridge(self.store, sdk_loader=self.sdk)
        FakeRunner.calls = []
        FakeRunner.error = None
        FakeState.approved = []
        FakeState.rejected = []
        FakeRunState.call = None

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def pause(self, mission_id="M-RESUME", call_ids=("call-1",)):
        interruptions = [
            {"call_id": call_id, "tool_name": "canonical_write", "agent_name": "A"}
            for call_id in call_ids
        ]
        return self.store.save_paused(
            mission_id,
            {"context": {}, "trace": {"trace_id": "trace-safe"}},
            interruptions,
        )

    def test_strict_model_canary_receipt_and_trace_flush(self):
        FakeRunner.result = FakeResult()
        receipt = asyncio.run(
            self.bridge.run(
                mission_id="M-CANARY",
                directive="Return the exact canary text",
                model_provider="run-scoped-provider",
                tracing_api_key=TRACE_AUTH_PLACEHOLDER,
                expected_output="EVIDENCEOPS_MODEL_CANARY_OK",
            )
        )
        self.assertEqual(receipt.status, "MODEL_BACKED_COMPLETE")
        self.assertEqual(receipt.response_id, "resp_model_canary")
        self.assertTrue(receipt.trace_flushed)
        self.assertEqual(self.flush_count, 1)

    def test_strict_canary_rejects_wrong_output(self):
        FakeRunner.result = FakeResult(output="almost")
        with self.assertRaises(StrictCanaryError):
            asyncio.run(
                self.bridge.run(
                    mission_id="M-BAD",
                    directive="canary",
                    model_provider="run-scoped-provider",
                    tracing_api_key=TRACE_AUTH_PLACEHOLDER,
                    expected_output="EVIDENCEOPS_MODEL_CANARY_OK",
                )
            )

    def test_interruption_state_is_encrypted_and_readable(self):
        interruption = SimpleNamespace(
            call_id="call-1", tool_name="canonical_write", agent=FakeAgent(name="A")
        )
        FakeRunner.result = FakeResult(interruptions=[interruption])
        receipt = asyncio.run(
            self.bridge.run(
                mission_id="M-PAUSE",
                directive="write canonically",
                model_provider="run-scoped-provider",
                tracing_api_key=TRACE_AUTH_PLACEHOLDER,
            )
        )
        self.assertEqual(receipt.status, "WAITING_APPROVAL")
        row = self.store.conn.execute(
            "SELECT state_ciphertext FROM durable_agent_runs WHERE mission_id='M-PAUSE'"
        ).fetchone()
        self.assertNotIn(b"trace-safe", bytes(row[0]))
        loaded = self.store.load("M-PAUSE")
        self.assertEqual(loaded.state_json["trace"]["trace_id"], "trace-safe")

    def test_resume_requires_complete_approval_coverage(self):
        version = self.pause(call_ids=("c1", "c2"))
        self.store.record_decision("M-RESUME", "c1", "APPROVE", "policy", "ok")
        with self.assertRaisesRegex(RuntimeError, "approval coverage incomplete"):
            self.store.claim_for_resume(
                "M-RESUME", expected_state_version=version
            )

    def test_unknown_approval_call_id_is_rejected(self):
        self.pause()
        with self.assertRaisesRegex(ValueError, "not a pending interruption"):
            self.store.record_decision(
                "M-RESUME", "unknown", "APPROVE", "policy", "bad"
            )

    def test_resume_is_fenced_and_completion_scrubs_state(self):
        version = self.pause()
        self.store.record_decision(
            "M-RESUME", "call-1", "APPROVE", "policy", "within scope"
        )
        FakeRunner.result = FakeResult(output="resumed")
        agent = FakeAgent(name="Resume Director")
        receipt = asyncio.run(
            self.bridge.resume(
                mission_id="M-RESUME",
                agent=agent,
                model_provider="run-scoped-provider",
                tracing_api_key=TRACE_AUTH_PLACEHOLDER,
                expected_state_version=version,
                interruption_lookup=lambda state, call_id: SimpleNamespace(
                    call_id=call_id
                ),
            )
        )
        self.assertEqual(receipt.output, "resumed")
        row = self.store.conn.execute(
            "SELECT status,state_ciphertext,interruptions_json FROM durable_agent_runs "
            "WHERE mission_id='M-RESUME'"
        ).fetchone()
        self.assertEqual(row["status"], "COMPLETE")
        self.assertEqual(bytes(row["state_ciphertext"]), b"")
        self.assertEqual(row["interruptions_json"], "[]")
        with self.assertRaisesRegex(RuntimeError, "not available for resume"):
            self.store.claim_for_resume("M-RESUME")

    def test_stale_state_version_fails_closed(self):
        version = self.pause()
        self.store.record_decision(
            "M-RESUME", "call-1", "APPROVE", "policy", "within scope"
        )
        with self.assertRaisesRegex(RuntimeError, "stale run-state version"):
            self.store.claim_for_resume(
                "M-RESUME", expected_state_version=version + 1
            )

    def test_active_claim_prevents_duplicate_resume(self):
        self.pause()
        self.store.record_decision(
            "M-RESUME", "call-1", "APPROVE", "policy", "within scope"
        )
        claim = self.store.claim_for_resume("M-RESUME")
        self.assertTrue(claim.claim_token)
        with self.assertRaisesRegex(RuntimeError, "not available for resume"):
            self.store.claim_for_resume("M-RESUME")

    def test_failed_resume_releases_claim(self):
        self.pause()
        self.store.record_decision(
            "M-RESUME", "call-1", "APPROVE", "policy", "within scope"
        )
        FakeRunner.error = RuntimeError("transient model failure")
        with self.assertRaisesRegex(RuntimeError, "transient model failure"):
            asyncio.run(
                self.bridge.resume(
                    mission_id="M-RESUME",
                    agent=FakeAgent(name="Resume Director"),
                    model_provider="run-scoped-provider",
                    tracing_api_key=TRACE_AUTH_PLACEHOLDER,
                    interruption_lookup=lambda state, call_id: SimpleNamespace(
                        call_id=call_id
                    ),
                )
            )
        row = self.store.conn.execute(
            "SELECT status,resume_token FROM durable_agent_runs WHERE mission_id='M-RESUME'"
        ).fetchone()
        self.assertEqual(row["status"], "WAITING_APPROVAL")
        self.assertIsNone(row["resume_token"])

    def test_resume_can_repause_with_new_version_and_clears_old_decisions(self):
        version = self.pause()
        self.store.record_decision(
            "M-RESUME", "call-1", "APPROVE", "policy", "within scope"
        )
        next_interruption = SimpleNamespace(
            call_id="call-2", tool_name="publish", agent=FakeAgent(name="A")
        )
        FakeRunner.result = FakeResult(interruptions=[next_interruption])
        receipt = asyncio.run(
            self.bridge.resume(
                mission_id="M-RESUME",
                agent=FakeAgent(name="Resume Director"),
                model_provider="run-scoped-provider",
                tracing_api_key=TRACE_AUTH_PLACEHOLDER,
                expected_state_version=version,
                interruption_lookup=lambda state, call_id: SimpleNamespace(
                    call_id=call_id
                ),
            )
        )
        self.assertEqual(receipt.status, "WAITING_APPROVAL")
        self.assertEqual(receipt.state_version, version + 1)
        self.assertEqual(self.store.decisions("M-RESUME"), {})
        self.store.record_decision(
            "M-RESUME", "call-2", "REJECT", "policy", "not allowed"
        )
        self.assertEqual(self.store.decisions("M-RESUME"), {"call-2": "REJECT"})

    def test_secret_like_state_is_rejected_before_persistence(self):
        with self.assertRaises(ValueError):
            self.store.save_paused(
                "M-SECRET",
                {"context": {"api_key": ("s" + "k-") + "this-should-never-persist"}},
                [],
            )

    def test_approval_is_idempotent_within_current_version(self):
        self.pause("M-APP", ("c1",))
        self.store.record_decision("M-APP", "c1", "APPROVE", "policy", "within scope")
        self.store.record_decision("M-APP", "c1", "REJECT", "policy", "scope changed")
        self.assertEqual(self.store.decisions("M-APP"), {"c1": "REJECT"})

    def test_invalid_trace_id_fails_closed(self):
        bad_sdk = self.sdk()
        bad_sdk["gen_trace_id"] = lambda: "invalid"
        bridge = DurableAgentsBridge(self.store, sdk_loader=lambda: bad_sdk)
        with self.assertRaises(RuntimeError):
            asyncio.run(
                bridge.run(
                    mission_id="M-TRACE",
                    directive="canary",
                    model_provider="run-scoped-provider",
                    tracing_api_key=TRACE_AUTH_PLACEHOLDER,
                )
            )


if __name__ == "__main__":
    unittest.main()
