"""Fail-closed reuse-before-build decisions for the existing RealityGuard.

This module does not create or deploy anything. It decides whether a proposed
local change may use an existing capability route, or whether a genuinely new
component has a sufficiently evidenced and bounded residual scope.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from .capability import CapabilityRegistry, canonical_json
from .schema import InputError
from .solutions import ReuseAction


class PrebuildDecisionCode(str, Enum):
    BLOCK_BUILD_INVENTORY_UNVERIFIED = "BLOCK_BUILD_INVENTORY_UNVERIFIED"
    BLOCK_DUPLICATE_BUILD = "BLOCK_DUPLICATE_BUILD"
    ROUTE_PATCH_EXISTING = "ROUTE_PATCH_EXISTING"
    ROUTE_COMPOSE_EXISTING = "ROUTE_COMPOSE_EXISTING"
    BLOCK_BUILD_GAP_PROOF_REQUIRED = "BLOCK_BUILD_GAP_PROOF_REQUIRED"
    BLOCK_BUILD_LIFECYCLE_GAP = "BLOCK_BUILD_LIFECYCLE_GAP"
    ALLOW_BOUNDED_NEW_BUILD = "ALLOW_BOUNDED_NEW_BUILD"


@dataclass(frozen=True)
class PrebuildDecision:
    schema_version: str
    decision_id: str
    decision: PrebuildDecisionCode
    objective: str
    reuse_action: ReuseAction
    selected_capability_ids: tuple[str, ...]
    covered_capabilities: tuple[str, ...]
    capability_gaps: tuple[str, ...]
    suppressed_duplicates: tuple[str, ...]
    inventory_verified: bool
    inventory_verification_scope: str
    inventory_manifest_hash: str
    gap_proof_verified: bool
    reuse_route_authorized: bool
    build_authorized: bool
    proposed_action_authorized: bool
    authorized_build_scope: tuple[str, ...]
    external_execution_claimed: bool
    manual_user_tasks: tuple[str, ...]
    reasons: tuple[str, ...]
    provenance: tuple[str, ...]
    rejected: tuple[dict[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["decision"] = self.decision.value
        value["reuse_action"] = self.reuse_action.value
        for key in (
            "selected_capability_ids", "covered_capabilities", "capability_gaps",
            "suppressed_duplicates", "authorized_build_scope", "manual_user_tasks",
            "reasons", "provenance", "rejected",
        ):
            value[key] = list(value[key])
        return value


def manifest_snapshot_hash(manifest: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(manifest).encode()).hexdigest()


def _nonempty_strings(value: Any, field_name: str, *, required: bool = True) -> tuple[str, ...]:
    if value is None and not required:
        return ()
    if not isinstance(value, list) or (required and not value):
        raise InputError(f"{field_name} must be {'a non-empty' if required else 'an'} string array")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise InputError(f"{field_name} must be {'a non-empty' if required else 'an'} string array")
    return tuple(sorted(set(item.strip() for item in value)))


class PrebuildGate:
    """Evaluate one proposed build against one finite capability snapshot."""

    schema_version = "realityguard.prebuild.v1"

    def evaluate(self, payload: dict[str, Any], capability_manifest: dict[str, Any]) -> PrebuildDecision:
        if not isinstance(payload, dict):
            raise InputError("prebuild request must be an object")
        objective = payload.get("objective")
        if not isinstance(objective, str) or not objective.strip():
            raise InputError("objective must be a non-empty string")
        required = _nonempty_strings(payload.get("requested_capabilities"), "requested_capabilities")

        proposal = payload.get("proposed_component")
        if not isinstance(proposal, dict):
            raise InputError("proposed_component must be an object")
        component_id = str(proposal.get("component_id", "")).strip()
        if not component_id:
            raise InputError("proposed_component.component_id is required")
        proposed_provides = _nonempty_strings(proposal.get("provides"), "proposed_component.provides")
        is_new = proposal.get("is_new_component") is True
        existing_target_id = str(proposal.get("existing_target_id", "")).strip()
        if is_new and existing_target_id:
            raise InputError("a new component cannot also identify an existing_target_id")
        if not is_new and not existing_target_id:
            raise InputError("an existing-component patch requires existing_target_id")

        inventory = payload.get("inventory")
        if not isinstance(inventory, dict):
            raise InputError("inventory must be an object")
        sources = _nonempty_strings(inventory.get("sources"), "inventory.sources", required=False)
        computed_hash = manifest_snapshot_hash(capability_manifest)
        supplied_hash = str(inventory.get("snapshot_hash", "")).strip()
        inventory_verified = all((
            inventory.get("enumerated") is True,
            inventory.get("inspected_to_end") is True,
            inventory.get("snapshot_current") is True,
            bool(sources),
            supplied_hash == computed_hash,
        ))

        registry = CapabilityRegistry.from_dict(capability_manifest)
        selection = registry.select(
            required,
            available_authority=str(payload.get("available_authority", "A2")),
            allow_external_effects=payload.get("allow_external_effects") is True,
            maximum_recurring_cost=float(payload.get("maximum_recurring_cost", 0)),
        )
        selected_ids = tuple(item.capability_id for item in selection.selected)
        provenance = tuple(sorted({item.source_ref for item in selection.selected if item.source_ref}))

        gap_proof = payload.get("gap_proof", {})
        if not isinstance(gap_proof, dict):
            raise InputError("gap_proof must be an object when supplied")
        proven_gaps = _nonempty_strings(
            gap_proof.get("uncovered_capabilities", []), "gap_proof.uncovered_capabilities", required=False
        )
        lifecycle_gaps = _nonempty_strings(
            gap_proof.get("lifecycle_proof_gaps", []), "gap_proof.lifecycle_proof_gaps", required=False
        )
        evidence_refs = _nonempty_strings(
            gap_proof.get("evidence_refs", []), "gap_proof.evidence_refs", required=False
        )
        adaptation_rejections = _nonempty_strings(
            gap_proof.get("adaptation_rejection_reasons", []),
            "gap_proof.adaptation_rejection_reasons",
            required=False,
        )
        gap_proof_verified = all((
            gap_proof.get("performed") is True,
            gap_proof.get("alternatives_evaluated") is True,
            set(proven_gaps) == set(selection.gaps),
            bool(evidence_refs),
            (not selection.selected) or (
                gap_proof.get("existing_adaptation_assessed") is True and bool(adaptation_rejections)
            ),
        ))

        reasons: list[str] = []
        reuse_action = ReuseAction.BUILD_NEW_ONLY_IF_GAP
        reuse_authorized = False
        build_authorized = False
        build_scope: tuple[str, ...] = ()

        if not inventory_verified:
            decision = PrebuildDecisionCode.BLOCK_BUILD_INVENTORY_UNVERIFIED
            reasons.append("The capability inventory is incomplete, stale, unbounded, or not bound to the supplied manifest hash.")
        elif not selection.gaps:
            decision = PrebuildDecisionCode.BLOCK_DUPLICATE_BUILD
            reuse_action = ReuseAction.ADOPT
            reuse_authorized = True
            reasons.append("Current eligible capability already covers the requested scope; a parallel component would duplicate it.")
        elif lifecycle_gaps and set(lifecycle_gaps).intersection(selection.gaps):
            decision = PrebuildDecisionCode.BLOCK_BUILD_LIFECYCLE_GAP
            reasons.append("Installation, binding, deployment, or readback deficits require execution proof; they do not justify replacement source code.")
        elif not is_new and existing_target_id in selected_ids:
            decision = PrebuildDecisionCode.ROUTE_PATCH_EXISTING
            reuse_action = ReuseAction.PATCH_EXISTING
            reuse_authorized = set(selection.gaps).issubset(set(proposed_provides))
            build_scope = selection.gaps if reuse_authorized else ()
            reasons.append(
                "Patch the selected existing component within the residual capability scope."
                if reuse_authorized else
                "The proposed patch does not cover every residual capability gap."
            )
        elif selection.selected and not gap_proof_verified:
            decision = PrebuildDecisionCode.ROUTE_COMPOSE_EXISTING
            reuse_action = ReuseAction.COMPOSE if len(selection.selected) > 1 else ReuseAction.ADAPT
            reuse_authorized = True
            reasons.append("Reuse, compose, or adapt the selected current capabilities before proposing a parallel component.")
        elif not gap_proof_verified:
            decision = PrebuildDecisionCode.BLOCK_BUILD_GAP_PROOF_REQUIRED
            reasons.append("A new component requires exact residual-gap proof, evidence, and assessment of existing alternatives.")
        elif not set(selection.gaps).issubset(set(proposed_provides)):
            decision = PrebuildDecisionCode.BLOCK_BUILD_GAP_PROOF_REQUIRED
            reasons.append("The proposed component does not cover every proven residual capability gap.")
        elif set(proposed_provides) - set(selection.gaps):
            decision = PrebuildDecisionCode.BLOCK_BUILD_GAP_PROOF_REQUIRED
            reasons.append("The proposed component exceeds the proven residual scope.")
        else:
            decision = PrebuildDecisionCode.ALLOW_BOUNDED_NEW_BUILD
            build_authorized = True
            build_scope = selection.gaps
            reasons.append("A current inventory proves a residual gap and the proposed new component is bounded exactly to that gap.")

        identity = {
            "objective": objective.strip(),
            "component": component_id,
            "manifest_hash": computed_hash,
            "selected": selected_ids,
            "gaps": selection.gaps,
            "decision": decision.value,
        }
        return PrebuildDecision(
            schema_version=self.schema_version,
            decision_id="rgp-" + hashlib.sha256(canonical_json(identity).encode()).hexdigest()[:20],
            decision=decision,
            objective=objective.strip(),
            reuse_action=reuse_action,
            selected_capability_ids=selected_ids,
            covered_capabilities=selection.covered,
            capability_gaps=selection.gaps,
            suppressed_duplicates=selection.suppressed_duplicates,
            inventory_verified=inventory_verified,
            inventory_verification_scope="CALLER_SUPPLIED_MANIFEST_HASH_AND_DECLARATIONS",
            inventory_manifest_hash=computed_hash,
            gap_proof_verified=gap_proof_verified,
            reuse_route_authorized=reuse_authorized,
            build_authorized=build_authorized,
            proposed_action_authorized=(decision == PrebuildDecisionCode.ROUTE_PATCH_EXISTING and reuse_authorized) or build_authorized,
            authorized_build_scope=build_scope,
            external_execution_claimed=False,
            manual_user_tasks=(),
            reasons=tuple(reasons),
            provenance=provenance,
            rejected=selection.rejected,
        )
