from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping, Sequence


@dataclass(frozen=True)
class TimescaleObjective:
    objective_id: str
    horizon: str
    value: float
    urgency: float
    option_value: float
    risk: float


@dataclass(frozen=True)
class InformationRoute:
    route_id: str
    expected_information_gain: float
    expected_value_gain: float
    cost: float
    owner_burden: float
    external_effect: bool = False


@dataclass(frozen=True)
class FrontierPlan:
    ordered_objectives: tuple[str, ...]
    information_route: str | None
    external_effect_authorized: bool
    receipt: str


def multi_timescale_objective_plan(objectives: Sequence[TimescaleObjective]) -> tuple[str, ...]:
    ids = [item.objective_id for item in objectives]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate objective_id")
    horizon_weight = {"NOW": 1.0, "NEAR": 0.8, "MID": 0.6, "LONG": 0.4}
    for item in objectives:
        if item.horizon not in horizon_weight:
            raise ValueError("unknown horizon")
        for value in (item.value, item.urgency, item.option_value, item.risk):
            if value < 0:
                raise ValueError("objective values must be non-negative")
    return tuple(
        item.objective_id
        for item in sorted(
            objectives,
            key=lambda item: (
                item.value * 0.40
                + item.urgency * horizon_weight[item.horizon] * 0.30
                + item.option_value * 0.20
                - item.risk * 0.10,
                item.objective_id,
            ),
            reverse=True,
        )
    )


def select_information_route(routes: Sequence[InformationRoute]) -> str | None:
    eligible = []
    for route in routes:
        if route.external_effect:
            continue
        if min(route.expected_information_gain, route.expected_value_gain, route.cost, route.owner_burden) < 0:
            raise ValueError("route metrics must be non-negative")
        utility = (
            route.expected_information_gain * 0.45
            + route.expected_value_gain * 0.35
            - route.cost * 0.10
            - route.owner_burden * 0.10
        )
        eligible.append((utility, route.route_id))
    if not eligible:
        return None
    return max(eligible, key=lambda item: (item[0], item[1]))[1]


def compile_frontier_plan(
    objectives: Sequence[TimescaleObjective],
    routes: Sequence[InformationRoute],
) -> FrontierPlan:
    ordered = multi_timescale_objective_plan(objectives)
    route = select_information_route(routes)
    payload: Mapping[str, object] = {
        "ordered_objectives": ordered,
        "information_route": route,
        "external_effect_authorized": False,
        "authority_inherited": False,
    }
    receipt = "sha256:" + sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return FrontierPlan(ordered, route, False, receipt)
