from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
import json
import re
from typing import Any, Iterable


AUTHORITY_ORDER = {
    "A0_READ_ONLY": 0,
    "A1_INTERNAL": 1,
    "A2_REVERSIBLE_EXTERNAL": 2,
    "A3_CONSEQUENTIAL": 3,
}
PRIVACY_ORDER = {
    "P0_PUBLIC": 0,
    "P1_INTERNAL": 1,
    "P2_PRIVATE": 2,
    "P3_RESTRICTED": 3,
}
HEALTH_STATES = {
    "HEALTHY",
    "DEGRADED",
    "STALE",
    "UNKNOWN",
    "FAILED",
    "RETIRED",
    "QUARANTINED",
}
ROUTABLE_HEALTH = {"HEALTHY", "DEGRADED"}
TERMINAL_SUCCESS = {"ACKED", "SEMANTICALLY_VERIFIED"}
TERMINAL_DELIVERY_STATES = TERMINAL_SUCCESS | {"CANCELLED", "REJECTED"}

SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "credential",
    "authorization",
)
SAFE_REFERENCE_KEYS = {
    "secret_ref",
    "secret_reference",
    "credential_ref",
    "credential_reference",
    "permit_ref",
    "permit_reference",
}
SAFE_REFERENCE_RE = re.compile(
    r"^(?:projects/[A-Za-z0-9._-]+/secrets/[A-Za-z0-9._-]+/versions/(?:latest|[0-9]+)"
    r"|secret://[A-Za-z0-9._/-]+"
    r"|permit://[A-Za-z0-9._/-]+"
    r"|opaque-ref:[A-Za-z0-9._:-]+)$"
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}", re.IGNORECASE),
    re.compile(r"\b(?:sk|sk-proj)-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\bya29\.[0-9A-Za-z._-]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
)
TRACEPARENT_RE = re.compile(
    r"^[0-9a-f]{2}-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$"
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _rank(value: str, table: dict[str, int]) -> int:
    try:
        return table[value]
    except KeyError as exc:
        raise ValueError(f"unknown classification: {value}") from exc


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _validate_unit_interval(name: str, value: float) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    if not 0.0 <= float(value) <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")


def _looks_like_safe_reference(key: str, value: Any) -> bool:
    return (
        key.lower() in SAFE_REFERENCE_KEYS
        and isinstance(value, str)
        and SAFE_REFERENCE_RE.fullmatch(value) is not None
    )


def _contains_raw_secret(value: Any, path: str = "payload") -> list[str]:
    """Return paths containing likely raw credential material.

    This is deliberately conservative. Known opaque reference shapes are
    allowed, while suspicious key names and common credential value patterns
    fail closed.
    """

    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            key_lower = key_text.lower()
            child_path = f"{path}.{key_text}"
            if _looks_like_safe_reference(key_lower, child):
                continue
            if any(fragment in key_lower for fragment in SENSITIVE_KEY_FRAGMENTS):
                findings.append(child_path)
            findings.extend(_contains_raw_secret(child, child_path))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            findings.extend(_contains_raw_secret(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        if any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS):
            findings.append(path)
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
    failure_domain: str = "UNSPECIFIED"
    descriptor_version: int = 1
    supersedes_descriptor_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        for name, value in (
            ("node_id", self.node_id),
            ("name", self.name),
            ("node_type", self.node_type),
            ("provider", self.provider),
            ("adapter", self.adapter),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if not self.capabilities or any(
            not isinstance(capability, str) or not capability.strip()
            for capability in self.capabilities
        ):
            raise ValueError("capabilities must contain non-empty strings")
        _rank(self.authority_ceiling, AUTHORITY_ORDER)
        _rank(self.privacy_ceiling, PRIVACY_ORDER)
        if self.health not in HEALTH_STATES:
            raise ValueError(f"unknown health state: {self.health}")
        for name, value in (
            ("freshness", self.freshness),
            ("reliability", self.reliability),
            ("proof_strength", self.proof_strength),
            ("executability", self.executability),
            ("owner_burden", self.owner_burden),
        ):
            _validate_unit_interval(name, value)
        if not isinstance(self.latency, (int, float)) or isinstance(self.latency, bool):
            raise ValueError("latency must be numeric")
        if float(self.latency) < 0:
            raise ValueError("latency must be non-negative")
        if not isinstance(self.descriptor_version, int) or self.descriptor_version < 1:
            raise ValueError("descriptor_version must be an integer >= 1")
        if (
            self.supersedes_descriptor_hash is not None
            and SHA256_RE.fullmatch(self.supersedes_descriptor_hash) is None
        ):
            raise ValueError("supersedes_descriptor_hash must be a lowercase SHA-256")
        try:
            _canonical_json(self.metadata)
        except (TypeError, ValueError) as exc:
            raise ValueError("metadata must be JSON serializable") from exc

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities or "*" in self.capabilities

    @property
    def effective_failure_domain(self) -> str:
        return (
            self.failure_domain
            if self.failure_domain != "UNSPECIFIED"
            else self.provider
        )

    @property
    def descriptor_hash(self) -> str:
        payload = {
            "node_id": self.node_id,
            "name": self.name,
            "node_type": self.node_type,
            "provider": self.provider,
            "capabilities": sorted(self.capabilities),
            "authority_ceiling": self.authority_ceiling,
            "privacy_ceiling": self.privacy_ceiling,
            "health": self.health,
            "enabled": self.enabled,
            "freshness": float(self.freshness),
            "reliability": float(self.reliability),
            "proof_strength": float(self.proof_strength),
            "executability": float(self.executability),
            "latency": float(self.latency),
            "owner_burden": float(self.owner_burden),
            "adapter": self.adapter,
            "fallback_adapter": self.fallback_adapter,
            "failure_domain": self.failure_domain,
            "descriptor_version": self.descriptor_version,
            "metadata": self.metadata,
        }
        return sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


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
    specversion: str = "1.0"
    traceparent: str | None = None
    tracestate: str | None = None
    minimum_freshness: float = 0.0
    minimum_proof_strength: float = 0.0
    minimum_executability: float = 0.0

    @property
    def payload_hash(self) -> str:
        return sha256(_canonical_json(self.payload).encode("utf-8")).hexdigest()

    def validate(self) -> None:
        if not all(
            (
                self.event_id,
                self.event_type,
                self.source,
                self.topic,
                self.idempotency_key,
                self.correlation_id,
                self.capability_required,
            )
        ):
            raise ValueError("mesh envelope identifiers must be non-empty")
        if self.specversion != "1.0":
            raise ValueError("unsupported CloudEvents specversion")
        _rank(self.authority_required, AUTHORITY_ORDER)
        _rank(self.privacy_class, PRIVACY_ORDER)
        for name, value in (
            ("minimum_freshness", self.minimum_freshness),
            ("minimum_proof_strength", self.minimum_proof_strength),
            ("minimum_executability", self.minimum_executability),
        ):
            _validate_unit_interval(name, value)
        if self.traceparent is not None and not TRACEPARENT_RE.fullmatch(
            self.traceparent
        ):
            raise ValueError("invalid W3C traceparent")
        findings = _contains_raw_secret(self.payload)
        if findings:
            raise ValueError(
                "raw secret-like payload material is forbidden: "
                + ", ".join(sorted(set(findings)))
            )

    def to_cloudevent(self) -> dict[str, Any]:
        """Render a CloudEvents-aligned structured event without credentials."""

        self.validate()
        event: dict[str, Any] = {
            "specversion": self.specversion,
            "id": self.event_id,
            "source": f"urn:federation:{self.source.lower()}",
            "type": self.event_type,
            "subject": self.topic,
            "datacontenttype": "application/json",
            "data": self.payload,
            "correlationid": self.correlation_id,
            "idempotencykey": self.idempotency_key,
            "capability": self.capability_required,
            "authority": self.authority_required,
            "privacy": self.privacy_class,
            "payloadhash": self.payload_hash,
            "minimumfreshness": self.minimum_freshness,
            "minimumproofstrength": self.minimum_proof_strength,
            "minimumexecutability": self.minimum_executability,
        }
        if self.traceparent is not None:
            event["traceparent"] = self.traceparent
        if self.tracestate is not None:
            event["tracestate"] = self.tracestate
        return event


@dataclass(frozen=True)
class RouteDecision:
    node_id: str
    adapter: str
    score: float
    reason: str
    is_fallback: bool = False
    failure_domain: str = "UNSPECIFIED"
    descriptor_hash: str | None = None


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
    trace_id: str | None = None
    latency_ms: float | None = None
    attempt_count: int | None = None
    incremental_cost_units: float | None = None
    owner_action_count: int | None = None
    failure_domain: str | None = None
    expected_state_change: bool | None = True
    postcondition_match: bool = True
    observed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.event_id or not self.target_node or not self.status:
            raise ValueError("receipt identifiers and status must be non-empty")
        if self.latency_ms is not None and self.latency_ms < 0:
            raise ValueError("latency_ms must be non-negative")
        if self.attempt_count is not None and self.attempt_count < 0:
            raise ValueError("attempt_count must be non-negative")
        if (
            self.incremental_cost_units is not None
            and self.incremental_cost_units < 0
        ):
            raise ValueError("incremental_cost_units must be non-negative")
        if self.owner_action_count is not None and self.owner_action_count < 0:
            raise ValueError("owner_action_count must be non-negative")
        if self.observed_at is not None and self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")

    @property
    def postcondition_verified(self) -> bool:
        if not self.postcondition_match:
            return False
        if self.expected_state_change is None:
            return True
        return self.state_changed is self.expected_state_change

    @property
    def verified(self) -> bool:
        return (
            self.transport_ok
            and self.semantic_match
            and self.readback_present
            and self.postcondition_verified
            and self.status in TERMINAL_SUCCESS
        )

    @property
    def telemetry_complete(self) -> bool:
        return all(
            value is not None
            for value in (
                self.trace_id,
                self.latency_ms,
                self.attempt_count,
                self.incremental_cost_units,
                self.owner_action_count,
                self.failure_domain,
            )
        )


class DeliveryLedger:
    """Provider-neutral idempotency, delivery, DLQ and replay state.

    The class stores no credentials or message bodies. The serializable
    snapshot makes the same state suitable for a durable provider adapter.
    """

    def __init__(self, max_attempts: int = 5) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self.max_attempts = max_attempts
        self._events: dict[str, dict[str, str]] = {}
        self._event_to_key: dict[str, str] = {}
        self._attempts: dict[tuple[str, str], int] = {}
        self._status: dict[tuple[str, str], str] = {}

    def admit(self, envelope: MeshEnvelope) -> bool:
        envelope.validate()
        existing = self._events.get(envelope.idempotency_key)
        if existing is None:
            prior_key = self._event_to_key.get(envelope.event_id)
            if prior_key is not None and prior_key != envelope.idempotency_key:
                raise ValueError(
                    "event_id already bound to a different idempotency key"
                )
            self._events[envelope.idempotency_key] = {
                "event_id": envelope.event_id,
                "payload_hash": envelope.payload_hash,
            }
            self._event_to_key[envelope.event_id] = envelope.idempotency_key
            return True
        if existing["payload_hash"] != envelope.payload_hash:
            raise ValueError("idempotency key reused with different payload")
        if existing["event_id"] != envelope.event_id:
            raise ValueError("idempotency key reused with different event_id")
        return False

    def assert_known(self, envelope: MeshEnvelope) -> None:
        existing = self._events.get(envelope.idempotency_key)
        if existing is None:
            raise ValueError("event has not been admitted")
        if (
            existing["event_id"] != envelope.event_id
            or existing["payload_hash"] != envelope.payload_hash
        ):
            raise ValueError("event identity or payload does not match ledger")

    def register_targets(
        self,
        event_id: str,
        target_nodes: Iterable[str],
    ) -> None:
        if event_id not in self._event_to_key:
            raise ValueError("cannot register targets for unknown event")
        for target_node in target_nodes:
            if not target_node:
                raise ValueError("target_node must be non-empty")
            self._status.setdefault((event_id, target_node), "PENDING")
            self._attempts.setdefault((event_id, target_node), 0)

    def record_attempt(
        self,
        event_id: str,
        target_node: str,
        *,
        succeeded: bool = False,
    ) -> str:
        key = (event_id, target_node)
        existing = self._status.get(key)
        if existing in TERMINAL_DELIVERY_STATES:
            return existing
        if existing is None:
            self._status[key] = "PENDING"
            self._attempts[key] = 0
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

    def record_receipt(self, receipt: DeliveryReceipt) -> str:
        key = (receipt.event_id, receipt.target_node)
        if key not in self._status:
            raise ValueError("receipt target was not registered")
        if receipt.verified:
            status = "SEMANTICALLY_VERIFIED"
        elif not receipt.transport_ok:
            status = "RETRYABLE"
        elif not receipt.semantic_match:
            status = "SEMANTIC_FAILURE"
        elif not receipt.readback_present:
            status = "READBACK_MISSING"
        elif not receipt.postcondition_verified:
            status = "POSTCONDITION_MISMATCH"
        else:
            status = "PARTIAL"
        self._status[key] = status
        return status

    def replay_dead_letter(self, event_id: str, target_node: str) -> str:
        key = (event_id, target_node)
        if self._status.get(key) != "DEAD_LETTER":
            raise ValueError("only dead-letter deliveries may be replayed")
        self._attempts[key] = 0
        self._status[key] = "REPLAY_READY"
        return "REPLAY_READY"

    def incomplete_targets(self, event_id: str) -> tuple[str, ...]:
        resumable = {"PENDING", "RETRYABLE", "REPLAY_READY"}
        return tuple(
            sorted(
                target_node
                for (current_event, target_node), status in self._status.items()
                if current_event == event_id and status in resumable
            )
        )

    def status(self, event_id: str, target_node: str) -> str | None:
        return self._status.get((event_id, target_node))

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "max_attempts": self.max_attempts,
            "events": self._events,
            "attempts": [
                {
                    "event_id": event_id,
                    "target_node": target_node,
                    "count": count,
                }
                for (event_id, target_node), count in sorted(
                    self._attempts.items()
                )
            ],
            "statuses": [
                {
                    "event_id": event_id,
                    "target_node": target_node,
                    "status": status,
                }
                for (event_id, target_node), status in sorted(
                    self._status.items()
                )
            ],
        }

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> "DeliveryLedger":
        if data.get("schema_version") != 1:
            raise ValueError("unsupported ledger snapshot schema")
        ledger = cls(max_attempts=int(data["max_attempts"]))
        events = data.get("events")
        if not isinstance(events, dict):
            raise ValueError("events must be a dictionary")
        for key, value in events.items():
            if (
                not isinstance(key, str)
                or not isinstance(value, dict)
                or not isinstance(value.get("event_id"), str)
                or SHA256_RE.fullmatch(str(value.get("payload_hash", "")))
                is None
            ):
                raise ValueError("invalid event record in snapshot")
            ledger._events[key] = {
                "event_id": value["event_id"],
                "payload_hash": value["payload_hash"],
            }
            ledger._event_to_key[value["event_id"]] = key
        for item in data.get("attempts", []):
            key = (item["event_id"], item["target_node"])
            ledger._attempts[key] = int(item["count"])
        for item in data.get("statuses", []):
            key = (item["event_id"], item["target_node"])
            ledger._status[key] = item["status"]
        return ledger


class MeshRouter:
    """Capability/authority/privacy/health and failure-domain aware router."""

    def __init__(self, nodes: Iterable[NodeDescriptor] = ()) -> None:
        self._nodes: dict[str, NodeDescriptor] = {}
        self.register_many(nodes)

    def register(self, node: NodeDescriptor) -> None:
        existing = self._nodes.get(node.node_id)
        if existing is None:
            self._nodes[node.node_id] = node
            return
        if existing.descriptor_hash == node.descriptor_hash:
            return
        if node.descriptor_version <= existing.descriptor_version:
            raise ValueError(
                "descriptor collision: replacement version must increase"
            )
        if node.supersedes_descriptor_hash != existing.descriptor_hash:
            raise ValueError(
                "descriptor collision: explicit matching supersedes hash required"
            )
        self._nodes[node.node_id] = node

    def register_many(self, nodes: Iterable[NodeDescriptor]) -> None:
        for node in nodes:
            self.register(node)

    def node(self, node_id: str) -> NodeDescriptor | None:
        return self._nodes.get(node_id)

    def nodes(self) -> tuple[NodeDescriptor, ...]:
        return tuple(self._nodes.values())

    @staticmethod
    def _minimum_proof_floor(authority_required: str) -> float:
        return {
            "A0_READ_ONLY": 0.0,
            "A1_INTERNAL": 0.25,
            "A2_REVERSIBLE_EXTERNAL": 0.75,
            "A3_CONSEQUENTIAL": 0.90,
        }[authority_required]

    @classmethod
    def _eligible(
        cls,
        node: NodeDescriptor,
        envelope: MeshEnvelope,
        excluded_failure_domains: frozenset[str] = frozenset(),
    ) -> bool:
        if not node.enabled or node.health not in ROUTABLE_HEALTH:
            return False
        if (
            node.health == "DEGRADED"
            and _rank(envelope.authority_required, AUTHORITY_ORDER)
            > AUTHORITY_ORDER["A1_INTERNAL"]
        ):
            return False
        if node.adapter == "UNBOUND" and node.fallback_adapter is None:
            return False
        if node.effective_failure_domain in excluded_failure_domains:
            return False
        if not node.supports(envelope.capability_required):
            return False
        if _rank(envelope.authority_required, AUTHORITY_ORDER) > _rank(
            node.authority_ceiling, AUTHORITY_ORDER
        ):
            return False
        if _rank(envelope.privacy_class, PRIVACY_ORDER) > _rank(
            node.privacy_ceiling, PRIVACY_ORDER
        ):
            return False
        proof_floor = cls._minimum_proof_floor(envelope.authority_required)
        if node.freshness < max(envelope.minimum_freshness, proof_floor):
            return False
        if node.proof_strength < max(
            envelope.minimum_proof_strength, proof_floor
        ):
            return False
        if node.executability < envelope.minimum_executability:
            return False
        if envelope.targets and node.node_id not in envelope.targets:
            return False
        return True

    @staticmethod
    def _score(node: NodeDescriptor) -> float:
        latency_component = max(
            0.0,
            1.0 - min(float(node.latency), 10.0) / 10.0,
        )
        burden_component = max(0.0, 1.0 - float(node.owner_burden))
        return round(
            0.23 * float(node.reliability)
            + 0.18 * float(node.freshness)
            + 0.20 * float(node.proof_strength)
            + 0.20 * float(node.executability)
            + 0.10 * latency_component
            + 0.09 * burden_component,
            6,
        )

    def route(
        self,
        envelope: MeshEnvelope,
        *,
        excluded_failure_domains: Iterable[str] = (),
    ) -> tuple[RouteDecision, ...]:
        envelope.validate()
        excluded = frozenset(excluded_failure_domains)
        eligible = [
            node
            for node in self._nodes.values()
            if self._eligible(node, envelope, excluded)
        ]
        decisions = []
        for node in eligible:
            use_fallback = (
                node.health == "DEGRADED"
                and node.fallback_adapter is not None
            )
            adapter = (
                node.fallback_adapter if use_fallback else node.adapter
            )
            decisions.append(
                RouteDecision(
                    node_id=node.node_id,
                    adapter=adapter,
                    score=self._score(node),
                    reason=(
                        "ELIGIBLE_FALLBACK_ADAPTER"
                        if use_fallback
                        else "ELIGIBLE_CAPABILITY_AUTHORITY_PRIVACY_HEALTH_"
                        "FRESHNESS_PROOF_FAILURE_DOMAIN_MATCH"
                    ),
                    is_fallback=use_fallback,
                    failure_domain=node.effective_failure_domain,
                    descriptor_hash=node.descriptor_hash,
                )
            )
        decisions.sort(key=lambda item: (-item.score, item.node_id))
        return tuple(decisions)

    def diverse_routes(
        self,
        envelope: MeshEnvelope,
        *,
        max_routes: int = 2,
    ) -> tuple[RouteDecision, ...]:
        if max_routes < 1:
            raise ValueError("max_routes must be >= 1")
        selected: list[RouteDecision] = []
        used_domains: set[str] = set()
        for route in self.route(envelope):
            if route.failure_domain in used_domains:
                continue
            selected.append(route)
            used_domains.add(route.failure_domain)
            if len(selected) >= max_routes:
                break
        return tuple(selected)

    def best_route(self, envelope: MeshEnvelope) -> RouteDecision | None:
        routes = self.route(envelope)
        return routes[0] if routes else None


class MeshControlPlane:
    """Logical mesh controller. Provider effects remain adapter-gated."""

    def __init__(
        self,
        router: MeshRouter | None = None,
        ledger: DeliveryLedger | None = None,
    ) -> None:
        self.router = router or MeshRouter()
        self.ledger = ledger or DeliveryLedger()

    def enroll(self, node: NodeDescriptor) -> None:
        self.router.register(node)

    def publish(self, envelope: MeshEnvelope) -> dict[str, Any]:
        admitted = self.ledger.admit(envelope)
        routes = self.router.route(envelope) if admitted else ()
        if admitted:
            self.ledger.register_targets(
                envelope.event_id,
                (route.node_id for route in routes),
            )
        return {
            "admitted": admitted,
            "resumed": False,
            "event_id": envelope.event_id,
            "payload_hash": envelope.payload_hash,
            "routes": routes,
            "route_count": len(routes),
        }

    def resume_incomplete(self, envelope: MeshEnvelope) -> dict[str, Any]:
        """Resume only unfinished receivers after a crash/restart.

        The caller must restore the durable ledger snapshot first. Completed
        receivers are never re-issued; dead-letter deliveries require explicit
        replay re-arming.
        """

        envelope.validate()
        self.ledger.assert_known(envelope)
        incomplete = set(self.ledger.incomplete_targets(envelope.event_id))
        routes = tuple(
            route
            for route in self.router.route(envelope)
            if route.node_id in incomplete
        )
        return {
            "admitted": False,
            "resumed": True,
            "event_id": envelope.event_id,
            "payload_hash": envelope.payload_hash,
            "routes": routes,
            "route_count": len(routes),
        }

    @staticmethod
    def promotion_gate(
        receipt: DeliveryReceipt,
        *,
        consequential: bool = False,
    ) -> str:
        if not receipt.transport_ok:
            return "TRANSPORT_FAILURE"
        if not receipt.semantic_match:
            return "SEMANTIC_FAILURE"
        if not receipt.readback_present:
            return "READBACK_MISSING"
        if not receipt.postcondition_match:
            return "POSTCONDITION_MISMATCH"
        if (
            receipt.expected_state_change is True
            and not receipt.state_changed
        ):
            return "EXPECTED_STATE_DELTA_MISSING"
        if (
            receipt.expected_state_change is False
            and receipt.state_changed
        ):
            return "UNEXPECTED_STATE_CHANGE"
        if consequential and not receipt.rollback_present:
            return "ROLLBACK_REQUIRED"
        if not receipt.verified:
            return "PARTIAL"
        return "VERIFIED_COMPLETE"

    @staticmethod
    def observability_gate(
        receipt: DeliveryReceipt,
        *,
        max_latency_ms: float,
        max_attempts: int,
        max_owner_actions: int = 0,
    ) -> str:
        if not receipt.verified:
            return "PROOF_NOT_VERIFIED"
        if not receipt.telemetry_complete:
            return "TELEMETRY_INCOMPLETE"
        if receipt.latency_ms is not None and receipt.latency_ms > max_latency_ms:
            return "SLO_LATENCY_BREACH"
        if (
            receipt.attempt_count is not None
            and receipt.attempt_count > max_attempts
        ):
            return "SLO_RETRY_BREACH"
        if (
            receipt.owner_action_count is not None
            and receipt.owner_action_count > max_owner_actions
        ):
            return "OWNER_BURDEN_BREACH"
        return "OBSERVABLE_WITHIN_TARGET"
