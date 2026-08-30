from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.mission_measurement_contract import (
    DEFAULT_METRIC_KEYS,
    MissionMeasurementBounds,
    build_mission_measurement_contract,
)


class CFBEMissionMeasurementContractTests(unittest.TestCase):
    def _bounds(self, **overrides):
        values = dict(
            information_questions_targeted=10.0,
            mission_value_target=10.0,
            proof_axes_targeted=10.0,
            max_cost=100.0,
            latency_ceiling_seconds=600.0,
            owner_intervention_ceiling_seconds=120.0,
            risk_ceiling=10.0,
            bound_refs={dimension: f"mission-contract:{dimension}" for dimension in DEFAULT_METRIC_KEYS},
        )
        values.update(overrides)
        return MissionMeasurementBounds(**values)

    def _observation_ids(self):
        return {dimension: f"OBS-{dimension}" for dimension in DEFAULT_METRIC_KEYS}

    def test_complete_pre_registration_builds_exact_eight_dimensions(self):
        contract = build_mission_measurement_contract(
            experiment_id="EXP-001",
            label="measured mission",
            observation_ids=self._observation_ids(),
            bounds=self._bounds(),
            experiment_evidence_refs=("mission:EXP-001",),
        )
        self.assertEqual(8, len(contract.dimensions))
        self.assertEqual(set(DEFAULT_METRIC_KEYS), {item.dimension for item in contract.dimensions})
        reversibility = next(item for item in contract.dimensions if item.dimension == "reversibility")
        self.assertEqual(1.0, reversibility.denominator)
        self.assertEqual("sovara.rollback.available", reversibility.metric_key)

    def test_missing_observation_binding_fails_closed(self):
        ids = self._observation_ids()
        ids.pop("risk")
        with self.assertRaisesRegex(ValueError, "MISSION_MEASUREMENT_OBSERVATION_BINDING_INCOMPLETE"):
            build_mission_measurement_contract(
                experiment_id="EXP-001",
                label="measured mission",
                observation_ids=ids,
                bounds=self._bounds(),
                experiment_evidence_refs=("mission:EXP-001",),
            )

    def test_missing_bound_provenance_fails_closed(self):
        refs = dict(self._bounds().bound_refs)
        refs.pop("mission_value")
        with self.assertRaisesRegex(ValueError, "MISSION_MEASUREMENT_BOUND_PROVENANCE_INCOMPLETE"):
            build_mission_measurement_contract(
                experiment_id="EXP-001",
                label="measured mission",
                observation_ids=self._observation_ids(),
                bounds=self._bounds(bound_refs=refs),
                experiment_evidence_refs=("mission:EXP-001",),
            )

    def test_zero_cost_ceiling_is_rejected_not_divided_away(self):
        with self.assertRaisesRegex(ValueError, "MISSION_MEASUREMENT_BOUND_MUST_BE_POSITIVE:estimated_cost"):
            build_mission_measurement_contract(
                experiment_id="EXP-001",
                label="measured mission",
                observation_ids=self._observation_ids(),
                bounds=self._bounds(max_cost=0.0),
                experiment_evidence_refs=("mission:EXP-001",),
            )

    def test_unknown_dimension_cannot_be_smuggled_into_observation_bindings(self):
        ids = self._observation_ids()
        ids["prestige_score"] = "OBS-prestige"
        with self.assertRaisesRegex(ValueError, "MISSION_MEASUREMENT_OBSERVATION_BINDING_INCOMPLETE"):
            build_mission_measurement_contract(
                experiment_id="EXP-001",
                label="measured mission",
                observation_ids=ids,
                bounds=self._bounds(),
                experiment_evidence_refs=("mission:EXP-001",),
            )


if __name__ == "__main__":
    unittest.main()
