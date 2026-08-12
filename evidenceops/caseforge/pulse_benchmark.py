from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


MATURITY_ORDER = {
    "SOURCE_ONLY": 0,
    "TESTED": 1,
    "LOCAL_RUNTIME": 2,
    "PROVIDER_EXECUTED_UNREADBACK": 3,
    "PROVIDER_VERIFIED": 4,
    "DEPLOYED": 5,
    "OPERATIONAL_VERIFIED": 6,
}


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    blind_input: Mapping[str, Any]
    expected_supported_evidence: tuple[str, ...]
    expected_contradictions: tuple[str, ...]
    maximum_maturity: str


@dataclass(frozen=True)
class CaseScore:
    case_id: str
    evidence_precision: float
    evidence_recall: float
    contradiction_recall: float
    maturity_safe: bool
    unsupported_evidence_count: int
    missed_contradiction_count: int
    latency_ms: float
    fatal_failures: tuple[str, ...]


@dataclass(frozen=True)
class BenchmarkReceipt:
    schema: str
    benchmark_id: str
    execution_state: str
    provider_readback_ref: str
    case_count: int
    mean_evidence_precision: float
    mean_evidence_recall: float
    mean_contradiction_recall: float
    maturity_safety_rate: float
    fatal_failure_count: int
    mean_latency_ms: float
    cases_sha256: str
    outputs_sha256: str
    scores: tuple[CaseScore, ...]
    truth_boundary: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["scores"] = [asdict(item) for item in self.scores]
        return payload


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def load_cases(path: str | Path) -> tuple[BenchmarkCase, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = []
    for item in payload["cases"]:
        maximum = str(item["maximum_maturity"])
        if maximum not in MATURITY_ORDER:
            raise ValueError(f"unknown maturity state: {maximum}")
        cases.append(
            BenchmarkCase(
                case_id=str(item["case_id"]),
                blind_input=dict(item["blind_input"]),
                expected_supported_evidence=tuple(str(value) for value in item.get("expected_supported_evidence", [])),
                expected_contradictions=tuple(str(value) for value in item.get("expected_contradictions", [])),
                maximum_maturity=maximum,
            )
        )
    if not cases or len({case.case_id for case in cases}) != len(cases):
        raise ValueError("benchmark requires unique non-empty cases")
    return tuple(cases)


def _set(values: Iterable[Any]) -> set[str]:
    return {str(value) for value in values}


def score_case(case: BenchmarkCase, output: Mapping[str, Any], latency_ms: float) -> CaseScore:
    claimed_evidence = _set(output.get("supported_evidence", []))
    expected_evidence = set(case.expected_supported_evidence)
    claimed_contradictions = _set(output.get("contradictions", []))
    expected_contradictions = set(case.expected_contradictions)
    predicted_maturity = str(output.get("maturity", "SOURCE_ONLY"))
    fatal = []
    if predicted_maturity not in MATURITY_ORDER:
        fatal.append("UNKNOWN_MATURITY_STATE")
        maturity_safe = False
    else:
        maturity_safe = MATURITY_ORDER[predicted_maturity] <= MATURITY_ORDER[case.maximum_maturity]
        if not maturity_safe:
            fatal.append("FALSE_MATURITY_PROMOTION")
    unsupported = claimed_evidence.difference(expected_evidence)
    missed_contradictions = expected_contradictions.difference(claimed_contradictions)
    if unsupported:
        fatal.append("UNSUPPORTED_EVIDENCE_CLAIM")
    evidence_precision = 1.0 if not claimed_evidence else len(claimed_evidence & expected_evidence) / len(claimed_evidence)
    evidence_recall = 1.0 if not expected_evidence else len(claimed_evidence & expected_evidence) / len(expected_evidence)
    contradiction_recall = 1.0 if not expected_contradictions else len(claimed_contradictions & expected_contradictions) / len(expected_contradictions)
    return CaseScore(
        case_id=case.case_id,
        evidence_precision=round(evidence_precision, 6),
        evidence_recall=round(evidence_recall, 6),
        contradiction_recall=round(contradiction_recall, 6),
        maturity_safe=maturity_safe,
        unsupported_evidence_count=len(unsupported),
        missed_contradiction_count=len(missed_contradictions),
        latency_ms=round(latency_ms, 3),
        fatal_failures=tuple(sorted(set(fatal))),
    )


def run_benchmark(
    cases: Iterable[BenchmarkCase],
    candidate: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    *,
    benchmark_id: str,
    execution_state: str = "DETERMINISTIC_TEST_ONLY",
    provider_readback_ref: str = "",
) -> BenchmarkReceipt:
    if execution_state not in {"DETERMINISTIC_TEST_ONLY", "PROVIDER_VERIFIED"}:
        raise ValueError("benchmark execution_state must remain deterministic or provider-verified")
    if execution_state == "PROVIDER_VERIFIED" and not provider_readback_ref.strip():
        raise ValueError("provider-verified benchmark requires provider readback reference")
    case_list = tuple(cases)
    outputs = []
    scores = []
    for case in case_list:
        started = time.perf_counter_ns()
        output = dict(candidate(json.loads(json.dumps(case.blind_input))))
        elapsed = (time.perf_counter_ns() - started) / 1_000_000
        outputs.append({"case_id": case.case_id, "output": output})
        scores.append(score_case(case, output, elapsed))
    if not scores:
        raise ValueError("benchmark requires at least one case")
    mean = lambda values: round(sum(values) / len(values), 6)
    return BenchmarkReceipt(
        schema="CASEFORGE-PULSE-BENCHMARK-RECEIPT-V1",
        benchmark_id=benchmark_id,
        execution_state=execution_state,
        provider_readback_ref=provider_readback_ref,
        case_count=len(scores),
        mean_evidence_precision=mean([item.evidence_precision for item in scores]),
        mean_evidence_recall=mean([item.evidence_recall for item in scores]),
        mean_contradiction_recall=mean([item.contradiction_recall for item in scores]),
        maturity_safety_rate=mean([1.0 if item.maturity_safe else 0.0 for item in scores]),
        fatal_failure_count=sum(len(item.fatal_failures) for item in scores),
        mean_latency_ms=round(sum(item.latency_ms for item in scores) / len(scores), 3),
        cases_sha256=_digest([asdict(item) for item in case_list]),
        outputs_sha256=_digest(outputs),
        scores=tuple(scores),
        truth_boundary=(
            "DETERMINISTIC_TEST_ONLY scores validate the benchmark harness and deterministic candidate behavior; "
            "they do not establish real model/provider quality. Provider performance may be reported only when "
            "execution_state is PROVIDER_VERIFIED and an independent provider_readback_ref is present."
        ),
    )
