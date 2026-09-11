from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, Mapping, Sequence, Tuple


class ProtocolSelectionError(RuntimeError):
    pass


class InteractionClass(str, Enum):
    TOOL = "tool"
    AGENT_TO_AGENT = "agent_to_agent"
    AGENT_TO_USER = "agent_to_user"
    EVENT = "event"
    RPC = "rpc"
    REALTIME = "realtime"


@dataclass(frozen=True)
class ProtocolProfile:
    semantic_id: str
    versions: Tuple[str, ...]
    interaction_classes: Tuple[InteractionClass, ...]
    transports: Tuple[str, ...]
    streaming: bool = False
    bidirectional: bool = False
    discovery: bool = False
    task_lifecycle: bool = False
    tool_invocation: bool = False
    ui_state_sync: bool = False
    event_envelope: bool = False
    schema_discovery: bool = False
    auth_capable: bool = True
    stateless_core: bool = False
    notes: str = ""


@dataclass(frozen=True)
class ProtocolObservation:
    transport: str | None = None
    content_type: str | None = None
    headers: Mapping[str, str] = field(default_factory=dict)
    payload_keys: Tuple[str, ...] = ()
    schema_hints: Tuple[str, ...] = ()
    url: str | None = None


@dataclass(frozen=True)
class CommunicationIntent:
    interaction_class: InteractionClass
    require_streaming: bool = False
    require_bidirectional: bool = False
    require_task_lifecycle: bool = False
    require_tool_invocation: bool = False
    require_ui_state_sync: bool = False
    require_event_envelope: bool = False
    require_discovery: bool = False
    prefer_binary: bool = False
    prefer_stateless: bool = False


@dataclass(frozen=True)
class ProtocolPolicy:
    allowed_protocols: Tuple[str, ...] = ()
    denied_protocols: Tuple[str, ...] = ()
    require_auth_capable: bool = True
    require_tls_transport: bool = True
    forbid_silent_downgrade: bool = True
    max_retry_attempts: int = 3


@dataclass(frozen=True)
class DetectionResult:
    semantic_id: str
    confidence: float
    reasons: Tuple[str, ...]


@dataclass(frozen=True)
class NegotiatedProtocol:
    semantic_id: str
    version: str
    transport: str
    confidence: float
    downgrade: bool = False
    reasons: Tuple[str, ...] = ()


@dataclass(frozen=True)
class MessageEnvelope:
    mission_id: str
    message_id: str
    correlation_id: str
    causation_id: str | None
    idempotency_key: str | None
    protocol_id: str
    protocol_version: str
    traceparent: str | None = None
    deadline_epoch_ms: int | None = None
    content_digest: str | None = None


class ProtocolRegistry:
    def __init__(self, profiles: Iterable[ProtocolProfile] = ()) -> None:
        self._profiles: Dict[str, ProtocolProfile] = {}
        for profile in profiles:
            self.register(profile)

    def register(self, profile: ProtocolProfile) -> None:
        existing = self._profiles.get(profile.semantic_id)
        if existing is not None and existing != profile:
            raise ValueError(f"protocol profile already registered differently: {profile.semantic_id}")
        self._profiles[profile.semantic_id] = profile

    def get(self, semantic_id: str) -> ProtocolProfile:
        return self._profiles[semantic_id]

    def all(self) -> Tuple[ProtocolProfile, ...]:
        return tuple(self._profiles[k] for k in sorted(self._profiles))


class ProtocolAwarenessEngine:
    """Passive/declared protocol awareness and safe negotiation.

    This engine does not perform intrusive network probing. It reasons only from
    supplied observations, declared capability metadata, and local policy.
    """

    def __init__(self, registry: ProtocolRegistry) -> None:
        self.registry = registry

    @staticmethod
    def _norm_headers(headers: Mapping[str, str]) -> Dict[str, str]:
        return {str(k).lower(): str(v) for k, v in headers.items()}

    def detect(self, observation: ProtocolObservation) -> Tuple[DetectionResult, ...]:
        h = self._norm_headers(observation.headers)
        keys = {k.lower() for k in observation.payload_keys}
        hints = {h.lower() for h in observation.schema_hints}
        content_type = (observation.content_type or "").lower()
        transport = (observation.transport or "").lower()
        url = (observation.url or "").lower()

        scored: Dict[str, Tuple[float, list[str]]] = {}

        def add(pid: str, score: float, reason: str) -> None:
            current, reasons = scored.get(pid, (0.0, []))
            reasons.append(reason)
            scored[pid] = (min(1.0, current + score), reasons)

        if "mcp-method" in h or "mcp-name" in h:
            add("PROTO.MCP", 0.85, "MCP routing header observed")
        if "mcp" in hints or "/mcp" in url:
            add("PROTO.MCP", 0.25, "MCP schema/URL hint")

        if "a2a-version" in h or "a2a-extensions" in h:
            add("PROTO.A2A", 0.8, "A2A service parameter observed")
        if "agentcard" in keys or "supportedinterfaces" in keys or "a2a" in hints:
            add("PROTO.A2A", 0.35, "A2A AgentCard/schema signal")

        if "ag-ui" in hints or "ag_ui" in hints or "agui" in hints:
            add("PROTO.AGUI", 0.6, "AG-UI schema hint")
        if "run_started" in keys or "state_snapshot" in keys or "tool_call_start" in keys:
            add("PROTO.AGUI", 0.3, "agent-user event signal")

        if "jsonrpc" in keys:
            add("PROTO.JSONRPC", 0.7, "JSON-RPC envelope")
        if content_type == "application/json" and {"id", "method"}.issubset(keys):
            add("PROTO.JSONRPC", 0.2, "method/id JSON request shape")

        if "grpc" in transport or "application/grpc" in content_type:
            add("PROTO.GRPC", 0.9, "gRPC transport/content type")

        if "text/event-stream" in content_type or transport == "sse":
            add("PROTO.SSE", 0.9, "Server-Sent Events transport")

        if transport in {"websocket", "websockets", "ws", "wss"}:
            add("PROTO.WEBSOCKET", 0.9, "WebSocket transport")

        if "cloudevents" in hints or {"specversion", "source", "type", "id"}.issubset(keys):
            add("PROTO.CLOUDEVENTS", 0.8, "CloudEvents envelope shape")

        if "openapi" in hints or "openapi" in keys:
            add("PROTO.OPENAPI", 0.8, "OpenAPI document signal")
        if "asyncapi" in hints or "asyncapi" in keys:
            add("PROTO.ASYNCAPI", 0.8, "AsyncAPI document signal")

        results = [DetectionResult(pid, score, tuple(reasons)) for pid, (score, reasons) in scored.items()]
        return tuple(sorted(results, key=lambda r: (-r.confidence, r.semantic_id)))

    @staticmethod
    def _supports_intent(profile: ProtocolProfile, intent: CommunicationIntent) -> bool:
        if intent.interaction_class not in profile.interaction_classes:
            return False
        if intent.require_streaming and not profile.streaming:
            return False
        if intent.require_bidirectional and not profile.bidirectional:
            return False
        if intent.require_task_lifecycle and not profile.task_lifecycle:
            return False
        if intent.require_tool_invocation and not profile.tool_invocation:
            return False
        if intent.require_ui_state_sync and not profile.ui_state_sync:
            return False
        if intent.require_event_envelope and not profile.event_envelope:
            return False
        if intent.require_discovery and not profile.discovery:
            return False
        if intent.prefer_stateless and not profile.stateless_core:
            return False
        return True

    @staticmethod
    def _transport_is_secure(transport: str) -> bool:
        t = transport.lower()
        return t in {"https", "grpc+tls", "wss", "webrtc+dtls", "quic+tls"}

    def select(
        self,
        intent: CommunicationIntent,
        policy: ProtocolPolicy = ProtocolPolicy(),
    ) -> Tuple[ProtocolProfile, ...]:
        allowed = set(policy.allowed_protocols)
        denied = set(policy.denied_protocols)
        candidates = []
        for profile in self.registry.all():
            if allowed and profile.semantic_id not in allowed:
                continue
            if profile.semantic_id in denied:
                continue
            if policy.require_auth_capable and not profile.auth_capable:
                continue
            if not self._supports_intent(profile, intent):
                continue
            if policy.require_tls_transport and not any(self._transport_is_secure(t) for t in profile.transports):
                continue
            candidates.append(profile)

        def score(p: ProtocolProfile) -> tuple:
            binary_bonus = 0 if (intent.prefer_binary and "grpc+tls" in p.transports) else 1
            stateless_bonus = 0 if (intent.prefer_stateless and p.stateless_core) else 1
            specialized = {
                InteractionClass.TOOL: "PROTO.MCP",
                InteractionClass.AGENT_TO_AGENT: "PROTO.A2A",
                InteractionClass.AGENT_TO_USER: "PROTO.AGUI",
                InteractionClass.EVENT: "PROTO.CLOUDEVENTS",
            }.get(intent.interaction_class)
            specialization = 0 if p.semantic_id == specialized else 1
            return (specialization, binary_bonus, stateless_bonus, p.semantic_id)

        return tuple(sorted(candidates, key=score))

    def negotiate(
        self,
        intent: CommunicationIntent,
        remote_supported: Mapping[str, Sequence[str]],
        policy: ProtocolPolicy = ProtocolPolicy(),
    ) -> NegotiatedProtocol:
        local_candidates = self.select(intent, policy)
        for profile in local_candidates:
            remote_versions = tuple(remote_supported.get(profile.semantic_id, ()))
            if not remote_versions:
                continue
            local_versions = profile.versions
            common = [v for v in local_versions if v in remote_versions]
            if not common:
                continue
            chosen = common[0]
            downgrade = chosen != local_versions[0]
            if downgrade and policy.forbid_silent_downgrade:
                raise ProtocolSelectionError(
                    f"downgrade requires explicit handling: {profile.semantic_id} {local_versions[0]} -> {chosen}"
                )
            secure_transports = [t for t in profile.transports if self._transport_is_secure(t)]
            if policy.require_tls_transport and not secure_transports:
                continue
            transport = secure_transports[0] if secure_transports else profile.transports[0]
            return NegotiatedProtocol(
                semantic_id=profile.semantic_id,
                version=chosen,
                transport=transport,
                confidence=1.0,
                downgrade=downgrade,
                reasons=("local/remote protocol and version intersection",),
            )
        raise ProtocolSelectionError("no compatible protocol satisfies intent and policy")

    @staticmethod
    def retry_allowed(*, idempotent: bool, attempt: int, policy: ProtocolPolicy) -> bool:
        return idempotent and 0 <= attempt < policy.max_retry_attempts


def default_protocol_registry() -> ProtocolRegistry:
    profiles = [
        ProtocolProfile(
            "PROTO.MCP",
            ("2026-07-28", "2025-11-25"),
            (InteractionClass.TOOL,),
            ("https",),
            discovery=True,
            tool_invocation=True,
            schema_discovery=True,
            stateless_core=True,
            notes="Tool/context protocol; current FUSE target treats 2026-07-28 stateless core as preferred.",
        ),
        ProtocolProfile(
            "PROTO.A2A",
            ("1.0", "0.3"),
            (InteractionClass.AGENT_TO_AGENT,),
            ("grpc+tls", "https"),
            streaming=True,
            discovery=True,
            task_lifecycle=True,
            schema_discovery=True,
            notes="Agent interoperability with AgentCard/interface negotiation and multiple bindings.",
        ),
        ProtocolProfile(
            "PROTO.AGUI",
            ("1",),
            (InteractionClass.AGENT_TO_USER,),
            ("https", "wss"),
            streaming=True,
            bidirectional=True,
            discovery=False,
            ui_state_sync=True,
            notes="Event-oriented agent/user interaction and frontend state synchronization.",
        ),
        ProtocolProfile(
            "PROTO.CLOUDEVENTS",
            ("1.0.2",),
            (InteractionClass.EVENT,),
            ("https", "wss", "grpc+tls"),
            event_envelope=True,
            notes="Vendor-neutral event envelope; transport binding is separate.",
        ),
        ProtocolProfile(
            "PROTO.JSONRPC",
            ("2.0",),
            (InteractionClass.RPC, InteractionClass.TOOL, InteractionClass.AGENT_TO_AGENT),
            ("https", "wss"),
            streaming=True,
        ),
        ProtocolProfile(
            "PROTO.GRPC",
            ("1",),
            (InteractionClass.RPC, InteractionClass.AGENT_TO_AGENT),
            ("grpc+tls",),
            streaming=True,
            bidirectional=True,
            schema_discovery=True,
        ),
        ProtocolProfile(
            "PROTO.SSE",
            ("1",),
            (InteractionClass.REALTIME, InteractionClass.AGENT_TO_USER),
            ("https",),
            streaming=True,
        ),
        ProtocolProfile(
            "PROTO.WEBSOCKET",
            ("13",),
            (InteractionClass.REALTIME, InteractionClass.AGENT_TO_USER),
            ("wss",),
            streaming=True,
            bidirectional=True,
        ),
        ProtocolProfile(
            "PROTO.OPENAPI",
            ("3.2.0", "3.1.2"),
            (InteractionClass.RPC,),
            ("https",),
            schema_discovery=True,
            notes="API contract/schema description; concrete HTTP behavior is defined by the API.",
        ),
        ProtocolProfile(
            "PROTO.ASYNCAPI",
            ("3.1.0", "3.0.0"),
            (InteractionClass.EVENT,),
            ("https",),
            schema_discovery=True,
            notes="Machine-readable event-driven API description across multiple broker/transports.",
        ),
    ]
    return ProtocolRegistry(profiles)
