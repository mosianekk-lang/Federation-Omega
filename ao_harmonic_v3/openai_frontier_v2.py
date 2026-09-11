from __future__ import annotations

"""OpenAI frontier-model bridge for the existing Adaptive Intelligence Router.

This module is additive. It preserves the proven AIR v1 routing/cost boundary,
selects an OpenAI model profile for the workload, and builds strictly bounded
Responses/WebSocket intents. It does not invoke OpenAI, mint authority, create
credentials, or treat payload construction as provider execution proof.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence

from federation.omnisurface_fabric_v2 import AsyncCorrelation

from .cost_governor import CostClass
from .intelligence_router import (
    AdaptiveIntelligenceRouter,
    IntelligenceAssessment,
    IntelligenceRouteDecision,
    IntelligenceTier,
    ProviderIntelligenceBinding,
)

SCHEMA = "FEDERATION-OPENAI-FRONTIER-BRIDGE-V2"
VERSION = "2.0.0"
SOURCE_CHECKED = "2026-09-11"
EXTERNAL_EFFECTS = False
PROVIDER_EXECUTION = False


class OpenAIWorkloadClass(str, Enum):
    BULK = "BULK"
    BALANCED = "BALANCED"
    HARD_END_TO_END = "HARD_END_TO_END"


@dataclass(frozen=True)
class OpenAIModelProfile:
    profile_id: str
    model_id: str
    workload_class: OpenAIWorkloadClass
    supported_efforts: tuple[str, ...]
    context_window_tokens: int
    max_output_tokens: int
    supports_async_tools: bool
    supports_mid_turn_steering: bool
    supports_configuration_update: bool
    supports_prompt_cache_options: bool
    source_ref: str


LUNA = OpenAIModelProfile(
    profile_id="OPENAI-GPT56-LUNA-V1",
    model_id="gpt-5.6-luna",
    workload_class=OpenAIWorkloadClass.BULK,
    supported_efforts=("none", "low", "medium", "high", "xhigh", "max"),
    context_window_tokens=1_050_000,
    max_output_tokens=128_000,
    supports_async_tools=False,
    supports_mid_turn_steering=False,
    supports_configuration_update=False,
    supports_prompt_cache_options=True,
    source_ref="official:openai:gpt-5.6-luna:2026-09-11",
)

SOL = OpenAIModelProfile(
    profile_id="OPENAI-GPT56-SOL-V1",
    model_id="gpt-5.6-sol",
    workload_class=OpenAIWorkloadClass.BALANCED,
    supported_efforts=("low", "medium", "high", "xhigh", "max"),
    context_window_tokens=1_050_000,
    max_output_tokens=128_000,
    supports_async_tools=False,
    supports_mid_turn_steering=False,
    supports_configuration_update=False,
    supports_prompt_cache_options=True,
    source_ref="official:openai:model-catalog:2026-09-11",
)

ASTRA = OpenAIModelProfile(
    profile_id="OPENAI-GPT6-ASTRA-V1",
    model_id="gpt-6-astra",
    workload_class=OpenAIWorkloadClass.HARD_END_TO_END,
    supported_efforts=("low", "medium", "high", "xhigh", "max"),
    context_window_tokens=1_050_000,
    max_output_tokens=128_000,
    supports_async_tools=True,
    supports_mid_turn_steering=True,
    supports_configuration_update=True,
    supports_prompt_cache_options=True,
    source_ref="official:openai:gpt-6-astra:2026-09-11",
)

PROFILES = {
    OpenAIWorkloadClass.BULK: LUNA,
    OpenAIWorkloadClass.BALANCED: SOL,
    OpenAIWorkloadClass.HARD_END_TO_END: ASTRA,
}

_EFFORT_BY_TIER = {
    IntelligenceTier.INSTANT: "low",
    IntelligenceTier.MEDIUM: "medium",
    IntelligenceTier.HIGH: "high",
    IntelligenceTier.EXTRA_HIGH: "xhigh",
    IntelligenceTier.PRO: "max",
}

_TIER_INDEX = {
    IntelligenceTier.INSTANT: 0,
    IntelligenceTier.MEDIUM: 1,
    IntelligenceTier.HIGH: 2,
    IntelligenceTier.EXTRA_HIGH: 3,
    IntelligenceTier.PRO: 4,
}


class OpenAIFrontierBindingCatalog:
    """Translate AIR assessments into a workload-appropriate OpenAI model binding."""

    @staticmethod
    def choose_workload(
        assessment: IntelligenceAssessment,
        *,
        high_volume: bool = False,
        force_workload: OpenAIWorkloadClass | None = None,
    ) -> OpenAIWorkloadClass:
        if force_workload is not None:
            if (
                force_workload is OpenAIWorkloadClass.BULK
                and _TIER_INDEX[assessment.minimum_tier] >= _TIER_INDEX[IntelligenceTier.HIGH]
            ):
                raise ValueError("OPENAI_FRONTIER_BULK_ROUTE_BELOW_AIR_MINIMUM_QUALITY_FLOOR")
            return force_workload
        if (
            _TIER_INDEX[assessment.desired_tier] >= _TIER_INDEX[IntelligenceTier.EXTRA_HIGH]
            or _TIER_INDEX[assessment.minimum_tier] >= _TIER_INDEX[IntelligenceTier.EXTRA_HIGH]
        ):
            return OpenAIWorkloadClass.HARD_END_TO_END
        if high_volume and _TIER_INDEX[assessment.minimum_tier] <= _TIER_INDEX[IntelligenceTier.MEDIUM]:
            return OpenAIWorkloadClass.BULK
        if (
            _TIER_INDEX[assessment.desired_tier] <= _TIER_INDEX[IntelligenceTier.MEDIUM]
            and _TIER_INDEX[assessment.minimum_tier] <= _TIER_INDEX[IntelligenceTier.MEDIUM]
        ):
            return OpenAIWorkloadClass.BULK
        return OpenAIWorkloadClass.BALANCED

    @classmethod
    def responses_api(
        cls,
        assessment: IntelligenceAssessment,
        *,
        high_volume: bool = False,
        force_workload: OpenAIWorkloadClass | None = None,
        estimated_monthly_cost: float | None = None,
        current_month_spend: float = 0.0,
        already_paid_or_included: bool = False,
        available: bool = True,
        authorised: bool = True,
        hard_cap_or_quota_available: bool = False,
    ) -> ProviderIntelligenceBinding:
        workload = cls.choose_workload(
            assessment,
            high_volume=high_volume,
            force_workload=force_workload,
        )
        profile = PROFILES[workload]
        effort = _EFFORT_BY_TIER[assessment.desired_tier]
        if effort not in profile.supported_efforts:
            raise ValueError("OPENAI_FRONTIER_REASONING_EFFORT_UNSUPPORTED")
        cost_class = (
            CostClass.C2_CONTROLLED_PAID
            if profile is ASTRA or _TIER_INDEX[assessment.desired_tier] >= _TIER_INDEX[IntelligenceTier.EXTRA_HIGH]
            else CostClass.C1_MICRO_SERVERLESS
        )
        return ProviderIntelligenceBinding(
            binding_id=f"{profile.profile_id}::{assessment.desired_tier.value}",
            provider="OPENAI",
            surface="RESPONSES_API",
            tier=assessment.desired_tier,
            model=profile.model_id,
            reasoning_effort=effort,
            available=available,
            authorised=authorised,
            programmatic=True,
            cost_class=cost_class,
            estimated_monthly_cost=estimated_monthly_cost,
            current_month_spend=current_month_spend,
            already_paid_or_included=already_paid_or_included,
            event_driven=True,
            scale_to_zero=True,
            hard_cap_or_quota_available=hard_cap_or_quota_available,
            notes=(
                f"{SCHEMA} {VERSION}; workload={workload.value}; source_checked={SOURCE_CHECKED}; "
                "provider availability, API authority, cost and runtime remain separately proven"
            ),
        )


@dataclass(frozen=True)
class FrontierToolGate:
    permit_id: str
    allow_read_tools: bool = True
    allow_code_interpreter: bool = False
    allow_custom_tools: bool = False
    allow_mcp: bool = False
    allow_image_generation: bool = False
    allow_computer_use: bool = False
    allow_hosted_shell: bool = False
    allow_apply_patch: bool = False

    def validate(self) -> "FrontierToolGate":
        if not self.permit_id.strip():
            raise PermissionError("OPENAI_FRONTIER_TOOL_PERMIT_REQUIRED")
        return self


class FrontierResponsesPayloadBuilder:
    """Build a strict Responses payload after the existing AIR route is admitted."""

    READ_TOOL_TYPES = {"web_search", "file_search"}
    CODE_INTERPRETER_TYPES = {"code_interpreter"}
    CUSTOM_TOOL_TYPES = {"function", "custom"}
    MCP_TOOL_TYPES = {"mcp"}
    IMAGE_TOOL_TYPES = {"image_generation"}
    COMPUTER_TOOL_TYPES = {"computer", "computer_use", "computer_use_preview"}
    SHELL_TOOL_TYPES = {"shell", "hosted_shell", "local_shell"}
    PATCH_TOOL_TYPES = {"apply_patch"}
    ALL_TOOL_TYPES = (
        READ_TOOL_TYPES
        | CODE_INTERPRETER_TYPES
        | CUSTOM_TOOL_TYPES
        | MCP_TOOL_TYPES
        | IMAGE_TOOL_TYPES
        | COMPUTER_TOOL_TYPES
        | SHELL_TOOL_TYPES
        | PATCH_TOOL_TYPES
    )

    @staticmethod
    def _profile_for_decision(decision: IntelligenceRouteDecision) -> OpenAIModelProfile:
        if decision.selected_binding is None:
            raise ValueError("OPENAI_FRONTIER_SELECTED_BINDING_REQUIRED")
        for profile in PROFILES.values():
            if decision.selected_binding.model == profile.model_id:
                return profile
        raise ValueError("OPENAI_FRONTIER_MODEL_NOT_IN_ADMITTED_PROFILE_SET")

    @classmethod
    def _validate_tool(cls, tool: Mapping[str, object], gate: FrontierToolGate, profile: OpenAIModelProfile) -> dict[str, object]:
        if not isinstance(tool, Mapping):
            raise TypeError("OPENAI_FRONTIER_TOOL_MUST_BE_MAPPING")
        tool_type = tool.get("type")
        if not isinstance(tool_type, str) or tool_type not in cls.ALL_TOOL_TYPES:
            raise ValueError("OPENAI_FRONTIER_TOOL_TYPE_NOT_ALLOWLISTED")
        if tool.get("async") is not None and not isinstance(tool.get("async"), bool):
            raise TypeError("OPENAI_FRONTIER_TOOL_ASYNC_MUST_BE_BOOLEAN")
        if tool.get("async") is True:
            if tool_type not in cls.CUSTOM_TOOL_TYPES:
                raise ValueError("OPENAI_FRONTIER_ASYNC_ONLY_FUNCTION_OR_CUSTOM")
            if not profile.supports_async_tools:
                raise ValueError("OPENAI_FRONTIER_MODEL_DOES_NOT_SUPPORT_ASYNC_TOOLS")
        if tool_type in cls.READ_TOOL_TYPES and not gate.allow_read_tools:
            raise PermissionError("OPENAI_FRONTIER_READ_TOOL_NOT_PERMITTED")
        if tool_type in cls.CODE_INTERPRETER_TYPES and not gate.allow_code_interpreter:
            raise PermissionError("OPENAI_FRONTIER_CODE_INTERPRETER_NOT_PERMITTED")
        if tool_type in cls.CUSTOM_TOOL_TYPES and not gate.allow_custom_tools:
            raise PermissionError("OPENAI_FRONTIER_CUSTOM_TOOL_NOT_PERMITTED")
        if tool_type in cls.MCP_TOOL_TYPES and not gate.allow_mcp:
            raise PermissionError("OPENAI_FRONTIER_MCP_NOT_PERMITTED")
        if tool_type in cls.IMAGE_TOOL_TYPES and not gate.allow_image_generation:
            raise PermissionError("OPENAI_FRONTIER_IMAGE_GENERATION_NOT_PERMITTED")
        if tool_type in cls.COMPUTER_TOOL_TYPES and not gate.allow_computer_use:
            raise PermissionError("OPENAI_FRONTIER_COMPUTER_USE_NOT_PERMITTED")
        if tool_type in cls.SHELL_TOOL_TYPES and not gate.allow_hosted_shell:
            raise PermissionError("OPENAI_FRONTIER_SHELL_NOT_PERMITTED")
        if tool_type in cls.PATCH_TOOL_TYPES and not gate.allow_apply_patch:
            raise PermissionError("OPENAI_FRONTIER_APPLY_PATCH_NOT_PERMITTED")
        return dict(tool)

    @classmethod
    def build(
        cls,
        decision: IntelligenceRouteDecision,
        input_data: object,
        *,
        previous_response_id: str | None = None,
        tools: Sequence[Mapping[str, object]] = (),
        tool_gate: FrontierToolGate | None = None,
        tool_choice: str | Mapping[str, object] | None = None,
        parallel_tool_calls: bool | None = None,
        prompt_cache_key: str | None = None,
        prompt_cache_options: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        base = AdaptiveIntelligenceRouter.to_openai_responses_payload(
            decision,
            input_data,
            previous_response_id=previous_response_id,
        )
        profile = cls._profile_for_decision(decision)

        if tools:
            gate = (tool_gate or FrontierToolGate(permit_id="")).validate()
            base["tools"] = [cls._validate_tool(tool, gate, profile) for tool in tools]
        elif tool_gate is not None:
            tool_gate.validate()

        if tool_choice is not None:
            if not tools:
                raise ValueError("OPENAI_FRONTIER_TOOL_CHOICE_REQUIRES_TOOLS")
            if not isinstance(tool_choice, (str, Mapping)):
                raise TypeError("OPENAI_FRONTIER_TOOL_CHOICE_INVALID")
            base["tool_choice"] = dict(tool_choice) if isinstance(tool_choice, Mapping) else tool_choice

        if parallel_tool_calls is not None:
            if not isinstance(parallel_tool_calls, bool):
                raise TypeError("OPENAI_FRONTIER_PARALLEL_TOOL_CALLS_MUST_BE_BOOLEAN")
            base["parallel_tool_calls"] = parallel_tool_calls

        if prompt_cache_key is not None:
            if not isinstance(prompt_cache_key, str) or not prompt_cache_key.strip() or len(prompt_cache_key) > 512:
                raise ValueError("OPENAI_FRONTIER_PROMPT_CACHE_KEY_INVALID")
            base["prompt_cache_key"] = prompt_cache_key

        if prompt_cache_options is not None:
            if not profile.supports_prompt_cache_options:
                raise ValueError("OPENAI_FRONTIER_MODEL_DOES_NOT_SUPPORT_PROMPT_CACHE_OPTIONS")
            if not isinstance(prompt_cache_options, Mapping):
                raise TypeError("OPENAI_FRONTIER_PROMPT_CACHE_OPTIONS_MUST_BE_MAPPING")
            allowed = {"mode", "ttl", "comparison_response_id"}
            unknown = set(prompt_cache_options) - allowed
            if unknown:
                raise ValueError(f"OPENAI_FRONTIER_PROMPT_CACHE_OPTIONS_UNSUPPORTED:{sorted(unknown)}")
            if prompt_cache_options.get("ttl") not in {None, "30m"}:
                raise ValueError("OPENAI_FRONTIER_PROMPT_CACHE_TTL_UNSUPPORTED")
            base["prompt_cache_options"] = dict(prompt_cache_options)

        return base


@dataclass(frozen=True)
class AstraSteeringIntent:
    previous_response_id: str
    input: str
    single_agent: bool = True
    conversation_bound: bool = False
    automatic_compaction: bool = False

    def to_websocket_event(self) -> dict[str, object]:
        if not self.previous_response_id.strip() or not self.input.strip():
            raise ValueError("OPENAI_ASTRA_STEERING_RESPONSE_ID_AND_INPUT_REQUIRED")
        if not self.single_agent:
            raise ValueError("OPENAI_ASTRA_STEERING_REQUIRES_SINGLE_AGENT")
        if self.conversation_bound:
            raise ValueError("OPENAI_ASTRA_STEERING_CONVERSATION_BOUND_UNSUPPORTED")
        if self.automatic_compaction:
            raise ValueError("OPENAI_ASTRA_STEERING_AUTOMATIC_COMPACTION_UNSUPPORTED")
        return {"type": "response.steer", "previous_response_id": self.previous_response_id, "input": self.input}


@dataclass(frozen=True)
class AstraReasoningContinuation:
    request_level_effort: str
    effective_effort: str
    standard_mode: bool = True
    single_agent: bool = True

    def configuration_update(self, target_effort: str) -> tuple["AstraReasoningContinuation", dict[str, object]]:
        if not self.standard_mode or not self.single_agent:
            raise ValueError("OPENAI_ASTRA_CONFIGURATION_UPDATE_REQUIRES_STANDARD_SINGLE_AGENT")
        if self.request_level_effort not in ASTRA.supported_efforts or self.effective_effort not in ASTRA.supported_efforts:
            raise ValueError("OPENAI_ASTRA_CONFIGURATION_STATE_INVALID")
        if target_effort not in ASTRA.supported_efforts:
            raise ValueError("OPENAI_ASTRA_CONFIGURATION_EFFORT_UNSUPPORTED")
        item = {"type": "configuration_update", "reasoning": {"effort": target_effort}}
        return (
            AstraReasoningContinuation(
                request_level_effort=self.request_level_effort,
                effective_effort=target_effort,
                standard_mode=True,
                single_agent=True,
            ),
            item,
        )


@dataclass(frozen=True)
class AsyncToolResult:
    call_id: str
    output: object
    tool_kind: str = "function"

    def to_response_input(self, correlation: AsyncCorrelation) -> dict[str, object]:
        correlation.validate()
        if not self.call_id.strip() or self.call_id != correlation.provider_call_id:
            raise ValueError("OPENAI_FRONTIER_ASYNC_RESULT_CALL_ID_MISMATCH")
        if self.tool_kind not in {"function", "custom"}:
            raise ValueError("OPENAI_FRONTIER_ASYNC_RESULT_TOOL_KIND_UNSUPPORTED")
        return {
            "type": "function_call_output" if self.tool_kind == "function" else "custom_tool_call_output",
            "call_id": self.call_id,
            "output": self.output,
        }


__all__ = [
    "SCHEMA", "VERSION", "SOURCE_CHECKED", "EXTERNAL_EFFECTS", "PROVIDER_EXECUTION",
    "OpenAIWorkloadClass", "OpenAIModelProfile", "LUNA", "SOL", "ASTRA", "PROFILES",
    "OpenAIFrontierBindingCatalog", "FrontierToolGate", "FrontierResponsesPayloadBuilder",
    "AstraSteeringIntent", "AstraReasoningContinuation", "AsyncToolResult",
]
