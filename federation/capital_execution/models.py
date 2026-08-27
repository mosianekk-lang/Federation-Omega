from __future__ import annotations

from dataclasses import dataclass, field, asdict
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping
import hashlib
import json


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def stable_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def as_decimal(value: Any) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid decimal value") from exc
    if not result.is_finite():
        raise ValueError("decimal value must be finite")
    return result


@dataclass(frozen=True)
class BookLevel:
    price: Decimal
    volume: Decimal

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BookLevel":
        level = cls(as_decimal(value["price"]), as_decimal(value["volume"]))
        if level.price <= 0 or level.volume <= 0:
            raise ValueError("order book price and volume must be positive")
        return level


@dataclass(frozen=True)
class MarketSnapshot:
    venue: str
    pair: str
    bids: tuple[BookLevel, ...]
    asks: tuple[BookLevel, ...]
    timestamp_ms: int
    source_ref: str
    public_data: bool = True

    def validate(self) -> None:
        if not self.venue or not self.pair or not self.source_ref:
            raise ValueError("market snapshot identity and source_ref are required")
        if self.timestamp_ms <= 0:
            raise ValueError("market snapshot timestamp must be positive")
        if not self.bids or not self.asks:
            raise ValueError("market snapshot requires bids and asks")
        if any(self.bids[i].price < self.bids[i + 1].price for i in range(len(self.bids) - 1)):
            raise ValueError("bids must be sorted descending")
        if any(self.asks[i].price > self.asks[i + 1].price for i in range(len(self.asks) - 1)):
            raise ValueError("asks must be sorted ascending")
        if not self.public_data:
            raise PermissionError("V1_MARKET_SNAPSHOT_MUST_BE_PUBLIC")

    @property
    def best_bid(self) -> Decimal:
        self.validate()
        return self.bids[0].price

    @property
    def best_ask(self) -> Decimal:
        self.validate()
        return self.asks[0].price

    @property
    def mid(self) -> Decimal:
        return (self.best_bid + self.best_ask) / Decimal("2")

    @property
    def spread_bps(self) -> Decimal:
        return ((self.best_ask - self.best_bid) / self.mid) * Decimal("10000")

    def fingerprint(self) -> str:
        self.validate()
        return stable_sha256(asdict(self))


@dataclass(frozen=True)
class ShadowOrderRequest:
    capital_intent_id: str
    pair: str
    side: str
    base_volume: Decimal
    maximum_slippage_bps: Decimal
    mode: str = "SHADOW"
    external_effect: bool = False
    financial_effect: bool = False

    def validate(self) -> None:
        if not self.capital_intent_id or not self.pair:
            raise ValueError("capital_intent_id and pair are required")
        if self.side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if self.base_volume <= 0:
            raise ValueError("base_volume must be positive")
        if self.maximum_slippage_bps < 0:
            raise ValueError("maximum_slippage_bps cannot be negative")
        if self.mode != "SHADOW" or self.external_effect or self.financial_effect:
            raise PermissionError("V1_EXECUTION_IS_SHADOW_ONLY")

    def fingerprint(self) -> str:
        self.validate()
        return stable_sha256(asdict(self))


@dataclass(frozen=True)
class ShadowFill:
    request_fingerprint: str
    snapshot_fingerprint: str
    status: str
    filled_base_volume: Decimal
    unfilled_base_volume: Decimal
    vwap: Decimal | None
    best_price: Decimal
    gross_counter_value: Decimal
    slippage_bps: Decimal | None
    depth_levels_used: int
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    external_effect: bool = False
    financial_effect: bool = False

    def fingerprint(self) -> str:
        if self.external_effect or self.financial_effect:
            raise PermissionError("SHADOW_FILL_CANNOT_HAVE_FINANCIAL_EFFECT")
        return stable_sha256(asdict(self))
