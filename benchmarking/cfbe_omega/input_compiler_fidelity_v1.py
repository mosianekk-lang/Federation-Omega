from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Callable, Iterable, Mapping

from federation.cfbe_input_compiler_v2 import CompiledMission, InputContext, compile_owner_input


DEFAULT_CASES = Path(__file__).with_name("input_compiler_fidelity_cases_v1.json")
Compiler = Callable[[str, InputContext | None], CompiledMission]


@dataclass(frozen=True, slots=True)
class FidelityCaseResult:
    case_id: str
    intent_ok: bool
    effect_ok: bool
    approval_ok: bool
    clarification_ok: bool
    capability_ok: bool
    workstream_ok: bool
    mission_ir_ok: bool
    deterministic_ok: bool
    hard_veto: bool
    observed_intent: str
    observed_effect_class: str
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures and not self.hard_veto


@dataclass(frozen=True, slots=True)
class FidelitySuiteReport:
    schema: str
    compiler_name: str
    case_count: int
    passed_cases: int
    intent_accuracy: float
    effect_accuracy: float
    approval_accuracy: float
    clarification_accuracy: float
    capability_coverage: float
    workstream_coverage: float
    mission_ir_validity: float
    deterministic_rate: float
    hard_veto_count: int
    status: str
    failed_case_ids: tuple[str, ...]
    results: tuple[FidelityCaseResult, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["results"] = [asdict(item) | {"passed": item.passed} for item in self.results]
        return payload


def load_cases(path: str | Path = DEFAULT_CASES) -> tuple[Mapping[str, object], ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != "CFBE-INPUT-COMPILER-FIDELITY-CASES-V1":
        raise ValueError("CFBE_FIDELITY_CASE_SCHEMA_INVALID")
    cases = tuple(payload.get("cases", ()))
    if not cases:
        raise ValueError("CFBE_FIDELITY_CASES_REQUIRED")
    return cases


def _context(case: Mapping[str, object]) -> InputContext:
    return InputContext(
        active_mission_id=str(case["active_mission_id"]) if case.get("active_mission_id") else None,
        active_objective=str(case["active_objective"]) if case.get("active_objective") else None,
        domain="GENERAL",
        source_frontier="FIDELITY_FIXTURE",
        privacy_class="PUBLIC_SAFE",
        rights_state="OWNER_CONTROLLED",
    )


def evaluate_case(case: Mapping[str, object], compiler: Compiler = compile_owner_input) -> FidelityCaseResult:
    context = _context(case)
    compiled = compiler(str(case["prompt"]), context)
    compiled.mission_ir.validate()
    repeat = compiler(str(case["prompt"]), context)

    expected_intent = str(case["expected_intent"])
    expected_effect = str(case["expected_effect_class"])
    expected_approval = bool(case["expected_owner_approval"])
    expected_clarification = bool(case["expected_clarification"])
    required_capabilities = set(map(str, case.get("required_capabilities", ())))
    required_workstreams = set(map(str, case.get("required_workstreams", ())))

    checks = {
        "intent": compiled.intent.kind.value == expected_intent,
        "effect": compiled.mission_ir.effect_class == expected_effect,
        "approval": compiled.mission_ir.owner_approval_required == expected_approval,
        "clarification": compiled.intent.owner_clarification_required == expected_clarification,
        "capability": required_capabilities.issubset(set(compiled.capability_hints)),
        "workstream": required_workstreams.issubset(set(compiled.workstream_hints)),
        "mission_ir": True,
        "deterministic": compiled.digest() == repeat.digest(),
    }
    failures = tuple(name for name, ok in checks.items() if not ok)
    consequential = expected_effect == "CONSEQUENTIAL_EFFECT"
    continuation_without_context = str(case["prompt"]).strip().casefold() in {"n", "continue"} and not case.get("active_mission_id") and not case.get("active_objective")
    hard_veto = bool(
        (consequential and (not compiled.mission_ir.owner_approval_required or not compiled.mission_ir.authority_requirements))
        or (continuation_without_context and not compiled.intent.owner_clarification_required)
        or not checks["mission_ir"]
        or not checks["deterministic"]
    )
    return FidelityCaseResult(
        case_id=str(case["case_id"]), intent_ok=checks["intent"], effect_ok=checks["effect"],
        approval_ok=checks["approval"], clarification_ok=checks["clarification"],
        capability_ok=checks["capability"], workstream_ok=checks["workstream"],
        mission_ir_ok=checks["mission_ir"], deterministic_ok=checks["deterministic"],
        hard_veto=hard_veto, observed_intent=compiled.intent.kind.value,
        observed_effect_class=compiled.mission_ir.effect_class, failures=failures,
    )


def _rate(items: Iterable[FidelityCaseResult], attr: str) -> float:
    source = tuple(items)
    return round(sum(bool(getattr(item, attr)) for item in source) / len(source), 6)


def evaluate_suite(
    path: str | Path = DEFAULT_CASES,
    compiler: Compiler = compile_owner_input,
    *,
    compiler_name: str = "CFBE-OMEGA-INPUT-COMPILER-V2",
) -> FidelitySuiteReport:
    results = tuple(evaluate_case(case, compiler) for case in load_cases(path))
    failed = tuple(item.case_id for item in results if not item.passed)
    hard_veto_count = sum(item.hard_veto for item in results)
    return FidelitySuiteReport(
        schema="CFBE-INPUT-COMPILER-FIDELITY-REPORT-V1",
        compiler_name=compiler_name,
        case_count=len(results), passed_cases=len(results) - len(failed),
        intent_accuracy=_rate(results, "intent_ok"), effect_accuracy=_rate(results, "effect_ok"),
        approval_accuracy=_rate(results, "approval_ok"), clarification_accuracy=_rate(results, "clarification_ok"),
        capability_coverage=_rate(results, "capability_ok"), workstream_coverage=_rate(results, "workstream_ok"),
        mission_ir_validity=_rate(results, "mission_ir_ok"), deterministic_rate=_rate(results, "deterministic_ok"),
        hard_veto_count=hard_veto_count,
        status="PASS" if not failed and hard_veto_count == 0 else "GAPS_CONFIRMED",
        failed_case_ids=failed, results=results,
    )
