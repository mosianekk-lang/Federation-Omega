from __future__ import annotations

"""Sentinel Ω binding into existing Federation repair/proof machinery.

This module is deliberately not an executor or scheduler. It converts a
proof-bound Formation Ω ActionCandidate into the existing SOL 6.1
RepairCandidate contract using an allowlisted runbook. A2/external-effect
bindings require explicit current provider-authority evidence but remain
EXECUTION_REQUIRED until a separate provider executor acts and semantic
readback is independently verified.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from formation_omega.autonomic_fabric import ActionCandidate, AuthorityCeiling
from sol_61_runtime.repair import RepairCandidate

SCHEMA = "SENTINEL-OMEGA-REPAIR-BINDING-V1"
EXTERNAL_EFFECTS = False

_AUTHORITY_RANK = {
    AuthorityCeiling.A0_OBSERVE: 0,
    AuthorityCeiling.A1_INTERNAL: 1,
    AuthorityCeiling.A2_BOUNDED_EFFECT: 2,
    AuthorityCeiling.A3_CONSEQUENTIAL: 3,
}


class RepairBindingState(StrEnum):
    BOUND_INTERNAL_PROOF_REQUIRED = "BOUND_INTERNAL_PROOF_REQUIRED"
    BOUND_PROVIDER_EXECUTION_REQUIRED = "BOUND_PROVIDER_EXECUTION_REQUIRED"
    HELD_NO_MATCHING_RUNBOOK = "HELD_NO_MATCHING_RUNBOOK"
    HELD_AUTHORITY_EVIDENCE = "HELD_AUTHORITY_EVIDENCE"
    HELD_OWNER_RESERVED = "HELD_OWNER_RESERVED"


@dataclass(frozen=True)
class RepairRunbook:
    runbook_id: str
    incident_class: str
    change_set: tuple[str, ...]
    rollback_steps: tuple[str, ...]
    expected_effects: dict[str, float]
    max_authority: AuthorityCeiling = AuthorityCeiling.A1_INTERNAL
    external_effect: bool = False
    risk: str = "LOW"
    controller_change: bool = False
    required_capabilities: tuple[str, ...] = ()
    proof_refs: tuple[str, ...] = ()
    provider_executor_ref: str | None = None
    semantic_readback_ref: str | None = None
    rollback_ref: str | None = None

    def validate(self) -> "RepairRunbook":
        if not self.runbook_id.strip() or not self.incident_class.strip():
            raise ValueError("runbook identity and incident_class are required")
        if not self.change_set:
            raise ValueError("runbook change_set is required")
        if not self.rollback_steps:
            raise ValueError("runbook rollback_steps are required")
        if not self.proof_refs:
            raise ValueError("runbook proof_refs are required")
        if self.external_effect and _AUTHORITY_RANK[self.max_authority] < _AUTHORITY_RANK[AuthorityCeiling.A2_BOUNDED_EFFECT]:
            raise ValueError("external-effect runbook requires A2 or higher ceiling")
        return self


@dataclass(frozen=True)
class ProviderAuthorityEvidence:
    authority_ref: str
    executor_ref: str
    target_ref: str
    semantic_readback_ref: str
    rollback_ref: str
    current: bool
    action_authorized: bool
    exact_target: bool
    reversible: bool
    no_new_spend: bool
    no_iam_change: bool
    no_credential_change: bool
    proof_refs: tuple[str, ...]

    def eligible(self) -> bool:
        return bool(
            self.authority_ref.strip()
            and self.executor_ref.strip()
            and self.target_ref.strip()
            and self.semantic_readback_ref.strip()
            and self.rollback_ref.strip()
            and self.proof_refs
            and self.current
            and self.action_authorized
            and self.exact_target
            and self.reversible
            and self.no_new_spend
            and self.no_iam_change
            and self.no_credential_change
        )


@dataclass(frozen=True)
class BoundRepairPlan:
    state: RepairBindingState
    action_id: str
    runbook_id: str | None
    repair_candidate: RepairCandidate | None
    authority_ceiling: AuthorityCeiling
    external_effect: bool
    provider_execution_authorized: bool
    provider_execution_performed: bool
    semantic_readback_required: bool
    rollback_required: bool
    proof_refs: tuple[str, ...]
    hold_reason: str | None = None


class RepairRunbookRegistry:
    """Small deterministic runbook registry; this is not a second scheduler."""

    def __init__(self, runbooks: Iterable[RepairRunbook] = ()) -> None:
        self._items: dict[str, RepairRunbook] = {}
        for item in runbooks:
            self.register(item)

    def register(self, runbook: RepairRunbook) -> None:
        runbook.validate()
        existing = self._items.get(runbook.runbook_id)
        if existing is not None and existing != runbook:
            raise ValueError(f"conflicting runbook identity: {runbook.runbook_id}")
        self._items[runbook.runbook_id] = runbook

    def match(self, *, incident_class: str, required_capabilities: tuple[str, ...]) -> tuple[RepairRunbook, ...]:
        needed = set(required_capabilities)
        matches = [
            item
            for item in self._items.values()
            if item.incident_class == incident_class and needed.issubset(set(item.required_capabilities))
        ]
        return tuple(sorted(matches, key=lambda item: (_AUTHORITY_RANK[item.max_authority], item.external_effect, item.risk, item.runbook_id)))


class SentinelRepairBinder:
    """Bind a Sentinel/Formation repair proposal to existing SOL 6.1 proof gates."""

    def bind(
        self,
        action: ActionCandidate,
        *,
        incident_class: str,
        registry: RepairRunbookRegistry,
        provider_authority: ProviderAuthorityEvidence | None = None,
    ) -> BoundRepairPlan:
        if not action.evidence_refs:
            raise ValueError("action requires evidence_refs before repair binding")
        if action.authority_ceiling == AuthorityCeiling.A3_CONSEQUENTIAL:
            return BoundRepairPlan(
                state=RepairBindingState.HELD_OWNER_RESERVED,
                action_id=action.action_id,
                runbook_id=None,
                repair_candidate=None,
                authority_ceiling=action.authority_ceiling,
                external_effect=action.external_effect,
                provider_execution_authorized=False,
                provider_execution_performed=False,
                semantic_readback_required=action.external_effect,
                rollback_required=True,
                proof_refs=tuple(sorted(set(action.evidence_refs))),
                hold_reason="OWNER_RESERVED_A3",
            )

        matches = registry.match(incident_class=incident_class, required_capabilities=tuple(action.required_capabilities))
        if not matches:
            return BoundRepairPlan(
                state=RepairBindingState.HELD_NO_MATCHING_RUNBOOK,
                action_id=action.action_id,
                runbook_id=None,
                repair_candidate=None,
                authority_ceiling=action.authority_ceiling,
                external_effect=action.external_effect,
                provider_execution_authorized=False,
                provider_execution_performed=False,
                semantic_readback_required=action.external_effect,
                rollback_required=True,
                proof_refs=tuple(sorted(set(action.evidence_refs))),
                hold_reason="NO_MATCHING_RUNBOOK",
            )

        runbook = matches[0]
        if _AUTHORITY_RANK[action.authority_ceiling] > _AUTHORITY_RANK[runbook.max_authority]:
            return self._authority_hold(action, runbook, "RUNBOOK_AUTHORITY_CEILING_EXCEEDED")
        if action.external_effect != runbook.external_effect:
            return self._authority_hold(action, runbook, "ACTION_RUNBOOK_EFFECT_MISMATCH")

        provider_authorized = False
        if action.external_effect:
            if action.authority_ceiling != AuthorityCeiling.A2_BOUNDED_EFFECT:
                return self._authority_hold(action, runbook, "EXTERNAL_EFFECT_REQUIRES_A2")
            if provider_authority is None or not provider_authority.eligible():
                return self._authority_hold(action, runbook, "PROVIDER_AUTHORITY_EVIDENCE_INCOMPLETE")
            if runbook.provider_executor_ref and runbook.provider_executor_ref != provider_authority.executor_ref:
                return self._authority_hold(action, runbook, "PROVIDER_EXECUTOR_MISMATCH")
            if runbook.semantic_readback_ref and runbook.semantic_readback_ref != provider_authority.semantic_readback_ref:
                return self._authority_hold(action, runbook, "SEMANTIC_READBACK_CONTRACT_MISMATCH")
            if runbook.rollback_ref and runbook.rollback_ref != provider_authority.rollback_ref:
                return self._authority_hold(action, runbook, "ROLLBACK_CONTRACT_MISMATCH")
            provider_authorized = True

        refs = set(action.evidence_refs) | set(runbook.proof_refs)
        if provider_authority is not None:
            refs.update(provider_authority.proof_refs)
        candidate = RepairCandidate(
            repair_id=f"sentinel:{action.action_id}:{runbook.runbook_id}",
            incident_class=incident_class,
            change_set=runbook.change_set,
            expected_effects=dict(runbook.expected_effects),
            rollback_steps=runbook.rollback_steps,
            risk=runbook.risk,
            controller_change=runbook.controller_change,
        )
        state = RepairBindingState.BOUND_PROVIDER_EXECUTION_REQUIRED if action.external_effect else RepairBindingState.BOUND_INTERNAL_PROOF_REQUIRED
        return BoundRepairPlan(
            state=state,
            action_id=action.action_id,
            runbook_id=runbook.runbook_id,
            repair_candidate=candidate,
            authority_ceiling=action.authority_ceiling,
            external_effect=action.external_effect,
            provider_execution_authorized=provider_authorized,
            provider_execution_performed=False,
            semantic_readback_required=action.external_effect,
            rollback_required=True,
            proof_refs=tuple(sorted(refs)),
            hold_reason=None,
        )

    @staticmethod
    def _authority_hold(action: ActionCandidate, runbook: RepairRunbook, reason: str) -> BoundRepairPlan:
        return BoundRepairPlan(
            state=RepairBindingState.HELD_AUTHORITY_EVIDENCE,
            action_id=action.action_id,
            runbook_id=runbook.runbook_id,
            repair_candidate=None,
            authority_ceiling=action.authority_ceiling,
            external_effect=action.external_effect,
            provider_execution_authorized=False,
            provider_execution_performed=False,
            semantic_readback_required=action.external_effect,
            rollback_required=True,
            proof_refs=tuple(sorted(set(action.evidence_refs) | set(runbook.proof_refs))),
            hold_reason=reason,
        )
