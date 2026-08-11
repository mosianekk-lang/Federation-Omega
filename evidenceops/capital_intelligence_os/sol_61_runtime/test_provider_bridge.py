from __future__ import annotations

import unittest

from provider_bridge import ExecutionRequest, InMemoryAdapter, ProviderCapability, ProviderExecutionBridge


class ProviderExecutionBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bridge = ProviderExecutionBridge()
        self.bridge.register_adapter("github", InMemoryAdapter())
        self.bridge.register_capability(ProviderCapability("github", "write", True, True, True, "VERIFIED"))

    def test_verified_execution_idempotency_and_rollback(self) -> None:
        request = ExecutionRequest(
            request_id="req-1",
            provider="github",
            operation="write",
            payload={"path": "x"},
            idempotency_key="idem-1",
            expected_readback={"active": True},
        )
        first = self.bridge.execute(request)
        second = self.bridge.execute(request)
        self.assertEqual(first.execution_ref, second.execution_ref)
        rolled = self.bridge.rollback(first)
        self.assertFalse(rolled["readback"]["active"])

    def test_unverified_authority_is_blocked(self) -> None:
        self.bridge.register_capability(ProviderCapability("apps_script", "source_write", True, True, True, "OWNER_CONSENT_REQUIRED"))
        request = ExecutionRequest("req-2", "apps_script", "source_write", {}, "idem-2")
        self.assertEqual(self.bridge.admit(request)["state"], "OWNER_CONSENT_REQUIRED")

    def test_owner_reserved_operation_requires_authority(self) -> None:
        self.bridge.register_capability(ProviderCapability("gmail", "send", True, True, False, "VERIFIED", owner_reserved=True))
        self.bridge.register_adapter("gmail", InMemoryAdapter())
        request = ExecutionRequest("req-3", "gmail", "send", {}, "idem-3")
        self.assertEqual(self.bridge.admit(request)["state"], "OWNER_AUTHORITY_REQUIRED")

    def test_readback_mismatch_rolls_back(self) -> None:
        request = ExecutionRequest(
            request_id="req-4",
            provider="github",
            operation="write",
            payload={"path": "x"},
            idempotency_key="idem-4",
            expected_readback={"active": False},
        )
        with self.assertRaisesRegex(RuntimeError, "READBACK_MISMATCH"):
            self.bridge.execute(request)


if __name__ == "__main__":
    unittest.main()
