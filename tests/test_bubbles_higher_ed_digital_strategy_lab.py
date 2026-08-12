from __future__ import annotations

import copy
import unittest

from bubbles.higher_ed_digital_strategy_lab import (
    HigherEdDigitalStrategyLab,
    STUDENT_LIFECYCLE_STAGES,
    validate_reference_model,
)


class HigherEdDigitalStrategyLabTests(unittest.TestCase):
    def test_reference_model_covers_required_domains_and_lifecycle(self) -> None:
        receipt = validate_reference_model()
        self.assertEqual("DETERMINISTIC_TESTED_REFERENCE_MODEL", receipt.state)
        self.assertEqual((), receipt.missing_domains)
        self.assertEqual((), receipt.missing_lifecycle_stages)
        self.assertEqual(set(STUDENT_LIFECYCLE_STAGES), set(receipt.lifecycle_coverage))
        self.assertTrue(receipt.traceability_pass)
        self.assertTrue(receipt.transition_pass)
        self.assertTrue(receipt.risk_control_pass)
        self.assertFalse(receipt.external_effect)
        self.assertFalse(receipt.provider_verified)

    def test_reference_model_covers_all_architecture_layers(self) -> None:
        receipt = validate_reference_model()
        self.assertEqual(
            {
                "business_capability",
                "application",
                "data",
                "integration",
                "technology",
                "risk_control",
            },
            set(receipt.architecture_layer_coverage),
        )

    def test_receipt_is_deterministic(self) -> None:
        first = validate_reference_model()
        second = validate_reference_model()
        self.assertEqual(first.receipt_sha256, second.receipt_sha256)
        self.assertEqual(64, len(first.receipt_sha256))

    def test_missing_control_fails_closed(self) -> None:
        reference = HigherEdDigitalStrategyLab.reference()
        caps = list(reference.capabilities)
        target = caps[0]
        caps[0] = type(target)(
            capability_id=target.capability_id,
            domain=target.domain,
            outcome=target.outcome,
            applications=target.applications,
            data_products=target.data_products,
            integrations=target.integrations,
            controls=(),
            lifecycle_stages=target.lifecycle_stages,
        )
        receipt = HigherEdDigitalStrategyLab(caps, reference.waves).validate()
        self.assertEqual("HOLD", receipt.state)
        self.assertFalse(receipt.risk_control_pass)
        self.assertIn("CONTROL_MISSING:CAP-DIG-TEACH", receipt.violations)

    def test_unsequenced_capability_fails_transition_gate(self) -> None:
        reference = HigherEdDigitalStrategyLab.reference()
        waves = list(reference.waves)
        first = waves[0]
        waves[0] = type(first)(
            wave=first.wave,
            name=first.name,
            capabilities=tuple(item for item in first.capabilities if item != "CAP-DIG-STUDENT"),
            success_metrics=first.success_metrics,
            rollback_trigger=first.rollback_trigger,
        )
        receipt = HigherEdDigitalStrategyLab(reference.capabilities, waves).validate()
        self.assertEqual("HOLD", receipt.state)
        self.assertFalse(receipt.transition_pass)
        self.assertIn("UNSEQUENCED_CAPABILITY:CAP-DIG-STUDENT", receipt.violations)

    def test_executive_case_is_truth_bounded(self) -> None:
        case = HigherEdDigitalStrategyLab.reference().executive_case()
        self.assertIn("synthetic", str(case["mission"]).casefold())
        self.assertIn("deterministically validated", str(case["safe_claim"]).casefold())
        self.assertFalse(case["architecture_receipt"]["provider_verified"])
        joined = " ".join(case["forbidden_claims"]).casefold()
        self.assertIn("deployed", joined)
        self.assertIn("real student", joined)


if __name__ == "__main__":
    unittest.main()
