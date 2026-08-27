from __future__ import annotations

from dataclasses import dataclass

from .models import stable_sha256


_REASON_TO_DIMENSION = {
    "NO_POSITIVE_EXCESS_RETURN": "benchmark_participation",
    "MATERIAL_BENCHMARK_UNDERPERFORMANCE": "benchmark_participation",
    "SAMPLE_TOO_SMALL": "entry_exit_frequency",
    "HOLDOUT_SAMPLE_TOO_SMALL": "entry_exit_frequency",
    "SLIPPAGE_LIMIT": "execution_cost_model",
    "SLIPPAGE_LIMIT_BREACHED": "execution_cost_model",
    "SPREAD_LIMIT": "execution_cost_model",
    "DEPTH_LIMIT": "liquidity_sizing",
    "INSUFFICIENT_ORDER_BOOK_DEPTH": "liquidity_sizing",
    "STALE_MARKET_DATA": "data_freshness",
    "RECONCILIATION_UNHEALTHY": "execution_reconciliation",
    "REQUEST_BINDING_MISMATCH": "execution_reconciliation",
    "SNAPSHOT_BINDING_MISMATCH": "execution_reconciliation",
    "CROSS_ASSET_GENERALISATION_FAILURE": "regime_adaptation",
}


@dataclass(frozen=True)
class ExecutionFailureMutation:
    parent_id: str
    evidence_ref: str
    reason_codes: tuple[str, ...]
    changed_dimensions: tuple[str, ...]
    hypothesis: str
    mutation_id: str
    material_change_required: bool = True
    auto_promote: bool = False
    external_effect: bool = False
    financial_effect: bool = False


class ExecutionFailureWinBridge:
    """Turns observed capital/execution failures into bounded mutation hypotheses only."""

    def propose(self, *, parent_id: str, evidence_ref: str, reason_codes: tuple[str, ...]) -> ExecutionFailureMutation:
        if not parent_id or not evidence_ref:
            raise ValueError("parent_id and evidence_ref are required")
        reasons = tuple(sorted(set(reason_codes)))
        if not reasons:
            raise ValueError("at least one failure reason is required")
        dimensions = tuple(sorted({_REASON_TO_DIMENSION.get(reason, "single_material_hypothesis") for reason in reasons}))
        hypothesis = "; ".join(f"change {dimension} because evidence recorded {','.join(reason for reason in reasons if _REASON_TO_DIMENSION.get(reason, 'single_material_hypothesis') == dimension)}" for dimension in dimensions)
        seed = {"parent_id": parent_id, "evidence_ref": evidence_ref, "reason_codes": reasons, "changed_dimensions": dimensions}
        return ExecutionFailureMutation(parent_id, evidence_ref, reasons, dimensions, hypothesis, "FW-" + stable_sha256(seed)[:20])
