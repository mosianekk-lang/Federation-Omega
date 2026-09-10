"""Evidence-gated commercial/production maturity planner."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping


DEFAULT_STAGES=(
    "FUNCTIONALITY","SECURITY","PRIVACY","RELIABILITY","PERFORMANCE","SCALABILITY",
    "COST","OBSERVABILITY","RECOVERY","INSTALL_DEPLOY","UPGRADE","ROLLBACK",
    "DOCUMENTATION","UX","SUPPORTABILITY","LICENSING_DEPENDENCIES","RELEASE_REPRODUCIBILITY"
)


@dataclass(frozen=True, slots=True)
class MaturityCourt:
    applicable: tuple[str,...]
    passed: tuple[str,...]
    failed: tuple[str,...]
    missing: tuple[str,...]
    state: str


class CommercialMaturityController:
    def __init__(self, applicable: tuple[str,...]=DEFAULT_STAGES):
        if not applicable: raise ValueError("APPLICABLE_MATURITY_GATES_REQUIRED")
        self.applicable=tuple(dict.fromkeys(applicable))
    def evaluate(self, evidence: Mapping[str,bool]) -> MaturityCourt:
        passed=tuple(x for x in self.applicable if evidence.get(x) is True)
        failed=tuple(x for x in self.applicable if evidence.get(x) is False)
        missing=tuple(x for x in self.applicable if x not in evidence)
        state="COMMERCIAL_READY_VERIFIED" if len(passed)==len(self.applicable) and not failed and not missing else "COMMERCIAL_MATURITY_OPEN"
        return MaturityCourt(self.applicable,passed,failed,missing,state)
    def next_gates(self, evidence: Mapping[str,bool], limit:int=4) -> tuple[str,...]:
        court=self.evaluate(evidence)
        return (court.failed+court.missing)[:limit]
