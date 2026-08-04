#!/usr/bin/env python3
"""Require provider-callable execution proof for OpenAI credential rotation.

Spreadsheet rows, queue labels, source packages, historical trigger IDs, and generic
runtime health responses are not execution proof. In particular, Google Sheets
API writes cannot be treated as firing Apps Script edit/change triggers.
"""

from __future__ import annotations

import argparse
import copy
from typing import Any, Mapping

from ops.openai_rotation_contract import (
    RotationContractError,
    assert_no_key_material,
    load_json,
    validate_receipt,
)

CALLABLE_ROUTE_TYPES = {
    "DIRECT_GOOGLE_CLOUD_API",
    "APPS_SCRIPT_EXECUTION_API",
    "AUTHENTICATED_APPS_SCRIPT_WEB_APP",
    "VERIFIED_TIME_DRIVEN_APPS_SCRIPT_TRIGGER",
    "PRIVATE_PROVIDER_OPERATOR",
}

NON_EXECUTION_ROUTE_TYPES = {
    "SHEET_API_EDIT_TRIGGER",
    "SHEET_API_CHANGE_TRIGGER",
    "QUEUE_ROW_ONLY",
    "SOURCE_PACKAGE_ONLY",
    "GENERIC_RUNTIME_HEALTH",
    "HISTORICAL_TRIGGER_ID_ONLY",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RotationContractError(message)


def validate_callable_routes(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Validate destination execution routes without accepting credential values."""

    assert_no_key_material(receipt)
    destinations = receipt.get("destinations")
    _require(isinstance(destinations, list) and destinations, "Destination receipts are required")

    for destination in destinations:
        _require(isinstance(destination, Mapping), "Destination receipt must be an object")
        destination_id = destination.get("destination_id")
        route = destination.get("execution_route")
        _require(isinstance(route, Mapping), f"Callable execution route missing for {destination_id}")

        route_type = route.get("route_type")
        _require(route_type not in NON_EXECUTION_ROUTE_TYPES, f"Non-execution route rejected for {destination_id}")
        _require(route_type in CALLABLE_ROUTE_TYPES, f"Unsupported callable route for {destination_id}")
        _require(
            route.get("depends_on_api_write_trigger") is False,
            f"API-written sheet rows cannot trigger Apps Script execution for {destination_id}",
        )
        _require(
            route.get("callable_provider_readback") is True,
            f"Provider-callable route readback missing for {destination_id}",
        )
        _require(bool(route.get("provider_proof_ref")), f"Provider proof reference missing for {destination_id}")
        _require(bool(route.get("executed_at")), f"Execution timestamp missing for {destination_id}")
        _require(
            route.get("generic_health_response") is False,
            f"Generic runtime health is not semantic execution proof for {destination_id}",
        )

    return copy.deepcopy(dict(receipt))


def validate_complete_rotation(manifest: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the existing closure contract plus callable route proof."""

    validate_receipt(manifest, receipt)
    return validate_callable_routes(receipt)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("receipt")
    args = parser.parse_args()

    manifest = load_json(args.manifest)
    receipt = load_json(args.receipt)
    validate_complete_rotation(manifest, receipt)
    print("OPENAI_ROTATION_CALLABLE_ROUTE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
