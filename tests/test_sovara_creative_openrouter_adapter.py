from datetime import datetime, timezone
import unittest

from sovara.creative.openrouter_adapter import (
    MaturePolicyState,
    OpenRouterPlanState,
    OpenRouterPolicySnapshot,
    OpenRouterPriceCeiling,
    OpenRouterReceiptState,
    build_openrouter_request_plan,
    evaluate_openrouter_response,
)
from sovara.creative.policy import (
    ContentClass,
    Eligibility,
    MatureContext,
    PrivacyClass,
    RoutePolicy,
    RouteType,
)


NOW = datetime(2026, 8, 28, 19, 30, tzinfo=timezone.utc)


def snapshot(**overrides):
    values = {
        "snapshot_id": "SC-OR-POLICY-20260828-001",
        "model_id": "example/model-v1",
        "provider_allowlist": ("example-provider",),
        "provider_readback_allowlist": ("Example Provider",),
        "checked_at": "2026-08-28T18:00:00Z",
        "expires_at": "2026-08-29T18:00:00Z",
        "source_urls": (
            "https://openrouter.ai/docs/guides/routing/provider-selection",
            "https://example-provider.invalid/current-policy",
        ),
        "mature_policy_state": MaturePolicyState.ALLOWED,
        "zdr_supported": True,
        "data_collection_deny_supported": True,
        "structured_outputs_supported": True,
    }
    values.update(overrides)
    return OpenRouterPolicySnapshot(**values)


def route(**overrides):
    values = {
        "route_id": "openrouter-example",
        "route_type": RouteType.OPENROUTER_FCX,
        "privacy_ceiling": PrivacyClass.INTERNAL,
        "policy_verified": True,
        "mature_class_allowed": True,
    }
    values.update(overrides)
    return RoutePolicy(**values)


def plan(**overrides):
    values = {
        "mission_id": "SC-OR-001",
        "content_class": ContentClass.BRAND_COMMERCIAL,
        "privacy_class": PrivacyClass.INTERNAL,
        "route": route(),
        "policy_snapshot": snapshot(),
        "messages": ({"role": "user", "content": "Return the bounded marker."},),
        "evaluated_at": NOW,
    }
    values.update(overrides)
    return build_openrouter_request_plan(**values)


class OpenRouterRequestPlanTests(unittest.TestCase):
    def test_ready_plan_is_source_only_and_has_no_silent_fallback(self):
        result = plan(price_ceiling=OpenRouterPriceCeiling(2.5, 8.0))

        self.assertTrue(result.ready)
        self.assertFalse(result.external_effect)
        self.assertFalse(result.live_execution_authorized)
        self.assertEqual(result.credential_reference, "env:OPENROUTER_API_KEY")
        self.assertEqual(result.required_headers["X-OpenRouter-Metadata"], "enabled")
        self.assertNotIn("Authorization", result.required_headers)
        provider = result.request_body["provider"]
        self.assertEqual(provider["only"], ["example-provider"])
        self.assertEqual(provider["order"], ["example-provider"])
        self.assertFalse(provider["allow_fallbacks"])
        self.assertTrue(provider["require_parameters"])
        self.assertEqual(provider["data_collection"], "deny")
        self.assertTrue(provider["zdr"])
        self.assertEqual(provider["max_price"], {"prompt": 2.5, "completion": 8.0})

    def test_missing_verified_adult_or_consent_gate_is_ineligible(self):
        result = plan(
            content_class=ContentClass.MATURE_ADULT_ORIENTED,
            mature_context=MatureContext(all_participants_adults=True, consent_verified=False),
        )

        self.assertEqual(result.state, OpenRouterPlanState.HOLD_RIGHTS_OR_CONSENT)
        self.assertEqual(result.eligibility, Eligibility.INELIGIBLE)
        self.assertEqual(result.request_body, {})

    def test_ambiguous_age_fails_closed(self):
        result = plan(
            content_class=ContentClass.MATURE_ADULT_ORIENTED,
            mature_context=MatureContext(
                all_participants_adults=True,
                consent_verified=True,
                ambiguous_age=True,
            ),
        )

        self.assertEqual(result.state, OpenRouterPlanState.HOLD_RIGHTS_OR_CONSENT)

    def test_sensitive_performer_assets_are_sovereign_only(self):
        result = plan(
            content_class=ContentClass.MATURE_ADULT_ORIENTED,
            privacy_class=PrivacyClass.SENSITIVE_PERFORMER,
            route=route(privacy_ceiling=PrivacyClass.SENSITIVE_PERFORMER),
            mature_context=MatureContext(all_participants_adults=True, consent_verified=True),
        )

        self.assertEqual(result.state, OpenRouterPlanState.HOLD_PRIVACY_SOVEREIGN_ONLY)
        self.assertEqual(result.eligibility, Eligibility.SOVEREIGN_ONLY)

    def test_secret_payload_is_non_generative_only(self):
        result = plan(privacy_class=PrivacyClass.SECRET)

        self.assertEqual(result.state, OpenRouterPlanState.HOLD_NON_GENERATIVE_ONLY)
        self.assertEqual(result.eligibility, Eligibility.NON_GENERATIVE_ONLY)

    def test_stale_policy_snapshot_requires_recheck(self):
        result = plan(
            policy_snapshot=snapshot(
                checked_at="2026-08-26T00:00:00Z",
                expires_at="2026-08-27T00:00:00Z",
            )
        )

        self.assertEqual(result.state, OpenRouterPlanState.HOLD_POLICY_RECHECK)
        self.assertIn("POLICY_SNAPSHOT_STALE", result.reason_codes)

    def test_missing_zdr_capability_requires_recheck(self):
        result = plan(policy_snapshot=snapshot(zdr_supported=False))

        self.assertEqual(result.state, OpenRouterPlanState.HOLD_POLICY_RECHECK)
        self.assertIn("ZDR_CAPABILITY_UNVERIFIED", result.reason_codes)

    def test_route_privacy_ceiling_is_enforced_below_adapter_ceiling(self):
        result = plan(route=route(privacy_ceiling=PrivacyClass.PUBLIC))

        self.assertEqual(result.state, OpenRouterPlanState.HOLD_PROVIDER_INELIGIBLE)
        self.assertEqual(result.eligibility, Eligibility.INELIGIBLE)

    def test_non_generation_route_contract_is_rejected(self):
        result = plan(route=route(generation_capable=False))

        self.assertEqual(result.state, OpenRouterPlanState.HOLD_PROVIDER_INELIGIBLE)

    def test_mature_policy_unknown_requires_recheck(self):
        result = plan(
            content_class=ContentClass.MATURE_ADULT_ORIENTED,
            policy_snapshot=snapshot(mature_policy_state=MaturePolicyState.UNKNOWN),
            mature_context=MatureContext(all_participants_adults=True, consent_verified=True),
        )

        self.assertEqual(result.state, OpenRouterPlanState.HOLD_POLICY_RECHECK)

    def test_restricted_mature_route_preserves_restrictions(self):
        result = plan(
            content_class=ContentClass.MATURE_ADULT_ORIENTED,
            policy_snapshot=snapshot(
                mature_policy_state=MaturePolicyState.ALLOWED_WITH_RESTRICTIONS,
                restrictions=("TEXT_PLANNING_ONLY",),
            ),
            mature_context=MatureContext(all_participants_adults=True, consent_verified=True),
        )

        self.assertEqual(result.eligibility, Eligibility.ELIGIBLE_WITH_RESTRICTIONS)
        self.assertIn("TEXT_PLANNING_ONLY", result.reason_codes)

    def test_structured_output_is_schema_bound(self):
        schema = {
            "type": "object",
            "properties": {"marker": {"type": "string"}},
            "required": ["marker"],
            "additionalProperties": False,
        }
        result = plan(response_schema=schema, response_schema_name="creative_canary")

        response_format = result.request_body["response_format"]
        self.assertEqual(response_format["type"], "json_schema")
        self.assertTrue(response_format["json_schema"]["strict"])

    def test_credential_like_payload_keys_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "credential-like"):
            plan(messages=({"role": "user", "content": "hello", "api_key": "not-allowed"},))

    def test_invalid_or_non_finite_price_ceiling_is_rejected(self):
        for value in (-1.0, 0.0, float("inf"), float("nan")):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "positive"):
                OpenRouterPriceCeiling(value, 1.0)


class OpenRouterReceiptTests(unittest.TestCase):
    def response(self, **overrides):
        value = {
            "id": "gen-123",
            "model": "example/model-v1",
            "openrouter_metadata": {
                "strategy": "direct",
                "attempt": 1,
                "endpoints": {
                    "available": [
                        {
                            "provider": "Example Provider",
                            "model": "example/model-v1",
                            "selected": True,
                        }
                    ]
                },
            },
            "choices": [{"message": {"content": "SOVARA-CANARY-OK"}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 5, "cost": 0.001},
        }
        value.update(overrides)
        return value

    def evaluate(self, response=None, **overrides):
        values = {
            "request_fingerprint": "f" * 64,
            "transport_status": 200,
            "response": self.response() if response is None else response,
            "allowed_models": ("example/model-v1",),
            "allowed_provider_readbacks": ("Example Provider",),
            "expected_semantic_marker": "SOVARA-CANARY-OK",
            "maximum_cost_usd": 0.01,
        }
        values.update(overrides)
        return evaluate_openrouter_response(**values)

    def test_semantic_receipt_separates_metadata_usage_cost_and_output_hash(self):
        result = self.evaluate()

        self.assertEqual(result.state, OpenRouterReceiptState.SEMANTIC_VERIFIED)
        self.assertTrue(result.admission_ready)
        self.assertEqual(result.provider, "Example Provider")
        self.assertEqual(result.resolved_model, "example/model-v1")
        self.assertEqual(result.cost_usd, 0.001)
        self.assertEqual(len(result.output_sha256), 64)
        self.assertFalse(result.raw_output_persisted)

    def test_transport_success_without_provider_readback_is_not_semantic_proof(self):
        response = self.response()
        response["openrouter_metadata"]["endpoints"]["available"][0]["selected"] = False
        result = self.evaluate(response)

        self.assertEqual(result.state, OpenRouterReceiptState.PROVIDER_READBACK_MISSING)
        self.assertFalse(result.admission_ready)

    def test_unexpected_provider_is_rejected(self):
        response = self.response()
        response["openrouter_metadata"]["endpoints"]["available"][0]["provider"] = "Other Provider"
        result = self.evaluate(response)

        self.assertEqual(result.state, OpenRouterReceiptState.PROVIDER_NOT_ALLOWED)

    def test_router_metadata_is_required_even_when_legacy_provider_field_exists(self):
        response = self.response(provider="Example Provider")
        response.pop("openrouter_metadata")
        result = self.evaluate(response)

        self.assertEqual(result.state, OpenRouterReceiptState.ROUTER_METADATA_MISSING)

    def test_retry_or_fallback_metadata_is_rejected(self):
        response = self.response()
        response["openrouter_metadata"]["attempt"] = 2
        result = self.evaluate(response)

        self.assertEqual(result.state, OpenRouterReceiptState.ROUTER_METADATA_INVALID)

    def test_missing_cost_readback_is_not_admission_ready(self):
        result = self.evaluate(
            self.response(usage={"prompt_tokens": 20, "completion_tokens": 5})
        )

        self.assertEqual(result.state, OpenRouterReceiptState.COST_READBACK_MISSING)

    def test_cost_cap_excess_is_held(self):
        result = self.evaluate(
            self.response(usage={"prompt_tokens": 20, "completion_tokens": 5, "cost": 0.02})
        )

        self.assertEqual(result.state, OpenRouterReceiptState.COST_CAP_EXCEEDED)

    def test_negative_usage_is_invalid(self):
        result = self.evaluate(
            self.response(usage={"prompt_tokens": -1, "completion_tokens": 5, "cost": 0.001})
        )

        self.assertEqual(result.state, OpenRouterReceiptState.USAGE_READBACK_INVALID)

    def test_negative_or_non_finite_cost_is_invalid(self):
        for cost in (-0.01, float("inf"), float("nan")):
            with self.subTest(cost=cost):
                result = self.evaluate(
                    self.response(usage={"prompt_tokens": 20, "completion_tokens": 5, "cost": cost})
                )
                self.assertEqual(result.state, OpenRouterReceiptState.COST_READBACK_INVALID)

    def test_invalid_cost_cap_is_rejected(self):
        for cost_cap in (-0.01, float("inf"), float("nan")):
            with self.subTest(cost_cap=cost_cap), self.assertRaisesRegex(ValueError, "non-negative"):
                self.evaluate(maximum_cost_usd=cost_cap)

    def test_semantic_mismatch_preserves_hash_without_raw_output(self):
        result = self.evaluate(self.response(choices=[{"message": {"content": "wrong"}}]))

        self.assertEqual(result.state, OpenRouterReceiptState.SEMANTIC_MISMATCH)
        self.assertEqual(len(result.output_sha256), 64)
        self.assertFalse(result.raw_output_persisted)

    def test_non_2xx_transport_is_failure_even_with_valid_body(self):
        result = self.evaluate(transport_status=429)

        self.assertEqual(result.state, OpenRouterReceiptState.TRANSPORT_FAILED)


if __name__ == "__main__":
    unittest.main()
