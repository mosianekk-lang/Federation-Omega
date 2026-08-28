from __future__ import annotations

import unittest

from sovara.creative.openrouter_image_catalog_probe import (
    DEFAULT_FREE_ALIAS,
    DEFAULT_MODEL,
    build_receipt,
    find_model,
)


def catalog(*, include_free: bool = False, image_output: bool = True) -> dict:
    rows = [
        {
            "id": DEFAULT_MODEL,
            "architecture": {"output_modalities": ["image"] if image_output else ["text"]},
            "endpoints": f"/api/v1/images/models/{DEFAULT_MODEL}/endpoints",
        }
    ]
    if include_free:
        rows.append(
            {
                "id": DEFAULT_FREE_ALIAS,
                "architecture": {"output_modalities": ["image"]},
                "endpoints": f"/api/v1/images/models/{DEFAULT_FREE_ALIAS}/endpoints",
            }
        )
    return {"data": rows}


def endpoints(cost: float | None) -> dict:
    pricing = [] if cost is None else [{"billable": "output_image", "unit": "image", "cost_usd": cost}]
    return {"data": [{"provider": "Recraft", "pricing": pricing}]}


class OpenRouterImageCatalogProbeTests(unittest.TestCase):
    def test_find_model_exact(self) -> None:
        self.assertEqual(DEFAULT_MODEL, find_model(catalog(), DEFAULT_MODEL)["id"])
        self.assertIsNone(find_model(catalog(), "missing/model"))

    def test_current_catalog_without_free_alias_does_not_invent_zero_cost(self) -> None:
        receipt = build_receipt(catalog(), endpoints(0.04))
        self.assertEqual("PAID_ROUTE_VERIFIED", receipt["state"])
        self.assertFalse(receipt["free_alias_present"])
        self.assertFalse(receipt["zero_cost_verified"])
        self.assertEqual(0.04, receipt["unit_price_usd"])

    def test_zero_cost_requires_endpoint_native_zero_price(self) -> None:
        receipt = build_receipt(catalog(include_free=True), endpoints(0.0))
        self.assertEqual("ZERO_COST_ROUTE_VERIFIED", receipt["state"])
        self.assertTrue(receipt["free_alias_present"])
        self.assertTrue(receipt["zero_cost_verified"])

    def test_free_alias_presence_alone_is_not_zero_cost_proof(self) -> None:
        receipt = build_receipt(catalog(include_free=True), endpoints(0.04))
        self.assertEqual("PAID_ROUTE_VERIFIED", receipt["state"])
        self.assertTrue(receipt["free_alias_present"])
        self.assertFalse(receipt["zero_cost_verified"])

    def test_missing_endpoint_pricing_holds(self) -> None:
        receipt = build_receipt(catalog(), endpoints(None))
        self.assertEqual("HOLD_PRICE_READBACK", receipt["state"])
        self.assertIsNone(receipt["unit_price_usd"])

    def test_missing_image_output_holds(self) -> None:
        receipt = build_receipt(catalog(image_output=False), endpoints(0.04))
        self.assertEqual("HOLD_IMAGE_CAPABILITY", receipt["state"])

    def test_receipt_proves_no_effect_or_credential_use(self) -> None:
        receipt = build_receipt(catalog(), endpoints(0.04))
        self.assertEqual(["GET"], receipt["http_methods_used"])
        self.assertFalse(receipt["credential_used"])
        self.assertFalse(receipt["authorization_header_sent"])
        self.assertFalse(receipt["provider_effect_performed"])
        self.assertFalse(receipt["image_generation_performed"])
        self.assertFalse(receipt["spend_performed"])
        self.assertIn("does not authorize", receipt["truth_boundary"])


if __name__ == "__main__":
    unittest.main()
