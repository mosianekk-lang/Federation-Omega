from datetime import datetime, timezone

import pytest

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
        payload={"state": "ACTIVE"},
    )
    data.update(overrides)
    return MeshEnvelope(**data)


def receipt(**overrides):
    data = dict(
        event_id="EV-001",
        target_node="A",
        status="SEMANTICALLY_VERIFIED",
        transport_ok=True,
        semantic_match=True,
        readback_present=True,
        state_changed=True,
    )
    data.update(overrides)
    return DeliveryReceipt(**data)


def test_broadcast_routes_to_all_eligible_nodes():
    router = MeshRouter([node("A"), node("B")])
    routes = router.route(envelope())
    assert {route.node_id for route in routes} == {"A", "B"}


def test_targeted_route_only_hits_named_target():
    router = MeshRouter([node("A"), node("B")])
    routes = router.route(envelope(targets=("B",)))
    assert [route.node_id for route in routes] == ["B"]


def test_unhealthy_or_stale_node_is_excluded():
    router = MeshRouter(
        [
            node("A", health="FAILED"),
            node("B", health="STALE"),
            node("C"),
        ]
    )
    assert [route.node_id for route in router.route(envelope())] == ["C"]


def test_degraded_node_uses_explicit_fallback_for_internal_work():
    router = MeshRouter(
        [
            node(
                "A",
                health="DEGRADED",
                fallback_adapter="adapter:A:fallback",
            )
        ]
    )
    route = router.best_route(envelope())
    assert route is not None
    assert route.adapter == "adapter:A:fallback"
    assert route.is_fallback is True


def test_degraded_node_is_excluded_from_external_effect_work():
    router = MeshRouter(
        [
            node(
                "A",
                health="DEGRADED",
                fallback_adapter="adapter:A:fallback",
            )
        ]
    )
    assert (
        router.route(
            envelope(authority_required="A2_REVERSIBLE_EXTERNAL")
        )
        == ()
    )


def test_capability_mismatch_is_excluded():
    router = MeshRouter(
        [node("A", capabilities=("READ",)), node("B")]
    )
    assert [route.node_id for route in router.route(envelope())] == ["B"]


def test_authority_never_expands():
    router = MeshRouter(
        [node("A", authority_ceiling="A1_INTERNAL")]
    )
    assert (
        router.route(
            envelope(authority_required="A2_REVERSIBLE_EXTERNAL")
        )
        == ()
    )


def test_unknown_node_authority_fails_closed_at_admission():
    with pytest.raises(ValueError, match="unknown classification"):
        node("A", authority_ceiling="UNKNOWN")


def test_unknown_node_privacy_fails_closed_at_admission():
    with pytest.raises(ValueError, match="unknown classification"):
        node("A", privacy_ceiling="UNKNOWN")


def test_invalid_node_metrics_fail_closed():
    with pytest.raises(ValueError, match="freshness"):
        node("A", freshness=1.2)
    with pytest.raises(ValueError, match="latency"):
        node("A", latency=-1)


def test_privacy_ceiling_is_enforced():
    router = MeshRouter(
        [node("A", privacy_ceiling="P1_INTERNAL")]
    )
    assert (
        router.route(envelope(privacy_class="P2_PRIVATE"))
        == ()
    )


def test_effectful_route_requires_fresh_strong_proof():
    router = MeshRouter(
        [
            node(
                "A",
                freshness=0.70,
                proof_strength=0.70,
            ),
            node(
                "B",
                freshness=0.95,
                proof_strength=0.95,
            ),
        ]
    )
    routes = router.route(
        envelope(authority_required="A2_REVERSIBLE_EXTERNAL")
    )
    assert [route.node_id for route in routes] == ["B"]


def test_unbound_node_is_not_routable():
    router = MeshRouter([node("A", adapter="UNBOUND")])
    assert router.route(envelope()) == ()


def test_duplicate_event_is_suppressed_by_default():
    plane = MeshControlPlane(
        MeshRouter([node("A")]),
        DeliveryLedger(),
    )
    first = plane.publish(envelope())
    second = plane.publish(envelope())
    assert first["admitted"] is True
    assert first["route_count"] == 1
    assert second["admitted"] is False
    assert second["route_count"] == 0


def test_idempotency_key_cannot_be_reused_with_different_payload():
    ledger = DeliveryLedger()
    assert ledger.admit(envelope()) is True
    with pytest.raises(ValueError, match="different payload"):
        ledger.admit(envelope(payload={"state": "DIFFERENT"}))


def test_idempotency_key_cannot_be_reused_with_different_event_id():
    ledger = DeliveryLedger()
    assert ledger.admit(envelope()) is True
    with pytest.raises(ValueError, match="different event_id"):
        ledger.admit(envelope(event_id="EV-OTHER"))


def test_raw_secret_like_payload_keys_fail_closed():
    with pytest.raises(ValueError, match="raw secret-like"):
        envelope(payload={"api_key": "do-not-store"}).validate()


def test_raw_secret_value_pattern_fails_closed_even_under_innocent_key():
    with pytest.raises(ValueError, match="raw secret-like"):
        envelope(
            payload={"configuration": "Bearer abcdefghijklmnopqrstuvwxyz"}
        ).validate()


def test_opaque_secret_reference_is_allowed():
    envelope(
        payload={
            "secret_ref": "projects/p/secrets/gemini-key/versions/latest"
        }
    ).validate()


def test_dead_letter_after_bounded_retry_budget():
    ledger = DeliveryLedger(max_attempts=3)
    assert ledger.record_attempt("EV-1", "NODE") == "RETRYABLE"
    assert ledger.record_attempt("EV-1", "NODE") == "RETRYABLE"
    assert ledger.record_attempt("EV-1", "NODE") == "DEAD_LETTER"


def test_dead_letter_can_be_explicitly_rearmed_for_replay():
    ledger = DeliveryLedger(max_attempts=2)
    ledger.record_attempt("EV-1", "NODE")
    assert (
        ledger.record_attempt("EV-1", "NODE")
        == "DEAD_LETTER"
    )
    assert (
        ledger.replay_dead_letter("EV-1", "NODE")
        == "REPLAY_READY"
    )
    assert ledger.record_attempt("EV-1", "NODE") == "RETRYABLE"


def test_non_dead_letter_replay_fails_closed():
    ledger = DeliveryLedger(max_attempts=3)
    ledger.record_attempt("EV-1", "NODE")
    with pytest.raises(ValueError, match="dead-letter"):
        ledger.replay_dead_letter("EV-1", "NODE")


def test_resume_incomplete_after_crash_snapshot():
    plane = MeshControlPlane(
        MeshRouter([node("A"), node("B")]),
        DeliveryLedger(),
    )
    first = plane.publish(envelope())
    assert first["route_count"] == 2

    verified_a = receipt(target_node="A")
    assert (
        plane.ledger.record_receipt(verified_a)
        == "SEMANTICALLY_VERIFIED"
    )

    restored = DeliveryLedger.from_snapshot(
        plane.ledger.snapshot()
    )
    resumed_plane = MeshControlPlane(
        MeshRouter([node("A"), node("B")]),
        restored,
    )
    resumed = resumed_plane.resume_incomplete(envelope())
    assert resumed["resumed"] is True
    assert [route.node_id for route in resumed["routes"]] == ["B"]


def test_resume_rejects_changed_payload():
    plane = MeshControlPlane(
        MeshRouter([node("A")]),
        DeliveryLedger(),
    )
    plane.publish(envelope())
    with pytest.raises(ValueError, match="does not match"):
        plane.resume_incomplete(
            envelope(payload={"state": "DIFFERENT"})
        )


def test_descriptor_collision_requires_explicit_supersession():
    router = MeshRouter([node("A")])
    with pytest.raises(ValueError, match="replacement version"):
        router.register(node("A", reliability=0.5))


def test_descriptor_supersession_is_versioned_and_hash_bound():
    old = node("A")
    router = MeshRouter([old])
    replacement = node(
        "A",
        reliability=0.8,
        descriptor_version=2,
        supersedes_descriptor_hash=old.descriptor_hash,
    )
    router.register(replacement)
    assert router.node("A") == replacement


def test_wrong_supersession_hash_fails_closed():
    old = node("A")
    router = MeshRouter([old])
    with pytest.raises(ValueError, match="supersedes hash"):
        router.register(
            node(
                "A",
                reliability=0.8,
                descriptor_version=2,
                supersedes_descriptor_hash="0" * 64,
            )
        )


def test_semantic_readback_is_required_for_promotion():
    current = receipt(semantic_match=False)
    assert (
        MeshControlPlane.promotion_gate(current)
        == "SEMANTIC_FAILURE"
    )


def test_consequential_promotion_requires_rollback():
    current = receipt(rollback_present=False)
    assert (
        MeshControlPlane.promotion_gate(
            current,
            consequential=True,
        )
        == "ROLLBACK_REQUIRED"
    )


def test_verified_mutation_receipt_closes_nonconsequential_gate():
    assert (
        MeshControlPlane.promotion_gate(receipt())
        == "VERIFIED_COMPLETE"
    )


def test_verified_read_only_receipt_requires_no_state_change():
    current = receipt(
        state_changed=False,
        expected_state_change=False,
    )
    assert current.verified is True
    assert (
        MeshControlPlane.promotion_gate(current)
        == "VERIFIED_COMPLETE"
    )


def test_read_only_receipt_rejects_unexpected_mutation():
    current = receipt(
        state_changed=True,
        expected_state_change=False,
    )
    assert current.verified is False
    assert (
        MeshControlPlane.promotion_gate(current)
        == "UNEXPECTED_STATE_CHANGE"
    )


def test_mutation_receipt_requires_expected_state_delta():
    current = receipt(
        state_changed=False,
        expected_state_change=True,
    )
    assert (
        MeshControlPlane.promotion_gate(current)
        == "EXPECTED_STATE_DELTA_MISSING"
    )


def test_postcondition_mismatch_fails_closed():
    current = receipt(postcondition_match=False)
    assert (
        MeshControlPlane.promotion_gate(current)
        == "POSTCONDITION_MISMATCH"
    )


def test_new_node_can_join_without_router_rebuild():
    plane = MeshControlPlane()
    plane.enroll(node("A"))
    plane.enroll(node("B"))
    assert {
        route.node_id
        for route in plane.router.route(envelope())
    } == {"A", "B"}


def test_best_route_prefers_reliable_fresh_low_burden_node():
    router = MeshRouter(
        [
            node(
                "A",
                reliability=0.6,
                freshness=0.6,
                proof_strength=0.6,
                executability=0.6,
                latency=6,
                owner_burden=0.5,
            ),
            node(
                "B",
                reliability=0.99,
                freshness=0.99,
                proof_strength=0.99,
                executability=0.99,
                latency=0.2,
                owner_burden=0,
            ),
        ]
    )
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
    traceparent = (
        "00-4bf92f3577b34da6a3ce929d0e0e4736-"
        "00f067aa0ba902b7-01"
    )
    event = envelope(
        traceparent=traceparent,
        tracestate="vendor=value",
    ).to_cloudevent()
    assert event["traceparent"] == traceparent
    assert event["tracestate"] == "vendor=value"


def test_invalid_traceparent_fails_closed():
    with pytest.raises(ValueError, match="traceparent"):
        envelope(traceparent="not-a-trace").validate()


def test_diverse_routes_select_distinct_failure_domains():
    router = MeshRouter(
        [
            node("A", failure_domain="cell-1", reliability=0.99),
            node("B", failure_domain="cell-1", reliability=0.95),
            node("C", failure_domain="cell-2", reliability=0.90),
        ]
    )
    routes = router.diverse_routes(envelope(), max_routes=2)
    assert len(routes) == 2
    assert {
        route.failure_domain for route in routes
    } == {"cell-1", "cell-2"}


def test_failed_domain_can_be_excluded_without_freezing_other_routes():
    router = MeshRouter(
        [
            node("A", failure_domain="cell-1"),
            node("B", failure_domain="cell-2"),
        ]
    )
    routes = router.route(
        envelope(),
        excluded_failure_domains=("cell-1",),
    )
    assert [route.node_id for route in routes] == ["B"]


def test_observability_gate_requires_verified_proof_first():
    current = DeliveryReceipt(
        event_id="EV-1",
        target_node="NODE",
        status="ACKED",
        transport_ok=True,
        semantic_match=False,
        readback_present=True,
        state_changed=True,
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        latency_ms=100,
        attempt_count=1,
        incremental_cost_units=0.0,
        owner_action_count=0,
        failure_domain="cell-1",
    )
    assert (
        MeshControlPlane.observability_gate(
            current,
            max_latency_ms=1000,
            max_attempts=3,
        )
        == "PROOF_NOT_VERIFIED"
    )


def test_observability_gate_requires_complete_telemetry():
    current = receipt()
    assert (
        MeshControlPlane.observability_gate(
            current,
            max_latency_ms=1000,
            max_attempts=3,
        )
        == "TELEMETRY_INCOMPLETE"
    )


def test_observability_gate_accepts_within_target_receipt():
    current = receipt(
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        latency_ms=120,
        attempt_count=1,
        incremental_cost_units=0.0,
        owner_action_count=0,
        failure_domain="cell-1",
        observed_at=datetime.now(timezone.utc),
    )
    assert (
        MeshControlPlane.observability_gate(
            current,
            max_latency_ms=1000,
            max_attempts=3,
        )
        == "OBSERVABLE_WITHIN_TARGET"
    )


def test_observability_gate_surfaces_latency_and_owner_burden():
    common = dict(
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        attempt_count=1,
        incremental_cost_units=0.0,
        failure_domain="cell-1",
    )
    slow = receipt(
        latency_ms=2000,
        owner_action_count=0,
        **common,
    )
    assert (
        MeshControlPlane.observability_gate(
            slow,
            max_latency_ms=1000,
            max_attempts=3,
        )
        == "SLO_LATENCY_BREACH"
    )
    burden = receipt(
        latency_ms=100,
        owner_action_count=1,
        **common,
    )
    assert (
        MeshControlPlane.observability_gate(
            burden,
            max_latency_ms=1000,
            max_attempts=3,
        )
        == "OWNER_BURDEN_BREACH"
    )
