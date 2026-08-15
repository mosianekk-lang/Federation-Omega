from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from .live_canary import DEFAULT_MODEL, _redacted_result, _require_runtime_env


class ChatBridgeOmega4LiveCanaryTests(unittest.TestCase):
    def test_current_default_canary_model_is_explicit(self) -> None:
        self.assertEqual(DEFAULT_MODEL, "gpt-5.4-mini")

    def test_missing_api_key_fails_closed_without_accepting_chat_input(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                _require_runtime_env(DEFAULT_MODEL)

    def test_secret_presence_is_checked_but_never_returned(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-not-a-real-key"}, clear=True):
            _require_runtime_env(DEFAULT_MODEL)

    def test_result_redaction_excludes_raw_output(self) -> None:
        result = {
            "state": "TURN_COMPLETE_READBACK_VERIFIED",
            "namespace": "canary",
            "conversation_id": "conv_test",
            "response_id": "resp_test",
            "final_output": "sensitive synthetic output",
            "receipt": {"receipt_id": "receipt_test"},
        }
        redacted = _redacted_result(result)
        self.assertNotIn("final_output", redacted)
        self.assertNotIn("sensitive synthetic output", str(redacted))
        self.assertTrue(redacted["output_sha256"])

    def test_marker_verification_is_explicit(self) -> None:
        result = {"final_output": "cb4-marker-123"}
        redacted = _redacted_result(result, marker="cb4-marker-123")
        self.assertTrue(redacted["marker_observed"])
        redacted2 = _redacted_result(result, marker="different")
        self.assertFalse(redacted2["marker_observed"])


if __name__ == "__main__":
    unittest.main()
