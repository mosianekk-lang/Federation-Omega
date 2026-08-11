from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from .evidenceops_adapter import run_case_cycle


class EvidenceOpsInnovationRunner:
    """Callable bridge for the EvidenceOps↔FEVX adapter's derived-only hook."""

    def __init__(
        self,
        *,
        master_bible_path: str | Path,
        workspace: str | Path,
        learning_policy_path: str | Path,
        failure_lessons: Sequence[Mapping[str, Any]] = (),
    ) -> None:
        self.master_bible_path = Path(master_bible_path)
        self.workspace = Path(workspace)
        self.learning_policy_path = Path(learning_policy_path)
        self.failure_lessons = tuple(dict(item) for item in failure_lessons)

    runner_id = "EVIDENCEOPS-ALGORITHM-FOUNDRY-BRIDGE-V1"

    def identity(self) -> dict[str, Any]:
        return {
            "runner_id": self.runner_id,
            "master_bible_sha256": __import__("hashlib").sha256(
                self.master_bible_path.read_bytes()
            ).hexdigest(),
            "learning_policy_sha256": __import__("hashlib").sha256(
                self.learning_policy_path.read_bytes()
            ).hexdigest(),
            "failure_lesson_count": len(self.failure_lessons),
            "authority_ceiling": "A1_INTERNAL",
            "external_effect": False,
        }

    def __call__(self, packet: dict[str, Any]) -> dict[str, Any]:
        result = run_case_cycle(
            packet,
            master_bible_text=self.master_bible_path.read_text(encoding="utf-8"),
            workspace=self.workspace,
            learning_policy_path=self.learning_policy_path,
            failure_lessons=self.failure_lessons,
        )
        return {
            "state": result["status"],
            "maturity": result["maturity"],
            "cycle_id": result["cycle_id"],
            "algorithm_count": len(result["algorithm_results"]),
            "opportunity_count": result["opportunity_count"],
            "innovation_delta": result["innovation_delta"],
            "learning_delta": result["learning_delta"],
            "proof": result["proof"],
            "result_receipt_sha256": result["receipt_sha256"],
            "adapter_result_sha256": result["adapter_result_sha256"],
            "authority_ceiling": "A1_INTERNAL",
            "external_effect": False,
            "source_write": False,
            "verified_fact_write": False,
            "case_wall_crossing": False,
            "release_state": "HELD_FOR_EVIDENCEOPS_REVIEW",
        }
