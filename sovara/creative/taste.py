from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable


class TasteError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class TasteObservation:
    observation_id: str
    dimension: str
    value: str
    evidence_weight: float
    sequence: int
    source: str = "OWNER_CORRECTION"
    synthetic: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("observation_id", self.observation_id),
            ("dimension", self.dimension),
            ("value", self.value),
            ("source", self.source),
        ):
            if not value.strip():
                raise TasteError(f"{name} is required")
        if not 0.0 <= self.evidence_weight <= 1.0:
            raise TasteError("evidence_weight must be between 0 and 1")
        if self.sequence < 0:
            raise TasteError("sequence must be non-negative")


@dataclass(frozen=True, slots=True)
class TastePreference:
    dimension: str
    value: str
    confidence: float
    supporting_observation_ids: tuple[str, ...]
    conflicting_observation_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TasteReceipt:
    schema: str
    owner_scope: str
    preference_count: int
    conflict_count: int
    observation_ids: tuple[str, ...]
    state_sha256: str
    authority_inherited: bool
    external_effect_performed: bool
    receipt_sha256: str


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class TasteMemory:
    """Deterministic, evidence-weighted owner taste memory.

    Recent evidence decays less than older evidence. Synthetic observations are
    allowed for tests but never contribute to a promoted preference. Conflicting
    evidence is preserved in the preference receipt instead of being erased.
    This component performs no provider action and cannot grant authority.
    """

    def __init__(self, owner_scope: str, *, decay: float = 0.9) -> None:
        owner_scope = owner_scope.strip()
        if not owner_scope:
            raise TasteError("owner_scope is required")
        if not 0.0 < decay <= 1.0:
            raise TasteError("decay must be greater than 0 and at most 1")
        self.owner_scope = owner_scope
        self.decay = decay
        self._observations: dict[str, TasteObservation] = {}

    def observe(self, observation: TasteObservation) -> None:
        if observation.observation_id in self._observations:
            raise TasteError(f"duplicate observation_id: {observation.observation_id}")
        self._observations[observation.observation_id] = observation

    def observe_many(self, observations: Iterable[TasteObservation]) -> None:
        for observation in observations:
            self.observe(observation)

    def observations(self) -> tuple[TasteObservation, ...]:
        return tuple(
            sorted(self._observations.values(), key=lambda item: (item.sequence, item.observation_id))
        )

    def preference(self, dimension: str, *, as_of_sequence: int | None = None) -> TastePreference | None:
        dimension = dimension.strip()
        if not dimension:
            raise TasteError("dimension is required")
        eligible = [
            item
            for item in self.observations()
            if item.dimension == dimension and not item.synthetic
        ]
        if not eligible:
            return None
        horizon = max(item.sequence for item in eligible) if as_of_sequence is None else as_of_sequence
        if horizon < max(item.sequence for item in eligible):
            raise TasteError("as_of_sequence cannot precede observed evidence")
        scores: dict[str, float] = {}
        ids: dict[str, list[str]] = {}
        for item in eligible:
            score = item.evidence_weight * (self.decay ** (horizon - item.sequence))
            scores[item.value] = scores.get(item.value, 0.0) + score
            ids.setdefault(item.value, []).append(item.observation_id)
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        winner, winner_score = ranked[0]
        total = sum(scores.values())
        conflicts = tuple(
            sorted(obs_id for value, value_ids in ids.items() if value != winner for obs_id in value_ids)
        )
        return TastePreference(
            dimension=dimension,
            value=winner,
            confidence=0.0 if total == 0 else round(winner_score / total, 12),
            supporting_observation_ids=tuple(sorted(ids[winner])),
            conflicting_observation_ids=conflicts,
        )

    def preferences(self) -> tuple[TastePreference, ...]:
        dimensions = sorted(
            {item.dimension for item in self.observations() if not item.synthetic}
        )
        return tuple(
            preference
            for dimension in dimensions
            if (preference := self.preference(dimension)) is not None
        )

    def state_record(self) -> dict[str, object]:
        return {
            "schema": "SOVARA_SC_TASTE_STATE_V1",
            "owner_scope": self.owner_scope,
            "decay": self.decay,
            "observations": [
                {
                    "observation_id": item.observation_id,
                    "dimension": item.dimension,
                    "value": item.value,
                    "evidence_weight": item.evidence_weight,
                    "sequence": item.sequence,
                    "source": item.source,
                    "synthetic": item.synthetic,
                }
                for item in self.observations()
            ],
        }

    def receipt(self) -> TasteReceipt:
        state = self.state_record()
        state_sha = sha256(_stable_json(state).encode("utf-8")).hexdigest()
        preferences = self.preferences()
        base = {
            "schema": "SOVARA_SC_TASTE_RECEIPT_V1",
            "owner_scope": self.owner_scope,
            "preference_count": len(preferences),
            "conflict_count": sum(bool(item.conflicting_observation_ids) for item in preferences),
            "observation_ids": [item.observation_id for item in self.observations()],
            "state_sha256": state_sha,
            "authority_inherited": False,
            "external_effect_performed": False,
        }
        return TasteReceipt(
            schema=base["schema"],
            owner_scope=self.owner_scope,
            preference_count=base["preference_count"],
            conflict_count=base["conflict_count"],
            observation_ids=tuple(base["observation_ids"]),
            state_sha256=state_sha,
            authority_inherited=False,
            external_effect_performed=False,
            receipt_sha256=sha256(_stable_json(base).encode("utf-8")).hexdigest(),
        )
