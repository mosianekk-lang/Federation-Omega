#!/usr/bin/env python3
"""Require provider-callable, action-specific proof for OpenAI credential rotation.

Spreadsheet rows, queue labels, source packages, historical trigger IDs, generic
runtime health responses, and schema-position assumptions are not execution
proof. Google Sheets API writes must not be treated as firing Apps Script
edit/change triggers.
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

CANONICAL_QUEUE_COLUMNS = {
    "status": "status",
    "result": "resultJson",
    "started_at": "startedAt",
    "completed_at": "completedAt",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RotationContractError(message)


def _validate_queue_contract(destination_id: object, route: Mapping[str, Any]) -> None:
    queue_contract = route.get("queue_contract")
    if queue_contract is None:
        return

    _require(
        isinstance(queue_contract, Mapping),
        f"Queue contract must be an object for {destination_id}",
    )
    _require(
        queue_contract.get("header_driven") is True,
        f"Queue execution must be header-driven for {destination_id}",
    )
    _require(
        queue_contract.get("uses_positional_columns") is False,
        f"Legacy positional queue schema rejected for {destination_id}",
    )
    _require(
        bool(queue_contract.get("schema_readback_ref")),
        f"Queue schema readback missing for {destination_id}",
    )

    column_map = queue_contract.get("column_map")
    _require(
        isinstance(column_map, Mapping),
        f"Queue column map missing for {destination_id}",
    )
    for logical_name, expected_header in CANONICAL_QUEUE_COLUMNS.items():
        _require(
            column_map.get(logical_name) == expected_header,
            f"Canonical queue column {logical_name} must map to "
            f"{expected_header} for {destination_id}",
        )


def validate_callable_routes(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Validate destination execution routes without accepting credential values."""

    assert_no_key_material(receipt)
    destinations = receipt.get("destinations")
    _require(
        isinstance(destinations, list) and destinations,
        "Destination receipts are required",
    )

    fingerprints: dict[str, str] = {}

    for destination in destinations:
        _require(
            isinstance(destination, Mapping),
            "Destination receipt must be an object",
        )
        destination_id = destination.get("destination_id")
        route = destination.get("execution_route")
        _require(
            isinstance(route, Mapping),
            f"Callable execution route missing for {destination_id}",
        )

        route_type = route.get("route_type")
        _require(
            route_type not in NON_EXECUTION_ROUTE_TYPES,
            f"Non-execution route rejected for {destination_id}",
        )
        _require(
            route_type in CALLABLE_ROUTE_TYPES,
            f"Unsupported callable route for {destination_id}",
        )
        _require(
            route.get("depends_on_api_write_trigger") is False,
            f"API-written sheet rows cannot trigger Apps Script execution "
            f"for {destination_id}",
        )
        _require(
            route.get("callable_provider_readback") is True,
            f"Provider-callable route readback missing for {destination_id}",
        )
        _require(
            bool(route.get("provider_proof_ref")),
            f"Provider proof reference missing for {destination_id}",
        )
        _require(
            bool(route.get("executed_at")),
            f"Execution timestamp missing for {destination_id}",
        )
        _require(
            route.get("generic_health_response") is False,
            f"Generic runtime health is not semantic execution proof "
            f"for {destination_id}",
        )

        requested_action = route.get("requested_action")
        response_action = route.get("response_action")
        _require(
            isinstance(requested_action, str) and requested_action.strip(),
            f"Requested action missing for {destination_id}",
        )
        _require(
            response_action == requested_action,
            f"Response action does not match requested action for {destination_id}",
        )
        _require(
            route.get("semantic_fields_verified") is True,
            f"Action-specific semantic fields missing for {destination_id}",
        )

        fingerprint = route.get("semantic_response_fingerprint")
        _require(
            isinstance(fingerprint, str) and fingerprint.strip(),
            f"Semantic response fingerprint missing for {destination_id}",
        )
        previous_action = fingerprints.get(fingerprint)
        _require(
            previous_action is None or previous_action == requested_action,
            "Action-agnostic response fingerprint reused across distinct "
            f"actions: {previous_action} and {requested_action}",
        )
        fingerprints[fingerprint] = requested_action

        _validate_queue_contract(destination_id, route)

    return copy.deepcopy(dict(receipt))


def validate_complete_rotation(
    manifest: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
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
