from __future__ import annotations

from typing import Any, Mapping

from .algorithms import AlgorithmResult, sha256


class CrossImplementationReplicationEvaluator:
    """Compare canonical and independent implementations without trust transfer."""

    algorithm_id = "ALG-EOPS-CIRE-001"
    name = "Cross-Implementation Replication Evaluator"

    @staticmethod
    def _canonical_finality(result: Mapping[str, Any]) -> Mapping[str, Any]:
        for row in result.get("algorithm_results", []):
            if row.get("algorithm_id") == "ALG-EOPS-TFR-001":
                return row
        return {}

    def run(
        self,
        *,
        canonical_result: Mapping[str, Any],
        reference_result: Mapping[str, Any],
    ) -> dict[str, Any]:
        canonical_finality = self._canonical_finality(canonical_result)
        reference_finality = reference_result.get("terminal_finality", {})
        canonical_release = bool(
            canonical_finality.get("output", {}).get(
                "final_certificate_permitted", False
            )
        )
        reference_release = bool(reference_finality.get("release_allowed", False))
        canonical_count = int(canonical_finality.get("output", {}).get("total", 0))
        reference_count = int(reference_finality.get("item_count", 0))
        canonical_opportunities = {
            item.get("algorithm_id")
            for item in canonical_result.get("innovation_delta", {}).get(
                "identified_algorithm_opportunities", []
            )
        }
        reference_opportunities = {
            item.get("proposed_algorithm")
            for item in reference_result.get("opportunity_frontier", [])
        }
        agreement = {
            "final_release_decision": canonical_release == reference_release,
            "finality_item_count": canonical_count == reference_count,
            "learning_chain": (
                canonical_result.get("proof", {})
                .get("learning_chain", {})
                .get("status")
                == "PASSED"
                and reference_result.get("learning_verification", {}).get("status")
                == "PASSED"
            ),
            "read_only_boundary": (
                canonical_result.get("external_effect") is False
                and reference_result.get("external_effect") is False
                and canonical_result.get("source_write") is False
                and reference_result.get("source_write") is False
            ),
        }
        disagreements = [key for key, value in agreement.items() if not value]
        result = {
            "schema": "EVIDENCEOPS_CROSS_IMPLEMENTATION_REPLICATION_V1",
            "algorithm_id": self.algorithm_id,
            "name": self.name,
            "status": (
                "REPLICATED_AGREEMENT"
                if not disagreements
                else "REPLICATION_DIVERGENCE"
            ),
            "agreement": agreement,
            "disagreements": disagreements,
            "canonical_finality": {
                "release_allowed": canonical_release,
                "item_count": canonical_count,
            },
            "reference_finality": {
                "release_allowed": reference_release,
                "item_count": reference_count,
            },
            "opportunity_overlap": sorted(
                item
                for item in (canonical_opportunities & reference_opportunities)
                if item
            ),
            "canonical_result_hash": canonical_result.get("receipt_sha256"),
            "reference_result_hash": reference_result.get("result_hash"),
            "authority_ceiling": "A1_INTERNAL",
            "external_effect": False,
            "trust_transfer": False,
        }
        result["receipt_sha256"] = sha256(result)
        return result

    def run_algorithm(
        self,
        *,
        canonical_result: Mapping[str, Any],
        reference_result: Mapping[str, Any],
    ) -> AlgorithmResult:
        result = self.run(
            canonical_result=canonical_result,
            reference_result=reference_result,
        )
        disagreements = tuple(str(item) for item in result["disagreements"])
        return AlgorithmResult(
            algorithm_id=self.algorithm_id,
            name=self.name,
            status=result["status"],
            maturity="R3_INDEPENDENT_IMPLEMENTATION_TESTED_LOCAL",
            output=result,
            violations=disagreements,
            metrics={
                "agreement_ratio": (
                    sum(bool(value) for value in result["agreement"].values())
                    / max(1, len(result["agreement"]))
                ),
                "disagreement_count": float(len(disagreements)),
            },
            evidence_refs=tuple(
                value
                for value in (
                    result.get("canonical_result_hash"),
                    result.get("reference_result_hash"),
                )
                if value
            ),
        )
