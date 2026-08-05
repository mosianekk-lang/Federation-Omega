from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .algorithms_common import (
    AUTHORITY_CEILING, AlgorithmOpportunity, AlgorithmResult, clamp, number,
    sequence, sha256, text, unique_text,
)

class OwnerBurdenRouteOptimizer:
    algorithm_id = "ALG-EOPS-OBRO-001"
    name = "Owner-Burden Route Optimizer"

    def run(self, routes: Sequence[Mapping[str, Any]]) -> AlgorithmResult:
        ranked: list[dict[str, Any]] = []
        violations: list[str] = []
        for index, route in enumerate(routes, start=1):
            route_id = text(route.get("route_id")) or f"ROUTE-{index:04d}"
            authority = text(route.get("authority")) or AUTHORITY_CEILING
            if authority not in {"A0_READ", AUTHORITY_CEILING}:
                violations.append(f"{route_id}:ROUTE_EXCEEDS_A1_AUTHORITY")
                continue
            mission = clamp(number(route.get("mission_fidelity"), 0.5))
            value = clamp(number(route.get("expected_value"), 0.5))
            probability = clamp(number(route.get("probability"), 0.5))
            proof = clamp(number(route.get("proof_quality"), 0.5))
            reversibility = clamp(number(route.get("reversibility"), 0.5))
            information = clamp(number(route.get("information_gain"), 0.3))
            option_value = clamp(number(route.get("option_value"), 0.3))
            reuse = clamp(number(route.get("reuse_potential"), 0.3))
            cost = max(0.01, number(route.get("cost"), 0.2))
            latency = max(0.01, number(route.get("latency"), 0.2))
            maintenance = max(0.01, number(route.get("maintenance"), 0.2))
            risk = max(0.01, number(route.get("risk"), 0.1))
            owner_burden = max(0.0, number(route.get("owner_burden"), 0.1))
            numerator = mission * value * probability * proof * reversibility * (0.5 + information) * (0.5 + option_value) * (0.5 + reuse)
            denominator = 0.1 + cost + latency + maintenance + risk + owner_burden * 2.0
            score = numerator / denominator
            ranked.append({
                "route_id": route_id,
                "description": text(route.get("description")),
                "score": round(score, 8),
                "owner_burden": owner_burden,
                "proof_quality": proof,
                "reversibility": reversibility,
                "authority": authority,
                "fallback": text(route.get("fallback")),
            })
        ranked.sort(key=lambda row: (-row["score"], row["owner_burden"], row["route_id"]))
        return AlgorithmResult(
            algorithm_id=self.algorithm_id,
            name=self.name,
            status="ROUTE_SELECTED" if ranked else "NO_AUTHORISED_ROUTE",
            maturity="TESTED_LOCAL",
            output={"ranked_routes": ranked, "selected_route": ranked[0] if ranked else None},
            violations=tuple(violations),
            metrics={"route_count": float(len(ranked))},
        )
