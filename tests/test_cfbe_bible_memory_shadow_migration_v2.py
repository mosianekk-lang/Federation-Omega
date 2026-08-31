from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.bible_memory_fabric_v1 import ProjectionCompiler
from benchmarking.cfbe_omega.bible_memory_shadow_migration_v2 import (
    LEGACY_CURRENT_STATE,
    STREAM_ID,
    build_store,
    run_shadow_campaign,
    workstream_events,
)


class CFBEBibleMemoryShadowMigrationV2Tests(unittest.TestCase):
    def test_second_domain_campaign_is_exactly_30_of_30(self) -> None:
        report = run_shadow_campaign()
        self.assertEqual(30, report.pair_count)
        self.assertEqual(30, report.pass_count)
        self.assertEqual(0, report.hard_failure_count)
        self.assertEqual("SECOND_DOMAIN_SHADOW_PASS", report.promotion_state)

    def test_current_projection_matches_result_index_current_truth(self) -> None:
        projection = ProjectionCompiler().project(build_store().stream(STREAM_ID))
        self.assertEqual(LEGACY_CURRENT_STATE, projection.current)
        self.assertEqual(
            {"result-index-evt-0001", "result-index-evt-0003", "result-index-evt-0005"},
            set(projection.superseded_event_ids),
        )

    def test_as_of_queries_preserve_stale_candidate_and_narrow_recovery(self) -> None:
        events = workstream_events()
        compiler = ProjectionCompiler()
        stale = compiler.project(events, as_of_recorded_at="2026-08-31T18:57:49Z")
        broad = compiler.project(events, as_of_recorded_at="2026-08-31T19:17:34Z")
        recovered = compiler.project(events, as_of_recorded_at="2026-08-31T19:43:40Z")
        self.assertEqual("STALE_BASE_CANDIDATE_BLOCKED", stale.current["index_state"])
        self.assertEqual(906, broad.current["candidate_pr"])
        self.assertEqual(909, recovered.current["runtime_repair_pr"])
        self.assertEqual("NARROW_RUNTIME_REPAIR_ADMITTED", recovered.current["repair_candidate"])

    def test_structural_reconstruction_metric_is_not_owner_value_claim(self) -> None:
        report = run_shadow_campaign()
        self.assertEqual(87.5, report.structural_reconstruction_read_reduction_pct)
        self.assertEqual("UNPROVEN", report.observed_owner_value_state)
        self.assertEqual("NOT_PROMOTED", LEGACY_CURRENT_STATE["canonical_bible_cutover"])

    def test_shadow_events_are_public_safe_and_non_authorizing(self) -> None:
        for event in workstream_events():
            self.assertEqual("PUBLIC_SAFE", event.privacy_class)
            lowered = str(event.payload).lower()
            for forbidden in ("password", "credential", "medical_raw", "private_raw"):
                self.assertNotIn(forbidden, lowered)
        self.assertFalse(LEGACY_CURRENT_STATE["provider_effect_authorized"])


if __name__ == "__main__":
    unittest.main()
