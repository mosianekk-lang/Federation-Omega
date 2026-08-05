from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .algorithms_common import (
    AUTHORITY_CEILING, AlgorithmOpportunity, AlgorithmResult, clamp, number,
    sequence, sha256, text, unique_text,
)

class FailureToEngineeringGeneCompiler:
    algorithm_id = "ALG-EOPS-FEGC-001"
    name = "Failure-to-Engineering-Gene Compiler"

    def run(
        self,
        *,
        failure: Mapping[str, Any],
        recovery: Mapping[str, Any] | None = None,
        regression: Mapping[str, Any] | None = None,
    ) -> AlgorithmResult:
        failure_fingerprint = text(failure.get("fingerprint")) or sha256(
            {"category": failure.get("category"), "summary": failure.get("summary"), "workflow": failure.get("workflow_id")}
        )
        recovery = dict(recovery or {})
        regression = dict(regression or {})
        resolved = text(recovery.get("resolved_failure_fingerprint")) == failure_fingerprint
        regression_passed = regression.get("passed") is True
        readback = bool(recovery.get("readback"))
        violations: list[str] = []
        if not resolved:
            violations.append("RECOVERY_NOT_BOUND_TO_FAILURE_FINGERPRINT")
        if not readback:
            violations.append("RECOVERY_READBACK_MISSING")
        if not regression_passed:
            violations.append("REGRESSION_NOT_PASSED")
        if violations:
            return AlgorithmResult(
                algorithm_id=self.algorithm_id,
                name=self.name,
                status="NEGATIVE_RESULT_PRESERVED",
                maturity="SOURCE_BACKED_NEGATIVE_RESULT",
                output={
                    "failure_fingerprint": failure_fingerprint,
                    "negative_result": {"failure": dict(failure), "recovery": recovery, "regression": regression},
                    "gene_promoted": False,
                    "next_experiment": "close recovery fingerprint, readback and regression gates",
                },
                violations=tuple(violations),
                evidence_refs=tuple(unique_text(sequence(failure.get("evidence_refs")))),
            )
        gene_body = {
            "gene_id": f"GENE-{failure_fingerprint[:16].upper()}",
            "version": "1.0.0",
            "trigger": {
                "category": text(failure.get("category")) or "UNKNOWN",
                "fingerprint": failure_fingerprint,
                "signature": text(failure.get("summary")),
            },
            "guard": text(recovery.get("guard")) or text(recovery.get("repair")),
            "repair": text(recovery.get("repair")),
            "readback": text(recovery.get("readback")),
            "regression_test": text(regression.get("test_id")) or "BOUND_REGRESSION",
            "applicability": unique_text(sequence(recovery.get("applicability"))),
            "exclusions": unique_text(sequence(recovery.get("exclusions"))),
            "maturity": "M4_TESTED_ONE_LANE",
            "authority_ceiling": AUTHORITY_CEILING,
            "external_effect": False,
        }
        gene_body["gene_sha256"] = sha256(gene_body)
        return AlgorithmResult(
            algorithm_id=self.algorithm_id,
            name=self.name,
            status="ENGINEERING_GENE_COMPILED",
            maturity="M4_TESTED_ONE_LANE",
            output={"gene": gene_body, "gene_promoted": True},
            metrics={"gene_count": 1.0},
            evidence_refs=tuple(unique_text(sequence(failure.get("evidence_refs")) + sequence(recovery.get("evidence_refs")) + sequence(regression.get("evidence_refs")))),
        )
