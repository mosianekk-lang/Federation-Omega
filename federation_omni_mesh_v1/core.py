from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Iterable


AUTHORITY_ORDER = {
    "A0_READ_ONLY": 0,
    "A1_INTERNAL": 1,
    "A2_REVERSIBLE_EXTERNAL": 2,
    "A3_CONSEQUENTIAL": 3,
}
PRIVACY_ORDER = {"P0_PUBLIC": 0, "P1_INTERNAL": 1, "P2_PRIVATE": 2, "P3_RESTRICTED": 3}
TERMINAL_SUCCESS = {"ACKED", "SEMANTICALLY_VERIFIED"}
SENSITIVE_KEY_FRAGMENTS = ("password", "secret", "token", "api_key", "apikey", "private_key", "credential")


def _rank(value: str, table: dict[str, int], default: int = 10_000) -> int:
    return table.get(value, default)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _contains_raw_secret(value: Any, path: str = "payload") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_lower = str(key).lower()
            if any(fragment in key_lower for fragment in SENSITIVE_KEY_FRAGMENTS):
                findings.append(f"{path}.{key}")
            findings.extend(_contains_raw_secret(child, f"{path}.{key}"))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            findings.extend(_contains_raw_secret(child, f"{path}[{index}]"))
    return findings


@dataclass(frozen=True)
class NodeDescriptor:
    node_id: str
    name: str
    node_type: str
    provider: str
    capabilities: tuple[str, ...]
    authority_ceiling: str = "A1_INTERNAL"
    privacy_ceiling: str = "P2_PRIVATE"
    health: str = "HEALTHY"
    enabled: bool = True
    freshness: float = 1.0
    reliability: float = 1.0
    proof_strength: float = 1.0
    executability: float = 1.0
    latency: float = 1.0
    owner_burden: float = 0.0
    adapter: str = "UNBOUND"
    fallback_adapter: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict, compare=False)

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities or "*" in self.capabilities


@dataclass(frozen=True)
class MeshEnvelope:
    event_id: str
    event_type: str
    source: str
    topic: str
    idempotency_key: str
    correlation_id: str
    capability_required: str
    authority_required: str = "A1_INTERNAL"
    privacy_class: str = "P1_INTERNAL"
    targets: tuple[str, ...] = ()
    payload: dict[str, Any] = field(default_factory=dict, compare=False)

    @property
    def payload_hash(self) -> str:
        return sha256(_canonical_json(self.payload).encode("utf-8")).hexdigest()

    def validate(self) -> None:
        if not all((self.event_id, self.event_type, self.source, self.topic, self.idempotency_key, self.correlation_id)):
            raise ValueError("mesh envelope identifiers must be non-empty")
        if _rank(self.authority_required, AUTHORITY_ORDER) == 10_000:
            raise ValueError(f"unknown authority class: {self.authority_required}")
        if _rank(self.privacy_class, PRIVACY_ORDER) == 10_000:
            raise ValueError(f"unknown privacy class: {self.privacy_class}")
        findings = _contains_raw_secret(self.payload)
        if findings:
            raise ValueError("raw secret-like payload keys are forbidden: " + ", ".join(findings))


@dataclass(frozen=True)
class RouteDecision:
    node_id: str
    adapter: str
    score: float
    reason: str
    is_fallback: bool = False


@dataclass(frozen=True)
class DeliveryReceipt:
    event_id: str
    target_node: str
    status: str
    transport_ok: bool
    semantic_match: bool
    readback_present: bool
    state_changed: bool
    rollback_present: bool = False
    proof_refs: tuple[str, ...] = ()

    @property
    def verified(self) -> bool:
        return (
            self.transport_ok
            and self.semantic_match
            and self.readback_present
            and self.state_changed
            and self.status in TERMINAL_SUCCESS
        )


class DeliveryLedger:
    """Provider-neutral idempotency, delivery and DLQ state.

    The class intentionally stores no credentials. A production adapter may back
    the same semantics with Firestore/SQL/Sheets, but the contract stays stable.
    """

    def __init__(self, max_attempts: int = 5) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self.max_attempts = max_attempts
        self._events: dict[str, str] = {}
        self._attempts: dict[tuple[str, str], int] = {}
        self._status: dict[tuple[str, str], str] = {}

    def admit(self, envelope: MeshEnvelope) -> bool:
        envelope.validate()
        existing = self._events.get(envelope.idempotency_key)
        if existing is None:
            self._events[envelope.idempotency_key] = envelope.payload_hash
            return True
        if existing != envelope.payload_hash:
            raise ValueError("idempotency key reused with different payload")
        return False

    def record_attempt(self, event_id: str, target_node: str, *, succeeded: bool = False) -> str:
        key = (event_id, target_node)
        attempts = self._attempts.get(key, 0) + 1
        self._attempts[key] = attempts
        if succeeded:
            status = "ACKED"
        elif attempts >= self.max_attempts:
            status = "DEAD_LETTER"
        else:
            status = "RETRYABLE"
        self._status[key] = status
        return status

    def status(self, event_id: str, target_node: str) -> str | None:
        return self._status.get((event_id, target_node))


class MeshRouter:
    """Capability/authority/privacy/health aware all-to-all logical router."""

    def __init__(self, nodes: Iterable[NodeDescriptor] = ()) -> None:
        self._nodes: dict[str, NodeDescriptor] = {node.node_id: node for node in nodes}

    def register(self, node: NodeDescriptor) -> None:
        self._nodes[node.node_id] = node

    def register_many(self, nodes: Iterable[NodeDescriptor]) -> None:
        for node in nodes:
            self.register(node)

    def node(self, node_id: str) -> NodeDescriptor | None:
        return self._nodes.get(node_id)

    def nodes(self) -> tuple[NodeDescriptor, ...]:
        return tuple(self._nodes.values())

    @staticmethod
    def _eligible(node: NodeDescriptor, envelope: MeshEnvelope) -> bool:
        if not node.enabled or node.health in {"FAILED", "RETIRED", "QUARANTINED"}:
            return False
        if not node.supports(envelope.capability_required):
            return False
        if _rank(envelope.authority_required, AUTHORITY_ORDER) > _rank(node.authority_ceiling, AUTHORITY_ORDER):
            return False
        if _rank(envelope.privacy_class, PRIVACY_ORDER) > _rank(node.privacy_ceiling, PRIVACY_ORDER):
            return False
        if envelope.targets and node.node_id not in envelope.targets:
            return False
        return True

    @staticmethod
    def _score(node: NodeDescriptor) -> float:
        latency_component = max(0.0, 1.0 - min(node.latency, 10.0) / 10.0)
        burden_component = max(0.0, 1.0 - min(node.owner_burden, 1.0))
        return round(
            0.23 * node.reliability
            + 0.18 * node.freshness
            + 0.20 * node.proof_strength
            + 0.20 * node.executability
            + 0.10 * latency_component
            + 0.09 * burden_component,
            6,
        )

    def route(self, envelope: MeshEnvelope) -> tuple[RouteDecision, ...]:
        envelope.validate()
        eligible = [node for node in self._nodes.values() if self._eligible(node, envelope)]
        decisions = [
            RouteDecision(
                node_id=node.node_id,
                adapter=node.adapter,
                score=self._score(node),
                reason="ELIGIBLE_CAPABILITY_AUTHORITY_PRIVACY_HEALTH_MATCH",
                is_fallback=False,
            )
            for node in eligible
        ]
        decisions.sort(key=lambda item: (-item.score, item.node_id))
        return tuple(decisions)

    def best_route(self, envelope: MeshEnvelope) -> RouteDecision | None:
        routes = self.route(envelope)
        return routes[0] if routes else None


class MeshControlPlane:
    """Logical mesh controller. Provider effects remain adapter-gated.

    The control plane can broadcast to every eligible node or target a subset.
    It never manufactures authority, credentials, IAM or provider state.
    """

    def __init__(self, router: MeshRouter | None = None, ledger: DeliveryLedger | None = None) -> None:
        self.router = router or MeshRouter()
        self.ledger = ledger or DeliveryLedger()

    def enroll(self, node: NodeDescriptor) -> None:
        self.router.register(node)

    def publish(self, envelope: MeshEnvelope) -> dict[str, Any]:
        admitted = self.ledger.admit(envelope)
        routes = self.router.route(envelope) if admitted else ()
        return {
            "admitted": admitted,
            "event_id": envelope.event_id,
            "payload_hash": envelope.payload_hash,
            "routes": routes,
            "route_count": len(routes),
        }

    @staticmethod
    def promotion_gate(receipt: DeliveryReceipt, *, consequential: bool = False) -> str:
        if not receipt.transport_ok:
            return "TRANSPORT_FAILURE"
        if not receipt.semantic_match:
            return "SEMANTIC_FAILURE"
        if not receipt.readback_present:
            return "READBACK_MISSING"
        if not receipt.state_changed:
            return "NO_STATE_DELTA"
        if consequential and not receipt.rollback_present:
            return "ROLLBACK_REQUIRED"
        if not receipt.verified:
            return "PARTIAL"
        return "VERIFIED_COMPLETE"
