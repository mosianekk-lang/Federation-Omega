from __future__ import annotations

from pathlib import Path

from .progressive_execution import ProgressiveExecutionMixin
from .progressive_formation import FormationInnovationEngine
from .progressive_ledger import HashLinkedLearningLedger
from .progressive_models import WaveExecutionReceipt
from .progressive_planning import ProgressivePlanningMixin
from .progressive_scheduler import MultiStreamScheduler


class ProgressiveAlphaOmega(ProgressivePlanningMixin, ProgressiveExecutionMixin):
    """Formation Innovation + Alpha→Omega multi-path/multi-stream runtime."""

    def __init__(
        self,
        workspace: str | Path,
        *,
        max_parallel_safe: int = 8,
        failure_threshold: int = 2,
    ) -> None:
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.checkpoints = self.workspace / "progressive_checkpoints"
        self.checkpoints.mkdir(exist_ok=True)
        self.learning = HashLinkedLearningLedger(
            self.workspace / "progressive_learning.jsonl"
        )
        self.formation = FormationInnovationEngine()
        self.scheduler = MultiStreamScheduler(
            max_parallel_safe,
            failure_threshold,
        )
        self._reuse_hits = 0
        self._work_units_avoided = 0
        self.last_wave_receipt: WaveExecutionReceipt | None = None
