from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any, Mapping, Sequence
import csv
import io

from .models import as_decimal, stable_sha256


@dataclass(frozen=True)
class OHLCVBar:
    timestamp_ms: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def validate(self) -> None:
        if self.timestamp_ms <= 0:
            raise ValueError("timestamp_ms must be positive")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("OHLC prices must be positive")
        if self.volume < 0:
            raise ValueError("volume cannot be negative")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high violates OHLC invariants")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low violates OHLC invariants")


@dataclass(frozen=True)
class NormalizedOHLCVDataset:
    provider: str
    pair: str
    duration_seconds: int
    bars: tuple[OHLCVBar, ...]
    source_ref: str
    external_effect: bool = False
    financial_effect: bool = False

    def validate(self) -> None:
        if not self.provider or not self.pair or not self.source_ref:
            raise ValueError("dataset identity and source_ref are required")
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        if len(self.bars) < 1:
            raise ValueError("at least one OHLCV bar is required")
        timestamps = []
        for bar in self.bars:
            bar.validate()
            timestamps.append(bar.timestamp_ms)
        if timestamps != sorted(timestamps) or len(timestamps) != len(set(timestamps)):
            raise ValueError("OHLCV timestamps must be unique and ascending")
        if self.external_effect or self.financial_effect:
            raise PermissionError("DATASET_NORMALIZATION_CANNOT_HAVE_FINANCIAL_EFFECT")

    def fingerprint(self) -> str:
        self.validate()
        return stable_sha256(asdict(self))

    def to_csv_text(self) -> str:
        """Return deterministic OHLCV CSV suitable for later LONA upload after separate provider action."""
        self.validate()
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for bar in self.bars:
            writer.writerow([
                bar.timestamp_ms,
                str(bar.open),
                str(bar.high),
                str(bar.low),
                str(bar.close),
                str(bar.volume),
            ])
        return buffer.getvalue()


class LunoToLonaDataBridge:
    """Normalizes Luno candle payloads without uploading, trading or claiming LONA dataset creation."""

    def normalize_candles(
        self,
        *,
        pair: str,
        duration_seconds: int,
        payload: Mapping[str, Any],
        source_ref: str,
    ) -> NormalizedOHLCVDataset:
        raw = payload.get("candles")
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            raise ValueError("Luno candle payload requires a candles sequence")
        bars: list[OHLCVBar] = []
        for item in raw:
            if not isinstance(item, Mapping):
                raise ValueError("each candle must be a mapping")
            bar = OHLCVBar(
                timestamp_ms=int(item["timestamp"]),
                open=as_decimal(item["open"]),
                high=as_decimal(item["high"]),
                low=as_decimal(item["low"]),
                close=as_decimal(item["close"]),
                volume=as_decimal(item.get("volume", "0")),
            )
            bar.validate()
            bars.append(bar)
        dataset = NormalizedOHLCVDataset(
            provider="LUNO",
            pair=pair,
            duration_seconds=int(duration_seconds),
            bars=tuple(bars),
            source_ref=source_ref,
        )
        dataset.validate()
        return dataset
