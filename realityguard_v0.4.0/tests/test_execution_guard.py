from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from realityguard import EffectState, ExecutionGuard, GuardDecision
from realityguard.schema import InputError


ROOT = Path(__file__).resolve().parents[1]


def email_request() -> dict:
    return {
        "schema_version": "realityguard.execution-guard.v1",
        "request": {
            "request_id": "EMAIL-1",
            "tool_name": "gmail.send_email",
            "operation": "send",
            "effect_class": "EXTERNAL_MESSAGE",
            "target": {
                "recipients": ["faith@example.org", "employer@example.org"],
                "recipients_verified": True,
            },
            "payload": {
                "subject": "MPMB298-26 Rule 32 application",
                "attachments": [{
                    "name": "MPMB298-26.pdf",
                    "transport": {
                        "mode": "FILE_REFERENCE",
                        "reference": "file_000000007e2081f4bc40759fa4027778",
                        "sha256": "sha256:" + "a" * 64,
                    },
                }],
            },
            "expected_fruit": {
                "provider_state": "SENT",
                "recipient_count": 2,
                "attachment_sha256": ["sha256:" + "a" * 64],
            },
            "idempotency_key": "rule32-email-v1",
        },
        "authority": {
            "formation_permit_consumed": True,
            "permit_single_use": True,
            "action_binding_matches": True,
            "proof_ref": "formation:test-consumed",
        },
        "route": {
            "readback_supported": True,
            "semantic_canary_verified": True,
            "canary_proof_ref": "canary:gmail-draft-readback",
            "inline_binary_supported": False,
            "inline_binary_canary_verified": False,
        },
        "retry": {"attempt": 1, "previous_attempts": [], "exact_repair": ""},
    }


class ExecutionGuardRegressionTests(unittest.TestCase):
    def setUp(self):
        self.guard = ExecutionGuard()

    def test_original_gmail_pdf_base64_transport_is_blocked(self):
        payload = email_request()
        payload["request"]["payload"]["attachments"][0] = {
            "name": "MPMB298-26.pdf",
            "content_base64": "JVBERi0xLjQK" + ("A" * 1024),
        }
        result = self.guard.preflight_tool_call(payload)
        self.assertEqual(result.decision, GuardDecision.BLOCK_UNSAFE_BINARY_TRANSPORT)
        self.assertFalse(result.dispatch_authorized)
        self.assertTrue(result.binary_paths)

    def test_unchanged_failed_retry_is_blocked(self):
        payload = email_request()
        fingerprint = self.guard.preflight_tool_call(payload).request_fingerprint
        payload["retry"] = {
            "attempt": 2,
            "exact_repair": "Retry unchanged after transport error",
            "previous_attempts": [{
                "request_fingerprint": fingerprint,
                "idempotency_key": "old-key",
                "status": "FAILED",
            }],
        }
        self.assertEqual(self.guard.preflight_tool_call(payload).decision, GuardDecision.BLOCK_UNCHANGED_RETRY)

    def test_idempotency_key_replay_is_blocked(self):
        payload = email_request()
        payload["retry"] = {
            "attempt": 2,
            "exact_repair": "Changed provider route",
            "previous_attempts": [{
                "request_fingerprint": "sha256:different",
                "idempotency_key": payload["request"]["idempotency_key"],
                "status": "TRANSPORT_SUCCEEDED",
            }],
        }
        self.assertEqual(self.guard.preflight_tool_call(payload).decision, GuardDecision.BLOCK_IDEMPOTENCY_REPLAY)

    def test_repaired_file_reference_route_is_admitted(self):
        result = self.guard.preflight_tool_call(email_request())
        self.assertEqual(result.decision, GuardDecision.ALLOW_DISPATCH)
        self.assertEqual(result.effect_state, EffectState.AUTHORIZED)

    def test_side_effect_requires_consumed_bound_permit(self):
        payload = email_request()
        payload["authority"]["formation_permit_consumed"] = False
        self.assertEqual(self.guard.preflight_tool_call(payload).decision, GuardDecision.BLOCK_INVALID_AUTHORITY)

    def test_external_message_requires_verified_recipients(self):
        payload = email_request()
        payload["request"]["target"]["recipients_verified"] = False
        self.assertEqual(self.guard.preflight_tool_call(payload).decision, GuardDecision.BLOCK_UNVERIFIED_RECIPIENT)

    def test_route_without_semantic_readback_is_blocked(self):
        payload = email_request()
        payload["route"]["readback_supported"] = False
        self.assertEqual(self.guard.preflight_tool_call(payload).decision, GuardDecision.BLOCK_UNVERIFIED_ROUTE)

    def test_transport_success_alone_cannot_release_sent(self):
        preflight = self.guard.preflight_tool_call(email_request())
        record = self.guard.observe_dispatch(preflight, {"transport_succeeded": True})
        self.assertEqual(record["effect_state"], "TRANSPORT_SUCCEEDED")
        self.assertFalse(self.guard.guard_claim_release(record, "SENT")["claim_authorized"])

    def test_provider_receipt_without_readback_cannot_release_sent(self):
        preflight = self.guard.preflight_tool_call(email_request())
        record = self.guard.observe_dispatch(preflight, {
            "transport_succeeded": True,
            "provider_receipt": {
                "provider_id": "gmail-message-1",
                "request_fingerprint": preflight.request_fingerprint,
                "current": True,
            },
        })
        self.assertEqual(record["effect_state"], "RECEIPT_VERIFIED")
        self.assertFalse(self.guard.guard_claim_release(record, "SENT")["claim_authorized"])

    def test_semantic_readback_releases_only_verified_state(self):
        preflight = self.guard.preflight_tool_call(email_request())
        record = self.guard.observe_dispatch(preflight, {
            "transport_succeeded": True,
            "provider_receipt": {
                "provider_id": "gmail-message-1",
                "request_fingerprint": preflight.request_fingerprint,
                "current": True,
                "proof_ref": "gmail:message-1",
            },
            "semantic_readback": {
                "current": True,
                "independent": True,
                "matches_expected": True,
                "verified_states": ["SENT"],
                "proof_ref": "gmail:readback-message-1",
            },
        })
        self.assertTrue(self.guard.guard_claim_release(record, "SENT")["claim_authorized"])
        self.assertFalse(self.guard.guard_claim_release(record, "FILED")["claim_authorized"])

    def test_draft_is_not_filed_or_deadline_protected(self):
        preflight = self.guard.preflight_tool_call(email_request())
        record = self.guard.observe_dispatch(preflight, {
            "transport_succeeded": True,
            "provider_receipt": {
                "provider_id": "gmail-draft-1",
                "request_fingerprint": preflight.request_fingerprint,
                "current": True,
            },
            "semantic_readback": {
                "current": True,
                "independent": True,
                "matches_expected": True,
                "verified_states": ["DRAFT"],
                "proof_ref": "gmail:draft-readback-1",
            },
        })
        self.assertTrue(self.guard.guard_claim_release(record, "DRAFT")["claim_authorized"])
        self.assertFalse(self.guard.guard_claim_release(record, "FILED")["claim_authorized"])

    def test_read_only_call_does_not_require_effect_permit(self):
        payload = {
            "schema_version": "realityguard.execution-guard.v1",
            "request": {
                "request_id": "READ-1", "tool_name": "gmail.search",
                "operation": "search", "effect_class": "READ_ONLY",
            },
        }
        self.assertEqual(self.guard.preflight_tool_call(payload).decision, GuardDecision.ALLOW_READ)

    def test_local_guard_never_self_certifies_host_binding(self):
        result = self.guard.preflight_tool_call(email_request()).to_dict()
        self.assertEqual(result["provider_binding"], "ADAPTER_REQUIRED")
        self.assertFalse(result["target_runtime_binding_proven"])

    def test_invalid_schema_fails_closed(self):
        payload = email_request()
        payload["schema_version"] = "future"
        with self.assertRaises(InputError):
            self.guard.preflight_tool_call(payload)


class ExecutionGuardCliTests(unittest.TestCase):
    def test_cli_returns_seven_for_blocked_preflight(self):
        payload = email_request()
        payload["request"]["payload"] = {"content_base64": "JVBERi0xLjQK" + ("A" * 1024)}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "realityguard.cli", "execution-preflight", "--input", str(path)],
                cwd=ROOT, text=True, capture_output=True,
                env={"PYTHONPATH": str(ROOT / "src")},
            )
        self.assertEqual(proc.returncode, 7)
        self.assertEqual(json.loads(proc.stdout)["decision"], "BLOCK_UNSAFE_BINARY_TRANSPORT")


if __name__ == "__main__":
    unittest.main()
