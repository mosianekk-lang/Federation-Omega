"""Capability inventory, provenance and reuse-first ranking.

This module adapts Federation registry and deduplication patterns without
importing or claiming a live binding to the Federation runtime.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import IntEnum
from typing import Any, Iterable

from .schema import InputError


class CapabilityState(IntEnum):
    DISCOVERED = 0
    SOURCE_PRESENT = 1
    REFERENCE_OPERATIONAL = 2
    TESTED_LOCAL = 3
    VERIFIED_SCOPED = 4
    LIVE_BOUND = 5


AUTHORITY_RANK = {"A0": 0, "A1": 1, "A2": 2, "A3": 3, "A4": 4, "A5": 5}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class Capability:
    capability_id: str
    name: str
    provides: tuple[str, ...]
    state: CapabilityState
    current: bool
    authority_ceiling: str
    recurring_cost: float = 0
    user_burden: int = 0
    external_effect_required: bool = False
    source_ref: str = ""
    source_hash: str = ""
    system_id: str = ""
    supersedes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def semantic_fingerprint(self) -> str:
        payload = {
            "provides": sorted(self.provides),
            "external_effect_required": self.external_effect_required,
        }
        return hashlib.sha256(canonical_json(payload).encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["state"] = self.state.name
        return value


@dataclass(frozen=True)
class CapabilitySelection:
    selected: tuple[Capability, ...]
    suppressed_duplicates: tuple[str, ...]
    covered: tuple[str, ...]
    gaps: tuple[str, ...]
    rejected: tuple[dict[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected": [item.to_dict() for item in self.selected],
            "suppressed_duplicates": list(self.suppressed_duplicates),
            "covered": list(self.covered),
            "gaps": list(self.gaps),
            "rejected": list(self.rejected),
        }


class CapabilityRegistry:
    """A deterministic read-only registry for one routing decision."""

    def __init__(self, capabilities: Iterable[Capability]):
        self.capabilities = tuple(capabilities)

    @classmethod
    def from_dict(cls, payload: Any) -> "CapabilityRegistry":
        if not isinstance(payload, dict) or not isinstance(payload.get("capabilities"), list):
            raise InputError("capability manifest must contain a capabilities array")
        parsed: list[Capability] = []
        seen_ids: set[str] = set()
        for index, item in enumerate(payload["capabilities"]):
            if not isinstance(item, dict):
                raise InputError(f"capabilities[{index}] must be an object")
            try:
                state = CapabilityState[str(item.get("state", "DISCOVERED")).upper()]
            except KeyError as exc:
                raise InputError(f"capabilities[{index}].state is invalid") from exc
            provides = item.get("provides")
            if not isinstance(provides, list) or not provides or not all(isinstance(v, str) and v.strip() for v in provides):
                raise InputError(f"capabilities[{index}].provides must be a non-empty string array")
            capability_id = str(item.get("capability_id", "")).strip()
            if not capability_id:
                raise InputError(f"capabilities[{index}].capability_id is required")
            if capability_id in seen_ids:
                raise InputError(f"capabilities[{index}].capability_id is duplicated")
            seen_ids.add(capability_id)
            authority = str(item.get("authority_ceiling", "A0")).upper()
            if authority not in AUTHORITY_RANK:
                raise InputError(f"capabilities[{index}].authority_ceiling is invalid")
            parsed.append(Capability(
                capability_id=capability_id,
                name=str(item.get("name", capability_id)).strip() or capability_id,
                provides=tuple(sorted(set(v.strip() for v in provides))),
                state=state,
                current=item.get("current") is True,
                authority_ceiling=authority,
                recurring_cost=float(item.get("recurring_cost", 0)),
                user_burden=int(item.get("user_burden", 0)),
                external_effect_required=item.get("external_effect_required") is True,
                source_ref=str(item.get("source_ref", "")).strip(),
                source_hash=str(item.get("source_hash", "")).strip(),
                system_id=str(item.get("system_id", "")).strip(),
                supersedes=tuple(sorted(set(map(str, item.get("supersedes", []))))),
                metadata=dict(item.get("metadata", {})) if isinstance(item.get("metadata", {}), dict) else {},
            ))
        return cls(parsed)

    def _score(self, item: Capability, required: set[str]) -> tuple[int, int, int, float, str]:
        coverage = len(required.intersection(item.provides))
        return (coverage, int(item.state), -item.user_burden, -item.recurring_cost, item.capability_id)

    def select(
        self,
        required: Iterable[str],
        *,
        available_authority: str = "A2",
        allow_external_effects: bool = False,
        maximum_recurring_cost: float = 0,
    ) -> CapabilitySelection:
        required_set = {str(value).strip() for value in required if str(value).strip()}
        if not required_set:
            raise InputError("required_capabilities must not be empty")
        authority = available_authority.upper()
        if authority not in AUTHORITY_RANK:
            raise InputError("available_authority is invalid")

        rejected: list[dict[str, str]] = []
        eligible: list[Capability] = []
        for item in self.capabilities:
            reason = ""
            if not item.current:
                reason = "STALE_OR_UNVERIFIED"
            elif item.state == CapabilityState.DISCOVERED:
                reason = "DISCOVERY_IS_NOT_USABLE_CAPABILITY"
            elif AUTHORITY_RANK[item.authority_ceiling] > AUTHORITY_RANK[authority]:
                reason = "AUTHORITY_CEILING_EXCEEDS_ROUTE"
            elif item.recurring_cost > maximum_recurring_cost:
                reason = "RECURRING_COST_EXCEEDS_LIMIT"
            elif item.external_effect_required and not allow_external_effects:
                reason = "EXTERNAL_EFFECT_NOT_AUTHORIZED"
            elif not required_set.intersection(item.provides):
                reason = "NO_REQUIRED_CAPABILITY_OVERLAP"
            if reason:
                rejected.append({"capability_id": item.capability_id, "reason": reason})
            else:
                eligible.append(item)

        # A current eligible successor removes explicitly superseded implementations
        # before semantic deduplication. This prevents a legacy route from surviving
        # merely because its capability wording differs slightly.
        eligible_ids = {item.capability_id for item in eligible}
        superseded_ids = {
            old_id
            for item in eligible
            for old_id in item.supersedes
            if old_id in eligible_ids and old_id != item.capability_id
        }
        if superseded_ids:
            eligible = [item for item in eligible if item.capability_id not in superseded_ids]

        # Prefer one canonical implementation for semantically duplicate coverage.
        winners: dict[str, Capability] = {}
        suppressed: list[str] = sorted(superseded_ids)
        for item in eligible:
            key = item.semantic_fingerprint
            incumbent = winners.get(key)
            if incumbent is None or self._score(item, required_set) > self._score(incumbent, required_set):
                if incumbent is not None:
                    suppressed.append(incumbent.capability_id)
                winners[key] = item
            else:
                suppressed.append(item.capability_id)

        candidates = sorted(winners.values(), key=lambda item: self._score(item, required_set), reverse=True)
        selected: list[Capability] = []
        uncovered = set(required_set)
        while uncovered:
            useful = [item for item in candidates if uncovered.intersection(item.provides)]
            if not useful:
                break
            best = max(useful, key=lambda item: self._score(item, uncovered))
            selected.append(best)
            uncovered.difference_update(best.provides)
            candidates.remove(best)
        covered = required_set - uncovered
        return CapabilitySelection(
            selected=tuple(selected),
            suppressed_duplicates=tuple(sorted(set(suppressed))),
            covered=tuple(sorted(covered)),
            gaps=tuple(sorted(uncovered)),
            rejected=tuple(sorted(rejected, key=lambda value: (value["capability_id"], value["reason"]))),
        )
