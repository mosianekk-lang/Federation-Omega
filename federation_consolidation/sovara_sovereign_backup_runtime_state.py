"""Durable state, event ordering, and recovery decisions for SOVARA backups.

This module owns the compact runtime state machine: event validation, hash-linked
learning history, strict sequence selection, leases, retry timing, and artifact
set binding. It performs no provider effect and contains no private provider
pointer or credential.
"""
from __future__ import annotations
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence
from .sovara_sovereign_backup import ArtifactInput, BackupError, BackupEventType, IdempotencyLedger, reject_secret_metadata
RUNTIME_SCHEMA = 'SOVARA-SOVEREIGN-BACKUP-RUNTIME-1'
RUNTIME_VERSION = '1.0.0'
DEFAULT_DESTINATION_ALIAS = 'SOVARA_PRIVATE_BACKUP_REPOSITORY_V1'
GENESIS = 'GENESIS'
_HEX64 = frozenset('0123456789abcdef')

class RuntimeDecisionState(StrEnum):
    PROCESS = 'PROCESS'
    NO_EVENT = 'NO_EVENT'
    NOT_DUE = 'NOT_DUE'
    RETRY_NOT_DUE = 'RETRY_NOT_DUE'
    ACTIVE_LEASE = 'ACTIVE_LEASE'
    HELD_SEQUENCE_GAP = 'HELD_SEQUENCE_GAP'
    ALREADY_COMPLETED_EXACT = 'ALREADY_COMPLETED_EXACT'
    STATE_RACE_RETRY = 'STATE_RACE_RETRY'
    SUCCEEDED = 'SUCCEEDED'
    MISSED_RUN_RECOVERED = 'MISSED_RUN_RECOVERED'
    PROVIDER_RECEIPT_RECOVERED = 'PROVIDER_RECEIPT_RECOVERED'
    RETRY_SCHEDULED = 'RETRY_SCHEDULED'
    DEAD_LETTER = 'DEAD_LETTER'
    PROVIDER_EFFECT_STATE_RECONCILIATION_REQUIRED = 'PROVIDER_EFFECT_STATE_RECONCILIATION_REQUIRED'

@dataclass(frozen=True)
class BackupRuntimeEvent:
    sequence: int
    event_type: str
    event_id: str
    detected_at: str
    due_at: str
    source_identity: str
    source_version: str
    artifact_set_sha256: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> 'BackupRuntimeEvent':
        if not isinstance(value, Mapping):
            raise BackupError('runtime event must be an object')
        try:
            event_type = BackupEventType(str(value.get('event_type'))).value
        except ValueError as exc:
            raise BackupError('runtime event type is unsupported') from exc
        event = cls(sequence=int(value.get('sequence') or 0), event_type=event_type, event_id=str(value.get('event_id') or '').strip(), detected_at=normalise_time(str(value.get('detected_at') or '')), due_at=normalise_time(str(value.get('due_at') or '')), source_identity=str(value.get('source_identity') or '').strip(), source_version=str(value.get('source_version') or '').strip(), artifact_set_sha256=require_sha256(str(value.get('artifact_set_sha256') or ''), 'artifact_set_sha256'), metadata=dict(value.get('metadata') or {}))
        if event.sequence < 1:
            raise BackupError('runtime event sequence must be positive')
        if not event.event_id or len(event.event_id) > 192:
            raise BackupError('runtime event_id is missing or too long')
        if not event.source_identity or not event.source_version:
            raise BackupError('runtime source identity and version are required')
        reject_secret_metadata(event.payload(), 'runtime_event')
        return event

    def payload(self) -> Mapping[str, Any]:
        return {'sequence': self.sequence, 'event_type': self.event_type, 'event_id': self.event_id, 'detected_at': self.detected_at, 'due_at': self.due_at, 'source_identity': self.source_identity, 'source_version': self.source_version, 'artifact_set_sha256': self.artifact_set_sha256, 'metadata': dict(self.metadata)}

    @property
    def payload_sha256(self) -> str:
        return _sha256_json(self.payload())

@dataclass(frozen=True)
class RuntimeDecision:
    state: RuntimeDecisionState
    event: BackupRuntimeEvent | None = None
    missed_run: bool = False
    expired_lease_recovery: bool = False
    exact_duplicate_count: int = 0
    missing_sequence: int | None = None
    retry_at: str | None = None
    lease_owner: str | None = None

    def as_mapping(self) -> Mapping[str, Any]:
        return {'state': self.state.value, 'event': self.event.payload() if self.event else None, 'missed_run': self.missed_run, 'expired_lease_recovery': self.expired_lease_recovery, 'exact_duplicate_count': self.exact_duplicate_count, 'missing_sequence': self.missing_sequence, 'retry_at': self.retry_at, 'lease_owner': self.lease_owner}

@dataclass(frozen=True)
class RuntimeState:
    state_version: int = 0
    last_sequence: int = 0
    last_manifest: Mapping[str, Any] | None = None
    last_manifest_sha256: str | None = None
    last_receipt_sha256: str | None = None
    idempotency_events: tuple[Mapping[str, Any], ...] = ()
    completed_events: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    attempts: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    current_lease: Mapping[str, Any] | None = None
    runtime_anchor_hash: str = GENESIS
    runtime_event_counter: int = 0
    runtime_events: tuple[Mapping[str, Any], ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> 'RuntimeState':
        if value is None:
            return cls()
        if value.get('schema') != RUNTIME_SCHEMA:
            raise BackupError('runtime state schema is unsupported')
        if str(value.get('version')) != RUNTIME_VERSION:
            raise BackupError('runtime state version is unsupported')
        state = cls(state_version=int(value.get('state_version') or 0), last_sequence=int(value.get('last_sequence') or 0), last_manifest=dict(value['last_manifest']) if isinstance(value.get('last_manifest'), Mapping) else None, last_manifest_sha256=require_sha256(str(value['last_manifest_sha256']), 'last_manifest_sha256') if value.get('last_manifest_sha256') else None, last_receipt_sha256=require_sha256(str(value['last_receipt_sha256']), 'last_receipt_sha256') if value.get('last_receipt_sha256') else None, idempotency_events=tuple((dict(item) for item in value.get('idempotency_events') or ())), completed_events={str(key): dict(item) for key, item in dict(value.get('completed_events') or {}).items()}, attempts={str(key): dict(item) for key, item in dict(value.get('attempts') or {}).items()}, current_lease=dict(value['current_lease']) if isinstance(value.get('current_lease'), Mapping) else None, runtime_anchor_hash=str(value.get('runtime_anchor_hash') or GENESIS), runtime_event_counter=int(value.get('runtime_event_counter') or 0), runtime_events=tuple((dict(item) for item in value.get('runtime_events') or ())))
        verify_runtime_state(state)
        return state

    def to_mapping(self) -> Mapping[str, Any]:
        return {'schema': RUNTIME_SCHEMA, 'version': RUNTIME_VERSION, 'state_version': self.state_version, 'last_sequence': self.last_sequence, 'last_manifest': dict(self.last_manifest) if self.last_manifest else None, 'last_manifest_sha256': self.last_manifest_sha256, 'last_receipt_sha256': self.last_receipt_sha256, 'idempotency_events': [dict(item) for item in self.idempotency_events], 'completed_events': {key: dict(item) for key, item in self.completed_events.items()}, 'attempts': {key: dict(item) for key, item in self.attempts.items()}, 'current_lease': dict(self.current_lease) if self.current_lease else None, 'runtime_anchor_hash': self.runtime_anchor_hash, 'runtime_event_counter': self.runtime_event_counter, 'runtime_events': [dict(item) for item in self.runtime_events]}

def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode('utf-8')

def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def _sha256_json(value: Any) -> str:
    return sha256_bytes(_canonical_json(value))

def require_sha256(value: str, name: str) -> str:
    normalized = str(value).strip().lower()
    if len(normalized) != 64 or any((character not in _HEX64 for character in normalized)):
        raise BackupError(f'{name} must be a lowercase SHA-256')
    return normalized

def parse_time(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except ValueError as exc:
            raise BackupError('runtime timestamp must be ISO-8601') from exc
    if parsed.tzinfo is None:
        raise BackupError('runtime timestamp must include a timezone')
    return parsed.astimezone(UTC)

def normalise_time(value: str | datetime) -> str:
    return parse_time(value).replace(microsecond=0).isoformat().replace('+00:00', 'Z')

def artifact_set_sha256(artifacts: Iterable[ArtifactInput]) -> str:
    records: list[Mapping[str, Any]] = []
    names: set[str] = set()
    for artifact in artifacts:
        name = str(artifact.logical_name).strip()
        if not name or name in names:
            raise BackupError('runtime artifact logical names must be unique')
        names.add(name)
        record = {'logical_name': name, 'sha256': sha256_bytes(bytes(artifact.content)), 'size_bytes': len(artifact.content), 'media_type': str(artifact.media_type), 'classification': str(artifact.classification.value), 'source_ref': str(artifact.source_ref), 'email_eligible': bool(artifact.email_eligible)}
        reject_secret_metadata(record, 'runtime_artifact_metadata')
        records.append(record)
    if not records:
        raise BackupError('runtime event requires at least one artifact')
    return _sha256_json(sorted(records, key=lambda item: str(item['logical_name'])))

def verify_runtime_event_chain(state: RuntimeState) -> bool:
    previous = state.runtime_anchor_hash
    last_ordinal = 0
    for event in state.runtime_events:
        body = {'ordinal': event.get('ordinal'), 'kind': event.get('kind'), 'event_id': event.get('event_id'), 'occurred_at': event.get('occurred_at'), 'payload': event.get('payload'), 'previous_hash': event.get('previous_hash')}
        ordinal = int(body['ordinal'] or 0)
        if ordinal <= last_ordinal or body['previous_hash'] != previous:
            return False
        expected = _sha256_json(body)
        if event.get('event_hash') != expected:
            return False
        previous = expected
        last_ordinal = ordinal
    if state.runtime_events and state.runtime_event_counter < last_ordinal:
        return False
    return True

def verify_runtime_state(state: RuntimeState) -> bool:
    if state.state_version < 0 or state.last_sequence < 0:
        raise BackupError('runtime state versions may not be negative')
    if state.last_manifest is None:
        if state.last_sequence != 0 or state.last_manifest_sha256 is not None:
            raise BackupError('runtime state has sequence/hash without a manifest')
    else:
        calculated = _sha256_json(state.last_manifest)
        if calculated != state.last_manifest_sha256:
            raise BackupError('runtime last-manifest SHA-256 mismatch')
        if int(state.last_manifest.get('sequence') or 0) != state.last_sequence:
            raise BackupError('runtime last-manifest sequence mismatch')
    IdempotencyLedger(state.idempotency_events)
    for event_id, record in state.completed_events.items():
        if str(record.get('event_id')) != event_id:
            raise BackupError('runtime completed-event key mismatch')
        require_sha256(str(record.get('event_payload_sha256') or ''), 'event_payload_sha256')
        if int(record.get('sequence') or 0) > state.last_sequence:
            raise BackupError('completed event exceeds the last committed sequence')
    if state.current_lease:
        require_sha256(str(state.current_lease.get('event_payload_sha256') or ''), 'lease event_payload_sha256')
        parse_time(str(state.current_lease.get('expires_at') or ''))
    if not verify_runtime_event_chain(state):
        raise BackupError('runtime event hash chain is invalid')
    reject_secret_metadata(state.to_mapping(), 'runtime_state')
    return True

def append_runtime_event(state: RuntimeState, *, kind: str, event_id: str, occurred_at: str, payload: Mapping[str, Any], max_events: int=128) -> RuntimeState:
    if max_events < 8:
        raise BackupError('runtime event window must retain at least eight events')
    reject_secret_metadata(payload, 'runtime_learning_event')
    previous = str(state.runtime_events[-1]['event_hash']) if state.runtime_events else state.runtime_anchor_hash
    ordinal = state.runtime_event_counter + 1
    body = {'ordinal': ordinal, 'kind': str(kind), 'event_id': str(event_id), 'occurred_at': normalise_time(occurred_at), 'payload': dict(payload), 'previous_hash': previous}
    event = body | {'event_hash': _sha256_json(body)}
    events = [dict(item) for item in state.runtime_events] + [event]
    anchor = state.runtime_anchor_hash
    if len(events) > max_events:
        drop_count = len(events) - max_events
        anchor = str(events[drop_count - 1]['event_hash'])
        events = events[drop_count:]
    result = replace(state, runtime_anchor_hash=anchor, runtime_event_counter=ordinal, runtime_events=tuple(events))
    if not verify_runtime_event_chain(result):
        raise BackupError('runtime event append broke the hash chain')
    return result

def _normalise_events(state: RuntimeState, values: Sequence[Mapping[str, Any]]) -> tuple[list[BackupRuntimeEvent], int]:
    by_sequence: dict[int, BackupRuntimeEvent] = {}
    by_event_id: dict[str, BackupRuntimeEvent] = {}
    exact_duplicates = 0
    pending: list[BackupRuntimeEvent] = []
    for value in values:
        event = BackupRuntimeEvent.from_mapping(value)
        prior_sequence = by_sequence.get(event.sequence)
        if prior_sequence:
            if prior_sequence.payload_sha256 != event.payload_sha256:
                raise BackupError('multiple runtime events claim the same sequence')
            exact_duplicates += 1
            continue
        prior_id = by_event_id.get(event.event_id)
        if prior_id:
            if prior_id.payload_sha256 != event.payload_sha256:
                raise BackupError('runtime event_id collision with changed payload')
            exact_duplicates += 1
            continue
        by_sequence[event.sequence] = event
        by_event_id[event.event_id] = event
        completed = state.completed_events.get(event.event_id)
        if completed:
            if completed.get('event_payload_sha256') != event.payload_sha256:
                raise BackupError('completed runtime event reappeared with changed payload')
            exact_duplicates += 1
            continue
        if event.sequence <= state.last_sequence:
            raise BackupError('unrecorded event sequence is behind committed runtime state')
        pending.append(event)
    pending.sort(key=lambda item: (item.sequence, item.event_id))
    return (pending, exact_duplicates)

def select_next_event(state: RuntimeState, events: Sequence[Mapping[str, Any]], *, now: datetime | str, worker_id: str, missed_grace_seconds: int=60) -> RuntimeDecision:
    verify_runtime_state(state)
    current = parse_time(now)
    worker = str(worker_id).strip()
    if not worker:
        raise BackupError('worker_id is required')
    if missed_grace_seconds < 0:
        raise BackupError('missed_grace_seconds may not be negative')
    pending, exact_duplicates = _normalise_events(state, events)
    if not pending:
        return RuntimeDecision(state=RuntimeDecisionState.ALREADY_COMPLETED_EXACT if exact_duplicates else RuntimeDecisionState.NO_EVENT, exact_duplicate_count=exact_duplicates)
    expected_sequence = state.last_sequence + 1
    candidate = pending[0]
    if candidate.sequence > expected_sequence:
        return RuntimeDecision(state=RuntimeDecisionState.HELD_SEQUENCE_GAP, event=candidate, exact_duplicate_count=exact_duplicates, missing_sequence=expected_sequence)
    retry = state.attempts.get(candidate.event_id)
    if retry and retry.get('state') == RuntimeDecisionState.DEAD_LETTER.value:
        return RuntimeDecision(state=RuntimeDecisionState.DEAD_LETTER, event=candidate, exact_duplicate_count=exact_duplicates)
    if retry and retry.get('next_retry_at'):
        retry_at = parse_time(str(retry['next_retry_at']))
        if retry_at > current:
            return RuntimeDecision(state=RuntimeDecisionState.RETRY_NOT_DUE, event=candidate, exact_duplicate_count=exact_duplicates, retry_at=normalise_time(retry_at))
    expired_lease_recovery = False
    if state.current_lease:
        lease_event_id = str(state.current_lease.get('event_id') or '')
        lease_expiry = parse_time(str(state.current_lease.get('expires_at') or ''))
        lease_owner = str(state.current_lease.get('worker_id') or '')
        if lease_expiry > current:
            return RuntimeDecision(state=RuntimeDecisionState.ACTIVE_LEASE, event=candidate, exact_duplicate_count=exact_duplicates, retry_at=normalise_time(lease_expiry), lease_owner=lease_owner)
        if lease_event_id:
            expired_lease_recovery = True
    due = parse_time(candidate.due_at)
    if due > current:
        return RuntimeDecision(state=RuntimeDecisionState.NOT_DUE, event=candidate, exact_duplicate_count=exact_duplicates, retry_at=normalise_time(due))
    missed = current > due + timedelta(seconds=missed_grace_seconds)
    return RuntimeDecision(state=RuntimeDecisionState.PROCESS, event=candidate, missed_run=missed, expired_lease_recovery=expired_lease_recovery, exact_duplicate_count=exact_duplicates)
__all__ = ['BackupRuntimeEvent', 'DEFAULT_DESTINATION_ALIAS', 'GENESIS', 'RUNTIME_SCHEMA', 'RUNTIME_VERSION', 'RuntimeDecision', 'RuntimeDecisionState', 'RuntimeState', 'append_runtime_event', 'artifact_set_sha256', 'normalise_time', 'parse_time', 'require_sha256', 'select_next_event', 'sha256_bytes', 'verify_runtime_event_chain', 'verify_runtime_state']