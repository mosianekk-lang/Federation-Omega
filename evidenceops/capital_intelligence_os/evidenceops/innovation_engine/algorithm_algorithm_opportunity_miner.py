from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .algorithms_common import (
    AUTHORITY_CEILING, AlgorithmOpportunity, AlgorithmResult, clamp, number,
    sequence, sha256, text, unique_text,
)

class AlgorithmOpportunityMiner:
    """Detect repeated lessons that justify a reusable algorithm.

    The miner is intentionally deterministic. It does not infer that a new
    runtime exists; it identifies source-backed build opportunities and records
    why they deserve a bounded implementation or experiment.
    """

    algorithm_id = "ALG-EOPS-AOM-001"
    name = "Algorithm Opportunity Miner"

    _families: Mapping[str, Mapping[str, Any]] = {
        "ALG-EOPS-DEC-001": {
            "title": "Directive Execution Compiler",
            "family": "ACTION_VERB_AND_OUTCOME_INTEGRITY",
            "tokens": (
                "action verb", "artifact action", "send", "execute", "activate",
                "tool routing", "premature turn", "status-only", "directive",
            ),
        },
        "ALG-EOPS-CPDG-001": {
            "title": "Claim-Proof Distance Guard",
            "family": "CLAIM_AND_EVIDENCE_INTEGRITY",
            "tokens": (
                "proof missing", "unsupported claim", "inference as fact",
                "readback absent", "claim-proof", "false completion", "evidence",
            ),
        },
        "ALG-EOPS-UFP-001": {
            "title": "Unknown Frontier Prioritizer",
            "family": "UNKNOWN_AND_GAP_DISCOVERY",
            "tokens": (
                "unknown", "missing record", "gap", "assumption", "contradiction",
                "epistemic debt", "unlocated", "blind spot",
            ),
        },
        "ALG-EOPS-IGRS-001": {
            "title": "Information-Gain Route Selector",
            "family": "EXPERIMENT_AND_ROUTE_SELECTION",
            "tokens": (
                "information gain", "experiment", "reversible test", "route selection",
                "counterfactual", "probe", "smallest safe", "next proof",
            ),
        },
        "ALG-EOPS-TFR-001": {
            "title": "Terminal Finality Resolver",
            "family": "TERMINAL_FINALITY",
            "tokens": (
                "terminal finality", "pending", "unresolved", "queued", "blocked",
                "unknown state", "non-production", "terminal receipt",
            ),
        },
        "ALG-EOPS-CSIE-001": {
            "title": "Corpus Selection Integrity Evaluator",
            "family": "EXHAUSTIVE_CORPUS_AND_SELECTION",
            "tokens": (
                "ecasp", "exhaustive", "best", "final", "full corpus", "body retrieval",
                "inventory complete", "selection integrity", "g1-g10",
            ),
        },
        "ALG-EOPS-CPIG-001": {
            "title": "Control-Plane Integrity Guard",
            "family": "SCHEMA_ID_LEASE_AND_COLLISION_INTEGRITY",
            "tokens": (
                "schema", "foreign key", "cycle id", "collision", "lease epoch",
                "packet key", "revision drift", "attestation", "reservation",
            ),
        },
        "ALG-EOPS-ASPV-001": {
            "title": "Action-Specific Proof Validator",
            "family": "ACTION_SPECIFIC_PROVIDER_PROOF",
            "tokens": (
                "generic health", "http 200", "provider response", "semantic readback",
                "action-specific", "queued is not executed", "runtime health",
            ),
        },
        "ALG-EOPS-FEGC-001": {
            "title": "Failure-to-Engineering-Gene Compiler",
            "family": "FAILURE_LEARNING_AND_REUSE",
            "tokens": (
                "failure", "recovery", "regression test", "engineering gene",
                "negative result", "root cause", "repair", "cognitive antibody",
            ),
        },
        "ALG-EOPS-EVG-001": {
            "title": "EvidenceOps Evolution Governor",
            "family": "MEASURABLE_CONTINUOUS_EVOLUTION",
            "tokens": (
                "performance delta", "continuous learning", "evolution", "promotion",
                "baseline", "measurable improvement", "rollback", "calibration",
            ),
        },
        "ALG-EOPS-PSTG-001": {
            "title": "Proof-State Transition Guard",
            "family": "MATURITY_AND_PROOF_STATE_INTEGRITY",
            "tokens": (
                "design as runtime", "maturity state", "proof state", "promotion gate",
                "staged not running", "state transition", "false promotion",
            ),
        },
        "ALG-EOPS-EDP-001": {
            "title": "Epistemic Debt Prioritizer",
            "family": "EPISTEMIC_DEBT",
            "tokens": (
                "epistemic debt", "weak evidence", "untested assumption",
                "missing baseline", "unreplicated finding", "causal uncertainty",
            ),
        },
        "ALG-EOPS-OBRO-001": {
            "title": "Owner-Burden Route Optimizer",
            "family": "ROUTE_ECONOMICS_AND_OWNER_BURDEN",
            "tokens": (
                "owner burden", "owner-burden", "manual handoff", "route economics",
                "zero recurring owner burden", "owner intervention",
            ),
        },
        "ALG-EOPS-CIRE-001": {
            "title": "Cross-Implementation Replication Evaluator",
            "family": "REPRODUCIBILITY_AND_INDEPENDENT_IMPLEMENTATION",
            "tokens": (
                "replication", "independent implementation", "reproducibility",
                "cross-domain", "r3", "replicated finding",
            ),
        },
    }

    def run(self, signals: Sequence[Mapping[str, Any]]) -> AlgorithmResult:
        aggregates: dict[str, dict[str, Any]] = {
            algorithm_id: {
                "weighted_signal": 0.0,
                "count": 0,
                "evidence_refs": set(),
                "matched_tokens": set(),
            }
            for algorithm_id in self._families
        }

        for index, signal in enumerate(signals):
            rendered = " ".join(
                text(signal.get(key))
                for key in ("summary", "lesson", "failure", "opportunity", "details")
            ).lower()
            repetition = max(1.0, number(signal.get("repetition"), 1.0))
            impact = clamp(number(signal.get("impact"), 0.7))
            uncertainty = clamp(number(signal.get("uncertainty"), 0.6))
            reuse = clamp(number(signal.get("reuse_potential"), 0.7))
            cost = max(0.05, clamp(number(signal.get("implementation_cost"), 0.25)))
            weight = (impact * (0.5 + uncertainty) * (0.5 + reuse) * repetition) / (1.0 + cost)
            refs = unique_text(sequence(signal.get("evidence_refs")))
            if not refs:
                refs = [f"signal:{signal.get('signal_id', index + 1)}"]

            for algorithm_id, definition in self._families.items():
                matched = {token for token in definition["tokens"] if token in rendered}
                if not matched:
                    continue
                row = aggregates[algorithm_id]
                row["weighted_signal"] += weight * (1.0 + min(3, len(matched)) * 0.15)
                row["count"] += 1
                row["evidence_refs"].update(refs)
                row["matched_tokens"].update(matched)

        opportunities: list[AlgorithmOpportunity] = []
        for algorithm_id, aggregate in aggregates.items():
            if aggregate["count"] == 0:
                continue
            definition = self._families[algorithm_id]
            normalized = round(min(100.0, aggregate["weighted_signal"] * 10.0), 4)
            opportunities.append(
                AlgorithmOpportunity(
                    algorithm_id=algorithm_id,
                    title=str(definition["title"]),
                    problem_family=str(definition["family"]),
                    score=normalized,
                    signal_count=int(aggregate["count"]),
                    evidence_refs=tuple(sorted(aggregate["evidence_refs"])),
                    reason=(
                        "Repeated source-backed signals matched: "
                        + ", ".join(sorted(aggregate["matched_tokens"]))
                    ),
                )
            )

        opportunities.sort(key=lambda item: (-item.score, item.algorithm_id))
        status = "OPPORTUNITIES_IDENTIFIED" if opportunities else "NO_NEW_ALGORITHM_OPPORTUNITY"
        return AlgorithmResult(
            algorithm_id=self.algorithm_id,
            name=self.name,
            status=status,
            maturity="TESTED_LOCAL",
            output={
                "opportunities": [item.as_dict() for item in opportunities],
                "opportunity_count": len(opportunities),
                "source_signal_count": len(signals),
                "promotion_rule": "BUILD_AND_TEST_BEFORE_CAPABILITY_PROMOTION",
            },
            metrics={"opportunity_count": float(len(opportunities))},
        )
