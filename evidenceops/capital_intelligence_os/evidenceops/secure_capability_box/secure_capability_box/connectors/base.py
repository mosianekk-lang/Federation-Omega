from __future__ import annotations

from typing import Any, Protocol


class CapabilityConnector(Protocol):
    name: str

    def execute(
        self,
        *,
        action: str,
        credential: memoryview,
        payload: dict[str, Any],
        correlation_id: str,
    ) -> dict[str, Any]: ...

    def readiness(self) -> dict[str, object]: ...
