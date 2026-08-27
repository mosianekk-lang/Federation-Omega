import unittest

from ao_harmonic_v3.failure_win_v2 import (
    FailureEventType,
    FailureObservation,
    FailureToOperationalWinKernelV2,
    FailureWinRequest,
    FailureWinState,
    RecoveryRoute,
)
from ao_harmonic_v3.models import PerformanceVector
from evidenceops.lex_omega.test_lex_omega_adversarial_boundary import (
    test_future_effective_authority_fails_closed,
    test_missing_source_pinpoint_is_rejected_at_construction,
    test_multi_authority_partial_support_fails_closed,
    test_proposition_text_mutation_fails_closed,
    test_proposed_amendment_source_must_not_be_current_law_without_in_force_proof,
    test_stale_authority_fails_closed,
    test_support_key_substitution_fails_closed,
    test_superseded_authority_fails_closed,
    test_unrelated_nonblank_pinpoint_must_not_satisfy_support_binding,
)


class LexOmegaAdversarialBoundaryAirlockTests(unittest.TestCase):
    def test_01_support_key_substitution_fails_closed(self):
        test_support_key_substitution_fails_closed()

    def test_02_proposition_text_mutation_fails_closed(self):
        test_proposition_text_mutation_fails_closed()

    def test_03_missing_source_pinpoint_fails_closed(self):
        test_missing_source_pinpoint_is_rejected_at_construction()

    def test_04_unrelated_nonblank_pinpoint_fails_closed(self):
        test_unrelated_nonblank_pinpoint_must_not_satisfy_support_binding()

    def test_05_stale_authority_fails_closed(self):
        test_stale_authority_fails_closed()

    def test_06_superseded_authority_fails_closed(self):
        test_superseded_authority_fails_closed()

    def test_07_future_effective_authority_fails_closed(self):
        test_future_effective_authority_fails_closed()

    def test_08_proposed_amendment_without_in_force_proof_fails_closed(self):
        test_proposed_amendment_source_must_not_be_current_law_without_in_force_proof()

    def test_09_multi_authority_partial_support_fails_closed(self):
        test_multi_authority_partial_support_fails_closed()

    def test_10_failure_win_v2_lex_receiver_canary_preserves_authority_boundary(self):
        # Native Lex boundary first: stale authority must remain fail-closed.
        test_stale_authority_fails_closed()

        incumbent = PerformanceVector(quality=9, reliability=8, proof=9, speed=2, owner_burden=1)
        candidate = PerformanceVector(
            quality=9,
            reliability=8,
            proof=9,
            speed=5,
            owner_time_recovered=2,
            recovery_gain=2,
            owner_burden=0,
        )
        route_id = "lex-current-authority-validation-fixture"
        result = FailureToOperationalWinKernelV2().evaluate(
            FailureWinRequest(
                observation=FailureObservation(
                    event_id="FWV2-LEX-PRECURSOR-CANARY",
                    event_type=FailureEventType.PRECURSOR_RISK,
                    system_id="Lex Advocate",
                    objective="preempt a synthetic legal-authority staleness risk",
                    claim="an authority binding may become stale before reliance",
                    observed_fruit="synthetic adversarial boundary only; no legal/provider effect",
                    desired_outcome="prewarm a current source/pinpoint/authority validation route",
                    failure_code="SYNTHETIC_LEX_AUTHORITY_DRIFT",
                    material=False,
                    precursor_signals=("stale-authority-fixture", "pinpoint-fixture"),
                ),
                incumbent=incumbent,
                routes=(
                    RecoveryRoute(
                        route_id=route_id,
                        route_type="REROUTE",
                        performance=candidate,
                        proof_strength=1.0,
                        reversibility=1.0,
                        strategic_value=1.0,
                        expected_value=2.0,
                    ),
                ),
            )
        )
        self.assertEqual(FailureWinState.PREEMPTION_READY, result.state)
        self.assertTrue(result.vector_gate_passed)
        self.assertIn(route_id, result.selected_route_ids)
        self.assertFalse(result.proof_graph.complete)
        self.assertNotEqual(FailureWinState.OPERATIONAL_WIN_VERIFIED, result.state)


if __name__ == "__main__":
    unittest.main()
