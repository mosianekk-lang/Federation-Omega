from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Callable, Mapping, Protocol, Sequence
import urllib.request
import urllib.error


class LLMGatewayError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMRequest:
    request_id: str
    model: str
    messages: tuple[Mapping[str, str], ...]
    temperature: float = 0.2
    max_output_tokens: int = 1200
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    provider_id: str
    model: str
    text: str
    usage: Mapping[str, object] = field(default_factory=dict)
    raw_metadata: Mapping[str, object] = field(default_factory=dict)


class LLMProvider(Protocol):
    provider_id: str

    def healthy(self) -> bool: ...
    def infer(self, request: LLMRequest) -> LLMResponse: ...


class InProcessLLMProvider:
    """Host-injected provider. The provider callable never receives credentials."""

    def __init__(self, provider_id: str, handler: Callable[[LLMRequest], str | LLMResponse]):
        self.provider_id = provider_id
        self._handler = handler

    def healthy(self) -> bool:
        return True

    def infer(self, request: LLMRequest) -> LLMResponse:
        value = self._handler(request)
        if isinstance(value, LLMResponse):
            return value
        return LLMResponse(provider_id=self.provider_id, model=request.model, text=str(value))


class OpenAICompatibleHTTPProvider:
    """OpenAI-compatible chat endpoint. Token material is supplied only by a host callback."""

    def __init__(
        self,
        *,
        provider_id: str,
        base_url: str,
        default_model: str,
        token_loader: Callable[[], str | None] | None = None,
        timeout_seconds: float = 60.0,
    ):
        if not base_url.startswith(("http://", "https://")):
            raise LLMGatewayError("LLM_ENDPOINT_INVALID")
        self.provider_id = provider_id
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.token_loader = token_loader
        self.timeout_seconds = timeout_seconds

    def healthy(self) -> bool:
        return True

    def infer(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self.default_model
        body = {
            "model": model,
            "messages": [dict(m) for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
        }
        headers = {"Content-Type": "application/json", "User-Agent": "FUSE-Sovereign-FCOA/0.4"}
        if self.token_loader:
            token = self.token_loader()
            if token:
                headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(
            self.base_url + "/v1/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LLMGatewayError(f"LLM_PROVIDER_CALL_FAILED:{type(exc).__name__}") from exc
        choices = payload.get("choices") or []
        if not choices:
            raise LLMGatewayError("LLM_PROVIDER_EMPTY_RESPONSE")
        message = choices[0].get("message") or {}
        text = message.get("content")
        if not isinstance(text, str):
            raise LLMGatewayError("LLM_PROVIDER_TEXT_MISSING")
        return LLMResponse(
            provider_id=self.provider_id,
            model=model,
            text=text,
            usage=payload.get("usage") or {},
            raw_metadata={"id": payload.get("id"), "created": payload.get("created")},
        )


class LLMGateway:
    """Task-scoped model router. Reachability never grants action authority."""

    def __init__(self, providers: Sequence[LLMProvider] = ()):
        self._providers: dict[str, LLMProvider] = {p.provider_id: p for p in providers}

    def register(self, provider: LLMProvider) -> None:
        self._providers[provider.provider_id] = provider

    def providers(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))

    def infer(self, request: LLMRequest, *, preferred_provider: str | None = None) -> LLMResponse:
        if preferred_provider:
            provider = self._providers.get(preferred_provider)
            if provider is None or not provider.healthy():
                raise LLMGatewayError("PREFERRED_LLM_PROVIDER_UNAVAILABLE")
            return provider.infer(request)
        candidates = [p for _, p in sorted(self._providers.items()) if p.healthy()]
        if not candidates:
            raise LLMGatewayError("NO_QUALIFIED_LLM_PROVIDER")
        errors: list[str] = []
        for provider in candidates:
            try:
                return provider.infer(request)
            except LLMGatewayError as exc:
                errors.append(f"{provider.provider_id}:{exc}")
        raise LLMGatewayError("ALL_LLM_PROVIDERS_FAILED:" + "|".join(errors))
