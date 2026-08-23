from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from .evolution import fitness
from .models import PerformanceVector


_WORD = re.compile(r"[A-Za-z0-9_]+")
_PRIORITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
_CATEGORY_WEIGHT = {
    "OBJECTIVE": 3.0,
    "VERIFIED_FACT": 2.8,
    "DECISION": 2.6,
    "BLOCKER": 2.4,
    "NEXT_ACTION": 2.3,
    "USER_PREFERENCE": 2.2,
    "CODE_DELTA": 1.6,
    "REFERENCE": 0.6,
}


def canonical_sha256(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _normalise_text(text: str) -> str:
    return " ".join(str(text).split()).strip().lower()


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(_normalise_text(text)))


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _excerpt(text: str, limit: int) -> tuple[str, bool]:
    value = str(text)
    if len(value) <= limit:
        return value, False
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    marker = f" …[COMPACTED sha256={digest}]… "
    available = max(0, limit - len(marker))
    head = math.ceil(available * 0.7)
    tail = max(0, available - head)
    omitted = max(0, len(value) - head - tail)
    marker = f" …[COMPACTED sha256={digest} omitted={omitted} chars]… "
    available = max(0, limit - len(marker))
    head = math.ceil(available * 0.7)
    tail = max(0, available - head)
    compacted = value[:head] + marker + (value[-tail:] if tail else "")
    return compacted, True


class CycleOutcome(str, Enum):
    PROMOTE_2X = "PROMOTE_2X"
    PROMOTE_INCREMENTAL = "PROMOTE_INCREMENTAL"
    REBUILD_REQUIRED = "REBUILD_REQUIRED"
    REJECT_INVARIANT = "REJECT_INVARIANT"
    HOLD_NO_GAIN = "HOLD_NO_GAIN"


@dataclass(frozen=True)
class ContextAtom:
    atom_id: str
    text: str
    category: str = "REFERENCE"
    priority: float = 0.5
    freshness: float = 0.5
    pinned: bool = False
    proof_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompactionPolicy:
    max_active_atoms: int = 24
    max_active_chars: int = 12_000
    max_atom_chars: int = 1_800
    near_duplicate_threshold: float = 0.94
    near_duplicate_scan_limit: int = 256
    archive_manifest_limit: int = 256


@dataclass(frozen=True)
class CompactAtom:
    atom_id: str
    text: str
    category: str
    priority: float
    freshness: float
    pinned: bool
    proof_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    content_sha256: str
    source_characters: int
    compacted: bool
    merged_from: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompactionResult:
    active_atoms: tuple[CompactAtom, ...]
    archive_manifest: tuple[dict[str, Any], ...]
    duplicate_groups: tuple[dict[str, Any], ...]
    before_atoms: int
    before_characters: int
    active_characters: int
    compression_ratio: float
    budget_overflow: bool
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ContextCompactor:
    """Build a bounded working set while preserving provenance and hashes.

    This class does not delete or persist the source material. It returns a
    compact active capsule and an archive manifest so the full records can live
    in an external evidence store and be retrieved only when needed.
    """

    def __init__(self, policy: CompactionPolicy | None = None) -> None:
        self.policy = policy or CompactionPolicy()
        if self.policy.max_active_atoms < 1 or self.policy.max_active_chars < 1:
            raise ValueError("compaction budgets must be positive")

    @staticmethod
    def _score(atom: ContextAtom) -> float:
        category = str(atom.category).upper()
        return (
            (100.0 if atom.pinned else 0.0)
            + _CATEGORY_WEIGHT.get(category, 0.5)
            + max(0.0, min(1.0, atom.priority)) * 3.0
            + max(0.0, min(1.0, atom.freshness))
            + min(3, len(atom.proof_refs)) * 0.4
        )

    def compact(self, atoms: Iterable[ContextAtom]) -> CompactionResult:
        original = tuple(atoms)
        before_chars = sum(len(str(item.text)) for item in original)
        ranked = sorted(
            original,
            key=lambda item: (-self._score(item), item.atom_id),
        )

        canonical: list[dict[str, Any]] = []
        archive: list[dict[str, Any]] = []
        duplicate_groups: list[dict[str, Any]] = []
        exact_index: dict[tuple[str, str], int] = {}

        for atom in ranked:
            category = str(atom.category).upper()
            normalised = _normalise_text(atom.text)
            digest = hashlib.sha256(normalised.encode("utf-8")).hexdigest()
            exact_key = (category, digest)
            duplicate_index = exact_index.get(exact_key)

            if duplicate_index is None and len(canonical) <= self.policy.near_duplicate_scan_limit:
                atom_tokens = _tokens(atom.text)
                if len(atom_tokens) >= 8:
                    for index, candidate in enumerate(canonical):
                        if candidate["category"] != category:
                            continue
                        if _jaccard(atom_tokens, candidate["tokens"]) >= self.policy.near_duplicate_threshold:
                            duplicate_index = index
                            break

            if duplicate_index is not None:
                target = canonical[duplicate_index]
                target["proof_refs"].update(atom.proof_refs)
                target["source_refs"].update(atom.source_refs)
                target["merged_from"].append(atom.atom_id)
                target["pinned"] = target["pinned"] or atom.pinned
                target["priority"] = max(target["priority"], atom.priority)
                target["freshness"] = max(target["freshness"], atom.freshness)
                archive.append(
                    {
                        "atom_id": atom.atom_id,
                        "content_sha256": hashlib.sha256(str(atom.text).encode("utf-8")).hexdigest(),
                        "reason": "DUPLICATE",
                        "canonical_atom_id": target["atom_id"],
                    }
                )
                continue

            exact_index[exact_key] = len(canonical)
            canonical.append(
                {
                    "atom_id": atom.atom_id,
                    "text": str(atom.text),
                    "category": category,
                    "priority": atom.priority,
                    "freshness": atom.freshness,
                    "pinned": atom.pinned,
                    "proof_refs": set(atom.proof_refs),
                    "source_refs": set(atom.source_refs),
                    "merged_from": [],
                    "tokens": _tokens(atom.text),
                    "score": self._score(atom),
                }
            )

        active: list[CompactAtom] = []
        active_chars = 0
        for item in sorted(canonical, key=lambda value: (-value["score"], value["atom_id"])):
            text, was_compacted = _excerpt(item["text"], self.policy.max_atom_chars)
            projected_chars = active_chars + len(text)
            within_count = len(active) < self.policy.max_active_atoms
            within_chars = projected_chars <= self.policy.max_active_chars

            if not item["pinned"] and (not within_count or not within_chars):
                archive.append(
                    {
                        "atom_id": item["atom_id"],
                        "content_sha256": hashlib.sha256(item["text"].encode("utf-8")).hexdigest(),
                        "reason": "WORKING_SET_BUDGET",
                        "category": item["category"],
                    }
                )
                continue

            active.append(
                CompactAtom(
                    atom_id=item["atom_id"],
                    text=text,
                    category=item["category"],
                    priority=float(item["priority"]),
                    freshness=float(item["freshness"]),
                    pinned=bool(item["pinned"]),
                    proof_refs=tuple(sorted(item["proof_refs"])),
                    source_refs=tuple(sorted(item["source_refs"])),
                    content_sha256=hashlib.sha256(item["text"].encode("utf-8")).hexdigest(),
                    source_characters=len(item["text"]),
                    compacted=was_compacted,
                    merged_from=tuple(sorted(item["merged_from"])),
                )
            )
            active_chars += len(text)

        for item in canonical:
            if item["merged_from"]:
                duplicate_groups.append(
                    {
                        "canonical_atom_id": item["atom_id"],
                        "merged_atom_ids": tuple(sorted(item["merged_from"])),
                    }
                )

        archive = archive[: self.policy.archive_manifest_limit]
        overflow = (
            len(active) > self.policy.max_active_atoms
            or active_chars > self.policy.max_active_chars
        )
        ratio = before_chars / max(active_chars, 1)
        unsigned = {
            "active": [asdict(item) for item in active],
            "archive": archive,
            "duplicate_groups": duplicate_groups,
            "before_atoms": len(original),
            "before_characters": before_chars,
            "active_characters": active_chars,
            "budget_overflow": overflow,
        }
        return CompactionResult(
            active_atoms=tuple(active),
            archive_manifest=tuple(archive),
            duplicate_groups=tuple(duplicate_groups),
            before_atoms=len(original),
            before_characters=before_chars,
            active_characters=active_chars,
            compression_ratio=ratio,
            budget_overflow=overflow,
            receipt_sha256=canonical_sha256(unsigned),
        )


@dataclass(frozen=True)
class EffortRecord:
    attempted_routes: tuple[str, ...] = ()
    self_tests: tuple[tuple[str, bool], ...] = ()
    critical_blockers: tuple[str, ...] = ()
    fallback_routes: tuple[str, ...] = ()
    owner_only_gates: tuple[str, ...] = ()
    prework_complete: bool = False
    premature_stop: bool = False


@dataclass(frozen=True)
class BestEffortAssessment:
    complete: bool
    status: str
    issues: tuple[str, ...]
    attempted_routes: tuple[str, ...]
    passed_tests: tuple[str, ...]
    failed_tests: tuple[str, ...]


class BestEffortGovernor:
    def assess(self, *, objective: str, effort: EffortRecord) -> BestEffortAssessment:
        issues: list[str] = []
        if not str(objective).strip():
            issues.append("OBJECTIVE_MISSING")
        if not effort.attempted_routes:
            issues.append("NO_EXECUTION_ROUTE_ATTEMPTED")
        if effort.premature_stop:
            issues.append("PREMATURE_STOP")
        if not effort.self_tests:
            issues.append("SELF_TEST_MISSING")

        passed = tuple(name for name, result in effort.self_tests if result)
        failed = tuple(name for name, result in effort.self_tests if not result)
        if failed:
            issues.append("SELF_TEST_FAILURE")

        unresolved = set(effort.critical_blockers)
        owner_only = set(effort.owner_only_gates)
        if unresolved:
            if effort.fallback_routes:
                pass
            elif unresolved.issubset(owner_only) and effort.prework_complete:
                pass
            else:
                issues.append("CRITICAL_BLOCKER_WITHOUT_FALLBACK")

        complete = not issues
        status = (
            "BEST_EFFORT_AT_OWNER_GATE"
            if complete and unresolved and unresolved.issubset(owner_only)
            else "BEST_EFFORT_COMPLETE"
            if complete
            else "BEST_EFFORT_INCOMPLETE"
        )
        return BestEffortAssessment(
            complete=complete,
            status=status,
            issues=tuple(issues),
            attempted_routes=tuple(dict.fromkeys(effort.attempted_routes)),
            passed_tests=passed,
            failed_tests=failed,
        )


@dataclass(frozen=True)
class CodeUnit:
    component_id: str
    lines_of_code: int = 0
    complexity: float = 0.0
    duplication_ratio: float = 0.0
    change_frequency: float = 0.0
    test_confidence: float = 0.0
    context_weight: float = 0.0
    unique_function: bool = True


@dataclass(frozen=True)
class RestructureAction:
    component_id: str
    action: str
    priority: str
    reason: str
    expected_context_reduction: float
    preserves_behavior: bool = True


class CodeRestructuringPlanner:
    """Recommend rebuilds that reduce complexity instead of adding layers."""

    def plan(self, units: Iterable[CodeUnit]) -> tuple[RestructureAction, ...]:
        actions: list[RestructureAction] = []
        for unit in units:
            if unit.duplication_ratio >= 0.75 and not unit.unique_function:
                actions.append(
                    RestructureAction(
                        component_id=unit.component_id,
                        action="MERGE_DUPLICATE_IMPLEMENTATIONS",
                        priority="CRITICAL",
                        reason="high overlap without a unique function",
                        expected_context_reduction=min(0.9, unit.duplication_ratio),
                    )
                )
            if unit.lines_of_code >= 700 or unit.context_weight >= 0.70:
                actions.append(
                    RestructureAction(
                        component_id=unit.component_id,
                        action="EXTRACT_STABLE_MODULE_BOUNDARIES",
                        priority="HIGH",
                        reason="component is too large for the active working set",
                        expected_context_reduction=min(0.75, max(0.25, unit.context_weight)),
                    )
                )
            if unit.complexity >= 25:
                actions.append(
                    RestructureAction(
                        component_id=unit.component_id,
                        action="SPLIT_BY_RESPONSIBILITY",
                        priority="HIGH",
                        reason="complexity exceeds the rebuild threshold",
                        expected_context_reduction=min(0.60, unit.complexity / 100.0),
                    )
                )
            if unit.change_frequency >= 0.60 and unit.test_confidence < 0.70:
                actions.append(
                    RestructureAction(
                        component_id=unit.component_id,
                        action="ADD_CHARACTERIZATION_TESTS_BEFORE_REBUILD",
                        priority="HIGH",
                        reason="hot code lacks sufficient regression protection",
                        expected_context_reduction=0.0,
                    )
                )

        unique: dict[tuple[str, str], RestructureAction] = {}
        for action in actions:
            unique[(action.component_id, action.action)] = action
        return tuple(
            sorted(
                unique.values(),
                key=lambda item: (
                    _PRIORITY_ORDER.get(item.priority, 99),
                    item.component_id,
                    item.action,
                ),
            )
        )


class BoundedDeltaMemory:
    """Keep only recent state deltas and a cryptographic checkpoint."""

    def __init__(self, *, max_records: int = 12, max_delta_characters: int = 4_000) -> None:
        if max_records < 1 or max_delta_characters < 128:
            raise ValueError("invalid bounded-memory limits")
        self.max_records = max_records
        self.max_delta_characters = max_delta_characters
        self._checkpoint_hash = "GENESIS"
        self._records: list[dict[str, Any]] = []
        self._latest: dict[str, Any] = {}
        self._total_commits = 0

    @staticmethod
    def _deep_diff(previous: Any, current: Any) -> Any:
        if isinstance(previous, Mapping) and isinstance(current, Mapping):
            delta: dict[str, Any] = {}
            keys = sorted(set(previous) | set(current))
            for key in keys:
                if key not in current:
                    delta[str(key)] = {"__deleted__": True}
                elif key not in previous:
                    delta[str(key)] = current[key]
                else:
                    child = BoundedDeltaMemory._deep_diff(previous[key], current[key])
                    if child is not None:
                        delta[str(key)] = child
            return delta or None
        return None if previous == current else current

    def commit(self, state: Mapping[str, Any]) -> dict[str, Any]:
        current = json.loads(json.dumps(dict(state), sort_keys=True, default=str))
        state_hash = canonical_sha256(current)
        delta = self._deep_diff(self._latest, current)
        if delta is None:
            return {
                "status": "NO_CHANGE",
                "state_hash": state_hash,
                "retained_records": len(self._records),
                "checkpoint_hash": self._checkpoint_hash,
            }

        delta_text = json.dumps(delta, sort_keys=True, separators=(",", ":"))
        if len(delta_text) > self.max_delta_characters:
            delta = {
                "_compacted": True,
                "changed_top_level_keys": tuple(sorted(delta.keys())),
                "full_state_sha256": state_hash,
                "source_delta_characters": len(delta_text),
            }

        previous_hash = self._records[-1]["record_hash"] if self._records else self._checkpoint_hash
        unsigned = {
            "sequence": self._total_commits + 1,
            "previous_hash": previous_hash,
            "state_hash": state_hash,
            "delta": delta,
        }
        record = {**unsigned, "record_hash": canonical_sha256(unsigned)}
        self._records.append(record)
        self._latest = current
        self._total_commits += 1

        while len(self._records) > self.max_records:
            removed = self._records.pop(0)
            self._checkpoint_hash = removed["record_hash"]
        return record

    def verify(self) -> bool:
        previous_hash = self._checkpoint_hash
        for record in self._records:
            unsigned = {
                "sequence": record["sequence"],
                "previous_hash": record["previous_hash"],
                "state_hash": record["state_hash"],
                "delta": record["delta"],
            }
            if record["previous_hash"] != previous_hash:
                return False
            if canonical_sha256(unsigned) != record["record_hash"]:
                return False
            previous_hash = record["record_hash"]
        return True

    def snapshot(self) -> dict[str, Any]:
        return {
            "checkpoint_hash": self._checkpoint_hash,
            "retained_records": len(self._records),
            "total_commits": self._total_commits,
            "latest_state_hash": canonical_sha256(self._latest),
            "verified": self.verify(),
        }


@dataclass(frozen=True)
class AdaptiveCycleRequest:
    cycle_id: str
    objective: str
    incumbent: PerformanceVector
    candidate: PerformanceVector
    effort: EffortRecord
    context_atoms: tuple[ContextAtom, ...] = ()
    code_units: tuple[CodeUnit, ...] = ()
    invariant_checks: tuple[tuple[str, bool], ...] = ()
    proof_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class AdaptiveCycleResult:
    cycle_id: str
    outcome: CycleOutcome
    baseline_score: float
    candidate_score: float
    target_score: float
    improvement: float
    measured_ratio: float | None
    target_progress: float
    target_met: bool
    promote: bool
    claim_state: str
    best_effort: BestEffortAssessment
    failed_invariants: tuple[str, ...]
    compaction: CompactionResult
    restructure_actions: tuple[RestructureAction, ...]
    next_action: str
    memory_record: dict[str, Any]
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["outcome"] = self.outcome.value
        return value


class AdaptiveCycleEngine:
    """Proof-gated improvement with a 2x target and bounded working memory.

    The 2x figure is a target, not an automatic claim. A candidate may be
    promoted as a truthful incremental improvement when it is fitter and passes
    the invariants; only measured target attainment receives PROMOTE_2X.
    """

    VERSION = "1.0.0"
    TARGET_MULTIPLIER = 2.0

    def __init__(
        self,
        *,
        compactor: ContextCompactor | None = None,
        memory: BoundedDeltaMemory | None = None,
    ) -> None:
        self.compactor = compactor or ContextCompactor()
        self.memory = memory or BoundedDeltaMemory()
        self.effort = BestEffortGovernor()
        self.restructure = CodeRestructuringPlanner()

    @staticmethod
    def _target_score(baseline: float) -> float:
        if baseline > 0:
            return baseline * AdaptiveCycleEngine.TARGET_MULTIPLIER
        return baseline + max(abs(baseline), 1.0)

    def run(self, request: AdaptiveCycleRequest) -> AdaptiveCycleResult:
        baseline = fitness(request.incumbent)
        candidate = fitness(request.candidate)
        target = self._target_score(baseline)
        improvement = candidate - baseline
        required_gain = max(target - baseline, 1e-9)
        target_progress = improvement / required_gain
        measured_ratio = candidate / baseline if baseline > 0 else None
        target_met = candidate >= target

        best_effort = self.effort.assess(objective=request.objective, effort=request.effort)
        failed_invariants = tuple(name for name, passed in request.invariant_checks if not passed)
        compaction = self.compactor.compact(request.context_atoms)
        restructure_actions = self.restructure.plan(request.code_units)

        if failed_invariants:
            outcome = CycleOutcome.REJECT_INVARIANT
            promote = False
            claim = "CANDIDATE_REJECTED_INVARIANT_FAILURE"
            next_action = "REPAIR_FAILED_INVARIANTS_AND_REBUILD"
        elif not best_effort.complete:
            outcome = CycleOutcome.REBUILD_REQUIRED
            promote = False
            claim = "BEST_EFFORT_NOT_YET_PROVEN"
            next_action = "CONTINUE_ROUTE_SEARCH_SELF_TEST_AND_REBUILD"
        elif candidate <= baseline:
            outcome = CycleOutcome.HOLD_NO_GAIN
            promote = False
            claim = "NO_MEASURED_IMPROVEMENT"
            next_action = "RESTRUCTURE_AND_REBUILD_BEFORE_RETRY"
        elif target_met:
            outcome = CycleOutcome.PROMOTE_2X
            promote = True
            claim = "MEASURED_2X_TARGET_MET"
            next_action = "PROMOTE_CANDIDATE_AND_SET_NEXT_BASELINE"
        else:
            outcome = CycleOutcome.PROMOTE_INCREMENTAL
            promote = True
            claim = "MEASURED_IMPROVEMENT_NOT_2X"
            next_action = "PROMOTE_SAFE_DELTA_THEN_GENERATE_NEXT_CANDIDATE"

        memory_state = {
            "cycle_id": request.cycle_id,
            "objective_sha256": hashlib.sha256(request.objective.encode("utf-8")).hexdigest(),
            "outcome": outcome.value,
            "baseline_score": baseline,
            "candidate_score": candidate,
            "target_score": target,
            "target_met": target_met,
            "promote": promote,
            "claim_state": claim,
            "best_effort_status": best_effort.status,
            "failed_invariants": failed_invariants,
            "context_receipt_sha256": compaction.receipt_sha256,
            "restructure_actions": tuple(
                f"{item.component_id}:{item.action}" for item in restructure_actions
            ),
            "proof_refs": tuple(sorted(set(request.proof_refs))),
        }
        memory_record = self.memory.commit(memory_state)
        unsigned = {
            **memory_state,
            "improvement": improvement,
            "measured_ratio": measured_ratio,
            "target_progress": target_progress,
            "next_action": next_action,
            "memory_record_hash": memory_record.get("record_hash", memory_record.get("state_hash")),
        }
        return AdaptiveCycleResult(
            cycle_id=request.cycle_id,
            outcome=outcome,
            baseline_score=baseline,
            candidate_score=candidate,
            target_score=target,
            improvement=improvement,
            measured_ratio=measured_ratio,
            target_progress=target_progress,
            target_met=target_met,
            promote=promote,
            claim_state=claim,
            best_effort=best_effort,
            failed_invariants=failed_invariants,
            compaction=compaction,
            restructure_actions=restructure_actions,
            next_action=next_action,
            memory_record=memory_record,
            receipt_sha256=canonical_sha256(unsigned),
        )
