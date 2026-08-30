import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CENSUS = ROOT / "governance" / "forest_first_consumer_census_v1.json"


class ForestFirstConsumerCensusV1Tests(unittest.TestCase):
    def setUp(self):
        self.census = json.loads(CENSUS.read_text(encoding="utf-8"))
        self.rows = {row["system"]: row for row in self.census["candidates"]}

    def test_all_consolidation_candidates_are_present(self):
        self.assertEqual(len(self.rows), 11)

    def test_high_coupling_families_are_not_early_migrations(self):
        self.assertEqual(self.rows["Superior Logic Doctrine"]["migration_order"], "LATE")
        self.assertEqual(self.rows["CASEFORGE-Ω"]["migration_order"], "LATE")
        self.assertEqual(self.rows["FORMATION-OMEGA Unified Powerhouse"]["migration_order"], "LAST")

    def test_no_hit_claims_are_bounded_not_zero_consumer_claims(self):
        for name in ("AEON-Ω", "IPEP", "SIF AI"):
            self.assertEqual(
                self.rows[name]["coupling"],
                "NO_DIRECT_NAME_HITS_IN_BOUNDED_CURRENT_MAIN_SEARCH",
            )
        self.assertFalse(self.census["truth_boundary"]["consumer_inventory_complete"])

    def test_scientia_split_preserves_existing_native_organ(self):
        row = self.rows["Next Frontier AI Bible / Ω-SCIENTIA"]
        self.assertEqual(row["coupling"], "SPLIT_EXISTING_NATIVE_OMEGA_SCIENTIA")
        self.assertIn("ao_harmonic_v3/science_and_routes.py::OmegaScientia", row["evidence"])

    def test_no_physical_migration_or_provider_effect(self):
        boundary = self.census["truth_boundary"]
        self.assertFalse(boundary["physical_migration_executed"])
        self.assertFalse(boundary["runtime_changed"])
        self.assertFalse(boundary["provider_effect"])


if __name__ == "__main__":
    unittest.main()
