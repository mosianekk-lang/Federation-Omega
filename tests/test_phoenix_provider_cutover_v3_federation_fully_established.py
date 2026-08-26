import unittest
from dataclasses import replace

from ops.federation_fully_established import (
    EstablishmentStage,
    GateResult,
    NotFullyEstablishedError,
    all_pass_record,
    assert_terminal_claim,
    evaluate_establishment,
)


class FederationFullyEstablishedAirlockBridgeTests(unittest.TestCase):
    def test_no_terminal_completion_below_fully_established(self):
        record = all_pass_record()
        results = dict(record.gate_results)
        results["rollback_proven"] = GateResult.FAIL
        partial = replace(record, gate_results=results)
        with self.assertRaises(NotFullyEstablishedError):
            assert_terminal_claim(partial, "DONE")

    def test_bidirectional_transport_is_not_the_gold_standard(self):
        record = all_pass_record()
        results = dict(record.gate_results)
        for gate in (
            "monitoring_active",
            "freshness_lease_active",
            "idempotency_proven",
            "duplicate_effect_suppression_proven",
            "retry_dlq_replay_proven",
            "failure_isolation_proven",
            "missed_run_recovery_proven",
            "rollback_proven",
            "sustained_soak_passed",
            "zero_critical_regressions",
            "jarvis_assurance_passed",
            "cfbe_benchmark_passed",
            "sentinel_observation_current",
            "canonical_state_synchronized",
            "owner_effect_gate_satisfied",
        ):
            results[gate] = GateResult.UNKNOWN
        decision = evaluate_establishment(replace(record, gate_results=results))
        self.assertEqual(EstablishmentStage.BIDIRECTIONAL, decision.stage)
        self.assertFalse(decision.fully_established)

    def test_all_required_gates_reach_fully_established(self):
        decision = assert_terminal_claim(all_pass_record(), "COMPLETED")
        self.assertTrue(decision.fully_established)
        self.assertEqual(EstablishmentStage.FULLY_ESTABLISHED, decision.stage)


if __name__ == "__main__":
    unittest.main()
