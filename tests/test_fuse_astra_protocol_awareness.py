import unittest

from fuse_astra_protocol_awareness.awareness import (
    CommunicationIntent,
    InteractionClass,
    ProtocolAwarenessEngine,
    ProtocolObservation,
    ProtocolPolicy,
    ProtocolSelectionError,
    default_protocol_registry,
)


class ProtocolAwarenessTests(unittest.TestCase):
    def setUp(self):
        self.engine = ProtocolAwarenessEngine(default_protocol_registry())

    def test_mcp_headers_detect_mcp(self):
        results = self.engine.detect(
            ProtocolObservation(headers={"Mcp-Method": "tools/call", "Mcp-Name": "search"})
        )
        self.assertEqual(results[0].semantic_id, "PROTO.MCP")
        self.assertGreaterEqual(results[0].confidence, 0.8)

    def test_a2a_agent_card_and_header_detect_a2a(self):
        results = self.engine.detect(
            ProtocolObservation(
                headers={"A2A-Version": "1.0"},
                payload_keys=("supportedInterfaces",),
            )
        )
        self.assertEqual(results[0].semantic_id, "PROTO.A2A")

    def test_tool_intent_prefers_mcp(self):
        candidates = self.engine.select(
            CommunicationIntent(
                InteractionClass.TOOL,
                require_tool_invocation=True,
                require_discovery=True,
                prefer_stateless=True,
            )
        )
        self.assertEqual(candidates[0].semantic_id, "PROTO.MCP")

    def test_agent_intent_can_negotiate_a2a_1_0(self):
        negotiated = self.engine.negotiate(
            CommunicationIntent(
                InteractionClass.AGENT_TO_AGENT,
                require_task_lifecycle=True,
                require_discovery=True,
                require_streaming=True,
                prefer_binary=True,
            ),
            {"PROTO.A2A": ("1.0",)},
        )
        self.assertEqual(negotiated.semantic_id, "PROTO.A2A")
        self.assertEqual(negotiated.version, "1.0")
        self.assertEqual(negotiated.transport, "grpc+tls")

    def test_silent_version_downgrade_fails_closed(self):
        with self.assertRaises(ProtocolSelectionError):
            self.engine.negotiate(
                CommunicationIntent(
                    InteractionClass.AGENT_TO_AGENT,
                    require_task_lifecycle=True,
                    require_discovery=True,
                ),
                {"PROTO.A2A": ("0.3",)},
                ProtocolPolicy(forbid_silent_downgrade=True),
            )

    def test_non_idempotent_action_is_not_retried(self):
        policy = ProtocolPolicy(max_retry_attempts=3)
        self.assertFalse(self.engine.retry_allowed(idempotent=False, attempt=0, policy=policy))
        self.assertTrue(self.engine.retry_allowed(idempotent=True, attempt=0, policy=policy))
        self.assertFalse(self.engine.retry_allowed(idempotent=True, attempt=3, policy=policy))

    def test_event_intent_prefers_cloudevents(self):
        candidates = self.engine.select(
            CommunicationIntent(InteractionClass.EVENT, require_event_envelope=True)
        )
        self.assertEqual(candidates[0].semantic_id, "PROTO.CLOUDEVENTS")

    def test_agent_user_state_sync_prefers_agui(self):
        candidates = self.engine.select(
            CommunicationIntent(
                InteractionClass.AGENT_TO_USER,
                require_streaming=True,
                require_bidirectional=True,
                require_ui_state_sync=True,
            )
        )
        self.assertEqual(candidates[0].semantic_id, "PROTO.AGUI")


if __name__ == "__main__":
    unittest.main()
