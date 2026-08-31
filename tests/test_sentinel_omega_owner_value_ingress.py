import unittest

from federation.sentinel_omega.owner_value_ingress import (
    MEASURED,
    OBSERVED_OWNER_VALUE,
    UNMEASURED,
    UNMEASURED_OWNER_VALUE,
    OwnerValueMissionObservationAdapter,
    OwnerValueMissionRecord,
    OwnerValuePairCompiler,
)
from federation.sentinel_omega.observation_ingress import ObservationIngressBatch
from federation.sentinel_omega.observability_causal_fabric import SignalKind


HEAD = "1ee2ab1b67fabb0e0496c55d0f8c1f021b057e61"


class OwnerValueIngressTests(unittest.TestCase):
    def _record(
        self,
        variant: str,
        *,
        observation_id: str | None = None,
        pair_id: str = "pair-1",
        task_signature: str = "task-owner-value-1",
        oracle_id: str = "oracle-owner-value-v1",
        source_head_sha: str = HEAD,
        intervention_seconds: float | None = 120.0,
        intervention_count: int | None = 2,
        clarifications: int | None = 1,
        corrections: int | None = 0,
        elapsed: float | None = 300.0,
        ratio: float | None = 1.0,
        accepted: bool | None = True,
        readback: bool = True,
        evidence_class: str = OBSERVED_OWNER_VALUE,
        measurement_state: str = MEASURED,
        proof_refs=None,
    ):
        return {
            "observation_id": observation_id or f"obs-{variant.lower()}",
            "pair_id": pair_id,
            "variant": variant,
            "mission_class": "SOFTWARE_ENGINEERING",
            "mission_id": f"mission-{pair_id}",
            "task_signature": task_signature,
            "oracle_id": oracle_id,
            "source_head_sha": source_head_sha,
            "observed_at": "2026-08-31T22:00:00+02:00",
            "accepted": accepted,
            "verified_output_ratio": ratio,
            "owner_intervention_seconds": intervention_seconds,
            "owner_intervention_count": intervention_count,
            "clarification_count": clarifications,
            "correction_count": corrections,
            "elapsed_seconds": elapsed,
            "independent_readback": readback,
            "proof_refs": proof_refs or (f"proof:{variant}:provider",),
            "evidence_class": evidence_class,
            "measurement_state": measurement_state,
        }

    def test_measured_record_normalizes_as_proof(self):
        item, observation = OwnerValueMissionObservationAdapter.adapt(self._record("BASELINE"))
        self.assertTrue(item.court_eligible_single_observation)
        self.assertEqual(observation.signal_kind, SignalKind.PROOF)
        self.assertEqual(observation.change_ref, HEAD)
        self.assertEqual(observation.attributes["measurement_state"], MEASURED)

    def test_unmeasured_record_is_preserved_but_not_court_eligible(self):
        record = self._record(
            "BUBBLES",
            intervention_seconds=None,
            intervention_count=None,
            clarifications=None,
            corrections=None,
            elapsed=None,
            ratio=None,
            accepted=None,
            readback=False,
            evidence_class=UNMEASURED_OWNER_VALUE,
            measurement_state=UNMEASURED,
        )
        item, observation = OwnerValueMissionObservationAdapter.adapt(record)
        self.assertFalse(item.court_eligible_single_observation)
        self.assertEqual(observation.signal_kind, SignalKind.HEALTH)
        with self.assertRaisesRegex(ValueError, "TWO_MEASURED_OBSERVATIONS"):
            OwnerValuePairCompiler.compile(
                OwnerValueMissionRecord.from_mapping(self._record("BASELINE")), item
            )

    def test_measured_record_cannot_claim_observed_without_readback(self):
        record = self._record("BASELINE", readback=False)
        with self.assertRaisesRegex(ValueError, "INDEPENDENT_READBACK"):
            OwnerValueMissionRecord.from_mapping(record)

    def test_unmeasured_record_cannot_claim_observed_owner_value(self):
        record = self._record(
            "BASELINE",
            intervention_seconds=None,
            intervention_count=None,
            clarifications=None,
            corrections=None,
            elapsed=None,
            ratio=None,
            accepted=None,
            readback=False,
            evidence_class=OBSERVED_OWNER_VALUE,
            measurement_state=UNMEASURED,
        )
        with self.assertRaisesRegex(ValueError, "UNMEASURED_CANNOT_CLAIM_OBSERVED"):
            OwnerValueMissionRecord.from_mapping(record)

    def test_negative_and_out_of_range_metrics_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "OWNER_SECONDS_NONNEGATIVE"):
            OwnerValueMissionRecord.from_mapping(
                self._record("BASELINE", intervention_seconds=-1)
            )
        with self.assertRaisesRegex(ValueError, "OUTPUT_RATIO_INVALID"):
            OwnerValueMissionRecord.from_mapping(
                self._record("BASELINE", ratio=1.1)
            )

    def test_pair_compiles_exactly_to_existing_court_contract(self):
        baseline = OwnerValueMissionRecord.from_mapping(
            self._record(
                "BASELINE",
                intervention_seconds=180.0,
                intervention_count=3,
                clarifications=2,
                corrections=1,
                elapsed=420.0,
                proof_refs=("proof:baseline:provider",),
            )
        )
        candidate = OwnerValueMissionRecord.from_mapping(
            self._record(
                "BUBBLES",
                intervention_seconds=60.0,
                intervention_count=1,
                clarifications=1,
                corrections=0,
                elapsed=240.0,
                proof_refs=("proof:candidate:provider",),
            )
        )
        compiled = OwnerValuePairCompiler.compile(baseline, candidate)
        payload = compiled.to_court_mapping()
        self.assertEqual(payload["evidence_mode"], OBSERVED_OWNER_VALUE)
        self.assertEqual(payload["baseline_owner_minutes"], 3.0)
        self.assertEqual(payload["candidate_owner_minutes"], 1.0)
        self.assertEqual(payload["baseline_owner_interventions"], 3)
        self.assertEqual(payload["candidate_owner_interventions"], 1)
        self.assertEqual(len(payload["proof_refs"]), 2)
        self.assertNotIn("baseline_observation_id", payload)
        self.assertNotIn("candidate_observation_id", payload)

    def test_pair_identity_mismatch_fails_closed(self):
        baseline = OwnerValueMissionRecord.from_mapping(self._record("BASELINE"))
        candidate = OwnerValueMissionRecord.from_mapping(
            self._record("BUBBLES", oracle_id="oracle-other")
        )
        with self.assertRaisesRegex(ValueError, "ORACLE_ID_MISMATCH"):
            OwnerValuePairCompiler.compile(baseline, candidate)

    def test_pair_requires_distinct_proof_references(self):
        baseline = OwnerValueMissionRecord.from_mapping(
            self._record("BASELINE", proof_refs=("proof:same",))
        )
        candidate = OwnerValueMissionRecord.from_mapping(
            self._record("BUBBLES", proof_refs=("proof:same",))
        )
        with self.assertRaisesRegex(ValueError, "DISTINCT_PROOF_REFS"):
            OwnerValuePairCompiler.compile(baseline, candidate)

    def test_baseline_owner_time_must_be_positive(self):
        baseline = OwnerValueMissionRecord.from_mapping(
            self._record("BASELINE", intervention_seconds=0.0)
        )
        candidate = OwnerValueMissionRecord.from_mapping(
            self._record("BUBBLES", intervention_seconds=0.0)
        )
        with self.assertRaisesRegex(ValueError, "BASELINE_OWNER_TIME_POSITIVE"):
            OwnerValuePairCompiler.compile(baseline, candidate)

    def test_exact_replay_deduplicates_through_sentinel_ingress(self):
        _, observation = OwnerValueMissionObservationAdapter.adapt(
            self._record("BASELINE")
        )
        collected = ObservationIngressBatch.collect((observation, observation))
        self.assertEqual(len(collected), 1)

    def test_missing_proof_reference_fails_closed(self):
        record = self._record("BASELINE")
        record["proof_refs"] = ()
        with self.assertRaisesRegex(ValueError, "PROOF_REF_REQUIRED"):
            OwnerValueMissionRecord.from_mapping(record)


if __name__ == "__main__":
    unittest.main()
