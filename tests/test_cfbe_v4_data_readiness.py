from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.v4_data_readiness import (
    MissionTelemetryEvidence,
    evaluate_objective_ecology_readiness,
)


class CFBEV4DataReadinessTests(unittest.TestCase):
    def _record(self, **overrides):
        telemetry = {
            "sovara.outcome.accepted": True,
            "sovara.mission.value": 0.9,
            "sovara.mission.cost": 0.1,
            "sovara.mission.risk": 0.2,
        }
        telemetry.update(overrides.pop("telemetry", {}))
        return MissionTelemetryEvidence(
            mission_id=overrides.pop("mission_id", "MSN-REAL-001"),
            telemetry=telemetry,
            evidence_refs=overrides.pop("evidence_refs", ("receipt:real-001",)),
            evidence_class=overrides.pop("evidence_class", "REAL_MISSION"),
        )

    def test_existing_sovara_telemetry_aliases_can_reach_data_ready(self):
        report = evaluate_objective_ecology_readiness((self._record(),))
        self.assertEqual(report.state, "DATA_READY")
        self.assertEqual(report.qualifying_mission_ids, ("MSN-REAL-001",))
        self.assertEqual(report.missing_fields, ())
        self.assertEqual(report.conflict_fields, ())

    def test_synthetic_canary_never_promotes_data_ready(self):
        report = evaluate_objective_ecology_readiness(
            (self._record(evidence_class="PUBLIC_SYNTHETIC"),)
        )
        self.assertEqual(report.state, "INSTRUMENTED_REAL_MISSION_DATA_REQUIRED")
        self.assertEqual(report.qualifying_mission_ids, ())

    def test_real_mission_without_provenance_fails_closed(self):
        report = evaluate_objective_ecology_readiness(
            (self._record(evidence_refs=()),)
        )
        self.assertEqual(report.state, "HELD_PROVENANCE_REQUIRED")

    def test_missing_required_field_fails_closed(self):
        telemetry = {
            "sovara.outcome.accepted": True,
            "sovara.mission.value": 0.9,
            "sovara.mission.cost": 0.1,
        }
        report = evaluate_objective_ecology_readiness(
            (self._record(telemetry=telemetry),)
        )
        self.assertEqual(report.state, "INSTRUMENTED_MISSING_REQUIRED_DATA")
        self.assertIn("mission.risk", report.missing_fields)

    def test_conflicting_aliases_fail_closed(self):
        telemetry = {
            "mission.accepted": False,
            "sovara.outcome.accepted": True,
            "sovara.mission.value": 0.9,
            "sovara.mission.cost": 0.1,
            "sovara.mission.risk": 0.2,
        }
        report = evaluate_objective_ecology_readiness(
            (self._record(telemetry=telemetry),)
        )
        self.assertEqual(report.state, "HELD_FIELD_CONFLICT")
        self.assertIn("mission.accepted", report.conflict_fields)

    def test_invalid_negative_value_telemetry_fails_closed(self):
        telemetry = {
            "sovara.outcome.accepted": True,
            "sovara.mission.value": -1.0,
            "sovara.mission.cost": 0.1,
            "sovara.mission.risk": 0.2,
        }
        report = evaluate_objective_ecology_readiness(
            (self._record(telemetry=telemetry),)
        )
        self.assertEqual(report.state, "HELD_INVALID_VALUE_TELEMETRY")


if __name__ == "__main__":
    unittest.main()
