from __future__ import annotations

"""Leakage-safe real-mission calibration court for the BCΩ-PRIME radar.

The court compiles candidate features from the final scope of completed
first-parent missions and resolves value only from later missions.  It may
propose a shadow scoring profile, but cannot change the live radar, dispatch
work, create provider effects, or promote itself.
"""

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import subprocess
from typing import Any, Sequence

from benchmarking.cfbe_omega.bco_prime_opportunity_exploitation_fabric_v1 import (
    OpportunityCandidate,
)


SCHEMA = "BCO_PRIME_REAL_TRACE_CALIBRATION_V1"
MIN_REAL_TRACES = 60
MIN_HOLDOUT_TRACES = 20
DEFAULT_COHORT_SIZE = 75
DEFAULT_HOLDOUT_SIZE = 25
DEFAULT_FUTURE_WINDOW = 20
TRAIN_GAIN_FLOOR = 0.03
HOLDOUT_GAIN_FLOOR = 0.03


@dataclass(frozen=True, slots=True)
class ScoreProfile:
    profile_name: str
    benefit_weights: tuple[tuple[str, float], ...]
    penalty_weights: tuple[tuple[str, float], ...]

    def validate(self) -> "ScoreProfile":
        benefits = dict(self.benefit_weights)
        penalties = dict(self.penalty_weights)
        if set(benefits) != {
            "value", "strategic_value", "leverage", "novelty", "confidence",
            "reversibility", "dependency_unlock", "urgency",
        }:
            raise ValueError("CALIBRATION_BENEFIT_WEIGHT_KEYS_INVALID")
        if set(penalties) != {"risk", "burden", "cost", "existing_coverage"}:
            raise ValueError("CALIBRATION_PENALTY_WEIGHT_KEYS_INVALID")
        if any(value < 0 for value in (*benefits.values(), *penalties.values())):
            raise ValueError("CALIBRATION_NEGATIVE_WEIGHT")
        if not math.isclose(sum(benefits.values()), 1.0, abs_tol=1e-9):
            raise ValueError("CALIBRATION_BENEFIT_WEIGHTS_MUST_SUM_TO_ONE")
        if not math.isclose(sum(penalties.values()), 1.0, abs_tol=1e-9):
            raise ValueError("CALIBRATION_PENALTY_WEIGHTS_MUST_SUM_TO_ONE")
        return self


BASELINE_PROFILE = ScoreProfile(
    profile_name="BCO_PRIME_RADAR_BASELINE_V1",
    benefit_weights=(
        ("value", 0.22), ("strategic_value", 0.18), ("leverage", 0.18),
        ("novelty", 0.12), ("confidence", 0.10), ("reversibility", 0.08),
        ("dependency_unlock", 0.08), ("urgency", 0.04),
    ),
    penalty_weights=(
        ("risk", 0.45), ("burden", 0.25), ("cost", 0.20),
        ("existing_coverage", 0.10),
    ),
).validate()


@dataclass(frozen=True, slots=True)
class RealMissionTrace:
    trace_id: str
    source_head_sha: str
    feature_observed_at: str
    outcome_window_started_at: str
    outcome_window_ended_at: str
    candidate: OpportunityCandidate
    realized_yield: float
    hard_regression: bool
    evidence_refs: tuple[str, ...]
    outcome_proof_refs: tuple[str, ...]
    real_trace: bool = True

    def validate(self) -> "RealMissionTrace":
        if not _valid_sha(self.source_head_sha):
            raise ValueError("CALIBRATION_SOURCE_HEAD_INVALID")
        if not self.real_trace:
            raise ValueError("CALIBRATION_REAL_TRACE_REQUIRED")
        feature_time = _timestamp(self.feature_observed_at)
        outcome_start = _timestamp(self.outcome_window_started_at)
        outcome_end = _timestamp(self.outcome_window_ended_at)
        if not feature_time < outcome_start <= outcome_end:
            raise ValueError("CALIBRATION_TEMPORAL_LEAKAGE")
        if not 0.0 <= float(self.realized_yield) <= 1.0:
            raise ValueError("CALIBRATION_REALIZED_YIELD_OUT_OF_RANGE")
        if len(self.evidence_refs) < 2 or len(self.outcome_proof_refs) < 2:
            raise ValueError("CALIBRATION_SOURCE_AND_OUTCOME_PROOF_REQUIRED")
        self.candidate.validate()
        return self


@dataclass(frozen=True, slots=True)
class CalibrationReceipt:
    schema: str
    source_head_sha: str
    evidence_mode: str
    trace_count: int
    training_count: int
    holdout_count: int
    future_window: int
    baseline_profile_name: str
    challenger_profile: ScoreProfile
    baseline_training_concordance: float
    challenger_training_concordance: float
    training_delta: float
    baseline_holdout_concordance: float
    challenger_holdout_concordance: float
    holdout_delta: float
    holdout_pairwise_regressions: int
    baseline_top_decile_regression_rate: float
    challenger_top_decile_regression_rate: float
    mean_realized_yield: float
    decision: str
    blockers: tuple[str, ...]
    live_weights_changed: bool
    live_weight_change_authorized: bool
    external_effect_authorized: bool
    stable_self_promotion_allowed: bool
    manual_user_tasks: tuple[str, ...]
    owner_action_required: bool
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class _MissionSnapshot:
    sha: str
    observed_at: str
    title: str
    paths: frozenset[str]
    scope_keys: frozenset[str]
    added_paths: frozenset[str]
    additions: int
    deletions: int


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _valid_sha(value: str) -> bool:
    return len(str(value)) == 40 and all(char in "0123456789abcdef" for char in str(value).lower())


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + sha256(payload).hexdigest()


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def score_candidate(candidate: OpportunityCandidate, profile: ScoreProfile = BASELINE_PROFILE) -> float:
    profile.validate()
    candidate.validate()
    benefit = sum(weight * float(getattr(candidate, name)) for name, weight in profile.benefit_weights)
    penalty = sum(weight * float(getattr(candidate, name)) for name, weight in profile.penalty_weights)
    evidence_factor = min(1.0, 0.55 + 0.15 * len(candidate.evidence_refs))
    return round(_clip((benefit - penalty) * evidence_factor), 9)


def _pairwise_concordance(traces: Sequence[RealMissionTrace], profile: ScoreProfile) -> float:
    correct = 0.0
    comparable = 0
    for index, left in enumerate(traces):
        for right in traces[index + 1:]:
            outcome_delta = left.realized_yield - right.realized_yield
            if math.isclose(outcome_delta, 0.0, abs_tol=1e-12):
                continue
            score_delta = score_candidate(left.candidate, profile) - score_candidate(right.candidate, profile)
            comparable += 1
            if score_delta * outcome_delta > 0:
                correct += 1.0
            elif math.isclose(score_delta, 0.0, abs_tol=1e-12):
                correct += 0.5
    return round(correct / comparable, 9) if comparable else 0.0


def _pairwise_regressions(
    traces: Sequence[RealMissionTrace],
    baseline: ScoreProfile,
    challenger: ScoreProfile,
) -> int:
    regressions = 0
    for index, left in enumerate(traces):
        for right in traces[index + 1:]:
            outcome_delta = left.realized_yield - right.realized_yield
            if math.isclose(outcome_delta, 0.0, abs_tol=1e-12):
                continue
            base_delta = score_candidate(left.candidate, baseline) - score_candidate(right.candidate, baseline)
            challenger_delta = score_candidate(left.candidate, challenger) - score_candidate(right.candidate, challenger)
            if base_delta * outcome_delta > 0 and challenger_delta * outcome_delta <= 0:
                regressions += 1
    return regressions


def _top_decile_regression_rate(traces: Sequence[RealMissionTrace], profile: ScoreProfile) -> float:
    if not traces:
        return 1.0
    count = max(1, math.ceil(len(traces) * 0.10))
    ranked = sorted(traces, key=lambda item: (-score_candidate(item.candidate, profile), item.trace_id))[:count]
    return round(sum(item.hard_regression for item in ranked) / count, 9)


def optimize_shadow_profile(
    training: Sequence[RealMissionTrace],
    *,
    baseline: ScoreProfile = BASELINE_PROFILE,
    step: float = 0.02,
    max_rounds: int = 20,
) -> ScoreProfile:
    """Fit one bounded coordinate challenger to training traces only."""

    if not training:
        return baseline
    benefits = dict(baseline.benefit_weights)
    penalties = dict(baseline.penalty_weights)
    best = _pairwise_concordance(training, baseline)
    for _ in range(max_rounds):
        improved = False
        for group_name in ("benefit", "penalty"):
            current = benefits if group_name == "benefit" else penalties
            for increase in sorted(current):
                for decrease in sorted(current):
                    if increase == decrease or current[decrease] + 1e-12 < step:
                        continue
                    candidate_weights = dict(current)
                    candidate_weights[increase] += step
                    candidate_weights[decrease] -= step
                    candidate = ScoreProfile(
                        profile_name="BCO_PRIME_RADAR_COORDINATE_CHALLENGER_V1",
                        benefit_weights=tuple(sorted((candidate_weights if group_name == "benefit" else benefits).items())),
                        penalty_weights=tuple(sorted((penalties if group_name == "benefit" else candidate_weights).items())),
                    ).validate()
                    quality = _pairwise_concordance(training, candidate)
                    if quality > best + 1e-12:
                        if group_name == "benefit":
                            benefits = candidate_weights
                        else:
                            penalties = candidate_weights
                        best = quality
                        improved = True
        if not improved:
            break
    return ScoreProfile(
        profile_name="BCO_PRIME_RADAR_COORDINATE_CHALLENGER_V1",
        benefit_weights=tuple(sorted(benefits.items())),
        penalty_weights=tuple(sorted(penalties.items())),
    ).validate()


def evaluate_calibration(
    traces: Sequence[RealMissionTrace],
    *,
    holdout_size: int = DEFAULT_HOLDOUT_SIZE,
    future_window: int = DEFAULT_FUTURE_WINDOW,
) -> CalibrationReceipt:
    if len({item.trace_id for item in traces}) != len(traces):
        raise ValueError("CALIBRATION_TRACE_IDS_MUST_BE_UNIQUE")
    validated = tuple(item.validate() for item in traces)
    source_heads = {item.source_head_sha for item in validated}
    if len(source_heads) != 1:
        raise ValueError("CALIBRATION_SOURCE_HEAD_MISMATCH")
    if holdout_size < 1 or holdout_size >= len(validated):
        raise ValueError("CALIBRATION_HOLDOUT_BOUND_INVALID")
    ordered = tuple(sorted(validated, key=lambda item: (item.feature_observed_at, item.trace_id)))
    training, holdout = ordered[:-holdout_size], ordered[-holdout_size:]
    challenger = optimize_shadow_profile(training)
    base_train = _pairwise_concordance(training, BASELINE_PROFILE)
    challenge_train = _pairwise_concordance(training, challenger)
    base_holdout = _pairwise_concordance(holdout, BASELINE_PROFILE)
    challenge_holdout = _pairwise_concordance(holdout, challenger)
    pairwise_regressions = _pairwise_regressions(holdout, BASELINE_PROFILE, challenger)
    baseline_regression_rate = _top_decile_regression_rate(holdout, BASELINE_PROFILE)
    challenger_regression_rate = _top_decile_regression_rate(holdout, challenger)
    blockers: list[str] = []
    if len(ordered) < MIN_REAL_TRACES:
        blockers.append("MINIMUM_REAL_TRACE_COHORT_REQUIRED")
    if len(holdout) < MIN_HOLDOUT_TRACES:
        blockers.append("MINIMUM_CHRONOLOGICAL_HOLDOUT_REQUIRED")
    if challenge_train - base_train < TRAIN_GAIN_FLOOR:
        blockers.append("TRAINING_GAIN_BELOW_FLOOR")
    if challenge_holdout - base_holdout < HOLDOUT_GAIN_FLOOR:
        blockers.append("HOLDOUT_GAIN_BELOW_FLOOR")
    if pairwise_regressions:
        blockers.append("HELD_OUT_PAIRWISE_REGRESSION")
    if challenger_regression_rate > baseline_regression_rate:
        blockers.append("TOP_DECILE_HARD_REGRESSION_RATE_INCREASED")
    decision = "SHADOW_PROFILE_CANDIDATE" if not blockers else "HOLD_BASELINE_NEGATIVE_RESULT"
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "source_head_sha": next(iter(source_heads), ""),
        "evidence_mode": "REAL_FIRST_PARENT_MISSION_TRACE",
        "trace_count": len(ordered),
        "training_count": len(training),
        "holdout_count": len(holdout),
        "future_window": future_window,
        "baseline_profile_name": BASELINE_PROFILE.profile_name,
        "challenger_profile": asdict(challenger),
        "baseline_training_concordance": base_train,
        "challenger_training_concordance": challenge_train,
        "training_delta": round(challenge_train - base_train, 9),
        "baseline_holdout_concordance": base_holdout,
        "challenger_holdout_concordance": challenge_holdout,
        "holdout_delta": round(challenge_holdout - base_holdout, 9),
        "holdout_pairwise_regressions": pairwise_regressions,
        "baseline_top_decile_regression_rate": baseline_regression_rate,
        "challenger_top_decile_regression_rate": challenger_regression_rate,
        "mean_realized_yield": round(sum(item.realized_yield for item in ordered) / len(ordered), 9) if ordered else 0.0,
        "decision": decision,
        "blockers": tuple(blockers),
        "live_weights_changed": False,
        "live_weight_change_authorized": False,
        "external_effect_authorized": False,
        "stable_self_promotion_allowed": False,
        "manual_user_tasks": (),
        "owner_action_required": False,
    }
    body["receipt_sha256"] = _canonical_hash(body)
    return CalibrationReceipt(**body)


def _git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=check, capture_output=True, text=True,
    )
    return result.stdout.strip()


def _scope_key(path: str) -> str:
    parts = path.split("/")
    return "/".join(parts[:2]) if len(parts) > 1 else parts[0]


def _snapshots(repo: Path, source_head_sha: str, history_limit: int) -> tuple[_MissionSnapshot, ...]:
    log = _git(repo, "log", "--first-parent", f"-{history_limit}", "--pretty=format:%H%x09%aI%x09%s", source_head_sha)
    rows: list[tuple[str, str, str]] = []
    for line in log.splitlines():
        sha, observed_at, title = line.split("\t", 2)
        if "#" in title or title.lower().startswith(("merge", "feat", "fix", "test", "docs", "cfbe")):
            rows.append((sha, observed_at, title))
    snapshots: list[_MissionSnapshot] = []
    for sha, observed_at, title in reversed(rows):
        status_text = _git(repo, "diff-tree", "--first-parent", "--no-commit-id", "--name-status", "-r", sha)
        statuses: dict[str, str] = {}
        for line in status_text.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                statuses[parts[-1]] = parts[0]
        numstat = _git(repo, "show", "--first-parent", "--format=", "--numstat", sha)
        paths: set[str] = set()
        additions = deletions = 0
        for line in numstat.splitlines():
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            added, deleted, path = parts
            paths.add(path)
            additions += 0 if added == "-" else int(added)
            deletions += 0 if deleted == "-" else int(deleted)
        if not paths:
            continue
        snapshots.append(_MissionSnapshot(
            sha=sha,
            observed_at=observed_at,
            title=title,
            paths=frozenset(paths),
            scope_keys=frozenset(_scope_key(path) for path in paths),
            added_paths=frozenset(path for path, status in statuses.items() if status.startswith("A")),
            additions=additions,
            deletions=deletions,
        ))
    return tuple(snapshots)


def _candidate_from_snapshot(item: _MissionSnapshot) -> OpportunityCandidate:
    path_count = max(1, len(item.paths))
    scope_count = len(item.scope_keys)
    test_count = sum(path.startswith("tests/") or "/test" in path.lower() for path in item.paths)
    text = (item.title + " " + " ".join(sorted(item.paths))).lower()
    changed_lines = item.additions + item.deletions
    strategic = min(1.0, scope_count / 6 * 0.55 + (0.45 if re.search(r"federation|govern|runtime|provider|control|court|policy", text) else 0.0))
    leverage = min(1.0, scope_count / 8 * 0.45 + test_count / path_count * 0.25 + (0.30 if re.search(r"bridge|adapter|compiler|fabric|index|mesh|reuse", text) else 0.0))
    confidence = min(1.0, test_count / path_count * 1.5 + (0.25 if test_count else 0.0) + (0.15 if re.search(r"prove|verify|test|court", text) else 0.0))
    reversibility = max(0.0, 1.0 - (0.35 if any(path.startswith(".github/workflows/") for path in item.paths) else 0.0) - (0.25 if re.search(r"deploy|iam|secret|migration", text) else 0.0))
    risk = min(1.0, (0.50 if any(path.startswith(".github/") or "security" in path for path in item.paths) else 0.0) + (0.35 if re.search(r"provider|cloud|wif|oidc|iam|secret|deploy", text) else 0.0))
    return OpportunityCandidate(
        candidate_id=item.sha,
        summary=item.title,
        evidence_refs=(f"git:{item.sha}:scope", f"git:{item.sha}:diff"),
        value=min(1.0, math.log1p(changed_lines) / math.log1p(1800)),
        strategic_value=strategic,
        leverage=leverage,
        novelty=min(1.0, len(item.added_paths) / path_count * 0.8 + (0.2 if re.search(r"admit|add|initialize|new|v1", item.title.lower()) else 0.0)),
        confidence=confidence,
        reversibility=reversibility,
        dependency_unlock=min(1.0, scope_count / 7 * 0.4 + (0.6 if re.search(r"unlock|bridge|adapter|runtime|route|compiler|mesh|repair", text) else 0.0)),
        urgency=0.9 if re.search(r"fix|repair|recover|restore|revert|drift", item.title.lower()) else 0.35,
        risk=risk,
        burden=0.0,
        cost=0.35 if re.search(r"provider|cloud|model|api", text) else 0.0,
        existing_coverage=min(1.0, 1.0 - len(item.added_paths) / path_count),
    )


def _path_survives(repo: Path, source_head_sha: str, path: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{source_head_sha}:{path}"],
        cwd=repo, capture_output=True, text=True,
    )
    return result.returncode == 0


def collect_real_mission_traces(
    repo: str | Path,
    *,
    source_head_sha: str | None = None,
    cohort_size: int = DEFAULT_COHORT_SIZE,
    future_window: int = DEFAULT_FUTURE_WINDOW,
    history_limit: int = 140,
) -> tuple[RealMissionTrace, ...]:
    root = Path(repo).resolve()
    source_head = source_head_sha or _git(root, "rev-parse", "HEAD")
    if not _valid_sha(source_head):
        raise ValueError("CALIBRATION_SOURCE_HEAD_INVALID")
    snapshots = _snapshots(root, source_head, history_limit)
    if len(snapshots) <= future_window:
        return ()
    eligible = snapshots[:-future_window]
    selected = eligible[-cohort_size:]
    offset = len(eligible) - len(selected)
    traces: list[RealMissionTrace] = []
    for relative_index, item in enumerate(selected):
        absolute_index = offset + relative_index
        future = snapshots[absolute_index + 1:absolute_index + future_window + 1]
        exact_reuse = sum(bool(item.paths & later.paths) for later in future)
        scope_reuse = sum(bool(item.scope_keys & later.scope_keys) for later in future)
        regression = any(
            re.search(r"fix|repair|revert|correct|drift", later.title.lower())
            and (bool(item.paths & later.paths) or bool(item.scope_keys & later.scope_keys))
            for later in future[:10]
        )
        survival = sum(_path_survives(root, source_head, path) for path in item.paths) / len(item.paths)
        realized = (
            0.45 * min(1.0, exact_reuse / 4)
            + 0.20 * min(1.0, scope_reuse / 8)
            + 0.20 * survival
            + 0.15 * (0.0 if regression else 1.0)
        )
        traces.append(RealMissionTrace(
            trace_id=f"REAL-{item.sha[:12]}",
            source_head_sha=source_head,
            feature_observed_at=item.observed_at,
            outcome_window_started_at=future[0].observed_at,
            outcome_window_ended_at=future[-1].observed_at,
            candidate=_candidate_from_snapshot(item),
            realized_yield=round(_clip(realized), 9),
            hard_regression=bool(regression),
            evidence_refs=(f"git:{item.sha}:first-parent-scope", f"git:{item.sha}:numstat"),
            outcome_proof_refs=(f"git:{future[0].sha}:window-start", f"git:{future[-1].sha}:window-end"),
        ).validate())
    return tuple(traces)


def real_trace_calibration_manifest() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "minimum_real_traces": MIN_REAL_TRACES,
        "minimum_holdout_traces": MIN_HOLDOUT_TRACES,
        "default_future_window": DEFAULT_FUTURE_WINDOW,
        "temporal_leakage_rejected": True,
        "production_profile_immutable": True,
        "external_effect_authority": False,
        "stable_self_promotion": False,
        "manual_user_tasks": [],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=SCHEMA)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--source-head")
    parser.add_argument("--cohort-size", type=int, default=DEFAULT_COHORT_SIZE)
    parser.add_argument("--holdout-size", type=int, default=DEFAULT_HOLDOUT_SIZE)
    parser.add_argument("--future-window", type=int, default=DEFAULT_FUTURE_WINDOW)
    parser.add_argument("--history-limit", type=int, default=140)
    return parser


def main() -> int:
    args = _parser().parse_args()
    traces = collect_real_mission_traces(
        args.repo,
        source_head_sha=args.source_head,
        cohort_size=args.cohort_size,
        future_window=args.future_window,
        history_limit=args.history_limit,
    )
    receipt = evaluate_calibration(
        traces,
        holdout_size=args.holdout_size,
        future_window=args.future_window,
    )
    print(json.dumps(receipt.to_dict(), sort_keys=True))
    return 0


__all__ = [
    "BASELINE_PROFILE", "CalibrationReceipt", "DEFAULT_COHORT_SIZE",
    "DEFAULT_FUTURE_WINDOW", "DEFAULT_HOLDOUT_SIZE", "MIN_HOLDOUT_TRACES",
    "MIN_REAL_TRACES", "RealMissionTrace", "SCHEMA", "ScoreProfile",
    "collect_real_mission_traces", "evaluate_calibration",
    "optimize_shadow_profile", "real_trace_calibration_manifest",
    "score_candidate",
]


if __name__ == "__main__":
    raise SystemExit(main())
