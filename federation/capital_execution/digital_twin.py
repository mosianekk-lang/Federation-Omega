from __future__ import annotations

from decimal import Decimal

from .models import MarketSnapshot, ShadowFill, ShadowOrderRequest


class ExecutionDigitalTwin:
    """Deterministic order-book walk. It never calls a venue or creates a real order."""

    def simulate(self, request: ShadowOrderRequest, snapshot: MarketSnapshot) -> ShadowFill:
        request.validate()
        snapshot.validate()
        if request.pair != snapshot.pair:
            raise ValueError("request pair does not match snapshot pair")

        levels = snapshot.asks if request.side == "BUY" else snapshot.bids
        best = levels[0].price
        remaining = request.base_volume
        filled = Decimal("0")
        counter = Decimal("0")
        used = 0

        for level in levels:
            if remaining <= 0:
                break
            take = min(remaining, level.volume)
            filled += take
            counter += take * level.price
            remaining -= take
            used += 1

        if filled <= 0:
            return ShadowFill(
                request_fingerprint=request.fingerprint(),
                snapshot_fingerprint=snapshot.fingerprint(),
                status="REJECTED",
                filled_base_volume=Decimal("0"),
                unfilled_base_volume=request.base_volume,
                vwap=None,
                best_price=best,
                gross_counter_value=Decimal("0"),
                slippage_bps=None,
                depth_levels_used=0,
                reason_codes=("NO_EXECUTABLE_DEPTH",),
            )

        vwap = counter / filled
        if request.side == "BUY":
            slippage = ((vwap - best) / best) * Decimal("10000")
        else:
            slippage = ((best - vwap) / best) * Decimal("10000")
        slippage = max(Decimal("0"), slippage)

        reasons: list[str] = []
        status = "FILLED" if remaining <= 0 else "PARTIAL"
        if remaining > 0:
            reasons.append("INSUFFICIENT_ORDER_BOOK_DEPTH")
        if slippage > request.maximum_slippage_bps:
            status = "REJECTED"
            reasons.append("SLIPPAGE_LIMIT_BREACHED")

        return ShadowFill(
            request_fingerprint=request.fingerprint(),
            snapshot_fingerprint=snapshot.fingerprint(),
            status=status,
            filled_base_volume=filled,
            unfilled_base_volume=max(Decimal("0"), remaining),
            vwap=vwap,
            best_price=best,
            gross_counter_value=counter,
            slippage_bps=slippage,
            depth_levels_used=used,
            reason_codes=tuple(reasons),
        )
