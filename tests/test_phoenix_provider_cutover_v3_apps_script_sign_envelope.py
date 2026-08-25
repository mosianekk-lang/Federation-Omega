from __future__ import annotations

import hashlib
import hmac
import json
import unittest

from tools.sign_envelope import (
    build_unsigned_envelope,
    canonical_json,
    sign_envelope,
)


SECRET = "gateway-test-secret-material-with-at-least-32-characters"
TIMESTAMP = "2026-08-23T19:45:00Z"
NONCE = "nonce-0123456789abcdef0123456789abcdef"


class AppsScriptGatewayEnvelopeSignerTests(unittest.TestCase):
    def test_status_envelope_matches_exact_lowercase_hex_hmac(self) -> None:
        unsigned = build_unsigned_envelope(
            action="STATUS",
            timestamp=TIMESTAMP,
            nonce=NONCE,
        )
        signed = sign_envelope(unsigned, SECRET)
        expected = hmac.new(
            SECRET.encode("utf-8"),
            canonical_json(unsigned).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(expected, signed["signature"])
        self.assertRegex(signed["signature"], r"^[a-f0-9]{64}$")
        self.assertEqual({}, signed["payload"])
        self.assertNotIn(SECRET, json.dumps(signed))

    def test_challenge_payload_is_exact_and_bounded(self) -> None:
        unsigned = build_unsigned_envelope(
            action="challenge",
            timestamp=TIMESTAMP,
            nonce=NONCE,
            challenge="nonce-canary-001",
        )
        self.assertEqual("CHALLENGE", unsigned["action"])
        self.assertEqual({"challenge": "nonce-canary-001"}, unsigned["payload"])

    def test_wrong_target_and_unsupported_action_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "canonical target"):
            build_unsigned_envelope(
                action="STATUS",
                timestamp=TIMESTAMP,
                nonce=NONCE,
                target_project_number="516699068552",
            )
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            build_unsigned_envelope(
                action="CODE_APPLY",
                timestamp=TIMESTAMP,
                nonce=NONCE,
            )

    def test_credential_like_challenge_and_short_secret_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "Credential-like"):
            build_unsigned_envelope(
                action="CHALLENGE",
                timestamp=TIMESTAMP,
                nonce=NONCE,
                challenge="Bearer abcdefghijklmnopqrstuvwxyz",
            )
        unsigned = build_unsigned_envelope(
            action="STATUS",
            timestamp=TIMESTAMP,
            nonce=NONCE,
        )
        with self.assertRaisesRegex(ValueError, "at least 32"):
            sign_envelope(unsigned, "too-short")


if __name__ == "__main__":
    unittest.main()
