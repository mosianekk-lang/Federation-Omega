import inspect

import pytest

from ao_harmonic_v3 import AdaptiveIntelligenceRouter, IntelligenceSignals, IntelligenceTier
from ao_harmonic_v3.openai_frontier_v2 import (
    ASTRA,
    LUNA,
    AsyncToolResult,
    AstraReasoningContinuation,
    AstraSteeringIntent,
    FrontierResponsesPayloadBuilder,
    FrontierToolGate,
    OpenAIFrontierBindingCatalog,
    OpenAIWorkloadClass,
)
from federation.omnisurface_fabric_v2 import AsyncCorrelation


def _routed(signals: IntelligenceSignals, **binding_kwargs):
    router = AdaptiveIntelligenceRouter()
    assessment = router.assess(signals)
    binding = OpenAIFrontierBindingCatalog.responses_api(
        assessment,
        estimated_monthly_cost=0.0,
        **binding_kwargs,
    )
    return assessment, router.route(signals, [binding], assessment=assessment)


def test_low_pressure_routes_to_luna_volume_lane():
    signals = IntelligenceSignals(
        task_id="bulk", complexity=0.10, consequence=0.10, uncertainty=0.10,
        dependency_density=0.10, adversarial_complexity=0.05, evidence_volume=0.05,
        ambiguity=0.10, irreversibility=0.05, long_horizon=0.10, required_accuracy=0.70,
    )
    assessment, decision = _routed(signals, high_volume=True)
    assert assessment.desired_tier in {IntelligenceTier.INSTANT, IntelligenceTier.MEDIUM}
    assert decision.selected_binding is not None
    assert decision.selected_binding.model == LUNA.model_id
    assert decision.execution_allowed is True


def test_extra_high_pressure_routes_to_astra():
    signals = IntelligenceSignals(
        task_id="hard", consequence=0.95, uncertainty=0.80, irreversibility=0.90,
        adversarial_complexity=0.85, required_accuracy=0.99,
    )
    assessment, decision = _routed(signals)
    assert assessment.desired_tier in {IntelligenceTier.EXTRA_HIGH, IntelligenceTier.PRO}
    assert decision.selected_binding is not None
    assert decision.selected_binding.model == ASTRA.model_id
    assert decision.selected_binding.reasoning_effort in ASTRA.supported_efforts


def test_bulk_force_cannot_cross_air_quality_floor():
    router = AdaptiveIntelligenceRouter()
    assessment = router.assess(IntelligenceSignals(
        task_id="legal", high_stakes=True, legal_or_regulatory=True, consequence=0.80,
    ))
    assert assessment.minimum_tier == IntelligenceTier.HIGH
    with pytest.raises(ValueError, match="BULK_ROUTE_BELOW_AIR_MINIMUM_QUALITY_FLOOR"):
        OpenAIFrontierBindingCatalog.responses_api(
            assessment, force_workload=OpenAIWorkloadClass.BULK, estimated_monthly_cost=0.0,
        )


def test_unknown_paid_cost_still_fails_closed_through_existing_air():
    router = AdaptiveIntelligenceRouter()
    signals = IntelligenceSignals(
        task_id="astra-cost-hold", consequence=0.95, uncertainty=0.80, irreversibility=0.90,
    )
    assessment = router.assess(signals)
    binding = OpenAIFrontierBindingCatalog.responses_api(assessment)
    decision = router.route(signals, [binding], assessment=assessment)
    assert binding.model == ASTRA.model_id
    assert decision.execution_allowed is False
    assert decision.owner_approval_required is True


def test_astra_async_function_tool_builds_only_with_explicit_tool_gate():
    _, decision = _routed(IntelligenceSignals(
        task_id="async", consequence=0.95, uncertainty=0.80, irreversibility=0.90,
    ))
    tool = {
        "type": "function", "name": "query_federation_state",
        "description": "Read bounded Federation state.",
        "parameters": {"type": "object", "properties": {}}, "async": True,
    }
    with pytest.raises(PermissionError, match="TOOL_PERMIT_REQUIRED"):
        FrontierResponsesPayloadBuilder.build(decision, "inspect", tools=[tool])
    payload = FrontierResponsesPayloadBuilder.build(
        decision, "inspect", tools=[tool],
        tool_gate=FrontierToolGate(permit_id="PERMIT-READ-001", allow_custom_tools=True),
        parallel_tool_calls=True,
    )
    assert payload["model"] == ASTRA.model_id
    assert payload["tools"][0]["async"] is True
    assert payload["parallel_tool_calls"] is True
    assert "permit_id" not in payload


def test_async_tool_is_rejected_on_luna():
    _, decision = _routed(IntelligenceSignals(
        task_id="bulk-async", complexity=0.10, consequence=0.10, uncertainty=0.10,
    ), high_volume=True)
    assert decision.selected_binding is not None
    assert decision.selected_binding.model == LUNA.model_id
    with pytest.raises(ValueError, match="MODEL_DOES_NOT_SUPPORT_ASYNC_TOOLS"):
        FrontierResponsesPayloadBuilder.build(
            decision, "bulk",
            tools=[{"type": "function", "name": "later", "parameters": {}, "async": True}],
            tool_gate=FrontierToolGate(permit_id="PERMIT-ASYNC-001", allow_custom_tools=True),
        )


def test_computer_shell_patch_mcp_and_image_are_fail_closed_by_default():
    _, decision = _routed(IntelligenceSignals(
        task_id="high-effect-tools", consequence=0.95, uncertainty=0.80, irreversibility=0.90,
    ))
    cases = [
        ({"type": "computer"}, "COMPUTER_USE_NOT_PERMITTED"),
        ({"type": "shell"}, "SHELL_NOT_PERMITTED"),
        ({"type": "apply_patch"}, "APPLY_PATCH_NOT_PERMITTED"),
        ({"type": "mcp", "server_label": "fuse"}, "MCP_NOT_PERMITTED"),
        ({"type": "image_generation"}, "IMAGE_GENERATION_NOT_PERMITTED"),
    ]
    for tool, message in cases:
        with pytest.raises(PermissionError, match=message):
            FrontierResponsesPayloadBuilder.build(
                decision, "bounded", tools=[tool],
                tool_gate=FrontierToolGate(permit_id="PERMIT-BASE-001"),
            )


def test_prompt_cache_contract_is_strict():
    _, decision = _routed(IntelligenceSignals(
        task_id="cache", consequence=0.95, uncertainty=0.80, irreversibility=0.90,
    ))
    payload = FrontierResponsesPayloadBuilder.build(
        decision, "cached work", prompt_cache_key="fuse:mission:cache",
        prompt_cache_options={"ttl": "30m"},
    )
    assert payload["prompt_cache_key"] == "fuse:mission:cache"
    assert payload["prompt_cache_options"] == {"ttl": "30m"}
    with pytest.raises(ValueError, match="PROMPT_CACHE_TTL_UNSUPPORTED"):
        FrontierResponsesPayloadBuilder.build(
            decision, "cached work", prompt_cache_options={"ttl": "24h"},
        )


def test_astra_steering_event_matches_bounded_websocket_contract():
    event = AstraSteeringIntent(
        previous_response_id="resp_1",
        input="Use the revised requirement without restarting completed work.",
    ).to_websocket_event()
    assert event == {
        "type": "response.steer", "previous_response_id": "resp_1",
        "input": "Use the revised requirement without restarting completed work.",
    }
    with pytest.raises(ValueError, match="CONVERSATION_BOUND_UNSUPPORTED"):
        AstraSteeringIntent("resp_1", "change", conversation_bound=True).to_websocket_event()
    with pytest.raises(ValueError, match="AUTOMATIC_COMPACTION_UNSUPPORTED"):
        AstraSteeringIntent("resp_1", "change", automatic_compaction=True).to_websocket_event()


def test_configuration_update_preserves_request_level_effort():
    state = AstraReasoningContinuation(request_level_effort="medium", effective_effort="medium")
    updated, item = state.configuration_update("high")
    assert state.request_level_effort == "medium"
    assert updated.request_level_effort == "medium"
    assert updated.effective_effort == "high"
    assert item == {"type": "configuration_update", "reasoning": {"effort": "high"}}
    with pytest.raises(ValueError, match="EFFORT_UNSUPPORTED"):
        state.configuration_update("none")


def test_async_result_is_bound_to_original_provider_call_and_fdof_lease():
    correlation = AsyncCorrelation(
        mission_id="M1", mission_node_id="node-1", fdof_lease_id="lease-1",
        provider="OPENAI", provider_call_id="call_1",
    )
    item = AsyncToolResult(call_id="call_1", output={"ok": True}).to_response_input(correlation)
    assert item["type"] == "function_call_output"
    assert item["call_id"] == "call_1"
    with pytest.raises(ValueError, match="CALL_ID_MISMATCH"):
        AsyncToolResult(call_id="call_2", output="wrong").to_response_input(correlation)


def test_builder_has_no_sampling_escape_hatch_for_astra():
    parameters = inspect.signature(FrontierResponsesPayloadBuilder.build).parameters
    assert "temperature" not in parameters
    assert "top_p" not in parameters
    assert "top_logprobs" not in parameters
    assert "logprobs" not in parameters


def test_source_layer_claims_no_provider_execution():
    from ao_harmonic_v3 import openai_frontier_v2
    assert openai_frontier_v2.EXTERNAL_EFFECTS is False
    assert openai_frontier_v2.PROVIDER_EXECUTION is False
