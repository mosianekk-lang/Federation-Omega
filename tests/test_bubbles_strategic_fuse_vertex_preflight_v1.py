from __future__ import annotations

import unittest

from bubbles.strategic_fuse_vertex_preflight_v1 import (
    ACTION,
    DEFAULT_OPERATOR,
    EXPECTED_TARGET,
    run_preflight,
)


class StrategicFuseVertexPreflightTests(unittest.TestCase):
    def success(self, **overrides):
        body = {
            "ok": True,
            "status": "GEMINI_VERTEX_CAPABILITY_READ",
            "authMode": "CLOUD_RUN_SERVICE_IDENTITY",
            "target": dict(EXPECTED_TARGET),
            "serviceState": "ENABLED",
            "semanticExecutionAttempted": False,
            "incrementalCost": 0,
            "silentFallback": False,
        }
        body.update(overrides)
        return body

    def test_success_requires_exact_a0_truth_contract(self):
        observed = {}
        def invoke(url, action, payload):
            observed.update(url=url, action=action, payload=payload)
            return self.success()
        receipt = run_preflight(source_ref="main:abc", invoke_fn=invoke)
        self.assertEqual("VERTEX_A0_CAPABILITY_READBACK_VERIFIED", receipt.state)
        self.assertTrue(receipt.provider_native_capability_readback_verified)
        self.assertEqual(DEFAULT_OPERATOR, observed["url"])
        self.assertEqual(ACTION, observed["action"])
        self.assertEqual(EXPECTED_TARGET, observed["payload"])
        self.assertFalse(receipt.semantic_execution_attempted)
        self.assertEqual(0, receipt.incremental_cost)
        self.assertFalse(receipt.provider_mutation_attempted)
        self.assertEqual("NONE", receipt.authority_delta)

    def test_semantic_execution_signal_blocks_a0_promotion(self):
        receipt = run_preflight(
            source_ref="main:abc",
            invoke_fn=lambda *_: self.success(semanticExecutionAttempted=True),
        )
        self.assertEqual("HELD_PROVIDER_CAPABILITY_OR_TRUTH_BOUNDARY", receipt.state)
        self.assertFalse(receipt.provider_native_capability_readback_verified)
        self.assertTrue(receipt.failure_fingerprint.startswith("sha256:"))

    def test_nonzero_cost_blocks_a0_promotion(self):
        receipt = run_preflight(
            source_ref="main:abc",
            invoke_fn=lambda *_: self.success(incrementalCost=1),
        )
        self.assertFalse(receipt.provider_native_capability_readback_verified)
        self.assertEqual("HELD_PROVIDER_CAPABILITY_OR_TRUTH_BOUNDARY", receipt.state)

    def test_silent_fallback_blocks_a0_promotion(self):
        receipt = run_preflight(
            source_ref="main:abc",
            invoke_fn=lambda *_: self.success(silentFallback=True),
        )
        self.assertFalse(receipt.provider_native_capability_readback_verified)

    def test_wrong_target_blocks_a0_promotion(self):
        wrong = dict(EXPECTED_TARGET)
        wrong["project"] = "wrong-project"
        receipt = run_preflight(
            source_ref="main:abc",
            invoke_fn=lambda *_: self.success(target=wrong),
        )
        self.assertFalse(receipt.provider_native_capability_readback_verified)
        self.assertIn("targetMatch=False", receipt.failure_detail)

    def test_disabled_vertex_service_is_preserved_as_provider_hold(self):
        receipt = run_preflight(
            source_ref="main:abc",
            invoke_fn=lambda *_: self.success(
                status="VERTEX_AI_API_DISABLED",
                serviceState="DISABLED",
            ),
        )
        self.assertEqual("HELD_PROVIDER_CAPABILITY_OR_TRUTH_BOUNDARY", receipt.state)
        self.assertEqual("DISABLED", receipt.vertex_service_state)

    def test_missing_or_failed_callable_edge_emits_receipt_instead_of_raising(self):
        def invoke(*_):
            raise RuntimeError("operator HTTP 403: denied")
        receipt = run_preflight(source_ref="main:abc", invoke_fn=invoke)
        self.assertEqual("HELD_CALLABILITY_UNPROVEN", receipt.state)
        self.assertTrue(receipt.operator_invocation_attempted)
        self.assertFalse(receipt.operator_authenticated_response_observed)
        self.assertTrue(receipt.failure_fingerprint.startswith("sha256:"))
        self.assertIn("403", receipt.failure_detail)

    def test_operator_target_cannot_be_repointed(self):
        with self.assertRaisesRegex(ValueError, "OPERATOR_TARGET_MISMATCH"):
            run_preflight(operator_url="https://example.invalid", source_ref="main:abc")

    def test_source_ref_is_required(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_REF_REQUIRED"):
            run_preflight(source_ref="")

    def test_receipt_is_deterministic_for_same_evidence(self):
        invoke = lambda *_: self.success()
        first = run_preflight(source_ref="main:abc", invoke_fn=invoke)
        second = run_preflight(source_ref="main:abc", invoke_fn=invoke)
        self.assertEqual(first.receipt_sha256, second.receipt_sha256)

    def test_preflight_never_invokes_semantic_action(self):
        actions = []
        def invoke(_url, action, _payload):
            actions.append(action)
            return self.success()
        run_preflight(source_ref="main:abc", invoke_fn=invoke)
        self.assertEqual(["READ_GEMINI_VERTEX_CAPABILITY"], actions)
        self.assertNotIn("VERIFY_GEMINI_VERTEX_SEMANTIC", actions)


if __name__ == "__main__":
    unittest.main()
