from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Tuple


class AssuranceGateState(str, Enum):
    PASS = "PASS"
    HOLD_FOR_DISCOVERY = "HOLD_FOR_DISCOVERY"
    REPAIR_REQUIRED = "REPAIR_REQUIRED"
    OWNER_DECISION_REQUIRED = "OWNER_DECISION_REQUIRED"


@dataclass(frozen=True)
class AssuranceContext:
    """Evidence summary used by the pre-owner assurance gate.

    The gate deliberately consumes results from existing assurance/audit systems rather
    than reimplementing their reasoning. A caller must therefore show which checks were
    actually run. This makes "assurance exists somewhere" insufficient: the relevant
    checks must be in the recommendation path.
    """

    recommendation_id: str
    consequential: bool = False
    major_redesign: bool = False
    inherited_estate: bool = False
    estate_inventory_verified: bool = False
    proof_state_reconciled: bool = False
    duplication_lineage_checked: bool = False
    maturity_gap_checked: bool = False
    prior_failure_scan_checked: bool = False
    realityguard_checked: bool = False
    fklm_checked: bool = False
    strongest_countercase_tested: bool = False
    authority_boundary_checked: bool = False
    reversibility_checked: bool = False
    owner_burden_checked: bool = False
    owner_only_decision: bool = False
    unresolved_material_unknowns: Tuple[str, ...] = field(default_factory=tuple)


class PreOwnerAssuranceGate:
    """Fail-closed release gate for consequential recommendations.

    It prevents two failure classes observed in the Kim DataVerse estate:
    1. major redesign before an inherited estate is sufficiently discovered; and
    2. preventable defects reaching the owner because available assurance systems were
       not invoked before the recommendation was presented.
    """

    DISCOVERY_CHECKS = (
        "estate_inventory_verified",
        "proof_state_reconciled",
        "duplication_lineage_checked",
        "maturity_gap_checked",
        "prior_failure_scan_checked",
    )
    CONSEQUENTIAL_CHECKS = (
        "proof_state_reconciled",
        "realityguard_checked",
        "fklm_checked",
        "strongest_countercase_tested",
        "authority_boundary_checked",
        "reversibility_checked",
        "owner_burden_checked",
    )

    @classmethod
    def contract(cls) -> Dict[str, Any]:
        return {
            "version": "POA-1.0",
            "principle": "SYSTEM_QA_BEFORE_OWNER",
            "major_change_rule": "AUDIT_FIRST_BEFORE_ARCHITECTURE",
            "discovery_checks": list(cls.DISCOVERY_CHECKS),
            "consequential_checks": list(cls.CONSEQUENTIAL_CHECKS),
            "release_states": [AssuranceGateState.PASS.value],
            "owner_decision_state": AssuranceGateState.OWNER_DECISION_REQUIRED.value,
            "blocked_states": [
                AssuranceGateState.HOLD_FOR_DISCOVERY.value,
                AssuranceGateState.REPAIR_REQUIRED.value,
            ],
        }

    @staticmethod
    def _missing(context: AssuranceContext, names: Tuple[str, ...]) -> Tuple[str, ...]:
        return tuple(name for name in names if not bool(getattr(context, name)))

    @classmethod
    def assess(cls, context: AssuranceContext) -> Dict[str, Any]:
        discovery_missing: Tuple[str, ...] = ()
        consequential_missing: Tuple[str, ...] = ()

        if context.major_redesign and context.inherited_estate:
            discovery_missing = cls._missing(context, cls.DISCOVERY_CHECKS)

        if context.consequential:
            consequential_missing = cls._missing(context, cls.CONSEQUENTIAL_CHECKS)

        if context.unresolved_material_unknowns or discovery_missing:
            state = AssuranceGateState.HOLD_FOR_DISCOVERY
        elif consequential_missing:
            state = AssuranceGateState.REPAIR_REQUIRED
        elif context.owner_only_decision:
            state = AssuranceGateState.OWNER_DECISION_REQUIRED
        else:
            state = AssuranceGateState.PASS

        blockers = tuple(
            dict.fromkeys(
                (*discovery_missing, *consequential_missing, *context.unresolved_material_unknowns)
            )
        )
        release_allowed = state is AssuranceGateState.PASS
        owner_action_required = state is AssuranceGateState.OWNER_DECISION_REQUIRED

        return {
            "assurance_version": "POA-1.0",
            "recommendation_id": context.recommendation_id,
            "gate_state": state.value,
            "release_allowed": release_allowed,
            "owner_action_required": owner_action_required,
            "blocking_items": list(blockers),
            "discovery_missing": list(discovery_missing),
            "consequential_missing": list(consequential_missing),
            "context": asdict(context),
        }
