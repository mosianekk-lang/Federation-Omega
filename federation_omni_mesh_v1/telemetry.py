from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import ceil
from typing import Iterable

from .core import (
    DeliveryReceipt,
    MeshEnvelope,
    MeshRouter,
    NodeDescriptor,
)


@dataclass(frozen=True)
class TelemetrySummary:
    receipt_count: int
    verified_count: int
    transport_failure_count: int
    semantic_failure_count: int
    readback_missing_count: int
    postcondition_failure_count: int
    p95_latency_ms: float | None
    max_attempt_count: int | None
    total_incremental_cost_units: float | None
    unknown_cost_count: int
    total_owner_actions: int
    failure_domain_count: int
    telemetry_complete_count: int
    timestamped_receipt_count: int
    window_start: datetime | None
    window_end: datetime | None

    @property
    def verified_rate(self) -> float | None:
        if self.receipt_count == 0:
            return None
        return self.verified_count / self.receipt_count


class MeshTelemetryWindow:
    """Aggregate proof-safe route telemetry without recording message bodies.

    Missing cost, timestamps or other observations remain unknown rather than
    being silently converted to zero. Optional window boundaries are applied
    only to timestamped receipts; untimestamped receipts remain visible and
    prevent measured-window promotion.
    """

    def __init__(
        self,
        receipts: Iterable[DeliveryReceipt] = (),
        *,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
        minimum_receipts: int = 1,
    ) -> None:
        if minimum_receipts < 1:
            raise ValueError("minimum_receipts must be >= 1")
        for name, value in (
            ("window_start", window_start),
            ("window_end", window_end),
        ):
            if value is not None and value.tzinfo is None:
                raise ValueError(f"{name} must be timezone-aware")
        if (
            window_start is not None
            and window_end is not None
            and window_end < window_start
        ):
            raise ValueError("window_end must not precede window_start")
        self._receipts: list[DeliveryReceipt] = list(receipts)
        self.window_start = window_start
        self.window_end = window_end
        self.minimum_receipts = minimum_receipts

    def add(self, receipt: DeliveryReceipt) -> None:
        self._receipts.append(receipt)

    def _in_window(self, receipt: DeliveryReceipt) -> bool:
        if self.window_start is None and self.window_end is None:
            return True
        if receipt.observed_at is None:
            return True
        if (
            self.window_start is not None
            and receipt.observed_at < self.window_start
        ):
            return False
        if (
            self.window_end is not None
            and receipt.observed_at > self.window_end
        ):
            return False
        return True

    def receipts(self) -> tuple[DeliveryReceipt, ...]:
        return tuple(
            receipt
            for receipt in self._receipts
            if self._in_window(receipt)
        )

    def summary(self) -> TelemetrySummary:
        receipts = self.receipts()
        latencies = sorted(
            receipt.latency_ms
            for receipt in receipts
            if receipt.latency_ms is not None
        )
        p95 = None
        if latencies:
            index = max(0, ceil(0.95 * len(latencies)) - 1)
            p95 = float(latencies[index])
        attempts = [
            receipt.attempt_count
            for receipt in receipts
            if receipt.attempt_count is not None
        ]
        domains = {
            receipt.failure_domain
            for receipt in receipts
            if receipt.failure_domain is not None
        }
        known_costs = [
            receipt.incremental_cost_units
            for receipt in receipts
            if receipt.incremental_cost_units is not None
        ]
        unknown_cost_count = len(receipts) - len(known_costs)
        total_cost = (
            float(sum(known_costs))
            if receipts and unknown_cost_count == 0
            else None
        )
        return TelemetrySummary(
            receipt_count=len(receipts),
            verified_count=sum(
                1 for receipt in receipts if receipt.verified
            ),
            transport_failure_count=sum(
                1 for receipt in receipts if not receipt.transport_ok
            ),
            semantic_failure_count=sum(
                1
                for receipt in receipts
                if receipt.transport_ok and not receipt.semantic_match
            ),
            readback_missing_count=sum(
                1
                for receipt in receipts
                if (
                    receipt.transport_ok
                    and receipt.semantic_match
                    and not receipt.readback_present
                )
            ),
            postcondition_failure_count=sum(
                1
                for receipt in receipts
                if (
                    receipt.transport_ok
                    and receipt.semantic_match
                    and receipt.readback_present
                    and not receipt.postcondition_verified
                )
            ),
            p95_latency_ms=p95,
            max_attempt_count=max(attempts) if attempts else None,
            total_incremental_cost_units=total_cost,
            unknown_cost_count=unknown_cost_count,
            total_owner_actions=sum(
                receipt.owner_action_count or 0
                for receipt in receipts
            ),
            failure_domain_count=len(domains),
            telemetry_complete_count=sum(
                1
                for receipt in receipts
                if receipt.telemetry_complete
            ),
            timestamped_receipt_count=sum(
                1
                for receipt in receipts
                if receipt.observed_at is not None
            ),
            window_start=self.window_start,
            window_end=self.window_end,
        )

    def evaluate_targets(
        self,
        *,
        max_p95_latency_ms: float,
        max_attempt_count: int,
        max_owner_actions: int = 0,
        max_semantic_failures: int = 0,
        max_transport_failures: int = 0,
        max_readback_failures: int = 0,
        max_postcondition_failures: int = 0,
        minimum_verified_rate: float = 1.0,
        minimum_receipts: int | None = None,
    ) -> tuple[str, ...]:
        if not 0.0 <= minimum_verified_rate <= 1.0:
            raise ValueError(
                "minimum_verified_rate must be between 0 and 1"
            )
        summary = self.summary()
        required_receipts = (
            self.minimum_receipts
            if minimum_receipts is None
            else minimum_receipts
        )
        if required_receipts < 1:
            raise ValueError("minimum_receipts must be >= 1")
        findings: list[str] = []
        if summary.receipt_count == 0:
            return ("NO_MEASUREMENTS",)
        if summary.receipt_count < required_receipts:
            findings.append("INSUFFICIENT_SAMPLE")
        if (
            (self.window_start is not None or self.window_end is not None)
            and summary.timestamped_receipt_count < summary.receipt_count
        ):
            findings.append("WINDOW_TIMESTAMPS_INCOMPLETE")
        if summary.telemetry_complete_count < summary.receipt_count:
            findings.append("TELEMETRY_INCOMPLETE")
        if summary.unknown_cost_count:
            findings.append("COST_TELEMETRY_UNKNOWN")
        if (
            summary.p95_latency_ms is None
            or summary.p95_latency_ms > max_p95_latency_ms
        ):
            findings.append("P95_LATENCY_TARGET_MISSED")
        if (
            summary.max_attempt_count is None
            or summary.max_attempt_count > max_attempt_count
        ):
            findings.append("RETRY_TARGET_MISSED")
        if summary.total_owner_actions > max_owner_actions:
            findings.append("OWNER_BURDEN_TARGET_MISSED")
        if summary.transport_failure_count > max_transport_failures:
            findings.append("TRANSPORT_FAILURE_BUDGET_EXCEEDED")
        if summary.semantic_failure_count > max_semantic_failures:
            findings.append("SEMANTIC_FAILURE_BUDGET_EXCEEDED")
        if summary.readback_missing_count > max_readback_failures:
            findings.append("READBACK_FAILURE_BUDGET_EXCEEDED")
        if (
            summary.postcondition_failure_count
            > max_postcondition_failures
        ):
            findings.append("POSTCONDITION_FAILURE_BUDGET_EXCEEDED")
        if (
            summary.verified_rate is None
            or summary.verified_rate < minimum_verified_rate
        ):
            findings.append("VERIFIED_RATE_TARGET_MISSED")
        return (
            tuple(findings)
            if findings
            else ("TARGETS_MET_FOR_MEASURED_WINDOW",)
        )


class FailureDomainCircuit:
    """Fail-closed domain quarantine that leaves unrelated domains routable."""

    def __init__(self) -> None:
        self._open_domains: set[str] = set()

    def trip(self, failure_domain: str) -> None:
        if not failure_domain:
            raise ValueError("failure_domain must be non-empty")
        self._open_domains.add(failure_domain)

    def reset(self, failure_domain: str) -> None:
        self._open_domains.discard(failure_domain)

    @property
    def open_domains(self) -> frozenset[str]:
        return frozenset(self._open_domains)

    def route(
        self,
        router: MeshRouter,
        envelope: MeshEnvelope,
    ):
        return router.route(
            envelope,
            excluded_failure_domains=self._open_domains,
        )


@dataclass(frozen=True)
class SyntheticScaleReceipt:
    node_count: int
    failure_domain_count: int
    routed_count: int
    adapter_relationship_count: int
    pairwise_relationship_count: int
    all_nodes_routable: bool
    measurement_kind: str = "IN_MEMORY_ROUTABILITY_ONLY"


def synthetic_scale_probe(
    *,
    node_count: int = 1000,
    failure_domain_count: int = 20,
) -> SyntheticScaleReceipt:
    """Exercise the N-adapter model without external I/O or timing claims."""

    if node_count < 1:
        raise ValueError("node_count must be >= 1")
    if failure_domain_count < 1:
        raise ValueError("failure_domain_count must be >= 1")
    nodes = [
        NodeDescriptor(
            node_id=f"NODE-{index:05d}",
            name=f"Synthetic node {index}",
            node_type="SYNTHETIC",
            provider="SYNTHETIC",
            capabilities=("SYNC",),
            authority_ceiling="A1_INTERNAL",
            privacy_ceiling="P1_INTERNAL",
            adapter=f"adapter:{index}",
            failure_domain=(
                f"cell-{index % failure_domain_count:03d}"
            ),
        )
        for index in range(node_count)
    ]
    router = MeshRouter(nodes)
    envelope = MeshEnvelope(
        event_id="SCALE-PROBE",
        event_type="SYNTHETIC_SCALE",
        source="CFBE",
        topic="mesh.scale.probe.v1",
        idempotency_key="SCALE-PROBE-1",
        correlation_id="SCALE-CORR-1",
        capability_required="SYNC",
        authority_required="A1_INTERNAL",
        privacy_class="P1_INTERNAL",
        payload={"probe": "metadata-only"},
    )
    routes = router.route(envelope)
    return SyntheticScaleReceipt(
        node_count=node_count,
        failure_domain_count=failure_domain_count,
        routed_count=len(routes),
        adapter_relationship_count=len(router.nodes()),
        pairwise_relationship_count=0,
        all_nodes_routable=len(routes) == node_count,
    )
