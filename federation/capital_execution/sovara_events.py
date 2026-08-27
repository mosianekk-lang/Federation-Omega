from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .models import stable_sha256


ALLOWED_EVENT_TYPES = {
    "QUANT.EVIDENCE.RECONCILED",
    "CAPITAL.INTENT.PREPARED",
    "SHADOW.EXECUTION.RECONCILED",
    "CAPITAL.CANDIDATE.REJECTED",
    "CAPITAL.CIRCUIT.OPENED",
    "FAILURE.WIN.TRIGGERED",
    "LUNO.MARKET.SNAPSHOT_OBSERVED",
    "LUNO.DATASET.NORMALIZED",
}

_DISALLOWED_KEYS = {
    "authorization",
    "credential_value",
    "private_material",
    "token_value",
    "execution_lease",
    "owner_capital_authority",
}


def _validate_payload(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).lower()
            if key_text in _DISALLOWED_KEYS or key_text.endswith("_credential"):
                raise PermissionError("EVENT_PAYLOAD_CONTAINS_PRIVATE_OR_AUTHORITY_FIELD")
            _validate_payload(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _validate_payload(child)


@dataclass(frozen=True)
class CapitalCloudEvent:
    event_id: str
    event_type: str
    source: str
    subject: str
    data: Mapping[str, Any]
    external_effect: bool = False
    financial_effect: bool = False

    def validate(self) -> None:
        if not self.event_id or not self.source or not self.subject:
            raise ValueError("event identity fields are required")
        if self.event_type not in ALLOWED_EVENT_TYPES:
            raise ValueError("event type is not allowlisted")
        if self.external_effect or self.financial_effect:
            raise PermissionError("CAPITAL_EVENT_MUST_BE_NO_EFFECT")
        _validate_payload(self.data)

    def digest(self) -> str:
        self.validate()
        return stable_sha256(asdict(self))


class CapitalEventFactory:
    """Builds SOVARA-compatible no-effect envelopes. It does not publish them."""

    def build(self, *, event_type: str, source: str, subject: str, data: Mapping[str, Any]) -> CapitalCloudEvent:
        seed = {"event_type": event_type, "source": source, "subject": subject, "data": dict(data), "external_effect": False, "financial_effect": False}
        event = CapitalCloudEvent(stable_sha256(seed), event_type, source, subject, dict(data))
        event.validate()
        return event
