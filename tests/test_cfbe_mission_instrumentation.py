from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.mission_instrumentation import enrich_mission_telemetry


class CFBEMissionInstrumentationTests(unittest.TestCase):
    def _base(self):
        return {
            "sovara.mission.value": 8.0,
            "sovara.mission.cost": 2.0,
            "sovara.mission.risk": 1.0,
            "sovara.owner.intervention_seconds": 30.0,
            "sovara.rollback.available": True,
            "sovara.evidence.coverage": 0.8,
        }

    def test_enrichment_is_additive_and_non_mutating(self):
        base = self._base()
        enriched = enrich_mission_telemetry(
            base,
            information_questions_resolved=7,
            proof_axes_gained=6,
            elapsed_seconds=120,
        )
        self.assertNotIn("cfbe.information.questions_resolved", base)
        self.assertEqual(7.0, enriched["cfbe.information.questions_resolved"])
        self.assertEqual(6.0, enriched["cfbe.proof.axes_gained"])
        self.assertEqual(120.0, enriched["sovara.mission.elapsed_seconds"])
        self.assertEqual(0.8, enriched["sovara.evidence.coverage"])

    def test_missing_existing_economic_field_fails_closed(self):
        base = self._base()
        base.pop("sovara.mission.value")
        with self.assertRaisesRegex(ValueError, "MISSION_INSTRUMENTATION_BASE_FIELDS_MISSING"):
            enrich_mission_telemetry(
                base,
                information_questions_resolved=1,
                proof_axes_gained=1,
                elapsed_seconds=1,
            )

    def test_negative_elapsed_time_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "MISSION_INSTRUMENTATION_NON_NEGATIVE_FINITE_REQUIRED:elapsed_seconds"):
            enrich_mission_telemetry(
                self._base(),
                information_questions_resolved=1,
                proof_axes_gained=1,
                elapsed_seconds=-1,
            )

    def test_rollback_must_remain_observed_boolean(self):
        base = self._base()
        base["sovara.rollback.available"] = "TRUE"
        with self.assertRaisesRegex(ValueError, "MISSION_INSTRUMENTATION_ROLLBACK_BOOLEAN_REQUIRED"):
            enrich_mission_telemetry(
                base,
                information_questions_resolved=1,
                proof_axes_gained=1,
                elapsed_seconds=1,
            )


if __name__ == "__main__":
    unittest.main()
