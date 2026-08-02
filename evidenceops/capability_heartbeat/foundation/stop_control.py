"""Immutable stop-generation fencing."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import Authority, parse_utc
from .errors import ContractError, FreshnessError, StopFencedError
from .privacy import require_code, require_hash


@dataclass(frozen=True, slots=True)
class StopControl:
    active: bool = True
    generation: int = 0
    stop_reason_code: str = "NONE"

    def __post_init__(self) -> None:
        if not isinstance(self.active, bool):
            raise ContractError("STOP_ACTIVE_MUST_BE_BOOLEAN")
        if isinstance(self.generation, bool) or not isinstance(self.generation, int) or self.generation < 0:
            raise ContractError("INVALID_STOP_GENERATION")
        require_code(self.stop_reason_code, field="stop_reason_code")
        if self.active and self.stop_reason_code != "NONE":
            raise ContractError("ACTIVE_CONTROL_CANNOT_HAVE_STOP_REASON")

    def stop(self, reason_code: str) -> "StopControl":
        require_code(reason_code, field="reason_code")
        if reason_code == "NONE":
            raise ContractError("STOP_REASON_REQUIRED")
        return StopControl(active=False, generation=self.generation + 1, stop_reason_code=reason_code)

    def assert_current(self, generation: int) -> None:
        if not self.active:
            raise StopFencedError("CONTROL_STOPPED")
        if generation != self.generation:
            raise StopFencedError("STALE_CONTROL_GENERATION")



@dataclass(frozen=True, slots=True)
class GenerationLease:
    lease_id: str
    node_id: str
    owner_code: str
    matter_code: str
    control_generation: int
    issued_at: str
    expires_at: str
    authority_ceiling: Authority = Authority.A0

    def __post_init__(self) -> None:
        require_hash(self.lease_id, field="lease_id")
        for field_name in ("node_id", "owner_code", "matter_code"):
            require_code(getattr(self, field_name), field=field_name)
        if isinstance(self.control_generation, bool) or not isinstance(self.control_generation, int) or self.control_generation < 0:
            raise ContractError("INVALID_CONTROL_GENERATION")
        issued = parse_utc(self.issued_at, field="issued_at")
        expires = parse_utc(self.expires_at, field="expires_at")
        if expires <= issued or (expires - issued).total_seconds() > 300:
            raise ContractError("INVALID_LEASE_TTL")
        if self.authority_ceiling is not Authority.A0:
            raise ContractError("LEASE_AUTHORITY_MUST_BE_A0")

    def assert_current(self, *, stop_control: StopControl, now: str) -> None:
        stop_control.assert_current(self.control_generation)
        current = parse_utc(now, field="now")
        if current < parse_utc(self.issued_at, field="issued_at") or current >= parse_utc(self.expires_at, field="expires_at"):
            raise FreshnessError("LEASE_NOT_FRESH")


@dataclass(frozen=True, slots=True)
class RecommendationDelegation:
    delegation_id: str
    from_node_id: str
    to_node_id: str
    owner_code: str
    matter_code: str
    recommendation_hash: str
    control_generation: int
    issued_at: str
    expires_at: str
    authority_ceiling: Authority = Authority.A0

    def __post_init__(self) -> None:
        for field_name in ("delegation_id", "recommendation_hash"):
            require_hash(getattr(self, field_name), field=field_name)
        for field_name in ("from_node_id", "to_node_id", "owner_code", "matter_code"):
            require_code(getattr(self, field_name), field=field_name)
        if self.from_node_id == self.to_node_id:
            raise ContractError("SELF_DELEGATION_PROHIBITED")
        if isinstance(self.control_generation, bool) or not isinstance(self.control_generation, int) or self.control_generation < 0:
            raise ContractError("INVALID_CONTROL_GENERATION")
        issued = parse_utc(self.issued_at, field="issued_at")
        expires = parse_utc(self.expires_at, field="expires_at")
        if expires <= issued or (expires - issued).total_seconds() > 300:
            raise ContractError("INVALID_DELEGATION_TTL")
        if self.authority_ceiling is not Authority.A0:
            raise ContractError("DELEGATION_AUTHORITY_MUST_BE_A0")

    def assert_current(self, *, stop_control: StopControl, now: str) -> None:
        stop_control.assert_current(self.control_generation)
        current = parse_utc(now, field="now")
        if current < parse_utc(self.issued_at, field="issued_at") or current >= parse_utc(self.expires_at, field="expires_at"):
            raise FreshnessError("DELEGATION_NOT_FRESH")
