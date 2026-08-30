import unittest

from sovara.creative.taste import TasteError, TasteMemory, TasteObservation


class SovaraCreativeTasteTests(unittest.TestCase):
    def observation(self, identity, value, weight, sequence, **extra):
        return TasteObservation(
            observation_id=identity,
            dimension="lighting",
            value=value,
            evidence_weight=weight,
            sequence=sequence,
            **extra,
        )

    def test_replay_is_deterministic(self):
        observations = [
            self.observation("obs-2", "low-key", 0.8, 2),
            self.observation("obs-1", "soft", 0.6, 1),
        ]
        a = TasteMemory("owner-creative")
        b = TasteMemory("owner-creative")
        a.observe_many(observations)
        b.observe_many(reversed(observations))
        self.assertEqual(a.state_record(), b.state_record())
        self.assertEqual(a.receipt(), b.receipt())

    def test_recent_owner_correction_can_outweigh_old_preference(self):
        memory = TasteMemory("owner-creative", decay=0.5)
        memory.observe(self.observation("old", "bright", 1.0, 0))
        memory.observe(self.observation("new", "low-key", 0.8, 3))
        preference = memory.preference("lighting")
        self.assertEqual(preference.value, "low-key")
        self.assertEqual(preference.conflicting_observation_ids, ("old",))

    def test_conflict_is_preserved_not_erased(self):
        memory = TasteMemory("owner-creative", decay=1.0)
        memory.observe(self.observation("a", "bright", 0.7, 1))
        memory.observe(self.observation("b", "low-key", 0.9, 2))
        preference = memory.preference("lighting")
        self.assertEqual(preference.supporting_observation_ids, ("b",))
        self.assertEqual(preference.conflicting_observation_ids, ("a",))
        self.assertEqual(memory.receipt().conflict_count, 1)

    def test_synthetic_evidence_never_promotes_preference(self):
        memory = TasteMemory("owner-creative")
        memory.observe(self.observation("synthetic", "low-key", 1.0, 1, synthetic=True))
        self.assertIsNone(memory.preference("lighting"))
        self.assertEqual(memory.receipt().preference_count, 0)

    def test_duplicate_observation_is_rejected(self):
        memory = TasteMemory("owner-creative")
        observation = self.observation("same", "bright", 0.8, 1)
        memory.observe(observation)
        with self.assertRaises(TasteError):
            memory.observe(observation)

    def test_invalid_weights_and_decay_fail_closed(self):
        with self.assertRaises(TasteError):
            self.observation("bad", "bright", 1.01, 1)
        with self.assertRaises(TasteError):
            TasteMemory("owner-creative", decay=0)

    def test_receipt_never_claims_authority_or_external_effect(self):
        memory = TasteMemory("owner-creative")
        memory.observe(self.observation("owner", "soft", 1.0, 1))
        receipt = memory.receipt()
        self.assertFalse(receipt.authority_inherited)
        self.assertFalse(receipt.external_effect_performed)


if __name__ == "__main__":
    unittest.main()
