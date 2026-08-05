from __future__ import annotations

from typing import Any, Mapping

from federation_learning import EventType

from .algorithms import (
    AUTHORITY_CEILING, ActionSpecificProofValidator, AlgorithmResult,
    ClaimProofDistanceGuard, ControlPlaneIntegrityGuard,
    CorpusSelectionIntegrityEvaluator, DirectiveExecutionCompiler,
    ProofStateTransitionGuard, TerminalFinalityResolver, sha256,
)
from .foundry_model import FoundryCycleResult
from .replication import CrossImplementationReplicationEvaluator


def finalize_foundry_cycle(self: Any, payload: Mapping[str, Any], cycle_id: str, evidence_refs: list[str], results: list[AlgorithmResult], learning_events: list[dict[str, Any]], opportunity_result: AlgorithmResult):
    for result in results:
        learning_events.extend(self._record_result(cycle_id=cycle_id, result=result, evidence_refs=evidence_refs))
        if result.algorithm_id in {item.get("algorithm_id") for item in opportunity_result.output.get("opportunities", [])}:
            try:
                target_state = "TEST_PASSED" if not result.violations else "BLOCKED"
                current_state = str(self.registry.get_lane(result.algorithm_id)["state"])
                if current_state != target_state:
                    self.registry.transition(result.algorithm_id, target_state, [result.status, result.as_dict()["receipt_sha256"]], "bounded deterministic algorithm execution")
            except (KeyError, ValueError):
                pass
    release_blocking_ids = {
        DirectiveExecutionCompiler.algorithm_id,
        ClaimProofDistanceGuard.algorithm_id,
        TerminalFinalityResolver.algorithm_id,
        CorpusSelectionIntegrityEvaluator.algorithm_id,
        ControlPlaneIntegrityGuard.algorithm_id,
        ActionSpecificProofValidator.algorithm_id,
        ProofStateTransitionGuard.algorithm_id,
        CrossImplementationReplicationEvaluator.algorithm_id,
    }
    critical_failures = [
        result for result in results
        if result.algorithm_id in release_blocking_ids
        and (bool(result.violations) or result.status in {
            "TERMINAL_FINALITY_OPEN", "INVENTORY_OR_ANALYSIS_INCOMPLETE",
            "UNVERIFIED", "DISPUTED", "BLOCKED_INVALID_CLAIM",
            "NO_AUTHORISED_EXPERIMENT_SELECTED", "TRANSITION_BLOCKED",
            "REPLICATION_DIVERGENCE",
        })
    ]
    status = "PASSED_WITH_HELD_GATES" if critical_failures else "PASSED"
    terminal_event = self.learning.record(
        event_type=EventType.SUCCESS if not critical_failures else EventType.CONSTRAINT,
        system_id=self.system_id,
        workflow_id=self.workflow_id,
        mission_id=self.mission_id,
        summary=f"algorithm foundry cycle {cycle_id}: {status}",
        details={
            "algorithm_count": len(results),
            "opportunity_count": opportunity_result.output.get("opportunity_count", 0),
            "critical_held_algorithm_ids": [item.algorithm_id for item in critical_failures],
            "cycle_status": status,
        },
        evidence_refs=evidence_refs,
        source_run_id=cycle_id,
        event_key=f"{cycle_id}:TERMINAL:{status}",
        category="CONTRACT" if critical_failures else None,
    )
    learning_events.append(terminal_event)
    registry_chain = self.registry.verify_chain()
    learning_chain = self.learning.verify_chain()
    evolution_chain = self.algorithm_ledger.verify_chain()
    proof = {
        "registry_chain": "PASSED" if registry_chain else "FAILED",
        "learning_chain": learning_chain,
        "evolution_chain": evolution_chain,
        "algorithm_result_receipts": [result.as_dict()["receipt_sha256"] for result in results],
        "source_signal_count": len(payload.get("lesson_signals", [])),
        "learning_event_count": len(learning_events),
        "authority_ceiling": AUTHORITY_CEILING,
        "external_effect": False,
    }
    proof["proof_sha256"] = sha256(proof)
    innovation_delta = {
        "identified_algorithm_opportunities": opportunity_result.output.get("opportunities", []),
        "tested_algorithm_ids": sorted({result.algorithm_id for result in results}),
        "reusable_gene_count": sum(1 for result in results if result.status == "ENGINEERING_GENE_COMPILED"),
        "preserved_negative_result_count": sum(1 for result in results if "NEGATIVE" in result.status or result.violations),
        "registered_algorithm_count": len(self.catalog.get("algorithms", [])),
        "next_experiment": "provider-independent replication and real-matter calibration" if not critical_failures else "close held proof and finality gates before promotion",
    }
    learning_summary = self.learning.summary()
    learning_delta = {
        "events_recorded": len(learning_events),
        "ledger_head_hash": learning_chain["ledger_head_hash"],
        "active_trigger_count": learning_summary["active_trigger_count"],
        "candidate_trigger_count": learning_summary["candidate_trigger_count"],
        "unresolved_failure_fingerprints": learning_summary["unresolved_failure_fingerprints"],
    }
    return FoundryCycleResult(
        cycle_id=cycle_id,
        status=status,
        algorithm_results=tuple(result.as_dict() for result in results),
        opportunity_count=int(opportunity_result.output.get("opportunity_count", 0)),
        innovation_delta=innovation_delta,
        learning_delta=learning_delta,
        maturity="LOCAL_DETERMINISTIC_FOUNDRY_EVOLUTION_AND_REPLICATION_CANARY_PASSED",
        proof=proof,
    )
