from __future__ import annotations

import unittest

from superior_logic.context_tournament import (
    ContextCandidate,
    ContextOutcome,
    ContextPolicyCourt,
    ContextTournament,
)


class ContextTournamentTests(unittest.TestCase):
    def candidate(self, cid: str, tokens: int, relevance: float, uniqueness: float = .5):
        return ContextCandidate(
            candidate_id=cid,
            source_class="REPOGRAPH",
            source_ref=f"repo:{cid}",
            revision="abc123",
            token_cost=tokens,
            relevance=relevance,
            uniqueness=uniqueness,
            proof_strength=.9,
            freshness=1.0,
            evidence_refs=(f"proof:{cid}",),
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

    def test_mandatory_context_fails_closed_when_budget_too_small(self):
        with self.assertRaisesRegex(ValueError, "MANDATORY_CONTEXT_EXCEEDS_BUDGET"):
            ContextTournament().select(
                (self.candidate("root", 800, .9),),
                token_budget=400,
                mandatory_ids=("root",),
            )

    def test_quality_regression_blocks_context_challenger(self):
        incumbent = ContextOutcome("inc", "tasks", "accept", 20, .9, .95, .01, 10000, 100, ("i",))
        challenger = ContextOutcome("new", "tasks", "accept", 20, .85, .95, .01, 4000, 60, ("c",))
        verdict = ContextPolicyCourt().compare(incumbent, challenger)
        self.assertEqual(verdict.winner, "inc")
        self.assertTrue(verdict.quality_regression)

    def test_identity_mismatch_is_not_comparable(self):
        incumbent = ContextOutcome("inc", "tasks-a", "accept", 20, .9, .9, .0, 1000, 10, ("i",))
        challenger = ContextOutcome("new", "tasks-b", "accept", 20, .9, .9, .0, 500, 9, ("c",))
        verdict = ContextPolicyCourt().compare(incumbent, challenger)
        self.assertFalse(verdict.comparable)
        self.assertEqual(verdict.reason, "EXPERIMENT_IDENTITY_MISMATCH")


if __name__ == "__main__":
    unittest.main()
