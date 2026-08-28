from __future__ import annotations

from datetime import datetime, timezone
import unittest

from sovara.creative.canary import CreativeCanarySpec
from sovara.creative.canary_authority import (
    CanaryAuthorityState,
    CanaryExecutionBinding,
    ImageRouteCatalogEvidence,
    evaluate_image_canary_authority,
)


NOW = datetime(2026, 8, 28, 21, 45, tzinfo=timezone.utc)
REQUEST_SHA = "a" * 64


def spec() -> CreativeCanarySpec:
    return CreativeCanarySpec(
        canary_id="SC-CANARY-AUTH-TEST-001",
        objective="Prove one bounded public-synthetic image canary",
        synthetic_only=True,
        case_data_allowed=False,
        real_person_allowed=False,
        provider_mutation_allowed=False,
        publishing_allowed=False,
        external_communication_allowed=False,
        production_traffic_allowed=False,
        provider_effect_authorized=False,
        max_provider_calls=1,
        max_assets=1,
        max_source_spend=0.0,
        required_semantic_assertions=(
            "FICTIONAL_SUBJECT_CONFIRMED",
            "REQUESTED_CREATIVE_INTENT_PRESENT",
            "ASSET_PAYLOAD_NONEMPTY",
            "ASSET_HASH_READBACK_MATCH",
        ),
        rollback_requirement="disable or delete the canary asset",
    )


def catalog(**overrides) -> ImageRouteCatalogEvidence:
    base = dict(
        snapshot_id="openrouter-images-catalog-test",
        checked_at="2026-08-28T21:40:00Z",
        expires_at="2026-08-28T22:40:00Z",
        model_id="example/image-model",
        endpoint="https://openrouter.ai/api/v1/images",
        output_modalities=("image",),
        unit_price_usd=0.0,
        pricing_unit="image",
        provider_native_readback_supported=True,
        source_urls=("https://openrouter.ai/api/v1/images/models",),
    )
    base.update(overrides)
    return ImageRouteCatalogEvidence(**base)


def binding(**overrides) -> CanaryExecutionBinding:
    base = dict(
        credential_reference="env:OPENROUTER_API_KEY",
        credential_bound=True,
        runtime_identity="github-actions:sovara-creative-canary",
        exact_request_sha256=REQUEST_SHA,
        privacy_eligible=True,
        provider_effect_authority_bound=True,
        finite_spend_authorized=False,
    )
    base.update(overrides)
    return CanaryExecutionBinding(**base)


class CanaryAuthorityTests(unittest.TestCase):
    def test_missing_catalog_holds_before_any_effect(self) -> None:
        decision = evaluate_image_canary_authority(spec(), None, binding(), evaluated_at=NOW)
        self.assertEqual(CanaryAuthorityState.HOLD_ROUTE_CATALOG, decision.state)
        self.assertFalse(decision.ready)

    def test_stale_catalog_holds_before_any_effect(self) -> None:
        decision = evaluate_image_canary_authority(
            spec(),
            catalog(expires_at="2026-08-28T21:44:00Z"),
            binding(),
            evaluated_at=NOW,
        )
        self.assertEqual(CanaryAuthorityState.HOLD_ROUTE_CATALOG, decision.state)

    def test_image_output_and_images_endpoint_are_required(self) -> None:
        decision = evaluate_image_canary_authority(
            spec(),
            catalog(output_modalities=("text",)),
            binding(),
            evaluated_at=NOW,
        )
        self.assertEqual(CanaryAuthorityState.HOLD_PROVIDER_CAPABILITY, decision.state)

    def test_price_must_come_from_current_catalog_readback(self) -> None:
        decision = evaluate_image_canary_authority(
            spec(),
            catalog(unit_price_usd=None),
            binding(),
            evaluated_at=NOW,
        )
        self.assertEqual(CanaryAuthorityState.HOLD_ZERO_COST_VERIFICATION, decision.state)

    def test_zero_cost_route_still_requires_bound_credential(self) -> None:
        decision = evaluate_image_canary_authority(
            spec(),
            catalog(unit_price_usd=0.0),
            binding(credential_bound=False, credential_reference="env:OPENROUTER_API_KEY"),
            evaluated_at=NOW,
        )
        self.assertEqual(CanaryAuthorityState.HOLD_CREDENTIAL, decision.state)
        self.assertTrue(decision.zero_cost_route)

    def test_zero_cost_route_still_requires_separate_effect_authority(self) -> None:
        decision = evaluate_image_canary_authority(
            spec(),
            catalog(unit_price_usd=0.0),
            binding(provider_effect_authority_bound=False),
            evaluated_at=NOW,
        )
        self.assertEqual(CanaryAuthorityState.HOLD_EFFECT_AUTHORITY, decision.state)
        self.assertTrue(decision.zero_cost_route)

    def test_paid_route_requires_finite_spend_authority(self) -> None:
        decision = evaluate_image_canary_authority(
            spec(),
            catalog(unit_price_usd=0.04),
            binding(finite_spend_authorized=False),
            evaluated_at=NOW,
        )
        self.assertEqual(CanaryAuthorityState.HOLD_FINITE_SPEND_AUTHORITY, decision.state)
        self.assertFalse(decision.zero_cost_route)

    def test_zero_cost_complete_preflight_only_reaches_one_canary_ready(self) -> None:
        decision = evaluate_image_canary_authority(
            spec(),
            catalog(unit_price_usd=0.0),
            binding(),
            evaluated_at=NOW,
        )
        self.assertEqual(CanaryAuthorityState.READY_FOR_ONE_CANARY, decision.state)
        self.assertTrue(decision.ready)
        self.assertIn("does not prove provider execution", decision.truth_boundary)

    def test_paid_route_can_be_ready_only_with_explicit_finite_spend(self) -> None:
        decision = evaluate_image_canary_authority(
            spec(),
            catalog(unit_price_usd=0.04),
            binding(finite_spend_authorized=True),
            evaluated_at=NOW,
        )
        self.assertEqual(CanaryAuthorityState.READY_FOR_ONE_CANARY, decision.state)
        self.assertIn("FINITE_SPEND_AUTHORITY_BOUND", decision.reasons)


if __name__ == "__main__":
    unittest.main()
