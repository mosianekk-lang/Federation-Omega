from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from typing import Any, Mapping, Protocol

from .blind_runner import (
    AgentContext,
    BlindRunReceipt,
    IsolatedBlindRunner,
    ModelBinding,
)


class OpenAIProviderAdapterError(RuntimeError):
    """Fail-closed provider adapter error."""


ALLOWED_PROVIDER_OPTIONS = frozenset(
    {
        "max_output_tokens",
        "reasoning",
        "temperature",
        "text",
        "top_p",
        "truncation",
    }
)

FORBIDDEN_PROVIDER_OPTIONS = frozenset(
    {
        "conversation",
        "include",
        "input",
        "instructions",
        "metadata",
        "model",
        "parallel_tool_calls",
        "previous_response_id",
        "prompt",
        "safety_identifier",
        "service_tier",
        "store",
        "tool_choice",
        "tools",
    }
)

PUBLIC_PROVIDER_STORAGE_CLASSES = frozenset(
    {
        "PUBLIC_SYNTHETIC",
        "PUBLIC_SOURCE_DERIVED_SYNTHETIC",
    }
)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _storage_classification(blind_payload: Mapping[str, Any]) -> str:
    return str(blind_payload.get("provider_storage_classification", "")).strip().upper()


def _validate_provider_storage(blind_payload: Mapping[str, Any], *, store: bool) -> None:
    if not store:
        return
    classification = _storage_classification(blind_payload)
    if classification not in PUBLIC_PROVIDER_STORAGE_CLASSES:
        raise OpenAIProviderAdapterError(
            "provider storage is restricted to explicitly public/synthetic benchmark data"
        )
    if bool(blind_payload.get("external_effect", False)):
        raise OpenAIProviderAdapterError(
            "provider-stored CASEFORGE benchmark must remain A1_INTERNAL/no-external-effect"
        )


@dataclass(frozen=True)
class ProviderResponseEvidence:
    provider: str
    response_id: str
    requested_model: str
    response_model: str
    status: str
    created_at: int | float | None
    request_id: str
    output_text_sha256: str
    store: bool

    def validate(self) -> "ProviderResponseEvidence":
        if self.provider != "openai":
            raise OpenAIProviderAdapterError("unsupported provider evidence")
        if not self.response_id.strip():
            raise OpenAIProviderAdapterError("provider response id is required")
        if not self.requested_model.strip() or not self.response_model.strip():
            raise OpenAIProviderAdapterError("requested and provider-returned model ids are required")
        if not self.status.strip():
            raise OpenAIProviderAdapterError("provider response status is required")
        if len(self.output_text_sha256) != 64:
            raise OpenAIProviderAdapterError("provider output digest is invalid")
        return self


@dataclass(frozen=True)
class ProviderReadbackEvidence:
    provider: str
    provider_readback_ref: str
    response_id: str
    response_model: str
    status: str
    model_version: str
    model_version_verified: bool

    def validate_against(self, execution: ProviderResponseEvidence) -> "ProviderReadbackEvidence":
        if self.provider != execution.provider:
            raise OpenAIProviderAdapterError("provider readback identity mismatch")
        if not self.provider_readback_ref.strip():
            raise OpenAIProviderAdapterError("provider readback reference is required")
        if self.response_id != execution.response_id:
            raise OpenAIProviderAdapterError("provider readback response id mismatch")
        if self.response_model != execution.response_model:
            raise OpenAIProviderAdapterError("provider readback model mismatch")
        if self.status != execution.status:
            raise OpenAIProviderAdapterError("provider readback status mismatch")
        if not self.model_version_verified or not self.model_version.strip():
            raise OpenAIProviderAdapterError("provider model version is not independently verified")
        return self


class ProviderReadbackVerifier(Protocol):
    def verify(self, execution: ProviderResponseEvidence) -> ProviderReadbackEvidence: ...


class OpenAIStoredResponseReadbackVerifier:
    """Provider-native readback for public/synthetic stored Responses canaries.

    The verifier retrieves the provider-stored Response by ID and independently
    retrieves the provider model resource. It records only non-secret identity,
    state and model-resource metadata. It never reads or emits credential values,
    and it does not treat a model alias alone as a verified version.
    """

    def __init__(self, *, client: Any) -> None:
        self.client = client

    @staticmethod
    def _value(obj: Any, name: str) -> Any:
        if isinstance(obj, Mapping):
            return obj.get(name)
        return getattr(obj, name, None)

    def verify(self, execution: ProviderResponseEvidence) -> ProviderReadbackEvidence:
        execution.validate()
        if not execution.store:
            raise OpenAIProviderAdapterError(
                "stored-response provider readback requires a provider-stored execution"
            )
        try:
            response = self.client.responses.retrieve(execution.response_id)
            response_id = str(self._value(response, "id") or "").strip()
            response_model = str(self._value(response, "model") or "").strip()
            status = str(self._value(response, "status") or "").strip()
            model_resource = self.client.models.retrieve(response_model)
        except Exception as exc:
            raise OpenAIProviderAdapterError(
                f"OpenAI provider readback failed: {type(exc).__name__}"
            ) from exc

        model_id = str(self._value(model_resource, "id") or "").strip()
        model_created = self._value(model_resource, "created")
        model_owner = str(self._value(model_resource, "owned_by") or "").strip()

        if not response_id or not response_model or not status:
            raise OpenAIProviderAdapterError("provider response readback is incomplete")
        if model_id != response_model:
            raise OpenAIProviderAdapterError("provider model-resource id mismatch")
        if not isinstance(model_created, (int, float)) or model_created <= 0:
            raise OpenAIProviderAdapterError("provider model-resource creation metadata missing")
        if not model_owner:
            raise OpenAIProviderAdapterError("provider model-resource owner metadata missing")

        created = int(model_created)
        model_version = (
            f"openai-model-resource:{model_id}:created={created}:owned_by={model_owner}"
        )
        readback_ref = (
            f"openai:response:{response_id}|model:{model_id}|created:{created}"
        )
        return ProviderReadbackEvidence(
            provider="openai",
            provider_readback_ref=readback_ref,
            response_id=response_id,
            response_model=response_model,
            status=status,
            model_version=model_version,
            model_version_verified=True,
        ).validate_against(execution)


@dataclass(frozen=True)
class ProviderBoundBlindRunReceipt:
    blind_run: BlindRunReceipt
    provider_execution: ProviderResponseEvidence
    provider_state: str
    provider_readback_ref: str = ""
    verified_model_version: str = ""
    authority_ceiling: str = "A1_INTERNAL"
    external_effect: bool = False

    def validate(self) -> "ProviderBoundBlindRunReceipt":
        self.provider_execution.validate()
        if self.provider_state not in {
            "PROVIDER_EXECUTED_UNREADBACK",
            "PROVIDER_VERIFIED",
        }:
            raise OpenAIProviderAdapterError("unsupported provider state")
        if self.provider_state == "PROVIDER_VERIFIED":
            if not self.provider_readback_ref.strip():
                raise OpenAIProviderAdapterError("provider verification requires independent readback")
            if not self.verified_model_version.strip():
                raise OpenAIProviderAdapterError("provider verification requires verified model version")
        if self.external_effect:
            raise OpenAIProviderAdapterError("CASEFORGE provider experiments are A1_INTERNAL only")
        return self


class OpenAIResponsesTestedAgent:
    """Tested-agent adapter for an already-authorised OpenAI Responses client.

    The adapter receives only the blind payload and control-free AgentContext from
    IsolatedBlindRunner. Provider tools, conversations, prompt references and
    previous-response references are prohibited so the tested agent cannot gain a
    second route to hidden benchmark material.
    """

    def __init__(
        self,
        *,
        client: Any,
        model: str,
        request_options: Mapping[str, Any] | None = None,
        store: bool = False,
    ) -> None:
        if not model.strip():
            raise OpenAIProviderAdapterError("OpenAI model id is required")
        self.client = client
        self.model = model.strip()
        self.store = bool(store)
        self.request_options = dict(request_options or {})
        forbidden = sorted(FORBIDDEN_PROVIDER_OPTIONS & set(self.request_options))
        if forbidden:
            raise OpenAIProviderAdapterError(
                "provider options would weaken blind isolation: " + ",".join(forbidden)
            )
        unsupported = sorted(set(self.request_options) - ALLOWED_PROVIDER_OPTIONS)
        if unsupported:
            raise OpenAIProviderAdapterError(
                "provider options are not admitted by the blind canary contract: "
                + ",".join(unsupported)
            )
        self._last_evidence: ProviderResponseEvidence | None = None

    @property
    def last_evidence(self) -> ProviderResponseEvidence:
        if self._last_evidence is None:
            raise OpenAIProviderAdapterError("no provider execution evidence exists")
        return self._last_evidence

    @staticmethod
    def _instructions() -> str:
        return (
            "You are being evaluated on a blind legal/evidentiary reasoning benchmark. "
            "Use only the case packet supplied in this request. Do not use tools, external "
            "retrieval, prior conversations, hidden prompts, or unstated facts. Distinguish "
            "observations, hypotheses, counter-hypotheses, missing evidence, legal-route "
            "questions, adverse considerations and uncertainty. Return one JSON object only. "
            "Never invent an authority, quotation, fact, source, procedural event or outcome."
        )

    def analyze(self, blind_payload: Mapping[str, Any], context: AgentContext) -> Any:
        self._last_evidence = None
        if context.provider.strip().lower() != "openai":
            raise OpenAIProviderAdapterError("agent context provider must be openai")
        if context.model != self.model:
            raise OpenAIProviderAdapterError("agent context model does not match adapter model")
        _validate_provider_storage(blind_payload, store=self.store)

        prompt = _canonical_json(blind_payload)
        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=self._instructions(),
                input=[{"role": "user", "content": prompt}],
                store=self.store,
                **self.request_options,
            )
        except Exception as exc:  # provider SDK exceptions are intentionally wrapped
            raise OpenAIProviderAdapterError(
                f"OpenAI Responses execution failed: {type(exc).__name__}"
            ) from exc

        output_text = str(getattr(response, "output_text", "") or "").strip()
        if not output_text:
            raise OpenAIProviderAdapterError("OpenAI Responses returned empty output text")

        response_id = str(getattr(response, "id", "") or "").strip()
        response_model = str(getattr(response, "model", "") or "").strip()
        status = str(getattr(response, "status", "") or "").strip()
        request_id = str(getattr(response, "_request_id", "") or "").strip()
        created_at = getattr(response, "created_at", None)
        self._last_evidence = ProviderResponseEvidence(
            provider="openai",
            response_id=response_id,
            requested_model=self.model,
            response_model=response_model,
            status=status,
            created_at=created_at,
            request_id=request_id,
            output_text_sha256=_sha256_text(output_text),
            store=self.store,
        ).validate()

        try:
            parsed = json.loads(output_text)
        except json.JSONDecodeError:
            parsed = {
                "response_format": "NON_JSON_OUTPUT",
                "analysis_text": output_text,
            }
        return parsed


class OpenAIProviderBlindExperiment:
    """Run an OpenAI-backed blind experiment without self-certifying provider proof."""

    def __init__(self, *, runner: IsolatedBlindRunner | None = None) -> None:
        self.runner = runner or IsolatedBlindRunner()

    def run(
        self,
        *,
        run_id: str,
        blind_payload: Mapping[str, Any],
        client: Any,
        model: str,
        request_options: Mapping[str, Any] | None = None,
        store: bool = False,
        readback_verifier: ProviderReadbackVerifier | None = None,
    ) -> ProviderBoundBlindRunReceipt:
        options = dict(request_options or {})
        agent = OpenAIResponsesTestedAgent(
            client=client,
            model=model,
            request_options=options,
            store=store,
        )
        binding = ModelBinding(
            provider="openai",
            model=model,
            version="REQUESTED_MODEL_ID_UNVERIFIED_VERSION",
            configuration={
                "store": bool(store),
                "request_options": options,
                "blind_tools_allowed": False,
                "provider_storage_classification": _storage_classification(blind_payload),
            },
            execution_state="DETERMINISTIC_TEST_ONLY",
        )
        blind_run = self.runner.run(
            run_id=run_id,
            blind_payload=blind_payload,
            agent=agent,
            model_binding=binding,
        )
        execution = agent.last_evidence

        if readback_verifier is None:
            return ProviderBoundBlindRunReceipt(
                blind_run=blind_run,
                provider_execution=execution,
                provider_state="PROVIDER_EXECUTED_UNREADBACK",
            ).validate()

        readback = readback_verifier.verify(execution).validate_against(execution)
        verified_blind_run = replace(
            blind_run,
            model=execution.requested_model,
            version=readback.model_version,
            execution_state="PROVIDER_VERIFIED",
            provider_readback_ref=readback.provider_readback_ref,
        )
        return ProviderBoundBlindRunReceipt(
            blind_run=verified_blind_run,
            provider_execution=execution,
            provider_state="PROVIDER_VERIFIED",
            provider_readback_ref=readback.provider_readback_ref,
            verified_model_version=readback.model_version,
        ).validate()


__all__ = [
    "ALLOWED_PROVIDER_OPTIONS",
    "FORBIDDEN_PROVIDER_OPTIONS",
    "PUBLIC_PROVIDER_STORAGE_CLASSES",
    "OpenAIProviderAdapterError",
    "OpenAIProviderBlindExperiment",
    "OpenAIResponsesTestedAgent",
    "OpenAIStoredResponseReadbackVerifier",
    "ProviderBoundBlindRunReceipt",
    "ProviderReadbackEvidence",
    "ProviderReadbackVerifier",
    "ProviderResponseEvidence",
]
