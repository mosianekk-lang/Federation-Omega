from federation_omni_mesh_v1 import (
    DeliveryLedger,
    DeliveryReceipt,
    MeshControlPlane,
    MeshEnvelope,
    MeshRouter,
    NodeDescriptor,
)


def node(node_id: str, **overrides):
    data = dict(
        node_id=node_id,
        name=node_id,
        node_type="SYSTEM",
        provider="FEDERATION",
        capabilities=("SYNC", "STATUS"),
        authority_ceiling="A2_REVERSIBLE_EXTERNAL",
        privacy_ceiling="P2_PRIVATE",
        adapter=f"adapter:{node_id}",
    )
    data.update(overrides)
    return NodeDescriptor(**data)


def envelope(**overrides):
    data = dict(
        event_id="EV-001",
        event_type="STATE_DELTA",
        source="SOVARA",
        topic="state.delta.v1",
        idempotency_key="IDEMP-001",
        correlation_id="CORR-001",
        capability_required="SYNC",
        authority_required="A1_INTERNAL",
        privacy_class="P1_INTERNAL",
        payload={"state":"ACTIVE"},
    )
    data.update(overrides)
    return MeshEnvelope(**data)


def test_broadcast_routes_to_all_eligible_nodes():
    router = MeshRouter([node("A"), node("B")])
    routes = router.route(envelope())
    assert {route.node_id for route in routes} == {"A", "B"}


def test_targeted_route_only_hits_named_target():
    router = MeshRouter([node("A"), node("B")])
    routes = router.route(envelope(targets=("B",)))
    assert [route.node_id for route in routes] == ["B"]


def test_unhealthy_node_is_excluded():
    router = MeshRouter([node("A", health="FAILED"), node("B")])
    assert [route.node_id for route in router.route(envelope())] == ["B"]


def test_capability_mismatch_is_excluded():
    router = MeshRouter([node("A", capabilities=("READ",)), node("B")])
    assert [route.node_id for route in router.route(envelope())] == ["B"]


def test_authority_never_expands():
    router = MeshRouter([node("A", authority_ceiling="A1_INTERNAL")])
    assert router.route(envelope(authority_required="A2_REVERSIBLE_EXTERNAL")) == ()


def test_privacy_ceiling_is_enforced():
    router = MeshRouter([node("A", privacy_ceiling="P1_INTERNAL")])
    assert router.route(envelope(privacy_class="P2_PRIVATE")) == ()


def test_duplicate_event_is_suppressed():
    plane = MeshControlPlane(MeshRouter([node("A")]), DeliveryLedger())
    first = plane.publish(envelope())
    second = plane.publish(envelope())
    assert first["admitted"] is True
    assert first["route_count"] == 1
    assert second["admitted"] is False
    assert second["route_count"] == 0


def test_idempotency_key_cannot_be_reused_with_different_payload():
    ledger = DeliveryLedger()
    assert ledger.admit(envelope()) is True
    try:
        ledger.admit(envelope(payload={"state":"DIFFERENT"}))
    except ValueError as exc:
        assert "different payload" in str(exc)
    else:
        raise AssertionError("expected idempotency collision to fail")


def test_raw_secret_like_payload_keys_fail_closed():
    try:
        envelope(payload={"api_key":"do-not-store"}).validate()
    except ValueError as exc:
        assert "raw secret-like" in str(exc)
    else:
        raise AssertionError("expected raw secret rejection")


def test_dead_letter_after_bounded_retry_budget():
    ledger = DeliveryLedger(max_attempts=3)
    assert ledger.record_attempt("EV-1", "NODE") == "RETRYABLE"
    assert ledger.record_attempt("EV-1", "NODE") == "RETRYABLE"
    assert ledger.record_attempt("EV-1", "NODE") == "DEAD_LETTER"


def test_dead_letter_can_be_explicitly_rearmed_for_replay():
    ledger = DeliveryLedger(max_attempts=2)
    ledger.record_attempt("EV-1", "NODE")
    assert ledger.record_attempt("EV-1", "NODE") == "DEAD_LETTER"
    assert ledger.replay_dead_letter("EV-1", "NODE") == "REPLAY_READY"
    assert ledger.record_attempt("EV-1", "NODE") == "RETRYABLE"


def test_non_dead_letter_replay_fails_closed():
    ledger = DeliveryLedger(max_attempts=3)
    ledger.record_attempt("EV-1", "NODE")
    try:
        ledger.replay_dead_letter("EV-1", "NODE")
    except ValueError as exc:
        assert "dead-letter" in str(exc)
    else:
        raise AssertionError("expected non-DLQ replay to fail")


def test_semantic_readback_is_required_for_promotion():
    receipt = DeliveryReceipt(
        event_id="EV-1",
        target_node="NODE",
        status="ACKED",
        transport_ok=True,
        semantic_match=False,
        readback_present=True,
        state_changed=True,
    )
    assert MeshControlPlane.promotion_gate(receipt) == "SEMANTIC_FAILURE"


def test_consequential_promotion_requires_rollback():
    receipt = DeliveryReceipt(
        event_id="EV-1",
        target_node="NODE",
        status="SEMANTICALLY_VERIFIED",
        transport_ok=True,
        semantic_match=True,
        readback_present=True,
        state_changed=True,
        rollback_present=False,
    )
    assert MeshControlPlane.promotion_gate(receipt, consequential=True) == "ROLLBACK_REQUIRED"


def test_verified_receipt_closes_nonconsequential_gate():
    receipt = DeliveryReceipt(
        event_id="EV-1",
        target_node="NODE",
        status="SEMANTICALLY_VERIFIED",
        transport_ok=True,
        semantic_match=True,
        readback_present=True,
        state_changed=True,
    )
    assert MeshControlPlane.promotion_gate(receipt) == "VERIFIED_COMPLETE"


def test_new_node_can_join_without_router_rebuild():
    plane = MeshControlPlane()
    plane.enroll(node("A"))
    plane.enroll(node("B"))
    assert {route.node_id for route in plane.router.route(envelope())} == {"A", "B"}


def test_best_route_prefers_reliable_fresh_low_burden_node():
    router = MeshRouter([
        node("A", reliability=.6, freshness=.6, proof_strength=.6, executability=.6, latency=6, owner_burden=.5),
        node("B", reliability=.99, freshness=.99, proof_strength=.99, executability=.99, latency=.2, owner_burden=0),
    ])
    assert router.best_route(envelope()).node_id == "B"


def test_cloudevents_aligned_serialization_has_required_context():
    event = envelope().to_cloudevent()
    assert event["specversion"] == "1.0"
    assert event["id"] == "EV-001"
    assert event["source"] == "urn:federation:sovara"
    assert event["type"] == "STATE_DELTA"
    assert event["subject"] == "state.delta.v1"
    assert event["correlationid"] == "CORR-001"
    assert event["payloadhash"] == envelope().payload_hash


def test_w3c_trace_context_is_preserved_in_cloudevent():
    traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    event = envelope(traceparent=traceparent, tracestate="vendor=value").to_cloudevent()
    assert event["traceparent"] == traceparent
    assert event["tracestate"] == "vendor=value"


def test_invalid_traceparent_fails_closed():
    try:
        envelope(traceparent="not-a-trace").validate()
    except ValueError as exc:
        assert "traceparent" in str(exc)
    else:
        raise AssertionError("expected invalid trace context to fail")


def test_diverse_routes_select_distinct_failure_domains():
    router = MeshRouter([
        node("A", failure_domain="cell-1", reliability=.99),
        node("B", failure_domain="cell-1", reliability=.95),
        node("C", failure_domain="cell-2", reliability=.90),
    ])
    routes = router.diverse_routes(envelope(), max_routes=2)
    assert len(routes) == 2
    assert {route.failure_domain for route in routes} == {"cell-1", "cell-2"}


def test_failed_domain_can_be_excluded_without_freezing_other_routes():
    router = MeshRouter([
        node("A", failure_domain="cell-1"),
        node("B", failure_domain="cell-2"),
    ])
    routes = router.route(envelope(), excluded_failure_domains=("cell-1",))
    assert [route.node_id for route in routes] == ["B"]


def test_observability_gate_requires_complete_telemetry():
    receipt = DeliveryReceipt(
        event_id="EV-1", target_node="NODE", status="ACKED",
        transport_ok=True, semantic_match=True, readback_present=True, state_changed=True,
    )
    assert MeshControlPlane.observability_gate(receipt, max_latency_ms=1000, max_attempts=3) == "TELEMETRY_INCOMPLETE"


def test_observability_gate_accepts_within_target_receipt():
    receipt = DeliveryReceipt(
        event_id="EV-1", target_node="NODE", status="ACKED",
        transport_ok=True, semantic_match=True, readback_present=True, state_changed=True,
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736", latency_ms=120,
        attempt_count=1, incremental_cost_units=0.0, owner_action_count=0,
        failure_domain="cell-1",
    )
    assert MeshControlPlane.observability_gate(receipt, max_latency_ms=1000, max_attempts=3) == "OBSERVABLE_WITHIN_TARGET"


def test_observability_gate_surfaces_latency_and_owner_burden():
    common = dict(
        event_id="EV-1", target_node="NODE", status="ACKED",
        transport_ok=True, semantic_match=True, readback_present=True, state_changed=True,
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736", attempt_count=1,
        incremental_cost_units=0.0, failure_domain="cell-1",
    )
    slow = DeliveryReceipt(latency_ms=2000, owner_action_count=0, **common)
    assert MeshControlPlane.observability_gate(slow, max_latency_ms=1000, max_attempts=3) == "SLO_LATENCY_BREACH"
    burden = DeliveryReceipt(latency_ms=100, owner_action_count=1, **common)
    assert MeshControlPlane.observability_gate(burden, max_latency_ms=1000, max_attempts=3) == "OWNER_BURDEN_BREACH"
