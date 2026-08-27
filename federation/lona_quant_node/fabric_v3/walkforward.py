"""Experiment-battery planners for Quant Evidence Fabric v3."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class Window:
    name: str
    start_date: str
    end_date: str
    role: str


@dataclass(frozen=True)
class BatteryCase:
    case_id: str
    asset: str
    window: Window
    parameters: Mapping[str, Any]
    commission: float


def expanding_walk_forward() -> tuple[Window, ...]:
    return (
        Window("wf1_train", "2020-01-01", "2021-12-31", "TRAIN"),
        Window("wf1_test", "2022-01-01", "2022-12-31", "HOLDOUT"),
        Window("wf2_train", "2020-01-01", "2022-12-31", "TRAIN"),
        Window("wf2_test", "2023-01-01", "2023-12-31", "HOLDOUT"),
        Window("wf3_train", "2020-01-01", "2023-12-31", "TRAIN"),
        Window("wf3_test", "2024-01-01", "2024-12-31", "HOLDOUT"),
        Window("wf4_train", "2020-01-01", "2024-12-31", "TRAIN"),
        Window("wf4_test", "2025-01-01", "2026-08-27", "HOLDOUT"),
    )


def parameter_neighborhood(base: Mapping[str, float | int], pct: float = 0.15) -> tuple[dict[str, float | int], ...]:
    low: dict[str, float | int] = {}
    high: dict[str, float | int] = {}
    for key, value in base.items():
        if isinstance(value, bool):
            low[key] = value
            high[key] = value
        elif isinstance(value, int):
            low[key] = max(1, round(value * (1 - pct)))
            high[key] = max(1, round(value * (1 + pct)))
        else:
            low[key] = value * (1 - pct)
            high[key] = value * (1 + pct)
    return (dict(base), low, high)


def build_survival_battery(
    *, assets: Sequence[str], base_parameters: Mapping[str, float | int], commissions: Sequence[float] = (0.001, 0.003)
) -> tuple[BatteryCase, ...]:
    cases: list[BatteryCase] = []
    holdouts = tuple(w for w in expanding_walk_forward() if w.role == "HOLDOUT")
    for asset in assets:
        for window in holdouts:
            for p_index, params in enumerate(parameter_neighborhood(base_parameters)):
                for commission in commissions:
                    cases.append(BatteryCase(
                        case_id=f"{asset}-{window.name}-p{p_index}-c{commission}",
                        asset=asset,
                        window=window,
                        parameters=params,
                        commission=commission,
                    ))
    return tuple(cases)
