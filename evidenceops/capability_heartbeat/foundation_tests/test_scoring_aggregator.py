from __future__ import annotations

import unittest

from evidenceops.capability_heartbeat.foundation.adapters.common import make_observation
from evidenceops.capability_heartbeat.foundation.aggregator import OnInputAggregator
from evidenceops.capability_heartbeat.foundation.contracts import BlockerCode, CapabilityStatus, RecommendationRole
from evidenceops.capability_heartbeat.foundation.errors import ContractError
from evidenceops.capability_heartbeat.foundation.policy import FlowPolicy, FlowState, apply_flow_policy, record_flow_failure
from evidenceops.capability_heartbeat.foundation.scoring import (
    coalesce_candidates,
    score_candidate,
    select_recommendations,
)

from evidenceops.capability_heartbeat.foundation_tests.helpers import MATTER, NOW, OBSERVED, OWNER, candidate, hash_of


def observation(code: str, *, owner=OWNER, matter=MATTER, confidence=9000):
    return make_observation(
        source_code="LOCAL_REPO",
        node_id="NODE-ROOT",
        owner_code=owner,
        matter_code=matter,
        capability_code=code,
        status=CapabilityStatus.AVAILABLE,
        confidence_bp=confidence,
        freshness_seconds=10,
        evidence_count=3,
        blocker_code=BlockerCode.NONE,
        observed_at=OBSERVED,
        semantic_value={"head_hash": hash_of(code), "reference_code": "DETACHED"},
    )


class ScoringTests(unittest.TestCase):
    def test_score_is_deterministic(self):
        item = candidate("CAPABILITY-A")
        self.assertEqual(score_candidate(item), score_candidate(item))
        self.assertEqual(score_candidate(item), 10640)

    def test_incompatible_and_unavailable_score_zero(self):
        self.assertEqual(score_candidate(candidate("CAP-A", compatible=False)), 0)
        self.assertEqual(
            score_candidate(candidate("CAP-B", status=CapabilityStatus.UNAVAILABLE)),
            0,
        )

    def test_no_output_without_useful_recommendation(self):
        result = select_recommendations((candidate("CAP-A", confidence=1000),))
        self.assertEqual(result, ())

    def test_preferred_backup_escalation_bound(self):
        result = select_recommendations(
            (
                candidate("CAP-A", confidence=9000),
                candidate("CAP-B", confidence=8000),
                candidate(
                    "CAP-C",
                    confidence=0,
                    status=CapabilityStatus.UNAVAILABLE,
                    blocker=BlockerCode.AUTHORITY_UNAVAILABLE,
                ),
            )
        )
        self.assertEqual(tuple(item.role for item in result), (
            RecommendationRole.PREFERRED,
            RecommendationRole.BACKUP,
            RecommendationRole.ESCALATION,
        ))
        self.assertEqual(len(result), 3)

    def test_stable_tie_break_uses_capability_code(self):
        result = select_recommendations((candidate("CAP-B"), candidate("CAP-A")))
        self.assertEqual(result[0].capability_code, "CAP-A")

    def test_coalescing_keeps_stronger_duplicate(self):
        result = coalesce_candidates((candidate("CAP-A", 7000), candidate("CAP-A", 9000)))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].confidence_bp, 9000)


class AggregatorAndFlowTests(unittest.TestCase):
    def test_single_on_input_aggregates(self):
        result = OnInputAggregator().on_input(
            observations=(observation("CAP-A"), observation("CAP-B", confidence=8000)),
            owner_code=OWNER,
            matter_code=MATTER,
            now=NOW,
        )
        self.assertTrue(result.has_output)
        self.assertEqual(result.observed_count, 2)
        self.assertEqual(result.suppressed_reason, "NONE")

    def test_empty_input_produces_no_output(self):
        result = OnInputAggregator().on_input(
            observations=(), owner_code=OWNER, matter_code=MATTER, now=NOW
        )
        self.assertFalse(result.has_output)

    def test_cross_owner_and_matter_bleed_rejected(self):
        for item in (
            observation("CAP-A", owner="OWNER-D4E5F6A7"),
            observation("CAP-A", matter="MATTER-E4F5A6B7"),
        ):
            with self.subTest(item=item), self.assertRaisesRegex(ContractError, "CROSS_OWNER"):
                OnInputAggregator().on_input(
                    observations=(item,), owner_code=OWNER, matter_code=MATTER, now=NOW
                )

    def test_rate_limit_suppresses_cycle(self):
        decision = apply_flow_policy(
            candidates=(candidate("CAP-A"),),
            now=NOW,
            policy=FlowPolicy(minimum_interval_seconds=30),
            state=FlowState(last_input_at="2026-08-02T12:00:00Z"),
        )
        self.assertEqual(decision.candidates, ())
        self.assertEqual(decision.suppressed_reason, "RATE_LIMITED")

    def test_circuit_breaker_opens_and_suppresses(self):
        policy = FlowPolicy(failure_threshold=2, circuit_open_seconds=60)
        state = record_flow_failure(now=NOW, policy=policy, state=FlowState())
        state = record_flow_failure(now=NOW, policy=policy, state=state)
        decision = apply_flow_policy(
            candidates=(candidate("CAP-A"),),
            now="2026-08-02T12:00:20Z",
            policy=policy,
            state=state,
        )
        self.assertEqual(decision.suppressed_reason, "CIRCUIT_OPEN")


if __name__ == "__main__":
    unittest.main()
