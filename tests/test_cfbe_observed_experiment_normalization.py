from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.observed_experiment_normalization import (
    OBSERVED_EXPERIMENT_EVIDENCE,
    OBSERVED_MEASUREMENT_EVIDENCE,
    ObservedDimensionMeasurement,
    ObservedExperimentMeasurements,
    evaluate_observed_experiment,
)
from benchmarking.cfbe_omega.v4_capability_foundry import (
    CapabilityFoundryInput,
    ConfidenceEvidence,
    ExperimentEvidence,
    GapObservation,
    RegressionBaselineEvidence,
    evaluate_capability_foundry_readiness,
)


class ObservedExperimentNormalizationTests(unittest.TestCase):
    def _measurement(self, dimension, numerator, denominator=10.0, **overrides):
        return ObservedDimensionMeasurement(
            experiment_id=overrides.pop("experiment_id", "EXP-REAL-001"),
            dimension=dimension,
            numerator=numerator,
            denominator=denominator,
            evidence_refs=overrides.pop(
                "evidence_refs",
                (f"receipt:EXP-REAL-001:{dimension}",),
            ),
            evidence_class=overrides.pop(
                "evidence_class",
                OBSERVED_MEASUREMENT_EVIDENCE,
            ),
            synthetic=overrides.pop("synthetic", False),
        )

    def _packet(self, **overrides):
        measurements = overrides.pop(
            "measurements",
            (
                self._measurement("expected_information_gain", 8.0),
                self._measurement("mission_value", 9.0),
                self._measurement("proof_strength_gain", 7.0),
                self._measurement("reversibility", 10.0),
                self._measurement("estimated_cost", 2.0),
                self._measurement("latency_burden", 1.0),
                self._measurement("owner_burden", 0.0),
                self._measurement("risk", 2.0),
            ),
        )
        return ObservedExperimentMeasurements(
            experiment_id=overrides.pop("experiment_id", "EXP-REAL-001"),
            label=overrides.pop("label", "real bounded Federation experiment"),
            measurements=measurements,
            experiment_evidence_refs=overrides.pop(
                "experiment_evidence_refs",
                ("workflow:run:001", "value:receipt:001"),
            ),
            evidence_class=overrides.pop(
                "evidence_class",
                OBSERVED_EXPERIMENT_EVIDENCE,
            ),
            synthetic=overrides.pop("synthetic", False),
        )

    def test_complete_provenance_bound_measurements_compile_fcos_option(self):
        report = evaluate_observed_experiment(self._packet())
        self.assertEqual(report.state, "OBSERVED_OPTION_READY")
        self.assertIsNotNone(report.option)
        self.assertEqual(report.normalized_values["expected_information_gain"], 0.8)
        self.assertEqual(report.normalized_values["mission_value"], 0.9)
        self.assertEqual(report.normalized_values["proof_strength_gain"], 0.7)
        self.assertEqual(report.normalized_values["reversibility"], 1.0)
        self.assertEqual(report.normalized_values["estimated_cost"], 0.2)
        self.assertEqual(report.normalized_values["latency_burden"], 0.1)
        self.assertEqual(report.normalized_values["owner_burden"], 0.0)
        self.assertEqual(report.normalized_values["risk"], 0.2)
        self.assertIn("workflow:run:001", report.option.evidence_refs)
        self.assertIn(
            "receipt:EXP-REAL-001:mission_value",
            report.option.evidence_refs,
        )

    def test_synthetic_experiment_cannot_compile_observed_option(self):
        report = evaluate_observed_experiment(self._packet(synthetic=True))
        self.assertEqual(report.state, "HELD_OBSERVED_EXPERIMENT_REQUIRED")
        self.assertIsNone(report.option)

    def test_synthetic_measurement_cannot_satisfy_dimension(self):
        measurements = list(self._packet().measurements)
        measurements[0] = self._measurement(
            "expected_information_gain",
            8.0,
            synthetic=True,
        )
        report = evaluate_observed_experiment(
            self._packet(measurements=tuple(measurements))
        )
        self.assertEqual(report.state, "HELD_OBSERVED_MEASUREMENT_REQUIRED")
        self.assertIsNone(report.option)

    def test_qualitative_category_is_not_inferred_into_numeric_value(self):
        measurements = list(self._packet().measurements)
        measurements[1] = self._measurement("mission_value", "VERY_HIGH")
        report = evaluate_observed_experiment(
            self._packet(measurements=tuple(measurements))
        )
        self.assertEqual(report.state, "INSTRUMENTED_MEASUREMENTS_INCOMPLETE")
        self.assertIn("MEASUREMENT_NUMERIC_VALUE_REQUIRED:mission_value", report.blockers)
        self.assertIn("MISSING_DIMENSION:mission_value", report.blockers)
        self.assertIsNone(report.option)

    def test_cross_experiment_stitching_fails_closed(self):
        measurements = list(self._packet().measurements)
        measurements[2] = self._measurement(
            "proof_strength_gain",
            7.0,
            experiment_id="EXP-OTHER-002",
        )
        report = evaluate_observed_experiment(
            self._packet(measurements=tuple(measurements))
        )
        self.assertEqual(report.state, "HELD_MEASUREMENT_CONFLICT")
        self.assertIn(
            "CROSS_EXPERIMENT_STITCHING_PROHIBITED:proof_strength_gain",
            report.blockers,
        )

    def test_duplicate_dimension_fails_closed(self):
        packet = self._packet()
        duplicate = self._measurement("risk", 1.0)
        report = evaluate_observed_experiment(
            self._packet(measurements=packet.measurements + (duplicate,))
        )
        self.assertEqual(report.state, "HELD_MEASUREMENT_CONFLICT")
        self.assertIn("DUPLICATE_DIMENSION:risk", report.blockers)

    def test_measurement_must_not_exceed_declared_bound(self):
        measurements = list(self._packet().measurements)
        measurements[-1] = self._measurement("risk", 11.0)
        report = evaluate_observed_experiment(
            self._packet(measurements=tuple(measurements))
        )
        self.assertEqual(report.state, "INSTRUMENTED_MEASUREMENTS_INCOMPLETE")
        self.assertIn("MEASUREMENT_EXCEEDS_DECLARED_BOUND:risk", report.blockers)

    def test_missing_measurement_provenance_fails_closed(self):
        measurements = list(self._packet().measurements)
        measurements[4] = self._measurement(
            "estimated_cost",
            2.0,
            evidence_refs=(),
        )
        report = evaluate_observed_experiment(
            self._packet(measurements=tuple(measurements))
        )
        self.assertEqual(report.state, "HELD_PROVENANCE_REQUIRED")
        self.assertIsNone(report.option)

    def test_observed_option_plugs_into_existing_v4_foundry_gate(self):
        normalized = evaluate_observed_experiment(self._packet())
        self.assertIsNotNone(normalized.option)
        packet = CapabilityFoundryInput(
            experiment=ExperimentEvidence(normalized.option),
            confidence=ConfidenceEvidence(
                0.9,
                ("cfbe:confidence:EXP-REAL-001",),
            ),
            gap_observations=(
                GapObservation(
                    "gap:incident:001",
                    "proof failure diagnostics require extra CI cycles",
                    ("github:run:failure:001",),
                ),
                GapObservation(
                    "gap:incident:002",
                    "proof failure diagnostics require extra CI cycles",
                    ("github:run:failure:002",),
                ),
            ),
            regression_baseline=RegressionBaselineEvidence(
                "proofos-pre-diagnostics-main",
                ("git:main:baseline",),
            ),
        )
        foundry = evaluate_capability_foundry_readiness(packet)
        self.assertEqual(foundry.state, "DATA_READY")
        self.assertGreater(foundry.opportunity_gradient, 0.0)


if __name__ == "__main__":
    unittest.main()
