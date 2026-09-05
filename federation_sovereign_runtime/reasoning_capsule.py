from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Iterable

from .core import stable_hash


@dataclass(frozen=True)
class ReasoningCapsule:
    """Provider-neutral mission rationale, not hidden chain-of-thought.

    The capsule stores decision-relevant state needed for durable continuation:
    conclusions, assumptions, evidence references, unresolved questions and the
    next concrete action. It deliberately excludes private model scratchpads.
    """

    capsule_id: str
    mission_id: str
    objective: str
    conclusions: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    unresolved_questions: tuple[str, ...] = ()
    rejected_routes: tuple[str, ...] = ()
    next_action: str = ""
    reasoning_effort: str = ""
    processor_ref: str = ""
    predecessor_sha256: str = ""
    version: int = 1

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.capsule_id.strip():
            errors.append("CAPSULE_ID_REQUIRED")
        if not self.mission_id.strip():
            errors.append("MISSION_ID_REQUIRED")
        if not self.objective.strip():
            errors.append("OBJECTIVE_REQUIRED")
        return tuple(errors)

    @property
    def sha256(self) -> str:
        return stable_hash(asdict(self))

    def successor(
        self,
        *,
        conclusions: Iterable[str] = (),
        assumptions: Iterable[str] = (),
        evidence_refs: Iterable[str] = (),
        unresolved_questions: Iterable[str] = (),
        rejected_routes: Iterable[str] = (),
        next_action: str | None = None,
        reasoning_effort: str | None = None,
        processor_ref: str | None = None,
    ) -> "ReasoningCapsule":
        def merged(existing: tuple[str, ...], new: Iterable[str]) -> tuple[str, ...]:
            return tuple(dict.fromkeys((*existing, *(item for item in new if item))))

        return replace(
            self,
            conclusions=merged(self.conclusions, conclusions),
            assumptions=merged(self.assumptions, assumptions),
            evidence_refs=merged(self.evidence_refs, evidence_refs),
            unresolved_questions=merged(self.unresolved_questions, unresolved_questions),
            rejected_routes=merged(self.rejected_routes, rejected_routes),
            next_action=self.next_action if next_action is None else next_action,
            reasoning_effort=self.reasoning_effort if reasoning_effort is None else reasoning_effort,
            processor_ref=self.processor_ref if processor_ref is None else processor_ref,
            predecessor_sha256=self.sha256,
            version=self.version + 1,
        )

    def compact(self, *, max_items_per_field: int = 12) -> "ReasoningCapsule":
        if max_items_per_field < 1:
            raise ValueError("MAX_ITEMS_PER_FIELD_MUST_BE_POSITIVE")

        def tail(values: tuple[str, ...]) -> tuple[str, ...]:
            return values[-max_items_per_field:]

        # Evidence is never truncated here; evidence references are proof state,
        # not conversational verbosity. Callers may externalize them but not
        # silently drop them.
        return replace(
            self,
            conclusions=tail(self.conclusions),
            assumptions=tail(self.assumptions),
            unresolved_questions=tail(self.unresolved_questions),
            rejected_routes=tail(self.rejected_routes),
            predecessor_sha256=self.sha256,
            version=self.version + 1,
        )


__all__ = ["ReasoningCapsule"]
