from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from typing import Dict, Iterable, Mapping, Sequence, Tuple


class HypervisorError(RuntimeError):
    pass


class DeliverySemantic(str, Enum):
    AT_MOST_ONCE = "at_most_once"
    AT_LEAST_ONCE = "at_least_once"
    EFFECTIVELY_ONCE = "effectively_once"


class SessionMode(str, Enum):
    STATELESS = "stateless"
    STATEFUL = "stateful"


class Compatibility(str, Enum):
    EXACT = "exact"
    SAFE = "safe"
    LOSSY = "lossy"
    INCOMPATIBLE = "incompatible"


@dataclass(frozen=True)
class SchemaContract:
    name: str
    version: str
    required_fields: Tuple[str, ...] = ()
    optional_fields: Tuple[str, ...] = ()
    semantic_features: Tuple[str, ...] = ()

    @property
    def fingerprint(self) -> str:
        payload = "|".join(
            (
                self.name,
                self.version,
                ",".join(sorted(self.required_fields)),
                ",".join(sorted(self.optional_fields)),
                ",".join(sorted(self.semantic_features)),
            )
        )
        return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EndpointContract:
    endpoint_id: str
    protocol_id: str
    version: str
    transport: str
    capabilities: Tuple[str, ...] = ()
    auth_schemes: Tuple[str, ...] = ()
    schema: SchemaContract | None = None
    session_mode: SessionMode = SessionMode.STATELESS
    delivery: DeliverySemantic = DeliverySemantic.AT_LEAST_ONCE
    max_inflight: int = 1
    supports_idempotency: bool = False
    supports_resume: bool = False
    supports_deadlines: bool = False


@dataclass(frozen=True)
class CommunicationRequirement:
    required_capabilities: Tuple[str, ...] = ()
    required_semantic_features: Tuple[str, ...] = ()
    allowed_protocols: Tuple[str, ...] = ()
    allowed_transports: Tuple[str, ...] = ()
    required_auth_schemes: Tuple[str, ...] = ()
    minimum_delivery: DeliverySemantic = DeliverySemantic.AT_LEAST_ONCE
    require_idempotency: bool = False
    require_resume: bool = False
    require_deadlines: bool = False
    max_semantic_loss: float = 0.0


@dataclass(frozen=True)
class AuthBinding:
    workload_identity: str
    auth_scheme: str
    scopes: Tuple[str, ...] = ()


@dataclass(frozen=True)
class SemanticLossReport:
    compatibility: Compatibility
    loss: float
    missing_capabilities: Tuple[str, ...] = ()
    missing_semantics: Tuple[str, ...] = ()
    weakened_guarantees: Tuple[str, ...] = ()


@dataclass(frozen=True)
class HypervisorRoute:
    endpoint: EndpointContract
    loss_report: SemanticLossReport
    auth_binding: AuthBinding | None
    reasons: Tuple[str, ...]


@dataclass(frozen=True)
class DriftReport:
    endpoint_id: str
    changed: bool
    version_changed: bool = False
    transport_changed: bool = False
    capabilities_removed: Tuple[str, ...] = ()
    auth_removed: Tuple[str, ...] = ()
    schema_changed: bool = False
    reasons: Tuple[str, ...] = ()


_DELIVERY_RANK = {
    DeliverySemantic.AT_MOST_ONCE: 0,
    DeliverySemantic.AT_LEAST_ONCE: 1,
    DeliverySemantic.EFFECTIVELY_ONCE: 2,
}


def compare_schema(required: SchemaContract | None, observed: SchemaContract | None) -> Compatibility:
    if required is None:
        return Compatibility.EXACT if observed is None else Compatibility.SAFE
    if observed is None:
        return Compatibility.INCOMPATIBLE
    required_fields = set(required.required_fields)
    observed_fields = set(observed.required_fields) | set(observed.optional_fields)
    if not required_fields.issubset(observed_fields):
        return Compatibility.INCOMPATIBLE
    required_semantics = set(required.semantic_features)
    observed_semantics = set(observed.semantic_features)
    if not required_semantics.issubset(observed_semantics):
        return Compatibility.LOSSY
    if required.fingerprint == observed.fingerprint:
        return Compatibility.EXACT
    return Compatibility.SAFE


class ProtocolHypervisor:
    """Semantic communication route selection above concrete protocol bindings.

    Hard requirements are evaluated before route preference. A route may be
    technically reachable yet rejected if its delivery, auth, schema, resume,
    deadline, or semantic guarantees are weaker than the mission contract.
    """

    def __init__(self, endpoints: Iterable[EndpointContract]) -> None:
        self.endpoints = tuple(endpoints)

    @staticmethod
    def semantic_loss(requirement: CommunicationRequirement, endpoint: EndpointContract) -> SemanticLossReport:
        missing_caps = tuple(sorted(set(requirement.required_capabilities) - set(endpoint.capabilities)))
        endpoint_semantics = set(endpoint.schema.semantic_features if endpoint.schema else ())
        missing_semantics = tuple(sorted(set(requirement.required_semantic_features) - endpoint_semantics))
        weakened = []
        if _DELIVERY_RANK[endpoint.delivery] < _DELIVERY_RANK[requirement.minimum_delivery]:
            weakened.append("delivery")
        if requirement.require_idempotency and not endpoint.supports_idempotency:
            weakened.append("idempotency")
        if requirement.require_resume and not endpoint.supports_resume:
            weakened.append("resume")
        if requirement.require_deadlines and not endpoint.supports_deadlines:
            weakened.append("deadlines")

        denominator = max(
            1,
            len(requirement.required_capabilities)
            + len(requirement.required_semantic_features)
            + int(requirement.minimum_delivery != DeliverySemantic.AT_MOST_ONCE)
            + int(requirement.require_idempotency)
            + int(requirement.require_resume)
            + int(requirement.require_deadlines),
        )
        loss = (len(missing_caps) + len(missing_semantics) + len(weakened)) / denominator
        if missing_caps or _DELIVERY_RANK[endpoint.delivery] < _DELIVERY_RANK[requirement.minimum_delivery]:
            compatibility = Compatibility.INCOMPATIBLE
        elif missing_semantics or weakened:
            compatibility = Compatibility.LOSSY
        elif loss == 0:
            compatibility = Compatibility.SAFE
        else:
            compatibility = Compatibility.LOSSY
        return SemanticLossReport(
            compatibility=compatibility,
            loss=loss,
            missing_capabilities=missing_caps,
            missing_semantics=missing_semantics,
            weakened_guarantees=tuple(weakened),
        )

    @staticmethod
    def _auth_binding(requirement: CommunicationRequirement, endpoint: EndpointContract, identities: Mapping[str, str]) -> AuthBinding | None:
        required = set(requirement.required_auth_schemes)
        available = set(endpoint.auth_schemes)
        if required and not required.intersection(available):
            return None
        if not available:
            return None
        scheme = sorted(required.intersection(available) or available)[0]
        identity = identities.get(endpoint.endpoint_id)
        if not identity:
            return None
        return AuthBinding(identity, scheme)

    def select(
        self,
        requirement: CommunicationRequirement,
        *,
        identities: Mapping[str, str] = {},
    ) -> HypervisorRoute:
        qualified = []
        for endpoint in self.endpoints:
            if requirement.allowed_protocols and endpoint.protocol_id not in requirement.allowed_protocols:
                continue
            if requirement.allowed_transports and endpoint.transport not in requirement.allowed_transports:
                continue
            report = self.semantic_loss(requirement, endpoint)
            if report.compatibility is Compatibility.INCOMPATIBLE:
                continue
            if report.loss > requirement.max_semantic_loss:
                continue
            auth = self._auth_binding(requirement, endpoint, identities)
            if requirement.required_auth_schemes and auth is None:
                continue
            qualified.append((endpoint, report, auth))

        if not qualified:
            raise HypervisorError("no communication route satisfies semantic and policy contract")

        def score(item):
            endpoint, report, auth = item
            resume_bonus = 0 if endpoint.supports_resume else 1
            idempotency_bonus = 0 if endpoint.supports_idempotency else 1
            inflight = -max(1, endpoint.max_inflight)
            return (report.loss, resume_bonus, idempotency_bonus, inflight, endpoint.endpoint_id)

        endpoint, report, auth = min(qualified, key=score)
        return HypervisorRoute(
            endpoint,
            report,
            auth,
            reasons=("hard semantic/policy gates satisfied", "lowest qualified semantic-loss route selected"),
        )


class ReplayProtector:
    """Mission-local replay/idempotency guard.

    This does not claim distributed exactly-once delivery. It detects duplicate
    envelopes locally so effect handlers can fail closed or perform readback.
    """

    def __init__(self) -> None:
        self._seen: set[tuple[str, str]] = set()
        self._last_sequence: Dict[str, int] = {}

    def accept(self, *, session_id: str, message_id: str, sequence: int, idempotency_key: str | None = None) -> bool:
        token = (session_id, idempotency_key or message_id)
        if token in self._seen:
            return False
        last = self._last_sequence.get(session_id, -1)
        if sequence <= last:
            return False
        self._seen.add(token)
        self._last_sequence[session_id] = sequence
        return True


class FlowWindow:
    def __init__(self, max_inflight: int) -> None:
        if max_inflight < 1:
            raise ValueError("max_inflight must be >= 1")
        self.max_inflight = max_inflight
        self.inflight = 0

    @property
    def backpressured(self) -> bool:
        return self.inflight >= self.max_inflight

    def acquire(self) -> None:
        if self.backpressured:
            raise HypervisorError("communication flow window is saturated")
        self.inflight += 1

    def release(self) -> None:
        if self.inflight <= 0:
            raise HypervisorError("cannot release an empty flow window")
        self.inflight -= 1


class ProtocolDriftDetector:
    @staticmethod
    def compare(baseline: EndpointContract, observed: EndpointContract) -> DriftReport:
        if baseline.endpoint_id != observed.endpoint_id:
            raise ValueError("endpoint identities differ")
        removed_caps = tuple(sorted(set(baseline.capabilities) - set(observed.capabilities)))
        removed_auth = tuple(sorted(set(baseline.auth_schemes) - set(observed.auth_schemes)))
        version_changed = baseline.version != observed.version
        transport_changed = baseline.transport != observed.transport
        baseline_schema = baseline.schema.fingerprint if baseline.schema else None
        observed_schema = observed.schema.fingerprint if observed.schema else None
        schema_changed = baseline_schema != observed_schema
        reasons = []
        if version_changed:
            reasons.append("protocol version changed")
        if transport_changed:
            reasons.append("transport binding changed")
        if removed_caps:
            reasons.append("capabilities removed")
        if removed_auth:
            reasons.append("auth schemes removed")
        if schema_changed:
            reasons.append("schema fingerprint changed")
        return DriftReport(
            endpoint_id=baseline.endpoint_id,
            changed=bool(reasons),
            version_changed=version_changed,
            transport_changed=transport_changed,
            capabilities_removed=removed_caps,
            auth_removed=removed_auth,
            schema_changed=schema_changed,
            reasons=tuple(reasons),
        )
