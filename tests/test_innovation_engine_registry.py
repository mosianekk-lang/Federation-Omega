from pathlib import Path

import pytest

from evidenceops.innovation_engine.registry import InnovationRegistry


def make_registry(tmp_path: Path) -> InnovationRegistry:
    registry = InnovationRegistry(tmp_path / "innovation.db")
    registry.upsert_lane(
        lane_id="LANE-TEST",
        title="Test lane",
        objective="Prove deterministic registry behaviour",
        state="READY",
        priority=100,
        next_action="Run test",
        proof_state="SCAFFOLD",
    )
    return registry


def test_promotion_fails_closed_without_required_evidence(tmp_path: Path) -> None:
    registry = make_registry(tmp_path)
    with pytest.raises(ValueError, match="Proof gate failed"):
        registry.transition("LANE-TEST", "PILOT_APPROVED", ["hypothesis"], "insufficient proof")


def test_transition_creates_verifiable_hash_chain(tmp_path: Path) -> None:
    registry = make_registry(tmp_path)
    first = registry.transition("LANE-TEST", "ACTIVE", ["owner_authority"], "start bounded work")
    second = registry.transition("LANE-TEST", "CHECKPOINTED", ["artifact_hash"], "preserve continuity")

    assert first.previous_hash is None
    assert second.previous_hash == first.receipt_hash
    assert registry.verify_chain() is True


def test_pilot_gate_passes_with_complete_proof(tmp_path: Path) -> None:
    registry = make_registry(tmp_path)
    receipt = registry.transition(
        "LANE-TEST",
        "PILOT_APPROVED",
        ["hypothesis", "success_metrics", "bounded_test", "rollback_plan"],
        "all deterministic pilot gates passed",
    )
    assert receipt.target_state == "PILOT_APPROVED"
    assert registry.verify_chain() is True
