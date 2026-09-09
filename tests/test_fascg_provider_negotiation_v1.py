import unittest

from benchmarking.cfbe_omega.fascg_provider_fabric_v1 import (
    CapabilityNegotiator, NegotiationAdvertisement, provider_fabric_manifest,
)


def ad(pid, protocols=("A2A_1",), caps=("handoff",), mods=("text",), verified=True):
    return NegotiationAdvertisement(
        advertisement_id=f"ad-{pid}", provider_id=pid, protocols=tuple(protocols),
        capabilities=tuple(caps), modalities=tuple(mods), endpoint_fingerprint="a"*64,
        authority_ceiling="A1_INTERNAL", proof_refs=(f"proof:{pid}",),
        advertisement_signature_verified=verified,
    )


class ProviderNegotiationTests(unittest.TestCase):
    def setUp(self): self.n=CapabilityNegotiator()
    def test_full_coverage_wins_over_partial(self):
        r=self.n.negotiate(("handoff","tools"), (ad("partial",caps=("handoff",)), ad("full",caps=("handoff","tools"))), allowed_protocols=("A2A_1",))
        self.assertEqual(r.provider_id,"full"); self.assertTrue(r.complete)
    def test_protocol_preference_is_deterministic(self):
        r=self.n.negotiate(("handoff",), (ad("p",protocols=("MCP_2026_07","A2A_1")),), allowed_protocols=("A2A_1","MCP_2026_07"))
        self.assertEqual(r.protocol,"A2A_1")
    def test_unverified_advertisement_is_ignored(self):
        r=self.n.negotiate(("handoff",), (ad("x",verified=False),), allowed_protocols=("A2A_1",))
        self.assertIsNone(r.provider_id); self.assertFalse(r.complete)
    def test_modality_requirement_is_enforced(self):
        r=self.n.negotiate(("handoff",), (ad("text",mods=("text",)), ad("multi",mods=("text","audio"))), allowed_protocols=("A2A_1",), required_modalities=("audio",))
        self.assertEqual(r.provider_id,"multi"); self.assertTrue(r.modalities_satisfied)
    def test_advertisement_never_proves_execution(self):
        r=self.n.negotiate(("handoff",), (ad("x"),), allowed_protocols=("A2A_1",))
        self.assertFalse(r.provider_execution_proven); self.assertFalse(r.external_effect_authorized)
    def test_empty_required_capabilities_rejected(self):
        with self.assertRaisesRegex(ValueError,"REQUIRED_CAPABILITIES_EMPTY"):
            self.n.negotiate((),(ad("x"),),allowed_protocols=("A2A_1",))
    def test_empty_protocol_set_rejected(self):
        with self.assertRaisesRegex(ValueError,"ALLOWED_PROTOCOLS_EMPTY"):
            self.n.negotiate(("handoff",),(ad("x"),),allowed_protocols=())
    def test_manifest_does_not_claim_live_mcp_a2a_endpoint(self):
        m=provider_fabric_manifest(); n=m["capability_negotiation"]
        self.assertTrue(n["stateless"]); self.assertFalse(n["live_mcp_or_a2a_endpoint_claimed"]); self.assertFalse(n["provider_execution_inherited_from_advertisement"])

if __name__=='__main__': unittest.main()
