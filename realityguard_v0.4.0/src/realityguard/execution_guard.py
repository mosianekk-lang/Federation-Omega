"""Fail-closed guard for Federation-controlled side-effecting tool calls.

The guard is host-neutral. A caller places it immediately before dispatch,
feeds the result through observe_dispatch, and asks guard_claim_release before
publishing an effect-state claim. Local use never self-certifies native
ChatGPT or provider-host binding.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .schema import InputError


SCHEMA_VERSION = "realityguard.execution-guard.v1"
SIDE_EFFECT_CLASSES = {
    "EXTERNAL_MESSAGE", "FILE_WRITE", "REPOSITORY_WRITE",
    "LEGAL_FILING", "SERVICE", "DEPLOYMENT", "DESTRUCTIVE",
}
FAILED_RETRY_STATES = {"FAILED", "UNVERIFIED", "TRANSPORT_SUCCEEDED", "RECEIPT_MISSING"}
INLINE_BINARY_KEYS = {
    "base64", "content_base64", "base64_payload", "raw_bytes",
    "attachment_data", "binary_data", "data_uri",
}
KNOWN_BINARY_PREFIXES = ("JVBERi0", "UEsDB", "iVBOR", "/9j/")
BASE64ISH = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")


class GuardDecision(str, Enum):
    ALLOW_READ = "ALLOW_READ"
    ALLOW_DISPATCH = "ALLOW_DISPATCH"
    BLOCK_INVALID_AUTHORITY = "BLOCK_INVALID_AUTHORITY"
    BLOCK_UNVERIFIED_ROUTE = "BLOCK_UNVERIFIED_ROUTE"
    BLOCK_UNSAFE_BINARY_TRANSPORT = "BLOCK_UNSAFE_BINARY_TRANSPORT"
    BLOCK_UNCHANGED_RETRY = "BLOCK_UNCHANGED_RETRY"
    BLOCK_IDEMPOTENCY_REPLAY = "BLOCK_IDEMPOTENCY_REPLAY"
    BLOCK_UNVERIFIED_RECIPIENT = "BLOCK_UNVERIFIED_RECIPIENT"
    BLOCK_MISSING_EXPECTED_FRUIT = "BLOCK_MISSING_EXPECTED_FRUIT"
    BLOCK_CLAIM_RELEASE = "BLOCK_CLAIM_RELEASE"


class EffectState(str, Enum):
    VALIDATED = "VALIDATED"
    AUTHORIZED = "AUTHORIZED"
    QUARANTINED = "QUARANTINED"
    FAILED = "FAILED"
    TRANSPORT_SUCCEEDED = "TRANSPORT_SUCCEEDED"
    RECEIPT_VERIFIED = "RECEIPT_VERIFIED"
    SEMANTIC_RESULT_SUCCEEDED = "SEMANTIC_RESULT_SUCCEEDED"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _dict(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputError(f"{field} must be an object")
    return value


def _semantic_request(request: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in request.items()
        if key not in {"request_id", "attempt_id", "created_at"}
    }


def request_fingerprint(request: dict[str, Any]) -> str:
    return _sha256(_semantic_request(request))


def _looks_like_inline_binary(value: str) -> bool:
    compact = "".join(value.split())
    if compact.startswith("data:") and ";base64," in compact[:128]:
        return True
    if compact.startswith(KNOWN_BINARY_PREFIXES):
        return True
    if len(compact) < 512 or len(compact) % 4 or not BASE64ISH.fullmatch(compact):
        return False
    try:
        decoded = base64.b64decode(compact, validate=True)
    except (ValueError, base64.binascii.Error):
        return False
    return len(decoded) >= 256


def _inline_binary_paths(value: Any, path: str = "$") -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if str(key).lower() in INLINE_BINARY_KEYS and item not in (None, "", [], {}):
                found.append(child)
            if isinstance(item, str) and _looks_like_inline_binary(item):
                found.append(child)
            elif isinstance(item, (dict, list)):
                found.extend(_inline_binary_paths(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            child = f"{path}[{index}]"
            if isinstance(item, str) and _looks_like_inline_binary(item):
                found.append(child)
            elif isinstance(item, (dict, list)):
                found.extend(_inline_binary_paths(item, child))
    return tuple(dict.fromkeys(found))


@dataclass(frozen=True)
class PreflightResult:
    decision: GuardDecision
    effect_state: EffectState
    request_fingerprint: str
    effect_class: str
    blockers: tuple[str, ...]
    binary_paths: tuple[str, ...]
    required_after_dispatch: tuple[str, ...]

    @property
    def dispatch_authorized(self) -> bool:
        return self.decision in {GuardDecision.ALLOW_READ, GuardDecision.ALLOW_DISPATCH}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "decision": self.decision.value,
            "effect_state": self.effect_state.value,
            "request_fingerprint": self.request_fingerprint,
            "effect_class": self.effect_class,
            "dispatch_authorized": self.dispatch_authorized,
            "blockers": list(self.blockers),
            "binary_paths": list(self.binary_paths),
            "required_after_dispatch": list(self.required_after_dispatch),
            "provider_binding": "ADAPTER_REQUIRED",
            "target_runtime_binding_proven": False,
            "manual_user_tasks": [],
            "owner_action_required": False,
        }


class ExecutionGuard:
    schema_version = SCHEMA_VERSION

    def preflight_tool_call(self, payload: dict[str, Any]) -> PreflightResult:
        root = _dict(payload, "input")
        if root.get("schema_version") != SCHEMA_VERSION:
            raise InputError(f"schema_version must be {SCHEMA_VERSION}")
        request = _dict(root.get("request"), "request")
        for field in ("request_id", "tool_name", "operation", "effect_class"):
            if not _nonempty_string(request.get(field)):
                raise InputError(f"request.{field} must be a non-empty string")
        effect_class = request["effect_class"].strip().upper()
        if effect_class != "READ_ONLY" and effect_class not in SIDE_EFFECT_CLASSES:
            raise InputError("request.effect_class is unsupported")
        fingerprint = request_fingerprint(request)
        if effect_class == "READ_ONLY":
            return PreflightResult(GuardDecision.ALLOW_READ, EffectState.VALIDATED, fingerprint, effect_class, (), (), ())

        expected = request.get("expected_fruit")
        if not isinstance(expected, dict) or not expected:
            return self._blocked(GuardDecision.BLOCK_MISSING_EXPECTED_FRUIT, fingerprint, effect_class, ("expected_fruit_required",))
        if not _nonempty_string(request.get("idempotency_key")):
            return self._blocked(GuardDecision.BLOCK_INVALID_AUTHORITY, fingerprint, effect_class, ("idempotency_key_required",))

        authority = _dict(root.get("authority"), "authority")
        authority_ok = all((
            authority.get("formation_permit_consumed") is True,
            authority.get("permit_single_use") is True,
            authority.get("action_binding_matches") is True,
            _nonempty_string(authority.get("proof_ref")),
        ))
        if not authority_ok:
            return self._blocked(GuardDecision.BLOCK_INVALID_AUTHORITY, fingerprint, effect_class, ("consumed_single_use_bound_permit_required",))

        route = _dict(root.get("route"), "route")
        route_ok = all((
            route.get("readback_supported") is True,
            route.get("semantic_canary_verified") is True,
            _nonempty_string(route.get("canary_proof_ref")),
        ))
        if not route_ok:
            return self._blocked(GuardDecision.BLOCK_UNVERIFIED_ROUTE, fingerprint, effect_class, ("semantic_canary_and_readback_route_required",))

        if effect_class == "EXTERNAL_MESSAGE":
            target = _dict(request.get("target"), "request.target")
            recipients = target.get("recipients")
            if target.get("recipients_verified") is not True or not isinstance(recipients, list) or not recipients:
                return self._blocked(GuardDecision.BLOCK_UNVERIFIED_RECIPIENT, fingerprint, effect_class, ("verified_nonempty_recipients_required",))

        binary_paths = _inline_binary_paths(request.get("payload"))
        inline_allowed = all((
            route.get("inline_binary_supported") is True,
            route.get("inline_binary_canary_verified") is True,
            _nonempty_string(route.get("inline_binary_canary_proof_ref")),
        ))
        if binary_paths and not inline_allowed:
            return self._blocked(
                GuardDecision.BLOCK_UNSAFE_BINARY_TRANSPORT, fingerprint, effect_class,
                ("inline_binary_requires_exact_tool_contract_and_semantic_canary",), binary_paths,
            )

        retry = root.get("retry", {})
        if not isinstance(retry, dict):
            raise InputError("retry must be an object")
        previous = retry.get("previous_attempts", [])
        if not isinstance(previous, list) or not all(isinstance(item, dict) for item in previous):
            raise InputError("retry.previous_attempts must be an array of objects")
        idempotency_key = request["idempotency_key"].strip()
        for attempt in previous:
            status = str(attempt.get("status", "")).upper()
            if attempt.get("idempotency_key") == idempotency_key and status not in {"FAILED_PRE_DISPATCH", "CANCELLED"}:
                return self._blocked(GuardDecision.BLOCK_IDEMPOTENCY_REPLAY, fingerprint, effect_class, ("idempotency_key_already_dispatched",))
            if attempt.get("request_fingerprint") == fingerprint and status in FAILED_RETRY_STATES:
                return self._blocked(GuardDecision.BLOCK_UNCHANGED_RETRY, fingerprint, effect_class, ("failed_or_unverified_route_must_change_before_retry",))
        if previous and not _nonempty_string(retry.get("exact_repair")):
            return self._blocked(GuardDecision.BLOCK_UNCHANGED_RETRY, fingerprint, effect_class, ("exact_repair_required_after_prior_attempt",))

        return PreflightResult(
            GuardDecision.ALLOW_DISPATCH, EffectState.AUTHORIZED, fingerprint, effect_class,
            (), binary_paths, ("provider_receipt", "independent_semantic_readback", "claim_release_gate"),
        )

    def observe_dispatch(self, preflight: PreflightResult | dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]:
        decision = preflight.to_dict() if isinstance(preflight, PreflightResult) else _dict(preflight, "preflight")
        observed = _dict(observation, "observation")
        if decision.get("dispatch_authorized") is not True:
            raise InputError("cannot observe dispatch for a blocked preflight")
        fingerprint = str(decision.get("request_fingerprint", ""))
        base = {
            "schema_version": SCHEMA_VERSION,
            "request_fingerprint": fingerprint,
            "effect_class": str(decision.get("effect_class", "")),
            "provider_binding": "ADAPTER_REQUIRED",
            "target_runtime_binding_proven": False,
            "manual_user_tasks": [],
            "owner_action_required": False,
        }
        if observed.get("transport_succeeded") is not True:
            return {**base, "effect_state": EffectState.FAILED.value, "completion_proven": False, "verified_states": [], "proof_refs": []}
        receipt = observed.get("provider_receipt")
        if not isinstance(receipt, dict) or not all((
            _nonempty_string(receipt.get("provider_id")),
            receipt.get("request_fingerprint") == fingerprint,
            receipt.get("current") is True,
        )):
            return {**base, "effect_state": EffectState.TRANSPORT_SUCCEEDED.value, "completion_proven": False, "verified_states": [], "proof_refs": []}
        semantic = observed.get("semantic_readback")
        if not isinstance(semantic, dict) or not all((
            semantic.get("current") is True,
            semantic.get("independent") is True,
            semantic.get("matches_expected") is True,
            _nonempty_string(semantic.get("proof_ref")),
        )):
            return {
                **base, "effect_state": EffectState.RECEIPT_VERIFIED.value,
                "completion_proven": False, "verified_states": [],
                "proof_refs": [str(receipt.get("proof_ref") or receipt["provider_id"])],
            }
        states = semantic.get("verified_states", [])
        if not isinstance(states, list) or not all(_nonempty_string(item) for item in states):
            raise InputError("semantic_readback.verified_states must be an array of non-empty strings")
        return {
            **base, "effect_state": EffectState.SEMANTIC_RESULT_SUCCEEDED.value,
            "completion_proven": True,
            "verified_states": list(dict.fromkeys(item.strip().upper() for item in states)),
            "proof_refs": [str(receipt.get("proof_ref") or receipt["provider_id"]), semantic["proof_ref"].strip()],
        }

    def guard_claim_release(self, record: dict[str, Any], claimed_state: str) -> dict[str, Any]:
        observed = _dict(record, "record")
        if not _nonempty_string(claimed_state):
            raise InputError("claimed_state must be a non-empty string")
        claim = claimed_state.strip().upper()
        verified_states = {
            str(item).strip().upper() for item in observed.get("verified_states", [])
            if _nonempty_string(item)
        }
        semantic = observed.get("effect_state") == EffectState.SEMANTIC_RESULT_SUCCEEDED.value
        claim_authorized = semantic and claim in verified_states
        return {
            "schema_version": SCHEMA_VERSION,
            "decision": "ALLOW_CLAIM_RELEASE" if claim_authorized else GuardDecision.BLOCK_CLAIM_RELEASE.value,
            "claimed_state": claim,
            "claim_authorized": claim_authorized,
            "safe_statement": (
                f"{claim} is verified by current independent semantic readback."
                if claim_authorized
                else f"{claim} is not verified; the strongest observed state is {observed.get('effect_state', 'UNKNOWN')}."
            ),
            "proof_refs": list(observed.get("proof_refs", [])) if claim_authorized else [],
            "provider_binding": "ADAPTER_REQUIRED",
            "target_runtime_binding_proven": False,
            "manual_user_tasks": [],
            "owner_action_required": False,
        }

    @staticmethod
    def _blocked(
        decision: GuardDecision,
        fingerprint: str,
        effect_class: str,
        blockers: tuple[str, ...],
        binary_paths: tuple[str, ...] = (),
    ) -> PreflightResult:
        return PreflightResult(decision, EffectState.QUARANTINED, fingerprint, effect_class, blockers, binary_paths, ())
