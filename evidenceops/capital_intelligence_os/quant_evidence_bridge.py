from __future__ import annotations

from typing import Any, Mapping

from .capital_intent import QuantResearchEvidence


REQUIRED_METRICS = {
    "total_return_pct",
    "benchmark_return_pct",
    "maximum_drawdown_pct",
    "sharpe_ratio",
    "sample_trades",
    "robustness_score",
    "regime_fit",
    "liquidity_quality",
}


def project_quant_evidence(payload: Mapping[str, Any]) -> QuantResearchEvidence:
    """Project a proof-bearing Quant Evidence Fabric record into CIOS without authority inheritance."""
    for key in ("strategy_id", "instrument_id", "evidence_ref", "research_state", "metrics"):
        if key not in payload:
            raise ValueError(f"missing quant evidence field: {key}")
    metrics = payload["metrics"]
    if not isinstance(metrics, Mapping):
        raise ValueError("metrics must be a mapping")
    missing = sorted(REQUIRED_METRICS.difference(metrics))
    if missing:
        raise ValueError(f"missing quant evidence metrics: {','.join(missing)}")
    if payload.get("provider_effect") is True or payload.get("financial_effect") is True:
        raise PermissionError("QUANT_EVIDENCE_PROJECTION_CANNOT_IMPORT_FINANCIAL_AUTHORITY")
    evidence = QuantResearchEvidence(
        strategy_id=str(payload["strategy_id"]),
        instrument_id=str(payload["instrument_id"]),
        evidence_ref=str(payload["evidence_ref"]),
        research_state=str(payload["research_state"]),
        expected_return_pct=float(metrics["total_return_pct"]),
        benchmark_return_pct=float(metrics["benchmark_return_pct"]),
        maximum_drawdown_pct=float(metrics["maximum_drawdown_pct"]),
        sharpe_ratio=float(metrics["sharpe_ratio"]),
        sample_trades=int(metrics["sample_trades"]),
        robustness_score=float(metrics["robustness_score"]),
        regime_fit=float(metrics["regime_fit"]),
        liquidity_quality=float(metrics["liquidity_quality"]),
        uncertainty=float(metrics.get("uncertainty", 0.0)),
        metadata={
            "source_code_sha256": payload.get("source_code_sha256"),
            "report_id": payload.get("report_id"),
            "experiment_id": payload.get("experiment_id"),
            "authority_inherited": False,
        },
    )
    evidence.validate()
    return evidence
