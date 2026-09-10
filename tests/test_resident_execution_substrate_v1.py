import unittest

import pytest

from federation.resident_execution_substrate_v1 import (
    AdmissionSnapshot,
    AtomicConflict,
    DesiredStateReconciler,
    DurableResultCache,
    FenceViolation,
    IdempotencyCollision,
    InMemoryAtomicDocumentBackend,
    ProviderConformanceKit,
    ResidentExecutionStore,
    ResultCacheRecord,
    WorkAdmissionController,
    WorkSpec,
    WorkState,
)


NOW = 1_800_000_000.0


def spec(**changes):
    values = dict(
        mission_id="MISSION-1",
        work_id="WORK-1",
        transition_id="TRANSITION-1",
        provider="provider",
        target="private-target",
        operation="RECONCILE",
        semantic_request_sha256="sha256:" + "a" * 64,
        idempotency_key="mission-1:work-1:epoch-1",
        source_epoch="main:abc",
        effect_class="A1_INTERNAL",
        risk_class="LOW",
        expected_readback="provider-native semantic equality",
        rollback_ref="rollback:immutable-1",
    )
    values.update(changes)
    return WorkSpec(**values)


def test_provider_contract_conformance_court():
    receipt = ProviderConformanceKit().run(InMemoryAtomicDocumentBackend)
    assert receipt.state == "CONFORMANT_LOCAL_COURT"
    assert receipt.checks[-1] == "READBACK_EXACT"


def test_work_issue_is_idempotent_but_semantic_collision_fails_closed():
    store = ResidentExecutionStore(InMemoryAtomicDocumentBackend(), clock=lambda: NOW)
    first = store.issue(spec())
    assert store.issue(spec()) == first
    with pytest.raises(IdempotencyCollision, match="SEMANTIC_COLLISION"):
        store.issue(spec(semantic_request_sha256="sha256:" + "b" * 64))


def test_lease_fencing_blocks_foreign_and_stale_workers():
    store = ResidentExecutionStore(InMemoryAtomicDocumentBackend(), clock=lambda: NOW)
    store.issue(spec())
    lease = store.acquire(spec().idempotency_key, owner="worker-a", lease_seconds=60)
    with pytest.raises(AtomicConflict, match="LEASE_HELD"):
        store.acquire(spec().idempotency_key, owner="worker-b", lease_seconds=60)
    with pytest.raises(FenceViolation, match="STALE_OR_FOREIGN"):
        store.transition(
            spec().idempotency_key,
            owner="worker-a",
            fencing_token=lease.fencing_token - 1,
            state=WorkState.READBACK_REQUIRED,
        )


def test_uncertain_effect_requires_readback_state_before_verified_success():
    store = ResidentExecutionStore(InMemoryAtomicDocumentBackend(), clock=lambda: NOW)
    store.issue(spec(effect_class="EXTERNAL_EFFECT"))
    lease = store.acquire(spec().idempotency_key, owner="worker-a", lease_seconds=60)
    with pytest.raises(ValueError, match="REQUIRES_READBACK_BEFORE_SUCCESS"):
        store.transition(
            spec().idempotency_key,
            owner="worker-a",
            fencing_token=lease.fencing_token,
            state=WorkState.SUCCEEDED,
            result_ref="unverified:ack",
            proof_refs=("proof:protocol-only",),
        )
    pending = store.transition(
        spec().idempotency_key,
        owner="worker-a",
        fencing_token=lease.fencing_token,
        state=WorkState.READBACK_REQUIRED,
    )
    with pytest.raises(ValueError, match="SUCCESS_REQUIRES_RESULT_AND_PROOF"):
        store.transition(
            spec().idempotency_key,
            owner="worker-a",
            fencing_token=pending.fencing_token,
            state=WorkState.SUCCEEDED,
        )
    done = store.transition(
        spec().idempotency_key,
        owner="worker-a",
        fencing_token=pending.fencing_token,
        state=WorkState.SUCCEEDED,
        result_ref="provider:readback-1",
        proof_refs=("proof:semantic",),
    )
    assert done.state is WorkState.SUCCEEDED
    with pytest.raises(AtomicConflict, match="TERMINAL_WORK_IS_IMMUTABLE"):
        store.transition(
            spec().idempotency_key,
            owner="worker-a",
            fencing_token=done.fencing_token,
            state=WorkState.FAILED,
            failure_fingerprint="late-conflict",
        )


def test_admission_applies_capacity_queue_and_saturation_backpressure():
    gate = WorkAdmissionController(max_active=2, max_queued=1)
    assert gate.decide(AdmissionSnapshot(4, 1, 0)).state == "ADMITTED"
    assert gate.decide(AdmissionSnapshot(4, 2, 0)).state == "QUEUED_BACKPRESSURE"
    assert gate.decide(AdmissionSnapshot(4, 2, 1)).state == "REJECTED_SATURATED"


def test_negative_cache_requires_determinism_and_invalidates_by_epoch():
    cache = DurableResultCache(InMemoryAtomicDocumentBackend(), clock=lambda: NOW)
    record = ResultCacheRecord(
        cache_key="semantic-task",
        outcome="DETERMINISTIC_FAILURE",
        payload_ref="failure:compiler-v1",
        proof_refs=("proof:fixture",),
        invalidation_key="source:abc|provider:1",
        expires_at=NOW + 60,
        deterministic=True,
    )
    cache.record(record, effect_class="NO_EFFECT")
    assert cache.lookup("semantic-task", invalidation_key="source:abc|provider:1") == record
    assert cache.lookup("semantic-task", invalidation_key="source:def|provider:1") is None
    with pytest.raises(ValueError, match="EXTERNAL_EFFECT"):
        cache.record(record, effect_class="EXTERNAL_EFFECT")


def test_desired_state_reconciler_is_managed_field_bounded():
    result = DesiredStateReconciler().compare(
        {"image": "sha256:new", "traffic": 0, "owner": "fuse"},
        {"image": "sha256:old", "traffic": 0, "owner": "foreign"},
        managed_fields=("image", "traffic"),
    )
    assert result.state == "DRIFT_DETECTED"
    assert result.actions == ("SET:image",)
    assert "owner" not in result.drift


class ResidentExecutionSubstrateUnittestBridge(unittest.TestCase):
    """Expose the focused pytest functions to ProofOS's unittest_glob runner."""

    test_provider_contract_conformance_court = staticmethod(
        test_provider_contract_conformance_court
    )
    test_work_issue_is_idempotent_but_semantic_collision_fails_closed = staticmethod(
        test_work_issue_is_idempotent_but_semantic_collision_fails_closed
    )
    test_lease_fencing_blocks_foreign_and_stale_workers = staticmethod(
        test_lease_fencing_blocks_foreign_and_stale_workers
    )
    test_uncertain_effect_requires_readback_state_before_verified_success = staticmethod(
        test_uncertain_effect_requires_readback_state_before_verified_success
    )
    test_admission_applies_capacity_queue_and_saturation_backpressure = staticmethod(
        test_admission_applies_capacity_queue_and_saturation_backpressure
    )
    test_negative_cache_requires_determinism_and_invalidates_by_epoch = staticmethod(
        test_negative_cache_requires_determinism_and_invalidates_by_epoch
    )
    test_desired_state_reconciler_is_managed_field_bounded = staticmethod(
        test_desired_state_reconciler_is_managed_field_bounded
    )
