#!/usr/bin/env python3
from __future__ import annotations

import copy
from datetime import date, datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from frontier_benchmark_engine import (
    BenchmarkError,
    compare_reports,
    compile_report,
    load_knowledgebase,
    refresh_repository,
    source_evidence,
    validate_knowledgebase,
    weighted_axis,
)


BASE = Path(__file__).resolve().parent


class FrontierContractTests(unittest.TestCase):
    def setUp(self):
        self.value = json.loads(
            (BASE / "frontier_knowledgebase_v2.json").read_text(encoding="utf-8")
        )

    def test_current_knowledgebase_validates(self):
        validate_knowledgebase(self.value)

    def test_weights_sum_to_one_hundred(self):
        self.assertEqual(sum(item["weight"] for item in self.value["dimensions"]), 100)

    def test_wrong_owner_rejected(self):
        broken = copy.deepcopy(self.value)
        broken["ownerId"] = "UNKNOWN"
        with self.assertRaises(BenchmarkError):
            validate_knowledgebase(broken)

    def test_absolute_superiority_permission_rejected(self):
        broken = copy.deepcopy(self.value)
        broken["claimPolicy"]["absoluteOrPerpetualSuperiorityAllowed"] = True
        with self.assertRaises(BenchmarkError):
            validate_knowledgebase(broken)

    def test_duplicate_source_rejected(self):
        broken = copy.deepcopy(self.value)
        broken["sources"].append(copy.deepcopy(broken["sources"][0]))
        with self.assertRaises(BenchmarkError):
            validate_knowledgebase(broken)

    def test_duplicate_proposition_rejected(self):
        broken = copy.deepcopy(self.value)
        proposition = copy.deepcopy(broken["sources"][0]["propositions"][0])
        broken["sources"][0]["propositions"].append(proposition)
        with self.assertRaises(BenchmarkError):
            validate_knowledgebase(broken)

    def test_score_without_linked_evidence_rejected(self):
        broken = copy.deepcopy(self.value)
        system = next(item for item in broken["systems"] if item["id"] == "nvidia_omniverse_peer")
        system["capabilityScores"]["durable_execution_resume"] = 1
        with self.assertRaises(BenchmarkError):
            validate_knowledgebase(broken)

    def test_fractional_score_rejected(self):
        broken = copy.deepcopy(self.value)
        broken["systems"][0]["capabilityScores"]["owner_authority_fidelity"] = 4.5
        with self.assertRaises(BenchmarkError):
            validate_knowledgebase(broken)

    def test_maturity_above_capability_rejected(self):
        broken = copy.deepcopy(self.value)
        system = next(item for item in broken["systems"] if item["id"] == "nvidia_omniverse_peer")
        system["maturityScores"]["durable_execution_resume"] = 1
        with self.assertRaises(BenchmarkError):
            validate_knowledgebase(broken)

    def test_public_maturity_above_three_rejected(self):
        broken = copy.deepcopy(self.value)
        system = next(item for item in broken["systems"] if item["id"] == "aws_agentcore_peer")
        system["maturityScores"]["durable_execution_resume"] = 4
        with self.assertRaises(BenchmarkError):
            validate_knowledgebase(broken)

    def test_non_https_public_source_rejected(self):
        broken = copy.deepcopy(self.value)
        broken["sources"][7]["url"] = "http://example.com"
        with self.assertRaises(BenchmarkError):
            validate_knowledgebase(broken)


class FrontierScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.value = load_knowledgebase(BASE / "frontier_knowledgebase_v2.json")
        cls.now = datetime(2026, 8, 22, 13, 40, tzinfo=timezone.utc)
        cls.report = compile_report(
            cls.value, current_date=date(2026, 8, 22), observed_at=cls.now
        )

    def test_dual_axes_are_separate(self):
        for system in self.report["systems"]:
            self.assertIn("capabilityScore", system)
            self.assertIn("operationalMaturityScore", system)
            self.assertNotEqual(
                system["capabilityScore"], system["operationalMaturityScore"]
            )

    def test_scores_are_bounded(self):
        for system in self.report["systems"]:
            for key in (
                "capabilityScore",
                "operationalMaturityScore",
                "evidenceConfidenceScore",
                "confidenceAdjustedCapability",
            ):
                self.assertGreaterEqual(system[key], 0)
                self.assertLessEqual(system[key], 100)

    def test_sovara_is_not_declared_supreme(self):
        self.assertFalse(self.report["claimAllowed"])
        self.assertNotIn("AHEAD_PROVEN", self.report["snapshotState"])

    def test_frontier_envelope_beats_any_single_portfolio(self):
        maximum = max(item["capabilityScore"] for item in self.report["systems"])
        self.assertGreaterEqual(self.report["frontierEnvelopeScore"], maximum)

    def test_current_report_exposes_measured_gaps(self):
        self.assertEqual(self.report["snapshotState"], "MEASURED_GAPS_ACTIVE")
        self.assertGreater(self.report["criticalGapCount"], 0)
        self.assertGreater(len(self.report["opportunityQueue"]), 0)

    def test_opportunity_queue_is_ranked(self):
        scores = [item["opportunityScore"] for item in self.report["opportunityQueue"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(
            self.report["opportunityQueue"][0]["dimension"],
            "durable_execution_resume",
        )

    def test_each_experiment_has_non_regression_and_owner_gates(self):
        for item in self.report["opportunityQueue"]:
            self.assertIn("no_critical_dimension_regression", item["promotionGates"])
            self.assertIn("owner_authority_unchanged", item["promotionGates"])

    def test_freshness_decay_and_expiry(self):
        source = copy.deepcopy(self.value["sources"][0])
        source["retrievedAt"] = "2026-01-01"
        result = source_evidence(source, current_date=date(2026, 8, 22))
        self.assertEqual(result["freshnessState"], "EXPIRED")
        self.assertEqual(result["freshnessFactor"], 0.25)

    def test_expired_source_blocks_current_state(self):
        broken = copy.deepcopy(self.value)
        broken["sources"][0]["retrievedAt"] = "2020-01-01"
        stale = compile_report(
            broken, current_date=date(2026, 8, 22), observed_at=self.now
        )
        self.assertFalse(stale["snapshotCurrent"])
        self.assertEqual(stale["snapshotState"], "UNKNOWN_STALE_EVIDENCE")

    def test_weighted_axis_is_deterministic(self):
        system = self.value["systems"][0]
        self.assertEqual(
            weighted_axis(system["capabilityScores"], self.value["dimensions"]),
            weighted_axis(system["capabilityScores"], self.value["dimensions"]),
        )

    def test_report_fingerprint_is_replay_stable(self):
        again = compile_report(
            self.value, current_date=date(2026, 8, 22), observed_at=self.now
        )
        self.assertEqual(
            self.report["snapshotFingerprint"], again["snapshotFingerprint"]
        )


class FrontierRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.value = load_knowledgebase(BASE / "frontier_knowledgebase_v2.json")
        self.now = datetime(2026, 8, 22, 13, 40, tzinfo=timezone.utc)

    def test_initial_refresh_creates_snapshot_index_and_journal(self):
        with tempfile.TemporaryDirectory() as directory:
            result = refresh_repository(
                self.value,
                directory,
                current_date=date(2026, 8, 22),
                observed_at=self.now,
            )
            self.assertTrue(result.material_change)
            self.assertEqual(result.state, "INITIAL_SNAPSHOT")
            self.assertTrue(Path(result.snapshot_path).exists())
            self.assertTrue(Path(result.index_path).exists())
            self.assertTrue((Path(directory) / "refresh-journal.ndjson").exists())

    def test_replay_is_idempotent_and_does_not_duplicate_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            first = refresh_repository(
                self.value,
                directory,
                current_date=date(2026, 8, 22),
                observed_at=self.now,
            )
            second = refresh_repository(
                self.value,
                directory,
                current_date=date(2026, 8, 22),
                observed_at=datetime(2026, 8, 22, 14, 0, tzinfo=timezone.utc),
            )
            self.assertFalse(second.material_change)
            self.assertEqual(second.state, "NO_MATERIAL_CHANGE")
            index = json.loads(Path(first.index_path).read_text(encoding="utf-8"))
            self.assertEqual(len(index["snapshots"]), 1)
            events = (Path(directory) / "refresh-journal.ndjson").read_text(
                encoding="utf-8"
            ).splitlines()
            self.assertEqual(len(events), 1)

    def test_changed_dataset_creates_delta_without_mutating_first_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            first = refresh_repository(
                self.value,
                directory,
                current_date=date(2026, 8, 22),
                observed_at=self.now,
            )
            first_bytes = Path(first.snapshot_path).read_bytes()
            changed = copy.deepcopy(self.value)
            changed["systems"][0]["capabilityScores"]["durable_execution_resume"] = 5
            second = refresh_repository(
                changed,
                directory,
                current_date=date(2026, 8, 22),
                observed_at=datetime(2026, 8, 22, 15, 0, tzinfo=timezone.utc),
            )
            self.assertTrue(second.material_change)
            self.assertEqual(second.state, "MATERIAL_CHANGE")
            self.assertIsNotNone(second.delta_path)
            self.assertEqual(Path(first.snapshot_path).read_bytes(), first_bytes)
            delta = json.loads(Path(second.delta_path).read_text(encoding="utf-8"))
            self.assertIn("sovara_v38_verified", delta["changedSystems"])
            self.assertIn("durable_execution_resume", delta["changedDimensions"])

    def test_compare_identical_reports_has_no_material_change(self):
        report = compile_report(
            self.value, current_date=date(2026, 8, 22), observed_at=self.now
        )
        delta = compare_reports(report, copy.deepcopy(report))
        self.assertFalse(delta["materialChange"])

    def test_broken_latest_pointer_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            refresh_repository(
                self.value,
                directory,
                current_date=date(2026, 8, 22),
                observed_at=self.now,
            )
            index_path = Path(directory) / "index.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            index["latestSnapshotPath"] = "snapshots/missing.json"
            index_path.write_text(json.dumps(index), encoding="utf-8")
            with self.assertRaises(BenchmarkError):
                refresh_repository(
                    self.value,
                    directory,
                    current_date=date(2026, 8, 22),
                    observed_at=self.now,
                )


if __name__ == "__main__":
    unittest.main()
