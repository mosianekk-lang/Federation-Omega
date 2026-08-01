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

    @classmethod
    async def run(cls, *args, **kwargs):
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
        self.sdk = lambda: {
            "Agent": FakeAgent,
            "RunConfig": FakeRunConfig,
            "RunState": FakeRunState,
            "Runner": FakeRunner,
            "gen_trace_id": lambda: "trace_01234567890123456789012345678901",
        }
        self.bridge = DurableAgentsBridge(self.store, sdk_loader=self.sdk)
        FakeRunner.calls = []
        FakeState.approved = []
        FakeState.rejected = []
        FakeRunState.call = None

    def tearDown(self):
        self.tmp.cleanup()

    def test_strict_model_canary_receipt(self):
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
        self.assertEqual(
            receipt.trace_id, "trace_01234567890123456789012345678901"
        )
        self.assertEqual(receipt.requests, 1)

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

    def test_resume_awaits_from_json_with_initial_agent_and_strict_context(self):
        self.store.save_paused(
            "M-RESUME",
            {"context": {}, "trace": {"trace_id": "trace-safe"}},
            [{"call_id": "call-1"}],
        )
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
                interruption_lookup=lambda state, call_id: SimpleNamespace(
                    call_id=call_id
                ),
            )
        )
        self.assertIs(FakeRunState.call["initial_agent"], agent)
        self.assertEqual(FakeRunState.call["state_json"]["context"], {})
        self.assertTrue(FakeRunState.call["strict_context"])
        self.assertEqual(FakeState.approved, ["call-1"])
        self.assertEqual(receipt.output, "resumed")
        self.assertEqual(
            receipt.trace_id, "trace_01234567890123456789012345678901"
        )

    def test_secret_like_state_is_rejected_before_persistence(self):
        with self.assertRaises(ValueError):
            self.store.save_paused(
                "M-SECRET",
                {"context": {"api_key": ("s" + "k-") + "this-should-never-persist"}},
                [],
            )

    def test_approval_is_idempotent(self):
        self.store.save_paused("M-APP", {"context": {}}, [{"call_id": "c1"}])
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
