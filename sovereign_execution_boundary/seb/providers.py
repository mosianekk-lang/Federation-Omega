from __future__ import annotations

from abc import ABC, abstractmethod
import json
import os
from time import monotonic
from typing import Callable
from urllib import error, request

from .models import FailureClass, ProviderRequest, ProviderResponse


class ProviderFailure(RuntimeError):
    def __init__(self, failure_class: FailureClass, message: str):
        super().__init__(message)
        self.failure_class = failure_class


class Provider(ABC):
    name: str

    @abstractmethod
    def complete(self, req: ProviderRequest) -> ProviderResponse: ...


class MockProvider(Provider):
    def __init__(self, name: str, behavior: Callable[[ProviderRequest, int], dict] | None = None):
        self.name = name
        self.calls = 0
        self.behavior = behavior or (lambda req, calls: {"result": req.prompt, "accepted": True})

    def complete(self, req: ProviderRequest) -> ProviderResponse:
        self.calls += 1
        started = monotonic()
        value = self.behavior(req, self.calls)
        if isinstance(value, ProviderFailure):
            raise value
        if not isinstance(value, dict):
            raise ProviderFailure(FailureClass.MALFORMED_OUTPUT, "provider output is not an object")
        return ProviderResponse(self.name, req.model, value, min(req.max_tokens, 64),
                                int((monotonic() - started) * 1000))


class OpenRouterProvider(Provider):
    name = "openrouter"
    endpoint = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, api_key_env: str = "OPENROUTER_API_KEY", timeout: float = 30.0):
        self.api_key_env = api_key_env
        self.timeout = timeout

    def complete(self, req: ProviderRequest) -> ProviderResponse:
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise ProviderFailure(FailureClass.MISSING_AUTHORITY, "OpenRouter credential unavailable")
        payload = {
            "model": req.model,
            "messages": [{"role": "user", "content": req.prompt}],
            "max_tokens": req.max_tokens,
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "seb_response", "strict": True, "schema": req.schema}},
        }
        http_req = request.Request(self.endpoint, data=json.dumps(payload).encode(), method="POST",
                                   headers={"Authorization": f"Bearer {api_key}",
                                            "Content-Type": "application/json",
                                            "X-Request-ID": req.request_id})
        started = monotonic()
        try:
            with request.urlopen(http_req, timeout=self.timeout) as response:
                raw = json.loads(response.read())
        except error.HTTPError as exc:
            if exc.code in {408, 429, 500, 502, 503, 504}:
                raise ProviderFailure(FailureClass.TRANSIENT, f"OpenRouter HTTP {exc.code}") from exc
            raise ProviderFailure(FailureClass.POLICY_REFUSAL, f"OpenRouter HTTP {exc.code}") from exc
        except (error.URLError, TimeoutError) as exc:
            raise ProviderFailure(FailureClass.PROVIDER_OUTAGE, "OpenRouter unavailable") from exc
        try:
            choice = raw["choices"][0]["message"]
            if choice.get("refusal"):
                raise ProviderFailure(FailureClass.POLICY_REFUSAL, str(choice["refusal"]))
            content = choice["content"]
            parsed = json.loads(content) if isinstance(content, str) else content
            usage = raw.get("usage", {})
            tokens = int(usage.get("total_tokens", 0))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ProviderFailure(FailureClass.MALFORMED_OUTPUT, "invalid OpenRouter response") from exc
        return ProviderResponse(self.name, req.model, parsed, tokens,
                                int((monotonic() - started) * 1000))

