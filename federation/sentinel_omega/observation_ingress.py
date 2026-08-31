from __future__ import annotations

"""Proof-bound observation ingress adapters for Sentinel Ω.

These adapters convert already-fetched provider/readback records into the canonical
NormalizedObservation shape. They do not call providers, create authority, or
upgrade record provenance. A source receipt/reference is mandatory for every
observation.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from .observability_causal_fabric import NormalizedObservation, SignalKind


def _iso(value: str) -> str:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc).isoformat()


def _require_proof(proof_ref: str) -> str:
    proof_ref = str(proof_ref).strip()
    if not proof_ref:
        raise ValueError("proof_ref is required")
    return proof_ref


def _status(record: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return str(record[key]).strip().upper()
    return "UNKNOWN"


@dataclass(frozen=True)
class GitHubWorkflowRunAdapter:
    source: str = "GITHUB_ACTIONS"

    def adapt(self, record: Mapping[str, Any], *, proof_ref: str) -> NormalizedObservation:
        proof = _require_proof(proof_ref)
        run_id = str(record.get("id") or record.get("run_id") or "").strip()
        name = str(record.get("name") or record.get("workflow_name") or "").strip()
        observed_at = str(record.get("updated_at") or record.get("created_at") or "").strip()
        if not run_id or not name or not observed_at:
            raise ValueError("workflow run id/name/timestamp are required")
        status = _status(record, "status")
        conclusion = _status(record, "conclusion")
        if status != "COMPLETED":
            severity = 0.25 if status in {"QUEUED", "IN_PROGRESS", "PENDING"} else 0.45
            fingerprint = f"GITHUB_WORKFLOW_{status}:{name}"
            kind = SignalKind.HEALTH
        elif conclusion in {"SUCCESS", "NEUTRAL", "SKIPPED"}:
            severity = 0.05
            fingerprint = f"GITHUB_WORKFLOW_{conclusion}:{name}"
            kind = SignalKind.HEALTH
        else:
            severity = 0.95 if conclusion in {"FAILURE", "TIMED_OUT", "ACTION_REQUIRED"} else 0.75
            fingerprint = f"GITHUB_WORKFLOW_{conclusion}:{name}"
            kind = SignalKind.EVENT
        head_sha = str(record.get("head_sha") or "").strip() or None
        return NormalizedObservation(
            observation_id=f"GH-RUN-{run_id}",
            source=self.source,
            signal_kind=kind,
            target_id=f"github:workflow:{name}",
            observed_at=_iso(observed_at),
            fingerprint=fingerprint,
            severity=severity,
            proof_refs=(proof,),
            change_ref=head_sha,
            attributes={
                "run_id": run_id,
                "status": status,
                "conclusion": conclusion,
                "event": record.get("event"),
                "head_branch": record.get("head_branch"),
                "run_number": record.get("run_number"),
            },
        ).validate()


@dataclass(frozen=True)
class HeartbeatObservationAdapter:
    source: str = "FEDERATION_HEARTBEAT"

    def adapt(
        self,
        record: Mapping[str, Any],
        *,
        target_id: str,
        proof_ref: str,
    ) -> NormalizedObservation:
        proof = _require_proof(proof_ref)
        target = str(target_id).strip()
        observed_at = str(record.get("checkedAt") or record.get("checked_at") or record.get("timestamp") or "").strip()
        status = _status(record, "status", "state")
        if not target or not observed_at or status == "UNKNOWN":
            raise ValueError("heartbeat target/timestamp/status are required")
        if any(token in status for token in ("FATAL", "FAILED", "DOWN", "ERROR", "UNHEALTHY")):
            severity = 0.95
            kind = SignalKind.EVENT
        elif any(token in status for token in ("DEGRADED", "WARN", "LATE", "STALE", "SKIPPED_LOCKED")):
            severity = 0.65
            kind = SignalKind.HEALTH
        else:
            severity = 0.05
            kind = SignalKind.HEALTH
        identity = str(record.get("heartbeat_id") or record.get("id") or f"{target}:{observed_at}")
        return NormalizedObservation(
            observation_id=f"HB-{identity}",
            source=self.source,
            signal_kind=kind,
            target_id=target,
            observed_at=_iso(observed_at),
            fingerprint=f"HEARTBEAT_{status}:{target}",
            severity=severity,
            proof_refs=(proof,),
            attributes={
                "status": status,
                "version": record.get("version"),
                "script_id": record.get("scriptId") or record.get("script_id"),
                "details": record.get("detailsJson") or record.get("details"),
            },
        ).validate()


@dataclass(frozen=True)
class QueueObservationAdapter:
    source: str = "FEDERATION_QUEUE"

    def adapt(
        self,
        record: Mapping[str, Any],
        *,
        queue_id: str,
        proof_ref: str,
        now: str,
    ) -> NormalizedObservation:
        proof = _require_proof(proof_ref)
        queue = str(queue_id).strip()
        command_id = str(record.get("Command_ID") or record.get("command_id") or record.get("id") or "").strip()
        updated_at = str(record.get("Updated_At") or record.get("updated_at") or record.get("timestamp") or "").strip()
        status = _status(record, "Status", "status", "state")
        if not queue or not command_id or not updated_at or status == "UNKNOWN":
            raise ValueError("queue/command/timestamp/status are required")
        age_seconds = max(0.0, (datetime.fromisoformat(_iso(now)) - datetime.fromisoformat(_iso(updated_at))).total_seconds())
        retries = int(record.get("retry_count") or record.get("Retry_Count") or 0)
        if any(token in status for token in ("FAILED", "DEAD", "FATAL", "QUARANTINED")):
            severity = 0.95
            kind = SignalKind.EVENT
        elif status in {"RUNNING_GAS", "RUNNING", "ACTIVE"}:
            severity = min(0.75, 0.10 + age_seconds / 3600.0)
            kind = SignalKind.QUEUE
        elif status in {"QUEUED", "READY", "PENDING", "RETRY_READY"}:
            severity = min(0.90, 0.15 + age_seconds / 1800.0 + 0.10 * retries)
            kind = SignalKind.QUEUE
        elif any(token in status for token in ("CLOSED", "COMPLETE", "DONE", "SUCCESS")):
            severity = 0.05
            kind = SignalKind.QUEUE
        else:
            severity = 0.40
            kind = SignalKind.QUEUE
        return NormalizedObservation(
            observation_id=f"QUEUE-{queue}-{command_id}",
            source=self.source,
            signal_kind=kind,
            target_id=f"queue:{queue}",
            observed_at=_iso(updated_at),
            fingerprint=f"QUEUE_{status}:{queue}",
            severity=severity,
            proof_refs=(proof,),
            attributes={
                "command_id": command_id,
                "status": status,
                "age_seconds": round(age_seconds, 3),
                "retry_count": retries,
                "receipt": record.get("Receipt") or record.get("receipt"),
            },
        ).validate()


@dataclass(frozen=True)
class ProjectionDriftObservationAdapter:
    source: str = "FEDERATION_STATE_PROJECTION"

    def adapt(
        self,
        *,
        system_id: str,
        observed_ref: str,
        expected_ref: str,
        observed_at: str,
        proof_ref: str,
    ) -> NormalizedObservation:
        proof = _require_proof(proof_ref)
        system = str(system_id).strip()
        observed = str(observed_ref).strip()
        expected = str(expected_ref).strip()
        if not system or not observed or not expected:
            raise ValueError("system/observed_ref/expected_ref are required")
        drifted = observed != expected
        return NormalizedObservation(
            observation_id=f"PROJECTION-{system}-{observed[:12]}-{expected[:12]}",
            source=self.source,
            signal_kind=SignalKind.PROOF if not drifted else SignalKind.EVENT,
            target_id=f"projection:{system}",
            observed_at=_iso(observed_at),
            fingerprint=("SOURCE_PROJECTION_DRIFT" if drifted else "SOURCE_PROJECTION_MATCH") + f":{system}",
            severity=0.85 if drifted else 0.02,
            proof_refs=(proof,),
            change_ref=expected,
            attributes={"observed_ref": observed, "expected_ref": expected, "drifted": drifted},
        ).validate()


class ObservationIngressBatch:
    """Deduplicates adapter outputs without hiding conflicting provider readbacks."""

    @staticmethod
    def collect(observations: Iterable[NormalizedObservation]) -> tuple[NormalizedObservation, ...]:
        by_id: dict[str, NormalizedObservation] = {}
        for observation in observations:
            item = observation.validate()
            prior = by_id.get(item.observation_id)
            if prior is not None and prior != item:
                raise ValueError(f"conflicting ingress observation: {item.observation_id}")
            by_id[item.observation_id] = item
        return tuple(sorted(by_id.values(), key=lambda item: (item.observed_at, item.observation_id)))
