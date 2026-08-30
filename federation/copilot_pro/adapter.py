from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from hashlib import sha256
import json
import math
import re
from typing import Iterable

from federation.orchestration.mission_arbitration import CapabilityRoute

_SAFE_ID = re.compile(r"^[A-Za-z0-9._:/@-]{1,256}$")
_BLOCKED_PRIVACY = {"PRIVATE_CASE", "SENSITIVE_IDENTITY", "SECRET"}


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _safe_id(value: str, field: str) -> str:
    value = str(value).strip()
    if not _SAFE_ID.fullmatch(value):
        raise ValueError(f"{field} is invalid")
    return value


def _paths(values: Iterable[str]) -> tuple[str, ...]:
    out: set[str] = set()
    for raw in values:
        value = str(raw).strip().replace("\\", "/")
        while value.startswith("./"):
            value = value[2:]
        if not value or value.startswith("/") or any(part in {"", ".."} for part in value.split("/")):
            raise ValueError("path_scope must contain relative traversal-free repository paths")
        out.add(value.rstrip("/"))
    if not out:
        raise ValueError("path_scope cannot be empty")
    return tuple(sorted(out))


def _finite_nonnegative(value: float | int, field: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field} must be finite and non-negative")
    return number


class CopilotRole(str, Enum):
    BUILDER = "BUILDER"
    REVIEWER = "REVIEWER"
    FALSIFIER = "FALSIFIER"
    GEMINI_CHALLENGER = "GEMINI_CHALLENGER"


class WriteMode(str, Enum):
    READ_ONLY = "READ_ONLY"
    BRANCH_PR = "BRANCH_PR"


class CopilotDispatchState(str, Enum):
    READY_INCLUDED_CREDITS = "READY_INCLUDED_CREDITS"
    HOLD_PRIVACY = "HOLD_PRIVACY"
    HOLD_AUTHORITY = "HOLD_AUTHORITY"
    HOLD_CREDIT_BUDGET = "HOLD_CREDIT_BUDGET"
    HOLD_MODEL_CONTRACT = "HOLD_MODEL_CONTRACT"


@dataclass(frozen=True)
class CopilotCreditBudget:
    """Verified point-in-time Copilot AI-credit budget snapshot.

    This object is planning evidence only. It does not configure GitHub billing or
    guarantee that a Copilot session will stop at task_credit_cap. A provider-side
    budget/usage readback is still required before paid-overage claims.
    """

    plan_id: str
    cycle_id: str
    included_total_credits: float
    included_used_credits: float
    snapshot_verified: bool
    additional_paid_usage_allowed: bool = False
    additional_paid_credit_cap: float = 0.0
    provider_budget_enforced: bool = False

    def validate(self) -> "CopilotCreditBudget":
        _safe_id(self.plan_id, "plan_id")
        _safe_id(self.cycle_id, "cycle_id")
        total = _finite_nonnegative(self.included_total_credits, "included_total_credits")
        used = _finite_nonnegative(self.included_used_credits, "included_used_credits")
        extra = _finite_nonnegative(self.additional_paid_credit_cap, "additional_paid_credit_cap")
        if used > total:
            raise ValueError("included_used_credits cannot exceed included_total_credits")
        if not self.additional_paid_usage_allowed and extra != 0:
            raise ValueError("paid credit cap must be zero when paid usage is disabled")
        return self

    @property
    def included_remaining(self) -> float:
        self.validate()
        return round(float(self.included_total_credits) - float(self.included_used_credits), 6)

    @property
    def total_authorised_remaining(self) -> float:
        extra = float(self.additional_paid_credit_cap) if self.additional_paid_usage_allowed else 0.0
        return round(self.included_remaining + extra, 6)


@dataclass(frozen=True)
class CopilotTaskSpec:
    task_id: str
    role: CopilotRole
    objective: str
    path_scope: tuple[str, ...]
    privacy_class: str
    write_mode: WriteMode
    task_credit_cap: float
    requested_model: str = "AUTO"
    source_pr_authorized: bool = False
    provider_effect: bool = False
    consequential_external_effect: bool = False

    @classmethod
    def create(
        cls,
        *,
        task_id: str,
        role: CopilotRole,
        objective: str,
        path_scope: Iterable[str],
        privacy_class: str,
        write_mode: WriteMode,
        task_credit_cap: float,
        requested_model: str = "AUTO",
        source_pr_authorized: bool = False,
        provider_effect: bool = False,
        consequential_external_effect: bool = False,
    ) -> "CopilotTaskSpec":
        _safe_id(task_id, "task_id")
        if not isinstance(role, CopilotRole):
            raise ValueError("role must be CopilotRole")
        if not isinstance(write_mode, WriteMode):
            raise ValueError("write_mode must be WriteMode")
        objective = str(objective).strip()
        if len(objective) < 8:
            raise ValueError("objective is too short")
        privacy = str(privacy_class).strip().upper()
        if privacy not in {"PUBLIC_SAFE", "INTERNAL_SAFE", "PRIVATE_CASE", "SENSITIVE_IDENTITY", "SECRET"}:
            raise ValueError("unknown privacy_class")
        cap = _finite_nonnegative(task_credit_cap, "task_credit_cap")
        if cap <= 0:
            raise ValueError("task_credit_cap must be positive")
        model = str(requested_model).strip() or "AUTO"
        return cls(
            task_id=task_id,
            role=role,
            objective=objective,
            path_scope=_paths(path_scope),
            privacy_class=privacy,
            write_mode=write_mode,
            task_credit_cap=cap,
            requested_model=model,
            source_pr_authorized=bool(source_pr_authorized),
            provider_effect=bool(provider_effect),
            consequential_external_effect=bool(consequential_external_effect),
        )


@dataclass(frozen=True)
class CopilotTaskEnvelope:
    schema: str
    task_id: str
    role: str
    objective_sha256: str
    path_scope: tuple[str, ...]
    privacy_class: str
    write_mode: str
    task_credit_cap: float
    requested_model: str
    source_pr_authorized: bool
    no_secret_payload: bool
    no_provider_effect: bool
    no_consequential_external_effect: bool
    envelope_sha256: str


@dataclass(frozen=True)
class CopilotDispatchDecision:
    state: CopilotDispatchState
    eligible: bool
    reasons: tuple[str, ...]
    task_id: str
    role: str
    requested_model: str
    task_credit_cap: float
    included_remaining_before: float
    paid_overage_authorized: bool
    provider_budget_enforced: bool
    decision_sha256: str


@dataclass(frozen=True)
class CopilotRunObservation:
    task_id: str
    role: CopilotRole
    observed_model: str
    credits_used: float
    proof_ref: str
    reality_state: str
    required_reality_state: str
    readiness: str
    quality: float
    reliability: float
    freshness: float
    proof_strength: float
    latency_penalty: float
    cost_penalty: float
    owner_burden_penalty: float
    risk_penalty: float
    model_identity_verified: bool

    def validate(self) -> "CopilotRunObservation":
        _safe_id(self.task_id, "task_id")
        if not isinstance(self.role, CopilotRole):
            raise ValueError("role must be CopilotRole")
        if not str(self.observed_model).strip():
            raise ValueError("observed_model is required")
        _finite_nonnegative(self.credits_used, "credits_used")
        if not str(self.proof_ref).strip():
            raise ValueError("proof_ref is required")
        for field in (
            "quality",
            "reliability",
            "freshness",
            "proof_strength",
            "latency_penalty",
            "cost_penalty",
            "owner_burden_penalty",
            "risk_penalty",
        ):
            value = float(getattr(self, field))
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{field} must be in [0,1]")
        if not self.model_identity_verified:
            raise ValueError("model identity must be independently observed before CFBE scoring")
        return self


def compile_task_envelope(spec: CopilotTaskSpec) -> CopilotTaskEnvelope:
    body = {
        "schema": "FCX_COPILOT_TASK_ENVELOPE_V1",
        "task_id": spec.task_id,
        "role": spec.role.value,
        "objective_sha256": _digest(spec.objective),
        "path_scope": spec.path_scope,
        "privacy_class": spec.privacy_class,
        "write_mode": spec.write_mode.value,
        "task_credit_cap": spec.task_credit_cap,
        "requested_model": spec.requested_model,
        "source_pr_authorized": spec.source_pr_authorized,
        "no_secret_payload": spec.privacy_class not in _BLOCKED_PRIVACY,
        "no_provider_effect": not spec.provider_effect,
        "no_consequential_external_effect": not spec.consequential_external_effect,
    }
    return CopilotTaskEnvelope(envelope_sha256=_digest(body), **body)


def evaluate_dispatch(spec: CopilotTaskSpec, budget: CopilotCreditBudget) -> CopilotDispatchDecision:
    budget.validate()
    reasons: list[str] = []

    if spec.privacy_class in _BLOCKED_PRIVACY:
        reasons.append(f"PRIVACY_CLASS_BLOCKED:{spec.privacy_class}")
    if spec.provider_effect or spec.consequential_external_effect:
        reasons.append("CONSEQUENTIAL_OR_PROVIDER_EFFECT_NOT_AUTHORISED")
    if spec.role == CopilotRole.BUILDER:
        if spec.write_mode != WriteMode.BRANCH_PR:
            reasons.append("BUILDER_REQUIRES_BRANCH_PR")
        if not spec.source_pr_authorized:
            reasons.append("BRANCH_PR_AUTHORITY_REQUIRED")
    elif spec.write_mode != WriteMode.READ_ONLY:
        reasons.append("NON_BUILDER_MUST_BE_READ_ONLY")

    if spec.role == CopilotRole.GEMINI_CHALLENGER and "gemini" not in spec.requested_model.lower():
        reasons.append("GEMINI_CHALLENGER_REQUIRES_GEMINI_MODEL_REQUEST")

    if not budget.snapshot_verified:
        reasons.append("CREDIT_BUDGET_SNAPSHOT_UNVERIFIED")
    if spec.task_credit_cap > budget.included_remaining:
        if not budget.additional_paid_usage_allowed:
            reasons.append("TASK_CAP_EXCEEDS_INCLUDED_REMAINING")
        elif spec.task_credit_cap > budget.total_authorised_remaining:
            reasons.append("TASK_CAP_EXCEEDS_TOTAL_AUTHORISED_REMAINING")
        elif not budget.provider_budget_enforced:
            reasons.append("PAID_OVERAGE_REQUIRES_PROVIDER_BUDGET_ENFORCEMENT")

    if any(reason.startswith("PRIVACY_CLASS_BLOCKED") for reason in reasons):
        state = CopilotDispatchState.HOLD_PRIVACY
    elif any("AUTHORI" in reason or "BRANCH_PR" in reason or "EFFECT" in reason or "NON_BUILDER" in reason for reason in reasons):
        state = CopilotDispatchState.HOLD_AUTHORITY
    elif any("GEMINI_CHALLENGER" in reason for reason in reasons):
        state = CopilotDispatchState.HOLD_MODEL_CONTRACT
    elif reasons:
        state = CopilotDispatchState.HOLD_CREDIT_BUDGET
    else:
        state = CopilotDispatchState.READY_INCLUDED_CREDITS

    body = {
        "state": state.value,
        "eligible": not reasons,
        "reasons": tuple(sorted(reasons)),
        "task_id": spec.task_id,
        "role": spec.role.value,
        "requested_model": spec.requested_model,
        "task_credit_cap": spec.task_credit_cap,
        "included_remaining_before": budget.included_remaining,
        "paid_overage_authorized": budget.additional_paid_usage_allowed,
        "provider_budget_enforced": budget.provider_budget_enforced,
    }
    return CopilotDispatchDecision(decision_sha256=_digest(body), **body)


def to_cfbe_route(observation: CopilotRunObservation) -> CapabilityRoute:
    """Map measured Copilot evidence into the existing Federation CFBE selector.

    The adapter deliberately accepts observed normalized metrics rather than
    inventing quality or value scores from token counts. The existing
    CapabilitySelector remains the ranking authority.
    """

    observation.validate()
    return CapabilityRoute(
        route_id=f"FCX-COPILOT:{observation.task_id}:{observation.role.value}",
        capability_id=f"FCX-COPILOT-{observation.role.value}",
        reality_state=observation.reality_state,
        required_reality_state=observation.required_reality_state,
        readiness=observation.readiness,
        authority_required="A1_INTERNAL",
        proof_ref=observation.proof_ref,
        external_effect=False,
        quality=observation.quality,
        reliability=observation.reliability,
        freshness=observation.freshness,
        proof_strength=observation.proof_strength,
        latency=observation.latency_penalty,
        cost=observation.cost_penalty,
        owner_burden=observation.owner_burden_penalty,
        risk=observation.risk_penalty,
    )


def usage_receipt(
    *,
    observation: CopilotRunObservation,
    task_envelope: CopilotTaskEnvelope,
    budget_cycle_id: str,
) -> dict[str, object]:
    observation.validate()
    body = {
        "schema": "FCX_COPILOT_USAGE_RECEIPT_V1",
        "task_id": observation.task_id,
        "role": observation.role.value,
        "observed_model": observation.observed_model,
        "credits_used": float(observation.credits_used),
        "proof_ref": observation.proof_ref,
        "task_envelope_sha256": task_envelope.envelope_sha256,
        "budget_cycle_id": _safe_id(budget_cycle_id, "budget_cycle_id"),
        "model_identity_verified": observation.model_identity_verified,
        "external_effect_claimed": False,
        "provider_effect_claimed": False,
    }
    return {**body, "receipt_sha256": _digest(body)}


__all__ = [
    "CopilotCreditBudget",
    "CopilotDispatchDecision",
    "CopilotDispatchState",
    "CopilotRole",
    "CopilotRunObservation",
    "CopilotTaskEnvelope",
    "CopilotTaskSpec",
    "WriteMode",
    "compile_task_envelope",
    "evaluate_dispatch",
    "to_cfbe_route",
    "usage_receipt",
]
