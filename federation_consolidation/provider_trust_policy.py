from __future__ import annotations

"""Shared provider-trust use policy for AAA receiving homes.

This module does not carry credentials and does not perform provider calls. It
validates a redacted Provider Trust Resolution receipt and exposes only the
minimum reusable policy signals that receiving systems need. Local systems must
still enforce their own evidence, mutation, privacy, approval and readback
requirements.
"""

from dataclasses import dataclass
from typing import Any, Mapping

from .provider_authority_attachment import canonical_sha256, reject_secret_payload
from .provider_trust_resolver import HEX64, RESOLUTION_SCHEMA, ProviderTrustError


@dataclass(frozen=True)
class ProviderTrustUseDecision:
    capability_alias: str
    state: str
    provider_runtime_ready: bool
    system_action_available: bool
    owner_action_required: bool
    next_action: str
    credential_rotation_recommended: bool
    trust_receipt_sha256: str
    consequential_authority_granted: bool = False


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProviderTrustError(message)


def validate_provider_trust_resolution(resolution: Mapping[str, Any]) -> dict[str, Any]:
    """Validate integrity and state semantics of a trust-resolution receipt."""

    reject_secret_payload(resolution)
    _require(resolution.get("schema") == RESOLUTION_SCHEMA, "unsupported provider trust resolution schema")
    _require(resolution.get("secret_value_recorded") is False, "provider trust resolution must not record secret values")

    receipt_sha = resolution.get("receipt_sha256")
    _require(isinstance(receipt_sha, str) and bool(HEX64.fullmatch(receipt_sha)), "provider trust resolution requires receipt SHA-256")
    unsigned = dict(resolution)
    unsigned.pop("receipt_sha256", None)
    _require(canonical_sha256(unsigned) == receipt_sha, "provider trust resolution receipt hash mismatch")

    alias = resolution.get("capability_alias")
    state = resolution.get("state")
    _require(isinstance(alias, str) and bool(alias), "provider trust capability alias is required")
    _require(isinstance(state, str) and bool(state), "provider trust state is required")

    reference_found = resolution.get("credential_reference_found") is True
    runtime_bound = resolution.get("runtime_bound") is True
    authenticated = resolution.get("provider_authenticated") is True
    live = resolution.get("provider_live_verified") is True
    ready = resolution.get("ready") is True

    if runtime_bound:
        _require(reference_found, "runtime_bound requires credential_reference_found")
    if authenticated:
        _require(runtime_bound, "provider_authenticated requires runtime_bound")
    if live:
        _require(authenticated, "provider_live_verified requires provider_authenticated")
    if ready:
        _require(state == "PROVIDER_LIVE_VERIFIED" and live, "ready may only accompany PROVIDER_LIVE_VERIFIED")
    if state == "PROVIDER_LIVE_VERIFIED":
        _require(all((reference_found, runtime_bound, authenticated, live, ready)), "PROVIDER_LIVE_VERIFIED state is internally inconsistent")
    if state == "BLOCKED_PROVIDER_BILLING":
        _require(authenticated and not live, "billing block requires authenticated non-live provider state")
        _require(resolution.get("credential_rotation_recommended") is False, "billing block must not recommend credential rotation")
    if state == "BLOCKED_PROVIDER_AUTH":
        _require(runtime_bound and not live, "auth block requires runtime-bound non-live state")
        _require(resolution.get("credential_rotation_recommended") is True, "auth block must recommend credential repair")
    if state == "BLOCKED_PROVIDER_TRANSIENT":
        _require(authenticated and not live, "transient block requires authenticated non-live provider state")
        _require(resolution.get("owner_action_required") is False, "transient provider block must remain system-actionable")

    return dict(resolution)


def provider_trust_use_decision(
    resolution: Mapping[str, Any],
    *,
    expected_capability_alias: str | None = None,
) -> ProviderTrustUseDecision:
    """Convert a verified resolution into provider-neutral receiving-home policy."""

    validated = validate_provider_trust_resolution(resolution)
    alias = str(validated["capability_alias"])
    if expected_capability_alias is not None:
        _require(alias == expected_capability_alias, "provider trust capability alias mismatch")

    state = str(validated["state"])
    owner_action_required = validated.get("owner_action_required") is True
    provider_runtime_ready = state == "PROVIDER_LIVE_VERIFIED" and validated.get("ready") is True
    system_action_available = (
        provider_runtime_ready
        or (
            not owner_action_required
            and str(validated.get("next_action") or "NONE") not in {"", "NONE"}
        )
    )

    return ProviderTrustUseDecision(
        capability_alias=alias,
        state=state,
        provider_runtime_ready=provider_runtime_ready,
        system_action_available=system_action_available,
        owner_action_required=owner_action_required,
        next_action=str(validated.get("next_action") or "NONE"),
        credential_rotation_recommended=validated.get("credential_rotation_recommended") is True,
        trust_receipt_sha256=str(validated["receipt_sha256"]),
        consequential_authority_granted=False,
    )


__all__ = [
    "ProviderTrustUseDecision",
    "provider_trust_use_decision",
    "validate_provider_trust_resolution",
]
