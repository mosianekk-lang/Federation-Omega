from __future__ import annotations

from hashlib import sha256
import unittest

from benchmarking.cfbe_omega.autopilot_metacognition_observed_intake_v1 import (
    MEASUREMENT_ORIGIN,
    PAIR_SCHEMA,
    RESUME_SCHEMA,
    SCHEMA,
    WITNESS_SCHEMA,
    compile_observed_operational_intake,
)


HEAD = "a" * 40
SOURCE_REF = f"source:{HEAD}"


def digest(label: str) -> str:
    return "sha256:" + sha256(label.encode("utf-8")).hexdigest()


def witness(
    ref: str,
    kind: str,
    evidence_class: str,
    *,
    independent: bool = False,
    environment: str = "production",
) -> dict[str, object]:
    return {
        "schema": WITNESS_SCHEMA,
        "ref": ref,
        "kind": kind,
        "evidence_class": evidence_class,
        "provider": "github",
        "environment": environment,
        "source_head_sha": HEAD,
        "provider_object_id": f"object-{ref}",
        "digest": digest(ref),
        "verified": True,
        "independent": independent,
        "observed_at_utc": "2026-09-01T00:02:00Z",
    }


def pair_bundle(index: int, *, external_effect: bool = False) -> tuple[list[dict[str, object]], dict[str, object]]:
    base = f"pair-{index:03d}"
    baseline_ref = f"exec:{base}:baseline"
    candidate_ref = f"exec:{base}:candidate"
    readback_ref = f"readback:{base}"
    outcome_ref = f"outcome:{base}"
    witnesses = [
        witness(baseline_ref, "EXECUTION", "IMMUTABLE_EXECUTION_RECEIPT"),
        witness(candidate_ref, "EXECUTION", "IMMUTABLE_EXECUTION_RECEIPT"),
        witness(readback_ref, "READBACK", "PROVIDER_LIVE_INDEPENDENT_READBACK", independent=True),
        witness(outcome_ref, "OUTCOME", "REPEATED_OPERATIONAL_SCOPED", independent=True),
    ]
    proof_refs = [SOURCE_REF, baseline_ref, candidate_ref, readback_ref, outcome_ref]
    authority_ref = ""
    if external_effect:
        authority_ref = f"authority:{base}"
        witnesses.append(witness(authority_ref, "AUTHORITY", "PROVIDER_AUTHORITY_RECEIPT"))
        proof_refs.append(authority_ref)

    record = {
        "schema": PAIR_SCHEMA,
        "pair_id": base,
        "source_head_sha": HEAD,
        "mission_class": "REAL_WORKFLOW_RECOVERY",
        "baseline_execution_id": f"baseline-run-{index}",
        "candidate_execution_id": f"candidate-run-{index}",
        "baseline_task_signature": f"matched-task-{index}",
        "candidate_task_signature": f"matched-task-{index}",
        "oracle_id": f"oracle-{index}",
        "measurement_origin": MEASUREMENT_ORIGIN,
        "baseline_quality": 0.70,
        "candidate_quality": 0.85,
        "baseline_elapsed_ms": 1000.0,
        "candidate_elapsed_ms": 900.0,
        "baseline_owner_minutes": 3.0,
        "candidate_owner_minutes": 1.0,
        "baseline_owner_interventions": 1,
        "candidate_owner_interventions": 0,
        "baseline_clarification_count": 1,
        "candidate_clarification_count": 0,
        "baseline_correction_count": 1,
        "candidate_correction_count": 0,
        "baseline_verified_output_ratio": 0.90,
        "candidate_verified_output_ratio": 1.0,
        "candidate_reflection_used": True,
        "candidate_confidence": 0.90,
        "candidate_outcome_correct": True,
        "confidence_recorded_at_utc": "2026-09-01T00:00:00Z",
        "outcome_resolved_at_utc": "2026-09-01T00:01:00Z",
        "independent_readback_ref": readback_ref,
        "proof_refs": proof_refs,
        "external_effect_observed": external_effect,
        "effect_authority_ref": authority_ref,
    }
    return witnesses, record


def resume_bundle(index: int, *, external_effect: bool = False) -> tuple[list[dict[str, object]], dict[str, object]]:
    base = f"resume-{index:03d}"
    before_ref = f"exec:{base}:before"
    after_ref = f"exec:{base}:after"
    checkpoint_ref = f"checkpoint:{base}"
    readback_ref = f"readback:{base}"
    witnesses = [
        witness(before_ref, "EXECUTION", "IMMUTABLE_EXECUTION_RECEIPT"),
        witness(after_ref, "EXECUTION", "IMMUTABLE_EXECUTION_RECEIPT"),
        witness(checkpoint_ref, "CHECKPOINT", "REPEATED_OPERATIONAL_SCOPED", independent=True),
        witness(readback_ref, "READBACK", "PROVIDER_LIVE_INDEPENDENT_READBACK", independent=True),
    ]
    proof_refs = [SOURCE_REF, before_ref, after_ref, checkpoint_ref, readback_ref]
    authority_ref = ""
    if external_effect:
        authority_ref = f"authority:{base}"
        witnesses.append(witness(authority_ref, "AUTHORITY", "PROVIDER_AUTHORITY_RECEIPT"))
        proof_refs.append(authority_ref)

    record = {
        "schema": RESUME_SCHEMA,
        "observation_id": base,
        "source_head_sha": HEAD,
        "mission_class": "REAL_WORKFLOW_RECOVERY",
        "measurement_origin": MEASUREMENT_ORIGIN,
        "process_before": f"process-before-{index}",
        "process_after": f"process-after-{index}",
        "checkpoint_id": f"checkpoint-id-{index}",
        "resumed": True,
        "duplicate_effect_count": 0,
        "state_drift": False,
        "independent_readback_ref": readback_ref,
        "proof_refs": proof_refs,
        "external_effect_observed": external_effect,
        "effect_authority_ref": authority_ref,
    }
    return witnesses, record


def cohort(pair_count: int, resume_count: int) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    witnesses: list[dict[str, object]] = []
    pairs: list[dict[str, object]] = []
    resumes: list[dict[str, object]] = []
    for index in range(pair_count):
        rows, record = pair_bundle(index)
        witnesses.extend(rows)
        pairs.append(record)
    for index in range(resume_count):
        rows, record = resume_bundle(index)
        witnesses.extend(rows)
        resumes.append(record)
    return witnesses, pairs, resumes


class AutoPilotObservedOperationalIntakeV1Tests(unittest.TestCase):
    def test_30_plus_10_structural_path_reaches_observed_candidate_but_not_provider_runtime(self) -> None:
        witnesses, pairs, resumes = cohort(30, 10)
        receipt = compile_observed_operational_intake(
            candidate_id="AUTOPILOT-METACOG-V1",
            source_head_sha=HEAD,
            witness_records=witnesses,
            pair_records=pairs,
            resume_records=resumes,
        )
        self.assertEqual(SCHEMA, receipt.schema)
        self.assertEqual(30, receipt.pair_record_count)
        self.assertEqual(10, receipt.resume_record_count)
        self.assertTrue(receipt.observed_empirical_candidate)
        self.assertTrue(receipt.owner_value_proven)
        self.assertFalse(receipt.provider_runtime_candidate)
        self.assertFalse(receipt.full_autopilot_runtime_proven)
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertFalse(receipt.stable_promotion_authorized)
        self.assertEqual(
            "OBSERVED_OPERATIONAL_METACOG_AND_OWNER_VALUE_CANDIDATE",
            receipt.decision,
        )
        self.assertEqual(
            "PROVIDER_NATIVE_ALWAYS_ON_EVENT_INTAKE_AND_DURABLE_RUNTIME",
            receipt.next_gate,
        )
        self.assertEqual(
            "OBSERVED_METACOG_EMPIRICAL_CANDIDATE",
            receipt.empirical_court["decision"],
        )
        self.assertEqual("OWNER_VALUE_PROVEN_DEPLOYMENT_GATES_OPEN", receipt.owner_value_court["decision"])

    def test_small_real_cohort_is_admitted_without_false_promotion(self) -> None:
        witnesses, pairs, resumes = cohort(3, 2)
        receipt = compile_observed_operational_intake(
            candidate_id="AUTOPILOT-METACOG-V1",
            source_head_sha=HEAD,
            witness_records=witnesses,
            pair_records=pairs,
            resume_records=resumes,
        )
        self.assertFalse(receipt.observed_empirical_candidate)
        self.assertFalse(receipt.owner_value_proven)
        self.assertEqual("OBSERVED_OPERATIONAL_INTAKE_ADMITTED_MORE_EPISODES_REQUIRED", receipt.decision)
        self.assertIn("MINIMUM_PAIRED_METACOG_CASES_REQUIRED", receipt.empirical_court["blockers"])
        self.assertIn("MINIMUM_CROSS_PROCESS_RESUME_CASES_REQUIRED", receipt.empirical_court["blockers"])

    def test_shadow_test_canary_and_fixture_environments_are_rejected(self) -> None:
        for environment in ("hosted-shadow", "synthetic", "fixture-lab", "test", "canary"):
            witnesses, pair = pair_bundle(0)
            witnesses[0] = {**witnesses[0], "environment": environment}
            _, resume = resume_bundle(0)
            with self.subTest(environment=environment):
                with self.assertRaisesRegex(ValueError, "WITNESS_NON_OPERATIONAL_ENVIRONMENT_REJECTED"):
                    compile_observed_operational_intake(
                        candidate_id="AUTOPILOT-METACOG-V1",
                        source_head_sha=HEAD,
                        witness_records=witnesses,
                        pair_records=[pair],
                        resume_records=[resume],
                    )

    def test_confidence_must_be_recorded_before_resolved_outcome(self) -> None:
        witnesses, pair = pair_bundle(0)
        pair = {
            **pair,
            "confidence_recorded_at_utc": "2026-09-01T00:03:00Z",
            "outcome_resolved_at_utc": "2026-09-01T00:01:00Z",
        }
        resume_witnesses, resume = resume_bundle(0)
        with self.assertRaisesRegex(ValueError, "OBSERVED_PAIR_CONFIDENCE_MUST_PREDATE_OUTCOME"):
            compile_observed_operational_intake(
                candidate_id="AUTOPILOT-METACOG-V1",
                source_head_sha=HEAD,
                witness_records=witnesses + resume_witnesses,
                pair_records=[pair],
                resume_records=[resume],
            )

    def test_unbound_proof_reference_fails_closed(self) -> None:
        witnesses, pair = pair_bundle(0)
        pair = {**pair, "proof_refs": list(pair["proof_refs"]) + ["readback:invented"]}
        resume_witnesses, resume = resume_bundle(0)
        with self.assertRaisesRegex(ValueError, "OBSERVED_PAIR_UNKNOWN_WITNESS_REF"):
            compile_observed_operational_intake(
                candidate_id="AUTOPILOT-METACOG-V1",
                source_head_sha=HEAD,
                witness_records=witnesses + resume_witnesses,
                pair_records=[pair],
                resume_records=[resume],
            )

    def test_raw_prompt_or_content_field_is_rejected(self) -> None:
        witnesses, pair = pair_bundle(0)
        pair = {**pair, "prompt": "private task content must never enter the telemetry schema"}
        resume_witnesses, resume = resume_bundle(0)
        with self.assertRaisesRegex(ValueError, "OBSERVED_PAIR_UNKNOWN_FIELDS_REJECTED"):
            compile_observed_operational_intake(
                candidate_id="AUTOPILOT-METACOG-V1",
                source_head_sha=HEAD,
                witness_records=witnesses + resume_witnesses,
                pair_records=[pair],
                resume_records=[resume],
            )

    def test_past_external_effect_requires_authority_witness_but_never_grants_new_authority(self) -> None:
        pair_witnesses, pair = pair_bundle(0, external_effect=True)
        resume_witnesses, resume = resume_bundle(0, external_effect=True)
        receipt = compile_observed_operational_intake(
            candidate_id="AUTOPILOT-METACOG-V1",
            source_head_sha=HEAD,
            witness_records=pair_witnesses + resume_witnesses,
            pair_records=[pair],
            resume_records=[resume],
        )
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertFalse(receipt.full_autopilot_runtime_proven)

        missing_authority = [row for row in pair_witnesses if row["kind"] != "AUTHORITY"]
        with self.assertRaisesRegex(ValueError, "OBSERVED_PAIR_UNKNOWN_WITNESS_REF"):
            compile_observed_operational_intake(
                candidate_id="AUTOPILOT-METACOG-V1",
                source_head_sha=HEAD,
                witness_records=missing_authority + resume_witnesses,
                pair_records=[pair],
                resume_records=[resume],
            )

    def test_truth_boundary_explicitly_denies_fixture_evidence_and_full_autopilot_claim(self) -> None:
        witnesses, pairs, resumes = cohort(1, 1)
        receipt = compile_observed_operational_intake(
            candidate_id="AUTOPILOT-METACOG-V1",
            source_head_sha=HEAD,
            witness_records=witnesses,
            pair_records=pairs,
            resume_records=resumes,
        )
        joined = " ".join(receipt.truth_boundary)
        self.assertIn("Unit tests", joined)
        self.assertIn("never establish OBSERVED_OPERATIONAL", joined)
        self.assertIn("cannot prove provider-native always-on intake", joined)
        self.assertFalse(receipt.stable_promotion_authorized)


if __name__ == "__main__":
    unittest.main()
