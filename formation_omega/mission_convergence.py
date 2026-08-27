"""Formation Ω Mission Convergence Engine (MCE) v1.

Public-safe, provider-neutral convergence primitives. MCE is not a sovereign
authority layer. It coordinates Formation Ω design/challenger decisions and
SOVARA execution around one closure contract, while preserving DPF provenance,
JARVIS independent assurance, CFBE benchmarking and surface-local proof.

No provider credential, external-effect authority or deployment right is
created by this module.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping


PROOF_AXES: tuple[str, ...] = (
    "design",
    "source",
    "installation",
    "identity",
    "authentication",
    "authorization",
    "execution",
    "semantic_proof",
    "independent_proof",
    "resilience",
    "rollback",
    "closure",
)

TERMINAL_WORK_STATUSES = frozenset({"VERIFIED", "SUPERSEDED", "CANCELLED"})
SECRET_FIELDS = frozenset(
    {
        "password",
        "passwd",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "cookie",
        "cookies",
        "authorization_header",
        "client_secret",
        "secret_value",
    }
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha256(value: Any) -> str:
    payload = value if isinstance(value, str) else _canonical_json(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def _assert_public_safe(value: Any, *, path: str = "payload") -> None:
    """Reject obvious secret-bearing fields from public-safe mission records."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).strip().casefold()
            if normalized in SECRET_FIELDS:
                raise ValueError(f"secret-bearing field prohibited at {path}.{key}")
            _assert_public_safe(item, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_public_safe(item, path=f"{path}[{index}]")


class ProofStatus(str, Enum):
    OPEN = "OPEN"
    PARTIAL = "PARTIAL"
    HELD = "HELD"
    PROVEN = "PROVEN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class WorkStatus(str, Enum):
    PLANNED = "PLANNED"
    READY = "READY"
    RUNNING = "RUNNING"
    HELD = "HELD"
    VERIFIED = "VERIFIED"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"


class FailureStatus(str, Enum):
    OPEN = "OPEN"
    MITIGATED = "MITIGATED"
    CLOSED = "CLOSED"


class IdeaPriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class IdeaDisposition(str, Enum):
    INTERRUPT_CLOSURE = "INTERRUPT_CLOSURE"
    PARALLEL_CHALLENGER = "PARALLEL_CHALLENGER"
    IMPROVEMENT_INBOX = "IMPROVEMENT_INBOX"
    FUTURE_BACKLOG = "FUTURE_BACKLOG"


@dataclass(frozen=True)
class MissionSpec:
    """Immutable closure contract compiled from an existing/legacy mission."""

    mission_id: str
    objective: str
    success_criteria: tuple[str, ...]
    authority_ceiling: str = "A1"
    constraints: tuple[str, ...] = ()
    required_proof_axes: tuple[str, ...] = PROOF_AXES
    rollback_required: bool = True
    source_contract_ref: str | None = None
    source_contract_sha256: str | None = None
    mission_sha256: str = ""

    @classmethod
    def create(
        cls,
        *,
        mission_id: str,
        objective: str,
        success_criteria: Iterable[str],
        authority_ceiling: str = "A1",
        constraints: Iterable[str] = (),
        required_proof_axes: Iterable[str] = PROOF_AXES,
        rollback_required: bool = True,
        source_contract_ref: str | None = None,
        source_contract_sha256: str | None = None,
    ) -> "MissionSpec":
        mission_id = str(mission_id).strip()
        objective = " ".join(str(objective).split())
        if not mission_id:
            raise ValueError("mission_id is required")
        if len(objective) < 8:
            raise ValueError("objective is too short")
        criteria = _clean(success_criteria)
        if not criteria:
            raise ValueError("at least one explicit success criterion is required")
        axes = tuple(dict.fromkeys(str(axis).strip() for axis in required_proof_axes if str(axis).strip()))
        unknown = sorted(set(axes) - set(PROOF_AXES))
        if unknown:
            raise ValueError(f"unknown proof axes: {unknown}")
        if rollback_required and "rollback" not in axes:
            axes = tuple((*axes, "rollback"))
        body = {
            "mission_id": mission_id,
            "objective": objective,
            "success_criteria": criteria,
            "authority_ceiling": str(authority_ceiling),
            "constraints": _clean(constraints),
            "required_proof_axes": axes,
            "rollback_required": bool(rollback_required),
            "source_contract_ref": source_contract_ref,
            "source_contract_sha256": source_contract_sha256,
        }
        _assert_public_safe(body)
        return cls(mission_sha256=_sha256(body), **body)

    @classmethod
    def from_legacy_contract(
        cls,
        contract: Mapping[str, Any],
        *,
        required_proof_axes: Iterable[str] = PROOF_AXES,
    ) -> "MissionSpec":
        """Reuse the repository's existing MissionContract identity and semantics."""

        required = ("mission_id", "objective", "success_criteria", "authority_ceiling", "contract_sha256")
        missing = [key for key in required if key not in contract]
        if missing:
            raise ValueError(f"legacy mission contract missing: {missing}")
        return cls.create(
            mission_id=str(contract["mission_id"]),
            objective=str(contract["objective"]),
            success_criteria=tuple(contract["success_criteria"]),
            authority_ceiling=str(contract["authority_ceiling"]),
            constraints=tuple(contract.get("constraints", ())),
            required_proof_axes=required_proof_axes,
            rollback_required=bool(contract.get("rollback_required", True)),
            source_contract_ref="FEDERATION_OMEGA_V2_MISSION_CONTRACT",
            source_contract_sha256=str(contract["contract_sha256"]),
        )


@dataclass(frozen=True)
class WorkItem:
    work_id: str
    lane: str
    objective: str
    dependencies: tuple[str, ...] = ()
    shared_state_key: str | None = None
    status: WorkStatus = WorkStatus.PLANNED
    idempotency_key: str = ""
    result_refs: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        work_id: str,
        lane: str,
        objective: str,
        dependencies: Iterable[str] = (),
        shared_state_key: str | None = None,
        status: WorkStatus = WorkStatus.PLANNED,
        result_refs: Iterable[str] = (),
    ) -> "WorkItem":
        body = {
            "work_id": str(work_id).strip(),
            "lane": str(lane).strip(),
            "objective": " ".join(str(objective).split()),
            "dependencies": _clean(dependencies),
            "shared_state_key": str(shared_state_key).strip() if shared_state_key else None,
        }
        if not all((body["work_id"], body["lane"], body["objective"])):
            raise ValueError("work_id, lane and objective are required")
        _assert_public_safe(body)
        return cls(
            **body,
            status=WorkStatus(status),
            idempotency_key=f"WORK-{_sha256(body)[:24].upper()}",
            result_refs=_clean(result_refs),
        )


@dataclass(frozen=True)
class ProofEntry:
    axis: str
    status: ProofStatus
    evidence_refs: tuple[str, ...] = ()
    claim_limit: str = ""
    observed_at: str = ""

    @classmethod
    def create(
        cls,
        *,
        axis: str,
        status: ProofStatus,
        evidence_refs: Iterable[str] = (),
        claim_limit: str = "",
        observed_at: str | None = None,
    ) -> "ProofEntry":
        if axis not in PROOF_AXES:
            raise ValueError(f"unknown proof axis: {axis}")
        status = ProofStatus(status)
        refs = _clean(evidence_refs)
        if status == ProofStatus.PROVEN and not refs:
            raise ValueError("PROVEN proof entry requires evidence_refs")
        return cls(
            axis=axis,
            status=status,
            evidence_refs=refs,
            claim_limit=" ".join(str(claim_limit).split()),
            observed_at=observed_at or _now(),
        )


@dataclass(frozen=True)
class FailureResolver:
    resolver_id: str
    fingerprint: str
    exact_gap: str
    diagnosis: str
    immediate_workaround: str
    permanent_fix: str
    alternate_route: str
    retry_condition: str
    proof_test: str
    closure_test: str
    status: FailureStatus = FailureStatus.OPEN
    occurrence_count: int = 1
    evidence_refs: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        fingerprint: str,
        exact_gap: str,
        diagnosis: str,
        immediate_workaround: str,
        permanent_fix: str,
        alternate_route: str,
        retry_condition: str,
        proof_test: str,
        closure_test: str,
        evidence_refs: Iterable[str] = (),
    ) -> "FailureResolver":
        fingerprint = " ".join(str(fingerprint).split())
        if len(fingerprint) < 6:
            raise ValueError("failure fingerprint is too short")
        body = {
            "fingerprint": fingerprint,
            "exact_gap": " ".join(str(exact_gap).split()),
            "diagnosis": " ".join(str(diagnosis).split()),
            "immediate_workaround": " ".join(str(immediate_workaround).split()),
            "permanent_fix": " ".join(str(permanent_fix).split()),
            "alternate_route": " ".join(str(alternate_route).split()),
            "retry_condition": " ".join(str(retry_condition).split()),
            "proof_test": " ".join(str(proof_test).split()),
            "closure_test": " ".join(str(closure_test).split()),
        }
        if any(not value for value in body.values()):
            raise ValueError("resolver fields must be non-empty")
        _assert_public_safe(body)
        digest = _sha256({"fingerprint": fingerprint.casefold()})
        return cls(
            resolver_id=f"RESOLVER-{digest[:24].upper()}",
            evidence_refs=_clean(evidence_refs),
            **body,
        )


@dataclass(frozen=True)
class ClosureLock:
    active: bool
    target: str
    p0_interrupt_only: bool = True
    opened_at: str = field(default_factory=_now)

    def disposition(self, priority: IdeaPriority) -> IdeaDisposition:
        priority = IdeaPriority(priority)
        if not self.active:
            return IdeaDisposition.PARALLEL_CHALLENGER
        if priority == IdeaPriority.P0:
            return IdeaDisposition.INTERRUPT_CLOSURE
        if priority == IdeaPriority.P1:
            return IdeaDisposition.PARALLEL_CHALLENGER
        if priority == IdeaPriority.P2:
            return IdeaDisposition.IMPROVEMENT_INBOX
        return IdeaDisposition.FUTURE_BACKLOG


@dataclass(frozen=True)
class MissionEvent:
    event_id: str
    mission_id: str
    event_type: str
    occurred_at: str
    payload: dict[str, Any]
    previous_event_hash: str | None
    event_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConvergenceLedger:
    """Append-only JSONL mission ledger with an integrity hash chain."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else None
        self._events: list[MissionEvent] = []
        self._ids: dict[str, str] = {}
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists():
                self._load()

    def _load(self) -> None:
        previous_hash: str | None = None
        for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            raw = json.loads(line)
            event = MissionEvent(**raw)
            expected = self._expected_hash(
                event_id=event.event_id,
                mission_id=event.mission_id,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
                payload=event.payload,
                previous_event_hash=previous_hash,
            )
            if event.previous_event_hash != previous_hash or event.event_hash != expected:
                raise ValueError(f"MCE_LEDGER_HASH_MISMATCH:{line_number}")
            prior = self._ids.get(event.event_id)
            if prior is not None and prior != event.event_hash:
                raise ValueError(f"MCE_EVENT_ID_CONFLICT:{event.event_id}")
            if prior is None:
                self._events.append(event)
                self._ids[event.event_id] = event.event_hash
            previous_hash = event.event_hash

    @staticmethod
    def _expected_hash(
        *,
        event_id: str,
        mission_id: str,
        event_type: str,
        occurred_at: str,
        payload: Mapping[str, Any],
        previous_event_hash: str | None,
    ) -> str:
        body = {
            "event_id": event_id,
            "mission_id": mission_id,
            "event_type": event_type,
            "occurred_at": occurred_at,
            "payload": dict(payload),
            "previous_event_hash": previous_event_hash,
        }
        return _sha256(body)

    @staticmethod
    def _event_id(mission_id: str, event_type: str, payload: Mapping[str, Any], idempotency_key: str | None) -> str:
        seed = {
            "mission_id": mission_id,
            "event_type": event_type,
            "payload": dict(payload),
            "idempotency_key": idempotency_key or "",
        }
        return f"MCE-EVT-{_sha256(seed)[:28].upper()}"

    def append(
        self,
        *,
        mission_id: str,
        event_type: str,
        payload: Mapping[str, Any],
        idempotency_key: str | None = None,
        occurred_at: str | None = None,
    ) -> MissionEvent:
        payload = json.loads(_canonical_json(dict(payload)))
        _assert_public_safe(payload)
        event_id = self._event_id(mission_id, event_type, payload, idempotency_key)
        existing_hash = self._ids.get(event_id)
        if existing_hash is not None:
            return next(event for event in self._events if event.event_id == event_id)
        occurred_at = occurred_at or _now()
        previous = self._events[-1].event_hash if self._events else None
        event_hash = self._expected_hash(
            event_id=event_id,
            mission_id=mission_id,
            event_type=event_type,
            occurred_at=occurred_at,
            payload=payload,
            previous_event_hash=previous,
        )
        event = MissionEvent(
            event_id=event_id,
            mission_id=mission_id,
            event_type=event_type,
            occurred_at=occurred_at,
            payload=payload,
            previous_event_hash=previous,
            event_hash=event_hash,
        )
        if self.path is not None:
            rendered = _canonical_json(event.to_dict())
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(rendered + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        self._events.append(event)
        self._ids[event_id] = event_hash
        return event

    def events(self, mission_id: str | None = None) -> tuple[MissionEvent, ...]:
        if mission_id is None:
            return tuple(self._events)
        return tuple(event for event in self._events if event.mission_id == mission_id)

    def verify(self) -> dict[str, Any]:
        previous: str | None = None
        for index, event in enumerate(self._events, start=1):
            expected = self._expected_hash(
                event_id=event.event_id,
                mission_id=event.mission_id,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
                payload=event.payload,
                previous_event_hash=previous,
            )
            if event.previous_event_hash != previous or event.event_hash != expected:
                raise ValueError(f"MCE_LEDGER_HASH_MISMATCH:{index}")
            previous = event.event_hash
        return {"state": "VERIFIED", "event_count": len(self._events), "head_hash": previous}


@dataclass(frozen=True)
class MissionProjection:
    mission: MissionSpec
    status: str
    work_items: Mapping[str, WorkItem]
    proof_vector: Mapping[str, ProofEntry]
    success_evidence: Mapping[str, tuple[str, ...]]
    resolvers: Mapping[str, FailureResolver]
    closure_lock: ClosureLock
    source_decisions: tuple[dict[str, Any], ...]
    last_event_hash: str | None

    @property
    def open_p0_failures(self) -> tuple[FailureResolver, ...]:
        return tuple(item for item in self.resolvers.values() if item.status == FailureStatus.OPEN)

    def ready_work_wave(self) -> tuple[WorkItem, ...]:
        complete = {work_id for work_id, item in self.work_items.items() if item.status.value in TERMINAL_WORK_STATUSES}
        candidates = [
            item
            for item in self.work_items.values()
            if item.status in {WorkStatus.PLANNED, WorkStatus.READY}
            and set(item.dependencies).issubset(complete)
        ]
        selected: list[WorkItem] = []
        used_shared_keys: set[str] = set()
        for item in sorted(candidates, key=lambda x: (x.lane, x.work_id)):
            if item.shared_state_key:
                if item.shared_state_key in used_shared_keys:
                    continue
                used_shared_keys.add(item.shared_state_key)
            selected.append(replace(item, status=WorkStatus.READY))
        return tuple(selected)

    def closure_gaps(self) -> tuple[str, ...]:
        gaps: list[str] = []
        for criterion in self.mission.success_criteria:
            if not self.success_evidence.get(criterion):
                gaps.append(f"SUCCESS:{criterion}")
        for axis in self.mission.required_proof_axes:
            entry = self.proof_vector.get(axis)
            if entry is None or entry.status not in {ProofStatus.PROVEN, ProofStatus.NOT_APPLICABLE}:
                gaps.append(f"PROOF:{axis}")
        if self.mission.rollback_required:
            rollback = self.proof_vector.get("rollback")
            if rollback is None or rollback.status != ProofStatus.PROVEN:
                gaps.append("ROLLBACK:required")
        if self.open_p0_failures:
            gaps.extend(f"FAILURE:{item.resolver_id}" for item in self.open_p0_failures)
        unfinished = [item.work_id for item in self.work_items.values() if item.status.value not in TERMINAL_WORK_STATUSES]
        gaps.extend(f"WORK:{work_id}" for work_id in sorted(unfinished))
        return tuple(dict.fromkeys(gaps))

    @property
    def closable(self) -> bool:
        return not self.closure_gaps()


class MissionConvergenceEngine:
    EVENT_MISSION_OPENED = "MISSION_OPENED"
    EVENT_WORK_ITEM_SET = "WORK_ITEM_SET"
    EVENT_PROOF_UPDATED = "PROOF_UPDATED"
    EVENT_SUCCESS_VERIFIED = "SUCCESS_VERIFIED"
    EVENT_FAILURE_SET = "FAILURE_SET"
    EVENT_CLOSURE_LOCK_SET = "CLOSURE_LOCK_SET"
    EVENT_SOURCE_DECISION = "SOURCE_DECISION"
    EVENT_MISSION_CLOSED = "MISSION_CLOSED"

    def __init__(self, ledger: ConvergenceLedger | None = None):
        self.ledger = ledger or ConvergenceLedger()

    def open_mission(self, mission: MissionSpec, *, closure_target: str | None = None) -> MissionProjection:
        self.ledger.append(
            mission_id=mission.mission_id,
            event_type=self.EVENT_MISSION_OPENED,
            payload={"mission": asdict(mission)},
            idempotency_key=mission.mission_sha256,
        )
        target = closure_target or f"Close mission: {mission.objective}"
        self.set_closure_lock(mission.mission_id, active=True, target=target)
        return self.project(mission.mission_id)

    def set_work_item(self, mission_id: str, item: WorkItem) -> MissionProjection:
        self._require_mission(mission_id)
        self.ledger.append(
            mission_id=mission_id,
            event_type=self.EVENT_WORK_ITEM_SET,
            payload={"work_item": asdict(item)},
            idempotency_key=f"{item.work_id}:{item.status.value}:{_sha256(asdict(item))}",
        )
        return self.project(mission_id)

    def update_work_status(self, mission_id: str, work_id: str, status: WorkStatus, *, result_refs: Iterable[str] = ()) -> MissionProjection:
        projection = self.project(mission_id)
        current = projection.work_items.get(work_id)
        if current is None:
            raise KeyError(f"unknown work item: {work_id}")
        updated = replace(current, status=WorkStatus(status), result_refs=_clean((*current.result_refs, *result_refs)))
        return self.set_work_item(mission_id, updated)

    def update_proof(self, mission_id: str, entry: ProofEntry) -> MissionProjection:
        self._require_mission(mission_id)
        self.ledger.append(
            mission_id=mission_id,
            event_type=self.EVENT_PROOF_UPDATED,
            payload={"proof": asdict(entry)},
            idempotency_key=f"{entry.axis}:{entry.status.value}:{_sha256(asdict(entry))}",
        )
        return self.project(mission_id)

    def verify_success(self, mission_id: str, criterion: str, *, evidence_refs: Iterable[str]) -> MissionProjection:
        projection = self.project(mission_id)
        criterion = " ".join(str(criterion).split())
        if criterion not in projection.mission.success_criteria:
            raise ValueError("criterion is not in the mission contract")
        refs = _clean(evidence_refs)
        if not refs:
            raise ValueError("success verification requires evidence")
        self.ledger.append(
            mission_id=mission_id,
            event_type=self.EVENT_SUCCESS_VERIFIED,
            payload={"criterion": criterion, "evidence_refs": refs},
            idempotency_key=f"{criterion}:{_sha256(refs)}",
        )
        return self.project(mission_id)

    def record_failure(self, mission_id: str, resolver: FailureResolver) -> MissionProjection:
        projection = self.project(mission_id)
        prior = projection.resolvers.get(resolver.resolver_id)
        if prior:
            resolver = replace(
                resolver,
                occurrence_count=prior.occurrence_count + 1,
                evidence_refs=_clean((*prior.evidence_refs, *resolver.evidence_refs)),
                status=prior.status if prior.status == FailureStatus.CLOSED else resolver.status,
            )
        self.ledger.append(
            mission_id=mission_id,
            event_type=self.EVENT_FAILURE_SET,
            payload={"resolver": asdict(resolver)},
            idempotency_key=f"{resolver.resolver_id}:{resolver.occurrence_count}:{resolver.status.value}",
        )
        return self.project(mission_id)

    def set_failure_status(self, mission_id: str, resolver_id: str, status: FailureStatus, *, evidence_refs: Iterable[str] = ()) -> MissionProjection:
        projection = self.project(mission_id)
        resolver = projection.resolvers.get(resolver_id)
        if resolver is None:
            raise KeyError(f"unknown resolver: {resolver_id}")
        updated = replace(resolver, status=FailureStatus(status), evidence_refs=_clean((*resolver.evidence_refs, *evidence_refs)))
        self.ledger.append(
            mission_id=mission_id,
            event_type=self.EVENT_FAILURE_SET,
            payload={"resolver": asdict(updated)},
            idempotency_key=f"{updated.resolver_id}:{updated.occurrence_count}:{updated.status.value}:{_sha256(updated.evidence_refs)}",
        )
        return self.project(mission_id)

    def set_closure_lock(self, mission_id: str, *, active: bool, target: str) -> MissionProjection:
        self._require_mission(mission_id)
        lock = ClosureLock(active=bool(active), target=" ".join(str(target).split()))
        self.ledger.append(
            mission_id=mission_id,
            event_type=self.EVENT_CLOSURE_LOCK_SET,
            payload={"closure_lock": asdict(lock)},
            idempotency_key=f"{lock.active}:{lock.target}",
        )
        return self.project(mission_id)

    def idea_disposition(self, mission_id: str, priority: IdeaPriority) -> IdeaDisposition:
        return self.project(mission_id).closure_lock.disposition(priority)

    def record_source_decision(self, mission_id: str, decision: Mapping[str, Any]) -> MissionProjection:
        self._require_mission(mission_id)
        decision = json.loads(_canonical_json(dict(decision)))
        _assert_public_safe(decision)
        self.ledger.append(
            mission_id=mission_id,
            event_type=self.EVENT_SOURCE_DECISION,
            payload={"decision": decision},
            idempotency_key=_sha256(decision),
        )
        return self.project(mission_id)

    def close_mission(self, mission_id: str, *, receipt_refs: Iterable[str]) -> dict[str, Any]:
        projection = self.project(mission_id)
        gaps = projection.closure_gaps()
        if gaps:
            raise ValueError(f"MISSION_NOT_CLOSABLE:{'|'.join(gaps)}")
        refs = _clean(receipt_refs)
        if not refs:
            raise ValueError("closure requires receipt_refs")
        body = {
            "mission_id": mission_id,
            "mission_sha256": projection.mission.mission_sha256,
            "success_evidence": dict(projection.success_evidence),
            "proof_vector": {axis: asdict(entry) for axis, entry in sorted(projection.proof_vector.items())},
            "receipt_refs": refs,
            "last_preclosure_event_hash": projection.last_event_hash,
        }
        receipt_sha = _sha256(body)
        self.ledger.append(
            mission_id=mission_id,
            event_type=self.EVENT_MISSION_CLOSED,
            payload={"closure_receipt": {**body, "closure_receipt_sha256": receipt_sha}},
            idempotency_key=receipt_sha,
        )
        return {**body, "closure_receipt_sha256": receipt_sha, "state": "CLOSED_VERIFIED"}

    def _require_mission(self, mission_id: str) -> MissionSpec:
        for event in self.ledger.events(mission_id):
            if event.event_type == self.EVENT_MISSION_OPENED:
                return MissionSpec(**event.payload["mission"])
        raise KeyError(f"unknown mission: {mission_id}")

    def project(self, mission_id: str) -> MissionProjection:
        events = self.ledger.events(mission_id)
        mission: MissionSpec | None = None
        work_items: dict[str, WorkItem] = {}
        proof: dict[str, ProofEntry] = {axis: ProofEntry(axis=axis, status=ProofStatus.OPEN) for axis in PROOF_AXES}
        success_evidence: dict[str, tuple[str, ...]] = {}
        resolvers: dict[str, FailureResolver] = {}
        closure_lock = ClosureLock(active=False, target="")
        source_decisions: list[dict[str, Any]] = []
        status = "OPEN"
        for event in events:
            payload = event.payload
            if event.event_type == self.EVENT_MISSION_OPENED:
                mission = MissionSpec(**payload["mission"])
            elif event.event_type == self.EVENT_WORK_ITEM_SET:
                raw = dict(payload["work_item"])
                raw["status"] = WorkStatus(raw["status"])
                work_items[raw["work_id"]] = WorkItem(**raw)
            elif event.event_type == self.EVENT_PROOF_UPDATED:
                raw = dict(payload["proof"])
                raw["status"] = ProofStatus(raw["status"])
                proof[raw["axis"]] = ProofEntry(**raw)
            elif event.event_type == self.EVENT_SUCCESS_VERIFIED:
                success_evidence[str(payload["criterion"])] = tuple(payload["evidence_refs"])
            elif event.event_type == self.EVENT_FAILURE_SET:
                raw = dict(payload["resolver"])
                raw["status"] = FailureStatus(raw["status"])
                resolvers[raw["resolver_id"]] = FailureResolver(**raw)
            elif event.event_type == self.EVENT_CLOSURE_LOCK_SET:
                closure_lock = ClosureLock(**payload["closure_lock"])
            elif event.event_type == self.EVENT_SOURCE_DECISION:
                source_decisions.append(dict(payload["decision"]))
            elif event.event_type == self.EVENT_MISSION_CLOSED:
                status = "CLOSED_VERIFIED"
        if mission is None:
            raise KeyError(f"unknown mission: {mission_id}")
        return MissionProjection(
            mission=mission,
            status=status,
            work_items=work_items,
            proof_vector=proof,
            success_evidence=success_evidence,
            resolvers=resolvers,
            closure_lock=closure_lock,
            source_decisions=tuple(source_decisions),
            last_event_hash=events[-1].event_hash if events else None,
        )
