from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from .core import BenchmarkEvaluation, evaluate_benchmark


AUTHORITY_CEILING = "A1_INTERNAL"
CONTROL_MARKER = "__CASEFORGE_HIDDEN_CONTROL__"
RESERVED_CONTROL_KEYS = frozenset(
    {
        "answer_key",
        "control_pack",
        "control_path",
        "expected_answer",
        "expected_outcome",
        "expected_winner",
        "fatal_tests",
        "scoring_requirements",
        "scoring_rubric",
    }
)


def _key_token(value: Any) -> str:
    return "".join(character for character in str(value).strip().lower() if character.isalnum())


RESERVED_CONTROL_TOKENS = frozenset(_key_token(key) for key in RESERVED_CONTROL_KEYS)


class BlindIsolationError(ValueError):
    """Raised when the tested-agent/scorer separation is violated."""


def _canonical_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    except (TypeError, ValueError) as exc:
        raise BlindIsolationError("blind experiment payload is not canonical JSON") from exc
    return text.encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _find_control_leaks(value: Any, *, path: str = "$") -> tuple[str, ...]:
    leaks: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{path}.{key}"
            if _key_token(key) in RESERVED_CONTROL_TOKENS:
                leaks.append(child)
            leaks.extend(_find_control_leaks(item, path=child))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            leaks.extend(_find_control_leaks(item, path=f"{path}[{index}]"))
    elif isinstance(value, str) and CONTROL_MARKER in value:
        leaks.append(path)
    return tuple(leaks)


def assert_blind_payload(payload: Mapping[str, Any]) -> str:
    """Fail closed if hidden scoring/control material leaked into the blind pack."""
    leaks = _find_control_leaks(payload)
    if leaks:
        raise BlindIsolationError("hidden control leakage detected at: " + ",".join(leaks))
    return _digest(payload)


@dataclass(frozen=True)
class ModelBinding:
    provider: str
    model: str
    version: str
    configuration: Mapping[str, Any]
    execution_state: str = "DETERMINISTIC_TEST_ONLY"
    provider_readback_ref: str = ""

    def validate(self) -> None:
        if not self.provider.strip() or not self.model.strip() or not self.version.strip():
            raise BlindIsolationError("provider, model and version are required")
        if self.execution_state not in {"DETERMINISTIC_TEST_ONLY", "PROVIDER_VERIFIED"}:
            raise BlindIsolationError("unsupported model execution state")
        if self.execution_state == "PROVIDER_VERIFIED" and not self.provider_readback_ref.strip():
            raise BlindIsolationError("provider-verified execution requires provider readback")

    @property
    def configuration_sha256(self) -> str:
        return _digest(self.configuration)


@dataclass(frozen=True)
class AgentContext:
    run_id: str
    case_id: str
    blind_input_sha256: str
    provider: str
    model: str
    version: str
    configuration_sha256: str
    execution_state: str
    provider_readback_ref: str
    authority_ceiling: str = AUTHORITY_CEILING
    external_effect: bool = False


class TestedAgent(Protocol):
    def analyze(self, blind_payload: Mapping[str, Any], context: AgentContext) -> Any: ...


@dataclass(frozen=True)
class BlindRunReceipt:
    run_id: str
    case_id: str
    blind_input_sha256: str
    tested_output_sha256: str
    tested_output: Any
    provider: str
    model: str
    version: str
    configuration_sha256: str
    execution_state: str
    provider_readback_ref: str
    input_unchanged: bool
    authority_ceiling: str = AUTHORITY_CEILING
    external_effect: bool = False


class IsolatedBlindRunner:
    """Give the tested agent only the blind packet and a control-free context.

    This is a deterministic interface-isolation contract. It does not claim
    process, container, provider or model isolation until a provider-bound
    canary and independent readback prove those stronger states.
    """

    def run(
        self,
        *,
        run_id: str,
        blind_payload: Mapping[str, Any],
        agent: TestedAgent,
        model_binding: ModelBinding,
    ) -> BlindRunReceipt:
        if not run_id.strip():
            raise BlindIsolationError("run_id is required")
        model_binding.validate()
        blind_hash = assert_blind_payload(blind_payload)
        case_id = str(blind_payload.get("case_id", "")).strip()
        if not case_id:
            raise BlindIsolationError("blind payload requires case_id")

        # Canonical JSON round-trip creates a detached JSON-only object. The
        # tested agent receives no scorer object, control path or control pack.
        agent_payload = json.loads(_canonical_bytes(blind_payload).decode("utf-8"))
        context = AgentContext(
            run_id=run_id,
            case_id=case_id,
            blind_input_sha256=blind_hash,
            provider=model_binding.provider,
            model=model_binding.model,
            version=model_binding.version,
            configuration_sha256=model_binding.configuration_sha256,
            execution_state=model_binding.execution_state,
            provider_readback_ref=model_binding.provider_readback_ref,
        )
        output = agent.analyze(agent_payload, context)
        output_snapshot = json.loads(_canonical_bytes(output).decode("utf-8"))
        input_unchanged = _digest(agent_payload) == blind_hash
        if not input_unchanged:
            raise BlindIsolationError("tested agent mutated the blind input")

        return BlindRunReceipt(
            run_id=run_id,
            case_id=case_id,
            blind_input_sha256=blind_hash,
            tested_output_sha256=_digest(output_snapshot),
            tested_output=output_snapshot,
            provider=model_binding.provider,
            model=model_binding.model,
            version=model_binding.version,
            configuration_sha256=model_binding.configuration_sha256,
            execution_state=model_binding.execution_state,
            provider_readback_ref=model_binding.provider_readback_ref,
            input_unchanged=True,
        )


@dataclass(frozen=True)
class ScoringReceipt:
    scorer_id: str
    scorer_version: str
    run_id: str
    case_id: str
    blind_input_sha256: str
    tested_output_sha256: str
    control_sha256: str
    score: float
    decision: str
    fatal_failures: tuple[str, ...]
    output_unchanged_by_scorer: bool
    authority_ceiling: str = AUTHORITY_CEILING
    external_effect: bool = False


class HiddenControlScorer:
    """Hold the control pack outside the tested-agent interface."""

    def __init__(
        self,
        *,
        scorer_id: str,
        scorer_version: str,
        control_pack: Mapping[str, Any],
    ) -> None:
        if not scorer_id.strip() or not scorer_version.strip():
            raise BlindIsolationError("scorer identity and version are required")
        case_id = str(control_pack.get("case_id", "")).strip()
        if not case_id:
            raise BlindIsolationError("control pack requires case_id")
        self.scorer_id = scorer_id
        self.scorer_version = scorer_version
        self._control = json.loads(_canonical_bytes(control_pack).decode("utf-8"))
        self._control_sha256 = _digest(self._control)
        self._case_id = case_id

    @property
    def control_sha256(self) -> str:
        return self._control_sha256

    def score(
        self,
        *,
        blind_run: BlindRunReceipt,
        competency_scores: Mapping[str, float],
        fatal_events: Sequence[str] = (),
    ) -> ScoringReceipt:
        if blind_run.case_id != self._case_id:
            raise BlindIsolationError("blind/control case mismatch")
        output_before = _digest(blind_run.tested_output)
        evaluation: BenchmarkEvaluation = evaluate_benchmark(
            competency_scores,
            fatal_events=fatal_events,
        )
        output_after = _digest(blind_run.tested_output)
        return ScoringReceipt(
            scorer_id=self.scorer_id,
            scorer_version=self.scorer_version,
            run_id=blind_run.run_id,
            case_id=blind_run.case_id,
            blind_input_sha256=blind_run.blind_input_sha256,
            tested_output_sha256=blind_run.tested_output_sha256,
            control_sha256=self._control_sha256,
            score=evaluation.score,
            decision=evaluation.decision,
            fatal_failures=evaluation.fatal_failures,
            output_unchanged_by_scorer=output_before == output_after,
        )


__all__ = [
    "AgentContext",
    "BlindIsolationError",
    "BlindRunReceipt",
    "CONTROL_MARKER",
    "HiddenControlScorer",
    "IsolatedBlindRunner",
    "ModelBinding",
    "RESERVED_CONTROL_KEYS",
    "RESERVED_CONTROL_TOKENS",
    "ScoringReceipt",
    "TestedAgent",
    "assert_blind_payload",
]
