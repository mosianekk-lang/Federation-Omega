from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
import re
from typing import Mapping, Sequence

from .policy import (
    ContentClass,
    Eligibility,
    MatureContext,
    PrivacyClass,
    RoutePolicy,
    RouteType,
    evaluate_route,
)


OPENROUTER_CHAT_COMPLETIONS_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_CREDENTIAL_REFERENCE = "env:OPENROUTER_API_KEY"
_PROVIDER_SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_ALLOWED_MESSAGE_ROLES = {"system", "user", "assistant", "tool"}
_FORBIDDEN_PAYLOAD_KEYS = {"api_key", "authorization", "credential", "password", "secret", "token"}
_PRIVACY_RANK = {
    PrivacyClass.PUBLIC: 0,
    PrivacyClass.INTERNAL: 1,
    PrivacyClass.PRIVATE_ASSET: 2,
    PrivacyClass.SENSITIVE_PERFORMER: 3,
    PrivacyClass.SECRET: 4,
}


class MaturePolicyState(str, Enum):
    ALLOWED = "ALLOWED"
    ALLOWED_WITH_RESTRICTIONS = "ALLOWED_WITH_RESTRICTIONS"
    INELIGIBLE = "INELIGIBLE"
    UNKNOWN = "UNKNOWN"


class OpenRouterPlanState(str, Enum):
    READY_SOURCE_ONLY = "READY_SOURCE_ONLY"
    HOLD_RIGHTS_OR_CONSENT = "HOLD_RIGHTS_OR_CONSENT"
    HOLD_PRIVACY_SOVEREIGN_ONLY = "HOLD_PRIVACY_SOVEREIGN_ONLY"
    HOLD_NON_GENERATIVE_ONLY = "HOLD_NON_GENERATIVE_ONLY"
    HOLD_POLICY_RECHECK = "HOLD_POLICY_RECHECK"
    HOLD_PROVIDER_INELIGIBLE = "HOLD_PROVIDER_INELIGIBLE"


class OpenRouterReceiptState(str, Enum):
    TRANSPORT_FAILED = "TRANSPORT_FAILED"
    GENERATION_ID_MISSING = "GENERATION_ID_MISSING"
    ROUTER_METADATA_MISSING = "ROUTER_METADATA_MISSING"
    ROUTER_METADATA_INVALID = "ROUTER_METADATA_INVALID"
    PROVIDER_READBACK_MISSING = "PROVIDER_READBACK_MISSING"
    PROVIDER_NOT_ALLOWED = "PROVIDER_NOT_ALLOWED"
    MODEL_READBACK_MISSING = "MODEL_READBACK_MISSING"
    MODEL_NOT_ALLOWED = "MODEL_NOT_ALLOWED"
    USAGE_READBACK_MISSING = "USAGE_READBACK_MISSING"
    USAGE_READBACK_INVALID = "USAGE_READBACK_INVALID"
    COST_READBACK_MISSING = "COST_READBACK_MISSING"
    COST_READBACK_INVALID = "COST_READBACK_INVALID"
    COST_CAP_EXCEEDED = "COST_CAP_EXCEEDED"
    OUTPUT_MISSING = "OUTPUT_MISSING"
    SEMANTIC_MISMATCH = "SEMANTIC_MISMATCH"
    SEMANTIC_VERIFIED = "SEMANTIC_VERIFIED"


def _parse_timestamp(value: str) -> datetime:
    candidate = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        raise ValueError("policy timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(encoded.encode("utf-8")).hexdigest()


def _contains_forbidden_key(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key).strip().lower() in _FORBIDDEN_PAYLOAD_KEYS:
                return True
            if _contains_forbidden_key(nested):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def _normalise_messages(messages: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    if not messages:
        raise ValueError("at least one message is required")
    normalised: list[dict[str, object]] = []
    for message in messages:
        role = str(message.get("role", "")).strip().lower()
        if role not in _ALLOWED_MESSAGE_ROLES:
            raise ValueError(f"unsupported message role: {role or '<empty>'}")
        if "content" not in message:
            raise ValueError("every message requires content")
        if _contains_forbidden_key(message):
            raise ValueError("credential-like keys are forbidden in OpenRouter payloads")
        try:
            copied = json.loads(json.dumps(dict(message), ensure_ascii=False))
        except (TypeError, ValueError) as exc:
            raise ValueError("messages must be JSON serializable") from exc
        copied["role"] = role
        normalised.append(copied)
    return normalised


@dataclass(frozen=True, slots=True)
class OpenRouterPriceCeiling:
    prompt_usd_per_million: float
    completion_usd_per_million: float

    def __post_init__(self) -> None:
        values = (float(self.prompt_usd_per_million), float(self.completion_usd_per_million))
        if any(not isfinite(value) or value <= 0 for value in values):
            raise ValueError("price ceilings must be positive")

    def as_provider_parameter(self) -> dict[str, float]:
        return {
            "prompt": float(self.prompt_usd_per_million),
            "completion": float(self.completion_usd_per_million),
        }


@dataclass(frozen=True, slots=True)
class OpenRouterPolicySnapshot:
    snapshot_id: str
    model_id: str
    provider_allowlist: tuple[str, ...]
    provider_readback_allowlist: tuple[str, ...]
    checked_at: str
    expires_at: str
    source_urls: tuple[str, ...]
    mature_policy_state: MaturePolicyState = MaturePolicyState.UNKNOWN
    restrictions: tuple[str, ...] = ()
    zdr_supported: bool = False
    data_collection_deny_supported: bool = False
    structured_outputs_supported: bool = False

    def __post_init__(self) -> None:
        if not self.snapshot_id.strip() or not self.model_id.strip():
            raise ValueError("snapshot_id and model_id are required")
        if not self.provider_allowlist:
            raise ValueError("an explicit downstream provider allowlist is required")
        if len(self.provider_allowlist) != len(set(self.provider_allowlist)):
            raise ValueError("provider_allowlist must not contain duplicates")
        if any(not _PROVIDER_SLUG.fullmatch(item) for item in self.provider_allowlist):
            raise ValueError("provider_allowlist contains an invalid provider slug")
        if not self.provider_readback_allowlist:
            raise ValueError("an explicit provider readback allowlist is required")
        if len(self.provider_readback_allowlist) != len(set(self.provider_readback_allowlist)):
            raise ValueError("provider_readback_allowlist must not contain duplicates")
        if any(not item.strip() or item != item.strip() for item in self.provider_readback_allowlist):
            raise ValueError("provider_readback_allowlist contains an invalid display label")
        checked = _parse_timestamp(self.checked_at)
        expires = _parse_timestamp(self.expires_at)
        if expires <= checked:
            raise ValueError("expires_at must be later than checked_at")
        if not self.source_urls or any(not item.startswith("https://") for item in self.source_urls):
            raise ValueError("current HTTPS policy sources are required")
        if self.mature_policy_state is MaturePolicyState.ALLOWED_WITH_RESTRICTIONS and not self.restrictions:
            raise ValueError("restricted mature policy state requires explicit restrictions")

    def is_current(self, at: datetime) -> bool:
        point = at if at.tzinfo is not None else at.replace(tzinfo=timezone.utc)
        point = point.astimezone(timezone.utc)
        return _parse_timestamp(self.checked_at) <= point < _parse_timestamp(self.expires_at)


@dataclass(frozen=True, slots=True)
class OpenRouterRequestPlan:
    state: OpenRouterPlanState
    eligibility: Eligibility
    reason_codes: tuple[str, ...]
    endpoint: str | None
    credential_reference: str | None
    required_headers: Mapping[str, str]
    request_body: Mapping[str, object]
    request_fingerprint: str
    raw_prompt_persisted: bool = False
    external_effect: bool = False
    live_execution_authorized: bool = False

    @property
    def ready(self) -> bool:
        return self.state is OpenRouterPlanState.READY_SOURCE_ONLY


@dataclass(frozen=True, slots=True)
class OpenRouterSemanticReceipt:
    state: OpenRouterReceiptState
    request_fingerprint: str
    transport_status: int
    generation_id: str | None
    provider: str | None
    resolved_model: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_usd: float | None
    semantic_verified: bool
    output_sha256: str | None
    failure_code: str | None
    raw_output_persisted: bool = False

    @property
    def admission_ready(self) -> bool:
        return self.state is OpenRouterReceiptState.SEMANTIC_VERIFIED


def _held_plan(
    *,
    state: OpenRouterPlanState,
    eligibility: Eligibility,
    reasons: Sequence[str],
    mission_id: str,
    snapshot_id: str,
) -> OpenRouterRequestPlan:
    fingerprint = _canonical_hash(
        {
            "mission_id": mission_id,
            "snapshot_id": snapshot_id,
            "state": state.value,
            "eligibility": eligibility.value,
            "reason_codes": tuple(reasons),
        }
    )
    return OpenRouterRequestPlan(
        state=state,
        eligibility=eligibility,
        reason_codes=tuple(reasons),
        endpoint=None,
        credential_reference=None,
        required_headers={},
        request_body={},
        request_fingerprint=fingerprint,
    )


def build_openrouter_request_plan(
    *,
    mission_id: str,
    content_class: ContentClass,
    privacy_class: PrivacyClass,
    route: RoutePolicy,
    policy_snapshot: OpenRouterPolicySnapshot,
    messages: Sequence[Mapping[str, object]],
    evaluated_at: datetime,
    mature_context: MatureContext | None = None,
    max_tokens: int = 1200,
    temperature: float = 0.2,
    response_schema: Mapping[str, object] | None = None,
    response_schema_name: str = "sovara_creative_response",
    price_ceiling: OpenRouterPriceCeiling | None = None,
) -> OpenRouterRequestPlan:
    """Prepare a fail-closed OpenRouter request without invoking the provider.

    The adapter deliberately stops at a source-only plan. Credential resolution,
    spend authority, network execution, and provider admission remain separate
    action-specific gates.
    """

    mid = mission_id.strip()
    if not mid:
        raise ValueError("mission_id is required")
    if route.route_type is not RouteType.OPENROUTER_FCX:
        raise ValueError("route must be OPENROUTER_FCX")
    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")
    if not 0.0 <= float(temperature) <= 2.0:
        raise ValueError("temperature must be in [0, 2]")

    if content_class is ContentClass.MATURE_ADULT_ORIENTED:
        if mature_context is None or not mature_context.hard_gate_passes:
            return _held_plan(
                state=OpenRouterPlanState.HOLD_RIGHTS_OR_CONSENT,
                eligibility=Eligibility.INELIGIBLE,
                reasons=("VERIFIED_ADULT_AND_CONSENT_GATE_REQUIRED",),
                mission_id=mid,
                snapshot_id=policy_snapshot.snapshot_id,
            )

    if privacy_class is PrivacyClass.SECRET:
        return _held_plan(
            state=OpenRouterPlanState.HOLD_NON_GENERATIVE_ONLY,
            eligibility=Eligibility.NON_GENERATIVE_ONLY,
            reasons=("SECRET_DATA_NEVER_EXTERNAL_GENERATIVE",),
            mission_id=mid,
            snapshot_id=policy_snapshot.snapshot_id,
        )

    # Initial OpenRouter admission is intentionally capped at INTERNAL. Private
    # assets and performer-sensitive material stay on the sovereign route even
    # if a caller supplies a wider RoutePolicy.
    if _PRIVACY_RANK[privacy_class] > _PRIVACY_RANK[PrivacyClass.INTERNAL]:
        return _held_plan(
            state=OpenRouterPlanState.HOLD_PRIVACY_SOVEREIGN_ONLY,
            eligibility=Eligibility.SOVEREIGN_ONLY,
            reasons=("OPENROUTER_INITIAL_PRIVACY_CEILING_INTERNAL",),
            mission_id=mid,
            snapshot_id=policy_snapshot.snapshot_id,
        )

    route_eligibility = evaluate_route(
        content_class=content_class,
        privacy_class=privacy_class,
        route=route,
        mature_context=mature_context,
    )
    if route_eligibility is Eligibility.POLICY_RECHECK_REQUIRED:
        return _held_plan(
            state=OpenRouterPlanState.HOLD_POLICY_RECHECK,
            eligibility=route_eligibility,
            reasons=("ROUTE_POLICY_NOT_CURRENT",),
            mission_id=mid,
            snapshot_id=policy_snapshot.snapshot_id,
        )
    if route_eligibility is not Eligibility.ELIGIBLE or not route.generation_capable:
        return _held_plan(
            state=OpenRouterPlanState.HOLD_PROVIDER_INELIGIBLE,
            eligibility=Eligibility.INELIGIBLE,
            reasons=("ROUTE_CONTRACT_INELIGIBLE",),
            mission_id=mid,
            snapshot_id=policy_snapshot.snapshot_id,
        )

    if not route.available or not route.policy_verified:
        return _held_plan(
            state=OpenRouterPlanState.HOLD_POLICY_RECHECK,
            eligibility=Eligibility.POLICY_RECHECK_REQUIRED,
            reasons=("ROUTE_POLICY_NOT_CURRENT",),
            mission_id=mid,
            snapshot_id=policy_snapshot.snapshot_id,
        )

    if not policy_snapshot.is_current(evaluated_at):
        return _held_plan(
            state=OpenRouterPlanState.HOLD_POLICY_RECHECK,
            eligibility=Eligibility.POLICY_RECHECK_REQUIRED,
            reasons=("POLICY_SNAPSHOT_STALE",),
            mission_id=mid,
            snapshot_id=policy_snapshot.snapshot_id,
        )

    missing_privacy_features = tuple(
        name
        for name, present in (
            ("ZDR_CAPABILITY_UNVERIFIED", policy_snapshot.zdr_supported),
            ("DATA_COLLECTION_DENY_UNVERIFIED", policy_snapshot.data_collection_deny_supported),
        )
        if not present
    )
    if missing_privacy_features:
        return _held_plan(
            state=OpenRouterPlanState.HOLD_POLICY_RECHECK,
            eligibility=Eligibility.POLICY_RECHECK_REQUIRED,
            reasons=missing_privacy_features,
            mission_id=mid,
            snapshot_id=policy_snapshot.snapshot_id,
        )

    if content_class is ContentClass.MATURE_ADULT_ORIENTED:
        if policy_snapshot.mature_policy_state is MaturePolicyState.UNKNOWN:
            return _held_plan(
                state=OpenRouterPlanState.HOLD_POLICY_RECHECK,
                eligibility=Eligibility.POLICY_RECHECK_REQUIRED,
                reasons=("MODEL_PROVIDER_MATURE_POLICY_UNKNOWN",),
                mission_id=mid,
                snapshot_id=policy_snapshot.snapshot_id,
            )
        if policy_snapshot.mature_policy_state is MaturePolicyState.INELIGIBLE or not route.mature_class_allowed:
            return _held_plan(
                state=OpenRouterPlanState.HOLD_PROVIDER_INELIGIBLE,
                eligibility=Eligibility.INELIGIBLE,
                reasons=("MODEL_PROVIDER_MATURE_CLASS_INELIGIBLE",),
                mission_id=mid,
                snapshot_id=policy_snapshot.snapshot_id,
            )

    if response_schema is not None and not policy_snapshot.structured_outputs_supported:
        return _held_plan(
            state=OpenRouterPlanState.HOLD_POLICY_RECHECK,
            eligibility=Eligibility.POLICY_RECHECK_REQUIRED,
            reasons=("STRUCTURED_OUTPUT_SUPPORT_UNVERIFIED",),
            mission_id=mid,
            snapshot_id=policy_snapshot.snapshot_id,
        )

    normalised_messages = _normalise_messages(messages)
    providers = list(policy_snapshot.provider_allowlist)
    provider_preferences: dict[str, object] = {
        "only": providers,
        "order": providers,
        "allow_fallbacks": False,
        "require_parameters": True,
        "data_collection": "deny",
        "zdr": True,
    }
    if price_ceiling is not None:
        provider_preferences["max_price"] = price_ceiling.as_provider_parameter()

    body: dict[str, object] = {
        "model": policy_snapshot.model_id,
        "messages": normalised_messages,
        "max_tokens": int(max_tokens),
        "temperature": float(temperature),
        "provider": provider_preferences,
    }
    if response_schema is not None:
        if not response_schema_name.strip():
            raise ValueError("response_schema_name is required when response_schema is supplied")
        if _contains_forbidden_key(response_schema):
            raise ValueError("credential-like keys are forbidden in response schemas")
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": response_schema_name.strip(),
                "strict": True,
                "schema": json.loads(json.dumps(dict(response_schema), ensure_ascii=False)),
            },
        }

    eligibility = (
        Eligibility.ELIGIBLE_WITH_RESTRICTIONS
        if content_class is ContentClass.MATURE_ADULT_ORIENTED
        and policy_snapshot.mature_policy_state is MaturePolicyState.ALLOWED_WITH_RESTRICTIONS
        else Eligibility.ELIGIBLE
    )
    reasons = ["CURRENT_POLICY_AND_PRIVACY_GATES_PASS", "NO_SILENT_PROVIDER_FALLBACK"]
    reasons.extend(policy_snapshot.restrictions)
    return OpenRouterRequestPlan(
        state=OpenRouterPlanState.READY_SOURCE_ONLY,
        eligibility=eligibility,
        reason_codes=tuple(reasons),
        endpoint=OPENROUTER_CHAT_COMPLETIONS_ENDPOINT,
        credential_reference=OPENROUTER_CREDENTIAL_REFERENCE,
        required_headers={
            "Content-Type": "application/json",
            "X-OpenRouter-Metadata": "enabled",
        },
        request_body=body,
        request_fingerprint=_canonical_hash(
            {
                "mission_id": mid,
                "policy_snapshot": policy_snapshot.snapshot_id,
                "request_body": body,
            }
        ),
    )


def _message_text(response: Mapping[str, object]) -> str | None:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
        return None
    message = choices[0].get("message")
    if not isinstance(message, Mapping):
        return None
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        fragments: list[str] = []
        for part in content:
            if isinstance(part, Mapping) and isinstance(part.get("text"), str):
                fragments.append(str(part["text"]))
        return "".join(fragments) or None
    return None


def evaluate_openrouter_response(
    *,
    request_fingerprint: str,
    transport_status: int,
    response: Mapping[str, object],
    allowed_models: Sequence[str],
    allowed_provider_readbacks: Sequence[str],
    expected_semantic_marker: str,
    maximum_cost_usd: float | None = None,
) -> OpenRouterSemanticReceipt:
    """Evaluate provider evidence without retaining raw generated content."""

    if not allowed_models:
        raise ValueError("allowed_models must not be empty")
    if not allowed_provider_readbacks:
        raise ValueError("allowed_provider_readbacks must not be empty")
    if maximum_cost_usd is not None:
        cost_cap = float(maximum_cost_usd)
        if not isfinite(cost_cap) or cost_cap < 0:
            raise ValueError("maximum_cost_usd must be finite and non-negative")

    def receipt(
        state: OpenRouterReceiptState,
        *,
        generation_id: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        cost: float | None = None,
        output_hash: str | None = None,
    ) -> OpenRouterSemanticReceipt:
        verified = state is OpenRouterReceiptState.SEMANTIC_VERIFIED
        return OpenRouterSemanticReceipt(
            state=state,
            request_fingerprint=request_fingerprint,
            transport_status=int(transport_status),
            generation_id=generation_id,
            provider=provider,
            resolved_model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
            semantic_verified=verified,
            output_sha256=output_hash,
            failure_code=None if verified else state.value,
        )

    if not 200 <= int(transport_status) < 300:
        return receipt(OpenRouterReceiptState.TRANSPORT_FAILED)

    generation_id = response.get("id") if isinstance(response.get("id"), str) else None
    model = response.get("model") if isinstance(response.get("model"), str) else None
    if not generation_id:
        return receipt(OpenRouterReceiptState.GENERATION_ID_MISSING, model=model)

    router_metadata = response.get("openrouter_metadata")
    if not isinstance(router_metadata, Mapping):
        return receipt(
            OpenRouterReceiptState.ROUTER_METADATA_MISSING,
            generation_id=generation_id,
            model=model,
        )
    strategy = router_metadata.get("strategy")
    attempt = router_metadata.get("attempt")
    endpoints = router_metadata.get("endpoints")
    available = endpoints.get("available") if isinstance(endpoints, Mapping) else None
    if strategy != "direct" or isinstance(attempt, bool) or attempt != 1 or not isinstance(available, list):
        return receipt(
            OpenRouterReceiptState.ROUTER_METADATA_INVALID,
            generation_id=generation_id,
            model=model,
        )
    selected = [
        item
        for item in available
        if isinstance(item, Mapping) and item.get("selected") is True
    ]
    if len(selected) != 1:
        return receipt(
            OpenRouterReceiptState.PROVIDER_READBACK_MISSING,
            generation_id=generation_id,
            model=model,
        )
    provider = selected[0].get("provider")
    selected_model = selected[0].get("model")
    if not isinstance(provider, str) or not provider:
        return receipt(
            OpenRouterReceiptState.PROVIDER_READBACK_MISSING,
            generation_id=generation_id,
            model=model,
        )
    if provider not in set(allowed_provider_readbacks):
        return receipt(
            OpenRouterReceiptState.PROVIDER_NOT_ALLOWED,
            generation_id=generation_id,
            provider=provider,
            model=model,
        )
    if not model or not isinstance(selected_model, str):
        return receipt(
            OpenRouterReceiptState.MODEL_READBACK_MISSING,
            generation_id=generation_id,
            provider=provider,
        )
    if model not in set(allowed_models) or selected_model not in set(allowed_models):
        return receipt(
            OpenRouterReceiptState.MODEL_NOT_ALLOWED,
            generation_id=generation_id,
            provider=provider,
            model=model,
        )

    usage = response.get("usage")
    if not isinstance(usage, Mapping):
        return receipt(
            OpenRouterReceiptState.USAGE_READBACK_MISSING,
            generation_id=generation_id,
            provider=provider,
            model=model,
        )
    raw_prompt_tokens = usage.get("prompt_tokens")
    raw_completion_tokens = usage.get("completion_tokens")
    prompt_tokens = raw_prompt_tokens if isinstance(raw_prompt_tokens, int) and not isinstance(raw_prompt_tokens, bool) else None
    completion_tokens = raw_completion_tokens if isinstance(raw_completion_tokens, int) and not isinstance(raw_completion_tokens, bool) else None
    if prompt_tokens is None or completion_tokens is None:
        return receipt(
            OpenRouterReceiptState.USAGE_READBACK_MISSING,
            generation_id=generation_id,
            provider=provider,
            model=model,
        )
    if prompt_tokens < 0 or completion_tokens < 0:
        return receipt(
            OpenRouterReceiptState.USAGE_READBACK_INVALID,
            generation_id=generation_id,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
    raw_cost = usage.get("cost")
    if isinstance(raw_cost, bool) or not isinstance(raw_cost, (int, float)):
        return receipt(
            OpenRouterReceiptState.COST_READBACK_MISSING,
            generation_id=generation_id,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
    cost = float(raw_cost)
    if not isfinite(cost) or cost < 0:
        return receipt(
            OpenRouterReceiptState.COST_READBACK_INVALID,
            generation_id=generation_id,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
        )
    if maximum_cost_usd is not None and cost > float(maximum_cost_usd):
        return receipt(
            OpenRouterReceiptState.COST_CAP_EXCEEDED,
            generation_id=generation_id,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
        )

    output = _message_text(response)
    if output is None:
        return receipt(
            OpenRouterReceiptState.OUTPUT_MISSING,
            generation_id=generation_id,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
        )
    output_hash = sha256(output.encode("utf-8")).hexdigest()
    if not expected_semantic_marker or expected_semantic_marker not in output:
        return receipt(
            OpenRouterReceiptState.SEMANTIC_MISMATCH,
            generation_id=generation_id,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
            output_hash=output_hash,
        )
    return receipt(
        OpenRouterReceiptState.SEMANTIC_VERIFIED,
        generation_id=generation_id,
        provider=provider,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost=cost,
        output_hash=output_hash,
    )
