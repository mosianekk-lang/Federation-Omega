"""FUSE Execution / Readback Closure v1.

Binds one admitted action to one idempotent execution identity and refuses to call a
mutation successful until provider-native semantic readback proves the intended
postcondition. Write acknowledgements are receipts of transport only, never effect proof.

Provider-neutral: this module consumes supplied execution/readback/rollback receipts;
it does not itself call providers or manufacture success.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Mapping

from federation.action_admission_gate_v1 import ActionAdmissionReceipt
from federation.cfbe_chat_hyperperformance_v1 import EffectClass

SCHEMA = "FUSE-EXECUTION-READBACK-CLOSURE-V1"
VERSION = "1.0.0"


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: object) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


class ClosureState(str, Enum):
    HELD = "HELD"
    ATTEMPT_STARTED = "ATTEMPT_STARTED"
    WRITE_ACKNOWLEDGED = "WRITE_ACKNOWLEDGED"
    EFFECT_VERIFIED = "EFFECT_VERIFIED"
    BEHAVIOUR_VERIFIED = "BEHAVIOUR_VERIFIED"
    READBACK_MISMATCH = "READBACK_MISMATCH"
    ROLLBACK_REQUIRED = "ROLLBACK_REQUIRED"
    ROLLED_BACK_VERIFIED = "ROLLED_BACK_VERIFIED"
    TERMINAL_FAILED = "TERMINAL_FAILED"


@dataclass(frozen=True, slots=True)
class ExecutionAttempt:
    attempt_id: str
    action_admission_digest: str
    mission_id: str
    action_id: str
    unit_id: str
    effect_class: EffectClass
    target_scope: str
    idempotency_key: str
    request_fingerprint: str
    pre_state_fingerprint: str
    transport_ref: str = ""
    write_ack_ref: str = ""
    execution_error_ref: str = ""

    def validate(self) -> "ExecutionAttempt":
        required = (
            self.attempt_id, self.action_admission_digest, self.mission_id, self.action_id,
            self.unit_id, self.target_scope, self.idempotency_key, self.request_fingerprint,
            self.pre_state_fingerprint,
        )
        if not all(str(x).strip() for x in required):
            raise ValueError("EXECUTION_ATTEMPT_IDENTITY_REQUIRED")
        if self.effect_class is not EffectClass.READ_ONLY and not self.transport_ref.strip():
            raise ValueError("MUTATING_ATTEMPT_REQUIRES_TRANSPORT_REF")
        return self


@dataclass(frozen=True, slots=True)
class SemanticReadback:
    readback_id: str
    attempt_id: str
    provider_ref: str
    target_scope: str
    observed_state_fingerprint: str
    expected_state_fingerprint: str
    semantic_match: bool
    fresh: bool = True
    provider_native: bool = True
    behaviour_ref: str = ""

    def validate(self) -> "SemanticReadback":
        if not all((self.readback_id.strip(), self.attempt_id.strip(), self.provider_ref.strip(), self.target_scope.strip(), self.observed_state_fingerprint.strip(), self.expected_state_fingerprint.strip())):
            raise ValueError("SEMANTIC_READBACK_IDENTITY_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class RollbackReceipt:
    rollback_id: str
    attempt_id: str
    rollback_ack_ref: str
    readback_ref: str = ""
    restored_state_fingerprint: str = ""
    expected_pre_state_fingerprint: str = ""
    fresh: bool = True
    provider_native: bool = True

    def validate(self) -> "RollbackReceipt":
        if not all((self.rollback_id.strip(), self.attempt_id.strip(), self.rollback_ack_ref.strip())):
            raise ValueError("ROLLBACK_RECEIPT_IDENTITY_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class ExecutionClosureReceipt:
    mission_id: str
    action_id: str
    attempt_id: str
    state: ClosureState
    effect_class: EffectClass
    write_ack_ref: str
    readback_ref: str
    rollback_ref: str
    reasons: tuple[str, ...]
    receipt_digest: str

    @property
    def effect_verified(self) -> bool:
        return self.state in {ClosureState.EFFECT_VERIFIED, ClosureState.BEHAVIOUR_VERIFIED}


class IdempotencyLedger:
    """Detect duplicate keys whose immutable request identity diverges."""

    def __init__(self, entries: Mapping[str, str] | None = None) -> None:
        self._entries = dict(entries or {})

    def check(self, key: str, request_fingerprint: str) -> tuple[bool, str]:
        existing = self._entries.get(key)
        if existing is None:
            return True, "IDEMPOTENCY_KEY_NEW"
        if existing == request_fingerprint:
            return True, "IDEMPOTENT_REPLAY_SAME_REQUEST"
        return False, "IDEMPOTENCY_KEY_PAYLOAD_DIVERGENCE"


class ExecutionReadbackClosure:
    """Prove effect closure from admitted action through provider-native readback."""

    def close(
        self,
        *,
        admission: ActionAdmissionReceipt,
        attempt: ExecutionAttempt,
        ledger: IdempotencyLedger | None = None,
        readback: SemanticReadback | None = None,
        rollback: RollbackReceipt | None = None,
        rollback_required: bool = False,
    ) -> ExecutionClosureReceipt:
        attempt.validate()
        reasons: list[str] = []
        ledger = ledger or IdempotencyLedger()

        if not admission.admitted:
            reasons.append("ACTION_NOT_ADMITTED")
        if attempt.action_admission_digest != admission.receipt_digest:
            reasons.append("ATTEMPT_ADMISSION_DIGEST_MISMATCH")
        for name, left, right in (
            ("MISSION", attempt.mission_id, admission.mission_id),
            ("ACTION", attempt.action_id, admission.action_id),
            ("UNIT", attempt.unit_id, admission.unit_id),
        ):
            if left != right:
                reasons.append(f"ATTEMPT_{name}_MISMATCH")
        if attempt.effect_class is not admission.effect_class:
            reasons.append("ATTEMPT_EFFECT_CLASS_MISMATCH")

        idem_ok, idem_reason = ledger.check(attempt.idempotency_key, attempt.request_fingerprint)
        if not idem_ok:
            reasons.append(idem_reason)

        if reasons:
            return self._receipt(admission, attempt, ClosureState.HELD, reasons, readback, rollback)
        if attempt.execution_error_ref:
            state = ClosureState.ROLLBACK_REQUIRED if rollback_required and attempt.effect_class is not EffectClass.READ_ONLY else ClosureState.TERMINAL_FAILED
            return self._receipt(admission, attempt, state, ("EXECUTION_ERROR_REPORTED",), readback, rollback)

        if attempt.effect_class is EffectClass.READ_ONLY:
            if readback is None:
                return self._receipt(admission, attempt, ClosureState.ATTEMPT_STARTED, ("READ_RESULT_NOT_YET_PROVEN",), None, rollback)
            readback.validate()
            rr = self._validate_readback(attempt, readback, require_provider_native=False)
            if rr:
                return self._receipt(admission, attempt, ClosureState.READBACK_MISMATCH, rr, readback, rollback)
            state = ClosureState.BEHAVIOUR_VERIFIED if readback.behaviour_ref.strip() else ClosureState.EFFECT_VERIFIED
            return self._receipt(admission, attempt, state, (), readback, rollback)

        if not attempt.write_ack_ref.strip():
            return self._receipt(admission, attempt, ClosureState.ATTEMPT_STARTED, ("WRITE_ACK_NOT_RECEIVED",), readback, rollback)
        if readback is None:
            return self._receipt(admission, attempt, ClosureState.WRITE_ACKNOWLEDGED, ("WRITE_ACK_IS_NOT_EFFECT_PROOF",), None, rollback)

        readback.validate()
        rr = self._validate_readback(attempt, readback, require_provider_native=True)
        if rr:
            if rollback_required:
                if rollback is None:
                    return self._receipt(admission, attempt, ClosureState.ROLLBACK_REQUIRED, rr, readback, None)
                rb_reasons = self._validate_rollback(attempt, rollback)
                if rb_reasons:
                    return self._receipt(admission, attempt, ClosureState.ROLLBACK_REQUIRED, rr + rb_reasons, readback, rollback)
                return self._receipt(admission, attempt, ClosureState.ROLLED_BACK_VERIFIED, rr + ("ROLLBACK_SEMANTICALLY_VERIFIED",), readback, rollback)
            return self._receipt(admission, attempt, ClosureState.READBACK_MISMATCH, rr, readback, rollback)

        state = ClosureState.BEHAVIOUR_VERIFIED if readback.behaviour_ref.strip() else ClosureState.EFFECT_VERIFIED
        return self._receipt(admission, attempt, state, (), readback, rollback)

    @staticmethod
    def _validate_readback(attempt: ExecutionAttempt, readback: SemanticReadback, *, require_provider_native: bool) -> tuple[str, ...]:
        reasons: list[str] = []
        if readback.attempt_id != attempt.attempt_id:
            reasons.append("READBACK_ATTEMPT_MISMATCH")
        if readback.target_scope != attempt.target_scope:
            reasons.append("READBACK_TARGET_MISMATCH")
        if not readback.fresh:
            reasons.append("READBACK_NOT_FRESH")
        if require_provider_native and not readback.provider_native:
            reasons.append("PROVIDER_NATIVE_READBACK_REQUIRED")
        if not readback.semantic_match:
            reasons.append("SEMANTIC_POSTCONDITION_MISMATCH")
        if readback.observed_state_fingerprint != readback.expected_state_fingerprint:
            reasons.append("READBACK_FINGERPRINT_MISMATCH")
        return tuple(reasons)

    @staticmethod
    def _validate_rollback(attempt: ExecutionAttempt, rollback: RollbackReceipt) -> tuple[str, ...]:
        rollback.validate()
        reasons: list[str] = []
        if rollback.attempt_id != attempt.attempt_id:
            reasons.append("ROLLBACK_ATTEMPT_MISMATCH")
        if not rollback.readback_ref.strip():
            reasons.append("ROLLBACK_READBACK_REQUIRED")
        if not rollback.fresh:
            reasons.append("ROLLBACK_READBACK_NOT_FRESH")
        if not rollback.provider_native:
            reasons.append("ROLLBACK_PROVIDER_NATIVE_READBACK_REQUIRED")
        if not rollback.restored_state_fingerprint.strip() or not rollback.expected_pre_state_fingerprint.strip():
            reasons.append("ROLLBACK_STATE_FINGERPRINT_REQUIRED")
        elif rollback.expected_pre_state_fingerprint != attempt.pre_state_fingerprint:
            reasons.append("ROLLBACK_EXPECTED_PRESTATE_MISMATCH")
        elif rollback.restored_state_fingerprint != attempt.pre_state_fingerprint:
            reasons.append("ROLLBACK_STATE_NOT_RESTORED")
        return tuple(reasons)

    def _receipt(self, admission, attempt, state, reasons, readback, rollback):
        material = {
            "schema": SCHEMA, "version": VERSION,
            "mission_id": admission.mission_id, "action_id": admission.action_id,
            "attempt_id": attempt.attempt_id, "state": state.value,
            "effect": attempt.effect_class.value,
            "write_ack": attempt.write_ack_ref,
            "readback": readback.readback_id if readback else "",
            "rollback": rollback.rollback_id if rollback else "",
            "reasons": reasons,
        }
        return ExecutionClosureReceipt(
            mission_id=admission.mission_id,
            action_id=admission.action_id,
            attempt_id=attempt.attempt_id,
            state=state,
            effect_class=attempt.effect_class,
            write_ack_ref=attempt.write_ack_ref,
            readback_ref=readback.provider_ref if readback else "",
            rollback_ref=rollback.readback_ref if rollback else "",
            reasons=tuple(reasons),
            receipt_digest=_digest(material),
        )


__all__ = [
    "SCHEMA", "VERSION", "ClosureState", "ExecutionAttempt", "SemanticReadback",
    "RollbackReceipt", "ExecutionClosureReceipt", "IdempotencyLedger", "ExecutionReadbackClosure",
]
