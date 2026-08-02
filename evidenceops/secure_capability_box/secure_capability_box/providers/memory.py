from __future__ import annotations

from ..errors import ProviderUnavailable
from ..models import SecretReference


class InMemorySecretProvider:
    """Test-only provider; it deliberately reports production_ready=false."""

    name = "memory"

    def __init__(self, values: dict[str, bytes]) -> None:
        self._values = {key: bytes(value) for key, value in values.items()}

    def access(self, reference: SecretReference) -> bytearray:
        try:
            return bytearray(self._values[reference.reference_id])
        except KeyError as exc:
            raise ProviderUnavailable("referenced secret is unavailable") from exc

    def readiness(self) -> dict[str, object]:
        return {"state": "TEST_ONLY", "production_ready": False}
