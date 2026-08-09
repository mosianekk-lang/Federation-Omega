import json
import unittest
from pathlib import Path

from kaio_fluid.shadow import RegisteredSourceShadowValidator


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "tests" / "fixtures" / "federation_n_evidenceops_fevx_cse_v110.json"


class KaioRegisteredSourceShadowTests(unittest.TestCase):
    def load_packet(self):
        return json.loads(PACKET.read_text(encoding="utf-8"))

    def test_real_registered_source_packet_shadow_validates_without_provider_claim(self):
        result = RegisteredSourceShadowValidator().validate(self.load_packet())
        self.assertEqual("SHADOW_VALIDATED_REGISTERED_SOURCE_PACKET", result.status)
        self.assertEqual("evidenceops", result.domain)
        self.assertEqual(4, result.source_count)
        self.assertEqual(10, result.open_provider_proofs)
        self.assertEqual("A1_INTERNAL", result.authority_ceiling)
        self.assertFalse(result.external_effect)
        self.assertFalse(result.provider_mutation_permitted)
        self.assertFalse(result.provider_runtime_verified)
        self.assertIn("remain unverified", result.release_claim)

    def test_shadow_rejects_external_effect_or_provider_mutation(self):
        for field in ("external_effect", "provider_mutation_permitted"):
            packet = self.load_packet()
            packet[field] = True
            with self.assertRaises(ValueError):
                RegisteredSourceShadowValidator().validate(packet)

    def test_shadow_rejects_missing_sources(self):
        packet = self.load_packet()
        packet["sources"] = []
        with self.assertRaises(ValueError):
            RegisteredSourceShadowValidator().validate(packet)

    def test_shadow_is_deterministic(self):
        validator = RegisteredSourceShadowValidator()
        first = validator.validate(self.load_packet())
        second = validator.validate(self.load_packet())
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
