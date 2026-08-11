from __future__ import annotations

from typing import Protocol

from ..models import SecretReference


class SecretProvider(Protocol):
    name: str

    def access(self, reference: SecretReference) -> bytearray:
        """Return a mutable buffer so the broker can zero it after one execution."""
        ...

    def readiness(self) -> dict[str, object]: ...
