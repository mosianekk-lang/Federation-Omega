from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Mapping


_EFFECT_CLASSES = frozenset({
    "NO_EFFECT",
    "READ_ONLY",
    "BOUNDED_EFFECT",
    "CONSEQUENTIAL_EFFECT",
})


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _clean_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({str(item).strip() for item in values if str(item).strip()}))


@dataclass(frozen=True, slots=True)
class ContextBudgetIR:
    max_active_sources: int = 8
    max_heavy_sources: int = 3
    max_tool_results: int = 20
    max_tool_payload_chars: int = 120_000
    max_capsule_chars: int = 24_000

    def validate(self) -> None:
        for name, value in asdict(self).items():
            if int(value) <= 0:
                raise ValueError(f"MISSION_IR_CONTEXT_BUDGET_INVALID:{name}")


@dataclass(frozen=True, slots=True)
class MissionIR:
    """Provider-neutral execution contract compiled from domain-specific missions.

    MissionIR carries intent, constraints, proof, resource and authority needs.
    It never grants provider, financial or publication authority by itself.
    Domain systems such as SOVARA keep their richer native mission schemas and
    compile into this contract only when entering the shared execution fabric.
    """

    mission_id: str
    objective: str
    domain: str
    outcome_contract: str
    source_frontier: str
    privacy_class: str
    rights_state: str
    effect_class: str = "NO_EFFECT"
    owner_approval_required: bool = False
    rollback_required: bool = True
    authority_requirements: tuple[str, ...] = field(default_factory=tuple)
    proof_requirements: tuple[str, ...] = field(default_factory=tuple)
    provider_allowlist: tuple[str, ...] = field(default_factory=tuple)
    provider_denylist: tuple[str, ...] = field(default_factory=tuple)
    failure_domain_exclusions: tuple[str, ...] = field(default_factory=tuple)
    value_metrics: tuple[str, ...] = field(default_factory=tuple)
    context_budget: ContextBudgetIR = field(default_factory=ContextBudgetIR)
    max_cost_microunits: int | None = None
    latency_target_ms: int | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def normalized(self) -> "MissionIR":
        return MissionIR(
            mission_id=self.mission_id.strip(),
            objective=self.objective.strip(),
            domain=self.domain.strip().upper(),
            outcome_contract=self.outcome_contract.strip(),
            source_frontier=self.source_frontier.strip(),
            privacy_class=self.privacy_class.strip().upper(),
            rights_state=self.rights_state.strip().upper(),
            effect_class=self.effect_class.strip().upper(),
            owner_approval_required=bool(self.owner_approval_required),
            rollback_required=bool(self.rollback_required),
            authority_requirements=_clean_tuple(self.authority_requirements),
            proof_requirements=_clean_tuple(self.proof_requirements),
            provider_allowlist=_clean_tuple(self.provider_allowlist),
            provider_denylist=_clean_tuple(self.provider_denylist),
            failure_domain_exclusions=_clean_tuple(self.failure_domain_exclusions),
            value_metrics=_clean_tuple(self.value_metrics),
            context_budget=self.context_budget,
            max_cost_microunits=self.max_cost_microunits,
            latency_target_ms=self.latency_target_ms,
            metadata={str(k).strip(): str(v).strip() for k, v in sorted(dict(self.metadata).items())},
        )

    def validate(self) -> None:
        item = self.normalized()
        for name in (
            "mission_id",
            "objective",
            "domain",
            "outcome_contract",
            "source_frontier",
            "privacy_class",
            "rights_state",
        ):
            if not getattr(item, name):
                raise ValueError(f"MISSION_IR_REQUIRED:{name}")
        if item.effect_class not in _EFFECT_CLASSES:
            raise ValueError("MISSION_IR_EFFECT_CLASS_INVALID")
        if not item.proof_requirements:
            raise ValueError("MISSION_IR_PROOF_REQUIREMENTS_REQUIRED")
        if item.effect_class not in {"NO_EFFECT", "READ_ONLY"} and not item.authority_requirements:
            raise ValueError("MISSION_IR_EFFECT_AUTHORITY_REQUIRED")
        if set(item.provider_allowlist) & set(item.provider_denylist):
            raise ValueError("MISSION_IR_PROVIDER_POLICY_CONFLICT")
        if item.max_cost_microunits is not None and item.max_cost_microunits < 0:
            raise ValueError("MISSION_IR_COST_CEILING_INVALID")
        if item.latency_target_ms is not None and item.latency_target_ms <= 0:
            raise ValueError("MISSION_IR_LATENCY_TARGET_INVALID")
        item.context_budget.validate()

    def canonical_mapping(self) -> dict[str, object]:
        item = self.normalized()
        item.validate()
        return {
            "schema": "FEDERATION-MISSION-IR-V1",
            "mission_id": item.mission_id,
            "objective": item.objective,
            "domain": item.domain,
            "outcome_contract": item.outcome_contract,
            "source_frontier": item.source_frontier,
            "privacy_class": item.privacy_class,
            "rights_state": item.rights_state,
            "effect_class": item.effect_class,
            "owner_approval_required": item.owner_approval_required,
            "rollback_required": item.rollback_required,
            "authority_requirements": list(item.authority_requirements),
            "proof_requirements": list(item.proof_requirements),
            "provider_allowlist": list(item.provider_allowlist),
            "provider_denylist": list(item.provider_denylist),
            "failure_domain_exclusions": list(item.failure_domain_exclusions),
            "value_metrics": list(item.value_metrics),
            "context_budget": asdict(item.context_budget),
            "max_cost_microunits": item.max_cost_microunits,
            "latency_target_ms": item.latency_target_ms,
            "metadata": dict(item.metadata),
            "truth_boundary": {
                "authority_inherited": False,
                "provider_effect_authorized": False,
                "financial_effect_authorized": False,
                "publication_authorized": False,
            },
        }

    def digest(self) -> str:
        return sha256(_stable_json(self.canonical_mapping()).encode("utf-8")).hexdigest()
