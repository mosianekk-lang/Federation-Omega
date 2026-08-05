from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from federation_learning import LearningFabric

from .evolution import AlgorithmLedger, EvolutionGovernor
from .foundry_cycle import execute_foundry_cycle
from .foundry_learning import FoundryLearningMixin
from .foundry_model import FoundryCycleResult
from .registry import InnovationRegistry


class EvidenceOpsAlgorithmFoundry(FoundryLearningMixin):
    """Formation + Alpha-to-Omega compiler for EvidenceOps algorithms."""

    system_id = "EVIDENCEOPS-ALGORITHM-FOUNDRY"
    workflow_id = "MASTER-BIBLE-ALGORITHM-COMPILATION"
    mission_id = "EVIDENCEOPS-CONTINUOUS-ALGORITHM-EVOLUTION"

    def __init__(
        self,
        workspace: str | Path,
        *,
        learning_policy_path: str | Path,
        catalog_path: str | Path | None = None,
    ) -> None:
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.learning = LearningFabric(self.workspace / "learning", policy_path=learning_policy_path)
        self.registry = InnovationRegistry(self.workspace / "innovation.db")
        self.algorithm_ledger = AlgorithmLedger(self.workspace / "algorithm_evolution.db")
        self.evolution = EvolutionGovernor(self.algorithm_ledger)
        self.catalog_path = Path(catalog_path) if catalog_path else Path(__file__).with_name("algorithm_catalog.json")
        self.catalog = json.loads(self.catalog_path.read_text(encoding="utf-8"))

    def execute_cycle(self, payload: Mapping[str, Any]) -> FoundryCycleResult:
        return execute_foundry_cycle(self, payload)


__all__ = ["EvidenceOpsAlgorithmFoundry", "FoundryCycleResult"]
