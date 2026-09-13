from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, Sequence


def _canon(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def _sha(value) -> str:
    return hashlib.sha256(_canon(value)).hexdigest()


def _clean(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


@dataclass(frozen=True, slots=True)
class ContextCandidate:
    candidate_id: str
    source_class: str
    source_ref: str
    revision: str
    token_cost: int
    relevance: float
    uniqueness: float
    proof_strength: float
    freshness: float
    authority_class: str = "A0_READ"
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.candidate_id.strip() or not self.source_class.strip() or not self.source_ref.strip():
            raise ValueError("CONTEXT_IDENTITY_REQUIRED")
        if self.token_cost < 0:
            raise ValueError("NEGATIVE_CONTEXT_COST")
        for name in ("relevance", "uniqueness", "proof_strength", "freshness"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name.upper()}_OUTSIDE_UNIT_INTERVAL")
        if self.authority_class not in {"A0_READ", "A1_INTERNAL"}:
            raise ValueError("CONTEXT_AUTHORITY_ABOVE_READ_INTERNAL")
        if self.proof_strength > 0.0 and not self.evidence_refs:
            raise ValueError("PROVEN_CONTEXT_REQUIRES_EVIDENCE")


@dataclass(frozen=True, slots=True)
class ContextSelection:
    selected_ids: tuple[str, ...]
    total_tokens: int
    budget_tokens: int
    estimated_value: float
    rejected_ids: tuple[str, ...]
    selection_sha256: str


class ContextTournament:
    """Budgeted, provenance-aware context selection without external effects.

    This class does not fetch provider data or mutate repositories. It ranks already
    materialised candidate context records and selects a bounded portfolio. Richer
    retrievers (RepoGraph, semantic, Git history, issues, traces, skills) remain
    upstream providers; this tournament is the common selection contract.
    """

    @staticmethod
    def _score(candidate: ContextCandidate) -> float:
        candidate.validate()
        quality = (
            0.45 * candidate.relevance
            + 0.20 * candidate.uniqueness
            + 0.20 * candidate.proof_strength
            + 0.15 * candidate.freshness
        )
        # Zero-token structural metadata remains useful but receives no infinite
        # efficiency advantage. The 256-token floor keeps the score bounded.
        efficiency = quality / max(candidate.token_cost, 256)
        return round(efficiency, 12)

    def select(
        self,
        candidates: Sequence[ContextCandidate],
        *,
        token_budget: int,
        mandatory_ids: Iterable[str] = (),
        max_items: int = 16,
    ) -> ContextSelection:
        if token_budget < 0:
            raise ValueError("NEGATIVE_CONTEXT_BUDGET")
        if max_items < 1:
            raise ValueError("MAX_ITEMS_MUST_BE_POSITIVE")
        by_id: dict[str, ContextCandidate] = {}
        for candidate in candidates:
            candidate.validate()
            if candidate.candidate_id in by_id:
                raise ValueError("DUPLICATE_CONTEXT_CANDIDATE")
            by_id[candidate.candidate_id] = candidate

        required = _clean(mandatory_ids)
        missing = tuple(sorted(set(required) - set(by_id)))
        if missing:
            raise ValueError(f"MANDATORY_CONTEXT_MISSING:{','.join(missing)}")
        if len(required) > max_items:
            raise ValueError("MANDATORY_CONTEXT_EXCEEDS_ITEM_LIMIT")

        selected: list[ContextCandidate] = []
        used = 0
        for candidate_id in required:
            candidate = by_id[candidate_id]
            if used + candidate.token_cost > token_budget:
                raise ValueError("MANDATORY_CONTEXT_EXCEEDS_BUDGET")
            selected.append(candidate)
            used += candidate.token_cost

        optional = [c for c in candidates if c.candidate_id not in set(required)]
        optional.sort(key=lambda c: (-self._score(c), -c.relevance, c.token_cost, c.candidate_id))
        selected_ids = {c.candidate_id for c in selected}
        for candidate in optional:
            if len(selected) >= max_items:
                break
            if used + candidate.token_cost > token_budget:
                continue
            selected.append(candidate)
            selected_ids.add(candidate.candidate_id)
            used += candidate.token_cost

        selected_tuple = tuple(sorted(selected_ids))
        rejected = tuple(sorted(set(by_id) - set(selected_tuple)))
        estimated = round(sum(self._score(by_id[cid]) * max(by_id[cid].token_cost, 256) for cid in selected_tuple), 8)
        body = {
            "selected": selected_tuple,
            "rejected": rejected,
            "total_tokens": used,
            "budget_tokens": token_budget,
            "estimated_value": estimated,
            "candidate_fingerprints": tuple(
                sorted(
                    (
                        cid,
                        by_id[cid].source_class,
                        by_id[cid].source_ref,
                        by_id[cid].revision,
                        by_id[cid].token_cost,
                        by_id[cid].evidence_refs,
                    )
                    for cid in by_id
                )
            ),
        }
        return ContextSelection(
            selected_ids=selected_tuple,
            total_tokens=used,
            budget_tokens=token_budget,
            estimated_value=estimated,
            rejected_ids=rejected,
            selection_sha256=_sha(body),
        )


@dataclass(frozen=True, slots=True)
class ContextOutcome:
    policy_id: str
    task_set_id: str
    acceptance_hash: str
    sample_size: int
    accepted_task_rate: float
    verified_readback_rate: float
    regression_escape_rate: float
    median_context_tokens: float
    median_wall_seconds: float
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        if not self.policy_id or not self.task_set_id or not self.acceptance_hash:
            raise ValueError("CONTEXT_OUTCOME_IDENTITY_REQUIRED")
        if self.sample_size < 1 or self.median_context_tokens < 0 or self.median_wall_seconds <= 0:
            raise ValueError("CONTEXT_OUTCOME_METRICS_INVALID")
        for name in ("accepted_task_rate", "verified_readback_rate", "regression_escape_rate"):
            if not 0.0 <= float(getattr(self, name)) <= 1.0:
                raise ValueError(f"{name.upper()}_OUTSIDE_UNIT_INTERVAL")
        if not self.evidence_refs:
            raise ValueError("CONTEXT_OUTCOME_EVIDENCE_REQUIRED")


@dataclass(frozen=True, slots=True)
class ContextPolicyVerdict:
    winner: str | None
    comparable: bool
    reason: str
    quality_regression: bool
    token_reduction_ratio: float
    velocity_ratio: float


class ContextPolicyCourt:
    """Matched-task Pareto comparison; efficiency cannot compensate for quality regression."""

    @staticmethod
    def _ratio(incumbent: float, challenger: float) -> float:
        if challenger == 0:
            return float("inf") if incumbent > 0 else 1.0
        return incumbent / challenger

    def compare(self, incumbent: ContextOutcome, challenger: ContextOutcome) -> ContextPolicyVerdict:
        incumbent.validate()
        challenger.validate()
        comparable = (
            incumbent.task_set_id == challenger.task_set_id
            and incumbent.acceptance_hash == challenger.acceptance_hash
        )
        if not comparable:
            return ContextPolicyVerdict(None, False, "EXPERIMENT_IDENTITY_MISMATCH", False, 0.0, 0.0)
        quality_regression = (
            challenger.accepted_task_rate < incumbent.accepted_task_rate
            or challenger.verified_readback_rate < incumbent.verified_readback_rate
            or challenger.regression_escape_rate > incumbent.regression_escape_rate
        )
        token_ratio = self._ratio(incumbent.median_context_tokens, challenger.median_context_tokens)
        velocity_ratio = incumbent.median_wall_seconds / challenger.median_wall_seconds
        if quality_regression:
            return ContextPolicyVerdict(incumbent.policy_id, True, "QUALITY_OR_READBACK_REGRESSION", True, token_ratio, velocity_ratio)
        if challenger.sample_size < 10 or incumbent.sample_size < 10:
            return ContextPolicyVerdict(None, True, "INSUFFICIENT_PAIRED_SAMPLE", False, token_ratio, velocity_ratio)

        challenger_no_worse = (
            challenger.median_context_tokens <= incumbent.median_context_tokens
            and challenger.median_wall_seconds <= incumbent.median_wall_seconds
        )
        challenger_strictly_better = (
            challenger.median_context_tokens < incumbent.median_context_tokens
            or challenger.median_wall_seconds < incumbent.median_wall_seconds
        )
        incumbent_no_worse = (
            incumbent.median_context_tokens <= challenger.median_context_tokens
            and incumbent.median_wall_seconds <= challenger.median_wall_seconds
        )
        incumbent_strictly_better = (
            incumbent.median_context_tokens < challenger.median_context_tokens
            or incumbent.median_wall_seconds < challenger.median_wall_seconds
        )
        if challenger_no_worse and challenger_strictly_better:
            return ContextPolicyVerdict(challenger.policy_id, True, "CHALLENGER_ADVANCES", False, token_ratio, velocity_ratio)
        if incumbent_no_worse and incumbent_strictly_better:
            return ContextPolicyVerdict(incumbent.policy_id, True, "KEEP_INCUMBENT", False, token_ratio, velocity_ratio)
        if (
            challenger.median_context_tokens == incumbent.median_context_tokens
            and challenger.median_wall_seconds == incumbent.median_wall_seconds
        ):
            return ContextPolicyVerdict(incumbent.policy_id, True, "KEEP_INCUMBENT_NO_MATERIAL_GAIN", False, token_ratio, velocity_ratio)
        return ContextPolicyVerdict(None, True, "PARETO_TRADEOFF", False, token_ratio, velocity_ratio)


__all__ = [
    "ContextCandidate",
    "ContextOutcome",
    "ContextPolicyCourt",
    "ContextPolicyVerdict",
    "ContextSelection",
    "ContextTournament",
]
