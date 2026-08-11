from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

RISK_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


@dataclass(frozen=True)
class Constitution:
    constitution_id: str
    version: str
    principles: tuple[str, ...]
    forbidden_effects: tuple[str, ...]
    owner_reserved_actions: tuple[str, ...]


@dataclass(frozen=True)
class PolicyRule:
    rule_id: str
    effect: str
    priority: int
    action_types: tuple[str, ...] = ()
    min_risk: str = "LOW"
    required_roles: tuple[str, ...] = ()
    required_preconditions: tuple[str, ...] = ()
    forbidden_effects: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActionMandate:
    action_id: str
    action_type: str
    risk: str
    proposer_role: str
    executor_role: str
    certifier_role: str
    preconditions: tuple[str, ...]
    intended_effects: tuple[str, ...]
    rollback_available: bool
    owner_authorised: bool = False
    review_roles: tuple[str, ...] = ()
    proof_requirements: tuple[str, ...] = ()


@dataclass
class Decision:
    status: str
    reasons: list[str] = field(default_factory=list)
    matched_rules: list[str] = field(default_factory=list)
    required_proofs: list[str] = field(default_factory=list)


class PolicyKernel:
    """Deterministic, fail-closed policy evaluator for SOL 6.1 actions."""

    def __init__(self, constitution: Constitution, rules: list[PolicyRule]) -> None:
        self.constitution = constitution
        self.rules = sorted(rules, key=lambda r: (-r.priority, r.rule_id))

    def evaluate(self, mandate: ActionMandate, observed_preconditions: set[str]) -> Decision:
        required_proofs = sorted(set(mandate.proof_requirements))
        if mandate.risk not in RISK_ORDER:
            return Decision("DENIED", ["UNKNOWN_RISK_TIER"])
        if len({mandate.proposer_role, mandate.executor_role, mandate.certifier_role}) < 3:
            return Decision("DENIED", ["ROLE_SEPARATION_VIOLATION"])
        missing = sorted(set(mandate.preconditions) - observed_preconditions)
        if missing:
            return Decision("DENIED", [f"MISSING_PRECONDITIONS:{','.join(missing)}"])
        forbidden = sorted(set(mandate.intended_effects) & set(self.constitution.forbidden_effects))
        if forbidden:
            return Decision("DENIED", [f"CONSTITUTION_FORBIDS:{','.join(forbidden)}"])
        if mandate.action_type in self.constitution.owner_reserved_actions and not mandate.owner_authorised:
            return Decision("OWNER_AUTHORITY_REQUIRED", ["OWNER_RESERVED_ACTION"])
        if RISK_ORDER[mandate.risk] >= RISK_ORDER["HIGH"] and not mandate.rollback_available:
            return Decision("DENIED", ["HIGH_RISK_ACTION_REQUIRES_ROLLBACK"])

        matched: list[str] = []
        effects: list[str] = []
        review_missing = False
        for rule in self.rules:
            if rule.action_types and mandate.action_type not in rule.action_types:
                continue
            if RISK_ORDER[mandate.risk] < RISK_ORDER[rule.min_risk]:
                continue
            if set(rule.required_preconditions) - observed_preconditions:
                continue
            effect_overlap = set(rule.forbidden_effects) & set(mandate.intended_effects)
            if rule.effect == "DENY" and rule.forbidden_effects and not effect_overlap:
                continue
            if rule.effect != "DENY" and rule.forbidden_effects and effect_overlap:
                continue
            matched.append(rule.rule_id)
            effects.append(rule.effect)
            if rule.effect == "REQUIRE_REVIEW" and set(rule.required_roles) - set(mandate.review_roles):
                review_missing = True

        if "DENY" in effects:
            return Decision("DENIED", ["DENY_POLICY_PRECEDENCE"], matched, required_proofs)
        if "REQUIRE_OWNER" in effects and not mandate.owner_authorised:
            return Decision("OWNER_AUTHORITY_REQUIRED", ["POLICY_REQUIRES_OWNER"], matched, required_proofs)
        if review_missing:
            return Decision("REVIEW_REQUIRED", ["INDEPENDENT_REVIEW_REQUIRED"], matched, required_proofs)
        if "ALLOW" not in effects:
            return Decision("DENIED", ["NO_ALLOW_RULE_FAIL_CLOSED"], matched, required_proofs)
        return Decision("ELIGIBLE", ["POLICY_AND_CONSTITUTION_SATISFIED"], matched, required_proofs)

    @staticmethod
    def verify_proof_bundle(decision: Decision, proofs: dict[str, Any]) -> dict[str, Any]:
        missing = sorted(set(decision.required_proofs) - set(proofs))
        return {
            "eligible_decision": decision.status == "ELIGIBLE",
            "proof_complete": not missing,
            "missing": missing,
            "execution_authorised": decision.status == "ELIGIBLE" and not missing,
        }
