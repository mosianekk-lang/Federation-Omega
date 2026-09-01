from __future__ import annotations

"""BCΩ-PRIME v4 bridge to SOE Omega's existing Strategic Genome Library.

No new genome store is created. This adapter only translates the existing SOE
recommendation output into a deterministic PRIME-facing preparation receipt.
Historical mission sequences remain evidence-bound recommendations, never
execution authority or guaranteed future performance.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Iterable, Sequence

from formation_omega.strategic_ecology import StrategicGenomeLibrary, StrategicGenomeRecord


SCHEMA = "BCO_PRIME_V4_STRATEGIC_GENOME_BRIDGE_V1"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _receipt(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class GenomeRecommendation:
    pattern_id: str
    score: float
    realized_value: float
    reliability: float
    mission_sequence: tuple[str, ...]
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GenomePreparationReceipt:
    schema: str
    features: tuple[str, ...]
    recommendations: tuple[GenomeRecommendation, ...]
    selected_pattern_id: str | None
    preparatory_mission_sequence: tuple[str, ...]
    execution_authorized: bool
    provider_effect_authorized: bool
    truth_boundary: tuple[str, ...]
    receipt_sha256: str


def recommend_strategic_genomes(
    records: Iterable[StrategicGenomeRecord],
    *,
    features: Iterable[str],
    minimum_similarity: float = 0.30,
    max_results: int = 3,
) -> GenomePreparationReceipt:
    if not 0.0 <= minimum_similarity <= 1.0:
        raise ValueError("V4_GENOME_MINIMUM_SIMILARITY_INVALID")
    if max_results < 1:
        raise ValueError("V4_GENOME_MAX_RESULTS_INVALID")
    feature_tuple = tuple(sorted(set(item.strip() for item in features if item.strip())))
    if not feature_tuple:
        raise ValueError("V4_GENOME_FEATURES_REQUIRED")
    library = StrategicGenomeLibrary(records)
    ranked = library.recommend(feature_tuple, minimum_similarity=minimum_similarity)[:max_results]
    recommendations = tuple(
        GenomeRecommendation(
            pattern_id=record.pattern_id,
            score=round(float(score), 9),
            realized_value=float(record.realized_value),
            reliability=float(record.reliability),
            mission_sequence=record.mission_sequence,
            evidence_refs=record.evidence_refs,
        )
        for record, score in ranked
    )
    selected = recommendations[0] if recommendations else None
    truth_boundary = (
        "REUSES_SOE_STRATEGIC_GENOME_LIBRARY_NO_NEW_STORE",
        "HISTORICAL_REALIZED_VALUE_DOES_NOT_GUARANTEE_FUTURE_VALUE",
        "GENOME_RECOMMENDATION_IS_PREPARATION_NOT_EXECUTION_AUTHORITY",
        "PROVIDER_AND_CONSEQUENTIAL_EFFECTS_REMAIN_SEPARATELY_GATED",
    )
    body = {
        "schema": SCHEMA,
        "features": feature_tuple,
        "recommendations": [asdict(item) for item in recommendations],
        "selected_pattern_id": selected.pattern_id if selected else None,
        "preparatory_mission_sequence": selected.mission_sequence if selected else (),
        "execution_authorized": False,
        "provider_effect_authorized": False,
        "truth_boundary": truth_boundary,
    }
    return GenomePreparationReceipt(
        schema=SCHEMA,
        features=feature_tuple,
        recommendations=recommendations,
        selected_pattern_id=selected.pattern_id if selected else None,
        preparatory_mission_sequence=selected.mission_sequence if selected else (),
        execution_authorized=False,
        provider_effect_authorized=False,
        truth_boundary=truth_boundary,
        receipt_sha256=_receipt(body),
    )


__all__ = [
    "GenomePreparationReceipt",
    "GenomeRecommendation",
    "recommend_strategic_genomes",
]
