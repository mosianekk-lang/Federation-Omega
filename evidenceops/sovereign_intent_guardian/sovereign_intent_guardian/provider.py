"""Data-only advisory receipt contract; no executable provider is accepted here."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from .contracts import SHA256_RE, Verdict, canonical_json


PROVIDER_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")


class PermanentAdvisoryError(RuntimeError):
    """A non-retryable invalid advisory receipt."""


@dataclass(frozen=True)
class AdvisoryReview:
    """A validated external receipt candidate containing hashes, not raw model text."""

    provider_id: str
    observation_hashes: tuple[str, ...] = ()
    suggested_verdict: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "observation_hashes": list(self.observation_hashes),
            "suggested_verdict": self.suggested_verdict,
            "authority": "ADVISORY_ONLY",
        }


def validated_advisory_record(value: Any) -> dict[str, Any]:
    """Validate receipt data and return its only persistable representation."""

    if not isinstance(value, AdvisoryReview):
        raise PermanentAdvisoryError("ADVISORY_RECEIPT_SCHEMA_INVALID")
    if not PROVIDER_ID_RE.fullmatch(value.provider_id):
        raise PermanentAdvisoryError("ADVISORY_RECEIPT_PROVIDER_ID_INVALID")
    if len(value.observation_hashes) > 20:
        raise PermanentAdvisoryError("ADVISORY_RECEIPT_TOO_LARGE")
    if any(not isinstance(item, str) or not SHA256_RE.fullmatch(item) for item in value.observation_hashes):
        raise PermanentAdvisoryError("ADVISORY_RECEIPT_HASH_INVALID")
    if value.suggested_verdict not in {"", *(verdict.value for verdict in Verdict)}:
        raise PermanentAdvisoryError("ADVISORY_RECEIPT_VERDICT_INVALID")
    result = value.to_dict()
    result["source_type"] = "MODEL_ADVISORY_RECEIPT"
    if len(canonical_json(result).encode("utf-8")) > 16_384:
        raise PermanentAdvisoryError("ADVISORY_RECEIPT_TOO_LARGE")
    return result


def is_persistable_advisory_record(value: Mapping[str, Any]) -> bool:
    """Reject raw or caller-invented advisory bodies at the database boundary."""

    if not value:
        return True
    system_keys = {"provider_id", "source_type", "authority", "reason"}
    if set(value) == system_keys:
        return (
            value.get("provider_id") in {"not-consumed", "disabled"}
            and value.get("source_type") == "MODEL_ADVISORY_RECEIPT"
            and value.get("authority") == "ADVISORY_ONLY"
            and value.get("reason") in {"DETERMINISTIC_NON_ALIGN", "NO_ADVISORY_RECEIPT"}
        )
    receipt_keys = {
        "provider_id", "observation_hashes", "suggested_verdict", "authority", "source_type"
    }
    if set(value) != receipt_keys:
        return False
    try:
        candidate = AdvisoryReview(
            provider_id=value["provider_id"],
            observation_hashes=tuple(value["observation_hashes"]),
            suggested_verdict=value["suggested_verdict"],
        )
        return validated_advisory_record(candidate) == dict(value)
    except (KeyError, TypeError, PermanentAdvisoryError):
        return False
