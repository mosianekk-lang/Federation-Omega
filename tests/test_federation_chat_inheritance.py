from __future__ import annotations

import unittest

from federation_automation_gateway.chat_inheritance import SHARED_FABRIC_ID, build_profile, canonical_engine, engine_allowed


class FederationChatInheritanceTests(unittest.TestCase):
    def test_superior_logic_scoped_chat_inherits_canonical_engine(self):
        profile = build_profile(chat_session_id="CHAT-TEST-001", engine="SUPERIOR_LOGIC:CHAT-001")
        self.assertEqual(profile.canonical_engine, "SUPERIOR_LOGIC")
        self.assertEqual(profile.fabric_id, SHARED_FABRIC_ID)
        self.assertEqual(profile.authority_inheritance, "SHARED_FABRIC_ONLY")
        self.assertFalse(profile.credential_inheritance)
        self.assertEqual(profile.continuation_rule, "CONTINUE_UNTIL_SEMANTIC_TERMINAL_RECEIPT_OR_EXACT_EXTERNAL_GATE")

    def test_admitted_engine_profiles_can_scope_per_chat(self):
        for engine in ("SOVARA/session-7", "REALITYGUARD@chat-a", "CFBE:benchmark-chat", "KIOAS/workstream-4"):
            self.assertTrue(engine_allowed(engine), engine)
            self.assertIsNotNone(canonical_engine(engine))

    def test_unlisted_prefix_without_delimiter_is_rejected(self):
        self.assertFalse(engine_allowed("SUPERIOR_LOGIC_UNLISTED"))
        self.assertIsNone(canonical_engine("SOVARA2"))

    def test_profile_digest_is_deterministic(self):
        first = build_profile(chat_session_id="CHAT-1", engine="SUPERIOR_LOGIC")
        second = build_profile(chat_session_id="CHAT-1", engine="SUPERIOR_LOGIC")
        self.assertEqual(first.digest(), second.digest())

    def test_missing_session_or_unknown_engine_fails_closed(self):
        with self.assertRaises(ValueError):
            build_profile(chat_session_id="", engine="SUPERIOR_LOGIC")
        with self.assertRaises(ValueError):
            build_profile(chat_session_id="CHAT-X", engine="UNLISTED_ENGINE")


if __name__ == "__main__":
    unittest.main()
