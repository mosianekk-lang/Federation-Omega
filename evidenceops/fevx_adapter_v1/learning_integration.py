from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from federation_learning import EventType, LearningFabric


def capture_evidenceops_fevx_run(
    *,
    result: dict[str, Any] | None,
    workspace: str | Path,
    policy_path: str | Path,
    source_run_id: str,
    evidence_refs: Iterable[str] = (),
    exception: BaseException | None = None,
) -> dict[str, Any]:
    """Capture the complete EvidenceOps↔FEVX terminal learning state.

    This function writes only to the supplied artifact/external-evidence workspace.
    It performs no source, fact, case-wall or external mutation.
    """
    fabric = LearningFabric(workspace, policy_path=policy_path)
    captured: list[dict[str, Any]] = []
    common = {
        "system_id": "EVIDENCEOPS-FEVX-ADAPTER",
        "workflow_id": "MPMB298-READ-ONLY-ANALYTICAL-CANARY",
        "mission_id": "EVIDENCEOPS-FEVX-REAL-MATTER-LEARNING",
        "source_run_id": source_run_id,
        "evidence_refs": evidence_refs,
    }

    if exception is not None:
        captured.append(
            fabric.record(
                event_type=EventType.FAILURE,
                summary=f"{type(exception).__name__}: {exception}",
                details={
                    "exception_type": type(exception).__name__,
                    "message": str(exception),
                },
                **common,
            )
        )

    if result is not None:
        captured.extend(fabric.capture_result(result, **common))
        if result.get("real_case_accuracy_evidence") is False:
            captured.append(
                fabric.record(
                    event_type=EventType.CONSTRAINT,
                    summary="real-case legal accuracy remains unproven",
                    details={
                        "required_next_gate": (
                            "QUALIFIED_HUMAN_ACCURACY_AND_USEFULNESS_REVIEW"
                        )
                    },
                    category="UNSUPPORTED_CLAIM",
                    event_key=f"{source_run_id}:REAL_CASE_ACCURACY_UNPROVEN",
                    **common,
                )
            )
        if result.get("level_6_eligible") is False:
            captured.append(
                fabric.record(
                    event_type=EventType.CONSTRAINT,
                    summary="workflow-specific trusted autonomy remains held",
                    details={
                        "authority_ceiling": "A1_INTERNAL",
                        "reason": "owner grant and sustained calibration absent",
                    },
                    category="AUTHORITY",
                    event_key=f"{source_run_id}:LEVEL_6_HELD",
                    **common,
                )
            )

    return {
        "schema": "EVIDENCEOPS_FEVX_LEARNING_CAPTURE_V1",
        "source_run_id": source_run_id,
        "captured_event_count": len(captured),
        "events": captured,
        "verification": fabric.verify_chain(),
        "summary": fabric.summary(),
        "external_effect": False,
        "source_write": False,
        "verified_fact_write": False,
        "case_wall_crossing": False,
    }
