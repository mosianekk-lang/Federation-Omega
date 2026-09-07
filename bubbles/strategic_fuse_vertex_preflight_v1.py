"""Strategic FUSE Vertex AI A0 callability preflight v1.

This is a no-inference, no-provider-mutation adapter for GAP-STRATFUSE-002. It reuses
the existing federation-omega-operator `READ_GEMINI_VERTEX_CAPABILITY` action and emits
a truth-bounded receipt even when the callable edge is unavailable.

It does not enable the semantic Gemini canary, grant IAM, reveal credentials, mutate
provider configuration, spend on inference, bind FSED authority, or claim a provider
runtime. A successful receipt proves only current callable A0 capability readback.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Callable

from ops.federation_omega_operator.cios_client import invoke as operator_invoke

SCHEMA = "STRATEGIC-FUSE-VERTEX-A0-PREFLIGHT-V1"
VERSION = "1.0.0"
ACTION = "READ_GEMINI_VERTEX_CAPABILITY"
DEFAULT_OPERATOR = "https://federation-omega-operator-257649435135.africa-south1.run.app"
EXPECTED_TARGET = {
    "project": "sov-hybrid-suite",
    "location": "global",
    "model": "gemini-2.5-flash",
    "tenantId": "federation-omega",
}


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


def _safe_error(exc: Exception) -> str:
    text = " ".join(str(exc).split())[:800]
    text = re.sub(r"(?i)(bearer|authorization|x-fo-admin-token|fo_admin_token)\s*[:=]?\s*[^ ,;]+", r"\1=[REDACTED]", text)
    return text


@dataclass(frozen=True, slots=True)
class PreflightReceipt:
    schema: str
    version: str
    state: str
    action: str
    source_ref: str
    operator_url: str
    target: dict[str, str]
    operator_invocation_attempted: bool
    operator_authenticated_response_observed: bool
    provider_native_capability_readback_verified: bool
    vertex_service_state: str
    operator_status: str
    semantic_execution_attempted: bool
    incremental_cost: int | float | None
    silent_fallback: bool
    provider_mutation_attempted: bool
    authority_delta: str
    failure_fingerprint: str
    failure_detail: str
    next_transition: str
    truth_boundary: str
    receipt_sha256: str


def run_preflight(
    *,
    operator_url: str = DEFAULT_OPERATOR,
    source_ref: str,
    invoke_fn: Callable[[str, str, dict[str, Any]], dict[str, Any]] = operator_invoke,
) -> PreflightReceipt:
    source_ref = str(source_ref).strip()
    if not source_ref:
        raise ValueError("SOURCE_REF_REQUIRED")
    operator_url = str(operator_url).strip().rstrip("/")
    if operator_url != DEFAULT_OPERATOR:
        raise ValueError("OPERATOR_TARGET_MISMATCH")

    state = "HELD_CALLABILITY_UNPROVEN"
    authenticated = False
    capability_verified = False
    service_state = "UNKNOWN"
    operator_status = "NO_RESPONSE"
    semantic_attempted = False
    incremental_cost: int | float | None = None
    silent_fallback = False
    failure_detail = ""
    failure_fingerprint = ""

    try:
        result = invoke_fn(operator_url, ACTION, dict(EXPECTED_TARGET))
        authenticated = True
        if not isinstance(result, dict):
            raise RuntimeError("OPERATOR_RESPONSE_NOT_OBJECT")
        operator_status = str(result.get("status", "UNKNOWN"))
        service_state = str(result.get("serviceState", "UNKNOWN"))
        semantic_attempted = bool(result.get("semanticExecutionAttempted", False))
        incremental_cost = result.get("incrementalCost")
        silent_fallback = bool(result.get("silentFallback", False))
        observed_target = result.get("target")
        target_match = isinstance(observed_target, dict) and all(
            observed_target.get(key) == value for key, value in EXPECTED_TARGET.items()
        )
        capability_verified = bool(
            result.get("ok") is True
            and operator_status == "GEMINI_VERTEX_CAPABILITY_READ"
            and service_state == "ENABLED"
            and target_match
            and semantic_attempted is False
            and incremental_cost == 0
            and silent_fallback is False
        )
        if capability_verified:
            state = "VERTEX_A0_CAPABILITY_READBACK_VERIFIED"
        else:
            state = "HELD_PROVIDER_CAPABILITY_OR_TRUTH_BOUNDARY"
            failure_detail = (
                f"status={operator_status};serviceState={service_state};"
                f"targetMatch={target_match};semanticExecutionAttempted={semantic_attempted};"
                f"incrementalCost={incremental_cost};silentFallback={silent_fallback}"
            )
            failure_fingerprint = _digest(failure_detail)
    except Exception as exc:  # receipt is the evidence even when callability fails
        failure_detail = _safe_error(exc)
        failure_fingerprint = _digest({"type": type(exc).__name__, "detail": failure_detail})

    if capability_verified:
        next_transition = (
            "QUALIFY_ACTION_SPECIFIC_STRATEGIC_RUNTIME_BINDING; semantic Gemini/FSED work remains separately gated"
        )
    else:
        next_transition = (
            "PRESERVE_FAILURE_FINGERPRINT_AND_SELECT_MATERIALLY_DIFFERENT_CALLABLE_ROUTE_OR_CHANGED_PREDICATE"
        )

    material = {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "action": ACTION,
        "source_ref": source_ref,
        "operator_url": operator_url,
        "target": EXPECTED_TARGET,
        "operator_invocation_attempted": True,
        "operator_authenticated_response_observed": authenticated,
        "provider_native_capability_readback_verified": capability_verified,
        "vertex_service_state": service_state,
        "operator_status": operator_status,
        "semantic_execution_attempted": semantic_attempted,
        "incremental_cost": incremental_cost,
        "silent_fallback": silent_fallback,
        "provider_mutation_attempted": False,
        "authority_delta": "NONE",
        "failure_fingerprint": failure_fingerprint,
        "failure_detail": failure_detail,
        "next_transition": next_transition,
        "truth_boundary": (
            "Success proves only a current authenticated call through the existing federation-omega-operator "
            "to the zero-inference READ_GEMINI_VERTEX_CAPABILITY action with exact target/model readback. "
            "It does not prove Gemini semantic inference, FSED access, Strategic runtime binding, IAM change, "
            "background autonomy, provider mutation, production promotion or COMPLETE_VERIFIED."
        ),
    }
    return PreflightReceipt(receipt_sha256=_digest(material), **material)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Strategic FUSE Vertex A0 callability preflight")
    parser.add_argument("--operator", default=DEFAULT_OPERATOR)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run_preflight(operator_url=args.operator, source_ref=args.source_ref)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(asdict(receipt), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
