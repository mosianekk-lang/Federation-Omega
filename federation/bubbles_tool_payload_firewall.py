from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re


_HEAVY_CONTENT_KINDS = frozenset(
    {"workflow_log", "provider_log", "repository_listing", "connector_schema"}
)
_FAILURE_LINE = re.compile(
    r"(?i)\b(error|fail(?:ed|ure)?|exception|traceback|timeout|denied|forbidden|"
    r"invalid|blocked|rejected|conclusion|returncode|exit code)\b"
)
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*([^\s,;]+)"
)
_AUTHORIZATION_VALUE = re.compile(
    r"(?i)\bauthorization\b\s*[:=]\s*(?!bearer\b)([^\s,;]+)"
)
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")


@dataclass(frozen=True, slots=True)
class ToolPayloadBudget:
    """Per-result budget applied before raw tool output is hydrated into chat."""

    max_raw_chars: int = 24_000
    max_raw_lines: int = 300
    max_diagnostic_chars: int = 12_000
    max_diagnostic_lines: int = 120
    tail_lines: int = 20

    def validate(self) -> None:
        values = (
            self.max_raw_chars,
            self.max_raw_lines,
            self.max_diagnostic_chars,
            self.max_diagnostic_lines,
            self.tail_lines,
        )
        if any(value <= 0 for value in values):
            raise ValueError("TOOL_PAYLOAD_BUDGET_POSITIVE_VALUES_REQUIRED")
        if self.max_diagnostic_chars > self.max_raw_chars:
            raise ValueError("TOOL_DIAGNOSTIC_CHAR_BUDGET_MUST_NOT_EXCEED_RAW_BUDGET")
        if self.max_diagnostic_lines > self.max_raw_lines:
            raise ValueError("TOOL_DIAGNOSTIC_LINE_BUDGET_MUST_NOT_EXCEED_RAW_BUDGET")


@dataclass(frozen=True, slots=True)
class ToolPayloadObservation:
    tool_name: str
    payload_chars: int
    line_count: int
    content_kind: str = "text"
    contains_sensitive_hint: bool = False


@dataclass(frozen=True, slots=True)
class ToolPayloadDecision:
    admit_raw: bool
    action: str
    diagnostic_required: bool
    reasons: tuple[str, ...]
    max_diagnostic_chars: int


class ToolPayloadFirewall:
    """Fail-small admission decision before large tool output reaches active chat.

    This object does not intercept ChatGPT connectors by itself. It provides the
    deterministic contract that a host/runtime adapter must enforce before raw
    output is hydrated into an interactive context.
    """

    def __init__(self, budget: ToolPayloadBudget | None = None) -> None:
        self.budget = budget or ToolPayloadBudget()
        self.budget.validate()

    def evaluate(self, observation: ToolPayloadObservation) -> ToolPayloadDecision:
        if not observation.tool_name:
            raise ValueError("TOOL_PAYLOAD_TOOL_NAME_REQUIRED")
        if observation.payload_chars < 0 or observation.line_count < 0:
            raise ValueError("TOOL_PAYLOAD_NONNEGATIVE_MEASUREMENTS_REQUIRED")

        reasons: list[str] = []
        if observation.payload_chars > self.budget.max_raw_chars:
            reasons.append("RAW_CHAR_BUDGET")
        if observation.line_count > self.budget.max_raw_lines:
            reasons.append("RAW_LINE_BUDGET")
        if (
            observation.content_kind in _HEAVY_CONTENT_KINDS
            and observation.payload_chars > self.budget.max_raw_chars // 2
        ):
            reasons.append("HEAVY_CONTENT_PREEMPTION")
        if observation.contains_sensitive_hint:
            reasons.append("SENSITIVE_CONTENT_HINT")

        if reasons:
            action = (
                "REDACT_AND_EXTRACT_DIAGNOSTIC"
                if observation.contains_sensitive_hint
                else "EXTRACT_BOUNDED_DIAGNOSTIC"
            )
            return ToolPayloadDecision(
                admit_raw=False,
                action=action,
                diagnostic_required=True,
                reasons=tuple(sorted(set(reasons))),
                max_diagnostic_chars=self.budget.max_diagnostic_chars,
            )

        return ToolPayloadDecision(
            admit_raw=True,
            action="ADMIT_RAW",
            diagnostic_required=False,
            reasons=(),
            max_diagnostic_chars=self.budget.max_diagnostic_chars,
        )


@dataclass(frozen=True, slots=True)
class DiagnosticCapsule:
    raw_sha256: str
    raw_chars: int
    raw_lines: int
    selected_lines: int
    truncated: bool
    redaction_applied: bool
    excerpt: str


class DiagnosticExtractor:
    """Produce a bounded, redacted failure-oriented view of a large text result."""

    def __init__(self, budget: ToolPayloadBudget | None = None) -> None:
        self.budget = budget or ToolPayloadBudget()
        self.budget.validate()

    @staticmethod
    def _redact(line: str) -> tuple[str, bool]:
        redacted = False

        line, bearer_count = _BEARER.subn("Bearer [REDACTED]", line)
        if bearer_count:
            redacted = True

        def replace_authorization(match: re.Match[str]) -> str:
            nonlocal redacted
            redacted = True
            return "Authorization=[REDACTED]"

        line = _AUTHORIZATION_VALUE.sub(replace_authorization, line)

        def replace_assignment(match: re.Match[str]) -> str:
            nonlocal redacted
            redacted = True
            return f"{match.group(1)}=[REDACTED]"

        line = _SECRET_ASSIGNMENT.sub(replace_assignment, line)
        return line, redacted

    def extract(self, payload: str) -> DiagnosticCapsule:
        text = str(payload)
        lines = text.splitlines()
        raw_sha = sha256(text.encode("utf-8")).hexdigest()

        selected_indexes: list[int] = []
        seen: set[int] = set()

        def add(index: int) -> None:
            if 0 <= index < len(lines) and index not in seen:
                seen.add(index)
                selected_indexes.append(index)

        for index, line in enumerate(lines):
            if _FAILURE_LINE.search(line):
                add(index - 1)
                add(index)
                add(index + 1)
            if len(selected_indexes) >= self.budget.max_diagnostic_lines:
                break

        tail_start = max(0, len(lines) - self.budget.tail_lines)
        for index in range(tail_start, len(lines)):
            if len(selected_indexes) >= self.budget.max_diagnostic_lines:
                break
            add(index)

        selected_indexes.sort()
        output_lines: list[str] = []
        redaction_applied = False
        output_chars = 0
        for index in selected_indexes:
            line, line_redacted = self._redact(lines[index])
            redaction_applied = redaction_applied or line_redacted
            rendered = f"L{index + 1}: {line}"
            projected = output_chars + len(rendered) + (1 if output_lines else 0)
            if projected > self.budget.max_diagnostic_chars:
                break
            output_lines.append(rendered)
            output_chars = projected

        excerpt = "\n".join(output_lines)
        truncated = len(output_lines) < len(selected_indexes) or len(selected_indexes) < len(lines)
        return DiagnosticCapsule(
            raw_sha256=raw_sha,
            raw_chars=len(text),
            raw_lines=len(lines),
            selected_lines=len(output_lines),
            truncated=truncated,
            redaction_applied=redaction_applied,
            excerpt=excerpt,
        )
