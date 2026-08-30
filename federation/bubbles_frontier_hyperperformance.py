from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from typing import Iterable, Sequence


_HEX = frozenset("0123456789abcdef")


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _require_sha256(value: str, label: str) -> str:
    normalized = str(value).strip().lower()
    if len(normalized) != 64 or any(ch not in _HEX for ch in normalized):
        raise ValueError(f"{label}_SHA256_REQUIRED")
    return normalized


def _aware_datetime(value: str, label: str) -> datetime:
    normalized = str(value).strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{label}_ISO8601_REQUIRED") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label}_TIMEZONE_REQUIRED")
    return parsed


@dataclass(frozen=True, slots=True)
class WorkCell:
    """One bounded work cell with explicit correlated failure domains."""

    cell_id: str
    failure_domains: tuple[str, ...]
    capacity: int = 1
    active: bool = True

    def validate(self) -> None:
        if not self.cell_id.strip():
            raise ValueError("WORK_CELL_ID_REQUIRED")
        domains = tuple(item.strip() for item in self.failure_domains if item.strip())
        if not domains or len(set(domains)) != len(domains):
            raise ValueError("WORK_CELL_FAILURE_DOMAINS_INVALID")
        if self.capacity <= 0:
            raise ValueError("WORK_CELL_CAPACITY_INVALID")


@dataclass(frozen=True, slots=True)
class CellAllocationDecision:
    state: str
    work_id: str
    selected_cell_ids: tuple[str, ...]
    candidate_cell_ids: tuple[str, ...]
    excluded_cell_ids: tuple[str, ...]
    allocation_digest: str
    reason: str = ""


class WorkCellAllocator:
    """Deterministic cell/shuffle-shard allocation without execution authority.

    The allocator uses rendezvous-style hashing to choose a bounded set of cells.
    It can exclude unhealthy/correlated failure domains and, by default, refuses
    to place one work item into cells sharing any failure domain.
    """

    @staticmethod
    def _score(work_id: str, cell_id: str) -> str:
        return sha256(f"{work_id}\x1f{cell_id}".encode("utf-8")).hexdigest()

    def allocate(
        self,
        work_id: str,
        cells: Sequence[WorkCell],
        *,
        shard_width: int = 1,
        excluded_failure_domains: Iterable[str] = (),
        require_distinct_failure_domains: bool = True,
    ) -> CellAllocationDecision:
        if not work_id.strip():
            raise ValueError("WORK_ID_REQUIRED")
        if shard_width <= 0:
            raise ValueError("SHARD_WIDTH_INVALID")
        if not cells:
            raise ValueError("WORK_CELLS_REQUIRED")

        seen: set[str] = set()
        for cell in cells:
            cell.validate()
            if cell.cell_id in seen:
                raise ValueError("WORK_CELL_IDS_MUST_BE_UNIQUE")
            seen.add(cell.cell_id)

        excluded_domains = {item.strip() for item in excluded_failure_domains if item.strip()}
        eligible: list[WorkCell] = []
        excluded_ids: list[str] = []
        for cell in cells:
            domains = set(cell.failure_domains)
            if not cell.active or domains & excluded_domains:
                excluded_ids.append(cell.cell_id)
                continue
            eligible.append(cell)

        ranked = sorted(
            eligible,
            key=lambda cell: (self._score(work_id, cell.cell_id), cell.cell_id),
            reverse=True,
        )
        selected: list[WorkCell] = []
        occupied_domains: set[str] = set()
        for cell in ranked:
            if require_distinct_failure_domains and occupied_domains & set(cell.failure_domains):
                continue
            selected.append(cell)
            occupied_domains.update(cell.failure_domains)
            if len(selected) == shard_width:
                break

        candidate_ids = tuple(cell.cell_id for cell in ranked)
        selected_ids = tuple(cell.cell_id for cell in selected)
        body = {
            "work_id": work_id,
            "shard_width": shard_width,
            "require_distinct_failure_domains": require_distinct_failure_domains,
            "excluded_failure_domains": sorted(excluded_domains),
            "candidate_cell_ids": candidate_ids,
            "selected_cell_ids": selected_ids,
        }
        if len(selected) < shard_width:
            return CellAllocationDecision(
                state="HOLD_INSUFFICIENT_FAILURE_DOMAIN_DIVERSITY",
                work_id=work_id,
                selected_cell_ids=selected_ids,
                candidate_cell_ids=candidate_ids,
                excluded_cell_ids=tuple(sorted(excluded_ids)),
                allocation_digest=_digest(body),
                reason="Requested shard width cannot be satisfied without violating current cell/failure-domain constraints.",
            )
        return CellAllocationDecision(
            state="ALLOCATED",
            work_id=work_id,
            selected_cell_ids=selected_ids,
            candidate_cell_ids=candidate_ids,
            excluded_cell_ids=tuple(sorted(excluded_ids)),
            allocation_digest=_digest(body),
            reason="Deterministic bounded allocation only; provider/effect authority remains external.",
        )


@dataclass(frozen=True, slots=True)
class DeterministicAction:
    """Identity contract for effect-free work that may be safely reused."""

    action: str
    source_sha256: str
    input_sha256: str
    environment_sha256: str
    proof_scope: str
    fresh_until: str
    effect_class: str = "NO_EFFECT"

    def validate(self, *, now: str) -> None:
        if not self.action.strip() or not self.proof_scope.strip():
            raise ValueError("DETERMINISTIC_ACTION_IDENTITY_REQUIRED")
        _require_sha256(self.source_sha256, "SOURCE")
        _require_sha256(self.input_sha256, "INPUT")
        _require_sha256(self.environment_sha256, "ENVIRONMENT")
        if self.effect_class != "NO_EFFECT":
            raise ValueError("DETERMINISTIC_CACHE_EFFECT_CLASS_PROHIBITED")
        if _aware_datetime(now, "CACHE_NOW") >= _aware_datetime(self.fresh_until, "CACHE_FRESH_UNTIL"):
            raise ValueError("DETERMINISTIC_ACTION_FRESHNESS_EXPIRED")

    def cache_key(self) -> str:
        return _digest(
            {
                "action": self.action,
                "source_sha256": _require_sha256(self.source_sha256, "SOURCE"),
                "input_sha256": _require_sha256(self.input_sha256, "INPUT"),
                "environment_sha256": _require_sha256(self.environment_sha256, "ENVIRONMENT"),
                "proof_scope": self.proof_scope,
                "effect_class": self.effect_class,
            }
        )


@dataclass(frozen=True, slots=True)
class CachedResult:
    cache_key: str
    result_ref: str
    result_sha256: str
    proof_refs: tuple[str, ...]
    recorded_at: str


@dataclass(frozen=True, slots=True)
class CacheDecision:
    state: str
    cache_key: str
    reuse: bool
    result_ref: str = ""
    result_sha256: str = ""
    proof_refs: tuple[str, ...] = ()
    reason: str = ""


class DeterministicResultCache:
    """In-process content-addressed reuse index for deterministic NO_EFFECT work.

    This is not a durable cache, provider cache or execution authority. Callers
    must supply source/input/environment digests and a freshness window.
    """

    def __init__(self) -> None:
        self._results: dict[str, CachedResult] = {}

    def lookup(self, action: DeterministicAction, *, now: str) -> CacheDecision:
        action.validate(now=now)
        key = action.cache_key()
        result = self._results.get(key)
        if result is None:
            return CacheDecision("MISS", key, False, reason="No equivalent verified deterministic result is indexed.")
        if not result.proof_refs:
            return CacheDecision("HOLD_MISSING_PROOF", key, False, reason="Indexed result lacks proof references.")
        return CacheDecision(
            "HIT",
            key,
            True,
            result_ref=result.result_ref,
            result_sha256=result.result_sha256,
            proof_refs=result.proof_refs,
            reason="Exact source/input/environment/proof-scope identity matched; no new effect is authorized.",
        )

    def record(
        self,
        action: DeterministicAction,
        *,
        result_ref: str,
        result_sha256: str,
        proof_refs: Iterable[str],
        recorded_at: str,
        now: str,
    ) -> CacheDecision:
        action.validate(now=now)
        if not result_ref.strip():
            raise ValueError("CACHE_RESULT_REF_REQUIRED")
        digest = _require_sha256(result_sha256, "CACHE_RESULT")
        refs = tuple(sorted({item.strip() for item in proof_refs if item.strip()}))
        if not refs:
            raise ValueError("CACHE_PROOF_REFS_REQUIRED")
        _aware_datetime(recorded_at, "CACHE_RECORDED_AT")
        key = action.cache_key()
        candidate = CachedResult(key, result_ref, digest, refs, recorded_at)
        existing = self._results.get(key)
        if existing is not None and existing != candidate:
            raise ValueError("CACHE_RESULT_CONFLICT")
        self._results[key] = candidate
        return CacheDecision(
            "RECORDED" if existing is None else "IDEMPOTENT_RECORD",
            key,
            True,
            result_ref=result_ref,
            result_sha256=digest,
            proof_refs=refs,
            reason="Immutable deterministic result indexed for equivalent future NO_EFFECT work.",
        )


@dataclass(frozen=True, slots=True)
class ReliabilityBudget:
    slo_success_ratio: float
    observations: int
    failures: int
    min_observations: int = 20
    max_burn_fraction_for_promotion: float = 0.25

    def validate(self) -> None:
        if not 0.0 < self.slo_success_ratio < 1.0:
            raise ValueError("SLO_SUCCESS_RATIO_MUST_BE_BETWEEN_ZERO_AND_ONE")
        if self.observations < 0 or self.failures < 0 or self.failures > self.observations:
            raise ValueError("RELIABILITY_OBSERVATION_COUNTS_INVALID")
        if self.min_observations <= 0:
            raise ValueError("RELIABILITY_MIN_OBSERVATIONS_INVALID")
        if not 0.0 < self.max_burn_fraction_for_promotion <= 1.0:
            raise ValueError("RELIABILITY_PROMOTION_BURN_THRESHOLD_INVALID")


@dataclass(frozen=True, slots=True)
class ReliabilityBudgetDecision:
    state: str
    promote: bool
    allowed_failure_ratio: float
    observed_failure_ratio: float
    burn_fraction: float
    remaining_failure_ratio: float
    reason: str


class ReliabilityBudgetGovernor:
    """Deterministic promotion court for reliability-budget evidence windows.

    The governor consumes measurements supplied by the caller. It does not create
    production telemetry or certify an SLO merely because the arithmetic passes.
    """

    def evaluate(self, budget: ReliabilityBudget) -> ReliabilityBudgetDecision:
        budget.validate()
        allowed = 1.0 - budget.slo_success_ratio
        observed = (budget.failures / budget.observations) if budget.observations else 0.0
        burn = observed / allowed
        remaining = max(0.0, allowed - observed)
        if budget.observations < budget.min_observations:
            return ReliabilityBudgetDecision(
                "HOLD_INSUFFICIENT_DATA",
                False,
                allowed,
                observed,
                burn,
                remaining,
                "Observation window is below the preregistered minimum; promotion is held.",
            )
        if burn > budget.max_burn_fraction_for_promotion:
            return ReliabilityBudgetDecision(
                "HOLD_ERROR_BUDGET_BURN",
                False,
                allowed,
                observed,
                burn,
                remaining,
                "Observed failure burn exceeds the promotion threshold; retain incumbent/rollback path.",
            )
        return ReliabilityBudgetDecision(
            "PROMOTION_ELIGIBLE_RELIABILITY_ONLY",
            True,
            allowed,
            observed,
            burn,
            remaining,
            "Reliability arithmetic permits promotion; authority, proof, value and regression gates remain separate.",
        )
