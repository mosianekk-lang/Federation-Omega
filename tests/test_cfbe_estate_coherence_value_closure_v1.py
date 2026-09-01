from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.estate_coherence_value_closure_v1 import (
    ActionKind,
    CapabilityDecision,
    CapabilityProposal,
    OwnerValueState,
    PRDisposition,
    ProjectionState,
    PullRequestObservation,
    SurfaceObservation,
    benchmark_score,
    classify_pr,
    classify_surface,
    decide_capability,
    reconcile_estate,
)

MAIN = "a" * 40
OLD = "b" * 40


class EstateCoherenceValueClosureTests(unittest.TestCase):
    def surface(self, **overrides):
        data = {
            "surface_id": "KDV_CURRENT",
            "owner": "Kim Dataverse",
            "lifecycle": "CURRENT",
            "requires_current_source": True,
            "observed_source_sha": MAIN,
            "observed_at_sast": "2026-09-01T05:00:00+02:00",
            "ttl_seconds": 900,
            "proof_refs": ["provider:readback"],
        }
        data.update(overrides)
        return SurfaceObservation.from_mapping(data)

    def pr(self, **overrides):
        data = {
            "pr_number": 100,
            "title": "candidate",
            "base_sha": OLD,
            "head_sha": MAIN,
            "commits_behind_main": 0,
            "unique_capability": True,
            "proof_refs": ["github:pr/100"],
        }
        data.update(overrides)
        return PullRequestObservation.from_mapping(data)

    def proposal(self, **overrides):
        data = {
            "proposal_id": "CAP-X",
            "gap_id": "GAP-X",
            "gap_severity": 4,
            "existing_capability_coverage": 0.0,
            "composable_existing_capabilities": 0,
            "measurable_owner_value_hypothesis": True,
            "architectural_need_for_new_top_level_system": False,
        }
        data.update(overrides)
        return CapabilityProposal.from_mapping(data)

    def test_current_surface(self):
        self.assertEqual(
            ProjectionState.CURRENT,
            classify_surface(self.surface(), current_main_sha=MAIN, now_sast="2026-09-01T05:05:00+02:00"),
        )

    def test_drifted_surface(self):
        self.assertEqual(
            ProjectionState.DRIFTED,
            classify_surface(self.surface(observed_source_sha=OLD), current_main_sha=MAIN, now_sast="2026-09-01T05:05:00+02:00"),
        )

    def test_stale_surface_precedes_drift(self):
        self.assertEqual(
            ProjectionState.STALE,
            classify_surface(
                self.surface(observed_source_sha=OLD, observed_at_sast="2026-09-01T04:00:00+02:00", ttl_seconds=300),
                current_main_sha=MAIN,
                now_sast="2026-09-01T05:05:00+02:00",
            ),
        )

    def test_historical_surface_is_not_forced_current(self):
        self.assertEqual(
            ProjectionState.HISTORICAL,
            classify_surface(self.surface(intentionally_historical=True, observed_source_sha=OLD), current_main_sha=MAIN, now_sast="2026-09-01T05:05:00+02:00"),
        )

    def test_superseded_surface(self):
        self.assertEqual(
            ProjectionState.SUPERSEDED,
            classify_surface(self.surface(superseded_by="NEW_SURFACE"), current_main_sha=MAIN, now_sast="2026-09-01T05:05:00+02:00"),
        )

    def test_pr_unique_stale_restack(self):
        self.assertEqual(PRDisposition.RESTACK, classify_pr(self.pr(commits_behind_main=20)))

    def test_pr_duplicate_closes_even_if_green(self):
        self.assertEqual(PRDisposition.CLOSE, classify_pr(self.pr(semantic_duplicate=True, exact_head_green=True)))

    def test_pr_provider_gate_holds(self):
        self.assertEqual(PRDisposition.HOLD, classify_pr(self.pr(provider_or_effect_gate_open=True)))

    def test_pr_low_value_very_stale_closes(self):
        self.assertEqual(PRDisposition.CLOSE, classify_pr(self.pr(commits_behind_main=50, unique_capability=False)))

    def test_reuse_wins_before_new(self):
        self.assertEqual(
            CapabilityDecision.REUSE,
            decide_capability(self.proposal(existing_capability_coverage=0.9), owner_value=OwnerValueState(0, False)),
        )

    def test_extend_existing_capability(self):
        self.assertEqual(
            CapabilityDecision.EXTEND,
            decide_capability(self.proposal(existing_capability_coverage=0.6), owner_value=OwnerValueState(0, False)),
        )

    def test_merge_composable_capabilities(self):
        self.assertEqual(
            CapabilityDecision.MERGE,
            decide_capability(self.proposal(existing_capability_coverage=0.1, composable_existing_capabilities=3), owner_value=OwnerValueState(0, False)),
        )

    def test_new_top_level_system_blocked_without_owner_value(self):
        self.assertEqual(
            CapabilityDecision.HOLD,
            decide_capability(self.proposal(architectural_need_for_new_top_level_system=True), owner_value=OwnerValueState(0, False)),
        )

    def test_new_top_level_system_requires_strict_owner_value(self):
        self.assertEqual(
            CapabilityDecision.NEW,
            decide_capability(self.proposal(architectural_need_for_new_top_level_system=True), owner_value=OwnerValueState(10, True)),
        )

    def test_value_hypothesis_required(self):
        self.assertEqual(
            CapabilityDecision.HOLD,
            decide_capability(self.proposal(measurable_owner_value_hypothesis=False), owner_value=OwnerValueState(10, True)),
        )

    def test_generation_fence_rejects_replay(self):
        with self.assertRaisesRegex(ValueError, "GENERATION_FENCE"):
            reconcile_estate(
                generation=4,
                previous_generation=4,
                source_main_sha=MAIN,
                observed_at_sast="2026-09-01T05:05:00+02:00",
            )

    def test_reconcile_prioritizes_projection_and_owner_value(self):
        receipt = reconcile_estate(
            generation=5,
            previous_generation=4,
            source_main_sha=MAIN,
            observed_at_sast="2026-09-01T05:05:00+02:00",
            surfaces=[{
                "surface_id": "KDV_CURRENT",
                "owner": "KDV",
                "lifecycle": "CURRENT",
                "requires_current_source": True,
                "observed_source_sha": OLD,
                "observed_at_sast": "2026-09-01T05:00:00+02:00",
                "proof_refs": ["gdrive:read"],
            }],
            owner_value_state={"observed_pair_count": 0},
        )
        self.assertEqual(1, receipt.metrics.drifted_surfaces)
        self.assertEqual(10, receipt.metrics.owner_value_pair_deficit)
        self.assertEqual(ActionKind.RECONCILE_PROJECTION, receipt.actions[0].kind)
        self.assertEqual(ActionKind.COLLECT_OWNER_VALUE, receipt.actions[1].kind)
        self.assertFalse(receipt.stable_promotion_authorized)
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertFalse(receipt.external_effect)

    def test_deterministic_receipt_hash(self):
        kwargs = dict(
            generation=5,
            previous_generation=4,
            source_main_sha=MAIN,
            observed_at_sast="2026-09-01T05:05:00+02:00",
            surfaces=[],
            pull_requests=[],
            capability_proposals=[],
            owner_value_state={"observed_pair_count": 0},
        )
        one = reconcile_estate(**kwargs)
        two = reconcile_estate(**kwargs)
        self.assertEqual(one.receipt_sha256, two.receipt_sha256)
        self.assertEqual(one.to_dict(), two.to_dict())

    def test_benchmark_target_exceeds_baseline(self):
        score = benchmark_score()
        self.assertGreater(score["target_percent"], score["baseline_percent"])
        self.assertGreaterEqual(score["target_percent"], 90.0)

    def test_owner_value_pair_count_alone_does_not_prove_value(self):
        receipt = reconcile_estate(
            generation=2,
            previous_generation=1,
            source_main_sha=MAIN,
            observed_at_sast="2026-09-01T05:05:00+02:00",
            owner_value_state={"observed_pair_count": 10, "strict_owner_value_court_verified": False},
        )
        self.assertFalse(receipt.owner_value_proven)
        self.assertTrue(any(action.kind is ActionKind.COLLECT_OWNER_VALUE for action in receipt.actions))

    def test_strict_owner_value_closes_collection_action(self):
        receipt = reconcile_estate(
            generation=2,
            previous_generation=1,
            source_main_sha=MAIN,
            observed_at_sast="2026-09-01T05:05:00+02:00",
            owner_value_state={"observed_pair_count": 10, "strict_owner_value_court_verified": True},
        )
        self.assertTrue(receipt.owner_value_proven)
        self.assertFalse(any(action.kind is ActionKind.COLLECT_OWNER_VALUE for action in receipt.actions))

    def test_mixed_reconciliation_plan(self):
        receipt = reconcile_estate(
            generation=8,
            previous_generation=7,
            source_main_sha=MAIN,
            observed_at_sast="2026-09-01T05:05:00+02:00",
            surfaces=[
                {"surface_id": "KDV", "owner": "KDV", "lifecycle": "CURRENT", "requires_current_source": True, "observed_source_sha": OLD, "observed_at_sast": "2026-09-01T05:00:00+02:00"},
                {"surface_id": "OLD_INDEX", "owner": "KDV", "lifecycle": "HISTORICAL", "requires_current_source": False, "observed_source_sha": OLD, "observed_at_sast": "2026-08-01T05:00:00+02:00", "intentionally_historical": True},
            ],
            pull_requests=[
                {"pr_number": 1, "title": "unique stale", "base_sha": OLD, "head_sha": MAIN, "commits_behind_main": 20, "unique_capability": True},
                {"pr_number": 2, "title": "duplicate", "base_sha": OLD, "head_sha": MAIN, "commits_behind_main": 4, "unique_capability": False, "semantic_duplicate": True},
            ],
            capability_proposals=[
                {"proposal_id": "USE_EXISTING", "gap_id": "G1", "gap_severity": 4, "existing_capability_coverage": 0.95, "composable_existing_capabilities": 1, "measurable_owner_value_hypothesis": True}
            ],
            owner_value_state={"observed_pair_count": 0},
        )
        kinds = {action.kind for action in receipt.actions}
        self.assertIn(ActionKind.RECONCILE_PROJECTION, kinds)
        self.assertIn(ActionKind.MARK_HISTORICAL, kinds)
        self.assertIn(ActionKind.RESTACK_PR, kinds)
        self.assertIn(ActionKind.CLOSE_PR, kinds)
        self.assertIn(ActionKind.REUSE_CAPABILITY, kinds)
        self.assertIn(ActionKind.COLLECT_OWNER_VALUE, kinds)


if __name__ == "__main__":
    unittest.main()
