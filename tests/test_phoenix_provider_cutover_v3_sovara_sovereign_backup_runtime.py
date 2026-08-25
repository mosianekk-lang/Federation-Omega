from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from federation_consolidation.sovara_sovereign_backup import ArtifactClass, ArtifactInput, BackupError
from federation_consolidation.sovara_sovereign_backup_runtime import BackupRuntimeEvent, DEFAULT_DESTINATION_ALIAS, RuntimeDecisionState, RuntimeState, artifact_set_sha256, run_private_backup_cycle, select_next_event, verify_runtime_state
OWNER = 'owner@example.invalid'
NOW = datetime(2026, 8, 25, 0, 0, tzinfo=UTC)

@dataclass(frozen=True)
class ProviderFile:
    file_id: str
    name: str
    size_bytes: int
    url: str = ''

@dataclass(frozen=True)
class PermissionReadback:
    shared: bool
    owner_identities: tuple[str, ...]
    non_owner_identities: tuple[str, ...] = ()

def artifacts(version: str='v1'):
    return (ArtifactInput(logical_name='state.json', content=json.dumps({'version': version}, sort_keys=True).encode(), media_type='application/json', classification=ArtifactClass.PRIVATE_CONTROL, source_ref='source:fixture', email_eligible=False),)

def event(sequence: int, *, event_id: str | None=None, version: str='v1', due_offset_seconds: int=-120, detected_offset_seconds: int=-180):
    current = artifacts(version)
    return {'sequence': sequence, 'event_type': 'MATERIAL_CONFIG_CHANGE', 'event_id': event_id or f'EVT-{sequence:03d}', 'detected_at': (NOW + timedelta(seconds=detected_offset_seconds)).isoformat(), 'due_at': (NOW + timedelta(seconds=due_offset_seconds)).isoformat(), 'source_identity': 'source:fixture', 'source_version': version, 'artifact_set_sha256': artifact_set_sha256(current), 'metadata': {'scope': 'test'}}

class FakeAdapter:

    def __init__(self):
        self.state = None
        self.events = []
        self.aliases = {DEFAULT_DESTINATION_ALIAS: 'private-root'}
        self.containers = {}
        self.container_names = {}
        self.files = {}
        self.file_names = {}
        self.emails = {}
        self.reservations = {}
        self.effects = 0
        self.fail_upload = False
        self.force_cas_failure = False
        self.force_cas_failure_on_call = None
        self.cas_calls = 0
        self.owner = OWNER
        self.shared = False
        self.non_owners = ()
        self.counter = 0

    def load_runtime_state(self, destination_alias):
        return deepcopy(self.state)

    def compare_and_swap_runtime_state(self, destination_alias, expected_state_version, state):
        self.cas_calls += 1
        current = RuntimeState.from_mapping(self.state).state_version
        if self.force_cas_failure or self.force_cas_failure_on_call == self.cas_calls or current != expected_state_version:
            return False
        self.state = deepcopy(dict(state))
        return True

    def discover_backup_events(self, destination_alias, *, after_sequence, limit):
        return [deepcopy(item) for item in self.events if int(item['sequence']) > after_sequence][:limit]

    def reserve_backup_effect(self, destination_alias, *, idempotency_key, payload_sha256, worker_id, lease_expires_at):
        prior = self.reservations.get(idempotency_key)
        if prior:
            if prior['payload_sha256'] != payload_sha256:
                return {'state': 'COLLISION'}
            if prior.get('receipt'):
                return {'state': 'ALREADY_COMPLETED_EXACT'}
            return {'state': 'ACTIVE_LEASE'}
        self.reservations[idempotency_key] = {'payload_sha256': payload_sha256, 'worker_id': worker_id, 'lease_expires_at': lease_expires_at, 'receipt': None}
        return {'state': 'RESERVED'}

    def read_backup_effect_receipt(self, destination_alias, idempotency_key):
        prior = self.reservations.get(idempotency_key)
        return deepcopy(prior.get('receipt')) if prior and prior.get('receipt') else None

    def commit_backup_effect_receipt(self, destination_alias, *, idempotency_key, payload_sha256, receipt):
        prior = self.reservations[idempotency_key]
        if prior['payload_sha256'] != payload_sha256:
            raise BackupError('reservation payload changed')
        prior['receipt'] = deepcopy(dict(receipt))

    def resolve_destination(self, alias):
        return self.aliases.get(alias, '')

    def create_snapshot_container(self, destination, name):
        key = (destination, name)
        if key in self.container_names:
            return self.container_names[key]
        self.counter += 1
        ref = f'container-{self.counter}'
        self.container_names[key] = ref
        self.containers[ref] = name
        self.effects += 1
        return ref

    def upload_bytes(self, container, name, content, media_type):
        if self.fail_upload:
            raise RuntimeError('synthetic upload failure')
        key = (container, name)
        digest = hashlib.sha256(content).hexdigest()
        if key in self.file_names:
            file_id = self.file_names[key]
            if hashlib.sha256(self.files[file_id]).hexdigest() != digest:
                raise BackupError('idempotent file payload changed')
            return ProviderFile(file_id, name, len(content), f'private://{file_id}')
        self.counter += 1
        file_id = f'file-{self.counter}'
        self.file_names[key] = file_id
        self.files[file_id] = bytes(content)
        self.effects += 1
        return ProviderFile(file_id, name, len(content), f'private://{file_id}')

    def download_bytes(self, file_id):
        return self.files[file_id]

    def read_permissions(self, container):
        return PermissionReadback(shared=self.shared, owner_identities=(self.owner,), non_owner_identities=tuple(self.non_owners))

    def send_continuity_email(self, *, subject, body, attachments):
        key = hashlib.sha256((subject + body).encode()).hexdigest()
        if key not in self.emails:
            self.emails[key] = (subject, body, tuple(attachments))
            self.effects += 1
        return f'message-{key[:12]}'

def loader(runtime_event: BackupRuntimeEvent):
    return artifacts(runtime_event.source_version)

class SelectionTests(unittest.TestCase):

    def test_no_event(self):
        decision = select_next_event(RuntimeState(), [], now=NOW, worker_id='worker')
        self.assertEqual(RuntimeDecisionState.NO_EVENT, decision.state)

    def test_not_due(self):
        candidate = event(1, due_offset_seconds=60)
        decision = select_next_event(RuntimeState(), [candidate], now=NOW, worker_id='worker')
        self.assertEqual(RuntimeDecisionState.NOT_DUE, decision.state)

    def test_missed_event_selected(self):
        candidate = event(1, due_offset_seconds=-300)
        decision = select_next_event(RuntimeState(), [candidate], now=NOW, worker_id='worker', missed_grace_seconds=60)
        self.assertEqual(RuntimeDecisionState.PROCESS, decision.state)
        self.assertTrue(decision.missed_run)

    def test_sequence_gap_is_held(self):
        decision = select_next_event(RuntimeState(), [event(2)], now=NOW, worker_id='worker')
        self.assertEqual(RuntimeDecisionState.HELD_SEQUENCE_GAP, decision.state)
        self.assertEqual(1, decision.missing_sequence)

    def test_changed_event_id_payload_is_rejected(self):
        first = event(1, event_id='SAME', version='v1')
        second = event(2, event_id='SAME', version='v2')
        with self.assertRaisesRegex(BackupError, 'event_id collision'):
            select_next_event(RuntimeState(), [first, second], now=NOW, worker_id='worker')

    def test_exact_duplicate_delivery_is_counted_not_reprocessed_twice(self):
        candidate = event(1)
        decision = select_next_event(RuntimeState(), [candidate, deepcopy(candidate)], now=NOW, worker_id='worker')
        self.assertEqual(RuntimeDecisionState.PROCESS, decision.state)
        self.assertEqual(1, decision.exact_duplicate_count)

    def test_active_lease_blocks_duplicate_worker(self):
        candidate = event(1)
        parsed = BackupRuntimeEvent.from_mapping(candidate)
        state = RuntimeState(current_lease={'event_id': parsed.event_id, 'event_payload_sha256': parsed.payload_sha256, 'worker_id': 'other', 'claimed_at': NOW.isoformat(), 'expires_at': (NOW + timedelta(minutes=5)).isoformat(), 'idempotency_key': 'sovbak-x', 'payload_sha256': 'a' * 64})
        decision = select_next_event(state, [candidate], now=NOW, worker_id='worker')
        self.assertEqual(RuntimeDecisionState.ACTIVE_LEASE, decision.state)

    def test_expired_lease_is_recovered(self):
        candidate = event(1)
        parsed = BackupRuntimeEvent.from_mapping(candidate)
        state = RuntimeState(current_lease={'event_id': parsed.event_id, 'event_payload_sha256': parsed.payload_sha256, 'worker_id': 'old', 'claimed_at': (NOW - timedelta(minutes=10)).isoformat(), 'expires_at': (NOW - timedelta(minutes=5)).isoformat(), 'idempotency_key': 'sovbak-x', 'payload_sha256': 'a' * 64})
        decision = select_next_event(state, [candidate], now=NOW, worker_id='worker')
        self.assertEqual(RuntimeDecisionState.PROCESS, decision.state)
        self.assertTrue(decision.expired_lease_recovery)

class RuntimeExecutionTests(unittest.TestCase):

    def test_successful_missed_run_recovery(self):
        adapter = FakeAdapter()
        adapter.events = [event(1, due_offset_seconds=-600)]
        result = run_private_backup_cycle(adapter=adapter, artifact_loader=loader, expected_owner_identity=OWNER, worker_id='worker', now=NOW)
        self.assertEqual(RuntimeDecisionState.MISSED_RUN_RECOVERED.value, result['state'])
        self.assertTrue(result['provider_effect'])
        state = RuntimeState.from_mapping(adapter.state)
        self.assertEqual(1, state.last_sequence)
        self.assertIn('EVT-001', state.completed_events)
        self.assertTrue(verify_runtime_state(state))

    def test_exact_retry_does_not_duplicate_provider_effect(self):
        adapter = FakeAdapter()
        adapter.events = [event(1)]
        first = run_private_backup_cycle(adapter=adapter, artifact_loader=loader, expected_owner_identity=OWNER, worker_id='worker', now=NOW)
        effect_count = adapter.effects
        second = run_private_backup_cycle(adapter=adapter, artifact_loader=loader, expected_owner_identity=OWNER, worker_id='worker', now=NOW + timedelta(minutes=1))
        self.assertIn(second['state'], {RuntimeDecisionState.ALREADY_COMPLETED_EXACT.value, RuntimeDecisionState.NO_EVENT.value})
        self.assertEqual(effect_count, adapter.effects)
        self.assertEqual(1, RuntimeState.from_mapping(adapter.state).last_sequence)
        self.assertTrue(first['provider_effect'])

    def test_artifact_binding_mismatch_fails_before_provider(self):
        adapter = FakeAdapter()
        bad = event(1)
        bad['artifact_set_sha256'] = '0' * 64
        adapter.events = [bad]
        result = run_private_backup_cycle(adapter=adapter, artifact_loader=loader, expected_owner_identity=OWNER, worker_id='worker', now=NOW)
        self.assertEqual(RuntimeDecisionState.RETRY_SCHEDULED.value, result['state'])
        self.assertFalse(result['provider_effect'])
        self.assertEqual(0, adapter.effects)

    def test_provider_failure_schedules_retry(self):
        adapter = FakeAdapter()
        adapter.fail_upload = True
        adapter.events = [event(1)]
        result = run_private_backup_cycle(adapter=adapter, artifact_loader=loader, expected_owner_identity=OWNER, worker_id='worker', now=NOW)
        self.assertEqual(RuntimeDecisionState.RETRY_SCHEDULED.value, result['state'])
        state = RuntimeState.from_mapping(adapter.state)
        self.assertEqual(1, state.attempts['EVT-001']['attempt'])
        self.assertIsNone(state.current_lease)

    def test_max_attempts_dead_letters(self):
        adapter = FakeAdapter()
        adapter.fail_upload = True
        adapter.events = [event(1)]
        result = None
        current = NOW
        for _ in range(2):
            result = run_private_backup_cycle(adapter=adapter, artifact_loader=loader, expected_owner_identity=OWNER, worker_id='worker', now=current, max_attempts=2, base_backoff_seconds=1)
            current += timedelta(seconds=2)
            adapter.reservations.clear()
        self.assertEqual(RuntimeDecisionState.DEAD_LETTER.value, result['state'])

    def test_state_cas_race_occurs_before_provider_effect(self):
        adapter = FakeAdapter()
        adapter.events = [event(1)]
        adapter.force_cas_failure = True
        result = run_private_backup_cycle(adapter=adapter, artifact_loader=loader, expected_owner_identity=OWNER, worker_id='worker', now=NOW)
        self.assertEqual(RuntimeDecisionState.STATE_RACE_RETRY.value, result['state'])
        self.assertFalse(result['provider_effect'])
        self.assertEqual(0, adapter.effects)

    def test_provider_receipt_recovery_avoids_duplicate_effect(self):
        adapter = FakeAdapter()
        adapter.events = [event(1)]
        first = run_private_backup_cycle(adapter=adapter, artifact_loader=loader, expected_owner_identity=OWNER, worker_id='worker', now=NOW)
        completed_state = RuntimeState.from_mapping(adapter.state)
        adapter.state = RuntimeState().to_mapping()
        effects = adapter.effects
        second = run_private_backup_cycle(adapter=adapter, artifact_loader=loader, expected_owner_identity=OWNER, worker_id='worker', now=NOW + timedelta(minutes=1))
        self.assertEqual(RuntimeDecisionState.PROVIDER_RECEIPT_RECOVERED.value, second['state'])
        self.assertFalse(second['provider_effect'])
        self.assertEqual(effects, adapter.effects)
        self.assertEqual(1, RuntimeState.from_mapping(adapter.state).last_sequence)
        self.assertTrue(first['provider_effect'])
        self.assertEqual(1, completed_state.last_sequence)

    def test_retry_not_due_prevents_provider_reentry(self):
        adapter = FakeAdapter()
        adapter.fail_upload = True
        adapter.events = [event(1)]
        first = run_private_backup_cycle(adapter=adapter, artifact_loader=loader, expected_owner_identity=OWNER, worker_id='worker', now=NOW, base_backoff_seconds=60)
        effects = adapter.effects
        second = run_private_backup_cycle(adapter=adapter, artifact_loader=loader, expected_owner_identity=OWNER, worker_id='worker', now=NOW + timedelta(seconds=10), base_backoff_seconds=60)
        self.assertEqual(RuntimeDecisionState.RETRY_SCHEDULED.value, first['state'])
        self.assertEqual(RuntimeDecisionState.RETRY_NOT_DUE.value, second['state'])
        self.assertEqual(effects, adapter.effects)

    def test_final_state_race_preserves_provider_receipt_for_reconciliation(self):
        adapter = FakeAdapter()
        adapter.events = [event(1)]
        adapter.force_cas_failure_on_call = 2
        result = run_private_backup_cycle(adapter=adapter, artifact_loader=loader, expected_owner_identity=OWNER, worker_id='worker', now=NOW)
        self.assertEqual(RuntimeDecisionState.PROVIDER_EFFECT_STATE_RECONCILIATION_REQUIRED.value, result['state'])
        self.assertTrue(result['provider_effect'])
        self.assertTrue(adapter.reservations)

    def test_provider_reservation_collision_fails_closed(self):
        adapter = FakeAdapter()
        adapter.events = [event(1)]
        adapter.force_cas_failure = True
        first = run_private_backup_cycle(adapter=adapter, artifact_loader=loader, expected_owner_identity=OWNER, worker_id='worker', now=NOW)
        self.assertEqual(RuntimeDecisionState.STATE_RACE_RETRY.value, first['state'])
        reservation = next(iter(adapter.reservations.values()))
        reservation['payload_sha256'] = '0' * 64
        adapter.force_cas_failure = False
        with self.assertRaisesRegex(BackupError, 'payload collision'):
            run_private_backup_cycle(adapter=adapter, artifact_loader=loader, expected_owner_identity=OWNER, worker_id='worker', now=NOW + timedelta(minutes=1))

    def test_wrong_owner_fails_closed(self):
        adapter = FakeAdapter()
        adapter.owner = 'other@example.invalid'
        adapter.events = [event(1)]
        result = run_private_backup_cycle(adapter=adapter, artifact_loader=loader, expected_owner_identity=OWNER, worker_id='worker', now=NOW)
        self.assertEqual(RuntimeDecisionState.RETRY_SCHEDULED.value, result['state'])
        self.assertFalse(bool(adapter.read_backup_effect_receipt(DEFAULT_DESTINATION_ALIAS, next(iter(adapter.reservations)))))

class ArchitectureBoundaryTests(unittest.TestCase):

    def test_state_and_provider_controller_remain_separate_and_bounded(self):
        state_module = ROOT / 'federation_consolidation' / 'sovara_sovereign_backup_runtime_state.py'
        controller = ROOT / 'federation_consolidation' / 'sovara_sovereign_backup_runtime.py'
        state_lines = state_module.read_text(encoding='utf-8').splitlines()
        controller_lines = controller.read_text(encoding='utf-8').splitlines()
        self.assertLessEqual(len(state_lines), 600)
        self.assertLessEqual(len(controller_lines), 650)
        self.assertNotIn('def execute_private_backup', state_module.read_text(encoding='utf-8'))
        self.assertIn('def run_private_backup_cycle', controller.read_text(encoding='utf-8'))

    def test_compatibility_module_reexports_state_surface(self):
        from federation_consolidation import sovara_sovereign_backup_runtime as runtime
        self.assertIs(runtime.RuntimeState, RuntimeState)
        self.assertIs(runtime.BackupRuntimeEvent, BackupRuntimeEvent)
        self.assertTrue(callable(runtime.select_next_event))

class StateIntegrityTests(unittest.TestCase):

    def test_artifact_set_hash_is_order_independent(self):
        first = ArtifactInput(logical_name='a.txt', content=b'A', classification=ArtifactClass.PRIVATE_CONTROL)
        second = ArtifactInput(logical_name='b.txt', content=b'B', classification=ArtifactClass.PRIVATE_CONTROL)
        self.assertEqual(artifact_set_sha256([first, second]), artifact_set_sha256([second, first]))

    def test_runtime_state_round_trip(self):
        state = RuntimeState()
        self.assertEqual(state, RuntimeState.from_mapping(state.to_mapping()))

    def test_tampered_runtime_event_chain_is_rejected(self):
        adapter = FakeAdapter()
        adapter.events = [event(1)]
        run_private_backup_cycle(adapter=adapter, artifact_loader=loader, expected_owner_identity=OWNER, worker_id='worker', now=NOW)
        tampered = deepcopy(adapter.state)
        tampered['runtime_events'][-1]['payload']['sequence'] = 99
        with self.assertRaisesRegex(BackupError, 'hash chain'):
            RuntimeState.from_mapping(tampered)

    def test_tampered_last_manifest_is_rejected(self):
        adapter = FakeAdapter()
        adapter.events = [event(1)]
        run_private_backup_cycle(adapter=adapter, artifact_loader=loader, expected_owner_identity=OWNER, worker_id='worker', now=NOW)
        tampered = deepcopy(adapter.state)
        tampered['last_manifest']['source_version'] = 'changed'
        with self.assertRaisesRegex(BackupError, 'last-manifest'):
            RuntimeState.from_mapping(tampered)

    def test_secret_shaped_event_metadata_is_rejected(self):
        candidate = event(1)
        candidate['metadata'] = {'api_key': 'value'}
        with self.assertRaisesRegex(BackupError, 'secret-bearing'):
            BackupRuntimeEvent.from_mapping(candidate)
if __name__ == '__main__':
    unittest.main()