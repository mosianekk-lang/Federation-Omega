from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from benchmarking.cfbe_omega.mission_result_fabric_adapter_v1 import (
    MissionResultIdentity,
    MissionResultLookupReceipt,
)
from benchmarking.cfbe_omega.mission_result_index_v1 import DurableMissionResultIndex
from federation.mission_ir import MissionIR
from formation_omega.mission_convergence import (
    ConvergenceLedger,
    MissionConvergenceEngine,
    MissionProjection,
    MissionSpec,
    ProofEntry,
    WorkItem,
    WorkStatus,
)

_SCHEMA = "BCO-DURABLE-MISSION-RUNTIME-V1"
_CHECKPOINT_SCHEMA = "BCO-MISSION-CHECKPOINT-V1"
_REQUEST_STATES = frozenset({"PENDING", "RESOLVED", "EXPIRED", "CANCELLED"})
_EFFECT_CLASSES = frozenset({"NO_EFFECT", "READ_ONLY", "BOUNDED_EFFECT", "CONSEQUENTIAL_EFFECT"})


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_time(value: str) -> datetime:
    text = str(value).strip()
    if not text:
        raise ValueError("BCO_TIME_REQUIRED")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("BCO_TIME_MUST_BE_OFFSET_AWARE")
    return parsed


def _clean(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(item).strip() for item in values if str(item).strip()}))


def _checkpoint_filename(mission_id: str) -> str:
    return sha256(mission_id.encode("utf-8")).hexdigest() + ".json"


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        stream.write(_canonical(dict(payload)) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)
    try:
        directory_fd = os.open(str(path.parent), os.O_RDONLY)
    except (AttributeError, OSError):
        return
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


@dataclass(frozen=True, slots=True)
class PendingRequest:
    request_id: str
    mission_id: str
    step_id: str
    request_type: str
    target: str
    reason: str
    required_authority: tuple[str, ...]
    effect_class: str
    created_at: str
    expires_at: str
    input_identity_sha256: str
    continuation_key: str
    state: str = "PENDING"
    response_ref: str = ""
    response_sha256: str = ""
    proof_refs: tuple[str, ...] = ()

    def validate(self) -> "PendingRequest":
        required = (
            self.request_id,
            self.mission_id,
            self.step_id,
            self.request_type,
            self.target,
            self.reason,
            self.created_at,
            self.input_identity_sha256,
            self.continuation_key,
        )
        if not all(str(item).strip() for item in required):
            raise ValueError("BCO_PENDING_REQUEST_REQUIRED_FIELD_MISSING")
        if self.state not in _REQUEST_STATES:
            raise ValueError("BCO_PENDING_REQUEST_STATE_INVALID")
        if self.effect_class not in _EFFECT_CLASSES:
            raise ValueError("BCO_PENDING_REQUEST_EFFECT_CLASS_INVALID")
        _parse_time(self.created_at)
        if self.expires_at:
            _parse_time(self.expires_at)
        if self.state == "RESOLVED" and (not self.response_ref or not self.response_sha256):
            raise ValueError("BCO_PENDING_REQUEST_RESOLUTION_INCOMPLETE")
        return self

    def identity_mapping(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "mission_id": self.mission_id,
            "step_id": self.step_id,
            "request_type": self.request_type,
            "target": self.target,
            "reason": self.reason,
            "required_authority": list(self.required_authority),
            "effect_class": self.effect_class,
            "expires_at": self.expires_at,
            "input_identity_sha256": self.input_identity_sha256,
            "continuation_key": self.continuation_key,
        }


@dataclass(frozen=True, slots=True)
class MissionCheckpoint:
    checkpoint_id: str
    mission_id: str
    mission_ir_sha256: str
    sequence: int
    ledger_head_hash: str
    projection_sha256: str
    source_frontier: str
    policy_sha256: str
    environment_sha256: str
    active_work_ids: tuple[str, ...]
    completed_work_ids: tuple[str, ...]
    held_work_ids: tuple[str, ...]
    pending_request_ids: tuple[str, ...]
    bound_result_keys: tuple[str, ...]
    proof_state_sha256: str
    trace_id: str
    runtime_schema_version: int
    created_at: str
    parent_checkpoint_id: str | None
    checkpoint_sha256: str

    def body(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("checkpoint_sha256")
        payload["schema"] = _CHECKPOINT_SCHEMA
        return payload

    def validate(self) -> "MissionCheckpoint":
        if self.runtime_schema_version < 1:
            raise ValueError("BCO_RUNTIME_SCHEMA_INVALID")
        if not all(
            (
                self.checkpoint_id,
                self.mission_id,
                self.mission_ir_sha256,
                self.ledger_head_hash,
                self.projection_sha256,
                self.source_frontier,
                self.policy_sha256,
                self.environment_sha256,
                self.proof_state_sha256,
                self.created_at,
                self.checkpoint_sha256,
            )
        ):
            raise ValueError("BCO_CHECKPOINT_REQUIRED_FIELD_MISSING")
        _parse_time(self.created_at)
        if _digest(self.body()) != self.checkpoint_sha256:
            raise ValueError("BCO_CHECKPOINT_HASH_MISMATCH")
        return self


@dataclass(frozen=True, slots=True)
class ResumeReceipt:
    schema: str
    state: str
    mission_id: str
    mission_ir_sha256: str
    ledger_head_hash: str
    checkpoint_id: str = ""
    replayed_from_event_truth: bool = True
    pending_request_ids: tuple[str, ...] = ()
    ready_work_ids: tuple[str, ...] = ()
    reason: str = ""
    external_effects: int = 0
    provider_effect_authorized: bool = False
    financial_effect_authorized: bool = False
    publication_authorized: bool = False


class DurableMissionRuntimeV1:
    """Non-serving whole-mission durability composed from admitted Federation primitives.

    ConvergenceLedger remains execution event truth. MissionIR remains the mission
    identity/constraint contract. DurableMissionResultIndex remains result truth.
    Checkpoints are integrity/reference snapshots only in v1; restart state is rebuilt
    from the verified event history. No provider, financial or publication authority
    is granted by this runtime.
    """

    EVENT_MISSION_IR_BOUND = "BCO_MISSION_IR_BOUND"
    EVENT_CHECKPOINT_COMMITTED = "BCO_CHECKPOINT_COMMITTED"
    EVENT_REQUEST_PENDING = "BCO_REQUEST_PENDING"
    EVENT_REQUEST_RESOLVED = "BCO_REQUEST_RESOLVED"
    EVENT_REQUEST_EXPIRED = "BCO_REQUEST_EXPIRED"
    EVENT_REQUEST_CANCELLED = "BCO_REQUEST_CANCELLED"
    EVENT_RESULT_BOUND = "BCO_RESULT_BOUND"
    EVENT_TRACE_BOUND = "BCO_TRACE_BOUND"
    EVENT_RUNTIME_RESUMED = "BCO_RUNTIME_RESUMED"
    EVENT_RUNTIME_HELD = "BCO_RUNTIME_HELD"

    def __init__(
        self,
        root: str | Path,
        *,
        source_frontier: str,
        policy_sha256: str,
        environment_sha256: str,
        runtime_schema_version: int = 1,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.source_frontier = str(source_frontier).strip()
        self.policy_sha256 = str(policy_sha256).strip()
        self.environment_sha256 = str(environment_sha256).strip()
        self.runtime_schema_version = int(runtime_schema_version)
        if not all((self.source_frontier, self.policy_sha256, self.environment_sha256)):
            raise ValueError("BCO_RUNTIME_IDENTITY_REQUIRED")
        if self.runtime_schema_version < 1:
            raise ValueError("BCO_RUNTIME_SCHEMA_INVALID")
        self.ledger = ConvergenceLedger(self.root / "mission-events.jsonl")
        self.engine = MissionConvergenceEngine(self.ledger)
        self.result_index = DurableMissionResultIndex(self.root / "result-index.jsonl")
        self.checkpoint_dir = self.root / "checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _bound_event(self, mission_id: str):
        matches = [
            event
            for event in self.ledger.events(mission_id)
            if event.event_type == self.EVENT_MISSION_IR_BOUND
        ]
        if not matches:
            raise KeyError(f"BCO_MISSION_IR_NOT_BOUND:{mission_id}")
        first = matches[0]
        for other in matches[1:]:
            if other.payload != first.payload:
                raise ValueError("BCO_MISSION_IR_BIND_CONFLICT")
        return first

    def checkpoint_path(self, mission_id: str) -> Path:
        return self.checkpoint_dir / _checkpoint_filename(mission_id)

    def open(
        self,
        mission: MissionIR,
        *,
        required_proof_axes: Iterable[str] = ("source", "rollback"),
        trace_id: str = "",
    ) -> MissionProjection:
        normalized = mission.normalized()
        normalized.validate()
        if normalized.source_frontier != self.source_frontier:
            raise ValueError("BCO_SOURCE_FRONTIER_MISMATCH")
        try:
            bound = self._bound_event(normalized.mission_id)
        except KeyError:
            bound = None
        if bound is not None:
            if str(bound.payload["mission_ir_sha256"]) != normalized.digest():
                raise ValueError("BCO_MISSION_IR_BIND_CONFLICT")
            return self.engine.project(normalized.mission_id)

        axes = tuple(dict.fromkeys(str(item).strip() for item in required_proof_axes if str(item).strip()))
        if not normalized.rollback_required:
            axes = tuple(item for item in axes if item != "rollback")
        spec = MissionSpec.create(
            mission_id=normalized.mission_id,
            objective=normalized.objective,
            success_criteria=(normalized.outcome_contract,),
            authority_ceiling=normalized.metadata.get("authority_ceiling", "A1"),
            constraints=(
                f"MISSION_IR_EFFECT_CLASS:{normalized.effect_class}",
                f"MISSION_IR_PRIVACY_CLASS:{normalized.privacy_class}",
            ),
            required_proof_axes=axes,
            rollback_required=normalized.rollback_required,
            source_contract_ref="FEDERATION-MISSION-IR-V1",
            source_contract_sha256=normalized.digest(),
        )
        try:
            projection = self.engine.project(normalized.mission_id)
        except KeyError:
            projection = self.engine.open_mission(spec)
        else:
            if projection.mission.source_contract_sha256 != normalized.digest():
                raise ValueError("BCO_MISSION_IR_BIND_CONFLICT")

        payload = {
            "schema": _SCHEMA,
            "mission_ir_sha256": normalized.digest(),
            "mission_ir": normalized.canonical_mapping(),
            "source_frontier": self.source_frontier,
            "policy_sha256": self.policy_sha256,
            "environment_sha256": self.environment_sha256,
            "runtime_schema_version": self.runtime_schema_version,
            "truth_boundary": {
                "serving_route_changed": False,
                "provider_effect_authorized": False,
                "financial_effect_authorized": False,
                "publication_authorized": False,
            },
        }
        self.ledger.append(
            mission_id=normalized.mission_id,
            event_type=self.EVENT_MISSION_IR_BOUND,
            payload=payload,
            idempotency_key=normalized.digest(),
        )
        if trace_id:
            self.ledger.append(
                mission_id=normalized.mission_id,
                event_type=self.EVENT_TRACE_BOUND,
                payload={"trace_id": str(trace_id).strip()},
                idempotency_key=str(trace_id).strip(),
            )
        return self.engine.project(normalized.mission_id)

    def project(self, mission_id: str) -> MissionProjection:
        return self.engine.project(mission_id)

    def set_work_item(self, mission_id: str, item: WorkItem) -> MissionProjection:
        return self.engine.set_work_item(mission_id, item)

    def update_work_status(
        self,
        mission_id: str,
        work_id: str,
        status: WorkStatus,
        *,
        result_refs: Iterable[str] = (),
    ) -> MissionProjection:
        return self.engine.update_work_status(mission_id, work_id, status, result_refs=result_refs)

    def bind_proof(self, mission_id: str, entry: ProofEntry) -> MissionProjection:
        return self.engine.update_proof(mission_id, entry)

    def verify_success(
        self,
        mission_id: str,
        criterion: str,
        *,
        evidence_refs: Iterable[str],
    ) -> MissionProjection:
        return self.engine.verify_success(mission_id, criterion, evidence_refs=evidence_refs)

    @staticmethod
    def _request_from_payload(payload: Mapping[str, Any]) -> PendingRequest:
        raw = dict(payload)
        raw["required_authority"] = tuple(raw.get("required_authority", ()))
        raw["proof_refs"] = tuple(raw.get("proof_refs", ()))
        return PendingRequest(**raw).validate()

    def _request_projection(self, mission_id: str) -> dict[str, PendingRequest]:
        requests: dict[str, PendingRequest] = {}
        for event in self.ledger.events(mission_id):
            if event.event_type == self.EVENT_REQUEST_PENDING:
                request = self._request_from_payload(event.payload["request"])
                prior = requests.get(request.request_id)
                if prior is not None and prior.identity_mapping() != request.identity_mapping():
                    raise ValueError("BCO_PENDING_REQUEST_IDENTITY_CONFLICT")
                requests[request.request_id] = request
            elif event.event_type in {
                self.EVENT_REQUEST_RESOLVED,
                self.EVENT_REQUEST_EXPIRED,
                self.EVENT_REQUEST_CANCELLED,
            }:
                request = self._request_from_payload(event.payload["request"])
                prior = requests.get(request.request_id)
                if prior is None:
                    raise ValueError("BCO_PENDING_REQUEST_TRANSITION_WITHOUT_ORIGIN")
                if prior.identity_mapping() != request.identity_mapping():
                    raise ValueError("BCO_PENDING_REQUEST_IDENTITY_CONFLICT")
                requests[request.request_id] = request
        return requests

    def requests(self, mission_id: str) -> tuple[PendingRequest, ...]:
        return tuple(request for _, request in sorted(self._request_projection(mission_id).items()))

    def pending_requests(self, mission_id: str) -> tuple[PendingRequest, ...]:
        return tuple(request for request in self.requests(mission_id) if request.state == "PENDING")

    def request(
        self,
        mission_id: str,
        *,
        step_id: str,
        request_type: str,
        target: str,
        reason: str,
        input_identity: Mapping[str, Any],
        continuation_key: str,
        required_authority: Iterable[str] = (),
        effect_class: str = "READ_ONLY",
        expires_at: str = "",
        request_id: str | None = None,
        created_at: str | None = None,
    ) -> PendingRequest:
        self.engine.project(mission_id)
        effect = str(effect_class).strip().upper()
        input_sha = _digest(dict(input_identity))
        seed = {
            "mission_id": mission_id,
            "step_id": str(step_id).strip(),
            "request_type": str(request_type).strip(),
            "target": str(target).strip(),
            "input_identity_sha256": input_sha,
            "continuation_key": str(continuation_key).strip(),
        }
        req_id = str(request_id).strip() if request_id else f"BCO-REQ-{_digest(seed)[:24].upper()}"
        prior = self._request_projection(mission_id).get(req_id)
        created = prior.created_at if prior is not None else (created_at or _now())
        request = PendingRequest(
            request_id=req_id,
            mission_id=mission_id,
            step_id=str(step_id).strip(),
            request_type=str(request_type).strip(),
            target=str(target).strip(),
            reason=" ".join(str(reason).split()),
            required_authority=_clean(required_authority),
            effect_class=effect,
            created_at=created,
            expires_at=str(expires_at).strip(),
            input_identity_sha256=input_sha,
            continuation_key=str(continuation_key).strip(),
        ).validate()
        if prior is not None:
            if prior.identity_mapping() != request.identity_mapping():
                raise ValueError("BCO_PENDING_REQUEST_IDENTITY_CONFLICT")
            return prior
        self.ledger.append(
            mission_id=mission_id,
            event_type=self.EVENT_REQUEST_PENDING,
            payload={"request": asdict(request)},
            idempotency_key=req_id,
        )
        return request

    def _transition_request(
        self,
        mission_id: str,
        request_id: str,
        *,
        state: str,
        response_ref: str = "",
        response_sha256: str = "",
        proof_refs: Iterable[str] = (),
        transitioned_at: str | None = None,
    ) -> PendingRequest:
        current = self._request_projection(mission_id).get(request_id)
        if current is None:
            raise KeyError(f"BCO_PENDING_REQUEST_UNKNOWN:{request_id}")
        desired = replace(
            current,
            state=state,
            response_ref=str(response_ref).strip(),
            response_sha256=str(response_sha256).strip(),
            proof_refs=_clean(proof_refs),
        ).validate()
        if current.state == state:
            if current == desired:
                return current
            raise ValueError("BCO_PENDING_REQUEST_TRANSITION_CONFLICT")
        if current.state != "PENDING":
            raise ValueError(f"BCO_PENDING_REQUEST_NOT_PENDING:{current.state}")
        event_type = {
            "RESOLVED": self.EVENT_REQUEST_RESOLVED,
            "EXPIRED": self.EVENT_REQUEST_EXPIRED,
            "CANCELLED": self.EVENT_REQUEST_CANCELLED,
        }[state]
        self.ledger.append(
            mission_id=mission_id,
            event_type=event_type,
            payload={"request": asdict(desired), "transitioned_at": transitioned_at or _now()},
            idempotency_key=f"{request_id}:{state}:{desired.response_sha256}:{_digest(desired.proof_refs)}",
        )
        return desired

    def resolve_request(
        self,
        mission_id: str,
        request_id: str,
        *,
        response_ref: str,
        response_sha256: str,
        proof_refs: Iterable[str] = (),
        resolved_at: str | None = None,
    ) -> PendingRequest:
        return self._transition_request(
            mission_id,
            request_id,
            state="RESOLVED",
            response_ref=response_ref,
            response_sha256=response_sha256,
            proof_refs=proof_refs,
            transitioned_at=resolved_at,
        )

    def cancel_request(self, mission_id: str, request_id: str, *, cancelled_at: str | None = None) -> PendingRequest:
        return self._transition_request(
            mission_id,
            request_id,
            state="CANCELLED",
            transitioned_at=cancelled_at,
        )

    def _expire_due_requests(self, mission_id: str, *, now: str) -> tuple[str, ...]:
        current_time = _parse_time(now)
        expired: list[str] = []
        for request in self.pending_requests(mission_id):
            if request.expires_at and _parse_time(request.expires_at) < current_time:
                self._transition_request(
                    mission_id,
                    request.request_id,
                    state="EXPIRED",
                    transitioned_at=now,
                )
                expired.append(request.request_id)
        return tuple(sorted(expired))

    def bind_result(
        self,
        mission_id: str,
        identity: MissionResultIdentity,
        *,
        result_ref: str,
        result_sha256: str,
        proof_refs: tuple[str, ...],
        recorded_at: str,
        now: str,
    ) -> MissionResultLookupReceipt:
        if identity.mission_id != mission_id:
            raise ValueError("BCO_RESULT_MISSION_ID_MISMATCH")
        receipt = self.result_index.record(
            identity,
            result_ref=result_ref,
            result_sha256=result_sha256,
            proof_refs=proof_refs,
            recorded_at=recorded_at,
            now=now,
        )
        self.ledger.append(
            mission_id=mission_id,
            event_type=self.EVENT_RESULT_BOUND,
            payload={
                "cache_key": identity.cache_key,
                "identity": identity.canonical_mapping(),
                "result_ref": receipt.result_ref,
                "result_sha256": receipt.result_sha256,
                "proof_refs": list(receipt.proof_refs),
                "mission_ir_sha256": identity.mission_ir_sha256,
            },
            idempotency_key=f"{identity.cache_key}:{receipt.result_sha256}",
        )
        return receipt

    def _result_identities(self, mission_id: str) -> tuple[MissionResultIdentity, ...]:
        keys = (
            "schema",
            "mission_id",
            "mission_ir_sha256",
            "step_id",
            "source_sha256",
            "input_sha256",
            "policy_sha256",
            "environment_sha256",
            "proof_scope",
            "fresh_until",
            "cache_key",
        )
        identities: dict[str, MissionResultIdentity] = {}
        for event in self.ledger.events(mission_id):
            if event.event_type != self.EVENT_RESULT_BOUND:
                continue
            raw = dict(event.payload["identity"])
            identity = MissionResultIdentity(**{key: raw[key] for key in keys})
            prior = identities.get(identity.cache_key)
            if prior is not None and prior != identity:
                raise ValueError("BCO_RESULT_IDENTITY_CONFLICT")
            identities[identity.cache_key] = identity
        return tuple(identity for _, identity in sorted(identities.items()))

    @staticmethod
    def _projection_mapping(projection: MissionProjection) -> dict[str, Any]:
        return {
            "mission_sha256": projection.mission.mission_sha256,
            "status": projection.status,
            "work_items": {
                work_id: {
                    "status": item.status.value,
                    "result_refs": list(item.result_refs),
                    "dependencies": list(item.dependencies),
                    "shared_state_key": item.shared_state_key,
                }
                for work_id, item in sorted(projection.work_items.items())
            },
            "proof_vector": {
                axis: {
                    "status": entry.status.value,
                    "evidence_refs": list(entry.evidence_refs),
                    "claim_limit": entry.claim_limit,
                }
                for axis, entry in sorted(projection.proof_vector.items())
            },
            "success_evidence": {key: list(value) for key, value in sorted(projection.success_evidence.items())},
            "resolvers": {
                key: {
                    "status": value.status.value,
                    "occurrence_count": value.occurrence_count,
                    "evidence_refs": list(value.evidence_refs),
                }
                for key, value in sorted(projection.resolvers.items())
            },
            "closure_lock": asdict(projection.closure_lock),
            "source_decisions": list(projection.source_decisions),
            "last_event_hash": projection.last_event_hash,
        }

    def _read_checkpoint(self, mission_id: str) -> tuple[MissionCheckpoint | None, str]:
        path = self.checkpoint_path(mission_id)
        if not path.exists():
            return None, "CHECKPOINT_MISSING"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None, "CHECKPOINT_INVALID_JSON"
        if raw.get("schema") != _CHECKPOINT_SCHEMA:
            return None, "CHECKPOINT_SCHEMA_MISMATCH"
        raw = dict(raw)
        raw.pop("schema", None)
        try:
            checkpoint = MissionCheckpoint(**raw).validate()
        except (TypeError, ValueError):
            return None, "CHECKPOINT_INVALID"
        if checkpoint.mission_id != mission_id:
            return None, "CHECKPOINT_MISSION_MISMATCH"
        if checkpoint.runtime_schema_version > self.runtime_schema_version:
            return None, "CHECKPOINT_NEWER_RUNTIME_SCHEMA"
        ledger_hashes = {event.event_hash for event in self.ledger.events()}
        if checkpoint.ledger_head_hash not in ledger_hashes:
            return None, "CHECKPOINT_HEAD_UNKNOWN"
        committed = any(
            event.event_type == self.EVENT_CHECKPOINT_COMMITTED
            and event.payload.get("checkpoint_id") == checkpoint.checkpoint_id
            and event.payload.get("checkpoint_sha256") == checkpoint.checkpoint_sha256
            for event in self.ledger.events(mission_id)
        )
        if not committed:
            return None, "CHECKPOINT_UNCOMMITTED"
        return checkpoint, "CHECKPOINT_VALID"

    def checkpoint(self, mission_id: str, *, trace_id: str = "", created_at: str | None = None) -> MissionCheckpoint:
        verification = self.ledger.verify()
        projection = self.engine.project(mission_id)
        bound = self._bound_event(mission_id)
        requests = self._request_projection(mission_id)
        projection_mapping = self._projection_mapping(projection)
        active = tuple(
            sorted(
                work_id
                for work_id, item in projection.work_items.items()
                if item.status in {WorkStatus.READY, WorkStatus.RUNNING}
            )
        )
        completed = tuple(
            sorted(
                work_id
                for work_id, item in projection.work_items.items()
                if item.status in {WorkStatus.VERIFIED, WorkStatus.SUPERSEDED, WorkStatus.CANCELLED}
            )
        )
        held = tuple(sorted(work_id for work_id, item in projection.work_items.items() if item.status == WorkStatus.HELD))
        pending = tuple(sorted(request_id for request_id, item in requests.items() if item.state == "PENDING"))
        previous, _ = self._read_checkpoint(mission_id)
        body_seed = {
            "mission_id": mission_id,
            "mission_ir_sha256": str(bound.payload["mission_ir_sha256"]),
            "sequence": len(self.ledger.events()),
            "ledger_head_hash": str(verification["head_hash"]),
            "projection_sha256": _digest(projection_mapping),
            "source_frontier": self.source_frontier,
            "policy_sha256": self.policy_sha256,
            "environment_sha256": self.environment_sha256,
            "active_work_ids": active,
            "completed_work_ids": completed,
            "held_work_ids": held,
            "pending_request_ids": pending,
            "bound_result_keys": tuple(identity.cache_key for identity in self._result_identities(mission_id)),
            "proof_state_sha256": _digest(projection_mapping["proof_vector"]),
            "trace_id": str(trace_id).strip(),
            "runtime_schema_version": self.runtime_schema_version,
            "created_at": created_at or _now(),
            "parent_checkpoint_id": previous.checkpoint_id if previous else None,
        }
        checkpoint_id = "BCO-CP-" + _digest(body_seed)[:28].upper()
        candidate = MissionCheckpoint(checkpoint_id=checkpoint_id, checkpoint_sha256="", **body_seed)
        checkpoint = replace(candidate, checkpoint_sha256=_digest(candidate.body())).validate()
        _atomic_write_json(self.checkpoint_path(mission_id), {"schema": _CHECKPOINT_SCHEMA, **asdict(checkpoint)})
        self.ledger.append(
            mission_id=mission_id,
            event_type=self.EVENT_CHECKPOINT_COMMITTED,
            payload={
                "checkpoint_id": checkpoint.checkpoint_id,
                "checkpoint_sha256": checkpoint.checkpoint_sha256,
                "ledger_head_hash": checkpoint.ledger_head_hash,
                "projection_sha256": checkpoint.projection_sha256,
                "runtime_schema_version": checkpoint.runtime_schema_version,
            },
            idempotency_key=checkpoint.checkpoint_id,
        )
        return checkpoint

    def _hold(self, mission_id: str, mission_sha: str, *, state: str, reason: str) -> ResumeReceipt:
        event = self.ledger.append(
            mission_id=mission_id,
            event_type=self.EVENT_RUNTIME_HELD,
            payload={"state": state, "reason": reason},
            idempotency_key=f"{state}:{reason}",
        )
        return ResumeReceipt(
            schema=_SCHEMA,
            state=state,
            mission_id=mission_id,
            mission_ir_sha256=mission_sha,
            ledger_head_hash=event.event_hash,
            reason=reason,
        )

    def resume(self, mission: MissionIR, *, now: str, trace_id: str = "") -> ResumeReceipt:
        normalized = mission.normalized()
        normalized.validate()
        self.ledger.verify()
        bound = self._bound_event(normalized.mission_id)
        bound_ir = dict(bound.payload["mission_ir"])
        bound_source = str(bound.payload["source_frontier"])
        bound_policy = str(bound.payload["policy_sha256"])
        bound_environment = str(bound.payload["environment_sha256"])
        bound_digest = str(bound.payload["mission_ir_sha256"])

        if normalized.source_frontier != bound_source or self.source_frontier != bound_source:
            return self._hold(
                normalized.mission_id,
                normalized.digest(),
                state="HOLD_SOURCE_DRIFT",
                reason=f"expected={bound_source};candidate={normalized.source_frontier};runtime={self.source_frontier}",
            )
        if normalized.digest() != bound_digest or normalized.canonical_mapping() != bound_ir:
            return self._hold(
                normalized.mission_id,
                normalized.digest(),
                state="HOLD_MISSION_IDENTITY_DRIFT",
                reason="MissionIR differs from the bound execution contract.",
            )
        if self.policy_sha256 != bound_policy:
            return self._hold(
                normalized.mission_id,
                normalized.digest(),
                state="HOLD_POLICY_DRIFT",
                reason=f"expected={bound_policy};runtime={self.policy_sha256}",
            )
        if self.environment_sha256 != bound_environment:
            return self._hold(
                normalized.mission_id,
                normalized.digest(),
                state="HOLD_ENVIRONMENT_DRIFT",
                reason=f"expected={bound_environment};runtime={self.environment_sha256}",
            )

        checkpoint, checkpoint_state = self._read_checkpoint(normalized.mission_id)
        if checkpoint_state == "CHECKPOINT_NEWER_RUNTIME_SCHEMA":
            return self._hold(
                normalized.mission_id,
                normalized.digest(),
                state="HOLD_RUNTIME_SCHEMA_NEWER",
                reason=checkpoint_state,
            )

        for identity in self._result_identities(normalized.mission_id):
            result = self.result_index.lookup(identity, now=now)
            if result.state == "HOLD_FRESHNESS_EXPIRED":
                return self._hold(
                    normalized.mission_id,
                    normalized.digest(),
                    state="HOLD_RESULT_FRESHNESS_EXPIRED",
                    reason=identity.cache_key,
                )
            if result.state != "HIT":
                return self._hold(
                    normalized.mission_id,
                    normalized.digest(),
                    state="HOLD_RESULT_NOT_REUSABLE",
                    reason=f"{identity.cache_key}:{result.state}",
                )

        expired = self._expire_due_requests(normalized.mission_id, now=now)
        if expired:
            return self._hold(
                normalized.mission_id,
                normalized.digest(),
                state="HOLD_PENDING_REQUEST_EXPIRED",
                reason=",".join(expired),
            )

        projection = self.engine.project(normalized.mission_id)
        pending = tuple(item.request_id for item in self.pending_requests(normalized.mission_id))
        ready = tuple(item.work_id for item in projection.ready_work_wave())
        if trace_id:
            self.ledger.append(
                mission_id=normalized.mission_id,
                event_type=self.EVENT_TRACE_BOUND,
                payload={"trace_id": str(trace_id).strip()},
                idempotency_key=str(trace_id).strip(),
            )
        state = "RESUMED_EVENT_REPLAY_CHECKPOINT_VALIDATED" if checkpoint else "RESUMED_FROM_EVENT_TRUTH"
        event = self.ledger.append(
            mission_id=normalized.mission_id,
            event_type=self.EVENT_RUNTIME_RESUMED,
            payload={
                "state": state,
                "checkpoint_id": checkpoint.checkpoint_id if checkpoint else "",
                "checkpoint_state": checkpoint_state,
                "pending_request_ids": list(pending),
                "ready_work_ids": list(ready),
                "replayed_from_event_truth": True,
            },
            idempotency_key=f"{state}:{checkpoint.checkpoint_id if checkpoint else checkpoint_state}:{projection.last_event_hash}",
        )
        return ResumeReceipt(
            schema=_SCHEMA,
            state=state,
            mission_id=normalized.mission_id,
            mission_ir_sha256=normalized.digest(),
            ledger_head_hash=event.event_hash,
            checkpoint_id=checkpoint.checkpoint_id if checkpoint else "",
            replayed_from_event_truth=True,
            pending_request_ids=pending,
            ready_work_ids=ready,
            reason=checkpoint_state,
        )

    def verify(self, mission_id: str) -> dict[str, Any]:
        checkpoint, checkpoint_state = self._read_checkpoint(mission_id)
        return {
            "schema": _SCHEMA,
            "mission_id": mission_id,
            "ledger": self.ledger.verify(),
            "result_index": self.result_index.verify(),
            "checkpoint_state": checkpoint_state,
            "checkpoint_id": checkpoint.checkpoint_id if checkpoint else "",
            "provider_effect_authorized": False,
            "financial_effect_authorized": False,
            "publication_authorized": False,
        }

    def close(self, mission_id: str, *, receipt_refs: Iterable[str]) -> dict[str, Any]:
        if self.pending_requests(mission_id):
            raise ValueError("BCO_MISSION_HAS_PENDING_REQUESTS")
        return self.engine.close_mission(mission_id, receipt_refs=receipt_refs)
