#!/usr/bin/env python3
"""SOVARA provider recovery controller.

Provider-neutral orchestration for proof-bound recovery of blocked provider lanes.
The controller does not call providers, mutate IAM, spend provider credit, read
secret values, or promote a provider state.  It consumes redacted evidence and
returns a deterministic route plan with circuit-breakers and auto-continue
conditions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "SOVARA-PROVIDER-RECOVERY-CONTROLLER-V1"
VERSION = "1.0.0"
ISSUES = {
    "google": 52,
    "openai": 179,
    "openrouter": 592,
}
ROUTE_FAMILIES = (
    "REUSE_OPTIMISE",
    "COMPOSE_EXTEND",
    "MATERIAL_NEW",
    "REVERSIBLE_EXPERIMENT",
)
_SECRET_PATTERNS = (
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~-]{16,}\b", re.I),
)


def _reject_secret_material(value: Any) -> None:
    if isinstance(value, Mapping):
        for item in value.values():
            _reject_secret_material(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _reject_secret_material(item)
        return
    if isinstance(value, str):
        for pattern in _SECRET_PATTERNS:
            if pattern.search(value):
                raise ValueError("secret-like material is not accepted by the recovery controller")


def _fingerprint(lane: str, state: str, reason: str) -> str:
    material = json.dumps(
        {"lane": lane, "state": state, "reason": reason},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _lane_receipt(lane: str, state: str, reason: str, *, circuit: str, next_action: str,
                  auto_continue_on: list[str], proof: list[str]) -> dict[str, Any]:
    return {
        "lane": lane,
        "issue": ISSUES[lane],
        "state": state,
        "reason": reason,
        "failure_fingerprint": _fingerprint(lane, state, reason),
        "circuit": circuit,
        "next_action": next_action,
        "auto_continue_on": auto_continue_on,
        "proof": proof,
    }


def classify_google(evidence: Mapping[str, Any]) -> dict[str, Any]:
    closure = evidence.get("closure") or {}
    auth_ok = closure.get("canonical_wif_authenticated") is True
    cloud_ok = closure.get("google_cloud_readback_verified") is True
    operator_ok = closure.get("operator_authenticated_readback_verified") is True
    gemini_ok = closure.get("gemini_semantic_readback_verified") is True
    auth_error = str(
        evidence.get("wif_exchange_error")
        or evidence.get("auth_error_code")
        or evidence.get("auth_error")
        or ""
    ).lower()
    known_stale = evidence.get("canonical_wif_provider_known_stale") is True

    if gemini_ok and cloud_ok and operator_ok:
        return _lane_receipt(
            "google", "VERIFIED", "authenticated Google/Gemini semantic readback is proven",
            circuit="CLOSED", next_action="MAINTAIN_AND_REVALIDATE",
            auto_continue_on=[], proof=["WIF_AUTH", "CLOUD_READBACK", "OPERATOR_READBACK", "GEMINI_SEMANTIC_READBACK"],
        )
    if not auth_ok and (auth_error == "invalid_target" or known_stale):
        return _lane_receipt(
            "google", "AUTHENTICATED_ADMIN_REPAIR_REQUIRED",
            "canonical Google STS target is invalid, disabled, deleted, or otherwise unavailable before token issuance",
            circuit="OPEN_UNCHANGED_WIF_RETRY",
            next_action="REPAIR_EXISTING_CANONICAL_WIF_VIA_AUTHENTICATED_GOOGLE_ADMIN_THEN_VERIFY",
            auto_continue_on=["FRESH_WIF_TOKEN_ISSUED", "PROJECT_257649435135_READBACK"],
            proof=["STS_INVALID_TARGET", "NO_USABLE_GOOGLE_ACCESS_TOKEN"],
        )
    if auth_ok and not cloud_ok:
        return _lane_receipt(
            "google", "AUTHENTICATED_READBACK_PENDING",
            "Google identity is authenticated but exact Cloud Run provider readback is incomplete",
            circuit="CLOSED", next_action="RUN_EXACT_CLOUD_RUN_AND_SECRET_METADATA_READBACK",
            auto_continue_on=["CLOUD_RUN_UID_READBACK"], proof=["WIF_AUTH"],
        )
    if auth_ok and cloud_ok and not operator_ok:
        return _lane_receipt(
            "google", "OPERATOR_AUTHORITY_PENDING",
            "Google provider identity is live but Federation operator authenticated action readback is incomplete",
            circuit="CLOSED", next_action="RECOVER_OPERATOR_TOKEN_BY_SECRET_REFERENCE_AND_RUN_STATUS_READBACK",
            auto_continue_on=["OPERATOR_AUTHENTICATED_STATUS_200"], proof=["WIF_AUTH", "CLOUD_READBACK"],
        )
    if auth_ok and cloud_ok and operator_ok and not gemini_ok:
        return _lane_receipt(
            "google", "GEMINI_SEMANTIC_CANARY_PENDING",
            "Google and operator authority are live but Gemini exact semantic readback is incomplete",
            circuit="CLOSED", next_action="RUN_BOUNDED_GEMINI_EXACT_NONCE_CANARY",
            auto_continue_on=["GEMINI_EXACT_NONCE_MATCH"], proof=["WIF_AUTH", "CLOUD_READBACK", "OPERATOR_READBACK"],
        )
    return _lane_receipt(
        "google", "AUTHORITY_UNPROVEN", "no authenticated Google authority proof is present",
        circuit="OPEN_UNCHANGED_WIF_RETRY", next_action="DISCOVER_MATERIALLY_DIFFERENT_AUTHENTICATED_ADMIN_ROUTE",
        auto_continue_on=["FRESH_GOOGLE_AUTHORITY_RECEIPT"], proof=[],
    )


def classify_openai(evidence: Mapping[str, Any]) -> dict[str, Any]:
    closure = evidence.get("closure") or {}
    key_bound = closure.get("openai_api_authority_bound") is True or evidence.get("api_key_present") is True
    model_ok = closure.get("gpt56_model_resource_verified") is True
    semantic_ok = closure.get("gpt56_semantic_readback_verified") is True
    created_ok = closure.get("gpt56_provider_response_created") is True
    attempts = evidence.get("attempts") or []
    quota_exhausted = any(
        str(a.get("create_error_type") or "").lower() == "insufficient_quota"
        or str(a.get("create_error_code") or "").lower() == "credit_balance_exhausted"
        for a in attempts if isinstance(a, Mapping)
    )

    if semantic_ok:
        return _lane_receipt(
            "openai", "VERIFIED", "GPT-5.6 provider response and exact semantic readback are proven",
            circuit="CLOSED", next_action="RUN_CFBE_REQUIRED_REPETITIONS",
            auto_continue_on=[], proof=["API_AUTHORITY", "GPT56_MODEL_RESOURCE", "RESPONSE_CREATE", "RESPONSE_READBACK"],
        )
    if key_bound and model_ok and quota_exhausted:
        return _lane_receipt(
            "openai", "CREDIT_RECOVERY_REQUIRED",
            "OpenAI API authority and GPT-5.6 model visibility are proven but Responses creation is blocked by exhausted credit",
            circuit="OPEN_PAID_INFERENCE_RETRY",
            next_action="RESTORE_USABLE_PROJECT_CREDIT_OR_BIND_A_FUNDED_PROJECT_THEN_RUN_ONE_BOUNDED_CANARY",
            auto_continue_on=["OPENAI_RESPONSES_CREATE_200"], proof=["API_AUTHORITY", "GPT56_MODEL_RESOURCE", "429_INSUFFICIENT_QUOTA"],
        )
    if not key_bound:
        return _lane_receipt(
            "openai", "KEY_BINDING_REQUIRED", "no OpenAI execution credential is bound",
            circuit="OPEN_UNCHANGED_PROVIDER_RETRY", next_action="BIND_APPROVED_OPENAI_PROJECT_KEY_WITHOUT_EXPOSING_VALUE",
            auto_continue_on=["OPENAI_MODEL_RESOURCE_200"], proof=[],
        )
    if key_bound and model_ok and created_ok and not semantic_ok:
        return _lane_receipt(
            "openai", "SEMANTIC_READBACK_FAILED", "provider response creation succeeded but exact readback did not match",
            circuit="OPEN_UNCHANGED_SEMANTIC_RETRY", next_action="DIAGNOSE_RESPONSE_SHAPE_OR_MODEL_BEHAVIOR_WITH_DIFFERENT_REVERSIBLE_CANARY",
            auto_continue_on=["OPENAI_EXACT_NONCE_READBACK"], proof=["API_AUTHORITY", "GPT56_MODEL_RESOURCE", "RESPONSE_CREATE"],
        )
    return _lane_receipt(
        "openai", "PROVIDER_LIVE_OPEN", "OpenAI provider execution remains incomplete",
        circuit="CLOSED", next_action="RUN_LOWEST_COST_PROVIDER_DIAGNOSTIC",
        auto_continue_on=["OPENAI_PROVIDER_RECEIPT"], proof=[p for p, ok in (("API_AUTHORITY", key_bound), ("GPT56_MODEL_RESOURCE", model_ok)) if ok],
    )


def classify_openrouter(evidence: Mapping[str, Any]) -> dict[str, Any]:
    key_bound = evidence.get("api_key_bound") is True
    catalog = evidence.get("gpt56_catalog_present") is True
    current_key_http = evidence.get("current_key_http")
    credit_positive = evidence.get("account_credit_positive")
    semantic_ok = evidence.get("semantic_readback_verified") is True

    if semantic_ok:
        return _lane_receipt(
            "openrouter", "VERIFIED", "OpenRouter exact semantic provider readback is proven",
            circuit="CLOSED", next_action="KEEP_AS_INDEPENDENT_FALLBACK_ROUTE",
            auto_continue_on=[], proof=["KEY_AUTH", "GPT56_CATALOG", "SEMANTIC_READBACK"],
        )
    if catalog and not key_bound:
        return _lane_receipt(
            "openrouter", "SECURE_KEY_BINDING_REQUIRED",
            "live OpenRouter catalog exposes GPT-5.6 routes but the execution key is not bound to the current runtime",
            circuit="OPEN_UNBOUND_KEY_RETRY", next_action="BIND_OPENROUTER_KEY_BY_SECRET_REFERENCE_THEN_RUN_NO_SPEND_METADATA_READBACK",
            auto_continue_on=["OPENROUTER_KEY_METADATA_200"], proof=["PUBLIC_GPT56_CATALOG"],
        )
    if key_bound and current_key_http == 200 and credit_positive is False:
        return _lane_receipt(
            "openrouter", "CREDIT_RECOVERY_REQUIRED", "OpenRouter key is valid but usable account credit is not available",
            circuit="OPEN_PAID_INFERENCE_RETRY", next_action="RESTORE_OPENROUTER_CREDIT_THEN_RUN_BOUNDED_CANARY",
            auto_continue_on=["OPENROUTER_CREDIT_POSITIVE"], proof=["KEY_AUTH", "GPT56_CATALOG" if catalog else "KEY_AUTH"],
        )
    if key_bound and current_key_http == 200 and credit_positive is True:
        return _lane_receipt(
            "openrouter", "BOUNDED_CANARY_READY", "OpenRouter key and usable credit are present",
            circuit="CLOSED", next_action="RUN_EXACT_NONCE_GPT56_CANARY_WITH_BOUNDED_COST",
            auto_continue_on=["OPENROUTER_EXACT_NONCE_READBACK"], proof=["KEY_AUTH", "ACCOUNT_CREDIT", "GPT56_CATALOG" if catalog else "KEY_AUTH"],
        )
    return _lane_receipt(
        "openrouter", "PROVIDER_BINDING_OPEN", "OpenRouter execution state is incomplete",
        circuit="CLOSED", next_action="RUN_NO_SPEND_KEY_AND_CATALOG_METADATA_PROBE",
        auto_continue_on=["OPENROUTER_METADATA_RECEIPT"], proof=["PUBLIC_GPT56_CATALOG"] if catalog else [],
    )


def route_tournament(lanes: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    google = lanes["google"]["state"]
    openai = lanes["openai"]["state"]
    openrouter = lanes["openrouter"]["state"]

    candidates = [
        {
            "family": "REUSE_OPTIMISE",
            "route": "repair existing canonical Google WIF then reuse Secret Manager/operator/gateway",
            "priority": 100 if google == "AUTHENTICATED_ADMIN_REPAIR_REQUIRED" else 70,
            "reason": "restores the highest number of downstream provider capabilities with the least architectural duplication",
        },
        {
            "family": "COMPOSE_EXTEND",
            "route": "bind OpenRouter through the recovered private secret plane as an independent fallback",
            "priority": 85 if openrouter == "SECURE_KEY_BINDING_REQUIRED" else 55,
            "reason": "adds provider diversity while preserving direct-provider proof separation",
        },
        {
            "family": "REVERSIBLE_EXPERIMENT",
            "route": "run one bounded exact-nonce canary after a provider becomes funded/authorized",
            "priority": 75 if openai == "CREDIT_RECOVERY_REQUIRED" else 50,
            "reason": "highest-information proof with minimal spend and no production traffic",
        },
        {
            "family": "MATERIAL_NEW",
            "route": "create a new provider control plane only if verified reuse/repair is impossible",
            "priority": 10,
            "reason": "last resort because it increases estate complexity and duplicates existing authority architecture",
        },
    ]
    candidates.sort(key=lambda x: (-x["priority"], x["family"]))
    return {"selected": candidates[0], "candidates": candidates}


def build_recovery_receipt(evidence: Mapping[str, Any]) -> dict[str, Any]:
    _reject_secret_material(evidence)
    lanes = {
        "google": classify_google(evidence.get("google") or {}),
        "openai": classify_openai(evidence.get("openai") or {}),
        "openrouter": classify_openrouter(evidence.get("openrouter") or {}),
    }
    tournament = route_tournament(lanes)
    blocked = [name for name, lane in lanes.items() if lane["state"] != "VERIFIED"]
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "mission": "FORMATION_OMEGA_PROVIDER_CLOSURE",
        "orchestrator": "SOVARA",
        "formation_route_families": list(ROUTE_FAMILIES),
        "lanes": lanes,
        "route_tournament": tournament,
        "execution_policy": {
            "independent_lanes_continue": True,
            "unchanged_retry_when_circuit_open": False,
            "one_consequential_provider_lane_at_a_time": True,
            "secret_values_accepted": False,
            "provider_effect_performed_by_controller": False,
            "paid_inference_performed_by_controller": False,
            "promotion_requires_surface_specific_readback": True,
        },
        "blocked_lanes": blocked,
        "all_required_provider_lanes_verified": not blocked,
        "durable_trackers": ISSUES,
        "next_best_automated_path": tournament["selected"]["route"],
    }


def _load(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a proof-bound SOVARA provider recovery route plan")
    parser.add_argument("--google")
    parser.add_argument("--openai")
    parser.add_argument("--openrouter")
    parser.add_argument("--out")
    args = parser.parse_args()
    evidence = {
        "google": _load(args.google),
        "openai": _load(args.openai),
        "openrouter": _load(args.openrouter),
    }
    receipt = build_recovery_receipt(evidence)
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
