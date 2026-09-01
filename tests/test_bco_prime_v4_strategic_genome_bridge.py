import unittest

from benchmarking.cfbe_omega.bco_prime_v4_strategic_genome_bridge import recommend_strategic_genomes
from formation_omega.strategic_ecology import StrategicGenomeRecord


class StrategicGenomeBridgeTests(unittest.TestCase):
    def test_best_existing_genome_is_recommended_without_execution_authority(self):
        strong = StrategicGenomeRecord.create(
            features=("source-drift", "proof-repair", "github"),
            mission_sequence=("REFRESH_SOURCE", "MINIMAL_PATCH", "AIRLOCK", "READBACK"),
            realized_value=0.95,
            reliability=0.95,
            evidence_refs=("proof:strong",),
        )
        weak = StrategicGenomeRecord.create(
            features=("source-drift", "manual"),
            mission_sequence=("ASK_OWNER",),
            realized_value=0.2,
            reliability=0.4,
            evidence_refs=("proof:weak",),
        )
        receipt = recommend_strategic_genomes(
            (weak, strong),
            features=("source-drift", "proof-repair", "github"),
        )
        self.assertEqual(receipt.selected_pattern_id, strong.pattern_id)
        self.assertEqual(receipt.preparatory_mission_sequence, strong.mission_sequence)
        self.assertFalse(receipt.execution_authorized)
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertEqual(len(receipt.receipt_sha256), 64)

    def test_no_similar_genome_returns_empty_preparation(self):
        record = StrategicGenomeRecord.create(
            features=("creative", "canva"),
            mission_sequence=("DESIGN",),
            realized_value=0.8,
            reliability=0.8,
        )
        receipt = recommend_strategic_genomes(
            (record,),
            features=("github", "proof"),
            minimum_similarity=0.5,
        )
        self.assertIsNone(receipt.selected_pattern_id)
        self.assertEqual(receipt.preparatory_mission_sequence, ())

    def test_receipt_is_deterministic(self):
        record = StrategicGenomeRecord.create(
            features=("recovery", "provider"),
            mission_sequence=("READBACK", "REROUTE"),
            realized_value=0.7,
            reliability=0.9,
        )
        left = recommend_strategic_genomes((record,), features=("provider", "recovery"))
        right = recommend_strategic_genomes((record,), features=("recovery", "provider"))
        self.assertEqual(left, right)


if __name__ == "__main__":
    unittest.main()
