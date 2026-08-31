from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from evidenceops.caseforge.owner_value_deployment_court_v2 import evaluate_proof_court


HEAD = "4fcbe3d0810032520cb2367456d79ccda79d3a5f"
CANDIDATE = "bubbles-digital-twin-v2"


def owner_pair(index: int, **changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "pair_id": f"owner-{index}",
        "mission_class": "CURRENT_STATE_READ",
        "task_signature": f"task-{index}",
        "oracle_id": "oracle-v1",
        "source_head_sha": HEAD,
        "evidence_mode": "OBSERVED_OWNER_VALUE",
        "baseline_owner_minutes": 10,
        "candidate_owner_minutes": 5,
        "baseline_owner_interventions": 2,
        "candidate_owner_interventions": 1,
        "baseline_clarification_count": 2,
        "candidate_clarification_count": 1,
        "baseline_correction_count": 1,
        "candidate_correction_count": 0,
        "baseline_verified_output_ratio": 0.9,
        "candidate_verified_output_ratio": 1.0,
        "baseline_elapsed_seconds": 100,
        "candidate_elapsed_seconds": 50,
        "independent_readback": True,
        "proof_refs": [f"baseline:{index}", f"candidate:{index}"],
    }
    value.update(changes)
    return value


def internal_runtime(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "evidence_id": "runtime-1",
        "source_head_sha": HEAD,
        "evidence_mode": "INTERNAL_RUNTIME_QUALIFICATION",
        "environment": "ci-container",
        "image_digest": "sha256:" + "a" * 64,
        "revision_id": "",
        "provider_registration_verified": False,
        "workload_identity_verified": False,
        "health_readback_verified": True,
        "rollback_verified": True,
        "deployment_observed": False,
        "independent_readback": True,
        "provider_effect_authorized": False,
        "proof_refs": ["health:1", "rollback:1"],
    }
    value.update(changes)
    return value


def live_deployment(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "evidence_id": "deploy-1",
        "source_head_sha": HEAD,
        "evidence_mode": "LIVE_PROVIDER_DEPLOYMENT",
        "environment": "bounded-canary",
        "image_digest": "sha256:" + "b" * 64,
        "revision_id": "revision-1",
        "provider_registration_verified": True,
        "workload_identity_verified": True,
        "health_readback_verified": True,
        "rollback_verified": True,
        "deployment_observed": True,
        "independent_readback": True,
        "provider_effect_authorized": True,
        "proof_refs": ["provider:registration", "runtime:health", "runtime:rollback"],
    }
    value.update(changes)
    return value


class OwnerValueDeploymentCourtV2Tests(unittest.TestCase):
    def test_no_observations_holds(self) -> None:
        receipt = evaluate_proof_court(candidate_id=CANDIDATE, source_head_sha=HEAD)
        self.assertEqual("HOLD_NO_PROMOTION", receipt.decision)
        self.assertFalse(receipt.owner_value_proven)
        self.assertIn("OWNER_VALUE_MINIMUM_OBSERVED_PAIRS_REQUIRED", receipt.blockers)
        self.assertFalse(receipt.stable_promotion_authorized)
        self.assertFalse(receipt.external_effect)

    def test_default_minimum_requires_ten_pairs(self) -> None:
        receipt = evaluate_proof_court(
            candidate_id=CANDIDATE,
            source_head_sha=HEAD,
            owner_value_observations=[owner_pair(i) for i in range(9)],
        )
        self.assertFalse(receipt.owner_value_proven)
        self.assertIn("OWNER_VALUE_MINIMUM_OBSERVED_PAIRS_REQUIRED", receipt.blockers)

    def test_synthetic_or_shadow_cannot_count_as_owner_value(self) -> None:
        receipt = evaluate_proof_court(
            candidate_id=CANDIDATE,
            source_head_sha=HEAD,
            owner_value_observations=[
                owner_pair(i, evidence_mode="HOSTED_SHADOW") for i in range(10)
            ],
        )
        self.assertFalse(receipt.owner_value_proven)
        self.assertIn("OWNER_VALUE_EVIDENCE_MODE_INVALID", receipt.blockers)

    def test_task_oracle_identity_is_required(self) -> None:
        observations = [owner_pair(i) for i in range(10)]
        observations[0] = owner_pair(0, task_signature="", oracle_id="")
        receipt = evaluate_proof_court(
            candidate_id=CANDIDATE,
            source_head_sha=HEAD,
            owner_value_observations=observations,
        )
        self.assertFalse(receipt.owner_value_proven)
        self.assertIn("OWNER_VALUE_TASK_ORACLE_IDENTITY_REQUIRED", receipt.blockers)

    def test_duplicate_pair_id_is_rejected(self) -> None:
        observations = [owner_pair(i) for i in range(10)]
        observations[-1] = owner_pair(0)
        receipt = evaluate_proof_court(
            candidate_id=CANDIDATE,
            source_head_sha=HEAD,
            owner_value_observations=observations,
        )
        self.assertFalse(receipt.owner_value_proven)
        self.assertIn("OWNER_VALUE_PAIR_IDS_MUST_BE_UNIQUE", receipt.blockers)

    def test_output_quality_regression_blocks_owner_value(self) -> None:
        observations = [owner_pair(i) for i in range(10)]
        observations[0] = owner_pair(0, candidate_verified_output_ratio=0.8)
        receipt = evaluate_proof_court(
            candidate_id=CANDIDATE,
            source_head_sha=HEAD,
            owner_value_observations=observations,
        )
        self.assertFalse(receipt.owner_value_proven)
        self.assertIn("OWNER_VALUE_OUTPUT_RATIO_REGRESSION", receipt.blockers)

    def test_creator_time_must_improve_in_every_pair(self) -> None:
        observations = [owner_pair(i) for i in range(10)]
        observations[0] = owner_pair(0, candidate_owner_minutes=10)
        receipt = evaluate_proof_court(
            candidate_id=CANDIDATE,
            source_head_sha=HEAD,
            owner_value_observations=observations,
        )
        self.assertFalse(receipt.owner_value_proven)
        self.assertIn("OWNER_VALUE_CREATOR_TIME_NOT_RECOVERED", receipt.blockers)

    def test_clarification_and_correction_regressions_cannot_hide_in_aggregate(self) -> None:
        observations = [owner_pair(i) for i in range(10)]
        observations[0] = owner_pair(
            0,
            candidate_clarification_count=3,
            candidate_correction_count=2,
        )
        receipt = evaluate_proof_court(
            candidate_id=CANDIDATE,
            source_head_sha=HEAD,
            owner_value_observations=observations,
        )
        self.assertFalse(receipt.owner_value_proven)
        self.assertIn("OWNER_VALUE_CLARIFICATION_REGRESSION", receipt.blockers)
        self.assertIn("OWNER_VALUE_CORRECTION_REGRESSION", receipt.blockers)

    def test_independent_readback_and_two_proof_refs_are_required(self) -> None:
        observations = [owner_pair(i) for i in range(10)]
        observations[0] = owner_pair(0, independent_readback=False, proof_refs=["one"])
        receipt = evaluate_proof_court(
            candidate_id=CANDIDATE,
            source_head_sha=HEAD,
            owner_value_observations=observations,
        )
        self.assertFalse(receipt.owner_value_proven)
        self.assertIn("OWNER_VALUE_INDEPENDENT_READBACK_REQUIRED", receipt.blockers)
        self.assertIn("OWNER_VALUE_PROOF_REFS_INCOMPLETE", receipt.blockers)

    def test_owner_value_can_be_proven_while_deployment_gates_remain_open(self) -> None:
        receipt = evaluate_proof_court(
            candidate_id=CANDIDATE,
            source_head_sha=HEAD,
            owner_value_observations=[owner_pair(i) for i in range(10)],
        )
        self.assertTrue(receipt.owner_value_proven)
        self.assertEqual("OWNER_VALUE_PROVEN_DEPLOYMENT_GATES_OPEN", receipt.decision)
        self.assertEqual(50.0, receipt.creator_time_recovered_minutes)
        self.assertEqual(5.0, receipt.median_creator_time_recovered_minutes)
        self.assertEqual(1.0, receipt.median_clarification_delta)
        self.assertEqual(1.0, receipt.median_correction_delta)
        self.assertFalse(receipt.provider_deployment_proven)

    def test_internal_runtime_never_counts_as_provider_deployment(self) -> None:
        receipt = evaluate_proof_court(
            candidate_id=CANDIDATE,
            source_head_sha=HEAD,
            owner_value_observations=[owner_pair(i) for i in range(10)],
            runtime_or_deployment_evidence=[internal_runtime()],
        )
        self.assertTrue(receipt.internal_runtime_qualified)
        self.assertFalse(receipt.provider_deployment_proven)
        self.assertIn("LIVE_PROVIDER_DEPLOYMENT_EVIDENCE_REQUIRED", receipt.blockers)

    def test_complete_typed_evidence_reaches_owner_review_but_never_self_promotes(self) -> None:
        receipt = evaluate_proof_court(
            candidate_id=CANDIDATE,
            source_head_sha=HEAD,
            owner_value_observations=[owner_pair(i) for i in range(10)],
            runtime_or_deployment_evidence=[internal_runtime(), live_deployment()],
        )
        self.assertEqual(
            "OWNER_VALUE_AND_DEPLOYMENT_PROOF_SATISFIED_PROMOTION_REVIEW_REQUIRED",
            receipt.decision,
        )
        self.assertTrue(receipt.owner_value_proven)
        self.assertTrue(receipt.internal_runtime_qualified)
        self.assertTrue(receipt.provider_deployment_proven)
        self.assertFalse(receipt.stable_promotion_authorized)
        self.assertFalse(receipt.effect_authorized)
        self.assertFalse(receipt.external_effect)

    def test_source_head_mismatch_blocks_pair(self) -> None:
        observations = [owner_pair(i) for i in range(10)]
        observations[0] = owner_pair(0, source_head_sha="1" * 40)
        receipt = evaluate_proof_court(
            candidate_id=CANDIDATE,
            source_head_sha=HEAD,
            owner_value_observations=observations,
        )
        self.assertFalse(receipt.owner_value_proven)
        self.assertIn("OWNER_VALUE_SOURCE_HEAD_MISMATCH", receipt.blockers)

    def test_receipt_is_deterministic(self) -> None:
        kwargs = {
            "candidate_id": CANDIDATE,
            "source_head_sha": HEAD,
            "owner_value_observations": [owner_pair(i) for i in range(10)],
        }
        first = evaluate_proof_court(**kwargs)
        second = evaluate_proof_court(**kwargs)
        self.assertEqual(first.receipt_sha256, second.receipt_sha256)

    def test_cli_writes_hold_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "court.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "evidenceops.caseforge.owner_value_deployment_court_v2",
                    "--candidate-id",
                    CANDIDATE,
                    "--source-head-sha",
                    HEAD,
                    "--output",
                    str(output),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, msg=result.stderr)
            self.assertEqual("HOLD_NO_PROMOTION", json.loads(output.read_text())["decision"])


if __name__ == "__main__":
    unittest.main()
