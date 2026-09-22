from federation.orchestration.cross_model_handoff_reliability import (
    HandoffContract, HandoffObservation, HandoffState, decide
)


def contract():
    return HandoffContract(
        handoff_id="H1", task_id="T1", origin="CHATGPT", target="GEMINI",
        objective_hash="abc", ack_deadline_epoch=100, run_deadline_epoch=200,
        max_same_route_attempts=1, max_total_attempts=3,
    )


def test_queue_waits_before_ack_deadline():
    d = decide(contract(), HandoffObservation(HandoffState.QUEUED, 1, "bus", 50))
    assert d.next_state == HandoffState.QUEUED


def test_missed_ack_forces_route_switch_after_same_route_budget():
    d = decide(contract(), HandoffObservation(HandoffState.QUEUED, 1, "bus", 101))
    assert d.next_state == HandoffState.ROUTE_SWITCH_REQUIRED


def test_acknowledged_but_expired_run_retries_when_budget_remains():
    d = decide(contract(), HandoffObservation(HandoffState.ACKNOWLEDGED, 1, "bus", 201, ack_present=True))
    assert d.next_state == HandoffState.RETRY_DUE


def test_response_receipt_and_semantic_readback_closes():
    d = decide(contract(), HandoffObservation(
        HandoffState.RESPONSE_WRITTEN, 1, "bus", 150,
        response_present=True, receipt_present=True, semantic_readback_ok=True,
    ))
    assert d.next_state == HandoffState.COMPLETE


def test_receipt_without_semantic_readback_does_not_close():
    d = decide(contract(), HandoffObservation(
        HandoffState.RESPONSE_WRITTEN, 1, "bus", 150,
        response_present=True, receipt_present=True, semantic_readback_ok=False,
    ))
    assert d.next_state == HandoffState.RETRY_DUE


def test_owner_only_boundary_surfaces_exactly():
    d = decide(contract(), HandoffObservation(
        HandoffState.QUEUED, 1, "bus", 50,
        owner_only_boundary="fresh OAuth consent required",
    ))
    assert d.next_state == HandoffState.HELD_OWNER_ONLY
    assert d.notify_owner is True
