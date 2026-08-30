from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.empirical_measurement_fabric import (
    AcquisitionRoute,
    DimensionBound,
    FederationObservationPacket,
    compile_measurement_rows,
    plan_measurement_acquisition,
)
from frontier_convergence.os_core import ExperimentOption


class EmpiricalMeasurementFabricTests(unittest.TestCase):
    def _telemetry(self):
        return {
            "sovara.experiment.information_gain": 8.0,
            "sovara.mission.value": 80.0,
            "sovara.proof.strength_gain": 7.0,
            "sovara.experiment.reversibility": 1.0,
            "sovara.mission.cost": 20.0,
            "sovara.mission.elapsed_seconds": 30.0,
            "sovara.owner.intervention_seconds": 0.0,
            "sovara.mission.risk": 2.0,
        }

    def _packet(self, **overrides):
        payload = {
            "experiment_id": "EXP-FED-001",
            "label": "Federation empirical mission",
            "telemetry": self._telemetry(),
            "observed_at_sast": "2026-08-30T12:17:00+02:00",
            "source_system": "SOVARA_MCF",
            "source_work_id": "MISSION-001",
            "evidence_refs": ("mission:receipt:001", "workflow:run:001"),
            "evidence_class": "OBSERVED_FEDERATION_EXPERIMENT",
            "synthetic": False,
        }
        payload.update(overrides)
        return FederationObservationPacket(**payload)

    def _bounds(self):
        return (
            DimensionBound("expected_information_gain", ("sovara.experiment.information_gain",), 10.0, ("target:info:001",)),
            DimensionBound("mission_value", ("sovara.mission.value",), 100.0, ("target:value:001",)),
            DimensionBound("proof_strength_gain", ("sovara.proof.strength_gain",), 10.0, ("target:proof:001",)),
            DimensionBound("reversibility", ("sovara.experiment.reversibility",), 1.0, ("target:reversibility:001",)),
            DimensionBound("estimated_cost", ("sovara.mission.cost",), 100.0, ("ceiling:cost:001",)),
            DimensionBound("latency_burden", ("sovara.mission.elapsed_seconds",), 100.0, ("ceiling:latency:001",)),
            DimensionBound("owner_burden", ("sovara.owner.intervention_seconds",), 60.0, ("ceiling:owner:001",)),
            DimensionBound("risk", ("sovara.mission.risk",), 10.0, ("ceiling:risk:001",)),
        )

    def _option(self, label: str, info: float, refs=("route:evidence",)):
        return ExperimentOption.create(
            label=label,
            expected_information_gain=info,
            mission_value=0.5,
            proof_strength_gain=0.5,
            reversibility=1.0,
            estimated_cost=0.1,
            latency_burden=0.1,
            owner_burden=0.0,
            risk=0.1,
            evidence_refs=refs,
        )

    def test_complete_packet_compiles_all_eight_dimensions_and_existing_normalizer(self):
        report = compile_measurement_rows(self._packet(), self._bounds())
        self.assertEqual("MEASUREMENT_PACKET_READY", report.state)
        self.assertEqual("OBSERVED_OPTION_READY", report.normalized_state)
        self.assertEqual(8, len(report.rows))
        self.assertIsNotNone(report.option_key)
        by_dimension = {row["Dimension"]: row for row in report.rows}
        self.assertEqual(0.8, by_dimension["mission_value"]["Normalized_Value"])
        self.assertEqual(0.2, by_dimension["estimated_cost"]["Normalized_Value"])
        self.assertEqual(0.0, by_dimension["owner_burden"]["Normalized_Value"])
        self.assertIn("target:value:001", by_dimension["mission_value"]["Measurement_Evidence_Refs"])
        self.assertIn("mission:receipt:001", by_dimension["mission_value"]["Measurement_Evidence_Refs"])

    def test_measurement_ids_are_deterministic_for_same_source_identity(self):
        first = compile_measurement_rows(self._packet(), self._bounds())
        second = compile_measurement_rows(self._packet(), self._bounds())
        self.assertEqual(
            tuple(row["Measurement_ID"] for row in first.rows),
            tuple(row["Measurement_ID"] for row in second.rows),
        )

    def test_missing_dimensions_remain_partial_instead_of_being_inferred(self):
        telemetry = self._telemetry()
        telemetry.pop("sovara.experiment.information_gain")
        telemetry.pop("sovara.proof.strength_gain")
        report = compile_measurement_rows(self._packet(telemetry=telemetry), self._bounds())
        self.assertEqual("PARTIAL_MEASUREMENT_PACKET", report.state)
        self.assertEqual(
            ("expected_information_gain", "proof_strength_gain"),
            report.missing_dimensions,
        )
        self.assertEqual(6, len(report.rows))
        self.assertIsNone(report.option_key)

    def test_alias_conflict_fails_closed(self):
        telemetry = self._telemetry()
        telemetry["mission.value"] = 70.0
        bounds = list(self._bounds())
        bounds[1] = DimensionBound(
            "mission_value",
            ("mission.value", "sovara.mission.value"),
            100.0,
            ("target:value:001",),
        )
        report = compile_measurement_rows(self._packet(telemetry=telemetry), tuple(bounds))
        self.assertEqual("HELD_FIELD_CONFLICT", report.state)
        self.assertEqual(("mission_value",), report.conflict_dimensions)

    def test_bound_without_provenance_is_rejected(self):
        bounds = list(self._bounds())
        bounds[0] = DimensionBound(
            "expected_information_gain",
            ("sovara.experiment.information_gain",),
            10.0,
            (),
        )
        report = compile_measurement_rows(self._packet(), tuple(bounds))
        self.assertEqual("HELD_INVALID_MEASUREMENT", report.state)
        self.assertIn(
            "DIMENSION_BOUND_PROVENANCE_REQUIRED:expected_information_gain",
            report.blockers,
        )

    def test_observation_above_declared_bound_fails_closed(self):
        telemetry = self._telemetry()
        telemetry["sovara.mission.risk"] = 11.0
        report = compile_measurement_rows(self._packet(telemetry=telemetry), self._bounds())
        self.assertEqual("HELD_INVALID_MEASUREMENT", report.state)
        self.assertIn("OBSERVED_DIMENSION_EXCEEDS_BOUND:risk", report.blockers)

    def test_duplicate_dimension_bound_is_rejected(self):
        duplicate = DimensionBound(
            "risk",
            ("other.risk",),
            10.0,
            ("ceiling:risk:002",),
        )
        report = compile_measurement_rows(self._packet(), self._bounds() + (duplicate,))
        self.assertEqual("HELD_INVALID_MEASUREMENT", report.state)
        self.assertIn("DUPLICATE_DIMENSION_BOUND:risk", report.blockers)

    def test_synthetic_packet_compiles_but_cannot_become_observed_option(self):
        packet = self._packet(evidence_class="PUBLIC_SYNTHETIC", synthetic=True)
        report = compile_measurement_rows(packet, self._bounds())
        self.assertEqual("SYNTHETIC_PACKET_HELD_BY_DESIGN", report.state)
        self.assertEqual("HELD_OBSERVED_EXPERIMENT_REQUIRED", report.normalized_state)
        self.assertIsNone(report.option_key)
        self.assertTrue(all(row["Synthetic"] for row in report.rows))

    def test_real_packet_cannot_launder_synthetic_evidence_class(self):
        report = compile_measurement_rows(
            self._packet(evidence_class="PUBLIC_SYNTHETIC", synthetic=False),
            self._bounds(),
        )
        self.assertEqual("HELD_INVALID_MEASUREMENT", report.state)
        self.assertIn("OBSERVATION_EVIDENCE_CLASS_MISMATCH", report.blockers)

    def test_acquisition_planner_prefers_route_covering_more_missing_dimensions(self):
        routes = (
            AcquisitionRoute(
                "proof-suite",
                ("expected_information_gain", "proof_strength_gain"),
                self._option("proof suite", 0.6),
            ),
            AcquisitionRoute(
                "single-info",
                ("expected_information_gain",),
                self._option("single info", 0.95),
            ),
            AcquisitionRoute(
                "reversibility-probe",
                ("reversibility",),
                self._option("reversibility probe", 0.5),
            ),
        )
        plan = plan_measurement_acquisition(
            ("expected_information_gain", "proof_strength_gain", "reversibility"),
            routes,
        )
        self.assertEqual("ACQUISITION_PLAN_READY", plan.state)
        self.assertEqual("proof-suite", plan.selected_route_ids[0])
        self.assertEqual("reversibility-probe", plan.selected_route_ids[1])
        self.assertEqual((), plan.unresolved_dimensions)

    def test_acquisition_planner_uses_fcos_economics_to_break_equal_coverage_tie(self):
        routes = (
            AcquisitionRoute(
                "lower-value",
                ("risk",),
                self._option("lower value", 0.2),
            ),
            AcquisitionRoute(
                "higher-value",
                ("risk",),
                self._option("higher value", 0.9),
            ),
        )
        plan = plan_measurement_acquisition(("risk",), routes)
        self.assertEqual(("higher-value",), plan.selected_route_ids)

    def test_acquisition_plan_reports_unresolved_dimensions_without_inventing_route(self):
        plan = plan_measurement_acquisition(
            ("risk", "owner_burden"),
            (
                AcquisitionRoute(
                    "risk-only",
                    ("risk",),
                    self._option("risk only", 0.5),
                ),
            ),
        )
        self.assertEqual("ACQUISITION_PLAN_PARTIAL", plan.state)
        self.assertEqual(("owner_burden",), plan.unresolved_dimensions)

    def test_unknown_route_coverage_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "UNKNOWN_ROUTE_COVERAGE"):
            plan_measurement_acquisition(
                ("risk",),
                (
                    AcquisitionRoute(
                        "bad-route",
                        ("unknown_dimension",),
                        self._option("bad route", 0.5),
                    ),
                ),
            )

    def test_acquisition_route_requires_evidence(self):
        with self.assertRaisesRegex(ValueError, "ACQUISITION_ROUTE_EVIDENCE_REQUIRED"):
            plan_measurement_acquisition(
                ("risk",),
                (
                    AcquisitionRoute(
                        "unproven-route",
                        ("risk",),
                        self._option("unproven route", 0.5, refs=()),
                    ),
                ),
            )


if __name__ == "__main__":
    unittest.main()
