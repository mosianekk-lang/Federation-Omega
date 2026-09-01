from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import unittest

from benchmarking.cfbe_omega import bco_prime_opportunity_exploitation_fabric_v1 as radar
from benchmarking.cfbe_omega import bco_prime_real_trace_calibration_v1 as court


ROOT = Path(__file__).resolve().parents[1]
try:
    HEAD = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL,
    ).strip()
    GIT_AVAILABLE = True
except (FileNotFoundError, subprocess.CalledProcessError):
    HEAD = "a" * 40
    GIT_AVAILABLE = False
CONTRACT = ROOT / "benchmarking" / "cfbe_omega" / "BCO_PRIME_REAL_TRACE_CALIBRATION_V1.json"


def candidate(index: int, **changes: object) -> radar.OpportunityCandidate:
    values: dict[str, object] = {
        "candidate_id": f"C-{index:03d}",
        "summary": f"real mission {index}",
        "evidence_refs": (f"scope:{index}", f"diff:{index}"),
        "value": (index % 10) / 10,
        "strategic_value": ((index * 3) % 10) / 10,
        "leverage": ((index * 7) % 10) / 10,
        "novelty": ((index * 5) % 10) / 10,
        "confidence": 0.8,
        "reversibility": 0.9,
        "dependency_unlock": ((index * 2) % 10) / 10,
        "urgency": 0.35,
        "risk": 0.1,
        "burden": 0.0,
        "cost": 0.0,
        "existing_coverage": 0.3,
    }
    values.update(changes)
    return radar.OpportunityCandidate(**values)


def trace(index: int, **changes: object) -> court.RealMissionTrace:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=index * 3)
    values: dict[str, object] = {
        "trace_id": f"T-{index:03d}",
        "source_head_sha": HEAD,
        "feature_observed_at": base.isoformat(),
        "outcome_window_started_at": (base + timedelta(hours=1)).isoformat(),
        "outcome_window_ended_at": (base + timedelta(hours=2)).isoformat(),
        "candidate": candidate(index),
        "realized_yield": ((index * 4) % 10) / 10,
        "hard_regression": index % 13 == 0,
        "evidence_refs": (f"git:{index}:scope", f"git:{index}:diff"),
        "outcome_proof_refs": (f"git:{index}:future-start", f"git:{index}:future-end"),
    }
    values.update(changes)
    return court.RealMissionTrace(**values)


class ScoreContractTests(unittest.TestCase):
    def test_baseline_profile_is_exactly_the_live_radar_score(self) -> None:
        item = candidate(7)
        self.assertEqual(radar._opportunity_score(item), court.score_candidate(item))

    def test_profile_weight_keys_and_sums_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "BENEFIT_WEIGHT_KEYS_INVALID"):
            court.ScoreProfile("bad", (("value", 1.0),), court.BASELINE_PROFILE.penalty_weights).validate()

    def test_temporal_leakage_is_rejected(self) -> None:
        item = trace(1, outcome_window_started_at=trace(1).feature_observed_at)
        with self.assertRaisesRegex(ValueError, "TEMPORAL_LEAKAGE"):
            item.validate()

    def test_nonreal_and_weakly_proven_traces_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "REAL_TRACE_REQUIRED"):
            trace(1, real_trace=False).validate()
        with self.assertRaisesRegex(ValueError, "SOURCE_AND_OUTCOME_PROOF_REQUIRED"):
            trace(1, outcome_proof_refs=("only-one",)).validate()


class CalibrationGateTests(unittest.TestCase):
    def test_optimizer_is_deterministic_and_training_only(self) -> None:
        training = tuple(trace(index) for index in range(50))
        first = court.optimize_shadow_profile(training)
        second = court.optimize_shadow_profile(training)
        self.assertEqual(first, second)
        self.assertAlmostEqual(1.0, sum(dict(first.benefit_weights).values()))
        self.assertAlmostEqual(1.0, sum(dict(first.penalty_weights).values()))

    def test_insufficient_real_cohort_is_held(self) -> None:
        receipt = court.evaluate_calibration(tuple(trace(index) for index in range(30)), holdout_size=10)
        self.assertEqual("HOLD_BASELINE_NEGATIVE_RESULT", receipt.decision)
        self.assertIn("MINIMUM_REAL_TRACE_COHORT_REQUIRED", receipt.blockers)
        self.assertIn("MINIMUM_CHRONOLOGICAL_HOLDOUT_REQUIRED", receipt.blockers)

    def test_held_out_regression_blocks_profile_and_live_mutation(self) -> None:
        traces = tuple(
            trace(
                index,
                candidate=candidate(
                    index,
                    value=index / 74,
                    strategic_value=0.0,
                    leverage=0.0,
                    novelty=0.0,
                    dependency_unlock=0.0,
                ),
                realized_yield=1.0 - index / 74,
            )
            for index in range(75)
        )
        receipt = court.evaluate_calibration(traces)
        self.assertEqual("HOLD_BASELINE_NEGATIVE_RESULT", receipt.decision)
        self.assertFalse(receipt.live_weights_changed)
        self.assertFalse(receipt.live_weight_change_authorized)
        self.assertFalse(receipt.external_effect_authorized)
        self.assertFalse(receipt.stable_self_promotion_allowed)
        self.assertEqual([], list(receipt.manual_user_tasks))
        self.assertFalse(receipt.owner_action_required)

    def test_trace_ids_and_source_head_must_be_collision_safe(self) -> None:
        values = [trace(index) for index in range(60)]
        values[-1] = trace(0)
        with self.assertRaisesRegex(ValueError, "TRACE_IDS_MUST_BE_UNIQUE"):
            court.evaluate_calibration(values, holdout_size=20)
        mixed = [trace(index) for index in range(60)]
        mixed[-1] = trace(59, source_head_sha="b" * 40)
        with self.assertRaisesRegex(ValueError, "SOURCE_HEAD_MISMATCH"):
            court.evaluate_calibration(mixed, holdout_size=20)

    def test_receipt_is_deterministic_and_hash_bound(self) -> None:
        traces = tuple(trace(index) for index in range(75))
        first = court.evaluate_calibration(traces)
        second = court.evaluate_calibration(traces)
        self.assertEqual(first, second)
        self.assertTrue(first.receipt_sha256.startswith("sha256:"))
        self.assertEqual(71, len(first.receipt_sha256))


@unittest.skipUnless(GIT_AVAILABLE, "real repository history is unavailable in workflow-free export")
class RealRepositoryIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.traces = court.collect_real_mission_traces(ROOT, source_head_sha=HEAD)

    def test_real_first_parent_cohort_has_pre_post_separation(self) -> None:
        self.assertGreaterEqual(len(self.traces), court.MIN_REAL_TRACES)
        self.assertTrue(all(item.real_trace for item in self.traces))
        self.assertTrue(all(item.source_head_sha == HEAD for item in self.traces))
        self.assertTrue(all(
            datetime.fromisoformat(item.feature_observed_at)
            < datetime.fromisoformat(item.outcome_window_started_at)
            <= datetime.fromisoformat(item.outcome_window_ended_at)
            for item in self.traces
        ))

    def test_current_real_cohort_never_self_promotes_or_changes_live_weights(self) -> None:
        receipt = court.evaluate_calibration(self.traces)
        self.assertFalse(receipt.live_weights_changed)
        self.assertFalse(receipt.live_weight_change_authorized)
        self.assertFalse(receipt.external_effect_authorized)
        self.assertFalse(receipt.stable_self_promotion_allowed)
        self.assertEqual(len(self.traces), receipt.trace_count)

    def test_cli_emits_real_trace_receipt(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "benchmarking.cfbe_omega.bco_prime_real_trace_calibration_v1", "--repo", str(ROOT), "--source-head", HEAD],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(court.SCHEMA, payload["schema"])
        self.assertGreaterEqual(payload["trace_count"], court.MIN_REAL_TRACES)
        self.assertFalse(payload["live_weights_changed"])

    def test_contract_and_manifest_preserve_truth_boundary(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        manifest = court.real_trace_calibration_manifest()
        self.assertEqual(court.SCHEMA, contract["schema"])
        self.assertEqual(court.SCHEMA, manifest["schema"])
        self.assertTrue(manifest["temporal_leakage_rejected"])
        self.assertTrue(manifest["production_profile_immutable"])
        self.assertFalse(manifest["external_effect_authority"])
        self.assertFalse(manifest["stable_self_promotion"])


if __name__ == "__main__":
    unittest.main()
