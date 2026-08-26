from datetime import datetime, timedelta, timezone

import pytest

from .design_provenance_fabric import (
    CaptureNotReconstructable,
    CaptureState,
    CleanupDisposition,
    DesignProvenanceBridge,
    ReconciliationTrigger,
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
        if require_exact and not self.proof.get("exact_context_complete"):
            raise RuntimeError("incomplete")
        return {
            "conversation_key": conversation_key,
            "transcript": [dict(x) for x in self.transcript],
            "context_manifest": {
                "missing_ranges": self.proof.get("missing_ranges", []),
                "unavailable_sequences": self.proof.get("unavailable_sequences", []),
                "unresolved_artifacts": self.proof.get("unresolved_artifacts", []),
            },
        }


def exact_proof():
    return {
        "conversation_key": "chat-1",
        "namespace_key": "sovara",
        "source_provider": "CHATGPT_WEB",
        "event_count": 5,
        "first_sequence": 1,
        "last_sequence": 5,
        "expected_first_sequence": 1,
        "expected_last_sequence": 5,
        "missing_ranges": [],
        "unavailable_sequences": [],
        "unresolved_artifacts": [],
        "chain_head_hash": "a" * 64,
        "merkle_root": "b" * 64,
        "integrity_state": "PASS_EXACT",
        "restore_mode": "EXACT_TRANSCRIPT_RESTORE",
        "exact_context_complete": True,
        "terminal_observed": False,
        "closure_reason": "END_OF_CHAT",
    }


def events():
    return [
        {"sequence": 1, "event_type": "MESSAGE", "execution_state": "OBSERVED", "content_hash": "h1", "artifacts": []},
        {"sequence": 2, "event_type": "DECISION", "execution_state": "OBSERVED", "content_hash": "h2", "artifacts": []},
        {"sequence": 3, "event_type": "TOOL_CALL", "execution_state": "FAILED_VERIFIED", "content_hash": "h3", "artifacts": []},
        {"sequence": 4, "event_type": "CORRECTION", "execution_state": "OBSERVED", "content_hash": "h4", "artifacts": [{"artifact_key": "x"}]},
        {"sequence": 5, "event_type": "TOOL_RESULT", "execution_state": "EXECUTED_VERIFIED", "content_hash": "h3", "artifacts": []},
    ]


def test_exact_capture_manifest_and_reconciliation_and_compaction():
    writes = {"manifest": [], "reconcile": [], "cleanup": []}
    bridge = DesignProvenanceBridge(
        FakeLedger(exact_proof(), events()),
        manifest_sink=writes["manifest"].append,
        reconciliation_sink=writes["reconcile"].append,
        cleanup_sink=writes["cleanup"].append,
    )
    result = bridge.run_cycle(
        lab_id="DLAB-BEF-001",
        conversation_key="chat-1",
        source_locator="chatbridge://chat-1",
        trigger=ReconciliationTrigger.END_OF_CHAT,
        archive_pointer_available=True,
    )
    assert result.manifest.capture_state == CaptureState.FULL_CAPTURE_VERIFIED
    assert result.reconciliation.material_decision_sequences == (2,)
    assert result.reconciliation.failure_sequences == (3,)
    assert result.reconciliation.correction_sequences == (4,)
    assert result.reconciliation.tool_activity_sequences == (3, 5)
    assert result.cleanup_plan.canonical_raw_disposition == CleanupDisposition.PRESERVE_CANONICAL_RAW
    assert result.cleanup_plan.derived_disposition == CleanupDisposition.DEDUPE_DERIVED
    assert result.cleanup_plan.cleanup_eligible is True
    assert result.cleanup_plan.duplicate_groups[0]["sequences"] == [3, 5]
    assert len(writes["manifest"]) == len(writes["reconcile"]) == len(writes["cleanup"]) == 1


def test_incomplete_capture_never_authorizes_cleanup():
    proof = exact_proof()
    proof.update({
        "integrity_state": "PASS_BOUNDED",
        "restore_mode": "BOUNDED_TRANSCRIPT_RESTORE",
        "exact_context_complete": False,
        "expected_last_sequence": 6,
        "missing_ranges": [{"start": 6, "end": 6}],
    })
    bridge = DesignProvenanceBridge(FakeLedger(proof, events()))
    manifest = bridge.build_raw_manifest(
        lab_id="LAB", conversation_key="chat-1", source_locator="chatbridge://chat-1"
    )
    rec = bridge.reconcile(manifest, trigger=ReconciliationTrigger.DAILY_RECONCILIATION)
    plan = bridge.plan_compaction(manifest, rec, archive_pointer_available=True)
    assert manifest.capture_state == CaptureState.CAPTURE_INCOMPLETE
    assert "FULL_CAPTURE_NOT_YET_VERIFIED" in rec.unresolved_gates
    assert plan.cleanup_eligible is False
    assert plan.derived_disposition == CleanupDisposition.HOLD_RECONSTRUCTABILITY


def test_tampered_capture_reconciliation_fails_closed():
    proof = exact_proof()
    proof.update({"integrity_state": "FAIL_HASH_CHAIN", "exact_context_complete": False})
    bridge = DesignProvenanceBridge(FakeLedger(proof, events()))
    manifest = bridge.build_raw_manifest(
        lab_id="LAB", conversation_key="chat-1", source_locator="chatbridge://chat-1"
    )
    assert manifest.capture_state == CaptureState.CAPTURE_REJECTED_TAMPER
    with pytest.raises(CaptureNotReconstructable):
        bridge.reconcile(manifest, trigger=ReconciliationTrigger.END_OF_CHAT)


def test_design_gene_extractor_is_candidate_only():
    def extractor(rows):
        return [{"gene_id": "DG-1", "state": "CANDIDATE", "event_count": len(rows)}]

    bridge = DesignProvenanceBridge(
        FakeLedger(exact_proof(), events()), design_gene_extractor=extractor
    )
    manifest = bridge.build_raw_manifest(
        lab_id="LAB", conversation_key="chat-1", source_locator="cb://1"
    )
    rec = bridge.reconcile(manifest, trigger=ReconciliationTrigger.PRE_PROMOTION)
    assert rec.design_gene_candidates == (
        {"gene_id": "DG-1", "state": "CANDIDATE", "event_count": 5},
    )
    assert "PROMOTION_SEPARATE" in rec.truth_boundary


def test_daily_reconciliation_due_is_deterministic():
    now = datetime(2026, 8, 27, 0, 0, tzinfo=timezone.utc)
    assert DesignProvenanceBridge.daily_reconciliation_due(None, now=now)
    assert not DesignProvenanceBridge.daily_reconciliation_due(
        (now - timedelta(hours=23)).isoformat(), now=now
    )
    assert DesignProvenanceBridge.daily_reconciliation_due(
        (now - timedelta(hours=24)).isoformat(), now=now
    )


def test_contract_keeps_raw_authority_with_chatbridge():
    contract = DesignProvenanceBridge.contract()
    assert contract["raw_authority"] == "CHATBRIDGE_FULL_FIDELITY_LEDGER"
    assert "DERIVED_COPIES_ONLY" in contract["cleanup"]
    assert "NO_PROVIDER_AUTHORITY" in contract["provider_boundary"]
