from __future__ import annotations

from dataclasses import dataclass

from .objective import ObjectiveContract


@dataclass(frozen=True)
class IntegrityDecision:
    preserved: bool
    violations: tuple[str, ...]


class ObjectiveIntegrityKernel:
    """Separates immutable outcome semantics from replaceable execution routes."""
    def compare(self, canonical: ObjectiveContract, candidate: ObjectiveContract) -> IntegrityDecision:
        violations: list[str] = []
        if candidate.objective != canonical.objective:
            violations.append("OBJECTIVE_MUTATED")
        missing = set(canonical.mandatory_requirements) - set(candidate.mandatory_requirements)
        if missing:
            violations.append("MANDATORY_REQUIREMENT_DROPPED:" + ",".join(sorted(missing)))
        missing_tests = set(canonical.acceptance_tests) - set(candidate.acceptance_tests)
        if missing_tests:
            violations.append("ACCEPTANCE_TEST_WEAKENED:" + ",".join(sorted(missing_tests)))
        missing_bans = set(canonical.prohibited_substitutions) - set(candidate.prohibited_substitutions)
        if missing_bans:
            violations.append("PROHIBITED_SUBSTITUTION_REMOVED:" + ",".join(sorted(missing_bans)))
        missing_invariants = set(canonical.invariants) - set(candidate.invariants)
        if missing_invariants:
            violations.append("INVARIANT_REMOVED:" + ",".join(sorted(missing_invariants)))
        return IntegrityDecision(not violations, tuple(violations))
