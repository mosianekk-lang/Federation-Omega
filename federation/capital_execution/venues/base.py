from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, runtime_checkable

from ..models import MarketSnapshot


@dataclass(frozen=True)
class VenueObservationCapabilities:
    venue: str
    public_market_data: bool
    authenticated_account_read: bool = False
    order_write: bool = False
    withdrawal_write: bool = False
    transfer_write: bool = False

    def validate_observer_only(self) -> None:
        if not self.venue:
            raise ValueError("venue is required")
        if self.order_write or self.withdrawal_write or self.transfer_write:
            raise PermissionError("OBSERVER_CAPABILITY_CANNOT_INCLUDE_FINANCIAL_WRITE")


@runtime_checkable
class VenueMarketObserver(Protocol):
    """Venue-neutral observation contract. No execution methods are part of the protocol."""

    def snapshot(self, pair: str) -> MarketSnapshot:
        ...

    def candles(self, pair: str, *, since_ms: int, duration_seconds: int) -> Mapping[str, Any]:
        ...

    def markets(self, pair: str | None = None) -> Mapping[str, Any]:
        ...


def observer_capabilities(adapter: object, *, venue: str, authenticated_account_read: bool = False) -> VenueObservationCapabilities:
    capabilities = VenueObservationCapabilities(
        venue=venue,
        public_market_data=isinstance(adapter, VenueMarketObserver),
        authenticated_account_read=authenticated_account_read,
    )
    capabilities.validate_observer_only()
    return capabilities
