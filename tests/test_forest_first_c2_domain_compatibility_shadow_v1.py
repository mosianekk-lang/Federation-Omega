import unittest

from ao_harmonic_v3.domain_compatibility_shadow import run_c2_domain_compatibility_shadow


class ForestFirstC2DomainCompatibilityShadowV1Tests(unittest.TestCase):
    def setUp(self):
        self.report = run_c2_domain_compatibility_shadow()

    def test_all_five_required_scenarios_pass(self):
        self.assertEqual(self.report["scenario_count"], 5)
        self.assertTrue(self.report["pass"])
        self.assertTrue(all(row["pass_state"] for row in self.report["scenarios"]))

    def test_kioas_conflict_preserves_inputs_and_requires_regression(self):
        row = next(item for item in self.report["scenarios"] if item["scenario_id"] == "C2-KIOAS-CONFLICT-REGRESSION")
        self.assertTrue(row["checks"]["conflict_detected"])
        self.assertTrue(row["checks"]["regression_required"])
        self.assertTrue(row["checks"]["both_inputs_preserved"])

    def test_kaio_does_not_transfer_evidence_or_legal_authority(self):
        row = next(item for item in self.report["scenarios"] if item["scenario_id"] == "C2-KAIO-DOMAIN-AUTHORITY")
        self.assertTrue(row["checks"]["jfrie_remains_integrity_owner"])
        self.assertTrue(row["checks"]["truthgrid_evidenceops_remain_fact_owner"])
        self.assertTrue(row["checks"]["lex_remains_legal_owner"])
        self.assertTrue(row["checks"]["no_route_transfers_authority"])

    def test_legacy_maturity_is_not_inherited(self):
        self.assertFalse(self.report["legacy_kioas_proof_inherited"])
        self.assertFalse(self.report["legacy_kaio_maturity_inherited_to_lex"])
        self.assertFalse(self.report["provider_runtime_proved"])

    def test_shadow_remains_non_effectful_and_non_migratory(self):
        self.assertEqual(self.report["authority_ceiling"], "A1_INTERNAL")
        self.assertFalse(self.report["external_effect"])
        self.assertFalse(self.report["canonical_docs_modified"])
        self.assertFalse(self.report["physical_migration_executed"])
        self.assertEqual(self.report["independent_assurance_review"], "PENDING")


if __name__ == "__main__":
    unittest.main()
