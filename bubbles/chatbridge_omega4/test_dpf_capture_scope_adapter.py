import pytest

from .design_provenance_fabric import CaptureState, CleanupDisposition, ReconciliationTrigger
from .dpf_capture_scope_adapter import (
    ObservableCaptureScopeError,
    ObservableCaptureScopeLedger,
    ObservableScopeDesignProvenanceBridge,
    bind_observable_design_provenance_fabric,
)


class FakeLedger:
    def __init__(self, proof, transcript):
        self.proof = dict(proof)
        self.transcript = list(transcript)

    def verify(self, conversation_key):
        assert conversation_key == self.proof["conversation_key"]
        return dict(self.proof)

    def reconstruct(self, conversation_key, *, require_exact=False):
        assert conversation_key == self.proof["conversation_key"]
        return {
            "conversation_key": conversation_key,
            "transcript": [dict(x) for x in self.transcript],
            "context_manifest": {
                "missing_ranges": self.proof.get("missing_ranges", []),
                "unavailable_sequences": self.proof.get("unavailable_sequences", []),
                "unresolved_artifacts": self.proof.get("unresolved_artifacts", []),
            },
        }


class FakeRuntime:
    def __init__(self, ledger):
        self.full_fidelity = ledger


def bounded_proof():
    return {
        "conversation_key": "chat-rendered-1",
        "namespace_key": "sovara",
        "source_provider": "CHATGPT_RENDERED_DOM",
        "event_count": 4,
        "first_sequence": 1,
        "last_sequence": 4,
        "expected_first_sequence": 1,
        "expected_last_sequence": None,
        "missing_ranges": [],
        "unavailable_sequences": [],
        "unresolved_artifacts": [],
        "chain_head_hash": "a" * 64,
        "merkle_root": "b" * 64,
        "integrity_state": "PASS_BOUNDED",
        "restore_mode": "BOUNDED_TRANSCRIPT_RESTORE",
        "exact_context_complete": False,
    }


def transcript():
    return [
        {"sequence": 1, "event_type": "MESSAGE", "execution_state": "OBSERVED", "content_hash": "h1", "artifacts": []},
        {"sequence": 2, "event_type": "MESSAGE", "execution_state": "OBSERVED", "content_hash": "h2", "artifacts": []},
        {"sequence": 3, "event_type": "MESSAGE", "execution_state": "OBSERVED", "content_hash": "h3", "artifacts": []},
        {"sequence": 4, "event_type": "MESSAGE", "execution_state": "OBSERVED", "content_hash": "h4", "artifacts": []},
    ]


def rendered_evidence(**overrides):
    value = {
        "capture_scope": "RENDERED_DOM",
        "source_provider": "CHATGPT_RENDERED_DOM",
        "provider_native_complete": False,
        "exact_rendered_transcript_complete": True,
        "integrity_state": "HASH_CHAIN_VERIFIED",
        "missing_ranges": [],
        "unresolved_artifacts": [],
        "first_source_sequence": 1,
        "last_source_sequence": 4,
        "latest_rendered_message_count": 4,
        "captured_event_count": 4,
        "evidence_fingerprint": "rendered-proof-1",
    }
    value.update(overrides)
    return value


def test_gap_free_rendered_scope_can_be_dpf_complete_without_provider_native_claim():
    base = FakeLedger(bounded_proof(), transcript())
    scoped = ObservableCaptureScopeLedger(base, lambda _: rendered_evidence())
    proof = scoped.verify("chat-rendered-1")
    assert proof["exact_context_complete"] is True
    assert proof["dpf_observable_complete"] is True
    assert proof["dpf_provider_native_complete"] is False
    assert proof["dpf_capture_scope"] == "FULL_OBSERVABLE_RENDERED_CHAT"
    assert "HIDDEN_EVENTS_NOT_INFERRED" in proof["dpf_scope_truth_boundary"]


def test_observable_bridge_allows_reconciliation_and_derived_compaction_only_with_archive():
    base = FakeLedger(bounded_proof(), transcript())
    bridge = ObservableScopeDesignProvenanceBridge(
        ObservableCaptureScopeLedger(base, lambda _: rendered_evidence())
    )
    manifest = bridge.build_raw_manifest(
        lab_id="DLAB-DPF-001",
        conversation_key="chat-rendered-1",
        source_locator="chatbridge://rendered/chat-rendered-1",
    )
    rec = bridge.reconcile(manifest, trigger=ReconciliationTrigger.END_OF_CHAT)
    plan = bridge.plan_compaction(manifest, rec, archive_pointer_available=True)
    assert manifest.capture_state == CaptureState.FULL_CAPTURE_VERIFIED
    assert "FULL_OBSERVABLE_RENDERED_CHAT_VERIFIED" in manifest.truth_boundary
    assert "PROVIDER_NATIVE_COMPLETE_FALSE" in manifest.truth_boundary
    assert "FULL_CAPTURE_NOT_YET_VERIFIED" not in rec.unresolved_gates
    assert plan.cleanup_eligible is True
    assert plan.canonical_raw_disposition == CleanupDisposition.PRESERVE_CANONICAL_RAW


def test_rendered_scope_with_gap_remains_incomplete():
    base = FakeLedger(bounded_proof(), transcript())
    scoped = ObservableCaptureScopeLedger(
        base,
        lambda _: rendered_evidence(missing_ranges=[[3, 3]]),
    )
    proof = scoped.verify("chat-rendered-1")
    assert proof["exact_context_complete"] is False
    assert proof["dpf_observable_complete"] is False
    assert proof["dpf_provider_native_complete"] is False
    assert proof["dpf_capture_scope"] == "BOUNDED_RENDERED_DOM"


def test_rendered_scope_cannot_self_declare_provider_native_complete():
    base = FakeLedger(bounded_proof(), transcript())
    scoped = ObservableCaptureScopeLedger(
        base,
        lambda _: rendered_evidence(provider_native_complete=True),
    )
    with pytest.raises(ObservableCaptureScopeError):
        scoped.verify("chat-rendered-1")


def test_provider_native_exact_remains_exact_without_scope_override():
    proof = bounded_proof()
    proof.update({
        "integrity_state": "PASS_EXACT",
        "restore_mode": "EXACT_TRANSCRIPT_RESTORE",
        "exact_context_complete": True,
        "expected_last_sequence": 4,
    })
    base = FakeLedger(proof, transcript())
    scoped = ObservableCaptureScopeLedger(base, lambda _: None)
    result = scoped.verify("chat-rendered-1")
    assert result["dpf_provider_native_complete"] is True
    assert result["dpf_observable_complete"] is True
    assert result["dpf_capture_scope"] == "PROVIDER_NATIVE_EXACT"


def test_binder_keeps_raw_ledger_and_requires_scope_resolver():
    ledger = FakeLedger(bounded_proof(), transcript())
    bridge = bind_observable_design_provenance_fabric(
        FakeRuntime(ledger), evidence_resolver=lambda _: rendered_evidence()
    )
    assert isinstance(bridge, ObservableScopeDesignProvenanceBridge)
    assert bridge.ledger.ledger is ledger


def test_contract_separates_observable_and_provider_native_completeness():
    contract = ObservableScopeDesignProvenanceBridge.contract()
    assert contract["completeness_dimensions"] == [
        "FULL_OBSERVABLE_RENDERED_CHAT",
        "PROVIDER_NATIVE_EXACT",
    ]
    assert "hidden provider-native events" in contract["observable_scope_truth"].lower()
