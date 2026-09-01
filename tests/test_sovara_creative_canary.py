from __future__ import annotations

from hashlib import sha256
import unittest

from sovara.creative.canary import (
    CreativeCanaryObservation,
    CreativeCanarySpec,
    CreativeCanaryState,
    evaluate_creative_canary,
    source_only_canary_decision,
)


REQUIRED = (
    "FICTIONAL_SUBJECT_CONFIRMED",
    "REQUESTED_CREATIVE_INTENT_PRESENT",
    "ASSET_PAYLOAD_NONEMPTY",
    "ASSET_HASH_READBACK_MATCH",
)


def spec() -> CreativeCanarySpec:
    return CreativeCanarySpec(
        canary_id="SC-CANARY-TEST-001",
        objective="Prove one bounded public-synthetic asset path",
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
        required_semantic_assertions=REQUIRED,
        rollback_requirement="disable or delete the canary asset",
    )


def observation(**overrides) -> CreativeCanaryObservation:
    payload = b"fictional-synthetic-canary-asset"
    base = dict(
        source_revision="deadbeef",
        runtime_identity="bounded-runtime",
        provider_name="example-provider",
        provider_request_id="req-canary-001",
        provider_native_readback=True,
        asset_ids=("asset-001",),
        asset_sha256=(sha256(payload).hexdigest(),),
        semantic_assertions_passed=REQUIRED,
        rollback_or_disable_proven=True,
        rollback_or_disable_ref="rollback:asset-001",
        proof_ref="provider-receipt:001",
        provider_cost=0.0,
        provider_call_count=1,
    )
    base.update(overrides)
    return CreativeCanaryObservation(**base)


class SovaraCreativeCanaryTests(unittest.TestCase):
    def test_source_contract_stops_at_effect_authority(self) -> None:
        decision = source_only_canary_decision(spec())
        self.assertEqual(CreativeCanaryState.HOLD_EFFECT_AUTHORITY, decision.state)
        self.assertFalse(decision.verified)
        self.assertIn("Source tests or simulated", decision.truth_boundary)
        self.assertIn("do not prove provider execution", decision.truth_boundary)

    def test_no_runtime_authority_means_no_provider_canary(self) -> None:
        decision = evaluate_creative_canary(spec(), observation(), provider_effect_authority_bound=False, finite_spend_authorized=False)
        self.assertEqual(CreativeCanaryState.HOLD_EFFECT_AUTHORITY, decision.state)
        self.assertFalse(decision.verified)

    def test_provider_success_without_asset_hash_is_not_creative_canary_proof(self) -> None:
        decision = evaluate_creative_canary(spec(), observation(asset_sha256=()), provider_effect_authority_bound=True, finite_spend_authorized=False)
        self.assertEqual(CreativeCanaryState.HOLD_ASSET_READBACK, decision.state)
        self.assertFalse(decision.verified)

    def test_missing_semantic_assertion_fails_closed(self) -> None:
        decision = evaluate_creative_canary(spec(), observation(semantic_assertions_passed=REQUIRED[:-1]), provider_effect_authority_bound=True, finite_spend_authorized=False)
        self.assertEqual(CreativeCanaryState.HOLD_SEMANTIC_READBACK, decision.state)
        self.assertIn("MISSING:ASSET_HASH_READBACK_MATCH", decision.reasons)

    def test_paid_observation_requires_separate_finite_spend_authority(self) -> None:
        decision = evaluate_creative_canary(spec(), observation(provider_cost=0.05), provider_effect_authority_bound=True, finite_spend_authorized=False)
        self.assertEqual(CreativeCanaryState.HOLD_EFFECT_AUTHORITY, decision.state)
        self.assertIn("PAID_PROVIDER_EFFECT_WITHOUT_FINITE_SPEND_AUTHORITY", decision.reasons)

    def test_forbidden_effect_quarantines_canary(self) -> None:
        decision = evaluate_creative_canary(spec(), observation(publishing_performed=True), provider_effect_authority_bound=True, finite_spend_authorized=True)
        self.assertEqual(CreativeCanaryState.HOLD_EFFECT_AUTHORITY, decision.state)
        self.assertIn("PUBLISHING_PERFORMED", decision.reasons)

    def test_missing_provider_call_count_never_self_certifies(self) -> None:
        decision = evaluate_creative_canary(
            spec(),
            observation(provider_call_count=None),
            provider_effect_authority_bound=True,
            finite_spend_authorized=False,
        )
        self.assertEqual(CreativeCanaryState.HOLD_PROVIDER_RECEIPT, decision.state)
        self.assertIn("PROVIDER_CALL_COUNT_READBACK_REQUIRED", decision.reasons)

    def test_provider_call_count_above_contract_is_quarantined(self) -> None:
        decision = evaluate_creative_canary(
            spec(),
            observation(provider_call_count=2),
            provider_effect_authority_bound=True,
            finite_spend_authorized=False,
        )
        self.assertEqual(CreativeCanaryState.HOLD_EFFECT_AUTHORITY, decision.state)
        self.assertIn("PROVIDER_CALL_LIMIT_EXCEEDED:2>1", decision.reasons)

    def test_provider_call_count_rejects_non_integer_or_negative_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "provider_call_count"):
            observation(provider_call_count=True)
        with self.assertRaisesRegex(ValueError, "non-negative"):
            observation(provider_call_count=-1)

    def test_rollback_is_required_even_after_provider_and_semantic_readback(self) -> None:
        decision = evaluate_creative_canary(spec(), observation(rollback_or_disable_proven=False, rollback_or_disable_ref=""), provider_effect_authority_bound=True, finite_spend_authorized=False)
        self.assertEqual(CreativeCanaryState.HOLD_ROLLBACK_PROOF, decision.state)
        self.assertFalse(decision.verified)

    def test_complete_observation_advances_only_to_recovery_canary(self) -> None:
        decision = evaluate_creative_canary(spec(), observation(), provider_effect_authority_bound=True, finite_spend_authorized=False)
        self.assertEqual(CreativeCanaryState.VERIFIED, decision.state)
        self.assertTrue(decision.verified)
        self.assertEqual("FORCED_FAILURE_AND_RECOVERY_CANARY", decision.next_gate)
        self.assertIn("PROVIDER_CALL_BOUND_VERIFIED", decision.reasons)
        self.assertIn("do not prove provider execution", decision.truth_boundary)
        self.assertIn("repeated success", decision.truth_boundary)

    def test_v1_contract_rejects_self_authorized_provider_effect(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot authorize consequential effects"):
            CreativeCanarySpec(
                canary_id="SC-CANARY-BAD",
                objective="invalid self-authorized effect",
                synthetic_only=True,
                case_data_allowed=False,
                real_person_allowed=False,
                provider_mutation_allowed=False,
                publishing_allowed=False,
                external_communication_allowed=False,
                production_traffic_allowed=False,
                provider_effect_authorized=True,
                max_provider_calls=1,
                max_assets=1,
                max_source_spend=0.0,
                required_semantic_assertions=REQUIRED,
                rollback_requirement="rollback",
            )


if __name__ == "__main__":
    unittest.main()
