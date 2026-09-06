from __future__ import annotations

"""Fail-closed mission currentness selection for ChatGov.

This module is a thin resolver over supplied currentness observations. It does not
query providers, persist a second truth store, or mint authority. Persisted state
labels are treated as observations only; expiration and invalidation gates decide
whether a row may satisfy a current read.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence


CURRENT = "CURRENT"
REFRESH_REQUIRED = "REFRESH_REQUIRED"


def _instant(value: str) -> datetime:
    raw = str(value).strip()
    if not raw:
        raise ValueError("CURRENTNESS_TIMESTAMP_REQUIRED")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        raise ValueError("CURRENTNESS_TIMESTAMP_MUST_BE_OFFSET_AWARE")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class CurrentnessRecord:
    projection_id: str
    mission_id: str
    subject: str
    state: str
    observed_at: str
    expires_at: str
    source_ref: str = ""
    stale_action: str = "REFRESH_REQUIRED"
    event_valid: bool = True
    source_epoch_valid: bool = True
    provider_readback_valid: bool = True

    def validate(self) -> "CurrentnessRecord":
        if not self.projection_id.strip() or not self.mission_id.strip() or not self.subject.strip():
            raise ValueError("CURRENTNESS_SEMANTIC_IDENTITY_REQUIRED")
        observed = _instant(self.observed_at)
        expires = _instant(self.expires_at)
        if expires < observed:
            raise ValueError("CURRENTNESS_EXPIRY_PRECEDES_OBSERVATION")
        return self


@dataclass(frozen=True, slots=True)
class CurrentnessDecision:
    state: str
    mission_id: str
    subject: str
    projection_id: str = ""
    source_ref: str = ""
    stale_action: str = "REFRESH_REQUIRED"
    reasons: tuple[str, ...] = ()

    @property
    def reusable(self) -> bool:
        return self.state == CURRENT


def resolve_currentness(
    records: Sequence[CurrentnessRecord],
    *,
    mission_id: str,
    subject: str,
    now: str,
) -> CurrentnessDecision:
    """Return the newest eligible row for one exact mission+subject key.

    `Expires_At` is a hard upper freshness bound: `now >= expires_at` is expired.
    Event/source/provider invalidation can make a row unusable earlier. Historical
    rows remain untouched; if no row qualifies the caller gets REFRESH_REQUIRED.
    """

    mission_key = str(mission_id).strip()
    subject_key = str(subject).strip()
    if not mission_key or not subject_key:
        raise ValueError("CURRENTNESS_LOOKUP_KEY_REQUIRED")
    now_utc = _instant(now)

    matching: list[CurrentnessRecord] = []
    for record in records:
        record.validate()
        if record.mission_id == mission_key and record.subject == subject_key:
            matching.append(record)

    if not matching:
        return CurrentnessDecision(
            state=REFRESH_REQUIRED,
            mission_id=mission_key,
            subject=subject_key,
            reasons=("NO_MATCHING_CURRENTNESS_RECORD",),
        )

    matching.sort(key=lambda row: (_instant(row.observed_at), row.projection_id), reverse=True)
    rejected: list[str] = []
    for record in matching:
        reasons: list[str] = []
        if now_utc >= _instant(record.expires_at):
            reasons.append("EXPIRED")
        if not record.event_valid:
            reasons.append("EVENT_INVALIDATED")
        if not record.source_epoch_valid:
            reasons.append("SOURCE_EPOCH_INVALID")
        if not record.provider_readback_valid:
            reasons.append("PROVIDER_READBACK_INVALID")
        if reasons:
            rejected.extend(f"{record.projection_id}:{reason}" for reason in reasons)
            continue
        return CurrentnessDecision(
            state=CURRENT,
            mission_id=mission_key,
            subject=subject_key,
            projection_id=record.projection_id,
            source_ref=record.source_ref,
            stale_action=record.stale_action,
            reasons=("NEWEST_ELIGIBLE_UNEXPIRED_RECORD",),
        )

    newest = matching[0]
    return CurrentnessDecision(
        state=REFRESH_REQUIRED,
        mission_id=mission_key,
        subject=subject_key,
        projection_id=newest.projection_id,
        source_ref=newest.source_ref,
        stale_action=newest.stale_action or "REFRESH_REQUIRED",
        reasons=tuple(rejected) or ("NO_ELIGIBLE_CURRENTNESS_RECORD",),
    )


__all__ = [
    "CURRENT",
    "REFRESH_REQUIRED",
    "CurrentnessDecision",
    "CurrentnessRecord",
    "resolve_currentness",
]
