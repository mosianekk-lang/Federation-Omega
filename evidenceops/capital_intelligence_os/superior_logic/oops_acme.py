from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
import hashlib
import json
from typing import Any


class ActionClass(StrEnum):
    INTERNAL_REVERSIBLE = "INTERNAL_REVERSIBLE"
    EXTERNAL_CONSEQUENTIAL = "EXTERNAL_CONSEQUENTIAL"
    NON_DELEGABLE_PERSONAL = "NON_DELEGABLE_PERSONAL"


class ExternalActionDecision(StrEnum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    OWNER_DECISION_REQUIRED = "OWNER_DECISION_REQUIRED"


class ContinuationDecision(StrEnum):
    CONTINUE_ACTIVE_TURN = "CONTINUE_ACTIVE_TURN"
    ASK_OWNER = "ASK_OWNER"
    VERIFIED_COMPLETE = "VERIFIED_COMPLETE"
    PARTIAL_PRESERVED = "PARTIAL_PRESERVED"
    BLOCKED_IRREDUCIBLY = "BLOCKED_IRREDUCIBLY"


def _normalise_text(value: str) -> str:
    return " ".join(value.strip().split())


def _normalise_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(_normalise_text(value) for value in values)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class ExternalActionPayload:
    action: str
    account: str
    targets: tuple[str, ...] = ()
    subject: str = ""
    body_hash: str = ""
    attachment_hashes: tuple[str, ...] = ()
    consequences: tuple[str, ...] = ()
    action_class: ActionClass = ActionClass.EXTERNAL_CONSEQUENTIAL

    def normalised(self) -> dict[str, Any]:
        return {
            "action": _normalise_text(self.action).lower(),
            "account": _normalise_text(self.account).lower(),
            "targets": tuple(value.lower() for value in _normalise_tuple(self.targets)),
            "subject": _normalise_text(self.subject),
            "body_hash": self.body_hash.strip().lower(),
            "attachment_hashes": tuple(
                value.lower() for value in _normalise_tuple(self.attachment_hashes)
            ),
            "consequences": tuple(value.lower() for value in _normalise_tuple(self.consequences)),
            "action_class": self.action_class.value,
        }

    @property
    def fingerprint(self) -> str:
        payload = _canonical_json(self.normalised()).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class ExternalActionAuthorization:
    approval_reference: str
    authorized: bool
    action: str
    account: str
    targets: tuple[str, ...] = ()
    subject: str = ""
    body_hash: str = ""
    attachment_hashes: tuple[str, ...] = ()
    consequences: tuple[str, ...] = ()
    prohibitions: tuple[str, ...] = ()

    def as_payload(self) -> ExternalActionPayload:
        return ExternalActionPayload(
            action=self.action,
            account=self.account,
            targets=self.targets,
            subject=self.subject,
            body_hash=self.body_hash,
            attachment_hashes=self.attachment_hashes,
            consequences=self.consequences,
            action_class=ActionClass.EXTERNAL_CONSEQUENTIAL,
        )


@dataclass(frozen=True)
class ExternalActionEvaluation:
    decision: ExternalActionDecision
    allowed: bool
    effective_action_class: ActionClass
    route: str
    payload_fingerprint: str
    approval_reference: str
    mismatched_fields: tuple[str, ...]
    controlling_prohibitions: tuple[str, ...]
    missing_conditions: tuple[str, ...]
    connector_is_not_authority: bool
    safe_wording: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["decision"] = self.decision.value
        value["effective_action_class"] = self.effective_action_class.value
        return value


_EXTERNAL_ACTION_WORDS = {
    "send",
    "reply",
    "forward",
    "file",
    "publish",
    "delete",
    "share",
    "sign",
    "purchase",
    "pay",
    "accept",
    "change permission",
    "grant permission",
}


def _effective_action_class(payload: ExternalActionPayload) -> ActionClass:
    action = _normalise_text(payload.action).lower()
    if payload.action_class == ActionClass.NON_DELEGABLE_PERSONAL:
        return ActionClass.NON_DELEGABLE_PERSONAL
    if any(token in action for token in _EXTERNAL_ACTION_WORDS):
        return ActionClass.EXTERNAL_CONSEQUENTIAL
    return payload.action_class


def _controlling_prohibitions(action: str, prohibitions: tuple[str, ...]) -> tuple[str, ...]:
    action_lower = _normalise_text(action).lower()
    result: list[str] = []
    for prohibition in prohibitions:
        lowered = _normalise_text(prohibition).lower()
        generic = any(
            token in lowered for token in ("not authorized", "not authorised", "do not execute")
        )
        send_specific = "send" in action_lower and any(
            token in lowered
            for token in (
                "external_send_authorized:false",
                "external_send_authorised:false",
                "stop before sending",
                "do not send",
                "sending not authorized",
                "sending not authorised",
            )
        )
        if generic or send_specific:
            result.append(prohibition)
    return tuple(result)


def evaluate_external_action(
    payload: ExternalActionPayload,
    authorization: ExternalActionAuthorization | None,
    *,
    connector_available: bool = False,
) -> ExternalActionEvaluation:
    effective_class = _effective_action_class(payload)
    if effective_class == ActionClass.INTERNAL_REVERSIBLE:
        return ExternalActionEvaluation(
            ExternalActionDecision.ALLOW,
            True,
            effective_class,
            "ACME_CONTINUE",
            payload.fingerprint,
            "",
            (),
            (),
            (),
            True,
            "The action is internal and reversible within the authorised mission; continue and verify the result.",
        )
    if effective_class == ActionClass.NON_DELEGABLE_PERSONAL:
        return ExternalActionEvaluation(
            ExternalActionDecision.OWNER_DECISION_REQUIRED,
            False,
            effective_class,
            "OWNER_INPUT_REQUIRED",
            payload.fingerprint,
            authorization.approval_reference if authorization else "",
            (),
            (),
            ("non_delegable_personal_act",),
            True,
            "The action requires the account owner or another legally required person to act.",
        )
    if authorization is None:
        return ExternalActionEvaluation(
            ExternalActionDecision.OWNER_DECISION_REQUIRED,
            False,
            effective_class,
            "OOPS_HARD_GATE",
            payload.fingerprint,
            "",
            (),
            (),
            ("fresh_action_specific_authorization",),
            True,
            "External action blocked: exact action-specific owner authorization is missing.",
        )

    prohibitions = _controlling_prohibitions(payload.action, authorization.prohibitions)
    mismatches: list[str] = []
    proposed = payload.normalised()
    approved = authorization.as_payload().normalised()
    for field in (
        "action",
        "account",
        "targets",
        "subject",
        "body_hash",
        "attachment_hashes",
        "consequences",
    ):
        if proposed[field] != approved[field]:
            mismatches.append(field)

    missing: list[str] = []
    if not authorization.authorized:
        missing.append("authorization_not_granted")
    if not authorization.approval_reference.strip():
        missing.append("approval_reference")
    if prohibitions:
        missing.append("conflicting_prohibition")
    if mismatches:
        missing.append("payload_changed_or_scope_mismatch")

    allowed = not missing
    return ExternalActionEvaluation(
        ExternalActionDecision.ALLOW if allowed else ExternalActionDecision.BLOCK,
        allowed,
        effective_class,
        "OOPS_EXTERNAL_ACTION_GATE",
        payload.fingerprint,
        authorization.approval_reference,
        tuple(mismatches),
        prohibitions,
        tuple(missing),
        True,
        (
            "The exact external action and unchanged payload are authorised; execution still requires provider readback."
            if allowed
            else "External action blocked: authorization, prohibition and payload-integrity gates did not all pass."
        ),
    )


@dataclass(frozen=True)
class ContinuationContext:
    work_authorized: bool
    material_work_available: bool
    authority_available: bool = True
    material_risk_approval_needed: bool = False
    outcome_choice_needed: bool = False
    essential_unknown: bool = False
    nondelegable_personal_act: bool = False
    credible_routes_remaining: bool = True
    mission_complete: bool = False
    current_turn_active: bool = True
    persistent_runtime_proven: bool = False


@dataclass(frozen=True)
class ContinuationEvaluation:
    decision: ContinuationDecision
    ask_owner: bool
    material_input_reasons: tuple[str, ...]
    continue_active_turn: bool
    background_execution_allowed: bool
    stop_state: str
    safe_wording: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["decision"] = self.decision.value
        return value


def evaluate_continuation(context: ContinuationContext) -> ContinuationEvaluation:
    if context.mission_complete:
        return ContinuationEvaluation(
            ContinuationDecision.VERIFIED_COMPLETE,
            False,
            (),
            False,
            False,
            "VERIFIED_COMPLETE",
            "The mission may stop only because its requested outcome is verified complete.",
        )

    reasons: list[str] = []
    if not context.authority_available:
        reasons.append("AUTHORITY")
    if context.material_risk_approval_needed:
        reasons.append("MATERIAL_RISK_APPROVAL")
    if context.outcome_choice_needed:
        reasons.append("OUTCOME_CHOICE")
    if context.essential_unknown:
        reasons.append("ESSENTIAL_UNKNOWN")
    if context.nondelegable_personal_act:
        reasons.append("NON_DELEGABLE_PERSONAL_ACT")
    if reasons:
        return ContinuationEvaluation(
            ContinuationDecision.ASK_OWNER,
            True,
            tuple(reasons),
            False,
            False,
            "OWNER_DECISION_REQUIRED",
            "Owner input is required only for the listed material reason; all unaffected authorised work should continue.",
        )

    if (
        context.current_turn_active
        and context.work_authorized
        and context.material_work_available
        and context.credible_routes_remaining
    ):
        return ContinuationEvaluation(
            ContinuationDecision.CONTINUE_ACTIVE_TURN,
            False,
            (),
            True,
            context.persistent_runtime_proven,
            "CONTINUE",
            "Continue the highest-value authorised material work in the active turn and verify each result.",
        )

    if not context.credible_routes_remaining:
        return ContinuationEvaluation(
            ContinuationDecision.BLOCKED_IRREDUCIBLY,
            False,
            (),
            False,
            False,
            "BLOCKED_IRREDUCIBLY",
            "All credible non-duplicative routes are exhausted; preserve exact state and the provider or authority boundary.",
        )

    return ContinuationEvaluation(
        ContinuationDecision.PARTIAL_PRESERVED,
        False,
        (),
        False,
        context.persistent_runtime_proven,
        "PARTIALLY_COMPLETE_WITH_PRESERVED_STATE",
        "Preserve completed work, proof, gaps and the exact resumable continuation state without claiming background execution.",
    )
