import unittest

from omega_one.maturity import CapabilityMaturityCompiler, MaturityStage
from omega_one.portfolio import (
    CAPABILITY_HOLDS,
    PORTFOLIO_EVIDENCE,
    blueprint_capabilities,
    maturity_records,
    validate_blueprint_baseline,
)


class OmegaOnePortfolioTests(unittest.TestCase):
    def setUp(self):
        self.capabilities = blueprint_capabilities()
        self.records = maturity_records()
        self.verdicts = {
            verdict.capability_id: verdict
            for verdict in CapabilityMaturityCompiler.compile_portfolio(self.records)
        }

    def test_all_100_blueprint_capabilities_are_preserved_exactly_once(self):
        validation = validate_blueprint_baseline(self.records)
        self.assertEqual(validation["record_count"], 100)
        self.assertEqual(validation["unique_id_count"], 100)
        self.assertTrue(validation["ids_exact"])
        self.assertTrue(validation["all_zero_dilution"])
        self.assertTrue(validation["all_preserved"])

    def test_every_capability_has_design_proof_without_umbrella_runtime_promotion(self):
        self.assertEqual(len(self.verdicts), 100)
        for capability_id, verdict in self.verdicts.items():
            self.assertIsNotNone(verdict.lowest_proven_stage, capability_id)
            self.assertGreaterEqual(verdict.lowest_proven_stage, MaturityStage.DESIGNED)
            self.assertLess(verdict.lowest_proven_stage, MaturityStage.DEPLOYED)

    def test_v083_schema_compiler_and_sanitizer_keep_individual_proof(self):
        self.assertEqual(
            self.verdicts["CAP-031"].lowest_proven_stage,
            MaturityStage.DETERMINISTIC_TESTED,
        )
        self.assertEqual(
            self.verdicts["CAP-033"].lowest_proven_stage,
            MaturityStage.DETERMINISTIC_TESTED,
        )

    def test_complex_auth_remains_preserved_but_not_falsely_promoted(self):
        self.assertIn("CAP-034", CAPABILITY_HOLDS)
        self.assertEqual(
            self.verdicts["CAP-034"].lowest_proven_stage,
            MaturityStage.DESIGNED,
        )
        record = next(record for record in self.records if record.capability_id == "CAP-034")
        self.assertIn("OAuth2", record.metadata["holds"])

    def test_portfolio_receipts_are_evidence_not_individual_maturity_inheritance(self):
        self.assertEqual(len(PORTFOLIO_EVIDENCE), 3)
        historical = PORTFOLIO_EVIDENCE[1]
        staged = PORTFOLIO_EVIDENCE[2]
        self.assertEqual(
            historical["recorded_status"],
            "STATIC_CANDIDATE_REGISTRY_TESTED / NO_100_CAPABILITIES_DEPLOYED",
        )
        self.assertEqual(staged["proof_state"], "16_OF_16_UNIT_TESTS_PASS")
        self.assertIn(
            "individual provider maturity for every capability",
            staged["does_not_support"],
        )

    def test_no_capability_is_deleted_because_it_is_unproven(self):
        by_id = {capability.capability_id: capability for capability in self.capabilities}
        self.assertEqual(set(by_id), {f"CAP-{i:03d}" for i in range(1, 101)})
        for capability in by_id.values():
            self.assertEqual(capability.preservation_state, "PRESERVED_FULL_CAPABILITY")
            self.assertTrue(capability.zero_dilution)


if __name__ == "__main__":
    unittest.main()
