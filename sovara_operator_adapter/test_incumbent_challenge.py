import unittest

from sovara_operator_adapter.incumbent_challenge import (
    Candidate,
    ChallengeContext,
    ReflexivityError,
    challenge_incumbent,
    fitness,
    migration_gate,
    self_challenge_required,
)


def candidate(candidate_id: str, score: float, **overrides) -> Candidate:
    values = dict(
        candidate_id=candidate_id,
        mission_value=score,
        quality=score,
        reliability=score,
        latency_performance=score,
        cost_efficiency=score,
        proof_strength=score,
        reversibility=score,
        failure_domain_diversity=score,
        owner_burden_reduction=score,
        compatibility=score,
        maintainability=score,
        capability_unlock=score,
        information_gain=score,
        eligible=True,
        proof_current=True,
        authority_current=True,
        cost_known_included=True,
        independent_readback=False,
        positive_measured_value=False,
        rollback_ready=False,
        external_effect=False,
        consequential=False,
        iam_or_secret_change=False,
        destructive_change=False,
        novelty_only=False,
    )
    values.update(overrides)
    return Candidate(**values)


class IncumbentChallengeTests(unittest.TestCase):
    def test_working_incumbent_is_still_challenged_when_due(self):
        incumbent = candidate("incumbent", 0.70)
        challenger = candidate("challenger", 0.90)
        decision = challenge_incumbent(
            context=ChallengeContext("scheduler", "PERIODIC", challenge_due=True),
            incumbent=incumbent,
            challengers=[challenger],
        )
        self.assertEqual(decision.clean_slate_winner, "challenger")
        self.assertEqual(decision.serving_route, "incumbent")
        self.assertEqual(decision.verdict, "MIGRATION_CANDIDATE_PROOF_GATED")

    def test_no_trigger_keeps_incumbent_without_manufacturing_challenge(self):
        decision = challenge_incumbent(
            context=ChallengeContext("ci", "NONE"),
            incumbent=candidate("incumbent", 0.70),
            challengers=[candidate("challenger", 0.95)],
        )
        self.assertEqual(decision.verdict, "NO_CHALLENGE_DUE")
        self.assertEqual(decision.serving_route, "incumbent")

    def test_unproven_higher_theoretical_route_cannot_displace_incumbent(self):
        decision = challenge_incumbent(
            context=ChallengeContext("runtime", "NEW_PROVIDER", material_event=True),
            incumbent=candidate("proven", 0.70),
            challengers=[candidate("unproven", 0.99, proof_current=False)],
        )
        self.assertEqual(decision.clean_slate_winner, "proven")
        self.assertEqual(decision.verdict, "RETAIN_INCUMBENT_CONTINUES_TO_WIN")

    def test_novelty_is_not_a_fitness_dimension(self):
        incumbent = candidate("stable", 0.80)
        new = candidate("new", 0.75, novelty_only=True)
        self.assertGreater(fitness(incumbent), fitness(new))
        decision = challenge_incumbent(
            context=ChallengeContext("state", "FRONTIER_SHIFT", material_event=True),
            incumbent=incumbent,
            challengers=[new],
        )
        self.assertEqual(decision.clean_slate_winner, "stable")

    def test_clean_slate_winner_can_remain_provider_canary_gated(self):
        incumbent = candidate("CHATGPT_SCHEDULER", 0.62)
        gas = candidate(
            "GOOGLE_APPS_SCRIPT",
            0.91,
            independent_readback=False,
            positive_measured_value=False,
            rollback_ready=True,
        )
        decision = challenge_incumbent(
            context=ChallengeContext("LIGHTWEIGHT_CONTROL_SCHEDULER", "USER_CORRECTION", material_event=True),
            incumbent=incumbent,
            challengers=[gas],
        )
        self.assertEqual(decision.clean_slate_winner, "GOOGLE_APPS_SCRIPT")
        self.assertEqual(decision.verdict, "MIGRATION_CANDIDATE_PROOF_GATED")
        self.assertFalse(decision.migration_authorized)
        self.assertEqual(decision.serving_route, "CHATGPT_SCHEDULER")

    def test_proven_net_gain_can_become_migration_candidate(self):
        challenger = candidate(
            "proved",
            0.92,
            independent_readback=True,
            positive_measured_value=True,
            rollback_ready=True,
        )
        decision = challenge_incumbent(
            context=ChallengeContext("route", "SHADOW_PASS", material_event=True),
            incumbent=candidate("incumbent", 0.70),
            challengers=[challenger],
        )
        self.assertEqual(decision.verdict, "MIGRATION_CANDIDATE_PROVEN")
        self.assertTrue(decision.migration_authorized)
        self.assertEqual(decision.serving_route, "proved")

    def test_near_tie_uses_hysteresis(self):
        challenger = candidate(
            "near-tie",
            0.82,
            independent_readback=True,
            positive_measured_value=True,
            rollback_ready=True,
        )
        decision = challenge_incumbent(
            context=ChallengeContext(
                "route", "PERIODIC", challenge_due=True,
                hysteresis_margin=0.05, migration_margin=0.08,
            ),
            incumbent=candidate("incumbent", 0.79),
            challengers=[challenger],
        )
        self.assertEqual(decision.verdict, "HOLD_ANTI_CHURN_HYSTERESIS")
        self.assertFalse(decision.migration_authorized)
        self.assertEqual(decision.serving_route, "incumbent")

    def test_paid_unknown_or_authority_gated_route_cannot_auto_migrate(self):
        challenger = candidate(
            "paid-route",
            0.95,
            cost_known_included=False,
            independent_readback=True,
            positive_measured_value=True,
            rollback_ready=True,
        )
        decision = challenge_incumbent(
            context=ChallengeContext("runtime", "CAPACITY", material_event=True),
            incumbent=candidate("incumbent", 0.70),
            challengers=[challenger],
        )
        self.assertEqual(decision.clean_slate_winner, "incumbent")
        self.assertFalse(decision.migration_authorized)

    def test_external_or_iam_challenger_is_not_shadow_admissible(self):
        challenger = candidate(
            "unsafe-shadow",
            0.95,
            external_effect=True,
            iam_or_secret_change=True,
        )
        decision = challenge_incumbent(
            context=ChallengeContext("runtime", "NEW_ROUTE", material_event=True),
            incumbent=candidate("incumbent", 0.70),
            challengers=[challenger],
        )
        self.assertFalse(decision.shadow_admissible)
        self.assertFalse(decision.migration_authorized)

    def test_rollback_is_mandatory_even_after_positive_value(self):
        challenger = candidate(
            "no-rollback",
            0.93,
            independent_readback=True,
            positive_measured_value=True,
            rollback_ready=False,
        )
        ok, reasons = migration_gate(challenger)
        self.assertFalse(ok)
        self.assertIn("ROLLBACK_REQUIRED", reasons)

    def test_reflexivity_applies_to_governor_itself(self):
        self.assertTrue(self_challenge_required(governor_changed=True, architecture_changed=False))
        self.assertTrue(self_challenge_required(governor_changed=False, architecture_changed=True))
        self.assertFalse(self_challenge_required(governor_changed=False, architecture_changed=False))

    def test_deterministic_tie_breaking_uses_candidate_id(self):
        decision = challenge_incumbent(
            context=ChallengeContext("tie", "PERIODIC", challenge_due=True),
            incumbent=candidate("z-incumbent", 0.70),
            challengers=[candidate("b", 0.90), candidate("a", 0.90)],
        )
        self.assertEqual(decision.clean_slate_winner, "a")

    def test_score_contract_rejects_out_of_range_inputs(self):
        with self.assertRaises(ReflexivityError):
            candidate("bad", 1.2)


if __name__ == "__main__":
    unittest.main()
