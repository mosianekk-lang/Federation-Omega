import unittest

from fuse_astra_protocol_awareness.trust import (
    CommunicationTrustPolicy,
    InboundMessage,
    MessageClass,
    PeerIdentity,
    ProtocolSemanticFirewall,
    TrustDecision,
    authority_intersection,
)


class ProtocolTrustTests(unittest.TestCase):
    def setUp(self):
        self.firewall = ProtocolSemanticFirewall()
        self.policy = CommunicationTrustPolicy(
            trusted_issuers=("fuse-ca",),
            allowed_effects=("read", "write"),
            authorized_control_peers=("owner-console",),
            require_attestation_for_effects=("write",),
            max_message_age_ms=60_000,
        )

    def peer(self, peer_id="owner-console", authenticated=True, attested=True, issuer="fuse-ca"):
        return PeerIdentity(peer_id, issuer, authenticated, f"spiffe://fuse/{peer_id}", attested)

    def test_authorized_attested_control_message_is_allowed(self):
        msg = InboundMessage(
            "m1",
            MessageClass.CONTROL,
            self.peer(),
            requested_effect="write",
            claimed_authority=("deploy",),
        )
        result = self.firewall.evaluate(msg, self.policy)
        self.assertEqual(result.decision, TrustDecision.ALLOW)

    def test_tool_result_cannot_promote_itself_to_control(self):
        msg = InboundMessage(
            "m2",
            MessageClass.TOOL_RESULT,
            self.peer("tool-7"),
            requested_effect="read",
            claimed_authority=("deploy",),
            content_origin="web",
        )
        result = self.firewall.evaluate(msg, self.policy)
        self.assertEqual(result.decision, TrustDecision.QUARANTINE)

    def test_advertised_capability_does_not_grant_authority(self):
        msg = InboundMessage(
            "m3",
            MessageClass.AGENT_MESSAGE,
            self.peer("remote-agent"),
            requested_effect="read",
            advertised_capabilities=("admin", "deploy"),
        )
        result = self.firewall.evaluate(msg, self.policy)
        self.assertEqual(result.decision, TrustDecision.ALLOW)
        self.assertIn("capabilities treated as descriptive, not authoritative", result.reasons)
        self.assertEqual(authority_intersection(("admin", "deploy"), ("read",)), frozenset())

    def test_unauthenticated_peer_is_denied(self):
        msg = InboundMessage("m4", MessageClass.DATA, self.peer(authenticated=False))
        self.assertEqual(self.firewall.evaluate(msg, self.policy).decision, TrustDecision.DENY)

    def test_untrusted_issuer_is_denied(self):
        msg = InboundMessage("m5", MessageClass.DATA, self.peer(issuer="unknown-ca"))
        self.assertEqual(self.firewall.evaluate(msg, self.policy).decision, TrustDecision.DENY)

    def test_stale_message_is_denied(self):
        msg = InboundMessage("m6", MessageClass.DATA, self.peer(), age_ms=60_001)
        self.assertEqual(self.firewall.evaluate(msg, self.policy).decision, TrustDecision.DENY)

    def test_invalid_signature_is_denied(self):
        msg = InboundMessage("m7", MessageClass.DATA, self.peer(), signature_valid=False)
        self.assertEqual(self.firewall.evaluate(msg, self.policy).decision, TrustDecision.DENY)

    def test_write_effect_requires_attestation(self):
        msg = InboundMessage(
            "m8",
            MessageClass.CONTROL,
            self.peer(attested=False),
            requested_effect="write",
        )
        self.assertEqual(self.firewall.evaluate(msg, self.policy).decision, TrustDecision.DENY)

    def test_non_authorized_control_peer_is_denied(self):
        msg = InboundMessage(
            "m9",
            MessageClass.CONTROL,
            self.peer("agent-x"),
            requested_effect="read",
        )
        self.assertEqual(self.firewall.evaluate(msg, self.policy).decision, TrustDecision.DENY)


if __name__ == "__main__":
    unittest.main()
