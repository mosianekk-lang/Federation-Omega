from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable


@dataclass(frozen=True)
class Offer:
    offer_id: str
    name: str
    target_customer: str
    setup_price_zar: int
    monthly_price_zar: int
    included_builds: int
    included_support_hours: int


@dataclass(frozen=True)
class UsageEvent:
    tenant_id: str
    event_type: str
    quantity: float
    unit_cost_zar: float


class CommercialKernel:
    """Deterministic commercial product, metering and margin kernel."""

    def __init__(self) -> None:
        self.offers = {
            "AO-PILOT": Offer(
                "AO-PILOT",
                "Operational Automation Pilot",
                "One department with one process family",
                200_000,
                30_000,
                1,
                10,
            ),
            "AO-DEPARTMENT": Offer(
                "AO-DEPARTMENT",
                "Department Automation Platform",
                "Department requiring multiple governed workflows",
                500_000,
                75_000,
                4,
                30,
            ),
            "AO-ENTERPRISE": Offer(
                "AO-ENTERPRISE",
                "Enterprise Digital Systems Institution",
                "Multi-department regulated organisation",
                1_500_000,
                200_000,
                12,
                80,
            ),
        }

    def catalogue(self) -> list[dict]:
        return [asdict(offer) for offer in self.offers.values()]

    def quote(self, offer_id: str, months: int = 12) -> dict:
        if months < 1:
            raise ValueError("months must be positive")
        offer = self.offers[offer_id]
        recurring = offer.monthly_price_zar * months
        return {
            "offer_id": offer_id,
            "setup_zar": offer.setup_price_zar,
            "recurring_zar": recurring,
            "contract_value_zar": offer.setup_price_zar + recurring,
            "months": months,
        }

    def meter(self, events: Iterable[UsageEvent]) -> dict:
        rows = list(events)
        total = round(sum(row.quantity * row.unit_cost_zar for row in rows), 2)
        by_type: dict[str, float] = {}
        for row in rows:
            by_type[row.event_type] = round(
                by_type.get(row.event_type, 0.0) + row.quantity * row.unit_cost_zar,
                2,
            )
        return {"cost_zar": total, "by_type": by_type, "events": len(rows)}

    def unit_economics(self, offer_id: str, monthly_delivery_cost_zar: float) -> dict:
        offer = self.offers[offer_id]
        revenue = float(offer.monthly_price_zar)
        gross_profit = revenue - monthly_delivery_cost_zar
        gross_margin = gross_profit / revenue if revenue else 0.0
        return {
            "offer_id": offer_id,
            "monthly_revenue_zar": revenue,
            "monthly_delivery_cost_zar": monthly_delivery_cost_zar,
            "gross_profit_zar": round(gross_profit, 2),
            "gross_margin": round(gross_margin, 4),
            "commercially_healthy": gross_margin >= 0.55,
        }
