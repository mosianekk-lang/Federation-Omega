import unittest

from federation.copilot_pro.billing import (
    API_VERSION,
    REQUIRED_PERMISSION,
    build_ai_credit_usage_request,
    parse_ai_credit_usage_response,
)


class FCXCopilotBillingUsageTests(unittest.TestCase):
    def request(self):
        return build_ai_credit_usage_request(
            username="mosianekk-lang",
            year=2026,
            month=8,
            credential_reference_id="CR-005",
        )

    def payload(self):
        return {
            "timePeriod": {"year": 2026, "month": 8},
            "user": "mosianekk-lang",
            "usageItems": [
                {
                    "product": "Copilot AI Credits",
                    "sku": "AI Credit",
                    "model": "Gemini 3.1 Pro",
                    "unitType": "ai-credits",
                    "pricePerUnit": 0.01,
                    "grossQuantity": 12.5,
                    "grossAmount": 0.125,
                    "discountQuantity": 12.5,
                    "discountAmount": 0.125,
                    "netQuantity": 0,
                    "netAmount": 0,
                },
                {
                    "product": "Copilot AI Credits",
                    "sku": "AI Credit",
                    "model": "GPT-5.6",
                    "unitType": "ai-credits",
                    "pricePerUnit": 0.01,
                    "grossQuantity": 3,
                    "grossAmount": 0.03,
                    "discountQuantity": 3,
                    "discountAmount": 0.03,
                    "netQuantity": 0,
                    "netAmount": 0,
                },
            ],
        }

    def test_request_is_exact_read_only_and_value_free(self):
        request = self.request()
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.api_version, API_VERSION)
        self.assertEqual(request.required_permission, REQUIRED_PERMISSION)
        self.assertEqual(request.credential_reference_id, "CR-005")
        self.assertFalse(request.credential_value_included)
        self.assertFalse(request.billing_mutation_allowed)
        self.assertFalse(request.copilot_dispatch_allowed)
        self.assertEqual(
            request.endpoint_path,
            "/users/mosianekk-lang/settings/billing/ai_credit/usage?year=2026&month=8",
        )

    def test_request_rejects_raw_secret_like_reference(self):
        # Compose detector fixtures at runtime so Phoenix's static Core export
        # leak scanner does not confuse synthetic test material with leakage.
        raw_values = (
            "gh" + "p_secret_value",
            "github_" + "pat_secret",
            "Bearer abcdefgh",
            "token abcdefgh",
        )
        for raw in raw_values:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                build_ai_credit_usage_request(
                    username="mosianekk-lang",
                    year=2026,
                    month=8,
                    credential_reference_id=raw,
                )

    def test_response_requires_verified_plan_read_permission(self):
        with self.assertRaises(ValueError):
            parse_ai_credit_usage_response(
                request=self.request(),
                status_code=200,
                payload=self.payload(),
                plan_read_permission_verified=False,
            )

    def test_response_rejects_credential_value_exposure(self):
        with self.assertRaises(ValueError):
            parse_ai_credit_usage_response(
                request=self.request(),
                status_code=200,
                payload=self.payload(),
                plan_read_permission_verified=True,
                credential_value_exposed=True,
            )

    def test_response_rejects_non_200(self):
        with self.assertRaises(ValueError):
            parse_ai_credit_usage_response(
                request=self.request(),
                status_code=403,
                payload={},
                plan_read_permission_verified=True,
            )

    def test_response_rejects_wrong_user_or_period(self):
        payload = self.payload()
        payload["user"] = "other-user"
        with self.assertRaises(ValueError):
            parse_ai_credit_usage_response(
                request=self.request(),
                status_code=200,
                payload=payload,
                plan_read_permission_verified=True,
            )
        payload = self.payload()
        payload["timePeriod"]["year"] = 2025
        with self.assertRaises(ValueError):
            parse_ai_credit_usage_response(
                request=self.request(),
                status_code=200,
                payload=payload,
                plan_read_permission_verified=True,
            )

    def test_response_aggregates_ai_credit_items(self):
        payload = self.payload()
        payload["usageItems"].append(
            {
                "product": "Actions",
                "unitType": "minutes",
                "grossQuantity": 999,
                "grossAmount": 9,
                "discountQuantity": 0,
                "discountAmount": 0,
                "netQuantity": 999,
                "netAmount": 9,
            }
        )
        snapshot = parse_ai_credit_usage_response(
            request=self.request(),
            status_code=200,
            payload=payload,
            plan_read_permission_verified=True,
        )
        self.assertEqual(snapshot.gross_credits, 15.5)
        self.assertEqual(snapshot.discounted_credits, 15.5)
        self.assertEqual(snapshot.net_credits, 0)
        self.assertEqual(snapshot.net_amount_usd, 0)
        self.assertEqual(snapshot.model_count, 2)
        self.assertEqual(snapshot.models, ("GPT-5.6", "Gemini 3.1 Pro"))
        self.assertTrue(snapshot.response_semantic_verified)
        self.assertTrue(snapshot.provider_call_was_read_only)
        self.assertFalse(snapshot.credential_value_exposed)

    def test_zero_usage_month_is_valid_provider_readback(self):
        snapshot = parse_ai_credit_usage_response(
            request=self.request(),
            status_code=200,
            payload={
                "timePeriod": {"year": 2026, "month": 8},
                "user": "mosianekk-lang",
                "usageItems": [],
            },
            plan_read_permission_verified=True,
        )
        self.assertEqual(snapshot.gross_credits, 0)
        self.assertEqual(snapshot.net_amount_usd, 0)
        self.assertTrue(snapshot.response_semantic_verified)

    def test_snapshot_is_deterministic(self):
        a = parse_ai_credit_usage_response(
            request=self.request(),
            status_code=200,
            payload=self.payload(),
            plan_read_permission_verified=True,
        )
        b = parse_ai_credit_usage_response(
            request=self.request(),
            status_code=200,
            payload=self.payload(),
            plan_read_permission_verified=True,
        )
        self.assertEqual(a.snapshot_sha256, b.snapshot_sha256)


if __name__ == "__main__":
    unittest.main()
