"""Reuse-first solution routing kept separate from truth adjudication."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from .capability import CapabilityRegistry, CapabilitySelection, CapabilityState, canonical_json
from .model import ScanResult, Verdict
from .schema import InputError


class ReuseAction(str, Enum):
    ADOPT = "ADOPT"
    ADAPT = "ADAPT"
    COMPOSE = "COMPOSE"
    PATCH_EXISTING = "PATCH_EXISTING"
    BUILD_NEW_ONLY_IF_GAP = "BUILD_NEW_ONLY_IF_GAP"
    NO_ACTION_REQUIRED = "NO_ACTION_REQUIRED"


@dataclass(frozen=True)
class SolutionDecision:
    schema_version: str
    decision_id: str
    truth_verdict: str
    decision: str
    reuse_action: ReuseAction
    objective: str
    selected_capability_ids: tuple[str, ...]
    covered_capabilities: tuple[str, ...]
    capability_gaps: tuple[str, ...]
    suppressed_duplicates: tuple[str, ...]
    build_authorized: bool
    gap_proof_required: bool
    external_execution_claimed: bool
    promotion_authorized: bool
    manual_user_tasks: tuple[str, ...]
    rationale: str
    provenance: tuple[str, ...]
    rejected: tuple[dict[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["reuse_action"] = self.reuse_action.value
        for key in (
            "selected_capability_ids", "covered_capabilities", "capability_gaps",
            "suppressed_duplicates", "manual_user_tasks", "provenance", "rejected",
        ):
            value[key] = list(value[key])
        return value


def _reuse_action(selection: CapabilitySelection, required_count: int) -> ReuseAction:
    if not selection.selected:
        return ReuseAction.BUILD_NEW_ONLY_IF_GAP
    complete = len(selection.covered) == required_count and not selection.gaps
    if complete and len(selection.selected) == 1:
        only = selection.selected[0]
        if only.state >= CapabilityState.VERIFIED_SCOPED:
            return ReuseAction.ADOPT
        return ReuseAction.ADAPT
    if len(selection.selected) > 1:
        return ReuseAction.COMPOSE
    return ReuseAction.ADAPT


class SolutionRouter:
    schema_version = "realityguard.solution.v1"

    def route(self, scan: ScanResult, payload: dict[str, Any], registry: CapabilityRegistry) -> SolutionDecision:
        objective = payload.get("objective")
        required = payload.get("required_capabilities")
        if not isinstance(objective, str) or not objective.strip():
            raise InputError("objective must be a non-empty string")
        if not isinstance(required, list) or not required or not all(isinstance(v, str) and v.strip() for v in required):
            raise InputError("required_capabilities must be a non-empty string array")
        required = sorted(set(v.strip() for v in required))
        selection = registry.select(
            required,
            available_authority=str(payload.get("available_authority", "A2")),
            allow_external_effects=payload.get("allow_external_effects") is True,
            maximum_recurring_cost=float(payload.get("maximum_recurring_cost", 0)),
        )
        action = _reuse_action(selection, len(required))
        unsafe_claim = scan.verdict != Verdict.ALLOW_BOUNDED
        decision = "BLOCK_CLAIM_PRESERVE_OBJECTIVE" if unsafe_claim else "ROUTE_OBJECTIVE"
        if action == ReuseAction.BUILD_NEW_ONLY_IF_GAP:
            rationale = "No current, authorized, zero-cost capability covers the objective; a bounded gap proof is required before any new build."
        elif action == ReuseAction.ADOPT:
            rationale = "One current verified scoped capability covers the objective; reuse it without creating a replacement."
        elif action == ReuseAction.ADAPT:
            rationale = "An existing capability is the closest safe base; patch its verified gap instead of removing the objective or creating a parallel system."
        else:
            rationale = "Existing non-duplicate capabilities jointly cover or substantially reduce the objective; compose them under one route."
        provenance = tuple(sorted({item.source_ref for item in selection.selected if item.source_ref}))
        identity = {
            "truth": scan.correlation_id,
            "objective": objective.strip(),
            "required": required,
            "selected": [item.capability_id for item in selection.selected],
            "action": action.value,
        }
        return SolutionDecision(
            schema_version=self.schema_version,
            decision_id="rgs-" + hashlib.sha256(canonical_json(identity).encode()).hexdigest()[:20],
            truth_verdict=scan.verdict.value,
            decision=decision,
            reuse_action=action,
            objective=objective.strip(),
            selected_capability_ids=tuple(item.capability_id for item in selection.selected),
            covered_capabilities=selection.covered,
            capability_gaps=selection.gaps,
            suppressed_duplicates=selection.suppressed_duplicates,
            build_authorized=False,
            gap_proof_required=bool(selection.gaps),
            external_execution_claimed=False,
            promotion_authorized=False,
            manual_user_tasks=(),
            rationale=rationale,
            provenance=provenance,
            rejected=selection.rejected,
        )
