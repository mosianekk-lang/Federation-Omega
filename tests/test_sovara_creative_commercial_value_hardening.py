from __future__ import annotations

import unittest

from sovara.creative.commercial_value import (
    MetricDirection,
    MetricObservation,
    ValueClass,
    ValueEvidence,
    ValueGateState,
    ValueMetricSpec,
    compare_value_metrics,
    evaluate_value_gate,
)


class SovaraCreativeCommercialValueHardeningTests(unittest.TestCase):
    def test_duplicate_metric_observations_are_rejected(self) -> None:
        specs = (
            ValueMetricSpec("quality", ValueClass.OPERATIONAL, MetricDirection.HIGHER_IS_BETTER),
        )
        observations = (
            MetricObservation("quality", 1.0, 1.1, "evidence:1"),
            MetricObservation("quality", 1.0, 1.2, "evidence:2"),
        )
        with self.assertRaisesRegex(ValueError, "duplicate metric observation: quality"):
            compare_value_metrics(specs=specs, observations=observations)
        with self.assertRaisesRegex(ValueError, "duplicate metric observation: quality"):
            evaluate_value_gate(
                specs=specs,
                observations=observations,
                evidence=ValueEvidence(provider_native_readback=True, repeated_success=True),
            )

    def test_absent_optional_metric_does_not_depress_class_denominator(self) -> None:
        specs = (
            ValueMetricSpec(
                "required_quality",
                ValueClass.OPERATIONAL,
                MetricDirection.HIGHER_IS_BETTER,
                weight=1.0,
                minimum_gain=1.0,
                required=True,
            ),
            ValueMetricSpec(
                "optional_bonus",
                ValueClass.OPERATIONAL,
                MetricDirection.HIGHER_IS_BETTER,
                weight=9.0,
                minimum_gain=2.0,
                required=False,
            ),
            ValueMetricSpec(
                "commercial",
                ValueClass.COMMERCIAL,
                MetricDirection.HIGHER_IS_BETTER,
                required=True,
            ),
            ValueMetricSpec(
                "usability",
                ValueClass.USABILITY,
                MetricDirection.HIGHER_IS_BETTER,
                required=True,
            ),
        )
        observations = (
            MetricObservation("required_quality", 1.0, 1.0, "evidence:q"),
            MetricObservation("commercial", 1.0, 1.0, "evidence:c"),
            MetricObservation("usability", 1.0, 1.0, "evidence:u"),
        )
        decision = evaluate_value_gate(
            specs=specs,
            observations=observations,
            evidence=ValueEvidence(provider_native_readback=True, repeated_success=True),
        )
        self.assertEqual(1.0, decision.operational_target_rate)
        self.assertEqual(ValueGateState.PRODUCTION_VALUE_CANDIDATE, decision.state)

    def test_observed_optional_metric_enters_denominator_and_can_hold_value(self) -> None:
        specs = (
            ValueMetricSpec(
                "required_quality",
                ValueClass.OPERATIONAL,
                MetricDirection.HIGHER_IS_BETTER,
                weight=1.0,
                required=True,
            ),
            ValueMetricSpec(
                "optional_bonus",
                ValueClass.OPERATIONAL,
                MetricDirection.HIGHER_IS_BETTER,
                weight=1.0,
                minimum_gain=2.0,
                required=False,
            ),
            ValueMetricSpec("commercial", ValueClass.COMMERCIAL, MetricDirection.HIGHER_IS_BETTER),
            ValueMetricSpec("usability", ValueClass.USABILITY, MetricDirection.HIGHER_IS_BETTER),
        )
        observations = (
            MetricObservation("required_quality", 1.0, 1.0, "evidence:q"),
            MetricObservation("optional_bonus", 1.0, 1.0, "evidence:o"),
            MetricObservation("commercial", 1.0, 1.0, "evidence:c"),
            MetricObservation("usability", 1.0, 1.0, "evidence:u"),
        )
        decision = evaluate_value_gate(
            specs=specs,
            observations=observations,
            evidence=ValueEvidence(provider_native_readback=True, repeated_success=True),
        )
        self.assertEqual(0.5, decision.operational_target_rate)
        self.assertEqual(ValueGateState.HOLD_OPERATIONAL_VALUE, decision.state)

    def test_required_missing_metric_still_fails_closed(self) -> None:
        specs = (
            ValueMetricSpec("required", ValueClass.COMMERCIAL, MetricDirection.HIGHER_IS_BETTER),
        )
        decision = evaluate_value_gate(
            specs=specs,
            observations=(MetricObservation("other", 1.0, 1.0, "evidence:other"),),
            evidence=ValueEvidence(provider_native_readback=True, repeated_success=True),
        )
        self.assertEqual(ValueGateState.HOLD_NO_METRICS, decision.state)
        self.assertIn("MISSING:required", decision.reasons)

    def test_value_targets_do_not_bypass_runtime_or_repeat_evidence(self) -> None:
        specs = (
            ValueMetricSpec("commercial", ValueClass.COMMERCIAL, MetricDirection.HIGHER_IS_BETTER),
            ValueMetricSpec("operational", ValueClass.OPERATIONAL, MetricDirection.HIGHER_IS_BETTER),
            ValueMetricSpec("usability", ValueClass.USABILITY, MetricDirection.HIGHER_IS_BETTER),
        )
        observations = tuple(
            MetricObservation(name, 1.0, 2.0, f"evidence:{name}")
            for name in ("commercial", "operational", "usability")
        )
        runtime_hold = evaluate_value_gate(
            specs=specs,
            observations=observations,
            evidence=ValueEvidence(provider_native_readback=False, repeated_success=True),
        )
        repeat_hold = evaluate_value_gate(
            specs=specs,
            observations=observations,
            evidence=ValueEvidence(provider_native_readback=True, repeated_success=False),
        )
        self.assertEqual(ValueGateState.HOLD_RUNTIME_PROOF, runtime_hold.state)
        self.assertEqual(ValueGateState.HOLD_REPEATED_SUCCESS, repeat_hold.state)


if __name__ == "__main__":
    unittest.main()
