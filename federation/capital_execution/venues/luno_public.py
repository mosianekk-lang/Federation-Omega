from __future__ import annotations

from typing import Any, Callable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

from ..models import BookLevel, MarketSnapshot


Transport = Callable[[str, Mapping[str, Any]], Mapping[str, Any]]


class LunoPublicRESTClient:
    """Luno public market-data adapter. It intentionally contains no authenticated or write method."""

    API_BASE = "https://api.luno.com"
    PUBLIC_PATHS = {
        "/api/1/ticker",
        "/api/1/tickers",
        "/api/1/orderbook_top",
        "/api/1/orderbook",
        "/api/1/trades",
        "/api/exchange/1/candles",
        "/api/exchange/1/markets",
    }

    def __init__(self, transport: Transport | None = None, *, timeout_seconds: float = 5.0) -> None:
        self.timeout_seconds = float(timeout_seconds)
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._transport = transport or self._https_get

    def _https_get(self, path: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
        if path not in self.PUBLIC_PATHS:
            raise PermissionError("LUNO_PUBLIC_ADAPTER_PATH_NOT_ALLOWLISTED")
        query = urlencode([(key, value) for key, value in params.items() if value is not None], doseq=True)
        url = f"{self.API_BASE}{path}" + (f"?{query}" if query else "")
        if not url.startswith("https://"):
            raise PermissionError("LUNO_HTTPS_REQUIRED")
        request = Request(url, method="GET", headers={"Accept": "application/json", "User-Agent": "Federation-Capital-Execution/1.0"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("Luno response must be an object")
        return payload

    def _get(self, path: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
        if path not in self.PUBLIC_PATHS:
            raise PermissionError("LUNO_PUBLIC_ADAPTER_PATH_NOT_ALLOWLISTED")
        return self._transport(path, params)

    def ticker(self, pair: str) -> Mapping[str, Any]:
        return self._get("/api/1/ticker", {"pair": pair})

    def order_book_top(self, pair: str) -> Mapping[str, Any]:
        return self._get("/api/1/orderbook_top", {"pair": pair})

    def candles(self, pair: str, *, since_ms: int, duration_seconds: int) -> Mapping[str, Any]:
        allowed = {60, 300, 900, 1800, 3600, 10800, 14400, 28800, 86400, 259200, 604800}
        if duration_seconds not in allowed:
            raise ValueError("unsupported Luno candle duration")
        if since_ms <= 0:
            raise ValueError("since_ms must be positive")
        return self._get("/api/exchange/1/candles", {"pair": pair, "since": since_ms, "duration": duration_seconds})

    def markets(self, pair: str | None = None) -> Mapping[str, Any]:
        return self._get("/api/exchange/1/markets", {"pair": pair})

    def snapshot(self, pair: str) -> MarketSnapshot:
        payload = self.order_book_top(pair)
        bids = tuple(BookLevel.from_mapping(item) for item in payload.get("bids", ()))
        asks = tuple(BookLevel.from_mapping(item) for item in payload.get("asks", ()))
        snapshot = MarketSnapshot(
            venue="LUNO",
            pair=pair,
            bids=bids,
            asks=asks,
            timestamp_ms=int(payload.get("timestamp", 0)),
            source_ref=f"LUNO_PUBLIC:/api/1/orderbook_top?pair={pair}",
            public_data=True,
        )
        snapshot.validate()
        return snapshot

    def create_order(self, *args: Any, **kwargs: Any) -> None:
        raise PermissionError("LUNO_WRITE_OPERATIONS_NOT_IMPLEMENTED_V1")

    def cancel_order(self, *args: Any, **kwargs: Any) -> None:
        raise PermissionError("LUNO_WRITE_OPERATIONS_NOT_IMPLEMENTED_V1")

    def convert(self, *args: Any, **kwargs: Any) -> None:
        raise PermissionError("LUNO_WRITE_OPERATIONS_NOT_IMPLEMENTED_V1")
