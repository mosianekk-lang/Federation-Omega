from __future__ import annotations

"""Scheduled, read-only shadow runtime for Superior Logic maturation.

This runtime is deliberately narrower than the Stage-20 controller. It proves that a
non-chat runtime can wake up, assess the next maturity gap, compile a resumable
transaction and emit a candidate work package. It does not edit source, call providers,
grant authority, or claim SELF_SUSTAINING maturity.
"""

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .autonomous_maturation import (
    AutonomousMaturationController,
    MaturationAction,
    MaturationGap,
    SelfSustainingEvidence,
)
from .federation_evolution_program import EvolutionStage, SystemEvolutionState


RUNTIME_ID = "SUPERIOR-LOGIC-MATURATION-SHADOW-V1"
RUNTIME_AUTHORITY = "A1_INTERNAL"


@dataclass(frozen=True)
class ShadowRuntimeInput:
    run_id: str
    head_sha: str
    event: str
    observed_at: str
    previous_successful_cycles: int = 0
    previous_manual_cycles: int = 0

    def validate(self) -> "ShadowRuntimeInput":
        if not self.run_id.strip() or not self.head_sha.strip() or not self.event.strip():
            raise ValueError("run_id, head_sha and event are required")
        if not self.observed_at.strip():
            raise ValueError("observed_at is required")
        if self.previous_successful_cycles < 0 or self.previous_manual_cycles < 0:
            raise ValueError("cycle counters cannot be negative")
        return self


@dataclass(frozen=True)
class ShadowCandidateWorkPackage:
    work_package_id: str
    gap_id: str
    objective: str
    experiment_class: str
    next_safe_action: str
    required_evidence: tuple[str, ...]
    prohibited_effects: tuple[str, ...]
    authority_ceiling: str = RUNTIME_AUTHORITY
    external_effect: bool = False


@dataclass(frozen=True)
class ShadowRuntimeReceipt:
    runtime_id: str
    status: str
    run_id: str
    head_sha: str
    event: str
    observed_at: str
    cycle_number: int
    previous_successful_cycles: int
    previous_manual_cycles: int
    owner_intervention_rate: float
    selected_gap_id: str
    selected_gap_score: float
    controller_action: str
    transaction_id: str
    idempotency_key: str
    expected_state_epoch: str
    candidate_work_package: ShadowCandidateWorkPackage
    self_sustaining: bool
    self_sustaining_missing: tuple[str, ...]
    next_gate: str
    truth_boundary: tuple[str, ...]
    authority_ceiling: str = RUNTIME_AUTHORITY
    external_effect: bool = False

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["receipt_sha256"] = canonical_hash(value)
        return value


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _owner_rate(cycles: int, manual_cycles: int) -> float:
    if cycles <= 0:
        return 0.0
    return round(max(0, manual_cycles) / cycles, 8)


def _gap_for(input_state: ShadowRuntimeInput) -> MaturationGap:
    cycle = input_state.previous_successful_cycles + 1
    current_manual = 1 if input_state.event == "workflow_dispatch" else 0
    manual_cycles = input_state.previous_manual_cycles + current_manual
    owner_rate = _owner_rate(cycle, manual_cycles)

    if cycle < 3:
        return MaturationGap(
            gap_id="GAP-REPEATED-SHADOW-CYCLES",
            system_id="SUPERIOR_LOGIC",
            stage=EvolutionStage.AUTONOMOUS_MATURITY_DOMINANCE_CONTROLLER,
            description="Accumulate repeated provider-native chat-independent maturation cycles.",
            mission_value_gain=0.72,
            failure_recurrence_reduction=0.60,
            owner_burden_reduction=0.82,
            proof_strength_gain=0.88,
            resilience_gain=0.74,
            capability_reuse_gain=0.70,
            reversibility=1.0,
            cost=0.0,
            risk=0.05,
            evidence_refs=("github-actions:scheduled-shadow-runtime",),
        )

    if owner_rate > 0.10:
        return MaturationGap(
            gap_id="GAP-OWNER-INTERVENTION-RATE",
            system_id="SUPERIOR_LOGIC",
            stage=EvolutionStage.AUTONOMOUS_MATURITY_DOMINANCE_CONTROLLER,
            description="Reduce manual maturation invocations below the self-sustaining ceiling.",
            mission_value_gain=0.84,
            failure_recurrence_reduction=0.58,
            owner_burden_reduction=1.0,
            proof_strength_gain=0.70,
            resilience_gain=0.78,
            capability_reuse_gain=0.75,
            reversibility=1.0,
            cost=0.0,
            risk=0.04,
            evidence_refs=("github-actions:run-history",),
        )

    return MaturationGap(
        gap_id="GAP-CLOSED-LOOP-CANDIDATE-QUALIFICATION",
        system_id="SUPERIOR_LOGIC",
        stage=EvolutionStage.AUTONOMOUS_MATURITY_DOMINANCE_CONTROLLER,
        description="Move from autonomous gap planning to proof-gated challenger creation and qualification.",
        mission_value_gain=0.96,
        failure_recurrence_reduction=0.80,
        owner_burden_reduction=0.92,
        proof_strength_gain=0.86,
        resilience_gain=0.90,
        capability_reuse_gain=0.88,
        reversibility=0.95,
        cost=0.05,
        risk=0.18,
        evidence_refs=("github-actions:repeated-shadow-cycles",),
    )


def _work_package(gap: MaturationGap, cycle: int) -> ShadowCandidateWorkPackage:
    digest = canonical_hash({"gap": gap.gap_id, "cycle": cycle})[:16]
    if gap.gap_id == "GAP-CLOSED-LOOP-CANDIDATE-QUALIFICATION":
        return ShadowCandidateWorkPackage(
            work_package_id=f"SL-MAT-WP-{digest}",
            gap_id=gap.gap_id,
            objective="Create one branch-bound challenger and qualify it without direct canonical mutation.",
            experiment_class="BRANCH_BOUND_CHALLENGER",
            next_safe_action="BIND_TO_ADMITTED_CANDIDATE_BUILDER_WITH_PR_ONLY_OUTPUT",
            required_evidence=(
                "champion_anchor",
                "candidate_lineage",
                "deterministic_tests",
                "adversarial_tests",
                "independent_readback",
                "restore_test",
                "rollback_ref",
                "no_regression",
                "airlock_receipt",
            ),
            prohibited_effects=(
                "direct_main_mutation",
                "provider_authority_expansion",
                "credential_scope_expansion",
                "unapproved_recurring_cost",
                "external_consequential_effect",
            ),
        )
    return ShadowCandidateWorkPackage(
        work_package_id=f"SL-MAT-WP-{digest}",
        gap_id=gap.gap_id,
        objective="Repeat the chat-independent shadow cycle and accumulate independent run history.",
        experiment_class="REPEATED_SHADOW_RUNTIME",
        next_safe_action="ALLOW_NEXT_SCHEDULED_CYCLE",
        required_evidence=(
            "provider_run_receipt",
            "gap_selection_receipt",
            "transaction_identity",
            "artifact_readback",
        ),
        prohibited_effects=("source_mutation", "provider_mutation", "authority_expansion"),
    )


def _missing_self_sustaining(evidence: SelfSustainingEvidence) -> tuple[str, ...]:
    checks: Mapping[str, bool] = {
        "persistent_monitoring": evidence.persistent_monitoring,
        "repeated_successful_maturity_cycles": evidence.repeated_successful_maturity_cycles >= 3,
        "automatic_gap_detection": evidence.automatic_gap_detection,
        "automatic_repair_or_candidate_generation": evidence.automatic_repair_or_candidate_generation,
        "independent_proof": evidence.independent_proof,
        "verified_rollback": evidence.verified_rollback,
        "measurable_operational_value": evidence.measurable_operational_value,
        "cross_receiver_learning_with_compatibility_proof": evidence.cross_receiver_learning_with_compatibility_proof,
        "no_unresolved_constitutional_drift": evidence.no_unresolved_constitutional_drift,
        "owner_intervention_rate": evidence.owner_intervention_rate <= evidence.owner_intervention_rate_ceiling,
    }
    return tuple(key for key, passed in checks.items() if not passed)


class SuperiorLogicMaturationShadowRuntime:
    def __init__(self, controller: AutonomousMaturationController | None = None) -> None:
        self.controller = controller or AutonomousMaturationController()

    def run(self, input_state: ShadowRuntimeInput) -> ShadowRuntimeReceipt:
        input_state.validate()
        cycle = input_state.previous_successful_cycles + 1
        current_manual = 1 if input_state.event == "workflow_dispatch" else 0
        manual_cycles = input_state.previous_manual_cycles + current_manual
        gap = _gap_for(input_state)
        state_epoch = f"{input_state.head_sha[:16]}:{cycle}"
        decision = self.controller.plan(
            SystemEvolutionState(system_id="SUPERIOR_LOGIC"),
            (gap,),
            expected_state_epoch=state_epoch,
        )
        if decision.action == MaturationAction.ESCALATE_OWNER:
            raise RuntimeError("shadow runtime unexpectedly crossed the owner boundary")
        if decision.transaction is None:
            raise RuntimeError("shadow runtime did not produce a resumable transaction")

        work = _work_package(gap, cycle)
        self_evidence = SelfSustainingEvidence(
            persistent_monitoring=(input_state.event == "schedule" or input_state.previous_successful_cycles > 0),
            repeated_successful_maturity_cycles=cycle,
            automatic_gap_detection=True,
            automatic_repair_or_candidate_generation=False,
            independent_proof=False,
            verified_rollback=False,
            measurable_operational_value=False,
            cross_receiver_learning_with_compatibility_proof=False,
            no_unresolved_constitutional_drift=True,
            owner_interventions=manual_cycles,
        )
        missing = _missing_self_sustaining(self_evidence)
        next_gate = (
            "ACCUMULATE_THREE_REPEATED_PROVIDER_NATIVE_CYCLES"
            if cycle < 3
            else "ADMIT_PR_ONLY_CANDIDATE_BUILDER_AND_INDEPENDENT_ASSURANCE"
        )
        return ShadowRuntimeReceipt(
            runtime_id=RUNTIME_ID,
            status="SHADOW_MATURATION_CYCLE_VERIFIED",
            run_id=input_state.run_id,
            head_sha=input_state.head_sha,
            event=input_state.event,
            observed_at=input_state.observed_at,
            cycle_number=cycle,
            previous_successful_cycles=input_state.previous_successful_cycles,
            previous_manual_cycles=input_state.previous_manual_cycles,
            owner_intervention_rate=_owner_rate(cycle, manual_cycles),
            selected_gap_id=gap.gap_id,
            selected_gap_score=gap.priority_score,
            controller_action=decision.action.value,
            transaction_id=decision.transaction.transaction_id,
            idempotency_key=decision.transaction.idempotency_key,
            expected_state_epoch=state_epoch,
            candidate_work_package=work,
            self_sustaining=self_evidence.self_sustaining,
            self_sustaining_missing=missing,
            next_gate=next_gate,
            truth_boundary=(
                "scheduled_shadow_execution_does_not_prove_self_sustaining_maturity",
                "work_package_generation_does_not_prove_candidate_improvement",
                "github_actions_execution_does_not_grant_external_provider_authority",
                "no_source_or_provider_mutation_occurs_in_this_runtime",
            ),
        )

    @staticmethod
    def write_receipts(receipt: ShadowRuntimeReceipt, output_dir: Path) -> tuple[Path, Path, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        payload = receipt.to_dict()
        receipt_path = output_dir / "maturation_receipt.json"
        work_path = output_dir / "candidate_work_package.json"
        heartbeat_path = output_dir / "heartbeat.json"
        receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        work_path.write_text(
            json.dumps(asdict(receipt.candidate_work_package), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        heartbeat = {
            "runtime_id": receipt.runtime_id,
            "run_id": receipt.run_id,
            "head_sha": receipt.head_sha,
            "cycle_number": receipt.cycle_number,
            "status": receipt.status,
            "selected_gap_id": receipt.selected_gap_id,
            "self_sustaining": receipt.self_sustaining,
            "next_gate": receipt.next_gate,
            "external_effect": False,
        }
        heartbeat["heartbeat_sha256"] = canonical_hash(heartbeat)
        heartbeat_path.write_text(json.dumps(heartbeat, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return receipt_path, work_path, heartbeat_path


__all__ = [
    "RUNTIME_AUTHORITY",
    "RUNTIME_ID",
    "ShadowCandidateWorkPackage",
    "ShadowRuntimeInput",
    "ShadowRuntimeReceipt",
    "SuperiorLogicMaturationShadowRuntime",
    "canonical_hash",
]
