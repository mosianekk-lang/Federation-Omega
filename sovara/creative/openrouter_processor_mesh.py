from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
import math
from typing import Iterable, Mapping, Sequence

from .openrouter_adapter import OpenRouterReceiptState, OpenRouterSemanticReceipt
from .policy import PrivacyClass


OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_CREDENTIAL_REFERENCE = "env:OPENROUTER_API_KEY"


class ProcessorStrategy(str, Enum):
    PINNED = "PINNED"
    AUTO = "AUTO"
    PARETO_CODE = "PARETO_CODE"
    FUSION = "FUSION"
    NITRO = "NITRO"
    FLOOR = "FLOOR"
    FALLBACK = "FALLBACK"


class MeshPlanState(str, Enum):
    READY_SOURCE_ONLY = "READY_SOURCE_ONLY"
    HOLD_NO_CANDIDATE = "HOLD_NO_CANDIDATE"
    HOLD_PRIVACY = "HOLD_PRIVACY"
    HOLD_SPEND = "HOLD_SPEND"
    HOLD_COST_UNRESOLVED = "HOLD_COST_UNRESOLVED"
    HOLD_CAPABILITY = "HOLD_CAPABILITY"


class MeshProofState(str, Enum):
    SOURCE_ONLY = "SOURCE_ONLY"
    CREDENTIAL_VERIFIED = "CREDENTIAL_VERIFIED"
    PROVIDER_EXECUTED = "PROVIDER_EXECUTED"
    SEMANTIC_VERIFIED = "SEMANTIC_VERIFIED"
    BEHAVIOR_PROVEN = "BEHAVIOR_PROVEN"


class EndpointFamily(str, Enum):
    CHAT = "/chat/completions"
    RESPONSES = "/responses"
    MESSAGES = "/messages"
    IMAGES = "/images"
    VIDEOS = "/videos"
    SPEECH = "/audio/speech"
    TRANSCRIPTIONS = "/audio/transcriptions"
    EMBEDDINGS = "/embeddings"
    MODELS = "/models"
    IMAGE_MODELS = "/images/models"
    VIDEO_MODELS = "/videos/models"
    EMBEDDING_MODELS = "/embeddings/models"


_TEXT_OUTPUT = {"text"}
_IMAGE_OUTPUT = {"image", "images"}
_VIDEO_OUTPUT = {"video"}
_SPEECH_OUTPUT = {"speech", "audio"}
_TRANSCRIPTION_OUTPUT = {"transcription", "text_transcription"}
_EMBEDDING_OUTPUT = {"embeddings", "embedding"}
_ALLOWED_EXTERNAL_PRIVACY = {PrivacyClass.PUBLIC, PrivacyClass.INTERNAL}


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _normalise_set(values: Iterable[object] | None) -> frozenset[str]:
    return frozenset(str(value).strip().lower() for value in (values or ()) if str(value).strip())


def _finite_nonnegative(value: object | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return number


def _price_from_record(record: Mapping[str, object], key: str) -> float | None:
    pricing = record.get("pricing")
    if not isinstance(pricing, Mapping):
        return None
    value = _finite_nonnegative(pricing.get(key))
    if value is None:
        return None
    return value


@dataclass(frozen=True, slots=True)
class ModelCapability:
    model_id: str
    input_modalities: frozenset[str]
    output_modalities: frozenset[str]
    supported_parameters: frozenset[str]
    context_length: int | None = None
    prompt_price: float | None = None
    completion_price: float | None = None
    canonical_slug: str | None = None
    provider_count: int | None = None

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("model_id is required")
        if self.context_length is not None and int(self.context_length) <= 0:
            raise ValueError("context_length must be positive when supplied")

    @classmethod
    def from_api_record(cls, record: Mapping[str, object]) -> "ModelCapability":
        architecture = record.get("architecture")
        architecture = architecture if isinstance(architecture, Mapping) else {}
        input_modalities = architecture.get("input_modalities") or record.get("input_modalities") or ()
        output_modalities = architecture.get("output_modalities") or record.get("output_modalities") or ()
        params = record.get("supported_parameters") or ()
        context = record.get("context_length")
        try:
            context_value = int(context) if context is not None else None
        except (TypeError, ValueError):
            context_value = None
        providers = record.get("providers")
        provider_count = len(providers) if isinstance(providers, Sequence) and not isinstance(providers, (str, bytes)) else None
        return cls(
            model_id=str(record.get("id") or record.get("canonical_slug") or "").strip(),
            canonical_slug=str(record.get("canonical_slug") or "").strip() or None,
            input_modalities=_normalise_set(input_modalities),
            output_modalities=_normalise_set(output_modalities),
            supported_parameters=_normalise_set(params),
            context_length=context_value,
            prompt_price=_price_from_record(record, "prompt"),
            completion_price=_price_from_record(record, "completion"),
            provider_count=provider_count,
        )

    @property
    def free_variant(self) -> bool:
        return self.model_id.endswith(":free") or (
            self.prompt_price == 0.0 and self.completion_price == 0.0
        )


@dataclass(frozen=True, slots=True)
class CognitiveCapabilityContract:
    contract_id: str
    required_input_modalities: frozenset[str] = frozenset({"text"})
    required_output_modalities: frozenset[str] = frozenset({"text"})
    required_parameters: frozenset[str] = frozenset()
    minimum_context: int = 1
    strategy: ProcessorStrategy = ProcessorStrategy.PINNED
    exact_model_id: str | None = None
    router_model_id: str | None = None
    require_tools: bool = False
    require_structured_output: bool = False
    require_reasoning: bool = False
    require_zdr: bool = False
    deny_data_collection: bool = False
    web_search: bool = False
    web_fetch: bool = False
    max_prompt_price: float | None = None
    max_completion_price: float | None = None

    def __post_init__(self) -> None:
        if not self.contract_id.strip():
            raise ValueError("contract_id is required")
        if self.minimum_context <= 0:
            raise ValueError("minimum_context must be positive")
        if self.strategy is ProcessorStrategy.PINNED and not (self.exact_model_id or self.router_model_id):
            raise ValueError("PINNED strategy requires exact_model_id or router_model_id")
        for field in ("max_prompt_price", "max_completion_price"):
            value = getattr(self, field)
            if value is not None and (_finite_nonnegative(value) is None):
                raise ValueError(f"{field} must be finite and non-negative")

    @property
    def effective_required_parameters(self) -> frozenset[str]:
        params = set(self.required_parameters)
        if self.require_tools:
            params.update({"tools", "tool_choice"})
        if self.require_structured_output:
            params.add("response_format")
        if self.require_reasoning:
            params.add("reasoning")
        return frozenset(params)


@dataclass(frozen=True, slots=True)
class ProviderEnvelope:
    only: tuple[str, ...] = ()
    order: tuple[str, ...] = ()
    ignore: tuple[str, ...] = ()
    sort: str | None = None
    allow_fallbacks: bool = True
    require_parameters: bool = True
    zdr: bool = False
    data_collection: str | None = None
    max_price_prompt: float | None = None
    max_price_completion: float | None = None

    def as_request(self) -> dict[str, object]:
        result: dict[str, object] = {
            "allow_fallbacks": bool(self.allow_fallbacks),
            "require_parameters": bool(self.require_parameters),
        }
        if self.only:
            result["only"] = list(self.only)
        if self.order:
            result["order"] = list(self.order)
        if self.ignore:
            result["ignore"] = list(self.ignore)
        if self.sort:
            result["sort"] = self.sort
        if self.zdr:
            result["zdr"] = True
        if self.data_collection:
            result["data_collection"] = self.data_collection
        max_price: dict[str, float] = {}
        if self.max_price_prompt is not None:
            max_price["prompt"] = float(self.max_price_prompt)
        if self.max_price_completion is not None:
            max_price["completion"] = float(self.max_price_completion)
        if max_price:
            result["max_price"] = max_price
        return result


@dataclass(frozen=True, slots=True)
class CandidateScore:
    model: ModelCapability
    score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OpenRouterMeshPlan:
    state: MeshPlanState
    contract_id: str
    endpoint: EndpointFamily | None
    model_id: str | None
    candidate_ids: tuple[str, ...]
    provider: Mapping[str, object]
    plugins: tuple[Mapping[str, object], ...]
    credential_reference: str | None
    live_execution_authorized: bool
    external_effect: bool
    reason_codes: tuple[str, ...]
    plan_sha256: str


@dataclass(frozen=True, slots=True)
class OpenRouterMeshReceipt:
    proof_state: MeshProofState
    contract_id: str
    request_sha256: str
    resolved_model: str | None
    provider: str | None
    usage: Mapping[str, object]
    cost_usd: float | None
    semantic_verified: bool
    modality: str
    evidence_refs: tuple[str, ...] = ()

    @property
    def behavioral_proof_inherited(self) -> bool:
        return False


def endpoint_for_outputs(outputs: Iterable[str]) -> EndpointFamily:
    values = _normalise_set(outputs)
    if values & _IMAGE_OUTPUT:
        return EndpointFamily.IMAGES
    if values & _VIDEO_OUTPUT:
        return EndpointFamily.VIDEOS
    if values & _SPEECH_OUTPUT:
        return EndpointFamily.SPEECH
    if values & _TRANSCRIPTION_OUTPUT:
        return EndpointFamily.TRANSCRIPTIONS
    if values & _EMBEDDING_OUTPUT:
        return EndpointFamily.EMBEDDINGS
    return EndpointFamily.CHAT


def discovery_endpoints() -> tuple[EndpointFamily, ...]:
    return (
        EndpointFamily.MODELS,
        EndpointFamily.IMAGE_MODELS,
        EndpointFamily.VIDEO_MODELS,
        EndpointFamily.EMBEDDING_MODELS,
    )


def supports_contract(model: ModelCapability, contract: CognitiveCapabilityContract) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    if not contract.required_input_modalities.issubset(model.input_modalities):
        reasons.append("INPUT_MODALITY_MISMATCH")
    if not contract.required_output_modalities.issubset(model.output_modalities):
        reasons.append("OUTPUT_MODALITY_MISMATCH")
    if contract.minimum_context and (model.context_length or 0) < contract.minimum_context:
        reasons.append("CONTEXT_BELOW_FLOOR")
    missing = contract.effective_required_parameters - model.supported_parameters
    if missing:
        reasons.append("MISSING_REQUIRED_PARAMETERS:" + ",".join(sorted(missing)))
    if contract.exact_model_id and model.model_id != contract.exact_model_id:
        reasons.append("NOT_EXACT_MODEL")
    if contract.max_prompt_price is not None and (model.prompt_price is None or model.prompt_price > contract.max_prompt_price):
        reasons.append("PROMPT_PRICE_ABOVE_CEILING")
    if contract.max_completion_price is not None and (
        model.completion_price is None or model.completion_price > contract.max_completion_price
    ):
        reasons.append("COMPLETION_PRICE_ABOVE_CEILING")
    return not reasons, tuple(reasons)


def rank_candidates(
    models: Iterable[ModelCapability],
    contract: CognitiveCapabilityContract,
) -> tuple[CandidateScore, ...]:
    ranked: list[CandidateScore] = []
    for model in models:
        supported, reasons = supports_contract(model, contract)
        if not supported:
            continue
        score = 0.0
        score += 100.0 if contract.exact_model_id == model.model_id else 0.0
        score += min(float(model.context_length or 0) / max(contract.minimum_context, 1), 10.0)
        if model.free_variant:
            score += 5.0
        if model.provider_count:
            score += min(model.provider_count, 5) * 0.1
        ranked.append(CandidateScore(model=model, score=round(score, 6), reasons=("CAPABILITY_MATCH",)))
    ranked.sort(key=lambda item: (-item.score, item.model.model_id))
    return tuple(ranked)


def _router_model(contract: CognitiveCapabilityContract, ranked: Sequence[CandidateScore]) -> str | None:
    if contract.router_model_id:
        return contract.router_model_id
    if contract.strategy is ProcessorStrategy.AUTO:
        return "openrouter/auto"
    if contract.strategy is ProcessorStrategy.PINNED:
        return contract.exact_model_id or (ranked[0].model.model_id if ranked else None)
    return ranked[0].model.model_id if ranked else None


def _plugins(contract: CognitiveCapabilityContract) -> tuple[Mapping[str, object], ...]:
    plugins: list[Mapping[str, object]] = []
    if contract.strategy is ProcessorStrategy.FUSION:
        plugins.append({"id": "fusion"})
    if contract.web_search:
        plugins.append({"id": "web"})
    if contract.web_fetch:
        plugins.append({"id": "web-fetch"})
    return tuple(plugins)


def compile_mesh_plan(
    *,
    contract: CognitiveCapabilityContract,
    models: Iterable[ModelCapability],
    privacy_class: PrivacyClass,
    provider_envelope: ProviderEnvelope | None = None,
    credential_bound: bool = False,
    runtime_identity: str | None = None,
    finite_spend_authorized: bool = False,
    provider_effect_authorized: bool = False,
) -> OpenRouterMeshPlan:
    ranked = rank_candidates(models, contract)
    candidate_ids = tuple(item.model.model_id for item in ranked)
    endpoint = endpoint_for_outputs(contract.required_output_modalities)

    def held(state: MeshPlanState, reasons: Sequence[str]) -> OpenRouterMeshPlan:
        payload = {
            "state": state.value,
            "contract_id": contract.contract_id,
            "endpoint": endpoint.value,
            "candidates": candidate_ids,
            "reasons": tuple(reasons),
        }
        return OpenRouterMeshPlan(
            state=state,
            contract_id=contract.contract_id,
            endpoint=endpoint,
            model_id=None,
            candidate_ids=candidate_ids,
            provider={},
            plugins=(),
            credential_reference=None,
            live_execution_authorized=False,
            external_effect=False,
            reason_codes=tuple(reasons),
            plan_sha256=_digest(payload),
        )

    if privacy_class not in _ALLOWED_EXTERNAL_PRIVACY:
        return held(MeshPlanState.HOLD_PRIVACY, ("EXTERNAL_PROCESSOR_PRIVACY_CEILING_EXCEEDED",))
    if not ranked and not contract.router_model_id and contract.strategy is not ProcessorStrategy.AUTO:
        return held(MeshPlanState.HOLD_NO_CANDIDATE, ("NO_CURRENT_MODEL_SATISFIES_CONTRACT",))

    model_id = _router_model(contract, ranked)
    if not model_id:
        return held(MeshPlanState.HOLD_NO_CANDIDATE, ("ROUTER_OR_MODEL_ID_UNRESOLVED",))

    selected = ranked[0].model if ranked else None
    paid = selected is not None and not selected.free_variant
    live_requested = bool(credential_bound and runtime_identity and provider_effect_authorized)

    envelope = provider_envelope or ProviderEnvelope(
        sort="price" if contract.strategy is ProcessorStrategy.FLOOR else (
            "throughput" if contract.strategy is ProcessorStrategy.NITRO else None
        ),
        allow_fallbacks=contract.strategy not in {ProcessorStrategy.PINNED},
        require_parameters=True,
        zdr=contract.require_zdr,
        data_collection="deny" if contract.deny_data_collection else None,
        max_price_prompt=contract.max_prompt_price,
        max_price_completion=contract.max_completion_price,
    )
    explicit_price_ceiling = (
        envelope.max_price_prompt is not None and envelope.max_price_completion is not None
    )

    if paid and not finite_spend_authorized:
        return held(MeshPlanState.HOLD_SPEND, ("FINITE_SPEND_AUTHORITY_REQUIRED",))
    if selected is None and live_requested:
        if not finite_spend_authorized:
            return held(
                MeshPlanState.HOLD_COST_UNRESOLVED,
                ("ROUTER_PRICING_UNRESOLVED_FINITE_SPEND_AUTHORITY_REQUIRED",),
            )
        if not explicit_price_ceiling:
            return held(
                MeshPlanState.HOLD_COST_UNRESOLVED,
                ("ROUTER_PRICING_UNRESOLVED_PRICE_CEILING_REQUIRED",),
            )

    provider = envelope.as_request()
    plugins = _plugins(contract)
    live = bool(
        live_requested
        and (not paid or finite_spend_authorized)
        and (selected is not None or explicit_price_ceiling)
    )
    payload = {
        "state": MeshPlanState.READY_SOURCE_ONLY.value,
        "contract_id": contract.contract_id,
        "endpoint": endpoint.value,
        "model_id": model_id,
        "candidates": candidate_ids,
        "provider": provider,
        "plugins": plugins,
        "credential_bound": credential_bound,
        "runtime_identity_bound": bool(runtime_identity),
        "provider_effect_authorized": provider_effect_authorized,
        "finite_spend_authorized": finite_spend_authorized,
        "router_pricing_resolved": selected is not None,
        "explicit_price_ceiling": explicit_price_ceiling,
    }
    return OpenRouterMeshPlan(
        state=MeshPlanState.READY_SOURCE_ONLY,
        contract_id=contract.contract_id,
        endpoint=endpoint,
        model_id=model_id,
        candidate_ids=candidate_ids,
        provider=provider,
        plugins=plugins,
        credential_reference=OPENROUTER_CREDENTIAL_REFERENCE if credential_bound else None,
        live_execution_authorized=live,
        external_effect=False,
        reason_codes=("CAPABILITY_CONTRACT_COMPILED", "LIVE_AUTHORITY_BOUND" if live else "LIVE_AUTHORITY_OPEN"),
        plan_sha256=_digest(payload),
    )


def _validated_semantic_receipt(
    *,
    request_sha256: str,
    resolved_model: str | None,
    provider: str | None,
    cost: float | None,
    semantic_receipt: OpenRouterSemanticReceipt | None,
) -> bool:
    if semantic_receipt is None:
        return False
    if semantic_receipt.state is not OpenRouterReceiptState.SEMANTIC_VERIFIED:
        return False
    if semantic_receipt.request_fingerprint != request_sha256:
        raise ValueError("semantic receipt request fingerprint mismatch")
    if not resolved_model or semantic_receipt.resolved_model != resolved_model:
        raise ValueError("semantic receipt resolved model mismatch")
    if not provider or semantic_receipt.provider != provider:
        raise ValueError("semantic receipt provider mismatch")
    if cost is None or semantic_receipt.cost_usd is None:
        raise ValueError("semantic receipt cost readback required")
    if not math.isclose(float(cost), float(semantic_receipt.cost_usd), rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("semantic receipt cost mismatch")
    return True


def evaluate_mesh_receipt(
    *,
    contract: CognitiveCapabilityContract,
    request_sha256: str,
    modality: str,
    response: Mapping[str, object],
    evidence_refs: Sequence[str] = (),
    semantic_receipt: OpenRouterSemanticReceipt | None = None,
    semantic_verified: bool = False,
) -> OpenRouterMeshReceipt:
    if len(request_sha256.strip()) != 64 or any(ch not in "0123456789abcdef" for ch in request_sha256.strip().lower()):
        raise ValueError("request_sha256 must be a lowercase-compatible SHA-256 value")
    if semantic_verified and semantic_receipt is None:
        raise ValueError("semantic_verified cannot be self-asserted; semantic_receipt is required")

    usage = response.get("usage")
    usage = usage if isinstance(usage, Mapping) else {}
    raw_cost = usage.get("cost") if isinstance(usage, Mapping) else None
    cost = _finite_nonnegative(raw_cost)
    resolved_model = str(response.get("model") or "").strip() or None
    provider = str(response.get("provider") or "").strip() or None

    semantic_proven = _validated_semantic_receipt(
        request_sha256=request_sha256,
        resolved_model=resolved_model,
        provider=provider,
        cost=cost,
        semantic_receipt=semantic_receipt,
    )
    if semantic_proven:
        state = MeshProofState.SEMANTIC_VERIFIED
    elif resolved_model or provider:
        state = MeshProofState.PROVIDER_EXECUTED
    else:
        state = MeshProofState.SOURCE_ONLY

    return OpenRouterMeshReceipt(
        proof_state=state,
        contract_id=contract.contract_id,
        request_sha256=request_sha256,
        resolved_model=resolved_model,
        provider=provider,
        usage=dict(usage),
        cost_usd=cost,
        semantic_verified=semantic_proven,
        modality=str(modality).strip().lower(),
        evidence_refs=tuple(str(item).strip() for item in evidence_refs if str(item).strip()),
    )
