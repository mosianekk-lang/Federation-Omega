from __future__ import annotations

import unittest

from superior_logic.context_tournament import (
    ContextCandidate,
    ContextOutcome,
    ContextPolicyCourt,
    ContextTournament,
)


class ContextTournamentTests(unittest.TestCase):
    def candidate(self, cid: str, tokens: int, relevance: float, uniqueness: float = .5, revision: str = "abc123"):
        return ContextCandidate(
            candidate_id=cid,
            source_class="REPOGRAPH",
            source_ref=f"repo:{cid}",
            revision=revision,
            token_cost=tokens,
            relevance=relevance,
            uniqueness=uniqueness,
            proof_strength=.9,
            freshness=1.0,
            evidence_refs=(f"proof:{cid}",),
        )

    def outcome(self, policy: str, *, task_set: str = "tasks", acceptance: str = "accept",
                cohort: str = "cohort-v1", sample: int = 20, accepted: float = .9,
                readback: float = .9, regression: float = 0.0, tokens: float = 1000,
                seconds: float = 10):
        return ContextOutcome(
            policy,
            task_set,
            acceptance,
            cohort,
            sample,
            accepted,
            readback,
            regression,
            tokens,
            seconds,
            (f"proof:{policy}",),
        )

    def test_budgeted_selection_is_deterministic(self):
        candidates = (
            self.candidate("a", 400, .9),
            self.candidate("b", 600, .8),
            self.candidate("c", 800, .4),
        )
        engine = ContextTournament()
        first = engine.select(candidates, token_budget=1000)
        second = engine.select(tuple(reversed(candidates)), token_budget=1000)
        self.assertEqual(first.selected_ids, ("a", "b"))
        self.assertEqual(first.selection_sha256, second.selection_sha256)
        self.assertLessEqual(first.total_tokens, 1000)

    def test_context_revision_is_required(self):
        with self.assertRaisesRegex(ValueError, "CONTEXT_IDENTITY_REQUIRED"):
            self.candidate("a", 100, .9, revision="").validate()

    def test_mandatory_context_fails_closed_when_budget_too_small(self):
        with self.assertRaisesRegex(ValueError, "MANDATORY_CONTEXT_EXCEEDS_BUDGET"):
            ContextTournament().select(
                (self.candidate("root", 800, .9),),
                token_budget=400,
                mandatory_ids=("root",),
            )

    def test_mandatory_context_fails_closed_when_item_limit_too_small(self):
        candidates = (self.candidate("a", 100, .9), self.candidate("b", 100, .8))
        with self.assertRaisesRegex(ValueError, "MANDATORY_CONTEXT_EXCEEDS_ITEM_LIMIT"):
            ContextTournament().select(
                candidates,
                token_budget=1000,
                mandatory_ids=("a", "b"),
                max_items=1,
            )

    def test_quality_regression_blocks_context_challenger(self):
        incumbent = self.outcome("inc", accepted=.9, readback=.95, regression=.01, tokens=10000, seconds=100)
        challenger = self.outcome("new", accepted=.85, readback=.95, regression=.01, tokens=4000, seconds=60)
        verdict = ContextPolicyCourt().compare(incumbent, challenger)
        self.assertEqual(verdict.winner, "inc")
        self.assertTrue(verdict.quality_regression)

    def test_identity_mismatch_is_not_comparable(self):
        incumbent = self.outcome("inc", task_set="tasks-a")
        challenger = self.outcome("new", task_set="tasks-b", tokens=500, seconds=9)
        verdict = ContextPolicyCourt().compare(incumbent, challenger)
        self.assertFalse(verdict.comparable)
        self.assertEqual(verdict.reason, "EXPERIMENT_IDENTITY_MISMATCH")

    def test_comparison_cohort_mismatch_is_not_comparable(self):
        incumbent = self.outcome("inc", cohort="cohort-a")
        challenger = self.outcome("new", cohort="cohort-b", tokens=500, seconds=9)
        verdict = ContextPolicyCourt().compare(incumbent, challenger)
        self.assertFalse(verdict.comparable)
        self.assertEqual(verdict.reason, "EXPERIMENT_IDENTITY_MISMATCH")

    def test_challenger_must_be_pareto_better_on_context_and_velocity(self):
        incumbent = self.outcome("inc", tokens=1000, seconds=10)
        challenger = self.outcome("new", tokens=500, seconds=9)
        verdict = ContextPolicyCourt().compare(incumbent, challenger)
        self.assertEqual(verdict.winner, "new")
        self.assertEqual(verdict.reason, "CHALLENGER_ADVANCES")

    def test_efficiency_tradeoff_does_not_create_false_winner(self):
        incumbent = self.outcome("inc", tokens=1000, seconds=10)
        challenger = self.outcome("new", tokens=500, seconds=30)
        verdict = ContextPolicyCourt().compare(incumbent, challenger)
        self.assertIsNone(verdict.winner)
        self.assertEqual(verdict.reason, "PARETO_TRADEOFF")


if __name__ == "__main__":
    unittest.main()
