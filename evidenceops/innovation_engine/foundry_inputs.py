from __future__ import annotations

from typing import Any, Mapping

from federation_learning import EventType

from .algorithms import (
    AUTHORITY_CEILING, ActionSpecificProofValidator, AlgorithmOpportunityMiner,
    AlgorithmResult, ClaimProofDistanceGuard, ControlPlaneIntegrityGuard,
    CorpusSelectionIntegrityEvaluator, DirectiveExecutionCompiler,
    FailureToEngineeringGeneCompiler, InformationGainRouteSelector,
    TerminalFinalityResolver, UnknownFrontierPrioritizer,
    ProofStateTransitionGuard, EpistemicDebtPrioritizer,
    OwnerBurdenRouteOptimizer,
)
from .replication import CrossImplementationReplicationEvaluator


def build_foundry_results(self: Any, payload: Mapping[str, Any], cycle_id: str, evidence_refs: list[str]):
    results: list[AlgorithmResult] = []
    learning_events: list[dict[str, Any]] = []
    opportunity_result = AlgorithmOpportunityMiner().run(payload.get("lesson_signals", []))
    results.append(opportunity_result)
    self._register_algorithm_lanes(opportunity_result)
    directive = payload.get("directive")
    if directive:
        results.append(DirectiveExecutionCompiler().run(str(directive), available_routes=payload.get("available_routes", []), current_authority=str(payload.get("current_authority", AUTHORITY_CEILING))))
    for claim in payload.get("claims", []):
        results.append(ClaimProofDistanceGuard().run(claim))
    if payload.get("unknowns") is not None:
        results.append(UnknownFrontierPrioritizer().run(payload.get("unknowns", [])))
    if payload.get("experiments") is not None:
        results.append(InformationGainRouteSelector().run(payload.get("experiments", [])))
    if payload.get("finality_items") is not None:
        results.append(TerminalFinalityResolver().run(payload.get("finality_items", [])))
    for evaluation in payload.get("corpus_evaluations", []):
        results.append(CorpusSelectionIntegrityEvaluator().run(requested_claim=str(evaluation.get("requested_claim", "")), gates=evaluation.get("gates", {})))
    for transaction in payload.get("control_transactions", []):
        results.append(ControlPlaneIntegrityGuard().run(transaction, existing_ids=payload.get("existing_ids", []), existing_idempotency=payload.get("existing_idempotency", {}), valid_references=payload.get("valid_references", []), collision_owners=payload.get("collision_owners", {}), allowed_states=payload.get("allowed_states", [])))
    for pair in payload.get("action_proofs", []):
        results.append(ActionSpecificProofValidator().run(pair.get("action", {}), pair.get("proof", {})))
    for transition in payload.get("proof_state_transitions", []):
        results.append(ProofStateTransitionGuard().run(current_state=str(transition.get("current_state", "NO_EVIDENCE")), target_state=str(transition.get("target_state", "NO_EVIDENCE")), proof=transition.get("proof", {})))
    if payload.get("epistemic_debts") is not None:
        results.append(EpistemicDebtPrioritizer().run(payload.get("epistemic_debts", [])))
    if payload.get("route_candidates") is not None:
        results.append(OwnerBurdenRouteOptimizer().run(payload.get("route_candidates", [])))
    for pair in payload.get("replication_pairs", []):
        results.append(CrossImplementationReplicationEvaluator().run_algorithm(canonical_result=pair.get("canonical_result", {}), reference_result=pair.get("reference_result", {})))
    for lesson_index, lesson in enumerate(payload.get("failure_lessons", []), start=1):
        failure = lesson.get("failure", {})
        recovery = lesson.get("recovery")
        regression = lesson.get("regression")
        retrospective_failure = self.learning.record(
            event_type=EventType.FAILURE,
            system_id=self.system_id,
            workflow_id=self.workflow_id,
            mission_id=self.mission_id,
            summary="retrospective failure lesson: " + str(failure.get("summary", "unspecified failure")),
            details={"cycle_id": cycle_id, "source_failure": failure, "retrospective": True},
            evidence_refs=failure.get("evidence_refs", evidence_refs),
            category=str(failure.get("category", "UNKNOWN")),
            source_run_id=cycle_id,
            event_key=f"{cycle_id}:FAILURE-LESSON:{lesson_index}",
        )
        learning_events.append(retrospective_failure)
        if isinstance(recovery, Mapping):
            recovery_details = dict(recovery)
            recovery_details["resolved_failure_fingerprint"] = retrospective_failure["fingerprint"]
            learning_events.append(self.learning.record(
                event_type=EventType.RECOVERY,
                system_id=self.system_id,
                workflow_id=self.workflow_id,
                mission_id=self.mission_id,
                summary="verified recovery lesson: " + str(recovery.get("repair", "recovery recorded")),
                details=recovery_details,
                evidence_refs=recovery.get("evidence_refs", evidence_refs),
                source_run_id=cycle_id,
                event_key=f"{cycle_id}:RECOVERY-LESSON:{lesson_index}",
            ))
        results.append(FailureToEngineeringGeneCompiler().run(failure=failure, recovery=recovery, regression=regression))
    return results, learning_events, opportunity_result
