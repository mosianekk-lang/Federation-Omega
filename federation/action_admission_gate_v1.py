"""FUSE Action Admission Gate v1.

Separates topology readiness from permission to perform an action. Read-only work may be
admitted from an executable topology. Mutations additionally require fresh, exact,
action-specific authority plus currentness/readback/rollback contracts appropriate to
the effect class.

Provider-neutral and effect-free: this module emits admission receipts only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from typing import Mapping

from federation.cfbe_chat_hyperperformance_v1 import EffectClass
from federation.execution_topology_compiler_v1 import ExecutionTopologyReceipt
from federation.mission_ir import MissionIR

SCHEMA = "FUSE-ACTION-ADMISSION-GATE-V1"
VERSION = "1.0.1"


def _instant(value: str) -> datetime:
    raw = str(value).strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        raise ValueError("ACTION_ADMISSION_TIMESTAMP_MUST_BE_OFFSET_AWARE")
    return parsed.astimezone(timezone.utc)


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: object) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


class ActionAdmissionState(str, Enum):
    ADMITTED = "ACTION_ADMITTED"
    HELD = "ACTION_HELD"


_MISSION_EFFECT_CEILING = {
    "NO_EFFECT": 0,
    "READ_ONLY": 1,
    "BOUNDED_EFFECT": 2,
    "CONSEQUENTIAL_EFFECT": 3,
}
_ACTION_EFFECT_LEVEL = {
    EffectClass.READ_ONLY: 1,
    EffectClass.INTERNAL_WRITE: 2,
    EffectClass.EXTERNAL_EFFECT: 3,
}


@dataclass(frozen=True, slots=True)
class AuthorityGrant:
    grant_id: str
    mission_id: str
    action_id: str
    effect_class: EffectClass
    target_scope: str
    source_ref: str
    observed_at: str
    expires_at: str
    authority_refs: tuple[str, ...] = ()
    provider_identity_ref: str = ""
    owner_approval_ref: str = ""
    current_state_ref: str = ""
    readback_contract_ref: str = ""
    rollback_plan_ref: str = ""
    idempotency_key: str = ""
    revoked: bool = False

    def validate(self) -> "AuthorityGrant":
        if not all((self.grant_id.strip(), self.mission_id.strip(), self.action_id.strip(), self.target_scope.strip(), self.source_ref.strip())):
            raise ValueError("ACTION_AUTHORITY_IDENTITY_REQUIRED")
        observed = _instant(self.observed_at)
        expires = _instant(self.expires_at)
        if expires <= observed:
            raise ValueError("ACTION_AUTHORITY_EXPIRY_INVALID")
        if self.effect_class is not EffectClass.READ_ONLY and not self.authority_refs:
            raise ValueError("MUTATING_AUTHORITY_REQUIRES_AUTHORITY_REF")
        return self

    def current_at(self, now: str) -> bool:
        self.validate()
        point = _instant(now)
        return bool(not self.revoked and _instant(self.observed_at) <= point < _instant(self.expires_at))


@dataclass(frozen=True, slots=True)
class ActionRequest:
    action_id: str
    unit_id: str
    effect_class: EffectClass
    target_scope: str
    mutation_domain: str = ""
    provider: str = ""

    def validate(self) -> "ActionRequest":
        if not all((self.action_id.strip(), self.unit_id.strip(), self.target_scope.strip())):
            raise ValueError("ACTION_REQUEST_IDENTITY_REQUIRED")
        if self.effect_class is not EffectClass.READ_ONLY and not self.mutation_domain.strip():
            raise ValueError("MUTATING_ACTION_REQUIRES_MUTATION_DOMAIN")
        if self.effect_class is EffectClass.EXTERNAL_EFFECT and not self.provider.strip():
            raise ValueError("EXTERNAL_ACTION_REQUIRES_PROVIDER")
        return self


@dataclass(frozen=True, slots=True)
class ActionAdmissionReceipt:
    mission_id: str
    action_id: str
    unit_id: str
    state: ActionAdmissionState
    effect_class: EffectClass
    worker_id: str
    runtime_id: str
    authority_grant_id: str
    reasons: tuple[str, ...]
    topology_receipt_digest: str
    receipt_digest: str
    target_scope: str = ""
    provider: str = ""
    mutation_domain: str = ""

    @property
    def admitted(self) -> bool:
        return self.state is ActionAdmissionState.ADMITTED


class ActionAdmissionGate:
    """Fail closed between a ready execution topology and any mutating effect."""

    @staticmethod
    def _assignment(topology: ExecutionTopologyReceipt, unit_id: str):
        return next((a for a in topology.assignments if a.unit_id == unit_id), None)

    def admit(
        self,
        *,
        mission: MissionIR,
        topology: ExecutionTopologyReceipt,
        request: ActionRequest,
        now: str,
        grant: AuthorityGrant | None = None,
        provider_readiness: Mapping[str, bool] | None = None,
    ) -> ActionAdmissionReceipt:
        mission.validate(); request.validate()
        reasons: list[str] = []
        provider_readiness = dict(provider_readiness or {})

        if topology.mission_id != mission.mission_id or topology.mission_digest != mission.digest():
            raise ValueError("ACTION_TOPOLOGY_MISSION_MISMATCH")
        if not topology.executable:
            reasons.append("TOPOLOGY_NOT_EXECUTABLE")
        assignment = self._assignment(topology, request.unit_id)
        if assignment is None:
            reasons.append("TOPOLOGY_ASSIGNMENT_NOT_FOUND")
        elif assignment.mutation_domain != request.mutation_domain:
            reasons.append("ACTION_MUTATION_DOMAIN_MISMATCH")

        ceiling = _MISSION_EFFECT_CEILING.get(mission.effect_class, -1)
        if _ACTION_EFFECT_LEVEL[request.effect_class] > ceiling:
            reasons.append("MISSION_EFFECT_CEILING_EXCEEDED")

        if request.effect_class is EffectClass.READ_ONLY:
            if grant is not None and (
                grant.mission_id != mission.mission_id
                or grant.action_id != request.action_id
                or grant.effect_class is not request.effect_class
                or grant.target_scope != request.target_scope
                or not grant.current_at(now)
            ):
                reasons.append("OPTIONAL_READ_AUTHORITY_GRANT_INVALID")
            return self._receipt(mission, topology, request, assignment, grant, reasons)

        if grant is None:
            reasons.append("MUTATING_ACTION_AUTHORITY_REQUIRED")
            return self._receipt(mission, topology, request, assignment, grant, reasons)

        grant.validate()
        if not grant.current_at(now):
            reasons.append("ACTION_AUTHORITY_NOT_CURRENT")
        if grant.mission_id != mission.mission_id:
            reasons.append("ACTION_AUTHORITY_MISSION_MISMATCH")
        if grant.action_id != request.action_id:
            reasons.append("ACTION_AUTHORITY_ACTION_MISMATCH")
        if grant.effect_class is not request.effect_class:
            reasons.append("ACTION_AUTHORITY_EFFECT_MISMATCH")
        if grant.target_scope != request.target_scope:
            reasons.append("ACTION_AUTHORITY_TARGET_MISMATCH")
        if not grant.current_state_ref.strip():
            reasons.append("MUTATING_ACTION_CURRENT_STATE_PROOF_REQUIRED")
        if not grant.readback_contract_ref.strip():
            reasons.append("MUTATING_ACTION_READBACK_CONTRACT_REQUIRED")
        if not grant.idempotency_key.strip():
            reasons.append("MUTATING_ACTION_IDEMPOTENCY_KEY_REQUIRED")
        if mission.rollback_required and not grant.rollback_plan_ref.strip():
            reasons.append("MISSION_REQUIRES_ROLLBACK_PLAN")

        if request.effect_class is EffectClass.EXTERNAL_EFFECT:
            if not grant.provider_identity_ref.strip():
                reasons.append("EXTERNAL_ACTION_PROVIDER_IDENTITY_REQUIRED")
            if mission.owner_approval_required and not grant.owner_approval_ref.strip():
                reasons.append("MISSION_REQUIRES_OWNER_APPROVAL")
            if mission.provider_allowlist and request.provider not in set(mission.provider_allowlist):
                reasons.append("PROVIDER_NOT_ALLOWLISTED")
            if request.provider in set(mission.provider_denylist):
                reasons.append("PROVIDER_DENYLISTED")
            if not provider_readiness.get(request.provider, False):
                reasons.append("PROVIDER_READINESS_NOT_PROVEN")

        required = set(mission.authority_requirements)
        if required and not required.issubset(set(grant.authority_refs)):
            reasons.append("MISSION_AUTHORITY_REQUIREMENTS_UNSATISFIED")

        return self._receipt(mission, topology, request, assignment, grant, reasons)

    def _receipt(self, mission, topology, request, assignment, grant, reasons):
        state = ActionAdmissionState.ADMITTED if not reasons else ActionAdmissionState.HELD
        material = {
            "schema": SCHEMA,
            "version": VERSION,
            "mission_id": mission.mission_id,
            "action_id": request.action_id,
            "unit_id": request.unit_id,
            "state": state.value,
            "effect": request.effect_class.value,
            "target_scope": request.target_scope,
            "mutation_domain": request.mutation_domain,
            "provider": request.provider,
            "worker_id": assignment.worker_id if assignment else "",
            "runtime_id": assignment.runtime_id if assignment else "",
            "grant_id": grant.grant_id if grant else "",
            "topology": topology.receipt_digest,
            "reasons": reasons,
        }
        return ActionAdmissionReceipt(
            mission_id=mission.mission_id,
            action_id=request.action_id,
            unit_id=request.unit_id,
            state=state,
            effect_class=request.effect_class,
            worker_id=assignment.worker_id if assignment else "",
            runtime_id=assignment.runtime_id if assignment else "",
            authority_grant_id=grant.grant_id if grant else "",
            reasons=tuple(reasons),
            topology_receipt_digest=topology.receipt_digest,
            receipt_digest=_digest(material),
            target_scope=request.target_scope,
            provider=request.provider,
            mutation_domain=request.mutation_domain,
        )


__all__ = [
    "SCHEMA", "VERSION", "ActionAdmissionState", "AuthorityGrant", "ActionRequest",
    "ActionAdmissionReceipt", "ActionAdmissionGate",
]
