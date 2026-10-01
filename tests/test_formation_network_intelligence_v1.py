import unittest

from federation.formation_network_intelligence_v1 import (
    EvidenceKind,
    FormationNetworkIntelligence,
    NetworkEvidence,
    classify_mac,
)


class FormationNetworkIntelligenceTests(unittest.TestCase):
    def test_private_mac_is_not_vendor_oui(self):
        c = classify_mac("F6:92:B6:2D:2D:C0")
        self.assertTrue(c.unicast)
        self.assertTrue(c.locally_administered)
        self.assertFalse(c.vendor_oui_trustworthy)

    def test_ip_reuse_is_detected(self):
        intel = FormationNetworkIntelligence()
        out = intel.assess(
            [
                NetworkEvidence("e1", EvidenceKind.SECURITY_PRODUCT, "2026-05-14", "avast", ip="192.168.0.23", mac="EC:8E:77:7B:17:A9", current=False),
                NetworkEvidence("e2", EvidenceKind.SECURITY_PRODUCT, "2026-10-01", "avast-ui", ip="192.168.0.23", mac="F6:92:B6:2D:2D:C0", current=False),
            ]
        )
        self.assertTrue(out.ip_reuse_detected)
        self.assertIn("IP_REUSED_ACROSS_DISTINCT_MAC_IDENTITIES:192.168.0.23", out.contradictions)

    def test_offline_does_not_become_absent(self):
        intel = FormationNetworkIntelligence()
        out = intel.assess(
            [NetworkEvidence("e1", EvidenceKind.ARP, "2026-10-01", "windows-neighbor", ip="192.168.0.23", current=False)]
        )
        self.assertEqual(out.identity_state, "HISTORICAL")
        self.assertNotEqual(out.maliciousness, "MALICIOUS")

    def test_private_mac_reduces_confidence_and_requests_dhcp(self):
        intel = FormationNetworkIntelligence()
        out = intel.assess(
            [NetworkEvidence("e1", EvidenceKind.SECURITY_PRODUCT, "2026-10-01", "avast", ip="192.168.0.23", mac="F6:92:B6:2D:2D:C0", current=False)]
        )
        self.assertTrue(out.private_mac_present)
        self.assertIn("CORRELATE_DHCP_CLIENT_ID_OR_ROUTER_ASSOCIATION_HISTORY", out.next_evidence)

    def test_independent_current_evidence_increases_confidence(self):
        intel = FormationNetworkIntelligence()
        low = intel.assess([NetworkEvidence("e1", EvidenceKind.ARP, "t", "a", ip="192.168.0.23", mac="00:11:22:33:44:55")])
        high = intel.assess([
            NetworkEvidence("e1", EvidenceKind.ARP, "t", "a", ip="192.168.0.23", mac="00:11:22:33:44:55", independent=True),
            NetworkEvidence("e2", EvidenceKind.DHCP, "t", "b", ip="192.168.0.23", mac="00:11:22:33:44:55", hostname="host", independent=True),
        ])
        self.assertGreater(high.confidence, low.confidence)


if __name__ == "__main__":
    unittest.main()
