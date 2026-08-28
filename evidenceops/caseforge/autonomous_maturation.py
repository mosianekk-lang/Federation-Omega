from __future__ import annotations

"""Proof-governed autonomous maturation for Federation Evolution Stage 20.

This module extends the existing Federation Evolution Program. It does not create a
second top-level evolution system, schedule itself, mutate providers, grant authority,
or infer production maturity from source/tests. It compiles safe internal maturation
work and reserves owner escalation for constitutional, authority, cost, irreversible,
or genuinely consequential decisions.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence

from frontier_convergence.continuity_adapter import FederationExecutionContinuityAdapter

from .federation_evolution_program import (
    EvolutionDecision,
    EvolutionStage,
    FederationEvolutionOrchestrator,
    SystemEvolutionState,
)


AUTHORITY_CEILING = "A1_INTERNAL"
EXTERNAL_EFFECT_DEFAULT = False


class MaturationAction(str, Enum):
    OBSERVE = "OBSERVE"
    ADVANCE_EXISTING_STAGE = "ADVANCE_EXISTING_STAGE"
    AUTONOMOUS_INTERNAL_EXPERIMENT = "AUTONOMOUS_INTERNAL_EXPERIMENT"
    RUN_QUALIFICATION = "RUN_QUALIFICATION"
    PROMOTE_REVERSIBLE_INTERNAL_CHAMPION = "PROMOTE_REVERSIBLE_INTERNAL_CHAMPION"
    REVALIDATE_FRESHNESS = "REVALIDATE_FRESHNESS"
    ESCALATE_OWNER = "ESCALATE_OWNER"


@dataclass(frozen=True)
class MaturationGap:
    gap_id: str
    system_id: str
    stage: EvolutionStage
    description: str
    mission_value_gain: float = 0.0
    failure_recurrence_reduction: float = 0.0
    owner_burden_reduction: float = 0.0
    proof_strength_gain: float = 0.0
    resilience_gain: float = 0.0
    capability_reuse_gain: float = 0.0
    reversibility: float = 1.0
    cost: float = 0.0
    risk: float = 0.0
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> "MaturationGap":
        if not self.gap_id.strip() or not self.system_id.strip() or not self.description.strip():
            raise ValueError("gap_id, system_id and description are required")
        for name in (
            "mission_value_gain",
            "failure_recurrence_reduction",
            "owner_burden_reduction",
            "proof_strength_gain",
            "resilience_gain",
            "capability_reuse_gain",
            "reversibility",
            "cost",
            "risk",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0,1]")
        return self

    @property
    def priority_score(self) -> float:
        self.validate()
        positive = (
            0.24 * self.mission_value_gain
            + 0.18 * self.failure_recurrence_reduction
            + 0.18 * self.owner_burden_reduction
            + 0.12 * self.proof_strength_gain
            + 0.10 * self.resilience_gain
            + 0.08 * self.capability_reuse_gain
            + 0.10 * self.reversibility
        )
        penalty = 0.08 * self.cost + 0.14 * self.risk
        return round(positive - penalty, 9)


@dataclass(frozen=True)
class OwnerBoundary:
    constitutional_root_change: bool = False
    proof_threshold_reduction: bool = False
    owner_objective_or_value_tradeoff_change: bool = False
    irreversible_external_effect: bool = False
    destructive_data_mutation_without_verified_restore: bool = False
    new_or_expanded_provider_authority: bool = False
    credential_or_secret_scope_expansion: bool = False
    unapproved_recurring_cost: bool = False
    consequential_legal_hr_financial_or_personal_action: bool = False
    incomplete_proof_override_requested: bool = False
    unresolved_protected_objective_conflict: bool = False

    def triggers(self) -> tuple[str, ...]:
        values = asdict(self)
        return tuple(sorted(key.upper() for key, value in values.items() if value))


@dataclass(frozen=True)
class MaturationCandidate:
    candidate_id: str
    gap_id: str
    lineage_refs: tuple[str, ...]
    champion_anchor: str
    champion_score: float
    candidate_score: float
    rollback_ref: str = ""
    independent_readback: bool = False
    no_regression: bool = False
    restore_test_passed: bool = False
    proof_refs: tuple[str, ...] = ()
    creates_external_effect: bool = False
    expands_authority: bool = False
    creates_recurring_cost: bool = False
    expands_credential_scope: bool = False

    def validate(self) -> "MaturationCandidate":
        if not self.candidate_id.strip() or not self.gap_id.strip():
            raise ValueError("candidate_id and gap_id are required")
        if not 0.0 <= float(self.champion_score) <= 1.0:
            raise ValueError("champion_score must be in [0,1]")
        if not 0.0 <= float(self.candidate_score) <= 1.0:
            raise ValueError("candidate_score must be in [0,1]")
        return self

    @property
    def promotion_ready(self) -> bool:
        self.validate()
        return all(
            (
                bool(self.champion_anchor),
                bool(self.lineage_refs),
                bool(self.rollback_ref),
                self.independent_readback,
                self.no_regression,
                self.restore_test_passed,
                bool(self.proof_refs),
                self.candidate_score > self.champion_score,
                not self.creates_external_effect,
                not self.expands_authority,
                not self.creates_recurring_cost,
                not self.expands_credential_scope,
            )
        )


@dataclass(frozen=True)
class SelfSustainingEvidence:
    persistent_monitoring: bool = False
    repeated_successful_maturity_cycles: int = 0
    automatic_gap_detection: bool = False
    automatic_repair_or_candidate_generation: bool = False
    independent_proof: bool = False
    verified_rollback: bool = False
    measurable_operational_value: bool = False
    cross_receiver_learning_with_compatibility_proof: bool = False
    no_unresolved_constitutional_drift: bool = False
    owner_interventions: int = 0
    owner_intervention_rate_ceiling: float = 0.10

    @property
    def owner_intervention_rate(self) -> float:
        cycles = max(0, int(self.repeated_successful_maturity_cycles))
        if cycles == 0:
            return 1.0 if self.owner_interventions else 0.0
        return max(0, int(self.owner_interventions)) / cycles

    @property
    def self_sustaining(self) -> bool:
        return all(
            (
                self.persistent_monitoring,
                self.repeated_successful_maturity_cycles >= 3,
                self.automatic_gap_detection,
                self.automatic_repair_or_candidate_generation,
                self.independent_proof,
                self.verified_rollback,
                self.measurable_operational_value,
                self.cross_receiver_learning_with_compatibility_proof,
                self.no_unresolved_constitutional_drift,
                self.owner_intervention_rate <= self.owner_intervention_rate_ceiling,
            )
        )


@dataclass(frozen=True)
class MaturationTransaction:
    transaction_id: str
    idempotency_key: str
    system_id: str
    gap_id: str
    candidate_id: str
    expected_state_epoch: str
    payload_sha256: str
    checkpoint_state: str
    provider_receipt_refs: tuple[str, ...] = ()
    retry_rule: str = "READBACK_BEFORE_RETRY"


@dataclass(frozen=True)
class MaturationDecision:
    system_id: str
    action: MaturationAction
    evolution: EvolutionDecision
    selected_gap: MaturationGap | None
    ranked_gap_ids: tuple[str, ...]
    candidate_id: str
    owner_escalation_reasons: tuple[str, ...]
    reason_codes: tuple[str, ...]
    transaction: MaturationTransaction | None
    authority_ceiling: str = AUTHORITY_CEILING
    external_effect: bool = EXTERNAL_EFFECT_DEFAULT


class AutonomousMaturationController:
    """Stage-20 planner for autonomous, proof-gated maturation.

    The controller plans and qualifies A1_INTERNAL work. It deliberately emits no
    provider effect. External execution remains in SOVARA/provider-specific lanes.
    """

    def __init__(self, orchestrator: FederationEvolutionOrchestrator | None = None) -> None:
        self.orchestrator = orchestrator or FederationEvolutionOrchestrator()

    @staticmethod
    def _canonical_hash(value: Any) -> str:
        rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(rendered.encode("utf-8")).hexdigest()

    @staticmethod
    def rank_gaps(gaps: Iterable[MaturationGap]) -> tuple[MaturationGap, ...]:
        validated = tuple(item.validate() for item in gaps)
        return tuple(sorted(validated, key=lambda item: (-item.priority_score, item.gap_id)))

    @staticmethod
    def _candidate_owner_triggers(candidate: MaturationCandidate | None) -> OwnerBoundary:
        if candidate is None:
            return OwnerBoundary()
        return OwnerBoundary(
            irreversible_external_effect=candidate.creates_external_effect,
            new_or_expanded_provider_authority=candidate.expands_authority,
            credential_or_secret_scope_expansion=candidate.expands_credential_scope,
            unapproved_recurring_cost=candidate.creates_recurring_cost,
        )

    @classmethod
    def compile_transaction(
        cls,
        *,
        system_id: str,
        gap: MaturationGap,
        candidate: MaturationCandidate | None,
        expected_state_epoch: str,
        checkpoint_state: str,
        provider_receipt_refs: Sequence[str] = (),
    ) -> MaturationTransaction:
        payload = {
            "system_id": system_id,
            "gap_id": gap.gap_id,
            "candidate_id": candidate.candidate_id if candidate else "",
            "expected_state_epoch": expected_state_epoch,
            "checkpoint_state": checkpoint_state,
        }
        payload_sha = cls._canonical_hash(payload)
        identity = {
            "system_id": system_id,
            "gap_id": gap.gap_id,
            "candidate_id": payload["candidate_id"],
            "payload_sha256": payload_sha,
        }
        key = "maturation:" + cls._canonical_hash(identity)[:32]
        return MaturationTransaction(
            transaction_id="matx-" + cls._canonical_hash({"key": key, "epoch": expected_state_epoch})[:24],
            idempotency_key=key,
            system_id=system_id,
            gap_id=gap.gap_id,
            candidate_id=payload["candidate_id"],
            expected_state_epoch=expected_state_epoch,
            payload_sha256=payload_sha,
            checkpoint_state=checkpoint_state,
            provider_receipt_refs=tuple(provider_receipt_refs),
        )

    @staticmethod
    def continuity_checkpoint(
        *,
        system_id: str,
        transaction: MaturationTransaction,
        last_proven_state: str,
        last_completed_action: str,
        next_pending_action: str,
        previous: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return FederationExecutionContinuityAdapter.write_ahead_checkpoint(
            active_directive=f"AUTONOMOUS_MATURATION:{system_id}",
            objective="Advance the next proof-qualified maturity gate with minimum owner burden.",
            last_proven_state=last_proven_state,
            last_completed_action=last_completed_action,
            next_pending_action=next_pending_action,
            active_artifacts=(transaction.transaction_id, transaction.idempotency_key),
            active_dependencies=(transaction.expected_state_epoch,),
            tool_inflight=False,
            previous=previous,
        )

    @staticmethod
    def reconcile_interrupted_execution(
        event: Mapping[str, Any],
        *,
        previous_checkpoint: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Reuse CFRE/ChatBridge semantics after a timeout or interrupted turn."""
        return FederationExecutionContinuityAdapter.diagnose_failure(
            event,
            previous_checkpoint=previous_checkpoint,
        )

    def plan(
        self,
        state: SystemEvolutionState,
        gaps: Iterable[MaturationGap] = (),
        *,
        boundary: OwnerBoundary | None = None,
        candidate: MaturationCandidate | None = None,
        expected_state_epoch: str = "UNSPECIFIED",
    ) -> MaturationDecision:
        evolution = self.orchestrator.evaluate(state)
        ranked = self.rank_gaps(gaps)
        for gap in ranked:
            if gap.system_id != state.system_id:
                raise ValueError("maturation gap belongs to a different system")
        selected = ranked[0] if ranked else None

        base_boundary = boundary or OwnerBoundary()
        combined = OwnerBoundary(
            **{
                name: bool(getattr(base_boundary, name)) or bool(getattr(self._candidate_owner_triggers(candidate), name))
                for name in asdict(base_boundary)
            }
        )
        owner_triggers = combined.triggers()
        reasons: list[str] = []
        transaction: MaturationTransaction | None = None

        if owner_triggers:
            action = MaturationAction.ESCALATE_OWNER
            reasons.append("MANDATORY_OWNER_BOUNDARY")
        elif selected is None:
            if evolution.next_stage is None:
                action = MaturationAction.REVALIDATE_FRESHNESS
                reasons.append("NO_OPEN_GAP_CONTINUOUS_REVALIDATION")
            else:
                action = MaturationAction.ADVANCE_EXISTING_STAGE
                reasons.append(f"FOLLOW_EXISTING_EVOLUTION_STAGE:{evolution.next_stage.name}")
        elif candidate is None:
            action = MaturationAction.AUTONOMOUS_INTERNAL_EXPERIMENT
            reasons.append("HIGHEST_VALUE_GAP_SELECTED")
        elif candidate.gap_id != selected.gap_id:
            action = MaturationAction.RUN_QUALIFICATION
            reasons.append("CANDIDATE_NOT_BOUND_TO_SELECTED_GAP")
        elif candidate.promotion_ready:
            action = MaturationAction.PROMOTE_REVERSIBLE_INTERNAL_CHAMPION
            reasons.append("CHALLENGER_PARETO_IMPROVEMENT_PROVEN")
        else:
            action = MaturationAction.RUN_QUALIFICATION
            reasons.append("PROMOTION_PROOF_INCOMPLETE_CONTINUE_AUTONOMOUS_QUALIFICATION")

        if selected is not None and action != MaturationAction.ESCALATE_OWNER:
            transaction = self.compile_transaction(
                system_id=state.system_id,
                gap=selected,
                candidate=candidate,
                expected_state_epoch=expected_state_epoch,
                checkpoint_state=action.value,
            )

        return MaturationDecision(
            system_id=state.system_id,
            action=action,
            evolution=evolution,
            selected_gap=selected,
            ranked_gap_ids=tuple(item.gap_id for item in ranked),
            candidate_id=candidate.candidate_id if candidate else "",
            owner_escalation_reasons=owner_triggers,
            reason_codes=tuple(reasons),
            transaction=transaction,
        )


__all__ = [
    "AUTHORITY_CEILING",
    "EXTERNAL_EFFECT_DEFAULT",
    "AutonomousMaturationController",
    "MaturationAction",
    "MaturationCandidate",
    "MaturationDecision",
    "MaturationGap",
    "MaturationTransaction",
    "OwnerBoundary",
    "SelfSustainingEvidence",
]
