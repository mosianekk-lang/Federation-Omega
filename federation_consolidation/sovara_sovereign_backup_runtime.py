"""Provider execution controller for the SOVARA sovereign backup runtime.

The controller composes the provider-neutral backup core with a private adapter.
It serialises provider effects, reserves idempotency keys before mutation,
recovers receipts after state-write loss, and commits durable state through
compare-and-swap. This source is not itself an unattended scheduler.
"""
from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence
from .sovara_sovereign_backup import ArtifactInput, BackupError, BackupPlan, IdempotencyLedger, build_backup_plan, execute_private_backup, reject_secret_metadata
from .sovara_sovereign_backup_runtime_state import BackupRuntimeEvent, DEFAULT_DESTINATION_ALIAS, RUNTIME_SCHEMA, RuntimeDecision, RuntimeDecisionState, RuntimeState, append_runtime_event, artifact_set_sha256, normalise_time, parse_time, require_sha256, select_next_event, sha256_bytes, verify_runtime_state

class PrivateBackupRuntimeAdapter(Protocol):
    """Private provider adapter and durable runtime-state contract."""

    def resolve_destination(self, alias: str) -> str:
        ...

    def create_snapshot_container(self, destination: str, name: str) -> str:
        ...

    def upload_bytes(self, container: str, name: str, content: bytes, media_type: str) -> Any:
        ...

    def download_bytes(self, file_id: str) -> bytes:
        ...

    def read_permissions(self, container: str) -> Any:
        ...

    def send_continuity_email(self, *, subject: str, body: str, attachments: Sequence[tuple[str, bytes, str]]) -> str:
        ...

    def load_runtime_state(self, destination_alias: str) -> Mapping[str, Any] | None:
        ...

    def compare_and_swap_runtime_state(self, destination_alias: str, expected_state_version: int, state: Mapping[str, Any]) -> bool:
        ...

    def discover_backup_events(self, destination_alias: str, *, after_sequence: int, limit: int) -> Sequence[Mapping[str, Any]]:
        ...

    def reserve_backup_effect(self, destination_alias: str, *, idempotency_key: str, payload_sha256: str, worker_id: str, lease_expires_at: str) -> Mapping[str, Any]:
        ...

    def read_backup_effect_receipt(self, destination_alias: str, idempotency_key: str) -> Mapping[str, Any] | None:
        ...

    def commit_backup_effect_receipt(self, destination_alias: str, *, idempotency_key: str, payload_sha256: str, receipt: Mapping[str, Any]) -> None:
        ...

ArtifactLoader = Callable[[BackupRuntimeEvent], Iterable[ArtifactInput]]

def _claim_state(state: RuntimeState, *, event: BackupRuntimeEvent, worker_id: str, now: datetime, lease_seconds: int, plan: BackupPlan) -> RuntimeState:
    lease = {'event_id': event.event_id, 'event_payload_sha256': event.payload_sha256, 'worker_id': worker_id, 'claimed_at': normalise_time(now), 'expires_at': normalise_time(now + timedelta(seconds=lease_seconds)), 'idempotency_key': plan.idempotency_key, 'payload_sha256': plan.archive_sha256 or plan.manifest_sha256}
    claimed = replace(state, state_version=state.state_version + 1, current_lease=lease)
    return append_runtime_event(claimed, kind='LEASE_CLAIMED', event_id=event.event_id, occurred_at=normalise_time(now), payload={'sequence': event.sequence, 'worker_id': worker_id, 'idempotency_key': plan.idempotency_key, 'expired_lease_recovery': bool(state.current_lease)})

def _complete_state(state: RuntimeState, *, event: BackupRuntimeEvent, plan: BackupPlan, provider_receipt: Mapping[str, Any], ledger: IdempotencyLedger, now: datetime, missed_run: bool, receipt_recovered: bool) -> RuntimeState:
    reject_secret_metadata(provider_receipt, 'runtime_provider_receipt')
    receipt_sha = require_sha256(str(provider_receipt.get('receipt_sha256') or ''), 'provider receipt_sha256')
    completed = {key: dict(value) for key, value in state.completed_events.items()}
    completed[event.event_id] = {'event_id': event.event_id, 'sequence': event.sequence, 'event_payload_sha256': event.payload_sha256, 'idempotency_key': plan.idempotency_key, 'manifest_sha256': plan.manifest_sha256, 'archive_sha256': plan.archive_sha256, 'receipt_sha256': receipt_sha, 'completed_at': normalise_time(now), 'missed_run_recovered': missed_run, 'provider_receipt_recovered': receipt_recovered}
    attempts = {key: dict(value) for key, value in state.attempts.items()}
    attempts.pop(event.event_id, None)
    result = replace(state, state_version=state.state_version + 1, last_sequence=event.sequence, last_manifest=dict(plan.manifest), last_manifest_sha256=plan.manifest_sha256, last_receipt_sha256=receipt_sha, idempotency_events=tuple((dict(item) for item in ledger.events)), completed_events=completed, attempts=attempts, current_lease=None)
    kind = 'PROVIDER_RECEIPT_RECOVERED' if receipt_recovered else 'MISSED_RUN_RECOVERED' if missed_run else 'SUCCESS'
    result = append_runtime_event(result, kind=kind, event_id=event.event_id, occurred_at=normalise_time(now), payload={'sequence': event.sequence, 'backup_mode': str(plan.manifest['backup_mode']), 'manifest_sha256': plan.manifest_sha256, 'archive_sha256': plan.archive_sha256, 'receipt_sha256': receipt_sha, 'missed_run_recovered': missed_run, 'provider_receipt_recovered': receipt_recovered})
    verify_runtime_state(result)
    return result

def _failure_state(state: RuntimeState, *, event: BackupRuntimeEvent, now: datetime, error: Exception, max_attempts: int, base_backoff_seconds: int) -> tuple[RuntimeState, RuntimeDecisionState, str]:
    prior = dict(state.attempts.get(event.event_id) or {})
    attempt = int(prior.get('attempt') or 0) + 1
    fingerprint = sha256_bytes((type(error).__name__ + '|' + str(error)).encode('utf-8'))
    dead = attempt >= max_attempts
    next_retry = None
    if not dead:
        delay = min(86400, base_backoff_seconds * 2 ** max(0, attempt - 1))
        next_retry = normalise_time(now + timedelta(seconds=delay))
    attempts = {key: dict(value) for key, value in state.attempts.items()}
    attempts[event.event_id] = {'state': RuntimeDecisionState.DEAD_LETTER.value if dead else RuntimeDecisionState.RETRY_SCHEDULED.value, 'attempt': attempt, 'error_type': type(error).__name__, 'error_fingerprint': fingerprint, 'next_retry_at': next_retry, 'updated_at': normalise_time(now)}
    result = replace(state, state_version=state.state_version + 1, attempts=attempts, current_lease=None)
    result = append_runtime_event(result, kind='FAILURE', event_id=event.event_id, occurred_at=normalise_time(now), payload={'sequence': event.sequence, 'attempt': attempt, 'error_type': type(error).__name__, 'error_fingerprint': fingerprint, 'next_retry_at': next_retry, 'dead_letter': dead})
    verify_runtime_state(result)
    return (result, RuntimeDecisionState.DEAD_LETTER if dead else RuntimeDecisionState.RETRY_SCHEDULED, fingerprint)

def _build_event_plan(state: RuntimeState, event: BackupRuntimeEvent, artifact_loader: ArtifactLoader, *, checkpoint_every: int) -> tuple[tuple[ArtifactInput, ...], BackupPlan]:
    artifacts = tuple(artifact_loader(event))
    observed_artifact_set = artifact_set_sha256(artifacts)
    if observed_artifact_set != event.artifact_set_sha256:
        raise BackupError('runtime artifact set differs from the event binding')
    plan = build_backup_plan(event_type=event.event_type, event_id=event.event_id, created_at=event.detected_at, source_identity=event.source_identity, source_version=event.source_version, artifacts=artifacts, prior_manifest=state.last_manifest, prior_manifest_sha256=state.last_manifest_sha256, prior_receipt_sha256=state.last_receipt_sha256, sequence=event.sequence, checkpoint_every=checkpoint_every)
    return (artifacts, plan)

def _existing_receipt_ledger(state: RuntimeState, *, plan: BackupPlan, receipt: Mapping[str, Any]) -> IdempotencyLedger:
    ledger = IdempotencyLedger(state.idempotency_events)
    payload_sha = plan.archive_sha256 or plan.manifest_sha256
    ledger.admit(key=plan.idempotency_key, payload_sha256=payload_sha, receipt=receipt)
    return ledger

def run_private_backup_cycle(*, adapter: PrivateBackupRuntimeAdapter, artifact_loader: ArtifactLoader, expected_owner_identity: str, worker_id: str, now: datetime | str, destination_alias: str=DEFAULT_DESTINATION_ALIAS, event_limit: int=50, lease_seconds: int=300, missed_grace_seconds: int=60, checkpoint_every: int=7, max_attempts: int=5, base_backoff_seconds: int=60, send_email: bool=True) -> Mapping[str, Any]:
    """Discover, reserve, execute, verify, and commit one backup event."""
    if event_limit < 1 or event_limit > 1000:
        raise BackupError('event_limit must be between 1 and 1000')
    if lease_seconds < 30:
        raise BackupError('lease_seconds must be at least 30')
    if max_attempts < 1:
        raise BackupError('max_attempts must be positive')
    current = parse_time(now)
    state = RuntimeState.from_mapping(adapter.load_runtime_state(destination_alias))
    event_values = adapter.discover_backup_events(destination_alias, after_sequence=max(0, state.last_sequence - 1), limit=event_limit)
    decision = select_next_event(state, event_values, now=current, worker_id=worker_id, missed_grace_seconds=missed_grace_seconds)
    if decision.state is not RuntimeDecisionState.PROCESS or decision.event is None:
        return {'schema': RUNTIME_SCHEMA, 'state': decision.state.value, 'decision': decision.as_mapping(), 'state_version': state.state_version, 'last_sequence': state.last_sequence, 'provider_effect': False}
    event = decision.event
    try:
        _artifacts, plan = _build_event_plan(state, event, artifact_loader, checkpoint_every=checkpoint_every)
    except Exception as error:
        failed, terminal, fingerprint = _failure_state(state, event=event, now=current, error=error, max_attempts=max_attempts, base_backoff_seconds=base_backoff_seconds)
        adapter.compare_and_swap_runtime_state(destination_alias, state.state_version, failed.to_mapping())
        return {'schema': RUNTIME_SCHEMA, 'state': terminal.value, 'event_id': event.event_id, 'sequence': event.sequence, 'error_type': type(error).__name__, 'error_fingerprint': fingerprint, 'provider_effect': False}
    payload_sha = plan.archive_sha256 or plan.manifest_sha256
    reservation = dict(adapter.reserve_backup_effect(destination_alias, idempotency_key=plan.idempotency_key, payload_sha256=payload_sha, worker_id=worker_id, lease_expires_at=normalise_time(current + timedelta(seconds=lease_seconds))))
    reservation_state = str(reservation.get('state') or '')
    if reservation_state == 'COLLISION':
        raise BackupError('provider effect reservation reports a payload collision')
    if reservation_state == 'ACTIVE_LEASE':
        return {'schema': RUNTIME_SCHEMA, 'state': RuntimeDecisionState.ACTIVE_LEASE.value, 'event_id': event.event_id, 'sequence': event.sequence, 'provider_effect': False}
    if reservation_state == 'ALREADY_COMPLETED_EXACT':
        receipt = adapter.read_backup_effect_receipt(destination_alias, plan.idempotency_key)
        if receipt is None:
            raise BackupError('completed provider reservation lacks its receipt')
        reject_secret_metadata(receipt, 'recovered_provider_receipt')
        ledger = _existing_receipt_ledger(state, plan=plan, receipt=receipt)
        completed = _complete_state(state, event=event, plan=plan, provider_receipt=receipt, ledger=ledger, now=current, missed_run=decision.missed_run, receipt_recovered=True)
        if not adapter.compare_and_swap_runtime_state(destination_alias, state.state_version, completed.to_mapping()):
            return {'schema': RUNTIME_SCHEMA, 'state': RuntimeDecisionState.STATE_RACE_RETRY.value, 'event_id': event.event_id, 'sequence': event.sequence, 'provider_effect': False, 'provider_receipt_recovered': True}
        return {'schema': RUNTIME_SCHEMA, 'state': RuntimeDecisionState.PROVIDER_RECEIPT_RECOVERED.value, 'event_id': event.event_id, 'sequence': event.sequence, 'provider_effect': False, 'receipt_sha256': receipt['receipt_sha256'], 'runtime_state_version': completed.state_version}
    if reservation_state != 'RESERVED':
        raise BackupError('provider effect reservation returned an unsupported state')
    claimed = _claim_state(state, event=event, worker_id=worker_id, now=current, lease_seconds=lease_seconds, plan=plan)
    if not adapter.compare_and_swap_runtime_state(destination_alias, state.state_version, claimed.to_mapping()):
        return {'schema': RUNTIME_SCHEMA, 'state': RuntimeDecisionState.STATE_RACE_RETRY.value, 'event_id': event.event_id, 'sequence': event.sequence, 'provider_effect': False}
    ledger = IdempotencyLedger(claimed.idempotency_events)
    try:
        receipt = execute_private_backup(plan=plan, provider=adapter, destination_alias=destination_alias, expected_owner_identity=expected_owner_identity, ledger=ledger, send_email=send_email)
        adapter.commit_backup_effect_receipt(destination_alias, idempotency_key=plan.idempotency_key, payload_sha256=payload_sha, receipt=receipt)
        completed = _complete_state(claimed, event=event, plan=plan, provider_receipt=receipt, ledger=ledger, now=current, missed_run=decision.missed_run, receipt_recovered=False)
        if not adapter.compare_and_swap_runtime_state(destination_alias, claimed.state_version, completed.to_mapping()):
            return {'schema': RUNTIME_SCHEMA, 'state': RuntimeDecisionState.PROVIDER_EFFECT_STATE_RECONCILIATION_REQUIRED.value, 'event_id': event.event_id, 'sequence': event.sequence, 'provider_effect': True, 'receipt_sha256': receipt['receipt_sha256']}
        return {'schema': RUNTIME_SCHEMA, 'state': RuntimeDecisionState.MISSED_RUN_RECOVERED.value if decision.missed_run else RuntimeDecisionState.SUCCEEDED.value, 'event_id': event.event_id, 'sequence': event.sequence, 'backup_mode': plan.manifest['backup_mode'], 'manifest_sha256': plan.manifest_sha256, 'archive_sha256': plan.archive_sha256, 'receipt_sha256': receipt['receipt_sha256'], 'runtime_state_version': completed.state_version, 'missed_run_recovered': decision.missed_run, 'expired_lease_recovery': decision.expired_lease_recovery, 'provider_effect': True}
    except Exception as error:
        failed, terminal, fingerprint = _failure_state(claimed, event=event, now=current, error=error, max_attempts=max_attempts, base_backoff_seconds=base_backoff_seconds)
        adapter.compare_and_swap_runtime_state(destination_alias, claimed.state_version, failed.to_mapping())
        committed_receipt = adapter.read_backup_effect_receipt(destination_alias, plan.idempotency_key)
        return {'schema': RUNTIME_SCHEMA, 'state': terminal.value, 'event_id': event.event_id, 'sequence': event.sequence, 'error_type': type(error).__name__, 'error_fingerprint': fingerprint, 'provider_effect': True if committed_receipt else None, 'provider_effect_state': 'VERIFIED_COMMITTED' if committed_receipt else 'POSSIBLE_PARTIAL_OR_NONE'}
__all__ = ['ArtifactLoader', 'BackupRuntimeEvent', 'DEFAULT_DESTINATION_ALIAS', 'PrivateBackupRuntimeAdapter', 'RUNTIME_SCHEMA', 'RuntimeDecision', 'RuntimeDecisionState', 'RuntimeState', 'artifact_set_sha256', 'run_private_backup_cycle', 'select_next_event', 'verify_runtime_state']