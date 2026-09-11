from __future__ import annotations

"""Federation OmniSurface Fabric v2.

A provider-neutral capability registry, route planner and async/steering correlation
layer.  It performs no provider call, creates no credentials, sends no messages,
places no orders, and mints no authority.  External effects remain owned by the
existing Federation effect/permit/proof layers.
"""

from dataclasses import asdict, dataclass
from enum import StrEnum
from hashlib import sha256
import json
from typing import Iterable, Mapping, Sequence

SCHEMA = "FEDERATION-OMNISURFACE-FABRIC-V2"
VERSION = "2.0.0"
MCP_PROTOCOL_VERSION = "2026-07-28"
A2A_PROTOCOL_VERSION = "1.0"
EXTERNAL_EFFECTS = False
AUTHORITY_MINTING = False
FINANCIAL_EXECUTION = False


def _clean(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _hash(value: object) -> str:
    return sha256(_stable(value).encode("utf-8")).hexdigest()


class EffectClass(StrEnum):
    OBSERVE = "OBSERVE"
    INTERNAL = "INTERNAL"
    DRAFT = "DRAFT"
    REVERSIBLE_WRITE = "REVERSIBLE_WRITE"
    CONSEQUENTIAL = "CONSEQUENTIAL"
    FINANCIAL = "FINANCIAL"


_EFFECT_ORDER = {
    EffectClass.OBSERVE: 0,
    EffectClass.INTERNAL: 1,
    EffectClass.DRAFT: 2,
    EffectClass.REVERSIBLE_WRITE: 3,
    EffectClass.CONSEQUENTIAL: 4,
    EffectClass.FINANCIAL: 5,
}


class SurfaceState(StrEnum):
    CONNECTED_TOOL_EXPOSED = "CONNECTED_TOOL_EXPOSED"
    REPOSITORY_BRIDGE_ADMITTED = "REPOSITORY_BRIDGE_ADMITTED"
    MODEL_CATALOG_VERIFIED = "MODEL_CATALOG_VERIFIED"
    USER_NAMED_REVALIDATE_RUNTIME = "USER_NAMED_REVALIDATE_RUNTIME"
    FUTURE_DISCOVERY_ONLY = "FUTURE_DISCOVERY_ONLY"


class Protocol(StrEnum):
    MCP = "MCP"
    A2A = "A2A"
    FEDERATION_NATIVE = "FEDERATION_NATIVE"
    RESPONSES_API = "RESPONSES_API"
    REST = "REST"
    WEBSOCKET = "WEBSOCKET"
    CONNECTOR = "CONNECTOR"
    CLOUDEVENTS = "CLOUDEVENTS"
    WORKSPACE_EVENTS = "WORKSPACE_EVENTS"


@dataclass(frozen=True, slots=True)
class SurfaceDescriptor:
    surface_id: str
    provider: str
    product: str
    state: SurfaceState
    protocols: tuple[str, ...]
    capabilities: tuple[str, ...]
    readback_signals: tuple[str, ...]
    source_refs: tuple[str, ...]
    maximum_effect: EffectClass = EffectClass.INTERNAL
    auth_strategy: str = "PROVIDER_NATIVE_REVALIDATE_ON_USE"
    native_ai: tuple[str, ...] = ()
    event_sources: tuple[str, ...] = ()
    provider_readback_required: bool = True
    financial_surface: bool = False
    live_execution_claimed: bool = False

    def validate(self) -> "SurfaceDescriptor":
        if not all((self.surface_id.strip(), self.provider.strip(), self.product.strip())):
            raise ValueError("OMNISURFACE_IDENTITY_REQUIRED")
        if not self.protocols or not self.capabilities or not self.source_refs:
            raise ValueError("OMNISURFACE_PROTOCOL_CAPABILITY_PROOF_REQUIRED")
        if self.financial_surface and self.maximum_effect != EffectClass.OBSERVE:
            raise ValueError("OMNISURFACE_FINANCIAL_SURFACE_MUST_BE_OBSERVE_ONLY")
        if self.live_execution_claimed:
            raise ValueError("OMNISURFACE_REGISTRY_CANNOT_CLAIM_PROVIDER_EXECUTION")
        return self


@dataclass(frozen=True, slots=True)
class SurfaceAttestation:
    surface_id: str
    endpoint_fingerprint: str
    protocols: tuple[str, ...]
    capabilities: tuple[str, ...]
    proof_refs: tuple[str, ...]
    signature_verified: bool
    provider_identity_verified: bool
    authority_ceiling: EffectClass

    def validate(self) -> "SurfaceAttestation":
        if not all((self.surface_id.strip(), self.endpoint_fingerprint.strip())):
            raise ValueError("OMNISURFACE_ATTESTATION_IDENTITY_REQUIRED")
        if not self.protocols or not self.capabilities or not self.proof_refs:
            raise ValueError("OMNISURFACE_ATTESTATION_CONTENT_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class MissionNeed:
    mission_id: str
    capabilities: tuple[str, ...]
    maximum_effect: EffectClass = EffectClass.INTERNAL
    preferred_protocols: tuple[str, ...] = (
        f"MCP/{MCP_PROTOCOL_VERSION}",
        f"A2A/{A2A_PROTOCOL_VERSION}",
        Protocol.FEDERATION_NATIVE.value,
        Protocol.CONNECTOR.value,
        Protocol.REST.value,
    )
    require_event_driven: bool = False
    financial_execution_requested: bool = False

    def validate(self) -> "MissionNeed":
        if not self.mission_id.strip() or not self.capabilities:
            raise ValueError("OMNISURFACE_MISSION_ID_AND_CAPABILITIES_REQUIRED")
        if self.financial_execution_requested:
            raise PermissionError("OMNISURFACE_AUTONOMOUS_FINANCIAL_EXECUTION_FORBIDDEN")
        return self


@dataclass(frozen=True, slots=True)
class RouteChoice:
    mission_id: str
    selected_surface_ids: tuple[str, ...]
    covered_capabilities: tuple[str, ...]
    missing_capabilities: tuple[str, ...]
    proof_refs: tuple[str, ...]
    external_effect_authorized: bool = False
    provider_execution_proven: bool = False

    @property
    def complete(self) -> bool:
        return not self.missing_capabilities


@dataclass(frozen=True, slots=True)
class AsyncCorrelation:
    mission_id: str
    mission_node_id: str
    fdof_lease_id: str
    provider: str
    provider_call_id: str
    protocol_task_id: str | None = None
    parent_trace_id: str | None = None

    def validate(self) -> "AsyncCorrelation":
        required = (self.mission_id, self.mission_node_id, self.fdof_lease_id, self.provider, self.provider_call_id)
        if not all(str(value).strip() for value in required):
            raise ValueError("OMNISURFACE_ASYNC_CORRELATION_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class SteeringContinuation:
    mission_id: str
    revision: int
    patch_sha256: str
    completed_nodes: tuple[str, ...]
    invalidated_nodes: tuple[str, ...] = ()

    def validate(self) -> "SteeringContinuation":
        if not self.mission_id.strip() or self.revision < 1 or len(self.patch_sha256) != 64:
            raise ValueError("OMNISURFACE_STEERING_CONTINUATION_INVALID")
        if set(self.completed_nodes) & set(self.invalidated_nodes):
            raise ValueError("OMNISURFACE_COMPLETED_NODE_CANNOT_BE_SILENTLY_INVALIDATED")
        return self


@dataclass(frozen=True, slots=True)
class ProviderEventEnvelope:
    event_id: str
    source: str
    event_type: str
    subject: str
    occurred_at: str
    payload_sha256: str
    traceparent: str | None = None

    def validate(self) -> "ProviderEventEnvelope":
        if not all((self.event_id.strip(), self.source.strip(), self.event_type.strip(), self.subject.strip(), self.occurred_at.strip())):
            raise ValueError("OMNISURFACE_EVENT_FIELDS_REQUIRED")
        if len(self.payload_sha256) != 64:
            raise ValueError("OMNISURFACE_EVENT_PAYLOAD_HASH_REQUIRED")
        return self


class OmniSurfaceRegistry:
    def __init__(self, surfaces: Sequence[SurfaceDescriptor] = ()) -> None:
        validated = [surface.validate() for surface in surfaces]
        ids = [surface.surface_id for surface in validated]
        if len(ids) != len(set(ids)):
            raise ValueError("OMNISURFACE_DUPLICATE_SURFACE_ID")
        self._surfaces = {surface.surface_id: surface for surface in validated}

    @property
    def surfaces(self) -> Mapping[str, SurfaceDescriptor]:
        return dict(self._surfaces)

    def admit_future_surface(self, descriptor: SurfaceDescriptor, attestation: SurfaceAttestation) -> "OmniSurfaceRegistry":
        descriptor.validate()
        attestation.validate()
        if descriptor.surface_id != attestation.surface_id:
            raise ValueError("OMNISURFACE_ATTESTATION_SURFACE_MISMATCH")
        if not attestation.signature_verified or not attestation.provider_identity_verified:
            raise PermissionError("OMNISURFACE_ATTESTATION_NOT_VERIFIED")
        if not set(descriptor.protocols) & set(attestation.protocols):
            raise ValueError("OMNISURFACE_PROTOCOL_NEGOTIATION_FAILED")
        if not set(descriptor.capabilities).issubset(set(attestation.capabilities)):
            raise ValueError("OMNISURFACE_CAPABILITY_ADVERTISEMENT_INCOMPLETE")
        if _EFFECT_ORDER[attestation.authority_ceiling] < _EFFECT_ORDER[descriptor.maximum_effect]:
            raise PermissionError("OMNISURFACE_ATTESTED_AUTHORITY_BELOW_DESCRIPTOR_CEILING")
        return OmniSurfaceRegistry(tuple(self._surfaces.values()) + (descriptor,))

    def plan(self, need: MissionNeed) -> RouteChoice:
        need.validate()
        required = set(_clean(need.capabilities))
        uncovered = set(required)
        selected: list[SurfaceDescriptor] = []
        candidates = []
        preferred = {name: len(need.preferred_protocols) - i for i, name in enumerate(need.preferred_protocols)}
        for surface in self._surfaces.values():
            if _EFFECT_ORDER[surface.maximum_effect] < _EFFECT_ORDER[need.maximum_effect]:
                continue
            if need.require_event_driven and not surface.event_sources:
                continue
            overlap = required & set(surface.capabilities)
            if not overlap:
                continue
            protocol_score = max((preferred.get(protocol, 0) for protocol in surface.protocols), default=0)
            candidates.append((surface, protocol_score))
        while uncovered:
            ranked = sorted(
                candidates,
                key=lambda item: (
                    len(set(item[0].capabilities) & uncovered),
                    int(item[0].provider_readback_required),
                    item[1],
                    int(bool(item[0].event_sources)),
                    item[0].surface_id,
                ),
                reverse=True,
            )
            if not ranked or not (set(ranked[0][0].capabilities) & uncovered):
                break
            surface = ranked[0][0]
            selected.append(surface)
            uncovered -= set(surface.capabilities)
            candidates = [item for item in candidates if item[0].surface_id != surface.surface_id]
        refs = _clean(ref for surface in selected for ref in surface.source_refs)
        return RouteChoice(
            mission_id=need.mission_id,
            selected_surface_ids=tuple(surface.surface_id for surface in selected),
            covered_capabilities=tuple(sorted(required - uncovered)),
            missing_capabilities=tuple(sorted(uncovered)),
            proof_refs=refs,
        )

    def manifest(self) -> Mapping[str, object]:
        body = {
            "schema": SCHEMA,
            "version": VERSION,
            "mcp_protocol": MCP_PROTOCOL_VERSION,
            "a2a_protocol": A2A_PROTOCOL_VERSION,
            "external_effects": EXTERNAL_EFFECTS,
            "authority_minting": AUTHORITY_MINTING,
            "financial_execution": FINANCIAL_EXECUTION,
            "surface_count": len(self._surfaces),
            "surfaces": [asdict(self._surfaces[key]) for key in sorted(self._surfaces)],
        }
        return {**body, "sha256": _hash(body)}


MCP_2026 = f"MCP/{MCP_PROTOCOL_VERSION}"
A2A_1 = f"A2A/{A2A_PROTOCOL_VERSION}"


def _surface(
    surface_id: str,
    provider: str,
    product: str,
    state: SurfaceState,
    protocols: Iterable[str],
    capabilities: Iterable[str],
    source_refs: Iterable[str],
    *,
    maximum_effect: EffectClass = EffectClass.INTERNAL,
    readback_signals: Iterable[str] = ("provider_native_receipt",),
    native_ai: Iterable[str] = (),
    event_sources: Iterable[str] = (),
    auth_strategy: str = "PROVIDER_NATIVE_REVALIDATE_ON_USE",
    financial_surface: bool = False,
) -> SurfaceDescriptor:
    return SurfaceDescriptor(
        surface_id=surface_id,
        provider=provider,
        product=product,
        state=state,
        protocols=_clean(protocols),
        capabilities=_clean(capabilities),
        readback_signals=_clean(readback_signals),
        source_refs=_clean(source_refs),
        maximum_effect=maximum_effect,
        auth_strategy=auth_strategy,
        native_ai=_clean(native_ai),
        event_sources=_clean(event_sources),
        financial_surface=financial_surface,
    ).validate()


CURRENT_SURFACES = (
    _surface(
        "OPENAI-GPT6-ASTRA", "OpenAI", "GPT-6 Astra", SurfaceState.MODEL_CATALOG_VERIFIED,
        (Protocol.RESPONSES_API, MCP_2026, Protocol.WEBSOCKET),
        ("reasoning", "coding", "research", "structured_outputs", "web_search", "file_search", "image_generation",
         "computer_use", "hosted_shell", "apply_patch", "skills", "mcp_tools", "async_tool_calling",
         "mid_turn_steering", "reasoning_configuration_update", "multi_agent", "prompt_caching"),
        ("official:openai:gpt-6-astra", "repo:governance:adaptive_intelligence_router_v1"),
        native_ai=("gpt-6-astra",),
    ),
    _surface(
        "OPENAI-GPT56-LUNA", "OpenAI", "GPT-5.6 Luna", SurfaceState.MODEL_CATALOG_VERIFIED,
        (Protocol.RESPONSES_API,),
        ("volume_reasoning", "cost_sensitive_ai", "text", "vision"),
        ("official:openai:model-catalog", "repo:modisa:volume_model"),
        native_ai=("gpt-5.6-luna",),
    ),
    _surface(
        "GOOGLE-APPS-SCRIPT", "Google", "Apps Script", SurfaceState.REPOSITORY_BRIDGE_ADMITTED,
        (Protocol.REST, Protocol.FEDERATION_NATIVE),
        ("workspace_automation", "script_project_management", "script_source_management", "deployment_management", "remote_function_execution"),
        ("official:google:apps-script-api", "repo:workflow:strategic-fuse-appsscript-read-zero-traffic"),
        maximum_effect=EffectClass.REVERSIBLE_WRITE,
        readback_signals=("script_id", "deployment_id", "execution_result", "source_hash", "rollback_receipt"),
        event_sources=("apps_script_trigger",),
        auth_strategy="GOOGLE_OAUTH_USER_CONTEXT_REVALIDATE_SCOPES",
    ),
    _surface(
        "GOOGLE-CLOUD", "Google", "Google Cloud", SurfaceState.REPOSITORY_BRIDGE_ADMITTED,
        (Protocol.REST, Protocol.CLOUDEVENTS, MCP_2026, A2A_1),
        ("cloud_run", "cloud_run_jobs", "workflows", "pubsub", "eventarc", "storage", "iam", "secret_manager", "observability", "serverless_runtime"),
        ("official:gcp:eventarc", "official:gcp:workflows", "repo:docs:FUSE_GCP_OMEGA_V1"),
        maximum_effect=EffectClass.CONSEQUENTIAL,
        readback_signals=("project_id", "service_revision", "iam_policy", "workflow_execution", "event_delivery", "rollback_state"),
        event_sources=("eventarc", "pubsub", "audit_logs"),
        auth_strategy="GOOGLE_IAM_WORKLOAD_IDENTITY_OR_OWNER_OAUTH",
    ),
    _surface(
        "GOOGLE-AI-STUDIO-GEMINI", "Google", "Google AI Studio / Gemini API", SurfaceState.REPOSITORY_BRIDGE_ADMITTED,
        (Protocol.REST, A2A_1),
        ("reasoning", "multimodal", "function_calling", "structured_output", "code_execution", "grounding", "model_diversity"),
        ("official:google:gemini-function-calling", "repo:workflow:sovara-ai-studio-semantic-canary"),
        native_ai=("Gemini",),
    ),
    _surface(
        "GITHUB", "GitHub", "GitHub", SurfaceState.CONNECTED_TOOL_EXPOSED,
        (Protocol.CONNECTOR, Protocol.REST, MCP_2026),
        ("code", "repositories", "branches", "commits", "pull_requests", "issues", "ci", "actions", "provenance", "release_control"),
        ("connector:github", "repo:bubbles:platform-specialist-corps"),
        maximum_effect=EffectClass.CONSEQUENTIAL,
        readback_signals=("commit_sha", "pr_state", "workflow_run", "artifact", "post_merge_head"),
        event_sources=("github_webhook", "github_actions"),
        auth_strategy="GITHUB_APP_OR_OWNER_TOKEN_SCOPED",
    ),
    _surface(
        "GITHUB-COPILOT", "GitHub", "GitHub Copilot", SurfaceState.REPOSITORY_BRIDGE_ADMITTED,
        (MCP_2026, Protocol.FEDERATION_NATIVE),
        ("coding_agent", "custom_agents", "subagents", "code_review", "mcp_tools", "repository_context"),
        ("official:github:copilot-custom-agents", "repo:federation:copilot_pro"),
        native_ai=("GitHub Copilot",),
    ),
    _surface(
        "CANVA", "Canva", "Canva", SurfaceState.CONNECTED_TOOL_EXPOSED,
        (Protocol.CONNECTOR, MCP_2026),
        ("design", "presentation", "creative_ai", "asset_management", "brand_management", "library_search", "export", "comments", "design_edit"),
        ("official:canva:mcp", "connector:canva", "repo:federation:canva_omega_v1"),
        maximum_effect=EffectClass.REVERSIBLE_WRITE,
        readback_signals=("design_id", "design_content", "page_state", "asset_id", "export_receipt"),
        native_ai=("Canva AI", "Magic Studio"),
    ),
    _surface(
        "ADOBE", "Adobe", "Creative Cloud / Acrobat / Firefly", SurfaceState.CONNECTED_TOOL_EXPOSED,
        (Protocol.CONNECTOR, MCP_2026, Protocol.REST),
        ("pdf", "creative", "document", "image", "video", "firefly", "photoshop", "lightroom", "asset_search", "creative_production"),
        ("official:adobe:firefly-services", "official:adobe:ai-registry", "connector:adobe", "repo:federation:adobe_omega_v1"),
        maximum_effect=EffectClass.REVERSIBLE_WRITE,
        readback_signals=("asset_urn", "document_id", "operation_status", "result_asset", "export_receipt"),
        native_ai=("Adobe Firefly",),
    ),
    _surface(
        "GOOGLE-DRIVE", "Google", "Drive / Docs / Sheets / Slides", SurfaceState.CONNECTED_TOOL_EXPOSED,
        (Protocol.CONNECTOR, Protocol.REST),
        ("files", "documents", "spreadsheets", "slides", "storage", "search", "revisions", "comments", "knowledge"),
        ("connector:google-drive", "repo:bubbles:platform-specialist-corps"),
        maximum_effect=EffectClass.REVERSIBLE_WRITE,
        readback_signals=("file_id", "revision", "exact_content", "parent", "permission_state"),
        event_sources=("workspace_events", "drive_change_notifications"),
    ),
    _surface(
        "GMAIL", "Google", "Gmail", SurfaceState.CONNECTED_TOOL_EXPOSED,
        (Protocol.CONNECTOR, Protocol.REST),
        ("email", "search", "threads", "attachments", "labels", "draft", "send", "archive"),
        ("connector:gmail", "repo:bubbles:platform-specialist-corps"),
        maximum_effect=EffectClass.CONSEQUENTIAL,
        readback_signals=("message_id", "thread_id", "label_state", "sent_state"),
        event_sources=("gmail_watch", "pubsub"),
    ),
    _surface(
        "GOOGLE-CALENDAR", "Google", "Google Calendar", SurfaceState.CONNECTED_TOOL_EXPOSED,
        (Protocol.CONNECTOR, Protocol.REST, Protocol.WORKSPACE_EVENTS),
        ("calendar", "scheduling", "availability", "events", "attendees"),
        ("connector:google-calendar", "repo:bubbles:platform-specialist-corps"),
        maximum_effect=EffectClass.CONSEQUENTIAL,
        readback_signals=("event_id", "event_state", "free_busy"),
        event_sources=("workspace_events",),
    ),
    _surface(
        "GOOGLE-CONTACTS", "Google", "Google Contacts", SurfaceState.CONNECTED_TOOL_EXPOSED,
        (Protocol.CONNECTOR, Protocol.REST),
        ("contacts", "identity_resolution", "organizations"),
        ("connector:google-contacts", "repo:bubbles:platform-specialist-corps"),
        maximum_effect=EffectClass.OBSERVE,
        readback_signals=("contact_identity",),
    ),
    _surface(
        "MICROSOFT-COPILOT-STUDIO", "Microsoft", "Copilot Studio", SurfaceState.USER_NAMED_REVALIDATE_RUNTIME,
        (MCP_2026, Protocol.CONNECTOR, A2A_1),
        ("agents", "mcp_tools", "power_platform_connectors", "generative_orchestration", "enterprise_workflows"),
        ("official:microsoft:copilot-studio-mcp", "repo:federation:copilot_pro"),
        maximum_effect=EffectClass.CONSEQUENTIAL,
        native_ai=("Microsoft Copilot",),
    ),
    _surface(
        "OUTLOOK-EMAIL", "Microsoft", "Outlook Email", SurfaceState.CONNECTED_TOOL_EXPOSED,
        (Protocol.CONNECTOR, Protocol.REST),
        ("email", "search", "messages", "threads", "draft"),
        ("connector:microsoft-outlook-email", "repo:bubbles:platform-specialist-corps"),
        maximum_effect=EffectClass.CONSEQUENTIAL,
        readback_signals=("message_id", "folder_state", "draft_state"),
    ),
    _surface(
        "OUTLOOK-CALENDAR", "Microsoft", "Outlook Calendar", SurfaceState.CONNECTED_TOOL_EXPOSED,
        (Protocol.CONNECTOR, Protocol.REST),
        ("calendar", "scheduling", "availability", "events"),
        ("connector:microsoft-outlook-calendar", "repo:bubbles:platform-specialist-corps"),
        maximum_effect=EffectClass.CONSEQUENTIAL,
        readback_signals=("event_id", "event_state", "availability"),
    ),
    _surface(
        "WINDOWS-FEDERATION-PLANE", "Federation", "Windows Execution Plane", SurfaceState.REPOSITORY_BRIDGE_ADMITTED,
        (MCP_2026, Protocol.FEDERATION_NATIVE),
        ("windows", "computer_use", "local_execution", "hosted_windows", "desktop_automation", "task_receipts"),
        ("repo:windows_federation_plane", "repo:windows_federation_plane:mcp_service"),
        maximum_effect=EffectClass.CONSEQUENTIAL,
        readback_signals=("task_receipt", "mcp_result", "host_state", "artifact_hash"),
    ),
    _surface(
        "LUNO-OBSERVER", "Luno", "Luno API / Observer", SurfaceState.REPOSITORY_BRIDGE_ADMITTED,
        (Protocol.REST, Protocol.WEBSOCKET, MCP_2026),
        ("market_data", "ticker", "order_book", "trades", "candles", "account_observation"),
        ("official:luno:api", "repo:federation:capital_execution:luno_public", "repo:federation:capital_execution:luno_account_observer"),
        maximum_effect=EffectClass.OBSERVE,
        readback_signals=("market_snapshot", "permission_proof", "observation_receipt"),
        event_sources=("luno_websocket_feed",),
        financial_surface=True,
        auth_strategy="PUBLIC_OR_READ_ONLY_KEY_ONLY",
    ),
    _surface(
        "LONA-TRADING-ASSISTANT", "LONA", "LONA Trading Assistant", SurfaceState.CONNECTED_TOOL_EXPOSED,
        (Protocol.CONNECTOR, Protocol.FEDERATION_NATIVE),
        ("strategy_research", "backtest", "optimization", "market_data_analysis"),
        ("connector:lona-trading-assistant", "repo:federation:capital_execution:luno_lona_bridge"),
        maximum_effect=EffectClass.OBSERVE,
        financial_surface=True,
        auth_strategy="CONNECTED_ANALYTICS_ONLY_NO_AUTONOMOUS_TRADE",
    ),
    _surface(
        "BOOKING-COM", "Booking.com", "Booking.com", SurfaceState.CONNECTED_TOOL_EXPOSED,
        (Protocol.CONNECTOR,),
        ("travel_discovery", "stays", "attractions", "rental_cars"),
        ("connector:booking-com", "repo:bubbles:platform-specialist-corps"),
        maximum_effect=EffectClass.OBSERVE,
        readback_signals=("provider_result_reference",),
    ),
)


def build_default_registry() -> OmniSurfaceRegistry:
    return OmniSurfaceRegistry(CURRENT_SURFACES)


__all__ = [
    "SCHEMA", "VERSION", "MCP_PROTOCOL_VERSION", "A2A_PROTOCOL_VERSION", "EXTERNAL_EFFECTS",
    "AUTHORITY_MINTING", "FINANCIAL_EXECUTION", "EffectClass", "SurfaceState", "Protocol",
    "SurfaceDescriptor", "SurfaceAttestation", "MissionNeed", "RouteChoice", "AsyncCorrelation",
    "SteeringContinuation", "ProviderEventEnvelope", "OmniSurfaceRegistry", "CURRENT_SURFACES",
    "build_default_registry",
]
