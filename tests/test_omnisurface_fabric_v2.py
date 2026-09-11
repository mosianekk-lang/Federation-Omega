from hashlib import sha256

import pytest

from federation.omnisurface_fabric_v2 import (
    A2A_PROTOCOL_VERSION,
    MCP_PROTOCOL_VERSION,
    AsyncCorrelation,
    EffectClass,
    MissionNeed,
    OmniSurfaceRegistry,
    SteeringContinuation,
    SurfaceAttestation,
    SurfaceDescriptor,
    SurfaceState,
    build_default_registry,
)


def test_required_surface_estate_is_registered():
    registry = build_default_registry()
    required = {
        "OPENAI-GPT6-ASTRA", "OPENAI-GPT56-LUNA", "GOOGLE-APPS-SCRIPT", "GOOGLE-CLOUD",
        "GOOGLE-AI-STUDIO-GEMINI", "CANVA", "ADOBE", "GITHUB", "GITHUB-COPILOT",
        "GOOGLE-DRIVE", "GMAIL", "GOOGLE-CALENDAR", "GOOGLE-CONTACTS",
        "MICROSOFT-COPILOT-STUDIO", "OUTLOOK-EMAIL", "OUTLOOK-CALENDAR",
        "WINDOWS-FEDERATION-PLANE", "LUNO-OBSERVER", "LONA-TRADING-ASSISTANT", "BOOKING-COM",
    }
    assert required.issubset(registry.surfaces)


def test_astra_harvest_exposes_load_bearing_primitives():
    astra = build_default_registry().surfaces["OPENAI-GPT6-ASTRA"]
    assert "async_tool_calling" in astra.capabilities
    assert "mid_turn_steering" in astra.capabilities
    assert "reasoning_configuration_update" in astra.capabilities
    assert "computer_use" in astra.capabilities
    assert "hosted_shell" in astra.capabilities
    assert f"MCP/{MCP_PROTOCOL_VERSION}" in astra.protocols


def test_financial_surfaces_are_observe_only():
    registry = build_default_registry()
    for surface_id in ("LUNO-OBSERVER", "LONA-TRADING-ASSISTANT"):
        surface = registry.surfaces[surface_id]
        assert surface.financial_surface is True
        assert surface.maximum_effect == EffectClass.OBSERVE


def test_autonomous_financial_execution_request_fails_closed():
    need = MissionNeed(
        mission_id="money",
        capabilities=("market_data",),
        maximum_effect=EffectClass.FINANCIAL,
        financial_execution_requested=True,
    )
    with pytest.raises(PermissionError, match="AUTONOMOUS_FINANCIAL_EXECUTION_FORBIDDEN"):
        build_default_registry().plan(need)


def test_capability_plan_can_span_multiple_surfaces():
    route = build_default_registry().plan(MissionNeed(
        mission_id="creative-research",
        capabilities=("research", "presentation", "pdf", "files"),
        maximum_effect=EffectClass.INTERNAL,
    ))
    assert route.complete
    assert "OPENAI-GPT6-ASTRA" in route.selected_surface_ids
    assert any(surface in route.selected_surface_ids for surface in ("CANVA", "GOOGLE-DRIVE"))
    assert "ADOBE" in route.selected_surface_ids
    assert route.external_effect_authorized is False
    assert route.provider_execution_proven is False


def test_event_driven_plan_uses_event_capable_surface():
    route = build_default_registry().plan(MissionNeed(
        mission_id="event-runtime",
        capabilities=("eventarc", "cloud_run"),
        maximum_effect=EffectClass.INTERNAL,
        require_event_driven=True,
    ))
    assert route.complete
    assert route.selected_surface_ids == ("GOOGLE-CLOUD",)


def test_async_correlation_binds_provider_call_to_fdof_lease():
    correlation = AsyncCorrelation(
        mission_id="M1",
        mission_node_id="node-7",
        fdof_lease_id="lease-3",
        provider="OpenAI",
        provider_call_id="call-abc",
        protocol_task_id="task-mcp-1",
        parent_trace_id="00-trace-parent",
    ).validate()
    assert correlation.provider_call_id == "call-abc"
    assert correlation.fdof_lease_id == "lease-3"


def test_steering_cannot_silently_invalidate_completed_work():
    digest = sha256(b"new requirement").hexdigest()
    with pytest.raises(ValueError, match="CANNOT_BE_SILENTLY_INVALIDATED"):
        SteeringContinuation(
            mission_id="M2",
            revision=2,
            patch_sha256=digest,
            completed_nodes=("done",),
            invalidated_nodes=("done",),
        ).validate()


def test_future_surface_admission_is_protocol_and_identity_gated():
    registry = build_default_registry()
    descriptor = SurfaceDescriptor(
        surface_id="FUTURE-X",
        provider="FutureCo",
        product="Future Agent",
        state=SurfaceState.FUTURE_DISCOVERY_ONLY,
        protocols=(f"A2A/{A2A_PROTOCOL_VERSION}",),
        capabilities=("novel_capability",),
        readback_signals=("receipt",),
        source_refs=("provider:future-x:discovery",),
        maximum_effect=EffectClass.INTERNAL,
    )
    attestation = SurfaceAttestation(
        surface_id="FUTURE-X",
        endpoint_fingerprint="sha256:abc",
        protocols=(f"A2A/{A2A_PROTOCOL_VERSION}",),
        capabilities=("novel_capability", "extra"),
        proof_refs=("attestation:1",),
        signature_verified=True,
        provider_identity_verified=True,
        authority_ceiling=EffectClass.INTERNAL,
    )
    expanded = registry.admit_future_surface(descriptor, attestation)
    assert "FUTURE-X" in expanded.surfaces


def test_unverified_future_surface_is_rejected():
    descriptor = SurfaceDescriptor(
        surface_id="FUTURE-Y",
        provider="FutureCo",
        product="Future Tool",
        state=SurfaceState.FUTURE_DISCOVERY_ONLY,
        protocols=(f"MCP/{MCP_PROTOCOL_VERSION}",),
        capabilities=("x",),
        readback_signals=("receipt",),
        source_refs=("provider:future-y",),
        maximum_effect=EffectClass.INTERNAL,
    )
    attestation = SurfaceAttestation(
        surface_id="FUTURE-Y",
        endpoint_fingerprint="sha256:def",
        protocols=(f"MCP/{MCP_PROTOCOL_VERSION}",),
        capabilities=("x",),
        proof_refs=("attestation:2",),
        signature_verified=False,
        provider_identity_verified=True,
        authority_ceiling=EffectClass.INTERNAL,
    )
    with pytest.raises(PermissionError, match="ATTESTATION_NOT_VERIFIED"):
        OmniSurfaceRegistry().admit_future_surface(descriptor, attestation)


def test_manifest_is_deterministic_and_non_executing():
    first = build_default_registry().manifest()
    second = build_default_registry().manifest()
    assert first["sha256"] == second["sha256"]
    assert first["external_effects"] is False
    assert first["authority_minting"] is False
    assert first["financial_execution"] is False
    assert first["surface_count"] >= 20
