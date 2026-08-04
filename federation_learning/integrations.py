from __future__ import annotations

from typing import Any, Iterable

from .fabric import EventType, LearningFabric, digest


def capture_alpha_omega_maintenance(
    fabric: LearningFabric,
    report: dict[str, Any],
    *,
    mission_id: str,
    source_run_id: str = "",
    evidence_refs: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Translate an Alpha-Omega OperationsFabric maintenance report into events."""
    system_id = str(report.get("system_id") or "ALPHA-OMEGA")
    workflow_id = "ALPHA-OMEGA-MAINTENANCE"
    common = {
        "system_id": system_id,
        "workflow_id": workflow_id,
        "mission_id": mission_id,
        "source_run_id": source_run_id,
        "evidence_refs": evidence_refs,
    }
    events: list[dict[str, Any]] = []
    drift = report.get("drift") if isinstance(report.get("drift"), dict) else {}
    failure = report.get("failure") if isinstance(report.get("failure"), dict) else {}
    repair = report.get("repair") if isinstance(report.get("repair"), dict) else {}
    retirement = (
        report.get("retirement")
        if isinstance(report.get("retirement"), dict)
        else {}
    )

    if drift.get("drift"):
        events.append(
            fabric.record(
                event_type=EventType.CONSTRAINT,
                summary="Alpha-Omega maintenance detected state drift",
                details={"drift": drift, "repair": repair},
                category="INTEGRITY",
                event_key=digest([source_run_id, system_id, "DRIFT", drift]),
                **common,
            )
        )

    failure_category = str(failure.get("category", "NONE")).upper()
    if failure_category not in {"", "NONE"}:
        events.append(
            fabric.record(
                event_type=EventType.FAILURE,
                summary=f"Alpha-Omega maintenance failure: {failure_category}",
                details={"failure": failure, "repair": repair},
                category=failure_category,
                event_key=digest(
                    [source_run_id, system_id, "FAILURE", failure_category, failure]
                ),
                **common,
            )
        )

    if retirement.get("retire"):
        events.append(
            fabric.record(
                event_type=EventType.CONSTRAINT,
                summary="Alpha-Omega retirement criteria reached",
                details={"retirement": retirement},
                category="CAPACITY",
                event_key=digest(
                    [source_run_id, system_id, "RETIREMENT", retirement]
                ),
                **common,
            )
        )

    state = str(report.get("state", "UNKNOWN")).upper()
    healthy = state in {"MAINTENANCE_HEALTHY", "HEALTHY", "VERIFIED", "PASSED"}
    events.append(
        fabric.record(
            event_type=EventType.SUCCESS if healthy else EventType.CONSTRAINT,
            summary=f"Alpha-Omega maintenance terminal state: {state}",
            details={
                "state": state,
                "report_sha256": report.get("report_sha256"),
                "proof_files": report.get("proof_files", {}),
            },
            category=None if healthy else "RUNTIME",
            event_key=digest([source_run_id, system_id, "TERMINAL", state]),
            **common,
        )
    )
    return events


def capture_resolve_receipt(
    fabric: LearningFabric,
    receipt: dict[str, Any],
    *,
    mission_id: str,
    source_run_id: str = "",
    evidence_refs: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Translate an EvidenceOps RESOLVE receipt into learning events."""
    job_id = str(receipt.get("job_id") or "UNKNOWN-JOB")
    workflow_id = "EVIDENCEOPS-RESOLVE"
    common = {
        "system_id": "EVIDENCEOPS-RESOLVE",
        "workflow_id": workflow_id,
        "mission_id": mission_id,
        "source_run_id": source_run_id or job_id,
        "evidence_refs": evidence_refs,
    }
    events: list[dict[str, Any]] = []

    attempts = receipt.get("attempts", [])
    if isinstance(attempts, list):
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            status = str(attempt.get("status", "UNKNOWN")).upper()
            if status == "SUCCESS":
                events.append(
                    fabric.record(
                        event_type=EventType.SUCCESS,
                        summary=f"RESOLVE lane succeeded: {attempt.get('lane_id')}",
                        details={"attempt": attempt, "job_id": job_id},
                        event_key=digest(
                            [job_id, attempt.get("attempt"), attempt.get("lane_id"), status]
                        ),
                        **common,
                    )
                )
            else:
                failure_class = str(
                    attempt.get("failure_class") or "UNKNOWN"
                ).upper()
                events.append(
                    fabric.record(
                        event_type=EventType.FAILURE,
                        summary=f"RESOLVE lane failed: {attempt.get('lane_id')}",
                        details={"attempt": attempt, "job_id": job_id},
                        category=failure_class,
                        event_key=digest(
                            [job_id, attempt.get("attempt"), attempt.get("lane_id"), status]
                        ),
                        **common,
                    )
                )

    status = str(receipt.get("status", "UNKNOWN")).upper()
    terminal_success = status == "COMPLETE_VERIFIED"
    events.append(
        fabric.record(
            event_type=EventType.SUCCESS if terminal_success else EventType.CONSTRAINT,
            summary=f"RESOLVE terminal status: {status}",
            details={
                "job_id": job_id,
                "proof_level": receipt.get("proof_level"),
                "reason": receipt.get("reason"),
                "gates": receipt.get("gates", []),
            },
            category=None if terminal_success else "UNSUPPORTED_CLAIM",
            event_key=digest([job_id, "TERMINAL", status, receipt.get("proof_level")]),
            **common,
        )
    )
    return events
