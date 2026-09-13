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
                seconds: float, cost: float, owner: float, tools: float):
        return HarnessOutcome(
            genome_id=gid,
            task_set_id="tasks-v1",
            acceptance_hash="accept-v1",
            sample_size=20,
            accepted_task_rate=accepted,
            verified_readback_rate=readback,
            regression_escape_rate=regression,
            median_wall_seconds=seconds,
            median_cost=cost,
            owner_interventions=owner,
            tool_round_trips=tools,
            evidence_refs=(f"proof:{gid}",),
        )

    def test_harness_genome_is_deterministic(self):
        a = self.genome("model-a", "terminal-v1")
        b = self.genome("model-a", "terminal-v1")
        self.assertEqual(a.genome_id, b.genome_id)

    def test_experiment_compiler_binds_harness_parameters(self):
        genome = self.genome("model-a", "terminal-v1")
        exp = HarnessExperimentCompiler.compile(
            genome,
            implementation_sha256="impl",
            source_sha256="source",
            inputs={"task_set": "tasks-v1"},
            environment={"python": "3.13"},
            observation_window="2026-09-13",
            cost_latency_context={"currency": "USD"},
            controls={"acceptance_hash": "accept-v1"},
            authority={"ceiling": "A1_INTERNAL"},
        )
        self.assertTrue(exp.fingerprint)

    def test_unique_pareto_winner_advances_without_quality_regression(self):
        incumbent = self.genome("model-a", "terminal-v1")
        challenger = self.genome("model-a", "terminal-v2")
        outcomes = (
            self.outcome(incumbent.genome_id, accepted=.90, readback=.90, regression=.02, seconds=100, cost=2, owner=1, tools=10),
            self.outcome(challenger.genome_id, accepted=.95, readback=.95, regression=.01, seconds=60, cost=1, owner=.5, tools=6),
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
            self.outcome(incumbent.genome_id, accepted=.90, readback=.90, regression=.01, seconds=100, cost=2, owner=1, tools=10),
            self.outcome(challenger.genome_id, accepted=.80, readback=.95, regression=.01, seconds=10, cost=.1, owner=0, tools=1),
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
