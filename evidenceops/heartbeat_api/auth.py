"""Defense-in-depth application authentication for a private Cloud Run service."""

from __future__ import annotations

import hmac
from dataclasses import dataclass, field

from .errors import AuthenticationDenied


@dataclass(frozen=True, slots=True)
class InternalTokenAuthorizer:
    """Verifies an injected application token after platform IAM authentication."""

    expected_value: str = field(repr=False)

    @property
    def configured(self) -> bool:
        return isinstance(self.expected_value, str) and len(self.expected_value.encode("utf-8")) >= 32

    def verify(self, supplied_value: str | None) -> None:
        if not self.configured or not isinstance(supplied_value, str):
            raise AuthenticationDenied("application-internal authentication denied")
        if not hmac.compare_digest(self.expected_value, supplied_value):
            raise AuthenticationDenied("application-internal authentication denied")
