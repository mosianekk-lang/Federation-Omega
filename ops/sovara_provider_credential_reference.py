#!/usr/bin/env python3
"""Reference-only provider credential binding for SOVARA/Formation Omega.

This module never resolves, accepts, logs, or transports credential values. It
converts stable provider-secret handles into an execution-surface binding plan
that a separately authorised runtime may consume.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Any, Mapping

SCHEMA = "SOVARA-PROVIDER-CREDENTIAL-REFERENCE-V1"
SUPPORTED_KINDS = {
    "gcp_secret_name",
    "script_property_name",
    "environment_alias",
}
SUPPORTED_PROVIDERS = {"openrouter", "openai", "gemini", "anthropic", "deepseek"}

_ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,79}$")
_GCP_RE = re.compile(r"^[a-z][a-z0-9-]{2,254}$")
_SCRIPT_PROP_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,99}$")


class CredentialReferenceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CredentialReference:
    provider: str
    kind: str
    locator: str
    version: str | None = None


@dataclass(frozen=True, slots=True)
class BindingPlan:
    schema: str
    provider: str
    source_kind: str
    source_locator: str
    source_version: str | None
    destination_alias: str
    resolution_surface: str
    value_exposed: bool
    value_persisted: bool
    provider_call_performed: bool
    proof_required: tuple[str, ...]
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fingerprint(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate(ref: CredentialReference) -> None:
    if ref.provider not in SUPPORTED_PROVIDERS:
        raise CredentialReferenceError("unsupported provider")
    if ref.kind not in SUPPORTED_KINDS:
        raise CredentialReferenceError("unsupported reference kind")
    if not ref.locator or len(ref.locator) > 255:
        raise CredentialReferenceError("invalid reference locator")

    if ref.kind == "environment_alias" and not _ENV_RE.fullmatch(ref.locator):
        raise CredentialReferenceError("environment alias must be a symbolic name")
    if ref.kind == "gcp_secret_name" and not _GCP_RE.fullmatch(ref.locator):
        raise CredentialReferenceError("GCP secret reference must be a secret name only")
    if ref.kind == "script_property_name" and not _SCRIPT_PROP_RE.fullmatch(ref.locator):
        raise CredentialReferenceError("script property reference must be a symbolic name")


def build_binding_plan(ref: CredentialReference, *, resolution_surface: str) -> BindingPlan:
    """Build a value-free binding plan for a separately authorised runtime."""
    _validate(ref)
    if resolution_surface not in {"google_cloud", "apps_script", "private_runtime"}:
        raise CredentialReferenceError("unsupported resolution surface")

    core = {
        "schema": SCHEMA,
        "provider": ref.provider,
        "source_kind": ref.kind,
        "source_locator": ref.locator,
        "source_version": ref.version,
        "destination_alias": "PROVIDER_CREDENTIAL",
        "resolution_surface": resolution_surface,
        "value_exposed": False,
        "value_persisted": False,
        "provider_call_performed": False,
        "proof_required": [
            "REFERENCE_EXISTS",
            "EXECUTION_IDENTITY_AUTHORISED",
            "REFERENCE_BOUND_WITHOUT_VALUE_DISCLOSURE",
            "PROVIDER_METADATA_READBACK",
            "EXACT_NONCE_SEMANTIC_READBACK",
        ],
    }
    return BindingPlan(**core, fingerprint=_fingerprint(core))


def choose_openrouter_binding_route(*, google_admin_ready: bool, apps_script_property_ready: bool) -> dict[str, Any]:
    """Select the strongest current secret-reference route without reading a value."""
    if google_admin_ready:
        return {
            "family": "REUSE_OPTIMISE",
            "route": "google_cloud_secret_reference",
            "next_gate": "SECRET_REFERENCE_METADATA_READBACK",
            "provider_call_performed": False,
        }
    if apps_script_property_ready:
        return {
            "family": "COMPOSE_EXTEND",
            "route": "apps_script_property_reference",
            "next_gate": "SCRIPT_PROPERTY_REFERENCE_BINDING_READBACK",
            "provider_call_performed": False,
        }
    return {
        "family": "REVERSIBLE_EXPERIMENT",
        "route": "hold_until_secret_bearing_runtime_available",
        "next_gate": "AUTHORISED_SECRET_REFERENCE_RESOLVER_AVAILABLE",
        "provider_call_performed": False,
    }
