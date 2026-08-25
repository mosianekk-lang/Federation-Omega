from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


MODEL_ID = "gpt-5.6-sol"
MODEL_ALIAS = "gpt-5.6"
SUPPORTED_REASONING_EFFORTS = ("none", "low", "medium", "high", "xhigh", "max")
MAX_CONTEXT_TOKENS = 1_050_000
MAX_OUTPUT_TOKENS = 128_000
LONG_CONTEXT_PRICE_THRESHOLD = 272_000


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    category: str
    weight: float
    evaluator: str
    required_runs: int
    thresholds: Mapping[str, float | bool]
    context_tokens: int = 0

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "BenchmarkCase":
        case = cls(
            case_id=str(value["case_id"]),
            category=str(value["category"]),
            weight=float(value["weight"]),
            evaluator=str(value["evaluator"]),
            required_runs=int(value["required_runs"]),
            thresholds=dict(value.get("thresholds") or {}),
            context_tokens=int(value.get("context_tokens") or 0),
        )
        case.validate()
        return case

    def validate(self) -> None:
        if not self.case_id or not self.category or not self.evaluator:
            raise ValueError("case_id, category and evaluator are required")
        if self.weight <= 0:
            raise ValueError(f"{self.case_id}: weight must be > 0")
        if self.required_runs < 1:
            raise ValueError(f"{self.case_id}: required_runs must be >= 1")
        if not 0 <= self.context_tokens <= MAX_CONTEXT_TOKENS:
            raise ValueError(f"{self.case_id}: context exceeds the Sol 5.6 model contract")


@dataclass(frozen=True)
class RunObservation:
    run_id: str
    case_id: str
    result_state: str
    model: str | None = None
    reasoning_effort: str | None = None
    score_0_100: float | None = None
    latency_total_ms: float | None = None
    ttft_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None
    retries: int = 0
    cancellation_ack_ms: float | None = None
    duplicate_effects: int = 0
    external_effects: int = 0
    schema_valid: bool | None = None
    provider_live: bool = False
    independent_readback: bool = False
    output_hash: str | None = None
    provider_cost_usd: float | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RunObservation":
        observation = cls(**value)
        observation.validate()
        return observation

    def validate(self) -> None:
        if not self.run_id or not self.case_id:
            raise ValueError("run_id and case_id are required")
        if self.result_state not in {"PASS", "FAIL", "NOT_EXECUTED"}:
            raise ValueError(f"{self.run_id}: unsupported result_state")
        if self.result_state == "NOT_EXECUTED":
            if self.provider_live or self.independent_readback:
                raise ValueError(f"{self.run_id}: unexecuted run cannot carry live proof")
            return
        if self.model is None or self.reasoning_effort not in SUPPORTED_REASONING_EFFORTS:
            raise ValueError(f"{self.run_id}: model and supported reasoning_effort required")
        if self.score_0_100 is None or not 0 <= self.score_0_100 <= 100:
            raise ValueError(f"{self.run_id}: score_0_100 must be in [0, 100]")
        if not self.output_hash:
            raise ValueError(f"{self.run_id}: executed run requires output_hash")
        if self.provider_live and not self.independent_readback:
            raise ValueError(f"{self.run_id}: provider-live proof requires independent readback")
        for name in ("latency_total_ms", "ttft_ms", "cancellation_ack_ms", "provider_cost_usd"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{self.run_id}: {name} must be >= 0")
        for name in ("input_tokens", "output_tokens", "cached_input_tokens", "retries", "duplicate_effects", "external_effects"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{self.run_id}: {name} must be >= 0")
        if self.input_tokens is not None and self.input_tokens > MAX_CONTEXT_TOKENS:
            raise ValueError(f"{self.run_id}: input exceeds Sol 5.6 context")
        if self.output_tokens is not None and self.output_tokens > MAX_OUTPUT_TOKENS:
            raise ValueError(f"{self.run_id}: output exceeds Sol 5.6 maximum")
        if (
            self.cached_input_tokens is not None
            and self.input_tokens is not None
            and self.cached_input_tokens > self.input_tokens
        ):
            raise ValueError(f"{self.run_id}: cached input exceeds total input")


@dataclass(frozen=True)
class RouteCandidate:
    model: str
    quality_0_100: float
    p95_latency_ms: float
    cost_per_success_usd: float
    error_rate: float
    provider_verified: bool


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def nearest_rank(values: Iterable[float], percentile: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    if not 0 <= percentile <= 1:
        raise ValueError("percentile must be in [0, 1]")
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float] | None:
    if total == 0:
        return None
    if successes < 0 or successes > total:
        raise ValueError("successes must be in [0, total]")
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return round(max(0.0, centre - margin), 6), round(min(1.0, centre + margin), 6)


def load_spec(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = [BenchmarkCase.from_dict(item) for item in data.get("cases") or []]
    if not cases:
        raise ValueError("benchmark spec requires cases")
    ids = [case.case_id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("benchmark case IDs must be unique")
    if not math.isclose(sum(case.weight for case in cases), 100.0, abs_tol=1e-9):
        raise ValueError("benchmark case weights must sum to 100")
    data["cases"] = cases
    return data


def load_observations(path: str | Path) -> list[RunObservation]:
    observations: list[RunObservation] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                observations.append(RunObservation.from_dict(json.loads(line)))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"invalid observation at line {line_number}: {exc}") from exc
    run_ids = [item.run_id for item in observations]
    if len(run_ids) != len(set(run_ids)):
        raise ValueError("run IDs must be unique")
    return observations


def _threshold_failures(case: BenchmarkCase, observation: RunObservation) -> list[str]:
    if observation.result_state == "NOT_EXECUTED":
        return ["NOT_EXECUTED"]
    failures: list[str] = []
    thresholds = case.thresholds
    checks = (
        ("min_score_0_100", observation.score_0_100, lambda actual, limit: actual >= limit),
        ("max_latency_total_ms", observation.latency_total_ms, lambda actual, limit: actual <= limit),
        ("max_ttft_ms", observation.ttft_ms, lambda actual, limit: actual <= limit),
        ("max_retries", observation.retries, lambda actual, limit: actual <= limit),
        ("max_cancellation_ack_ms", observation.cancellation_ack_ms, lambda actual, limit: actual <= limit),
        ("max_duplicate_effects", observation.duplicate_effects, lambda actual, limit: actual <= limit),
        ("max_external_effects", observation.external_effects, lambda actual, limit: actual <= limit),
    )
    for name, actual, comparator in checks:
        if name in thresholds and (actual is None or not comparator(actual, float(thresholds[name]))):
            failures.append(name)
    if thresholds.get("require_schema_valid") is True and observation.schema_valid is not True:
        failures.append("require_schema_valid")
    if observation.result_state == "FAIL":
        failures.append("result_state")
    return failures


def evaluate_suite(spec: Mapping[str, Any], observations: Sequence[RunObservation]) -> dict[str, Any]:
    cases = list(spec["cases"])
    case_map = {case.case_id: case for case in cases}
    unknown = sorted({item.case_id for item in observations} - set(case_map))
    if unknown:
        raise ValueError(f"unknown case IDs: {unknown}")

    grouped: dict[str, list[RunObservation]] = {case.case_id: [] for case in cases}
    for observation in observations:
        grouped[observation.case_id].append(observation)

    executed = [item for item in observations if item.result_state != "NOT_EXECUTED"]
    verified_sol = [
        item
        for item in executed
        if item.model == MODEL_ID and item.provider_live and item.independent_readback
    ]
    complete_cases = 0
    passed_cases = 0
    weighted_numerator = 0.0
    weighted_denominator = 0.0
    gate_failures: list[dict[str, Any]] = []
    category_scores: dict[str, list[tuple[float, float]]] = {}

    for case in cases:
        runs = [item for item in grouped[case.case_id] if item.result_state != "NOT_EXECUTED"]
        if len(runs) >= case.required_runs:
            complete_cases += 1
        if runs:
            mean_score = sum(float(item.score_0_100) for item in runs) / len(runs)
            weighted_numerator += mean_score * case.weight
            weighted_denominator += case.weight
            category_scores.setdefault(case.category, []).append((mean_score, case.weight))
        failures = sorted({failure for item in runs for failure in _threshold_failures(case, item)})
        if len(runs) < case.required_runs:
            failures.append("INSUFFICIENT_REPETITIONS")
        if failures:
            gate_failures.append({"case_id": case.case_id, "failures": sorted(set(failures))})
        else:
            passed_cases += 1

    quality = None if not weighted_denominator else round(weighted_numerator / weighted_denominator, 4)
    total_input = sum(item.input_tokens or 0 for item in executed)
    total_cached = sum(item.cached_input_tokens or 0 for item in executed)
    cache_hit_rate = None if total_input == 0 else round(total_cached / total_input, 6)
    provider_costs = [item.provider_cost_usd for item in executed if item.provider_cost_usd is not None]

    category_report = {}
    for category, values in sorted(category_scores.items()):
        denominator = sum(weight for _, weight in values)
        category_report[category] = round(sum(score * weight for score, weight in values) / denominator, 4)

    required_provider_runs = sum(case.required_runs for case in cases)
    provider_complete = (
        len(verified_sol) >= required_provider_runs
        and complete_cases == len(cases)
        and len(verified_sol) == len(executed)
    )
    if not executed:
        truth_state = "PROVIDER_NOT_EXECUTED"
    elif provider_complete:
        truth_state = "PROVIDER_LIVE_VERIFIED"
    else:
        truth_state = "SYNTHETIC_OR_PARTIAL_NOT_MODEL_PROOF"

    report = {
        "schema": "CFBE-SOL56-RUNTIME-REPORT-V1",
        "benchmark_id": spec["benchmark_id"],
        "benchmark_version": spec["version"],
        "model_contract": {
            "model_id": MODEL_ID,
            "alias": MODEL_ALIAS,
            "max_context_tokens": MAX_CONTEXT_TOKENS,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "reasoning_efforts": list(SUPPORTED_REASONING_EFFORTS),
            "long_context_price_threshold": LONG_CONTEXT_PRICE_THRESHOLD,
        },
        "case_count": len(cases),
        "required_provider_runs": required_provider_runs,
        "observed_runs": len(observations),
        "executed_runs": len(executed),
        "provider_verified_sol_runs": len(verified_sol),
        "complete_case_coverage": round(complete_cases / len(cases), 6),
        "passed_case_rate": round(passed_cases / len(cases), 6),
        "weighted_quality_0_100": quality,
        "category_scores": category_report,
        "latency_ms": {
            "p50": nearest_rank((item.latency_total_ms for item in executed if item.latency_total_ms is not None), 0.50),
            "p95": nearest_rank((item.latency_total_ms for item in executed if item.latency_total_ms is not None), 0.95),
            "p99": nearest_rank((item.latency_total_ms for item in executed if item.latency_total_ms is not None), 0.99),
            "ttft_p95": nearest_rank((item.ttft_ms for item in executed if item.ttft_ms is not None), 0.95),
        },
        "token_efficiency": {
            "input_tokens": total_input,
            "output_tokens": sum(item.output_tokens or 0 for item in executed),
            "cached_input_tokens": total_cached,
            "cache_hit_rate": cache_hit_rate,
            "long_context_runs": sum((item.input_tokens or 0) > LONG_CONTEXT_PRICE_THRESHOLD for item in executed),
        },
        "provider_cost_usd": None if not provider_costs else round(sum(provider_costs), 8),
        "success_interval_95": wilson_interval(passed_cases, len(cases)),
        "gate_failures": gate_failures,
        "scale_readiness": "PASS" if provider_complete and not gate_failures else "BLOCKED",
        "truth_state": truth_state,
        "model_performance_claim_allowed": provider_complete,
        "external_effects": sum(item.external_effects for item in executed),
    }
    report["report_hash"] = canonical_hash(report)
    return report


def select_route(candidates: Sequence[RouteCandidate], task_tier: str) -> RouteCandidate:
    if task_tier not in {"FRONTIER", "STANDARD", "BULK"}:
        raise ValueError("task_tier must be FRONTIER, STANDARD or BULK")
    pool = [candidate for candidate in candidates if candidate.provider_verified]
    if task_tier == "FRONTIER":
        pool = [candidate for candidate in pool if candidate.model == MODEL_ID]
    if not pool:
        raise ValueError("no provider-verified candidate satisfies the route gate")
    quality_floor = {"FRONTIER": 90.0, "STANDARD": 82.0, "BULK": 75.0}[task_tier]
    pool = [candidate for candidate in pool if candidate.quality_0_100 >= quality_floor]
    if not pool:
        raise ValueError("no candidate meets the quality floor")

    def utility(candidate: RouteCandidate) -> tuple[float, float, float]:
        quality_weight = {"FRONTIER": 0.75, "STANDARD": 0.55, "BULK": 0.35}[task_tier]
        latency_score = 100.0 / (1.0 + candidate.p95_latency_ms / 1000.0)
        cost_score = 100.0 / (1.0 + 100.0 * candidate.cost_per_success_usd)
        score = (
            quality_weight * candidate.quality_0_100
            + (1 - quality_weight) * 0.55 * latency_score
            + (1 - quality_weight) * 0.45 * cost_score
            - 100.0 * candidate.error_rate
        )
        return score, candidate.quality_0_100, -candidate.cost_per_success_usd

    return max(pool, key=utility)


def write_report_atomic(report: Mapping[str, Any], output_path: str | Path) -> None:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline CFBE-Ω Sol 5.6 benchmark evaluator")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--observations", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    spec = load_spec(args.spec)
    report = evaluate_suite(spec, load_observations(args.observations))
    write_report_atomic(report, args.output)
    print(json.dumps({"truth_state": report["truth_state"], "report_hash": report["report_hash"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
