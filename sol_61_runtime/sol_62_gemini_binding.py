from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "SOL_6_2_GEMINI_BINDING_V1"
DEFAULT_BINDING_PATH = Path(__file__).with_name("SOL_6_2_GEMINI_BINDING.json")


class GeminiBindingError(RuntimeError):
    """Raised when the SOL 6.2 Gemini binding cannot be trusted or used."""


class ConnectionLevel(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONTROL_PLANE_AUTHENTICATED = "CONTROL_PLANE_AUTHENTICATED"
    INFERENCE_VERIFIED_SCOPED = "INFERENCE_VERIFIED_SCOPED"


READ_ONLY_CAPABILITIES = frozenset(
    {
        "READ_PROJECT_METADATA",
        "READ_WIF_PROVIDER_METADATA",
        "VERIFY_ADC_RUNTIME_IDENTITY",
        "READ_GEMINI_AUTHORITY_STATE",
    }
)


@dataclass(frozen=True)
class GeminiBinding:
    route_id: str
    project_id: str
    project_number: str
    region: str
    workflow_run_id: str
    source_sha: str
    oidc_exchange_succeeded: bool
    adc_verified: bool
    hardened_wif_contract_verified: bool
    provider_mutation_performed: bool
    model_inference_performed: bool
    secret_payload_accessed: bool
    declared_connection_state: str
    allowed_capabilities: frozenset[str]
    blocked_capabilities: frozenset[str]
    raw: Mapping[str, Any]

    @property
    def connection_level(self) -> ConnectionLevel:
        if (
            self.oidc_exchange_succeeded
            and self.adc_verified
            and self.hardened_wif_contract_verified
            and self.model_inference_performed
        ):
            return ConnectionLevel.INFERENCE_VERIFIED_SCOPED
        if self.oidc_exchange_succeeded and self.adc_verified:
            return ConnectionLevel.CONTROL_PLANE_AUTHENTICATED
        return ConnectionLevel.DISCONNECTED

    @property
    def control_plane_connected(self) -> bool:
        return self.connection_level in {
            ConnectionLevel.CONTROL_PLANE_AUTHENTICATED,
            ConnectionLevel.INFERENCE_VERIFIED_SCOPED,
        }

    @property
    def inference_ready(self) -> bool:
        return self.connection_level is ConnectionLevel.INFERENCE_VERIFIED_SCOPED

    def assert_capability(self, capability: str) -> None:
        capability = capability.strip().upper()
        if not capability:
            raise GeminiBindingError("empty Gemini capability")
        if capability in self.blocked_capabilities:
            raise GeminiBindingError(f"Gemini capability is fail-closed: {capability}")
        if capability not in self.allowed_capabilities:
            raise GeminiBindingError(f"Gemini capability is not admitted: {capability}")

    def assert_inference_ready(self) -> None:
        if not self.hardened_wif_contract_verified:
            raise GeminiBindingError("Gemini inference held: hardened WIF contract is not verified")
        if not self.adc_verified:
            raise GeminiBindingError("Gemini inference held: ADC runtime identity is not verified")
        if not self.model_inference_performed:
            raise GeminiBindingError("Gemini inference held: no provider-native inference receipt exists")
        if not self.inference_ready:
            raise GeminiBindingError("Gemini inference held: connection is not inference-verified")

    def receipt(self) -> dict[str, Any]:
        body = {
            "schema": "SOL_6_2_GEMINI_BINDING_RECEIPT_V1",
            "route_id": self.route_id,
            "project_id": self.project_id,
            "project_number": self.project_number,
            "region": self.region,
            "workflow_run_id": self.workflow_run_id,
            "source_sha": self.source_sha,
            "connection_level": self.connection_level.value,
            "control_plane_connected": self.control_plane_connected,
            "inference_ready": self.inference_ready,
            "hardened_wif_contract_verified": self.hardened_wif_contract_verified,
            "adc_verified": self.adc_verified,
            "provider_mutation_performed": self.provider_mutation_performed,
            "model_inference_performed": self.model_inference_performed,
            "secret_payload_accessed": self.secret_payload_accessed,
        }
        body["receipt_sha256"] = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return body


def _require_bool(mapping: Mapping[str, Any], key: str) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise GeminiBindingError(f"Gemini binding field must be boolean: {key}")
    return value


def load_binding(path: str | Path | None = None) -> GeminiBinding:
    binding_path = Path(path) if path is not None else DEFAULT_BINDING_PATH
    try:
        payload = json.loads(binding_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GeminiBindingError(f"cannot load Gemini binding: {binding_path}") from exc

    if payload.get("schema") != SCHEMA:
        raise GeminiBindingError(f"unsupported Gemini binding schema: {payload.get('schema')!r}")
    if payload.get("connection_mode") != "READ_ONLY_CONTROL_PLANE":
        raise GeminiBindingError("SOL 6.2 Gemini binding must remain read-only at this maturity state")

    proof = payload.get("live_provider_proof")
    if not isinstance(proof, dict):
        raise GeminiBindingError("live_provider_proof is required")

    run_id = str(proof.get("workflow_run_id", "")).strip()
    source_sha = str(proof.get("source_sha", "")).strip().lower()
    if not run_id.isdigit():
        raise GeminiBindingError("workflow_run_id must be a numeric provider run id")
    if len(source_sha) != 40 or any(ch not in "0123456789abcdef" for ch in source_sha):
        raise GeminiBindingError("source_sha must be a full Git commit SHA")

    allowed = frozenset(str(item).strip().upper() for item in payload.get("allowed_capabilities", []))
    blocked = frozenset(str(item).strip().upper() for item in payload.get("blocked_capabilities", []))
    if allowed != READ_ONLY_CAPABILITIES:
        raise GeminiBindingError("Gemini read-only capability set drifted")
    if "MODEL_INFERENCE" not in blocked or "PROVIDER_MUTATION" not in blocked:
        raise GeminiBindingError("Gemini inference and provider mutation must remain blocked")

    binding = GeminiBinding(
        route_id=str(payload.get("route_id", "")).strip(),
        project_id=str(payload.get("project_id", "")).strip(),
        project_number=str(payload.get("project_number", "")).strip(),
        region=str(payload.get("region", "")).strip(),
        workflow_run_id=run_id,
        source_sha=source_sha,
        oidc_exchange_succeeded=_require_bool(proof, "oidc_exchange_succeeded"),
        adc_verified=_require_bool(proof, "adc_verified"),
        hardened_wif_contract_verified=_require_bool(proof, "hardened_wif_contract_verified"),
        provider_mutation_performed=_require_bool(proof, "provider_mutation_performed"),
        model_inference_performed=_require_bool(proof, "model_inference_performed"),
        secret_payload_accessed=_require_bool(proof, "secret_payload_accessed"),
        declared_connection_state=str(payload.get("connection_state", "")).strip(),
        allowed_capabilities=allowed,
        blocked_capabilities=blocked,
        raw=payload,
    )

    if not binding.route_id or not binding.project_id or not binding.project_number or not binding.region:
        raise GeminiBindingError("Gemini binding identity fields are incomplete")
    if binding.provider_mutation_performed or binding.secret_payload_accessed:
        raise GeminiBindingError("read-only Gemini binding cannot admit mutation or secret-value access")

    expected_state = {
        ConnectionLevel.DISCONNECTED: "DISCONNECTED",
        ConnectionLevel.CONTROL_PLANE_AUTHENTICATED: "CONTROL_PLANE_AUTHENTICATED_INFERENCE_HELD",
        ConnectionLevel.INFERENCE_VERIFIED_SCOPED: "INFERENCE_VERIFIED_SCOPED",
    }[binding.connection_level]
    if binding.declared_connection_state != expected_state:
        raise GeminiBindingError(
            f"declared Gemini state {binding.declared_connection_state!r} does not match proof-derived state {expected_state!r}"
        )

    if binding.connection_level is ConnectionLevel.CONTROL_PLANE_AUTHENTICATED:
        if binding.hardened_wif_contract_verified:
            raise GeminiBindingError("inference-held state must preserve the unresolved WIF proof gap")
        if binding.model_inference_performed:
            raise GeminiBindingError("inference-held state cannot claim model inference")

    return binding


__all__ = [
    "ConnectionLevel",
    "GeminiBinding",
    "GeminiBindingError",
    "load_binding",
]
