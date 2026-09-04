from __future__ import annotations

from dataclasses import dataclass
from time import sleep

from .models import FailureClass, ProviderRequest, ProviderResponse
from .providers import Provider, ProviderFailure


@dataclass
class RouteOutcome:
    response: ProviderResponse | None
    attempts: int
    failures: list[tuple[str, FailureClass, str]]


class ProviderRouter:
    def __init__(self, providers: list[Provider], retries_per_provider: int = 2,
                 backoff_seconds: float = 0.0):
        if not providers:
            raise ValueError("at least one provider required")
        self.providers = providers
        self.retries_per_provider = max(1, retries_per_provider)
        self.backoff_seconds = max(0.0, backoff_seconds)
        self.quarantined: set[str] = set()

    def route(self, req: ProviderRequest) -> RouteOutcome:
        failures: list[tuple[str, FailureClass, str]] = []
        attempts = 0
        for provider in self.providers:
            if provider.name in self.quarantined:
                continue
            for attempt in range(self.retries_per_provider):
                attempts += 1
                try:
                    return RouteOutcome(provider.complete(req), attempts, failures)
                except ProviderFailure as exc:
                    failures.append((provider.name, exc.failure_class, str(exc)))
                    retryable = exc.failure_class in {FailureClass.TRANSIENT, FailureClass.PROVIDER_OUTAGE}
                    if not retryable:
                        if exc.failure_class in {FailureClass.MALFORMED_OUTPUT, FailureClass.SEMANTIC_FAILURE}:
                            self.quarantined.add(provider.name)
                        break
                    if attempt + 1 < self.retries_per_provider and self.backoff_seconds:
                        sleep(self.backoff_seconds * (2 ** attempt))
        return RouteOutcome(None, attempts, failures)

