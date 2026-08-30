from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.measurement_sheet_ingestion import (
    assemble_observed_experiment_rows,
)
from benchmarking.cfbe_omega.observed_experiment_normalization import (
    evaluate_observed_experiment,
)


DIMENSIONS = (
    ("expected_information_gain", 8.0),
    ("mission_value", 9.0),
    ("proof_strength_gain", 7.0),
    ("reversibility", 10.0),
    ("estimated_cost", 2.0),
    ("latency_burden", 1.0),
    ("owner_burden", 0.0),
    ("risk", 2.0),
)


class MeasurementSheetIngestionTests(unittest.TestCase):
    def _row(self, dimension: str, numerator: float, **overrides):
        denominator = overrides.pop("Denominator", 10.0)
        row = {
            "Measurement_ID": f"M-{dimension}",
            "Experiment_ID": "EXP-REAL-001",
            "Experiment_Label": "real bounded Federation experiment",
            "Dimension": dimension,
            "Numerator": numerator,
            "Denominator": denominator,
            "Normalized_Value": round(float(numerator) / float(denominator), 9),
            "Measurement_Evidence_Class": "OBSERVED_FEDERATION_MEASUREMENT",
            "Experiment_Evidence_Class": "OBSERVED_FEDERATION_EXPERIMENT",
            "Synthetic": False,
            "Measurement_Evidence_Refs": f"receipt:{dimension}; verifier:{dimension}",
            "Experiment_Evidence_Refs": "workflow:run:001; value:receipt:001",
            "State": "VERIFIED_NORMALIZED",
        }
        row.update(overrides)
        return row

    def _rows(self):
        return [self._row(dimension, numerator) for dimension, numerator in DIMENSIONS]

    def test_complete_sheet_rows_compile_through_existing_normalizer(self):
        packet = assemble_observed_experiment_rows(self._rows())
        report = evaluate_observed_experiment(packet)
        self.assertEqual("EXP-REAL-001", packet.experiment_id)
        self.assertEqual("OBSERVED_OPTION_READY", report.state)
        self.assertIsNotNone(report.option)
        self.assertEqual(0.9, report.normalized_values["mission_value"])
        self.assertIn("workflow:run:001", packet.experiment_evidence_refs)
        self.assertIn("receipt:mission_value", report.option.evidence_refs)

    def test_blank_stored_normalized_value_is_recomputed_from_raw_measurement(self):
        rows = self._rows()
        rows[1]["Normalized_Value"] = ""
        packet = assemble_observed_experiment_rows(rows)
        report = evaluate_observed_experiment(packet)
        self.assertEqual("OBSERVED_OPTION_READY", report.state)
        self.assertEqual(0.9, report.normalized_values["mission_value"])

    def test_stored_normalized_value_is_assertion_not_source_of_truth(self):
        rows = self._rows()
        rows[1]["Normalized_Value"] = 0.2
        with self.assertRaisesRegex(ValueError, "NORMALIZED_VALUE_MISMATCH:M-mission_value"):
            assemble_observed_experiment_rows(rows)

    def test_mixed_experiment_rows_are_rejected_before_packet_creation(self):
        rows = self._rows()
        rows[-1]["Experiment_ID"] = "EXP-OTHER-002"
        with self.assertRaisesRegex(ValueError, "MEASUREMENT_MIXED_EXPERIMENT_IDS"):
            assemble_observed_experiment_rows(rows)

    def test_conflicting_labels_fail_closed(self):
        rows = self._rows()
        rows[-1]["Experiment_Label"] = "different experiment"
        with self.assertRaisesRegex(ValueError, "MEASUREMENT_EXPERIMENT_LABEL_CONFLICT"):
            assemble_observed_experiment_rows(rows)

    def test_malformed_synthetic_flag_fails_closed(self):
        rows = self._rows()
        rows[0]["Synthetic"] = "NOPE"
        with self.assertRaisesRegex(ValueError, "MEASUREMENT_SYNTHETIC_BOOLEAN_REQUIRED"):
            assemble_observed_experiment_rows(rows)

    def test_held_or_incomplete_row_is_not_ingestion_eligible(self):
        rows = self._rows()
        rows[0]["State"] = "HELD_INCOMPLETE"
        with self.assertRaisesRegex(ValueError, "MEASUREMENT_ROW_NOT_ELIGIBLE"):
            assemble_observed_experiment_rows(rows)

    def test_semicolon_and_newline_refs_are_normalized_and_deduplicated(self):
        rows = self._rows()
        rows[0]["Experiment_Evidence_Refs"] = "workflow:run:001\nvalue:receipt:001;workflow:run:001"
        packet = assemble_observed_experiment_rows(rows)
        self.assertEqual(
            ("value:receipt:001", "workflow:run:001"),
            packet.experiment_evidence_refs,
        )

    def test_public_synthetic_rows_are_assembled_but_cannot_promote(self):
        rows = self._rows()
        for row in rows:
            row["Synthetic"] = "TRUE"
            row["Measurement_Evidence_Class"] = "PUBLIC_SYNTHETIC"
            row["Experiment_Evidence_Class"] = "PUBLIC_SYNTHETIC"
        packet = assemble_observed_experiment_rows(rows)
        report = evaluate_observed_experiment(packet)
        self.assertTrue(packet.synthetic)
        self.assertEqual("HELD_OBSERVED_EXPERIMENT_REQUIRED", report.state)
        self.assertIsNone(report.option)

    def test_explicit_experiment_id_must_match_every_row(self):
        with self.assertRaisesRegex(ValueError, "MEASUREMENT_MIXED_EXPERIMENT_IDS"):
            assemble_observed_experiment_rows(self._rows(), experiment_id="EXP-OTHER-002")


if __name__ == "__main__":
    unittest.main()
