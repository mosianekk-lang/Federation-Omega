#!/usr/bin/env python3
"""Validate and render redacted OpenAI credential-rotation evidence.

This module never accepts a raw credential as a command-line argument and never
prints credential material. It validates only metadata, secret references and
redacted provider/runtime receipts.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

MANIFEST_SCHEMA = "FEDOMEGA-OPENAI-CREDENTIAL-ROTATION-1"
RECEIPT_SCHEMA = "FEDOMEGA-OPENAI-CREDENTIAL-ROTATION-RECEIPT-1"
SHARED_ALIAS = "OPENAI_API_KEY"
DESTINATION_IDS = {"mosiane-live-thread", "modisa-legal-v2"}
KEY_PATTERN = re.compile(r"(?<![A-Za-z0-9])sk-(?:proj-)?[A-Za-z0-9_-]{20,}")
SECRET_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{2,62}$")


class RotationContractError(ValueError):
    """Raised when a manifest or receipt violates the rotation contract."""


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise RotationContractError("JSON root must be an object")
    return payload


def _iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_strings(item)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RotationContractError(message)


def assert_no_key_material(payload: Mapping[str, Any]) -> None:
    for value in _iter_strings(payload):
        if KEY_PATTERN.search(value):
            raise RotationContractError("Raw OpenAI credential pattern detected")


def validate_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a rotation manifest and return a defensive copy."""

    assert_no_key_material(manifest)
    _require(manifest.get("schema") == MANIFEST_SCHEMA, "Unsupported manifest schema")
    _require(bool(manifest.get("manifest_id")), "manifest_id is required")
    _require(bool(manifest.get("owner")), "owner is required")

    provider = manifest.get("provider_key")
    _require(isinstance(provider, Mapping), "provider_key must be an object")
    _require(bool(provider.get("display_name")), "provider key display name is required")
    _require(
        provider.get("creation_state")
        in {
            "OWNER_ASSERTED_CREATED_NOT_PROVIDER_READ_BACK",
            "PROVIDER_NATIVE_CREATION_VERIFIED",
        },
        "Invalid provider key creation state",
    )
    _require(provider.get("raw_value_available_to_repository") is False, "Repository must not receive raw key")
    _require(provider.get("raw_value_available_to_chat") is False, "Chat must not receive raw key")

    legacy = manifest.get("legacy_credential")
    _require(isinstance(legacy, Mapping), "legacy_credential must be an object")
    _require(legacy.get("shared_alias") == SHARED_ALIAS, "Legacy alias must be recorded exactly")
    _require(legacy.get("compromise_state") == "TREAT_AS_COMPROMISED", "Legacy key must remain compromised")

    destinations = manifest.get("destinations")
    _require(isinstance(destinations, list), "destinations must be a list")
    _require(len(destinations) == 2, "Exactly two credential destinations are required")

    seen_destinations: set[str] = set()
    seen_secret_ids: set[str] = set()
    for destination in destinations:
        _require(isinstance(destination, Mapping), "Each destination must be an object")
        destination_id = destination.get("destination_id")
        secret_id = destination.get("secret_id")
        _require(destination_id in DESTINATION_IDS, f"Unexpected destination: {destination_id!r}")
        _require(destination_id not in seen_destinations, f"Duplicate destination: {destination_id}")
        seen_destinations.add(destination_id)

        _require(isinstance(secret_id, str) and bool(SECRET_ID_PATTERN.fullmatch(secret_id)), "Invalid secret_id")
        _require(secret_id != SHARED_ALIAS, "The compromised shared alias cannot be reused")
        _require(secret_id not in seen_secret_ids, "Each destination requires a distinct secret reference")
        seen_secret_ids.add(secret_id)

        _require(destination.get("vault") == "GOOGLE_SECRET_MANAGER", "Unsupported vault")
        _require(
            destination.get("binding_mode") == "SECRET_MANAGER_REFERENCE_REQUIRED",
            "Literal credential binding is forbidden",
        )
        _require(destination.get("runtime_environment_name") == SHARED_ALIAS, "Runtime environment contract changed")
        _require(bool(destination.get("canary_mode")), "Canary mode is required")
        _require(bool(destination.get("semantic_probe")), "Semantic probe is required")
        _require(str(destination.get("promotion_state", "")).startswith("BLOCKED_"), "Promotion must remain blocked")

        if destination_id == "mosiane-live-thread":
            _require(destination.get("runtime_service") == "mosiane-live-thread", "Live Thread service mismatch")
            identity = destination.get("runtime_identity")
            _require(isinstance(identity, str) and identity.endswith(".gserviceaccount.com"), "Live Thread identity missing")
            _require(
                destination.get("canary_mode") == "ZERO_TRAFFIC_CLOUD_RUN_REVISION",
                "Live Thread must use a zero-traffic canary",
            )
        elif destination_id == "modisa-legal-v2":
            _require(
                destination.get("canary_mode") == "ISOLATED_NON_PRODUCTION_SEVEN_CHAMBER_QUALIFICATION",
                "MODISA must use isolated seven-chamber qualification",
            )

    _require(seen_destinations == DESTINATION_IDS, "Required destinations are incomplete")
    _require(
        manifest.get("completion_state") == "INCOMPLETE_BINDING_CANARY_REVOCATION_AND_REJECTION_UNVERIFIED",
        "Manifest must not claim completion before evidence exists",
    )
    return copy.deepcopy(dict(manifest))


def build_redacted_plan(manifest: Mapping[str, Any]) -> dict[str, Any]:
    validated = validate_manifest(manifest)
    destinations: list[dict[str, Any]] = []
    for destination in validated["destinations"]:
        destination_id = destination["destination_id"]
        secret_id = destination["secret_id"]
        if destination_id == "mosiane-live-thread":
            binding = {
                "vault_ingest": "AUTHORISED_PROVIDER_OPERATOR_SECURE_STDIN_REQUIRED",
                "runtime_binding_template": (
                    "gcloud run services update mosiane-live-thread "
                    "--project sov-hybrid-suite --region africa-south1 "
                    f"--update-secrets OPENAI_API_KEY={secret_id}:latest --no-traffic"
                ),
                "canary": "CREATE_ZERO_TRAFFIC_REVISION_THEN_VERIFY_HEALTH_SEMANTICS_IDENTITY_AND_SECRET_REFERENCE",
            }
        else:
            binding = {
                "vault_ingest": "AUTHORISED_PROVIDER_OPERATOR_SECURE_STDIN_REQUIRED",
                "runtime_binding_template": (
                    f"PRIVATE_EXECUTION_PLANE_ENV_FROM_SECRET_REFERENCE:{secret_id}:latest"
                ),
                "canary": "RUN_ISOLATED_SEVEN_CHAMBER_QUALIFICATION_WITH_EXTERNAL_ACTIONS_DISABLED",
            }
        destinations.append(
            {
                "destination_id": destination_id,
                "secret_id": secret_id,
                "binding": binding,
                "promotion_state": destination["promotion_state"],
            }
        )

    plan = {
        "schema": "FEDOMEGA-OPENAI-CREDENTIAL-ROTATION-PLAN-1",
        "manifest_id": validated["manifest_id"],
        "contains_raw_credential": False,
        "destinations": destinations,
        "closure_order": [
            "BIND_DESTINATION_SECRET_REFERENCES",
            "READ_BACK_SECRET_REFERENCES_AND_RUNTIME_IDENTITIES",
            "RUN_ISOLATED_CANARIES",
            "CAPTURE_ROLLBACK_TARGETS",
            "PROMOTE_ONLY_VERIFIED_REVISIONS",
            "REVOKE_EXPOSED_PROVIDER_KEY",
            "PROVE_EXPOSED_KEY_REJECTION",
            "ISSUE_REDACTED_CLOSURE_RECEIPT",
        ],
    }
    assert_no_key_material(plan)
    return plan


def validate_receipt(manifest: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a redacted closure receipt. Fail closed on missing proof."""

    validated_manifest = validate_manifest(manifest)
    assert_no_key_material(receipt)
    _require(receipt.get("schema") == RECEIPT_SCHEMA, "Unsupported receipt schema")
    _require(receipt.get("manifest_id") == validated_manifest["manifest_id"], "Receipt manifest mismatch")
    _require(receipt.get("plaintext_observed") is False, "Plaintext credential exposure reported")

    expected = {item["destination_id"]: item for item in validated_manifest["destinations"]}
    actual = receipt.get("destinations")
    _require(isinstance(actual, list) and len(actual) == len(expected), "Destination receipt set incomplete")

    seen: set[str] = set()
    for item in actual:
        _require(isinstance(item, Mapping), "Destination receipt must be an object")
        destination_id = item.get("destination_id")
        _require(destination_id in expected, f"Unexpected receipt destination: {destination_id!r}")
        _require(destination_id not in seen, f"Duplicate destination receipt: {destination_id}")
        seen.add(destination_id)
        expected_item = expected[destination_id]
        _require(item.get("secret_id") == expected_item["secret_id"], "Secret reference mismatch")
        _require(item.get("secret_reference_readback") is True, "Secret-reference readback missing")
        _require(item.get("least_privilege_identity_readback") is True, "Identity readback missing")
        _require(item.get("canary_health_verified") is True, "Canary health proof missing")
        _require(item.get("semantic_probe_verified") is True, "Semantic proof missing")
        _require(item.get("rollback_target_captured") is True, "Rollback proof missing")
        _require(item.get("production_promotion") in {False, "VERIFIED_REVISION_ONLY"}, "Unsafe promotion state")

    _require(seen == set(expected), "Destination receipt set incomplete")
    provider = receipt.get("provider_closure")
    _require(isinstance(provider, Mapping), "provider_closure must be an object")
    _require(provider.get("exposed_key_revoked") is True, "Provider revocation is unproven")
    _require(provider.get("exposed_key_rejection_verified") is True, "Old-key rejection is unproven")
    _require(receipt.get("completion_state") == "COMPLETE_REDACTED_AND_VERIFIED", "Invalid completion state")
    return copy.deepcopy(dict(receipt))


def receipt_template(manifest: Mapping[str, Any]) -> dict[str, Any]:
    validated = validate_manifest(manifest)
    return {
        "schema": RECEIPT_SCHEMA,
        "manifest_id": validated["manifest_id"],
        "plaintext_observed": False,
        "destinations": [
            {
                "destination_id": item["destination_id"],
                "secret_id": item["secret_id"],
                "secret_reference_readback": False,
                "least_privilege_identity_readback": False,
                "canary_health_verified": False,
                "semantic_probe_verified": False,
                "rollback_target_captured": False,
                "production_promotion": False,
            }
            for item in validated["destinations"]
        ],
        "provider_closure": {
            "exposed_key_revoked": False,
            "exposed_key_rejection_verified": False,
        },
        "completion_state": "INCOMPLETE",
    }


def _write_json(payload: Mapping[str, Any], output: str | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output:
        Path(output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate-manifest")
    validate_parser.add_argument("manifest")

    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("manifest")
    plan_parser.add_argument("--output")

    template_parser = subparsers.add_parser("receipt-template")
    template_parser.add_argument("manifest")
    template_parser.add_argument("--output")

    receipt_parser = subparsers.add_parser("validate-receipt")
    receipt_parser.add_argument("manifest")
    receipt_parser.add_argument("receipt")

    args = parser.parse_args()
    manifest = load_json(args.manifest)

    if args.command == "validate-manifest":
        validate_manifest(manifest)
        print("OPENAI_ROTATION_MANIFEST_VALID")
    elif args.command == "plan":
        _write_json(build_redacted_plan(manifest), args.output)
    elif args.command == "receipt-template":
        _write_json(receipt_template(manifest), args.output)
    elif args.command == "validate-receipt":
        receipt = load_json(args.receipt)
        validate_receipt(manifest, receipt)
        print("OPENAI_ROTATION_RECEIPT_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
