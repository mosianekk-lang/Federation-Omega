import unittest

from ao_harmonic_v3.failure_win_manifest import compile_receiver_manifest
from ao_harmonic_v3.failure_win_projection_contract import (
    EVENT_COLUMNS,
    PROOF_BOOLEAN_COLUMNS,
    REQUIRED_REPEATED_SUCCESSES,
    REQUIRED_SOAK_SECONDS,
    behavior_projection_formula,
    receiver_state_formula,
    truth_boundary_formula,
)


class FailureWinProjectionContractTests(unittest.TestCase):
    def test_live_behavior_formula_references_every_hard_gate(self):
        formula = behavior_projection_formula()
        self.assertIn("'Failure-Win Events v2'!H$2:H", formula)
        for key in PROOF_BOOLEAN_COLUMNS:
            column = EVENT_COLUMNS[key]
            self.assertIn(f"'Failure-Win Events v2'!{column}$2:{column}", formula)
        self.assertIn(f"repeats>={REQUIRED_REPEATED_SUCCESSES}", formula)
        self.assertIn(f"soak>={REQUIRED_SOAK_SECONDS}", formula)

    def test_live_state_formula_exposes_incomplete_raw_claim(self):
        formula = receiver_state_formula()
        self.assertIn("V2_BEHAVIOR_CLAIM_PROOF_INCOMPLETE", formula)
        self.assertIn("V2_BEHAVIOR_PROVEN", formula)
        self.assertIn("V2_INVOKED_PROOF_OPEN", formula)
        self.assertIn("'Failure-Win Events v2'!H$2:H", formula)

    def test_truth_boundary_names_complete_graph_repeat_and_soak(self):
        formula = truth_boundary_formula()
        self.assertIn("complete receiver-local proof graph", formula)
        self.assertIn("at least 3 distinct successes", formula)
        self.assertIn("at least 300 seconds soak", formula)

    def test_sovara_incomplete_claim_is_rejected_by_source_contract(self):
        registry = [{"receiver_id": "SOVARA Ω", "canonical_control": "SOVARA control", "primary_id": "sovara-id", "active": True}]
        aliases = [{"alias": "Current Chat / SOVARA", "canonical_receiver": "SOVARA Ω", "current": True}]
        event = {
            "event_id": "FWV2-CURRENT-CHAT-SOVARA-REPAIR-20260827-001",
            "timestamp": "2026-08-27T06:15:11+02:00",
            "receiver_id": "Current Chat / SOVARA",
            "kernel_version": "2.0.0",
            "kernel_invoked": True,
            "behavior_proven": True,
            "independent_readback": True,
            "current": True,
            "evidence_refs": ["source-proof-only/provider-not-attempted"],
            "failure_fact_preserved": True,
            "causal_falsification": True,
            "different_route": True,
            "vector_gate": False,
            "failure_first": False,
            "healthy_path": False,
            "rollback": False,
            "forward_canary": False,
            "semantic_readback": False,
            "positive_value": False,
            "no_regression": False,
            "no_burden_increase": False,
            "repeated_successes": 0,
            "soak_seconds": 0,
        }
        result = compile_receiver_manifest(registry, [event], generated_from="parity-regression", generated_at="2026-08-27T20:00:00+02:00", source_complete=True, receiver_alias_rows=aliases)
        self.assertFalse(result.receivers[0].behavior_proven)
        self.assertEqual(result.receivers[0].receiver_state, "V2_BEHAVIOR_CLAIM_PROOF_INCOMPLETE")

    def test_complete_event_remains_promotable(self):
        registry = [{"receiver_id": "A", "canonical_control": "A control", "primary_id": "a-id", "active": True}]
        event = {
            "event_id": "COMPLETE", "timestamp": "2026-08-27T20:00:00+02:00", "receiver_id": "A",
            "kernel_version": "2.0.0", "kernel_invoked": True, "behavior_proven": True,
            "independent_readback": True, "current": True, "evidence_refs": ["complete-proof"],
            "failure_fact_preserved": True, "causal_falsification": True, "different_route": True,
            "vector_gate": True, "failure_first": True, "healthy_path": True, "rollback": True,
            "forward_canary": True, "semantic_readback": True, "positive_value": True,
            "no_regression": True, "no_burden_increase": True, "repeated_successes": 3, "soak_seconds": 300,
        }
        result = compile_receiver_manifest(registry, [event], generated_from="parity-regression", generated_at="2026-08-27T20:00:00+02:00", source_complete=True)
        self.assertTrue(result.receivers[0].behavior_proven)
        self.assertEqual(result.receivers[0].receiver_state, "V2_BEHAVIOR_PROVEN")


if __name__ == "__main__":
    unittest.main()
