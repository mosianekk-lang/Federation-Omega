from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmarking.cfbe_omega.prospective_observation_cohort_v1 import (
    initialize_prospective_cohort,
    main,
    validate_cohort_manifest,
)


SOURCE_HEAD = "438fa90f9a39ee4886685df55ec01bb12670d770"


def task_oracles() -> list[dict[str, str]]:
    return [
        {"task_oracle_id": f"CFBE-REAL-TASK-ORACLE-{index:02d}", "task_class": task_class}
        for index, task_class in enumerate(
            (
                "DIRECTIVE_COMPLETION",
                "CLARIFICATION_HANDLING",
                "CORRECTION_RECOVERY",
                "EVIDENCE_RESOLUTION",
                "SOURCE_DRIFT_RECOVERY",
                "OWNER_TIME_REDUCTION",
                "OUTPUT_QUALITY_PRESERVATION",
                "RUNTIME_PROOF_ISOLATION",
                "DETERMINISTIC_READBACK",
                "PROMOTION_BOUNDARY_ENFORCEMENT",
            ),
            start=1,
        )
    ]


def manifest():
    return initialize_prospective_cohort(
        cohort_id="CFBE-VF-COHORT-001",
        champion_id="FEDERATION-MAIN-5D03D53",
        candidate_id="CFBE-VALUE-FOUNDRY-V1-438FA90",
        source_head_sha=SOURCE_HEAD,
        registered_at="2026-09-01T03:55:00Z",
        task_oracles=task_oracles(),
    )


class ProspectiveObservationCohortV1Tests(unittest.TestCase):
    def test_initializes_exactly_ten_unique_slots(self) -> None:
        item = manifest()
        self.assertEqual(len(item.slots), 10)
        self.assertEqual(len({slot.slot_id for slot in item.slots}), 10)
        self.assertEqual(len({slot.task_oracle_id for slot in item.slots}), 10)

    def test_initial_state_contains_no_measurements_or_value_claim(self) -> None:
        item = manifest()
        self.assertEqual(item.compiled_pair_count, 0)
        self.assertFalse(item.owner_value_proven)
        self.assertFalse(item.provider_deployment_proven)
        self.assertFalse(item.stable_promotion_allowed)
        self.assertFalse(item.provider_effect_authorized)
        self.assertFalse(item.external_effect)

    def test_every_slot_requires_real_and_prohibits_synthetic_and_shadow(self) -> None:
        for slot in manifest().slots:
            self.assertTrue(slot.real_observation_required)
            self.assertFalse(slot.synthetic_observation_allowed)
            self.assertFalse(slot.shadow_observation_allowed)

    def test_manifest_is_deterministic(self) -> None:
        self.assertEqual(manifest().receipt_sha256, manifest().receipt_sha256)

    def test_distinct_champion_and_candidate_are_required(self) -> None:
        with self.assertRaisesRegex(ValueError, "DISTINCT"):
            initialize_prospective_cohort(
                cohort_id="C", champion_id="SAME", candidate_id="SAME",
                source_head_sha=SOURCE_HEAD, registered_at="2026-09-01T03:55:00Z",
                task_oracles=task_oracles(),
            )

    def test_exactly_ten_oracles_are_required(self) -> None:
        with self.assertRaisesRegex(ValueError, "EXACTLY_TEN"):
            initialize_prospective_cohort(
                cohort_id="C", champion_id="A", candidate_id="B",
                source_head_sha=SOURCE_HEAD, registered_at="2026-09-01T03:55:00Z",
                task_oracles=task_oracles()[:-1],
            )

    def test_duplicate_oracle_id_is_rejected(self) -> None:
        values = task_oracles()
        values[1]["task_oracle_id"] = values[0]["task_oracle_id"]
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            initialize_prospective_cohort(
                cohort_id="C", champion_id="A", candidate_id="B",
                source_head_sha=SOURCE_HEAD, registered_at="2026-09-01T03:55:00Z",
                task_oracles=values,
            )

    def test_invalid_source_head_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "SOURCE_HEAD"):
            initialize_prospective_cohort(
                cohort_id="C", champion_id="A", candidate_id="B",
                source_head_sha="short", registered_at="2026-09-01T03:55:00Z",
                task_oracles=task_oracles(),
            )

    def test_tampered_manifest_fails_validation(self) -> None:
        payload = manifest().to_dict()
        payload["slots"][0]["synthetic_observation_allowed"] = True
        with self.assertRaisesRegex(ValueError, "SYNTHETIC"):
            validate_cohort_manifest(payload)

    def test_repository_manifest_is_valid_and_empty(self) -> None:
        root = Path(__file__).resolve().parents[1]
        path = root / "benchmarking/cfbe_omega/cohorts/CFBE_VALUE_FOUNDRY_COHORT_001.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        validate_cohort_manifest(payload)
        self.assertEqual(payload["compiled_pair_count"], 0)

    def test_cli_writes_valid_manifest(self) -> None:
        request = {
            "cohort_id": "CFBE-VF-COHORT-CLI",
            "champion_id": "A",
            "candidate_id": "B",
            "source_head_sha": SOURCE_HEAD,
            "registered_at": "2026-09-01T03:55:00Z",
            "task_oracles": task_oracles(),
        }
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.json"
            output_path = Path(directory) / "output.json"
            input_path.write_text(json.dumps(request), encoding="utf-8")
            with patch("sys.argv", ["cohort", "--input", str(input_path), "--output", str(output_path)]):
                self.assertEqual(main(), 0)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            validate_cohort_manifest(payload)

    def test_validation_does_not_mutate_input(self) -> None:
        payload = manifest().to_dict()
        before = copy.deepcopy(payload)
        validate_cohort_manifest(payload)
        self.assertEqual(payload, before)


if __name__ == "__main__":
    unittest.main()
