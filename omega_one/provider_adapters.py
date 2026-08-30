"""Provider-neutral, non-effect capability adapters for Omega-One.

The descriptors in this module record documented orchestration surfaces without
turning documentation into provider authority.  All adapters are deliberately
local: ``invoke`` produces a deterministic fake receipt and never opens a network
connection, resolves credentials, charges a provider, or performs an external
effect.

Zero-dilution invariant
-----------------------
The Universal Capability Contract (UCC) is the source of truth.  A request carries
the exact contract and its canonical hash.  Provider descriptors are additive
annotations only; routing or fallback cannot weaken effect, authority, privacy,
proof, maturity, or cost gates in order to make a request pass.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum, IntEnum
import hashlib
import json
from typing import Any, Iterable, Mapping

from .interop import EffectClass, UniversalCapabilityContract


REQUEST_SCHEMA_VERSION = "omega.provider-request.v1"
RECEIPT_SCHEMA_VERSION = "omega.provider-receipt.v1"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def ucc_sha256(ucc: UniversalCapabilityContract) -> str:
    """Return the deterministic hash used to bind an envelope to its full UCC."""

    return _sha256(asdict(ucc))


class ProviderId(str, Enum):
    OPENAI_CHATGPT = "openai_chatgpt"
    GEMINI_ADK = "gemini_adk"
    GITHUB_COPILOT = "github_copilot"


class CapabilityFlag(str, Enum):
    MULTI_AGENT = "multi_agent"
    NESTED_SUBAGENTS = "nested_subagents"
    PARALLEL_AGENTS = "parallel_agents"
    PARALLEL_TOOLS = "parallel_tools"
    HANDOFFS = "handoffs"
    AGENTS_AS_TOOLS = "agents_as_tools"
    BACKGROUND_TASKS = "background_tasks"
    POLLING = "polling"
    WEBHOOKS = "webhooks"
    BATCH_QUEUE = "batch_queue"
    TRACING = "tracing"
    EVALS = "evals"
    GUARDRAILS = "guardrails"
    HUMAN_APPROVAL = "human_approval"


class FeatureMaturity(str, Enum):
    STABLE = "STABLE"
    PREVIEW = "PREVIEW"
    BETA = "BETA"
    EXPERIMENTAL = "EXPERIMENTAL"
    UNVERIFIED = "UNVERIFIED"


_MATURITY_RANK = {
    FeatureMaturity.UNVERIFIED: 0,
    FeatureMaturity.EXPERIMENTAL: 1,
    FeatureMaturity.PREVIEW: 2,
    FeatureMaturity.BETA: 2,
    FeatureMaturity.STABLE: 3,
}


class RoutingMode(str, Enum):
    ROOT_SYNTHESIS = "ROOT_SYNTHESIS"
    HANDOFF = "HANDOFF"
    AGENT_AS_TOOL = "AGENT_AS_TOOL"
    WORKFLOW_GRAPH = "WORKFLOW_GRAPH"


class AsyncMode(str, Enum):
    SYNCHRONOUS = "SYNCHRONOUS"
    STREAMING = "STREAMING"
    POLLING = "POLLING"
    WEBHOOK = "WEBHOOK"
    BATCH = "BATCH"
    SCHEDULED = "SCHEDULED"


class AvailabilityState(str, Enum):
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    HALF_OPEN = "HALF_OPEN"
    OPEN = "OPEN"


class AuthorityLevel(IntEnum):
    A0_READ_ONLY = 0
    A1_INTERNAL = 1
    A2_EFFECT = 2
    A3_OWNER_RESERVED = 3


class PrivacyClass(IntEnum):
    P0_PUBLIC = 0
    P1_INTERNAL = 1
    P2_CONFIDENTIAL = 2
    P3_RESTRICTED = 3


def _authority_from_ucc(value: str) -> AuthorityLevel:
    prefix = str(value).strip().upper().split("_", 1)[0]
    table = {
        "A0": AuthorityLevel.A0_READ_ONLY,
        "A1": AuthorityLevel.A1_INTERNAL,
        "A2": AuthorityLevel.A2_EFFECT,
        "A3": AuthorityLevel.A3_OWNER_RESERVED,
    }
    if prefix not in table:
        raise ValueError("UCC_AUTHORITY_CEILING_INVALID")
    return table[prefix]


def _privacy_from_ucc(value: str) -> PrivacyClass:
    prefix = str(value).strip().upper().split("_", 1)[0]
    table = {
        "P0": PrivacyClass.P0_PUBLIC,
        "P1": PrivacyClass.P1_INTERNAL,
        "P2": PrivacyClass.P2_CONFIDENTIAL,
        "P3": PrivacyClass.P3_RESTRICTED,
    }
    if prefix not in table:
        raise ValueError("UCC_PRIVACY_CLASS_INVALID")
    return table[prefix]


@dataclass(frozen=True)
class CapabilitySupport:
    flag: CapabilityFlag
    supported: bool
    maturity: FeatureMaturity
    preview: bool = False
    portable_semantics: bool = True
    notes: tuple[str, ...] = ()
    source_urls: tuple[str, ...] = ()

    def validate(self) -> "CapabilitySupport":
        if self.preview and self.maturity == FeatureMaturity.STABLE:
            raise ValueError(f"PREVIEW_STABLE_CONTRADICTION:{self.flag.value}")
        if self.supported and self.maturity == FeatureMaturity.UNVERIFIED:
            raise ValueError(f"SUPPORTED_FEATURE_UNVERIFIED:{self.flag.value}")
        if not self.supported and self.portable_semantics:
            object.__setattr__(self, "portable_semantics", False)
        return self


@dataclass(frozen=True)
class ConcurrencySemantics:
    parallel_agents: bool
    nested_delegation: bool
    recommended_concurrency: int | None
    documented_hard_limit: int | None
    shared_mutable_state_safe: bool
    worker_model_scope: str
    worker_tool_scope: str
    notes: tuple[str, ...] = ()

    def validate(self) -> "ConcurrencySemantics":
        for value in (self.recommended_concurrency, self.documented_hard_limit):
            if value is not None and value < 1:
                raise ValueError("CONCURRENCY_LIMIT_MUST_BE_POSITIVE")
        if not self.parallel_agents and self.recommended_concurrency not in (None, 1):
            raise ValueError("NON_PARALLEL_PROVIDER_HAS_PARALLEL_RECOMMENDATION")
        return self


@dataclass(frozen=True)
class RoutingSemantics:
    modes: tuple[RoutingMode, ...]
    dynamic_model_routing: bool
    root_owns_final_answer: bool
    deterministic_graph_guaranteed: bool
    specialist_policy_isolation: bool
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class AsyncSemantics:
    modes: tuple[AsyncMode, ...]
    durable_queue_documented: bool
    supports_detached_completion: bool
    completion_signals: tuple[str, ...]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class RetentionPrivacyNotes:
    max_privacy_class: PrivacyClass
    zero_retention_possible: bool | None
    temporary_storage_possible: bool
    local_context_inherited_by_cloud: bool
    cross_provider_transfer_default: bool
    notes: tuple[str, ...]


@dataclass(frozen=True)
class AuthorityCostGate:
    authority_ceiling: AuthorityLevel = AuthorityLevel.A0_READ_ONLY
    live_execution_authorized: bool = False
    external_effects_authorized: bool = False
    credentials_authorized: bool = False
    owner_approval_required_for_effects: bool = True
    cost_authorization_required: bool = True
    local_cost_ceiling_units: int = 0

    def validate(self) -> "AuthorityCostGate":
        if self.local_cost_ceiling_units < 0:
            raise ValueError("LOCAL_COST_CEILING_NEGATIVE")
        if self.external_effects_authorized and not self.live_execution_authorized:
            raise ValueError("EXTERNAL_EFFECT_REQUIRES_LIVE_EXECUTION")
        return self


@dataclass(frozen=True)
class ProviderAvailabilityMetadata:
    provider: ProviderId
    availability: AvailabilityState = AvailabilityState.AVAILABLE
    circuit: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    failure_threshold: int = 3
    retry_after_seconds: int | None = None
    observed_at: str | None = None
    reason: str = "LOCAL_DESCRIPTOR_READY"

    def validate(self) -> "ProviderAvailabilityMetadata":
        if self.consecutive_failures < 0 or self.failure_threshold < 1:
            raise ValueError("CIRCUIT_COUNTER_INVALID")
        if self.retry_after_seconds is not None and self.retry_after_seconds < 0:
            raise ValueError("RETRY_AFTER_INVALID")
        return self

    @property
    def accepts_requests(self) -> bool:
        return self.availability in {AvailabilityState.AVAILABLE, AvailabilityState.DEGRADED} and self.circuit != CircuitState.OPEN


@dataclass(frozen=True)
class ProviderCapabilityDescriptor:
    provider: ProviderId
    display_name: str
    descriptor_version: str
    descriptor_maturity: FeatureMaturity
    capabilities: tuple[CapabilitySupport, ...]
    concurrency: ConcurrencySemantics
    routing: RoutingSemantics
    async_semantics: AsyncSemantics
    retention_privacy: RetentionPrivacyNotes
    gate: AuthorityCostGate
    source_urls: tuple[str, ...]
    ucc: UniversalCapabilityContract
    zero_dilution: bool = True
    preservation_state: str = "FULL_UCC_PRESERVED"

    def validate(self) -> "ProviderCapabilityDescriptor":
        if not self.display_name.strip() or not self.descriptor_version.strip():
            raise ValueError("PROVIDER_DESCRIPTOR_IDENTITY_REQUIRED")
        if not self.zero_dilution or self.preservation_state != "FULL_UCC_PRESERVED":
            raise ValueError("ZERO_DILUTION_REQUIRED")
        self.ucc.validate()
        if self.ucc.metadata.get("omega.zero_dilution") is not True:
            raise ValueError("UCC_ZERO_DILUTION_METADATA_REQUIRED")
        self.concurrency.validate()
        self.gate.validate()
        by_flag: dict[CapabilityFlag, CapabilitySupport] = {}
        for capability in self.capabilities:
            capability.validate()
            if capability.flag in by_flag:
                raise ValueError(f"DUPLICATE_CAPABILITY_FLAG:{capability.flag.value}")
            by_flag[capability.flag] = capability
        if not self.source_urls:
            raise ValueError("PROVIDER_DOCUMENTATION_SOURCE_REQUIRED")
        return self

    def support(self, flag: CapabilityFlag | str) -> CapabilitySupport:
        wanted = CapabilityFlag(flag)
        for capability in self.capabilities:
            if capability.flag == wanted:
                return capability
        return CapabilitySupport(wanted, False, FeatureMaturity.UNVERIFIED, portable_semantics=False)

    @property
    def capability_flags(self) -> Mapping[str, bool]:
        return {item.flag.value: item.supported for item in self.capabilities}

    @property
    def preview_flags(self) -> tuple[str, ...]:
        return tuple(sorted(item.flag.value for item in self.capabilities if item.preview))

    @property
    def ucc_sha256(self) -> str:
        return ucc_sha256(self.ucc)

    @property
    def descriptor_sha256(self) -> str:
        return _sha256(asdict(self))


def provider_neutral_ucc() -> UniversalCapabilityContract:
    """Create the shared, non-effect UCC bound to every local adapter request."""

    contract = UniversalCapabilityContract(
        capability_id="UCC-OMEGA-PROVIDER-ORCHESTRATION-A0",
        name="provider_neutral_agent_orchestration",
        description="Validate and simulate a provider-neutral agent orchestration request without provider execution.",
        input_schema={
            "type": "object",
            "required": ["task"],
            "properties": {"task": {"type": "string"}, "context": {"type": "object"}},
            "additionalProperties": True,
        },
        output_schema={
            "type": "object",
            "required": ["invocation_id", "status", "payload_sha256"],
            "properties": {
                "invocation_id": {"type": "string"},
                "status": {"const": "LOCAL_FAKE_COMPLETED"},
                "payload_sha256": {"type": "string"},
            },
            "additionalProperties": False,
        },
        effect_class=EffectClass.READ,
        authority_ceiling="A0_READ_ONLY",
        privacy_class="P1_INTERNAL",
        rollback_required=False,
        proof_required=("deterministic_receipt", "ucc_hash_binding", "no_external_effect"),
        metadata={
            "omega.zero_dilution": True,
            "omega.preservation_state": "FULL_UCC_PRESERVED",
            "omega.provider_execution_authorized": False,
            "omega.portable_contract": True,
        },
    )
    return contract.validate()


@dataclass(frozen=True)
class ProviderRequestEnvelope:
    request_id: str
    mission_id: str
    provider: ProviderId
    capability: CapabilityFlag
    payload: Mapping[str, Any]
    ucc: UniversalCapabilityContract
    source_ucc_sha256: str
    schema_version: str = REQUEST_SCHEMA_VERSION
    authority: AuthorityLevel = AuthorityLevel.A0_READ_ONLY
    privacy_class: PrivacyClass = PrivacyClass.P1_INTERNAL
    effect_class: EffectClass = EffectClass.READ
    consequential: bool = False
    owner_authorized: bool = False
    estimated_cost_units: int = 0
    cost_budget_units: int = 0
    cost_authorized: bool = False
    allow_preview: bool = False
    allow_fallback: bool = False
    fallback_providers: tuple[ProviderId, ...] = ()
    allow_cross_provider_data_transfer: bool = False
    deterministic_local_only: bool = True
    network_requested: bool = False
    credentials_requested: bool = False

    def canonical_body(self) -> Mapping[str, Any]:
        return asdict(self)

    @property
    def request_sha256(self) -> str:
        return _sha256(self.canonical_body())


@dataclass(frozen=True)
class AdmissionDecision:
    admitted: bool
    provider: ProviderId
    reasons: tuple[str, ...] = ()

    def require(self) -> "AdmissionDecision":
        if not self.admitted:
            raise ProviderRequestRejected(self.reasons)
        return self


class ProviderRequestRejected(RuntimeError):
    def __init__(self, reasons: Iterable[str]):
        self.reasons = tuple(sorted(set(str(reason) for reason in reasons if str(reason))))
        super().__init__("PROVIDER_REQUEST_REJECTED:" + "|".join(self.reasons))


@dataclass(frozen=True)
class ProviderInvocationReceipt:
    request_id: str
    mission_id: str
    provider: ProviderId
    capability: CapabilityFlag
    status: str
    invocation_id: str
    output: Mapping[str, Any]
    source_ucc_sha256: str
    descriptor_sha256: str
    network_used: bool
    credentials_used: bool
    external_effect: bool
    cost_units: int
    fallback_from: ProviderId | None = None
    schema_version: str = RECEIPT_SCHEMA_VERSION
    receipt_sha256: str = ""

    def verified(self) -> bool:
        body = asdict(self)
        supplied = body.pop("receipt_sha256")
        return bool(supplied) and supplied == _sha256(body)


class ProviderAdapter:
    """Fail-closed local adapter over one provider capability descriptor."""

    def __init__(
        self,
        descriptor: ProviderCapabilityDescriptor,
        availability: ProviderAvailabilityMetadata | None = None,
    ) -> None:
        self.descriptor = descriptor.validate()
        self._availability = (
            availability
            or ProviderAvailabilityMetadata(provider=descriptor.provider)
        ).validate()
        if self._availability.provider != self.descriptor.provider:
            raise ValueError("AVAILABILITY_PROVIDER_MISMATCH")

    @property
    def availability(self) -> ProviderAvailabilityMetadata:
        return self._availability

    def set_availability(self, metadata: ProviderAvailabilityMetadata) -> None:
        metadata.validate()
        if metadata.provider != self.descriptor.provider:
            raise ValueError("AVAILABILITY_PROVIDER_MISMATCH")
        self._availability = metadata

    def record_failure(self, reason: str = "LOCAL_HEALTH_FAILURE") -> ProviderAvailabilityMetadata:
        count = self._availability.consecutive_failures + 1
        circuit = CircuitState.OPEN if count >= self._availability.failure_threshold else CircuitState.CLOSED
        availability = AvailabilityState.UNAVAILABLE if circuit == CircuitState.OPEN else AvailabilityState.DEGRADED
        self._availability = replace(
            self._availability,
            availability=availability,
            circuit=circuit,
            consecutive_failures=count,
            reason=reason,
        )
        return self._availability

    def record_success(self) -> ProviderAvailabilityMetadata:
        self._availability = replace(
            self._availability,
            availability=AvailabilityState.AVAILABLE,
            circuit=CircuitState.CLOSED,
            consecutive_failures=0,
            retry_after_seconds=None,
            reason="LOCAL_HEALTH_SUCCESS",
        )
        return self._availability

    def build_request(
        self,
        *,
        request_id: str,
        mission_id: str,
        capability: CapabilityFlag | str,
        payload: Mapping[str, Any],
        **overrides: Any,
    ) -> ProviderRequestEnvelope:
        contract = self.descriptor.ucc
        return ProviderRequestEnvelope(
            request_id=request_id,
            mission_id=mission_id,
            provider=self.descriptor.provider,
            capability=CapabilityFlag(capability),
            payload=dict(payload),
            ucc=contract,
            source_ucc_sha256=ucc_sha256(contract),
            **overrides,
        )

    def admit(self, request: ProviderRequestEnvelope) -> AdmissionDecision:
        reasons: list[str] = []
        if request.schema_version != REQUEST_SCHEMA_VERSION:
            reasons.append("REQUEST_SCHEMA_VERSION_UNSUPPORTED")
        if not request.request_id.strip() or not request.mission_id.strip():
            reasons.append("REQUEST_IDENTITY_REQUIRED")
        if request.provider != self.descriptor.provider:
            reasons.append("REQUEST_PROVIDER_MISMATCH")
        if not isinstance(request.payload, Mapping):
            reasons.append("REQUEST_PAYLOAD_MAPPING_REQUIRED")
        if request.source_ucc_sha256 != ucc_sha256(request.ucc):
            reasons.append("SOURCE_UCC_HASH_MISMATCH")
        if request.source_ucc_sha256 != self.descriptor.ucc_sha256:
            reasons.append("DESCRIPTOR_UCC_HASH_MISMATCH")
        if request.ucc.metadata.get("omega.zero_dilution") is not True:
            reasons.append("ZERO_DILUTION_METADATA_REQUIRED")
        if request.ucc.metadata.get("omega.preservation_state") != "FULL_UCC_PRESERVED":
            reasons.append("FULL_UCC_PRESERVATION_REQUIRED")
        try:
            request.ucc.validate()
            ucc_authority = _authority_from_ucc(request.ucc.authority_ceiling)
            ucc_privacy = _privacy_from_ucc(request.ucc.privacy_class)
        except ValueError as exc:
            reasons.append(str(exc))
            ucc_authority = AuthorityLevel.A0_READ_ONLY
            ucc_privacy = PrivacyClass.P3_RESTRICTED

        support = self.descriptor.support(request.capability)
        if not support.supported:
            reasons.append("CAPABILITY_NOT_SUPPORTED")
        if support.preview and not request.allow_preview:
            reasons.append("PREVIEW_OPT_IN_REQUIRED")
        if request.authority > ucc_authority or request.authority > self.descriptor.gate.authority_ceiling:
            reasons.append("AUTHORITY_CEILING_EXCEEDED")
        if request.privacy_class < ucc_privacy:
            reasons.append("PRIVACY_CLASS_DILUTION")
        if request.privacy_class > self.descriptor.retention_privacy.max_privacy_class:
            reasons.append("PROVIDER_PRIVACY_CLASS_UNSUPPORTED")
        if request.effect_class != request.ucc.effect_class:
            reasons.append("EFFECT_CLASS_UCC_MISMATCH")
        if (
            (request.effect_class != EffectClass.READ or request.consequential)
            and self.descriptor.gate.owner_approval_required_for_effects
            and not request.owner_authorized
        ):
            reasons.append("OWNER_AUTHORITY_REQUIRED")
        if request.effect_class != EffectClass.READ or request.consequential:
            reasons.append("LOCAL_ADAPTER_NON_EFFECT_ONLY")
        if not request.deterministic_local_only:
            reasons.append("LIVE_PROVIDER_EXECUTION_DISABLED")
        if request.network_requested:
            reasons.append("NETWORK_USE_NOT_AUTHORIZED")
        if request.credentials_requested:
            reasons.append("CREDENTIAL_USE_NOT_AUTHORIZED")
        if request.estimated_cost_units < 0 or request.cost_budget_units < 0:
            reasons.append("COST_VALUE_NEGATIVE")
        if request.estimated_cost_units > request.cost_budget_units:
            reasons.append("COST_BUDGET_EXCEEDED")
        if request.estimated_cost_units > 0 and not request.cost_authorized:
            reasons.append("COST_AUTHORIZATION_REQUIRED")
        if request.estimated_cost_units > self.descriptor.gate.local_cost_ceiling_units:
            reasons.append("LOCAL_COST_CEILING_EXCEEDED")
        if not self._availability.accepts_requests:
            if self._availability.circuit == CircuitState.OPEN:
                reasons.append("PROVIDER_CIRCUIT_OPEN")
            else:
                reasons.append("PROVIDER_UNAVAILABLE")
        return AdmissionDecision(not reasons, self.descriptor.provider, tuple(sorted(set(reasons))))

    def validate_request(self, request: ProviderRequestEnvelope) -> AdmissionDecision:
        """Compatibility name for callers that treat admission as validation."""

        return self.admit(request)

    def invoke_local(
        self,
        request: ProviderRequestEnvelope,
        *,
        fallback_from: ProviderId | None = None,
    ) -> ProviderInvocationReceipt:
        self.admit(request).require()
        payload_sha = _sha256(request.payload)
        invocation_id = f"fake-{self.descriptor.provider.value}-{request.request_sha256[:24]}"
        output = {
            "invocation_id": invocation_id,
            "status": "LOCAL_FAKE_COMPLETED",
            "payload_sha256": payload_sha,
        }
        receipt = ProviderInvocationReceipt(
            request_id=request.request_id,
            mission_id=request.mission_id,
            provider=self.descriptor.provider,
            capability=request.capability,
            status="LOCAL_FAKE_COMPLETED",
            invocation_id=invocation_id,
            output=output,
            source_ucc_sha256=request.source_ucc_sha256,
            descriptor_sha256=self.descriptor.descriptor_sha256,
            network_used=False,
            credentials_used=False,
            external_effect=False,
            cost_units=0,
            fallback_from=fallback_from,
        )
        body = asdict(receipt)
        body.pop("receipt_sha256")
        return replace(receipt, receipt_sha256=_sha256(body))

    def invoke(self, request: ProviderRequestEnvelope) -> ProviderInvocationReceipt:
        """Invoke the deterministic fake only; live provider execution is absent."""

        return self.invoke_local(request)

    def fake_invoke(self, request: ProviderRequestEnvelope) -> ProviderInvocationReceipt:
        """Explicit alias for the only invocation mode this adapter implements."""

        return self.invoke_local(request)


class OpenAIChatGPTAdapter(ProviderAdapter):
    def __init__(self, availability: ProviderAvailabilityMetadata | None = None) -> None:
        super().__init__(_openai_descriptor(), availability)


class GeminiADKAdapter(ProviderAdapter):
    def __init__(self, availability: ProviderAvailabilityMetadata | None = None) -> None:
        super().__init__(_gemini_descriptor(), availability)


class CopilotAdapter(ProviderAdapter):
    def __init__(self, availability: ProviderAvailabilityMetadata | None = None) -> None:
        super().__init__(_copilot_descriptor(), availability)


# Descriptive aliases keep integrations provider-oriented without duplicating logic.
OpenAIProviderAdapter = OpenAIChatGPTAdapter
GeminiProviderAdapter = GeminiADKAdapter
CopilotProviderAdapter = CopilotAdapter


class ProviderAdapterRegistry:
    """Resolve primary/fallback adapters without weakening the request contract."""

    _FAILOVER_ELIGIBLE = {"PROVIDER_UNAVAILABLE", "PROVIDER_CIRCUIT_OPEN"}

    def __init__(self, adapters: Iterable[ProviderAdapter] = ()) -> None:
        self.adapters: dict[ProviderId, ProviderAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: ProviderAdapter) -> None:
        self.adapters[adapter.descriptor.provider] = adapter

    def get(self, provider: ProviderId | str) -> ProviderAdapter:
        key = ProviderId(provider)
        if key not in self.adapters:
            raise ProviderRequestRejected(("PROVIDER_ADAPTER_NOT_REGISTERED",))
        return self.adapters[key]

    def safe_fallback_vetoes(
        self,
        request: ProviderRequestEnvelope,
        fallback_provider: ProviderId | str,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        fallback_id = ProviderId(fallback_provider)
        if not request.allow_fallback:
            reasons.append("FALLBACK_NOT_AUTHORIZED")
        if fallback_id not in request.fallback_providers:
            reasons.append("FALLBACK_NOT_DECLARED")
        if fallback_id == request.provider:
            reasons.append("FALLBACK_EQUALS_PRIMARY")
        if not request.allow_cross_provider_data_transfer:
            reasons.append("CROSS_PROVIDER_DATA_TRANSFER_NOT_AUTHORIZED")
        if request.effect_class != EffectClass.READ or request.consequential:
            reasons.append("FALLBACK_EFFECT_VETO")
        if request.estimated_cost_units != 0:
            reasons.append("FALLBACK_COST_VETO")
        try:
            primary = self.get(request.provider)
            fallback = self.get(fallback_id)
        except ProviderRequestRejected as exc:
            reasons.extend(exc.reasons)
            return tuple(sorted(set(reasons)))

        source_support = primary.descriptor.support(request.capability)
        target_support = fallback.descriptor.support(request.capability)
        if not source_support.portable_semantics or not target_support.portable_semantics:
            reasons.append("FALLBACK_SEMANTICS_NOT_PORTABLE")
        if not target_support.supported:
            reasons.append("FALLBACK_CAPABILITY_UNSUPPORTED")
        if _MATURITY_RANK[target_support.maturity] < _MATURITY_RANK[source_support.maturity]:
            reasons.append("FALLBACK_MATURITY_REGRESSION")
        if target_support.preview and not request.allow_preview:
            reasons.append("FALLBACK_PREVIEW_OPT_IN_REQUIRED")
        if request.privacy_class > fallback.descriptor.retention_privacy.max_privacy_class:
            reasons.append("FALLBACK_PRIVACY_CLASS_UNSUPPORTED")
        if request.authority > fallback.descriptor.gate.authority_ceiling:
            reasons.append("FALLBACK_AUTHORITY_CEILING_EXCEEDED")
        if fallback.descriptor.ucc_sha256 != request.source_ucc_sha256:
            reasons.append("FALLBACK_UCC_HASH_MISMATCH")
        candidate = replace(request, provider=fallback_id)
        reasons.extend(fallback.admit(candidate).reasons)
        return tuple(sorted(set(reasons)))

    def invoke(self, request: ProviderRequestEnvelope) -> ProviderInvocationReceipt:
        primary = self.get(request.provider)
        decision = primary.admit(request)
        if decision.admitted:
            return primary.invoke_local(request)
        if not decision.reasons or set(decision.reasons) - self._FAILOVER_ELIGIBLE:
            raise ProviderRequestRejected(decision.reasons)
        if not request.allow_fallback:
            raise ProviderRequestRejected(decision.reasons + ("FALLBACK_NOT_AUTHORIZED",))

        accumulated = list(decision.reasons)
        for fallback_id in request.fallback_providers:
            vetoes = self.safe_fallback_vetoes(request, fallback_id)
            if vetoes:
                accumulated.extend(f"{fallback_id.value}:{reason}" for reason in vetoes)
                continue
            fallback = self.get(fallback_id)
            candidate = replace(request, provider=fallback_id)
            return fallback.invoke_local(candidate, fallback_from=request.provider)
        raise ProviderRequestRejected(accumulated + ["NO_SAFE_FALLBACK"])


def default_provider_adapters() -> tuple[ProviderAdapter, ...]:
    return (OpenAIChatGPTAdapter(), GeminiADKAdapter(), CopilotAdapter())


def default_provider_registry() -> ProviderAdapterRegistry:
    return ProviderAdapterRegistry(default_provider_adapters())


def _support(
    flag: CapabilityFlag,
    supported: bool,
    maturity: FeatureMaturity,
    *,
    preview: bool = False,
    portable: bool = True,
    notes: tuple[str, ...] = (),
    sources: tuple[str, ...] = (),
) -> CapabilitySupport:
    return CapabilitySupport(flag, supported, maturity, preview, portable, notes, sources)


_OPENAI_SUBAGENTS = "https://learn.chatgpt.com/docs/agent-configuration/subagents"
_OPENAI_MULTI_AGENT = "https://developers.openai.com/api/docs/guides/responses-multi-agent"
_OPENAI_AGENTS = "https://developers.openai.com/api/docs/guides/agents"
_OPENAI_ORCHESTRATION = "https://developers.openai.com/api/docs/guides/agents/orchestration"
_OPENAI_BACKGROUND = "https://developers.openai.com/api/docs/guides/background"
_OPENAI_BATCH = "https://developers.openai.com/api/docs/guides/batch"
_OPENAI_OBSERVABILITY = "https://developers.openai.com/api/docs/guides/agents/integrations-observability"
_OPENAI_GUARDRAILS = "https://developers.openai.com/api/docs/guides/agents/guardrails-approvals"
_OPENAI_FUNCTIONS = "https://developers.openai.com/api/docs/guides/function-calling"


def _openai_descriptor() -> ProviderCapabilityDescriptor:
    sources = (
        _OPENAI_SUBAGENTS,
        _OPENAI_MULTI_AGENT,
        _OPENAI_AGENTS,
        _OPENAI_ORCHESTRATION,
        _OPENAI_BACKGROUND,
        _OPENAI_BATCH,
        _OPENAI_OBSERVABILITY,
        _OPENAI_GUARDRAILS,
        _OPENAI_FUNCTIONS,
    )
    capabilities = (
        _support(CapabilityFlag.MULTI_AGENT, True, FeatureMaturity.BETA, preview=True, sources=(_OPENAI_MULTI_AGENT,)),
        _support(CapabilityFlag.NESTED_SUBAGENTS, True, FeatureMaturity.BETA, preview=True, sources=(_OPENAI_MULTI_AGENT,)),
        _support(CapabilityFlag.PARALLEL_AGENTS, True, FeatureMaturity.STABLE, sources=(_OPENAI_SUBAGENTS,)),
        _support(CapabilityFlag.PARALLEL_TOOLS, True, FeatureMaturity.STABLE, sources=(_OPENAI_FUNCTIONS,)),
        _support(CapabilityFlag.HANDOFFS, True, FeatureMaturity.STABLE, sources=(_OPENAI_ORCHESTRATION,)),
        _support(CapabilityFlag.AGENTS_AS_TOOLS, True, FeatureMaturity.STABLE, sources=(_OPENAI_ORCHESTRATION,)),
        _support(CapabilityFlag.BACKGROUND_TASKS, True, FeatureMaturity.STABLE, sources=(_OPENAI_BACKGROUND,)),
        _support(CapabilityFlag.POLLING, True, FeatureMaturity.STABLE, sources=(_OPENAI_BACKGROUND,)),
        _support(CapabilityFlag.WEBHOOKS, True, FeatureMaturity.STABLE, sources=("https://developers.openai.com/api/docs/guides/webhooks",)),
        _support(CapabilityFlag.BATCH_QUEUE, True, FeatureMaturity.STABLE, portable=False, sources=(_OPENAI_BATCH,)),
        _support(CapabilityFlag.TRACING, True, FeatureMaturity.STABLE, sources=(_OPENAI_OBSERVABILITY,)),
        _support(CapabilityFlag.EVALS, True, FeatureMaturity.STABLE, sources=("https://developers.openai.com/api/docs/guides/agent-evals",)),
        _support(CapabilityFlag.GUARDRAILS, True, FeatureMaturity.STABLE, sources=(_OPENAI_GUARDRAILS,)),
        _support(CapabilityFlag.HUMAN_APPROVAL, True, FeatureMaturity.STABLE, sources=(_OPENAI_GUARDRAILS,)),
    )
    return ProviderCapabilityDescriptor(
        provider=ProviderId.OPENAI_CHATGPT,
        display_name="OpenAI / ChatGPT Work / Codex",
        descriptor_version="2026-08-30",
        descriptor_maturity=FeatureMaturity.STABLE,
        capabilities=capabilities,
        concurrency=ConcurrencySemantics(
            parallel_agents=True,
            nested_delegation=True,
            recommended_concurrency=3,
            documented_hard_limit=None,
            shared_mutable_state_safe=False,
            worker_model_scope="shared-in-responses-multi-agent; configurable-in-codex-and-agents-sdk",
            worker_tool_scope="shared-in-responses-multi-agent; configurable-in-agents-sdk",
            notes=("Responses Multi-agent default and recommendation is three active subagents.",),
        ),
        routing=RoutingSemantics(
            modes=(RoutingMode.ROOT_SYNTHESIS, RoutingMode.HANDOFF, RoutingMode.AGENT_AS_TOOL),
            dynamic_model_routing=True,
            root_owns_final_answer=True,
            deterministic_graph_guaranteed=False,
            specialist_policy_isolation=True,
            notes=("Handoffs transfer ownership; agents-as-tools preserve manager ownership.",),
        ),
        async_semantics=AsyncSemantics(
            modes=(AsyncMode.SYNCHRONOUS, AsyncMode.STREAMING, AsyncMode.POLLING, AsyncMode.WEBHOOK, AsyncMode.BATCH, AsyncMode.SCHEDULED),
            durable_queue_documented=False,
            supports_detached_completion=True,
            completion_signals=("poll response", "webhook", "scheduled result"),
            notes=("Background responses, Batch, and product scheduled tasks are distinct surfaces.",),
        ),
        retention_privacy=RetentionPrivacyNotes(
            max_privacy_class=PrivacyClass.P3_RESTRICTED,
            zero_retention_possible=True,
            temporary_storage_possible=True,
            local_context_inherited_by_cloud=False,
            cross_provider_transfer_default=False,
            notes=("Background execution may require temporary storage; Work Cloud does not inherit local device context.",),
        ),
        gate=AuthorityCostGate(),
        source_urls=sources,
        ucc=provider_neutral_ucc(),
    )


_ADK_MULTI_AGENT = "https://google.github.io/adk-docs/agents/multi-agents/"
_ADK_PARALLEL = "https://google.github.io/adk-docs/agents/workflow-agents/parallel-agents/"
_ADK_RUNTIME = "https://google.github.io/adk-docs/runtime/"
_ADK_CALLBACKS = "https://google.github.io/adk-docs/callbacks/"


def _gemini_descriptor() -> ProviderCapabilityDescriptor:
    sources = (_ADK_MULTI_AGENT, _ADK_PARALLEL, _ADK_RUNTIME, _ADK_CALLBACKS)
    capabilities = (
        _support(CapabilityFlag.MULTI_AGENT, True, FeatureMaturity.STABLE, sources=(_ADK_MULTI_AGENT,)),
        _support(CapabilityFlag.NESTED_SUBAGENTS, True, FeatureMaturity.STABLE, sources=(_ADK_MULTI_AGENT,)),
        _support(CapabilityFlag.PARALLEL_AGENTS, True, FeatureMaturity.STABLE, sources=(_ADK_PARALLEL,)),
        _support(CapabilityFlag.PARALLEL_TOOLS, False, FeatureMaturity.UNVERIFIED, portable=False, notes=("Not promoted from general model tool calling into the ADK adapter contract.",)),
        _support(CapabilityFlag.HANDOFFS, True, FeatureMaturity.STABLE, sources=(_ADK_MULTI_AGENT,)),
        _support(CapabilityFlag.AGENTS_AS_TOOLS, True, FeatureMaturity.STABLE, sources=(_ADK_MULTI_AGENT,)),
        _support(CapabilityFlag.BACKGROUND_TASKS, False, FeatureMaturity.UNVERIFIED, portable=False),
        _support(CapabilityFlag.POLLING, False, FeatureMaturity.UNVERIFIED, portable=False),
        _support(CapabilityFlag.WEBHOOKS, False, FeatureMaturity.UNVERIFIED, portable=False),
        _support(CapabilityFlag.BATCH_QUEUE, False, FeatureMaturity.UNVERIFIED, portable=False),
        _support(CapabilityFlag.TRACING, True, FeatureMaturity.STABLE, sources=(_ADK_CALLBACKS,)),
        _support(CapabilityFlag.EVALS, True, FeatureMaturity.STABLE, sources=("https://google.github.io/adk-docs/evaluate/",)),
        _support(CapabilityFlag.GUARDRAILS, True, FeatureMaturity.STABLE, sources=(_ADK_CALLBACKS,)),
        _support(CapabilityFlag.HUMAN_APPROVAL, False, FeatureMaturity.UNVERIFIED, portable=False),
    )
    return ProviderCapabilityDescriptor(
        provider=ProviderId.GEMINI_ADK,
        display_name="Google Gemini / Agent Development Kit",
        descriptor_version="2026-08-30-conservative",
        descriptor_maturity=FeatureMaturity.STABLE,
        capabilities=capabilities,
        concurrency=ConcurrencySemantics(
            parallel_agents=True,
            nested_delegation=True,
            recommended_concurrency=None,
            documented_hard_limit=None,
            shared_mutable_state_safe=False,
            worker_model_scope="configurable-by-agent",
            worker_tool_scope="configurable-by-agent",
            notes=("ParallelAgent is a workflow primitive; no provider-wide safe concurrency number is asserted.",),
        ),
        routing=RoutingSemantics(
            modes=(RoutingMode.ROOT_SYNTHESIS, RoutingMode.HANDOFF, RoutingMode.AGENT_AS_TOOL, RoutingMode.WORKFLOW_GRAPH),
            dynamic_model_routing=True,
            root_owns_final_answer=False,
            deterministic_graph_guaranteed=False,
            specialist_policy_isolation=True,
        ),
        async_semantics=AsyncSemantics(
            modes=(AsyncMode.SYNCHRONOUS, AsyncMode.STREAMING),
            durable_queue_documented=False,
            supports_detached_completion=False,
            completion_signals=(),
            notes=("No generic durable queue is promoted into this adapter without deployment-specific proof.",),
        ),
        retention_privacy=RetentionPrivacyNotes(
            max_privacy_class=PrivacyClass.P2_CONFIDENTIAL,
            zero_retention_possible=None,
            temporary_storage_possible=True,
            local_context_inherited_by_cloud=False,
            cross_provider_transfer_default=False,
            notes=("Retention depends on the selected Gemini/Vertex runtime and deployment; no umbrella guarantee is inherited.",),
        ),
        gate=AuthorityCostGate(),
        source_urls=sources,
        ucc=provider_neutral_ucc(),
    )


_COPILOT_CODING_AGENT = "https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent"
_COPILOT_CUSTOM_AGENTS = "https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/create-custom-agents"
_COPILOT_SECURITY = "https://docs.github.com/en/copilot/concepts/agents/coding-agent/security"


def _copilot_descriptor() -> ProviderCapabilityDescriptor:
    sources = (_COPILOT_CODING_AGENT, _COPILOT_CUSTOM_AGENTS, _COPILOT_SECURITY)
    capabilities = (
        _support(CapabilityFlag.MULTI_AGENT, False, FeatureMaturity.UNVERIFIED, portable=False, notes=("No provider-neutral multi-agent runtime contract is asserted.",)),
        _support(CapabilityFlag.NESTED_SUBAGENTS, False, FeatureMaturity.UNVERIFIED, portable=False),
        _support(CapabilityFlag.PARALLEL_AGENTS, False, FeatureMaturity.UNVERIFIED, portable=False),
        _support(CapabilityFlag.PARALLEL_TOOLS, False, FeatureMaturity.UNVERIFIED, portable=False),
        _support(CapabilityFlag.HANDOFFS, False, FeatureMaturity.UNVERIFIED, portable=False),
        _support(CapabilityFlag.AGENTS_AS_TOOLS, False, FeatureMaturity.UNVERIFIED, portable=False),
        _support(CapabilityFlag.BACKGROUND_TASKS, True, FeatureMaturity.STABLE, portable=False, sources=(_COPILOT_CODING_AGENT,)),
        _support(CapabilityFlag.POLLING, False, FeatureMaturity.UNVERIFIED, portable=False),
        _support(CapabilityFlag.WEBHOOKS, False, FeatureMaturity.UNVERIFIED, portable=False),
        _support(CapabilityFlag.BATCH_QUEUE, False, FeatureMaturity.UNVERIFIED, portable=False),
        _support(CapabilityFlag.TRACING, False, FeatureMaturity.UNVERIFIED, portable=False),
        _support(CapabilityFlag.EVALS, False, FeatureMaturity.UNVERIFIED, portable=False),
        _support(CapabilityFlag.GUARDRAILS, True, FeatureMaturity.STABLE, portable=False, sources=(_COPILOT_SECURITY,)),
        _support(CapabilityFlag.HUMAN_APPROVAL, True, FeatureMaturity.STABLE, portable=False, sources=(_COPILOT_CODING_AGENT,)),
    )
    return ProviderCapabilityDescriptor(
        provider=ProviderId.GITHUB_COPILOT,
        display_name="GitHub Copilot coding agent",
        descriptor_version="2026-08-30-conservative",
        descriptor_maturity=FeatureMaturity.STABLE,
        capabilities=capabilities,
        concurrency=ConcurrencySemantics(
            parallel_agents=False,
            nested_delegation=False,
            recommended_concurrency=None,
            documented_hard_limit=None,
            shared_mutable_state_safe=False,
            worker_model_scope="provider-managed",
            worker_tool_scope="repository-and-policy-scoped",
            notes=("Independent coding tasks are not treated as an interchangeable nested-agent runtime.",),
        ),
        routing=RoutingSemantics(
            modes=(RoutingMode.WORKFLOW_GRAPH,),
            dynamic_model_routing=False,
            root_owns_final_answer=True,
            deterministic_graph_guaranteed=False,
            specialist_policy_isolation=False,
        ),
        async_semantics=AsyncSemantics(
            modes=(AsyncMode.SYNCHRONOUS, AsyncMode.STREAMING),
            durable_queue_documented=False,
            supports_detached_completion=True,
            completion_signals=("pull request or task status",),
            notes=("Background coding-agent work is provider-managed and not promoted as a generic queue.",),
        ),
        retention_privacy=RetentionPrivacyNotes(
            max_privacy_class=PrivacyClass.P2_CONFIDENTIAL,
            zero_retention_possible=None,
            temporary_storage_possible=True,
            local_context_inherited_by_cloud=False,
            cross_provider_transfer_default=False,
            notes=("Repository, organization, enterprise, and Copilot policy remain authoritative.",),
        ),
        gate=AuthorityCostGate(),
        source_urls=sources,
        ucc=provider_neutral_ucc(),
    )


__all__ = [
    "AdmissionDecision",
    "AsyncMode",
    "AsyncSemantics",
    "AuthorityCostGate",
    "AuthorityLevel",
    "AvailabilityState",
    "CapabilityFlag",
    "CapabilitySupport",
    "CircuitState",
    "ConcurrencySemantics",
    "CopilotAdapter",
    "FeatureMaturity",
    "GeminiADKAdapter",
    "GeminiProviderAdapter",
    "OpenAIChatGPTAdapter",
    "OpenAIProviderAdapter",
    "PrivacyClass",
    "ProviderAdapter",
    "ProviderAdapterRegistry",
    "ProviderAvailabilityMetadata",
    "ProviderCapabilityDescriptor",
    "ProviderId",
    "ProviderInvocationReceipt",
    "ProviderRequestEnvelope",
    "ProviderRequestRejected",
    "RetentionPrivacyNotes",
    "RoutingMode",
    "RoutingSemantics",
    "CopilotProviderAdapter",
    "default_provider_adapters",
    "default_provider_registry",
    "provider_neutral_ucc",
    "ucc_sha256",
]
