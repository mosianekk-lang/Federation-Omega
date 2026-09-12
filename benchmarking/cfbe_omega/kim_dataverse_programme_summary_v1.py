from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from benchmarking.cfbe_omega.kim_dataverse_level7_plus_current_source_signals_v1 import current_source_signals
from benchmarking.cfbe_omega.kim_dataverse_level7_plus_v1 import assess_levels
from benchmarking.cfbe_omega.kim_dataverse_l7_plus_source_scorecard_v1 import score_source_programme


@dataclass(frozen=True)
class ProgrammeSummary:
    highest_source_qualified_level: int
    architecture_score: float
    control_plane_score: float
    empirical_score: float
    provider_score: float
    value_score: float
    operational_level7_claim: bool


def programme_summary() -> ProgrammeSummary:
    signals: Mapping[str, bool] = current_source_signals()
    levels = assess_levels(signals)
    score = score_source_programme(signals)
    highest = max((item.level for item in levels if item.qualified), default=4)
    return ProgrammeSummary(
        highest_source_qualified_level=highest,
        architecture_score=score.architecture_score,
        control_plane_score=score.control_plane_score,
        empirical_score=score.empirical_score,
        provider_score=score.provider_score,
        value_score=score.value_score,
        operational_level7_claim=False,
    )
