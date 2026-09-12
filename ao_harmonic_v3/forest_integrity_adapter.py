from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .forest_integrity import (
    ConfidenceBand,
    EvidenceAtom,
    ObjectiveGenome,
    PathCandidate,
    rank_admissible_paths,
)
from .forest_omega import ForestOmegaContext
from .models import TruthState


CRITICAL_LEGACY_CONTROLS = (
    "legal_route_complete",
    "teach_back_complete",
    "jfrie_bound",
    "deadline_state_verified",
    "evidence_preservation_current",
    "continuity_checkpoint_current",
    "best_current_version_gate_passed",
)

ROUTE_ADMISSIBILITY_FIELDS = (
    "available",
    "authorised",
    "safe",
    "deadline_viable",
    "privacy_acceptable",
    "cost_acceptable",
    "dependencies_ready",
    "evidence_sufficient",
    "rollback_available",
)


@dataclass(frozen=True, slots=True)
class LegacyControlAssessment:
    control: str
    declared_value: bool
    typed_state: str
    consequentially_proven: bool = False


@dataclass(frozen=True, slots=True)
class ForestIntegrityShadowReport:
    matter_id: str
    objective: dict[str, Any]
    evidence_atoms: tuple[dict[str, Any], ...]
    control_assessments: tuple[dict[str, Any], ...]
    path_candidates: tuple[dict[str, Any], ...]
    admissible_paths: tuple[dict[str, Any], ...]
    missing_route_fields: dict[str, tuple[str, ...]]
    consequential_release_ready: bool
    owner_approval_represented: bool
    provider_effect_proved: bool
    authority_ceiling: str = "A1_INTERNAL"
    external_effect: bool = False
    runtime_rewired: bool = False
    truth_class: str = "SHADOW_TYPED_INTERPRETATION_OF_LEGACY_INPUT_NOT_PROVIDER_FACT"


class ForestIntegrityShadowAdapter:
    """Fail-closed typed interpretation of legacy ForestOmegaContext.

    This adapter does not change ForestFirstOmega.run(). It exists to measure
    where legacy boolean/string/routing semantics differ from typed Forest
    integrity contracts before any runtime migration is attempted.
    """

    def objective(self, context: ForestOmegaContext) -> ObjectiveGenome:
        return ObjectiveGenome(
            objective_id=f"FOREST:{context.matter_id}",
            objective=context.objective,
            desired_outcome=context.desired_outcome,
            success_conditions=(
                f"desired outcome achieved: {context.desired_outcome}",
                "proof and authority remain inside verified scope",
            ),
            constraints=tuple(context.cross_lane_risks),
            stop_conditions=(
                "verified authority boundary changes",
                "material contradictory evidence changes the decision",
                "objective is genuinely exhausted",
            ),
        )

    @staticmethod
    def evidence(context: ForestOmegaContext) -> tuple[EvidenceAtom, ...]:
        atoms: list[EvidenceAtom] = []
        for index, statement in enumerate(context.tree_facts, 1):
            atoms.append(
                EvidenceAtom(
                    evidence_id=f"LEGACY-TREE-{index}",
                    statement=statement,
                    truth_state=TruthState.UNVERIFIED,
                    source_refs=(),
                    confidence_band=ConfidenceBand.LOW,
                    direct=False,
                    scope=context.matter_id,
                )
            )
        return tuple(atoms)

    @staticmethod
    def controls(context: ForestOmegaContext) -> tuple[LegacyControlAssessment, ...]:
        rows: list[LegacyControlAssessment] = []
        for control in CRITICAL_LEGACY_CONTROLS:
            value = bool(getattr(context, control))
            rows.append(
                LegacyControlAssessment(
                    control=control,
                    declared_value=value,
                    typed_state="DECLARED_TRUE_UNBOUND" if value else "DECLARED_FALSE_BLOCKING",
                    consequentially_proven=False,
                )
            )
        return tuple(rows)

    @staticmethod
    def path(raw: dict[str, Any], index: int) -> tuple[PathCandidate, tuple[str, ...]]:
        missing = tuple(field for field in ROUTE_ADMISSIBILITY_FIELDS if field not in raw)
        candidate = PathCandidate(
            path_id=str(raw.get("route_id", f"FFI-ROUTE-{index}")),
            available=bool(raw.get("available", False)),
            authorised=bool(raw.get("authorised", False)),
            safe=bool(raw.get("safe", False)),
            deadline_viable=bool(raw.get("deadline_viable", False)),
            privacy_acceptable=bool(raw.get("privacy_acceptable", False)),
            cost_acceptable=bool(raw.get("cost_acceptable", False)),
            dependencies_ready=bool(raw.get("dependencies_ready", False)),
            evidence_sufficient=bool(raw.get("evidence_sufficient", False)),
            rollback_available=bool(raw.get("rollback_available", False)),
            strategic_value=float(raw.get("strategic_value", 0.0)),
            proof_strength=float(raw.get("proof_strength", 0.0)),
            reversibility=float(raw.get("reversibility", 0.0)),
            information_gain=float(raw.get("information_gain", 0.0)),
            owner_burden=float(raw.get("owner_burden", 0.0)),
            maintenance_cost=float(raw.get("maintenance_cost", 0.0)),
        )
        return candidate, missing

    def evaluate(self, context: ForestOmegaContext) -> ForestIntegrityShadowReport:
        objective = self.objective(context)
        evidence = self.evidence(context)
        controls = self.controls(context)

        candidates: list[PathCandidate] = []
        missing_fields: dict[str, tuple[str, ...]] = {}
        for index, raw in enumerate(context.route_alternatives, 1):
            candidate, missing = self.path(raw, index)
            candidates.append(candidate)
            if missing:
                missing_fields[candidate.path_id] = missing

        admissible = rank_admissible_paths(
            candidates,
            rollback_required=bool(context.consequential_action_planned),
        )

        critical_controls_proven = all(row.consequentially_proven for row in controls)
        evidence_proven = all(atom.consequentially_usable() for atom in evidence) if evidence else False
        owner_approval_represented = False
        consequential_release_ready = bool(
            not context.consequential_action_planned
            and critical_controls_proven
            and evidence_proven
            and admissible
        )

        return ForestIntegrityShadowReport(
            matter_id=context.matter_id,
            objective=asdict(objective),
            evidence_atoms=tuple(asdict(atom) for atom in evidence),
            control_assessments=tuple(asdict(row) for row in controls),
            path_candidates=tuple(asdict(path) for path in candidates),
            admissible_paths=tuple(asdict(path) for path in admissible),
            missing_route_fields=missing_fields,
            consequential_release_ready=consequential_release_ready,
            owner_approval_represented=owner_approval_represented,
            provider_effect_proved=False,
        )


__all__ = [
    "CRITICAL_LEGACY_CONTROLS",
    "ROUTE_ADMISSIBILITY_FIELDS",
    "ForestIntegrityShadowAdapter",
    "ForestIntegrityShadowReport",
    "LegacyControlAssessment",
]
