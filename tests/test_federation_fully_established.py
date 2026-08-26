import unittest
from dataclasses import replace

from ops.federation_fully_established import (
    EstablishmentRecord,
    EstablishmentStage,
    GateResult,
    NotFullyEstablishedError,
    REQUIRED_GATES,
    all_pass_record,
    assert_terminal_claim,
    completion_status,
    evaluate_establishment,
    terminal_claim_allowed,
)


class FullyEstablishedGoldStandardTests(unittest.TestCase):
    def test_all_gates_with_proof_and_freshness_reaches_gold_standard(self):
        decision = evaluate_establishment(all_pass_record())
        self.assertTrue(decision.fully_established)
        self.assertEqual(EstablishmentStage.FULLY_ESTABLISHED, decision.stage)
        self.assertEqual("FULLY_ESTABLISHED", completion_status(all_pass_record()))

    def test_missing_reverse_semantic_path_blocks_terminal_completion(self):
        record = all_pass_record()
        results = dict(record.gate_results)
        results["reverse_semantic_readback"] = GateResult.FAIL
        decision = evaluate_establishment(replace(record, gate_results=results))
        self.assertFalse(decision.fully_established)
        self.assertEqual(EstablishmentStage.SEMANTICALLY_VERIFIED, decision.stage)
        self.assertIn("reverse_semantic_readback", decision.missing_or_failed_gates)

    def test_resilient_without_soak_is_not_fully_established(self):
        record = all_pass_record()
        results = dict(record.gate_results)
        results["sustained_soak_passed"] = GateResult.UNKNOWN
        decision = evaluate_establishment(replace(record, gate_results=results))
        self.assertFalse(decision.fully_established)
        self.assertEqual(EstablishmentStage.RESILIENT, decision.stage)

    def test_not_applicable_requires_explicit_justification(self):
        record = all_pass_record()
        results = dict(record.gate_results)
        results["owner_effect_gate_satisfied"] = GateResult.NOT_APPLICABLE
        invalid = replace(record, gate_results=results)
        decision = evaluate_establishment(invalid)
        self.assertFalse(decision.fully_established)
        self.assertIn(
            "owner_effect_gate_satisfied",
            decision.invalid_not_applicable_gates,
        )

        valid = replace(
            invalid,
            not_applicable_justifications={
                "owner_effect_gate_satisfied": "Read-only connection; no effect gate applies."
            },
        )
        self.assertTrue(evaluate_establishment(valid).fully_established)

    def test_terminal_claims_fail_closed_below_gold_standard(self):
        record = EstablishmentRecord(
            work_id="PARTIAL",
            scope="provider-cell",
            gate_results={gate: GateResult.PASS for gate in REQUIRED_GATES[:-1]},
            proof_refs=("proof:partial",),
            measured_at="2026-08-26T00:00:00+02:00",
        )
        self.assertFalse(terminal_claim_allowed(record, "COMPLETED"))
        with self.assertRaises(NotFullyEstablishedError):
            assert_terminal_claim(record, "PRODUCTION_READY")

    def test_scoped_intermediate_claims_remain_permitted(self):
        record = EstablishmentRecord(
            work_id="SOURCE-ONLY",
            scope="source",
            gate_results={"target_discovered": GateResult.PASS},
            proof_refs=("proof:source",),
            measured_at="2026-08-26T00:00:00+02:00",
        )
        self.assertTrue(terminal_claim_allowed(record, "SOURCE_READY"))
        self.assertEqual(
            "IN_PROGRESS_NOT_TERMINALLY_ACCEPTABLE",
            completion_status(record),
        )

    def test_proof_refs_and_measured_at_are_mandatory(self):
        no_proof = all_pass_record(proof_refs=())
        no_time = all_pass_record(measured_at="")
        self.assertFalse(evaluate_establishment(no_proof).fully_established)
        self.assertFalse(evaluate_establishment(no_time).fully_established)


if __name__ == "__main__":
    unittest.main()
