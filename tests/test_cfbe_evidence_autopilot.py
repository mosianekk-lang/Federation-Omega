from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.evidence_autopilot import (
    DimensionMeasurementContract,
    ExperimentMeasurementContract,
    MetricObservation,
    compile_measurement_rows,
    compile_observed_experiment,
)


DIMENSIONS = (
    ("expected_information_gain", "cfbe.information.questions_resolved", 8.0, 10.0),
    ("mission_value", "sovara.mission.value", 9.0, 10.0),
    ("proof_strength_gain", "cfbe.proof.axes_gained", 7.0, 10.0),
    ("reversibility", "sovara.rollback.available", True, 1.0),
    ("estimated_cost", "sovara.mission.cost", 2.0, 10.0),
    ("latency_burden", "sovara.mission.elapsed_seconds", 1.0, 10.0),
    ("owner_burden", "sovara.owner.intervention_seconds", 0.0, 10.0),
    ("risk", "sovara.mission.risk", 2.0, 10.0),
)


class CFBEEvidenceAutopilotTests(unittest.TestCase):
    def _observation(self, dimension, metric_key, value, **overrides):
        return MetricObservation(
            observation_id=overrides.pop("observation_id", f"OBS-{dimension}"),
            experiment_id=overrides.pop("experiment_id", "EXP-REAL-001"),
            observed_at_sast=overrides.pop("observed_at_sast", "2026-08-30T12:00:00+02:00"),
            source_system=overrides.pop("source_system", "SOVARA_MCF"),
            source_work_id=overrides.pop("source_work_id", f"WORK-{dimension}"),
            metrics=overrides.pop("metrics", {metric_key: value}),
            evidence_refs=overrides.pop("evidence_refs", (f"receipt:{dimension}:001",)),
            synthetic=overrides.pop("synthetic", False),
        )

    def _contract(self, **overrides):
        dimensions = overrides.pop(
            "dimensions",
            tuple(
                DimensionMeasurementContract(
                    dimension=dimension,
                    observation_id=f"OBS-{dimension}",
                    metric_key=metric_key,
                    denominator=denominator,
                    denominator_ref=f"contract:{dimension}:bound",
                    semantics=f"observed {metric_key} / pre-registered bound",
                )
                for dimension, metric_key, _, denominator in DIMENSIONS
            ),
        )
        return ExperimentMeasurementContract(
            experiment_id=overrides.pop("experiment_id", "EXP-REAL-001"),
            label=overrides.pop("label", "real bounded Federation experiment"),
            experiment_evidence_refs=overrides.pop(
                "experiment_evidence_refs",
                ("mission:EXP-REAL-001", "workflow:run:001"),
            ),
            dimensions=dimensions,
            evidence_class=overrides.pop("evidence_class", "OBSERVED_FEDERATION_EXPERIMENT"),
        )

    def _observations(self):
        return tuple(
            self._observation(dimension, metric_key, value)
            for dimension, metric_key, value, _ in DIMENSIONS
        )

    def test_complete_real_telemetry_compiles_end_to_end(self):
        rows, packet, report = compile_observed_experiment(self._contract(), self._observations())
        self.assertEqual(8, len(rows))
        self.assertEqual("OBSERVED_OPTION_READY", report.state)
        self.assertIsNotNone(report.option)
        self.assertEqual(0.9, report.normalized_values["mission_value"])
        self.assertEqual(1.0, report.normalized_values["reversibility"])
        self.assertTrue(all(row["State"] == "OBSERVED_RAW" for row in rows))
        self.assertEqual("EXP-REAL-001", packet.experiment_id)

    def test_measurement_ids_are_deterministic(self):
        first = compile_measurement_rows(self._contract(), self._observations())
        second = compile_measurement_rows(self._contract(), self._observations())
        self.assertEqual(
            [row["Measurement_ID"] for row in first],
            [row["Measurement_ID"] for row in second],
        )

    def test_synthetic_observation_fails_before_row_creation(self):
        observations = list(self._observations())
        observations[0] = self._observation(
            "expected_information_gain",
            "cfbe.information.questions_resolved",
            8.0,
            synthetic=True,
        )
        with self.assertRaisesRegex(ValueError, "AUTOPILOT_SYNTHETIC_OBSERVATION_REJECTED"):
            compile_measurement_rows(self._contract(), observations)

    def test_cross_experiment_observation_fails_closed(self):
        observations = list(self._observations())
        observations[-1] = self._observation(
            "risk",
            "sovara.mission.risk",
            2.0,
            experiment_id="EXP-OTHER-002",
        )
        with self.assertRaisesRegex(ValueError, "AUTOPILOT_CROSS_EXPERIMENT_OBSERVATION:risk"):
            compile_measurement_rows(self._contract(), observations)

    def test_missing_metric_fails_closed(self):
        observations = list(self._observations())
        observations[1] = self._observation(
            "mission_value",
            "sovara.mission.value",
            9.0,
            metrics={"wrong.metric": 9.0},
        )
        with self.assertRaisesRegex(ValueError, "AUTOPILOT_METRIC_NOT_FOUND:mission_value"):
            compile_measurement_rows(self._contract(), observations)

    def test_qualitative_metric_is_not_converted_to_score(self):
        observations = list(self._observations())
        observations[1] = self._observation(
            "mission_value",
            "sovara.mission.value",
            "VERY_HIGH",
        )
        with self.assertRaisesRegex(ValueError, "OBSERVED_METRIC_NUMERIC_REQUIRED:mission_value"):
            compile_measurement_rows(self._contract(), observations)

    def test_missing_denominator_provenance_fails_closed(self):
        dimensions = list(self._contract().dimensions)
        target = dimensions[4]
        dimensions[4] = DimensionMeasurementContract(
            dimension=target.dimension,
            observation_id=target.observation_id,
            metric_key=target.metric_key,
            denominator=target.denominator,
            denominator_ref="",
            semantics=target.semantics,
        )
        with self.assertRaisesRegex(ValueError, "AUTOPILOT_DENOMINATOR_PROVENANCE_REQUIRED:estimated_cost"):
            compile_measurement_rows(self._contract(dimensions=tuple(dimensions)), self._observations())

    def test_incomplete_dimension_contract_is_rejected(self):
        dimensions = self._contract().dimensions[:-1]
        with self.assertRaisesRegex(ValueError, "AUTOPILOT_DIMENSION_CONTRACT_INCOMPLETE"):
            compile_measurement_rows(self._contract(dimensions=dimensions), self._observations())

    def test_observation_provenance_is_mandatory(self):
        observations = list(self._observations())
        observations[5] = self._observation(
            "latency_burden",
            "sovara.mission.elapsed_seconds",
            1.0,
            evidence_refs=(),
        )
        with self.assertRaisesRegex(ValueError, "AUTOPILOT_OBSERVATION_PROVENANCE_REQUIRED:latency_burden"):
            compile_measurement_rows(self._contract(), observations)

    def test_bound_excess_fails_closed(self):
        observations = list(self._observations())
        observations[4] = self._observation(
            "estimated_cost",
            "sovara.mission.cost",
            11.0,
        )
        with self.assertRaisesRegex(ValueError, "MEASUREMENT_EXCEEDS_DECLARED_BOUND:estimated_cost"):
            compile_measurement_rows(self._contract(), observations)

    def test_compiler_does_not_claim_independent_verification(self):
        rows = compile_measurement_rows(self._contract(), self._observations())
        self.assertTrue(all(row["Verification_Refs"] == "" for row in rows))
        self.assertTrue(all(row["State"] == "OBSERVED_RAW" for row in rows))
        self.assertTrue(all("not independent" in row["Truth_Boundary"] for row in rows))


if __name__ == "__main__":
    unittest.main()
