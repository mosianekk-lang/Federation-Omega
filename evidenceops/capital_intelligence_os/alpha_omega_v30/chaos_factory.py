from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .sandbox_fleet import OperationalSandbox, SandboxTask


@dataclass(frozen=True)
class ChaosCase:
    name: str
    task: SandboxTask
    expected_status: str


class ChaosFactory:
    """Runs deterministic fault cases and proves that controls contain each fault."""

    def __init__(self, sandbox: OperationalSandbox):
        self.sandbox = sandbox

    def run(self, cases: Iterable[ChaosCase]) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for case in cases:
            outcome = self.sandbox.run(case.task)
            contained = outcome["status"] == case.expected_status and outcome["rollback_verified"]
            results.append(
                {
                    "name": case.name,
                    "expected_status": case.expected_status,
                    "actual_status": outcome["status"],
                    "contained": contained,
                    "ledger_entry_hash": outcome["ledger_entry_hash"],
                    "rollback_verified": outcome["rollback_verified"],
                }
            )
        total = len(results)
        contained_count = sum(item["contained"] for item in results)
        recovery_score = contained_count / total if total else 0.0
        return {
            "valid": total > 0 and contained_count == total,
            "cases": results,
            "recovery_score": recovery_score,
            "faults_tested": total,
        }
