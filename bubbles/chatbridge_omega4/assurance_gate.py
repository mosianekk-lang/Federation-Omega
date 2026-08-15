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
    source_mutation: bool = False
    change_isolation_verified: bool = False
    provider_claim: bool = False
    provider_readback_verified: bool = False
    false_confidence_risk: bool = False
    false_confidence_challenge: bool = False
    unresolved_material_unknowns: Tuple[str, ...] = field(default_factory=tuple)


class PreOwnerAssuranceGate:
    """Fail-closed release gate for consequential recommendations.

    It prevents observed estate-level failure classes:
    1. major redesign before an inherited estate is sufficiently discovered;
    2. preventable defects reaching the owner because available assurance systems were
       not invoked before the recommendation was presented;
    3. source mutation before isolation;
    4. provider-effect claims without provider readback; and
    5. sophisticated/high-confidence output masking incomplete evidence.

    A PASS assessment is not the final release receipt. Consequential release must still
    persist the resulting assessment in the canonical assurance receipt store. Keeping
    receipt persistence outside the assessment avoids a circular "receipt required before
    a receipt can be generated" dependency.
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
            "version": "POA-1.1",
            "principle": "SYSTEM_QA_BEFORE_OWNER",
            "major_change_rule": "AUDIT_FIRST_BEFORE_ARCHITECTURE",
            "discovery_checks": list(cls.DISCOVERY_CHECKS),
            "consequential_checks": list(cls.CONSEQUENTIAL_CHECKS),
            "source_mutation_rule": "ISOLATE_BEFORE_MUTATION",
            "provider_claim_rule": "PROVIDER_READBACK_BEFORE_TERMINAL_CLAIM",
            "false_confidence_rule": "SOPHISTICATION_NEVER_SUBSTITUTES_FOR_DISCOVERY",
            "receipt_rule": "PERSIST_ASSESSMENT_BEFORE_CONSEQUENTIAL_RELEASE",
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
        hardening_missing = []

        if context.major_redesign and context.inherited_estate:
            discovery_missing = cls._missing(context, cls.DISCOVERY_CHECKS)

        if context.consequential:
            consequential_missing = cls._missing(context, cls.CONSEQUENTIAL_CHECKS)

        if context.source_mutation and not context.change_isolation_verified:
            hardening_missing.append("change_isolation_verified")

        if context.provider_claim and not context.provider_readback_verified:
            hardening_missing.append("provider_readback_verified")

        if context.false_confidence_risk and not context.false_confidence_challenge:
            hardening_missing.append("false_confidence_challenge")

        if context.unresolved_material_unknowns or discovery_missing:
            state = AssuranceGateState.HOLD_FOR_DISCOVERY
        elif "false_confidence_challenge" in hardening_missing:
            state = AssuranceGateState.HOLD_FOR_DISCOVERY
        elif consequential_missing or hardening_missing:
            state = AssuranceGateState.REPAIR_REQUIRED
        elif context.owner_only_decision:
            state = AssuranceGateState.OWNER_DECISION_REQUIRED
        else:
            state = AssuranceGateState.PASS

        blockers = tuple(
            dict.fromkeys(
                (
                    *discovery_missing,
                    *consequential_missing,
                    *tuple(hardening_missing),
                    *context.unresolved_material_unknowns,
                )
            )
        )
        release_allowed = state is AssuranceGateState.PASS
        owner_action_required = state is AssuranceGateState.OWNER_DECISION_REQUIRED

        return {
            "assurance_version": "POA-1.1",
            "recommendation_id": context.recommendation_id,
            "gate_state": state.value,
            "release_allowed": release_allowed,
            "owner_action_required": owner_action_required,
            "assurance_receipt_required_before_release": bool(context.consequential),
            "blocking_items": list(blockers),
            "discovery_missing": list(discovery_missing),
            "consequential_missing": list(consequential_missing),
            "hardening_missing": list(hardening_missing),
            "context": asdict(context),
        }
