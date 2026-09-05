from datetime import datetime, timedelta, timezone

import pytest

from federation_omni_mesh_v1 import (
    DeliveryReceipt,
    MeshEnvelope,
    MeshRouter,
    NodeDescriptor,
)
from federation_omni_mesh_v1.telemetry import (
    FailureDomainCircuit,
    MeshTelemetryWindow,
    synthetic_scale_probe,
)


def receipt(**overrides):
    data = dict(
        event_id="EV-1",
        target_node="NODE-1",
        status="SEMANTICALLY_VERIFIED",
        transport_ok=True,
        semantic_match=True,
        readback_present=True,
        state_changed=True,
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        latency_ms=100.0,
        attempt_count=1,
        incremental_cost_units=0.0,
        owner_action_count=0,
        failure_domain="cell-1",
        observed_at=datetime.now(timezone.utc),
    )
    data.update(overrides)
    return DeliveryReceipt(**data)


def sync_envelope():
    return MeshEnvelope(
        event_id="EV-1",
        event_type="STATE_DELTA",
        source="SOVARA",
        topic="state.delta.v1",
        idempotency_key="IDEMP-1",
        correlation_id="CORR-1",
        capability_required="SYNC",
        payload={"state": "ACTIVE"},
    )


def node(node_id, domain):
    return NodeDescriptor(
        node_id=node_id,
        name=node_id,
        node_type="SYSTEM",
        provider="FEDERATION",
        capabilities=("SYNC",),
        adapter=f"adapter:{node_id}",
        failure_domain=domain,
    )


def test_synthetic_scale_probe_routes_5000_nodes_without_pairwise_edges():
    result = synthetic_scale_probe(
        node_count=5000,
        failure_domain_count=50,
    )
    assert result.node_count == 5000
    assert result.routed_count == 5000
    assert result.adapter_relationship_count == 5000
    assert result.pairwise_relationship_count == 0
    assert result.all_nodes_routable is True
    assert result.measurement_kind == "IN_MEMORY_ROUTABILITY_ONLY"


def test_scale_probe_rejects_invalid_bounds():
    with pytest.raises(ValueError, match="node_count"):
        synthetic_scale_probe(node_count=0)


def test_failure_domain_circuit_isolates_only_tripped_domain():
    router = MeshRouter(
        [node("A", "cell-1"), node("B", "cell-2")]
    )
    circuit = FailureDomainCircuit()
    circuit.trip("cell-1")
    assert [
        route.node_id
        for route in circuit.route(router, sync_envelope())
    ] == ["B"]
    circuit.reset("cell-1")
    assert {
        route.node_id
        for route in circuit.route(router, sync_envelope())
    } == {"A", "B"}


def test_failure_domain_circuit_rejects_blank_domain():
    circuit = FailureDomainCircuit()
    with pytest.raises(ValueError, match="failure_domain"):
        circuit.trip("")


def test_telemetry_window_computes_p95_cost_owner_actions_and_domains():
    window = MeshTelemetryWindow(
        [
            receipt(latency_ms=10, failure_domain="cell-1"),
            receipt(
                latency_ms=20,
                failure_domain="cell-1",
                incremental_cost_units=0.2,
            ),
            receipt(
                latency_ms=30,
                failure_domain="cell-2",
                owner_action_count=1,
            ),
            receipt(
                latency_ms=40,
                failure_domain="cell-2",
                attempt_count=2,
            ),
        ]
    )
    summary = window.summary()
    assert summary.receipt_count == 4
    assert summary.verified_count == 4
    assert summary.p95_latency_ms == 40.0
    assert summary.max_attempt_count == 2
    assert summary.total_incremental_cost_units == 0.2
    assert summary.unknown_cost_count == 0
    assert summary.total_owner_actions == 1
    assert summary.failure_domain_count == 2
    assert summary.telemetry_complete_count == 4
    assert summary.verified_rate == 1.0


def test_missing_cost_remains_unknown_not_zero():
    window = MeshTelemetryWindow(
        [receipt(incremental_cost_units=None)]
    )
    summary = window.summary()
    assert summary.total_incremental_cost_units is None
    assert summary.unknown_cost_count == 1
    assert "COST_TELEMETRY_UNKNOWN" in window.evaluate_targets(
        max_p95_latency_ms=5000,
        max_attempt_count=3,
    )


def test_telemetry_window_preserves_semantic_failure_as_failure():
    window = MeshTelemetryWindow(
        [
            receipt(),
            receipt(
                status="ACKED",
                semantic_match=False,
            ),
        ]
    )
    summary = window.summary()
    assert summary.verified_count == 1
    assert summary.semantic_failure_count == 1
    findings = window.evaluate_targets(
        max_p95_latency_ms=5000,
        max_attempt_count=3,
        max_semantic_failures=0,
    )
    assert "SEMANTIC_FAILURE_BUDGET_EXCEEDED" in findings
    assert "VERIFIED_RATE_TARGET_MISSED" in findings


def test_transport_and_readback_failures_have_explicit_budgets():
    window = MeshTelemetryWindow(
        [
            receipt(
                status="FAILED",
                transport_ok=False,
            ),
            receipt(
                status="ACKED",
                readback_present=False,
            ),
        ]
    )
    findings = window.evaluate_targets(
        max_p95_latency_ms=5000,
        max_attempt_count=3,
    )
    assert "TRANSPORT_FAILURE_BUDGET_EXCEEDED" in findings
    assert "READBACK_FAILURE_BUDGET_EXCEEDED" in findings


def test_targets_met_requires_complete_measured_receipts():
    window = MeshTelemetryWindow(
        [
            receipt(
                latency_ms=100,
                attempt_count=1,
                owner_action_count=0,
            ),
            receipt(
                latency_ms=200,
                attempt_count=2,
                owner_action_count=0,
                failure_domain="cell-2",
            ),
        ],
        minimum_receipts=2,
    )
    assert window.evaluate_targets(
        max_p95_latency_ms=5000,
        max_attempt_count=3,
        max_owner_actions=0,
    ) == ("TARGETS_MET_FOR_MEASURED_WINDOW",)


def test_insufficient_sample_cannot_fake_slo_attainment():
    window = MeshTelemetryWindow(
        [receipt()],
        minimum_receipts=3,
    )
    findings = window.evaluate_targets(
        max_p95_latency_ms=5000,
        max_attempt_count=3,
    )
    assert "INSUFFICIENT_SAMPLE" in findings
    assert "TARGETS_MET_FOR_MEASURED_WINDOW" not in findings


def test_incomplete_telemetry_cannot_fake_slo_attainment():
    incomplete = DeliveryReceipt(
        event_id="EV-2",
        target_node="NODE-2",
        status="ACKED",
        transport_ok=True,
        semantic_match=True,
        readback_present=True,
        state_changed=True,
    )
    window = MeshTelemetryWindow([incomplete])
    findings = window.evaluate_targets(
        max_p95_latency_ms=5000,
        max_attempt_count=3,
    )
    assert "TELEMETRY_INCOMPLETE" in findings
    assert "COST_TELEMETRY_UNKNOWN" in findings
    assert "TARGETS_MET_FOR_MEASURED_WINDOW" not in findings


def test_window_requires_timestamped_receipts_for_window_claim():
    now = datetime.now(timezone.utc)
    window = MeshTelemetryWindow(
        [
            receipt(observed_at=now),
            receipt(observed_at=None),
        ],
        window_start=now - timedelta(minutes=1),
        window_end=now + timedelta(minutes=1),
        minimum_receipts=2,
    )
    findings = window.evaluate_targets(
        max_p95_latency_ms=5000,
        max_attempt_count=3,
    )
    assert "WINDOW_TIMESTAMPS_INCOMPLETE" in findings


def test_out_of_window_timestamped_receipts_are_excluded():
    now = datetime.now(timezone.utc)
    window = MeshTelemetryWindow(
        [
            receipt(observed_at=now),
            receipt(observed_at=now - timedelta(days=1)),
        ],
        window_start=now - timedelta(minutes=1),
        window_end=now + timedelta(minutes=1),
    )
    assert window.summary().receipt_count == 1


def test_no_measurements_is_explicit_not_success():
    assert MeshTelemetryWindow().evaluate_targets(
        max_p95_latency_ms=5000,
        max_attempt_count=3,
    ) == ("NO_MEASUREMENTS",)
