from __future__ import annotations

from typing import Any, Mapping, Sequence

from federation_learning import EventType

from .algorithms import AUTHORITY_CEILING, AlgorithmOpportunityMiner, AlgorithmResult, sha256


def _typed_event(name: str, fallback: EventType) -> EventType:
    """Use richer event types when available without breaking v1 ledgers."""
    return getattr(EventType, name, fallback)


class FoundryLearningMixin:
    def _record_result(self, *, cycle_id: str, result: AlgorithmResult, evidence_refs: Sequence[str]) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        result_dict = result.as_dict()
        negative = bool(result.violations) or any(
            marker in result.status
            for marker in (
                "BLOCKED", "REJECTED", "OPEN", "UNVERIFIED",
                "NEGATIVE", "DIVERGENCE", "NO_VALID",
            )
        )
        if result.algorithm_id == AlgorithmOpportunityMiner.algorithm_id:
            for opportunity in result.output.get("opportunities", []):
                events.append(
                    self.learning.record(
                        event_type=_typed_event("INNOVATION_CANDIDATE", EventType.CORRECTION),
                        system_id=self.system_id,
                        workflow_id=self.workflow_id,
                        mission_id=self.mission_id,
                        summary=f"algorithm opportunity: {opportunity['algorithm_id']} {opportunity['title']}",
                        details={
                            "learning_subtype": "INNOVATION_CANDIDATE",
                            "cycle_id": cycle_id,
                            "opportunity": opportunity,
                        },
                        evidence_refs=opportunity.get("evidence_refs", evidence_refs),
                        source_run_id=cycle_id,
                        event_key=f"{cycle_id}:OPPORTUNITY:{opportunity['algorithm_id']}",
                    )
                )
        semantic_type = "NEGATIVE_RESULT" if negative else "EXPERIMENT_RESULT"
        event_type = _typed_event(
            semantic_type,
            EventType.FAILURE if negative else EventType.SUCCESS,
        )
        events.append(
            self.learning.record(
                event_type=event_type,
                system_id=self.system_id,
                workflow_id=self.workflow_id,
                mission_id=self.mission_id,
                summary=f"{result.algorithm_id} produced {result.status}",
                details={
                    "learning_subtype": semantic_type,
                    "cycle_id": cycle_id,
                    "result": result_dict,
                },
                evidence_refs=evidence_refs,
                source_run_id=cycle_id,
                event_key=f"{cycle_id}:RESULT:{result.algorithm_id}:{result_dict['receipt_sha256']}",
            )
        )
        return events

    def _register_algorithm_lanes(self, opportunity_result: AlgorithmResult) -> None:
        for opportunity in opportunity_result.output.get("opportunities", []):
            algorithm_id = str(opportunity["algorithm_id"])
            try:
                current_state = str(self.registry.get_lane(algorithm_id)["state"])
            except KeyError:
                current_state = "READY"
            self.registry.upsert_lane(
                lane_id=algorithm_id,
                title=str(opportunity["title"]),
                objective=str(opportunity["reason"]),
                state=current_state,
                priority=float(opportunity["score"]),
                next_action="execute deterministic bounded test and evaluate",
                proof_state="SOURCE_BACKED_OPPORTUNITY",
            )

    def evolve_algorithm(
        self,
        *,
        algorithm_id: str,
        baseline_version: str,
        baseline_configuration: Mapping[str, Any],
        baseline_metrics: Mapping[str, float],
        candidate_version: str,
        candidate_configuration: Mapping[str, Any],
        candidate_metrics: Mapping[str, float],
        source_lessons: Sequence[str],
        expected_benefit: str,
        source_run_id: str,
        evidence_refs: Sequence[str] = (),
    ) -> dict[str, Any]:
        try:
            self.algorithm_ledger.active_version(algorithm_id)
        except KeyError:
            self.algorithm_ledger.initialize_algorithm(
                algorithm_id=algorithm_id,
                version=baseline_version,
                configuration=baseline_configuration,
                metrics=baseline_metrics,
            )
        candidate = self.algorithm_ledger.create_candidate(
            algorithm_id=algorithm_id,
            candidate_version=candidate_version,
            configuration=candidate_configuration,
            source_lessons=source_lessons,
            expected_benefit=expected_benefit,
        )
        self.learning.record(
            event_type=_typed_event("INNOVATION_CANDIDATE", EventType.CORRECTION),
            system_id=self.system_id,
            workflow_id=self.workflow_id,
            mission_id=self.mission_id,
            summary=f"evolution candidate {candidate['candidate_id']} for {algorithm_id}",
            details={
                "learning_subtype": "INNOVATION_CANDIDATE",
                "candidate": candidate,
                "expected_benefit": expected_benefit,
                "source_lessons": list(source_lessons),
            },
            evidence_refs=evidence_refs,
            source_run_id=source_run_id,
            event_key=f"{source_run_id}:EVOLUTION-CANDIDATE:{candidate['candidate_id']}",
        )
        decision = self.evolution.evaluate_and_maybe_promote(
            candidate_id=candidate["candidate_id"],
            candidate_metrics=candidate_metrics,
        )
        semantic_type = (
            "EXPERIMENT_RESULT" if decision.decision == "ACCEPT" else "NEGATIVE_RESULT"
        )
        event_type = _typed_event(
            semantic_type,
            EventType.SUCCESS if decision.decision == "ACCEPT" else EventType.FAILURE,
        )
        learning_event = self.learning.record(
            event_type=event_type,
            system_id=self.system_id,
            workflow_id=self.workflow_id,
            mission_id=self.mission_id,
            summary=f"evolution candidate {candidate['candidate_id']} decision {decision.decision}",
            details={
                "learning_subtype": semantic_type,
                "decision": decision.as_dict(),
            },
            evidence_refs=evidence_refs,
            source_run_id=source_run_id,
            event_key=f"{source_run_id}:EVOLUTION-DECISION:{candidate['candidate_id']}",
        )
        result = {
            "schema": "EVIDENCEOPS_ALGORITHM_EVOLUTION_RESULT_V1",
            "algorithm_id": algorithm_id,
            "candidate": candidate,
            "decision": decision.as_dict(),
            "learning_event_hash": learning_event["event_hash"],
            "evolution_chain": self.algorithm_ledger.verify_chain(),
            "learning_chain": self.learning.verify_chain(),
            "authority_ceiling": AUTHORITY_CEILING,
            "external_effect": False,
        }
        result["receipt_sha256"] = sha256(result)
        return result
