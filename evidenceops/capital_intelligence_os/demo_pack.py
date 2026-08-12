from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
import json

from .models import stable_sha256
from .mvp_journey import MVPJourneyOrchestrator
from .qualification import InternalQualificationCourt
from .workspace import DecisionBriefBuilder


class _Recorder:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def record(self, **kwargs: Any) -> None:
        self.rows.append(dict(kwargs))


class CIOSDemoPackBuilder:
    """Generate a public-safe, explicitly synthetic CIOS demonstration pack."""

    def __init__(self, fixture_path: str | Path | None = None) -> None:
        self.fixture_path = Path(fixture_path) if fixture_path else (
            Path(__file__).parent / "fixtures" / "synthetic_mvp_deal_v1.json"
        )

    def build(self) -> dict[str, object]:
        payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        recorder = _Recorder()
        journey = MVPJourneyOrchestrator(outcome_recorder=recorder).run(payload)
        qualification = InternalQualificationCourt(self.fixture_path).run()
        if not journey.passed:
            raise RuntimeError("synthetic MVP journey did not pass")
        if not qualification.passed:
            raise RuntimeError("internal qualification court did not pass")

        decision_brief = DecisionBriefBuilder().build(
            title=f"Synthetic Investment Committee Brief — {journey.target_name}",
            verified_facts=[
                "SYNTHETIC FIXTURE: target fits the configured acquisition thesis.",
                f"SYNTHETIC FIXTURE: normalized EBITDA = {journey.normalized_ebitda:.2f}.",
                f"MODEL OUTPUT: DCF enterprise value = {journey.dcf_enterprise_value:.2f}.",
                f"MODEL OUTPUT: diligence completeness = {journey.diligence_score:.1%}.",
                f"EVIDENCE CONTROL: {journey.contradiction_count} contradiction(s) remain visible.",
            ],
            assumptions=[
                "All company, financial, market and transaction inputs in this demo are synthetic.",
                "Public-market probability is a simplified model proxy, not a fact or trading signal.",
                "The demo does not establish accounting, legal, tax or investment advice.",
            ],
            risks=[
                "Material evidence contradiction requires resolution before a real decision.",
                "Incomplete diligence lowers decision readiness.",
                "Integration and synergy outputs remain scenario/model outputs until observed outcomes exist.",
            ],
            alternatives=["BUY", "HOLD", "PASS", "BUILD", "PARTNER", "DO NOTHING"],
            recommendation=(
                f"Council advisory output: {journey.council_recommendation}. "
                "Final acquisition decision remains human-gated."
            ),
        )

        manifest: dict[str, object] = {
            "schema": "CIOS-SYNTHETIC-DEMO-PACK-V1",
            "classification": "PUBLIC_SAFE_SYNTHETIC_DEMONSTRATION",
            "deal_id": journey.deal_id,
            "target_name": journey.target_name,
            "journey_passed": journey.passed,
            "qualification_passed": qualification.passed,
            "qualification_score": qualification.score,
            "qualification_receipt_sha256": qualification.receipt_sha256,
            "target_score": journey.target_score,
            "contradiction_count": journey.contradiction_count,
            "diligence_score": journey.diligence_score,
            "normalized_ebitda": journey.normalized_ebitda,
            "dcf_enterprise_value": journey.dcf_enterprise_value,
            "comparable_range": [journey.comparable_low, journey.comparable_high],
            "equity_value": journey.equity_value,
            "irr": journey.irr,
            "market_fundamental_probability": journey.market_fundamental_probability,
            "market_implied_proxy": journey.market_implied_proxy,
            "market_expectation_gap": journey.market_expectation_gap,
            "market_fragility": journey.market_fragility,
            "council_recommendation": journey.council_recommendation,
            "passport_readiness": journey.passport_readiness,
            "transaction_readiness": journey.transaction_readiness,
            "day_one_readiness": journey.day_one_readiness,
            "synergy_realization": journey.synergy_realization,
            "value_leakage": journey.value_leakage,
            "authority": {
                "final_acquisition": journey.final_recommendation_disposition,
                "live_order": journey.live_order_disposition,
                "private_to_public_market": journey.private_to_market_disposition,
            },
            "outcome_recorded": journey.outcome_recorded,
            "learning_chain_valid": journey.learning_chain_valid,
            "truth_boundary": (
                "Every company, financial, transaction, market and outcome input in this pack is synthetic. "
                "The pack demonstrates software behavior and proof controls; it does not demonstrate investment performance, "
                "provider production deployment, real customer outcomes or professional advice."
            ),
        }
        manifest["manifest_sha256"] = stable_sha256(manifest)

        case_study = self._case_study(manifest, journey, qualification)
        files = {
            "manifest.json": json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            "decision_brief.json": json.dumps(decision_brief, indent=2, sort_keys=True) + "\n",
            "qualification_receipt.json": json.dumps(asdict(qualification), indent=2, sort_keys=True, default=str) + "\n",
            "case_study.md": case_study,
            "dashboard.html": journey.dashboard_html,
        }
        pack_digest = stable_sha256({name: stable_sha256(content) for name, content in sorted(files.items())})
        return {
            "manifest": manifest,
            "decision_brief": decision_brief,
            "qualification": asdict(qualification),
            "files": files,
            "pack_sha256": pack_digest,
        }

    def write(self, output_dir: str | Path) -> dict[str, object]:
        pack = self.build()
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
        for name, content in pack["files"].items():
            (root / name).write_text(str(content), encoding="utf-8")
        receipt = {
            "schema": "CIOS-SYNTHETIC-DEMO-WRITE-RECEIPT-V1",
            "output_dir": str(root),
            "files": sorted(pack["files"]),
            "pack_sha256": pack["pack_sha256"],
            "external_effects": False,
        }
        (root / "pack_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return receipt

    @staticmethod
    def _case_study(manifest: dict[str, object], journey, qualification) -> str:
        return f"""# EvidenceOps Capital Intelligence OS — Synthetic Acquisition Demonstration

> **SYNTHETIC DEMONSTRATION ONLY.** No real company, customer, investor, transaction or investment outcome is represented here.

## Problem
A transaction team needs to move from acquisition thesis through evidence, diligence, valuation, public-market context, decision review and integration planning without losing provenance or silently granting consequential authority to AI.

## Demonstrated route

`THESIS → TARGET GATE → EVIDENCE/CONTRADICTIONS → DILIGENCE → QoE → DCF/COMPS → MARKET CONTEXT → COUNCIL → HUMAN GATE → INTEGRATION → OUTCOME LEARNING`

## Synthetic result
- Target fit score: **{journey.target_score:.2f}/100**
- Visible contradictions: **{journey.contradiction_count}**
- Diligence completeness: **{journey.diligence_score:.1%}**
- Normalized EBITDA: **{journey.normalized_ebitda:.2f}**
- DCF enterprise value: **{journey.dcf_enterprise_value:.2f}**
- Comparable range: **{journey.comparable_low:.2f} – {journey.comparable_high:.2f}**
- Transaction readiness: **{journey.transaction_readiness:.1%}**
- Council advisory output: **{journey.council_recommendation}**

## Authority controls
- Final acquisition recommendation: **{journey.final_recommendation_disposition}**
- Live order: **{journey.live_order_disposition}**
- Private M&A → public market export: **{journey.private_to_market_disposition}**

The Council can advise, but the final acquisition remains human-gated. Live trading and private-to-market export remain denied.

## Qualification
The deterministic/synthetic qualification court passed **{qualification.score:.0%}** of its transparent checks with receipt `{qualification.receipt_sha256}`. It covers independent numeric oracles, monotonicity, evidence thresholds, diligence boundaries, strategy hard gates, authority boundaries and end-to-end counterfactuals.

This is **not** historical-deal calibration or evidence of real-world investment performance.

## Proof-safe claim
> Built an evidence-native M&A decision system with deterministic valuation/QoE/diligence engines, contradiction-preserving evidence controls, bounded market intelligence, human-gated recommendations and a reproducible synthetic end-to-end acquisition demonstration.

## Current limitation
Provider production deployment, enterprise identity/KMS/VDR controls, licensed market data, real historical calibration and customer pilot outcomes remain separately proof-gated.

## Pack integrity
Manifest digest: `{manifest['manifest_sha256']}`
"""
