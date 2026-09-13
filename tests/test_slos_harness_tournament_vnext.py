from __future__ import annotations

import unittest

from superior_logic.harness_tournament import (
    HarnessExperimentCompiler,
    HarnessGenome,
    HarnessOutcome,
    HarnessTournament,
)


class HarnessTournamentTests(unittest.TestCase):
    def genome(self, model: str, aci: str):
        return HarnessGenome.create(
            model_ref=model,
            aci_profile=aci,
            context_policy="CTX-V1",
            skills=("repo-debug",),
            tools=("git", "python"),
            workspace_policy="PREPARED",
            fleet_shape="DIRECT",
            verifier_profile="SUPERCOURT-HIGH",
        )

    def outcome(self, gid: str, *, accepted: float, readback: float, regression: float,
                seconds: float, cost: float, owner: float, tools: float,
                outcome_value: float = 1.0, comparison_fingerprint: str = "cohort-v1"):
        return HarnessOutcome(
            genome_id=gid,
            task_set_id="tasks-v1",
            acceptance_hash="accept-v1",
            comparison_fingerprint=comparison_fingerprint,
            sample_size=20,
            accepted_task_rate=accepted,
            verified_readback_rate=readback,
            regression_escape_rate=regression,
            median_wall_seconds=seconds,
            median_cost=cost,
            owner_interventions=owner,
            tool_round_trips=tools,
            outcome_value=outcome_value,
            evidence_refs=(f"proof:{gid}",),
        )

    def test_harness_genome_is_deterministic(self):
        a = self.genome("model-a", "terminal-v1")
        b = self.genome("model-a", "terminal-v1")
        self.assertEqual(a.genome_id, b.genome_id)

    def test_experiment_compiler_separates_candidate_identity_from_common_cohort(self):
        a = self.genome("model-a", "terminal-v1")
        b = self.genome("model-a", "terminal-v2")
        common = dict(
            source_sha256="source",
            inputs={"task_set": "tasks-v1"},
            environment={"python": "3.13"},
            observation_window="2026-09-13",
            cost_latency_context={"currency": "USD"},
            controls={"acceptance_hash": "accept-v1"},
            authority={"ceiling": "A1_INTERNAL"},
        )
        exp_a = HarnessExperimentCompiler.compile(a, implementation_sha256="impl-a", **common)
        exp_b = HarnessExperimentCompiler.compile(b, implementation_sha256="impl-b", **common)
        self.assertNotEqual(exp_a.fingerprint, exp_b.fingerprint)
        self.assertEqual(exp_a.comparison_fingerprint, exp_b.comparison_fingerprint)

    def test_value_receipt_keeps_outcome_value_separate_from_latency(self):
        genome = self.genome("model-a", "terminal-v1")
        outcome = self.outcome(
            genome.genome_id,
            accepted=.9,
            readback=.9,
            regression=.01,
            seconds=200,
            cost=1,
            owner=.5,
            tools=5,
            outcome_value=.8,
        )
        receipt = outcome.value_receipt()
        self.assertEqual(receipt.outcome_value, .8)
        self.assertEqual(receipt.latency_ms, 200000)

    def test_negative_outcome_value_fails_closed(self):
        genome = self.genome("model-a", "terminal-v1")
        outcome = self.outcome(
            genome.genome_id,
            accepted=.9,
            readback=.9,
            regression=.01,
            seconds=100,
            cost=1,
            owner=.5,
            tools=5,
            outcome_value=-.1,
        )
        with self.assertRaisesRegex(ValueError, "NEGATIVE_BURDEN_OR_VALUE"):
            outcome.validate()

    def test_comparison_cohort_mismatch_is_not_comparable(self):
        incumbent = self.genome("model-a", "terminal-v1")
        challenger = self.genome("model-a", "terminal-v2")
        outcomes = (
            self.outcome(incumbent.genome_id, accepted=.9, readback=.9, regression=.01, seconds=100, cost=2, owner=1, tools=10, comparison_fingerprint="cohort-a"),
            self.outcome(challenger.genome_id, accepted=.95, readback=.95, regression=.01, seconds=60, cost=1, owner=.5, tools=6, comparison_fingerprint="cohort-b"),
        )
        verdict = HarnessTournament().compare(
            outcomes,
            incumbent_genome_id=incumbent.genome_id,
            minimum_quality=.7,
            minimum_reliability=.7,
        )
        self.assertFalse(verdict.comparable)
        self.assertEqual(verdict.reason, "EXPERIMENT_IDENTITY_MISMATCH")

    def test_unique_pareto_winner_advances_without_quality_regression(self):
        incumbent = self.genome("model-a", "terminal-v1")
        challenger = self.genome("model-a", "terminal-v2")
        outcomes = (
            self.outcome(incumbent.genome_id, accepted=.90, readback=.90, regression=.02, seconds=100, cost=2, owner=1, tools=10, outcome_value=.8),
            self.outcome(challenger.genome_id, accepted=.95, readback=.95, regression=.01, seconds=60, cost=1, owner=.5, tools=6, outcome_value=.9),
        )
        verdict = HarnessTournament().compare(
            outcomes,
            incumbent_genome_id=incumbent.genome_id,
            minimum_quality=.7,
            minimum_reliability=.7,
        )
        self.assertEqual(verdict.pareto_ids, (challenger.genome_id,))
        self.assertEqual(verdict.reason, "UNIQUE_PARETO_WINNER")

    def test_quality_regression_is_removed_before_pareto_selection(self):
        incumbent = self.genome("model-a", "terminal-v1")
        challenger = self.genome("model-a", "terminal-v2")
        outcomes = (
            self.outcome(incumbent.genome_id, accepted=.90, readback=.90, regression=.01, seconds=100, cost=2, owner=1, tools=10, outcome_value=.8),
            self.outcome(challenger.genome_id, accepted=.80, readback=.95, regression=.01, seconds=10, cost=.1, owner=0, tools=1, outcome_value=1.0),
        )
        verdict = HarnessTournament().compare(
            outcomes,
            incumbent_genome_id=incumbent.genome_id,
            minimum_quality=.6,
            minimum_reliability=.6,
        )
        self.assertIn(challenger.genome_id, verdict.hard_regressions)
        self.assertEqual(verdict.pareto_ids, (incumbent.genome_id,))


if __name__ == "__main__":
    unittest.main()
