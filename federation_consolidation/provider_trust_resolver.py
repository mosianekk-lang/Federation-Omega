from __future__ import annotations

"""Provider-neutral credential/trust resolution without exposing secret material.

This module composes existing Federation controls rather than creating a new
secret platform. It consumes logical capability aliases plus redacted proof
signals and returns the highest *proven* provider-trust state and exact next
action. Raw credentials are prohibited.
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping

from .provider_authority_attachment import canonical_sha256, reject_secret_payload


CONTRACT_SCHEMA = "FEDOMEGA-PROVIDER-TRUST-CONTRACT-1"
EVIDENCE_SCHEMA = "FEDOMEGA-PROVIDER-TRUST-EVIDENCE-1"
RESOLUTION_SCHEMA = "FEDOMEGA-PROVIDER-TRUST-RESOLUTION-1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")

BILLING_ERROR_CODES = {
    "credit_balance_exhausted",
    "insufficient_quota",
    "billing_hard_limit_reached",
}
AUTH_ERROR_CODES = {
    "invalid_api_key",
    "incorrect_api_key",
    "authentication_error",
    "invalid_authentication",
    "key_revoked",
}
TRANSIENT_ERROR_CODES = {
    "rate_limit_exceeded",
    "temporarily_unavailable",
    "server_error",
    "timeout",
}
AUTHENTICATED_PROVIDER_ERROR_CODES = BILLING_ERROR_CODES | TRANSIENT_ERROR_CODES


class ProviderTrustError(RuntimeError):
    """Fail-closed provider trust resolution error."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProviderTrustError(message)


def _load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ProviderTrustError("JSON root must be an object")
    return value


def _write_json(value: Mapping[str, Any], output: str | None) -> None:
    rendered = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if output:
        Path(output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


def validate_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    reject_secret_payload(contract)
    _require(contract.get("schema") == CONTRACT_SCHEMA, "unsupported trust contract schema")
    _require(bool(contract.get("contract_id")), "contract_id is required")
    capabilities = contract.get("capabilities")
    _require(isinstance(capabilities, Mapping) and bool(capabilities), "capabilities are required")

    for alias, spec in capabilities.items():
        _require(isinstance(alias, str) and alias.strip() == alias and alias, "invalid capability alias")
        _require(isinstance(spec, Mapping), f"capability {alias} must be an object")
        _require(bool(spec.get("provider")), f"capability {alias} provider is required")
        bindings = spec.get("bindings")
        _require(isinstance(bindings, list) and bool(bindings), f"capability {alias} bindings are required")
        seen: set[str] = set()
        for binding in bindings:
            _require(isinstance(binding, Mapping), f"capability {alias} binding must be an object")
            binding_id = binding.get("binding_id")
            _require(isinstance(binding_id, str) and bool(binding_id), f"capability {alias} binding_id is required")
            _require(binding_id not in seen, f"duplicate binding_id {binding_id}")
            seen.add(binding_id)
            _require(bool(binding.get("binding_type")), f"binding {binding_id} type is required")
            _require(bool(binding.get("reference")), f"binding {binding_id} reference is required")
            _require(binding.get("secret_value_recorded") is False, f"binding {binding_id} must not record secret values")
    return dict(contract)


def _binding_map(contract: Mapping[str, Any], alias: str) -> dict[str, Mapping[str, Any]]:
    capabilities = contract["capabilities"]
    spec = capabilities.get(alias)
    _require(isinstance(spec, Mapping), f"unknown capability alias: {alias}")
    return {str(item["binding_id"]): item for item in spec["bindings"]}


def validate_evidence(contract: Mapping[str, Any], evidence: Mapping[str, Any]) -> dict[str, Any]:
    reject_secret_payload(evidence)
    _require(evidence.get("schema") == EVIDENCE_SCHEMA, "unsupported trust evidence schema")
    alias = evidence.get("capability_alias")
    _require(isinstance(alias, str) and bool(alias), "capability_alias is required")
    bindings = _binding_map(contract, alias)

    reference_found = evidence.get("credential_reference_found") is True
    runtime_bound = evidence.get("runtime_bound") is True
    authenticated = evidence.get("provider_authenticated") is True
    live = evidence.get("provider_live_verified") is True

    if runtime_bound:
        _require(reference_found, "runtime_bound requires credential_reference_found")
    if authenticated:
        _require(runtime_bound, "provider_authenticated requires runtime_bound")
    if live:
        _require(authenticated, "provider_live_verified requires provider_authenticated")
        digest = evidence.get("semantic_receipt_sha256")
        _require(isinstance(digest, str) and bool(HEX64.fullmatch(digest)), "provider live proof requires semantic receipt SHA-256")

    binding_id = evidence.get("binding_id")
    if reference_found:
        _require(isinstance(binding_id, str) and binding_id in bindings, "known binding_id required when credential reference exists")

    provider_error_code = evidence.get("provider_error_code")
    if provider_error_code is not None:
        _require(isinstance(provider_error_code, str) and bool(provider_error_code), "provider_error_code must be a non-empty string")

    if evidence.get("archive_readback_verified") is True:
        archive_sha = evidence.get("archive_sha256")
        _require(isinstance(archive_sha, str) and bool(HEX64.fullmatch(archive_sha)), "archive readback requires archive SHA-256")

    _require(evidence.get("secret_value_recorded") is False, "secret values must never be recorded")
    return dict(evidence)


def _resolution_base(
    *,
    contract: Mapping[str, Any],
    evidence: Mapping[str, Any],
    binding: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "schema": RESOLUTION_SCHEMA,
        "contract_id": contract["contract_id"],
        "capability_alias": evidence["capability_alias"],
        "provider": contract["capabilities"][evidence["capability_alias"]]["provider"],
        "binding_id": binding.get("binding_id") if binding else None,
        "binding_type": binding.get("binding_type") if binding else None,
        "credential_reference_found": evidence.get("credential_reference_found") is True,
        "runtime_bound": evidence.get("runtime_bound") is True,
        "provider_authenticated": evidence.get("provider_authenticated") is True,
        "provider_live_verified": evidence.get("provider_live_verified") is True,
        "archive_readback_verified": evidence.get("archive_readback_verified") is True,
        "provider_error_code": evidence.get("provider_error_code"),
        "outer_workflow_success_observed": evidence.get("outer_workflow_success") is True,
        "outer_workflow_success_is_promoting": False,
        "secret_value_recorded": False,
        "semantic_receipt_sha256": evidence.get("semantic_receipt_sha256"),
        "archive_sha256": evidence.get("archive_sha256"),
    }


def resolve_provider_trust(contract: Mapping[str, Any], evidence: Mapping[str, Any]) -> dict[str, Any]:
    validated_contract = validate_contract(contract)
    validated_evidence = validate_evidence(validated_contract, evidence)
    alias = validated_evidence["capability_alias"]
    bindings = _binding_map(validated_contract, alias)
    binding = bindings.get(str(validated_evidence.get("binding_id"))) if validated_evidence.get("binding_id") else None
    result = _resolution_base(contract=validated_contract, evidence=validated_evidence, binding=binding)

    reference_found = result["credential_reference_found"]
    runtime_bound = result["runtime_bound"]
    authenticated = result["provider_authenticated"]
    live = result["provider_live_verified"]
    error_code = result["provider_error_code"]

    owner_action_required = False
    credential_rotation_recommended = False

    if live:
        state = "PROVIDER_LIVE_VERIFIED"
        next_action = "NONE"
    elif error_code in BILLING_ERROR_CODES and authenticated:
        state = "BLOCKED_PROVIDER_BILLING"
        next_action = "RESTORE_PROVIDER_BILLING"
        owner_action_required = True
    elif error_code in AUTH_ERROR_CODES and runtime_bound:
        state = "BLOCKED_PROVIDER_AUTH"
        next_action = "ROTATE_OR_REBIND_CREDENTIAL"
        owner_action_required = True
        credential_rotation_recommended = True
    elif error_code in TRANSIENT_ERROR_CODES and authenticated:
        state = "BLOCKED_PROVIDER_TRANSIENT"
        next_action = "RETRY_PROVIDER_PROBE"
    elif authenticated:
        state = "PROVIDER_AUTHENTICATED"
        next_action = "RUN_PROVIDER_LIVE_CANARY"
    elif runtime_bound:
        state = "RUNTIME_BOUND"
        next_action = "RUN_PROVIDER_AUTH_PROBE"
    elif reference_found:
        state = "CREDENTIAL_REFERENCE_FOUND"
        if binding and binding.get("self_service_binding_available") is True:
            next_action = "BIND_EXISTING_REFERENCE"
        else:
            next_action = "OWNER_BIND_EXISTING_REFERENCE"
            owner_action_required = True
    else:
        state = "BOOTSTRAP_REQUIRED"
        next_action = "OWNER_BOOTSTRAP_CREDENTIAL_REFERENCE"
        owner_action_required = True

    result.update(
        {
            "state": state,
            "ready": state == "PROVIDER_LIVE_VERIFIED",
            "next_action": next_action,
            "owner_action_required": owner_action_required,
            "credential_rotation_recommended": credential_rotation_recommended,
            "proof_ladder": [
                "CREDENTIAL_REFERENCE_FOUND",
                "RUNTIME_BOUND",
                "PROVIDER_AUTHENTICATED",
                "PROVIDER_LIVE_VERIFIED",
            ],
            "truth_boundary": (
                "Only inner semantic/provider evidence promotes maturity. Code, CI and outer workflow success are non-promoting signals."
            ),
        }
    )
    unsigned = dict(result)
    result["receipt_sha256"] = canonical_sha256(unsigned)
    return result


def _select_binding_from_key_source(contract: Mapping[str, Any], alias: str, key_source: str) -> str | None:
    bindings = _binding_map(contract, alias)
    source = str(key_source or "").upper()
    if source == "GITHUB_ACTIONS_SECRET":
        for binding_id, binding in bindings.items():
            if str(binding.get("binding_type", "")).startswith("GITHUB_ACTIONS"):
                return binding_id
    if source.startswith("GOOGLE_SECRET_MANAGER"):
        for binding_id, binding in bindings.items():
            if "SECRET_MANAGER" in str(binding.get("binding_type", "")):
                return binding_id
    return None


def evidence_from_chatbridge_artifacts(
    contract: Mapping[str, Any],
    *,
    binding_receipt: Mapping[str, Any],
    canary_receipt: Mapping[str, Any],
    provider_receipt: Mapping[str, Any],
    capability_alias: str = "OPENAI_PRIMARY_RUNTIME",
    outer_workflow_success: bool = False,
) -> dict[str, Any]:
    validate_contract(contract)
    reject_secret_payload(binding_receipt)
    reject_secret_payload(canary_receipt)
    reject_secret_payload(provider_receipt)

    key_bound = binding_receipt.get("key_bound") is True
    key_source = str(binding_receipt.get("key_source") or "NONE")
    binding_id = _select_binding_from_key_source(contract, capability_alias, key_source)
    error_code = canary_receipt.get("child_error_code")
    live = provider_receipt.get("provider_live_verified") is True
    conversation_identity_seen = bool(canary_receipt.get("conversation_id"))
    authenticated = live or conversation_identity_seen or error_code in AUTHENTICATED_PROVIDER_ERROR_CODES

    semantic_sha = provider_receipt.get("receipt_sha256")
    if not isinstance(semantic_sha, str) or not HEX64.fullmatch(semantic_sha):
        semantic_sha = None

    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "capability_alias": capability_alias,
        "binding_id": binding_id,
        "credential_reference_found": bool(key_bound or (key_source and key_source != "NONE")),
        "runtime_bound": key_bound,
        "provider_authenticated": bool(authenticated and key_bound),
        "provider_live_verified": bool(live),
        "provider_error_code": error_code,
        "semantic_receipt_sha256": semantic_sha,
        "archive_readback_verified": False,
        "archive_sha256": None,
        "outer_workflow_success": bool(outer_workflow_success),
        "secret_value_recorded": False,
    }
    return validate_evidence(contract, evidence)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve_parser = subparsers.add_parser("resolve")
    resolve_parser.add_argument("--contract", required=True)
    resolve_parser.add_argument("--evidence", required=True)
    resolve_parser.add_argument("--output")

    chatbridge_parser = subparsers.add_parser("from-chatbridge")
    chatbridge_parser.add_argument("--contract", required=True)
    chatbridge_parser.add_argument("--binding", required=True)
    chatbridge_parser.add_argument("--canary", required=True)
    chatbridge_parser.add_argument("--provider-receipt", required=True)
    chatbridge_parser.add_argument("--capability-alias", default="OPENAI_PRIMARY_RUNTIME")
    chatbridge_parser.add_argument("--outer-workflow-success", action="store_true")
    chatbridge_parser.add_argument("--output")

    args = parser.parse_args()
    contract = _load_json(args.contract)

    if args.command == "resolve":
        evidence = _load_json(args.evidence)
    else:
        evidence = evidence_from_chatbridge_artifacts(
            contract,
            binding_receipt=_load_json(args.binding),
            canary_receipt=_load_json(args.canary),
            provider_receipt=_load_json(args.provider_receipt),
            capability_alias=args.capability_alias,
            outer_workflow_success=args.outer_workflow_success,
        )

    resolution = resolve_provider_trust(contract, evidence)
    _write_json(resolution, args.output)
    if resolution["ready"]:
        print("PROVIDER_TRUST_READY")
    else:
        print(f"PROVIDER_TRUST_{resolution['state']}: {resolution['next_action']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
