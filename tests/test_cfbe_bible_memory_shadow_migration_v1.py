from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.bible_memory_fabric_v1 import ProjectionCompiler
from benchmarking.cfbe_omega.bible_memory_shadow_migration_v1 import (
    LEGACY_CURRENT_STATE,
    STREAM_ID,
    build_store,
    run_shadow_campaign,
    workstream_events,
)


class CFBEBibleMemoryShadowMigrationV1Tests(unittest.TestCase):
    def test_campaign_is_exactly_30_of_30_before_any_authoritative_migration(self) -> None:
        report = run_shadow_campaign()
        self.assertEqual(30, report.pair_count)
        self.assertEqual(30, report.pass_count)
        self.assertEqual(0, report.hard_failure_count)
        self.assertEqual("SHADOW_ENGINEERING_PASS", report.promotion_state)

    def test_rebuilt_current_projection_matches_public_legacy_snapshot(self) -> None:
        store = build_store()
        projection = ProjectionCompiler().project(store.stream(STREAM_ID))
        self.assertEqual(LEGACY_CURRENT_STATE, projection.current)
        self.assertIn("cfbe-input-evt-0003", projection.superseded_event_ids)

    def test_as_of_queries_preserve_failure_then_recovery_without_rewriting_history(self) -> None:
        events = workstream_events()
        compiler = ProjectionCompiler()
        failed = compiler.project(events, as_of_recorded_at="2026-08-31T18:51:55Z")
        recovered = compiler.project(events, as_of_recorded_at="2026-08-31T18:55:02Z")
        self.assertEqual("SOURCE_CANDIDATE_AIRLOCK_BLOCKED", failed.current["challenger_state"])
        self.assertEqual(895, failed.current["last_failed_pr"])
        self.assertEqual("SOURCE_ADMITTED", recovered.current["challenger_state"])
        self.assertEqual(900, recovered.current["successful_pr"])

    def test_shadow_harness_does_not_claim_real_owner_value_or_canonical_replacement(self) -> None:
        report = run_shadow_campaign()
        self.assertEqual(0, report.owner_reconstruction_prompts_in_harness)
        self.assertEqual("NOT_PROMOTED", LEGACY_CURRENT_STATE["canonical_replacement"])
        self.assertTrue(report.semantic_parity)

    def test_public_shadow_events_contain_no_private_or_consequential_payload_class(self) -> None:
        for event in workstream_events():
            self.assertEqual("PUBLIC_SAFE", event.privacy_class)
            lowered = str(event.payload).lower()
            for forbidden in ("password", "credential", "medical_raw", "private_raw"):
                self.assertNotIn(forbidden, lowered)


if __name__ == "__main__":
    unittest.main()
