from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .algorithms_common import (
    AUTHORITY_CEILING, AlgorithmOpportunity, AlgorithmResult, clamp, number,
    sequence, sha256, text, unique_text,
)

class ClaimProofDistanceGuard:
    algorithm_id = "ALG-EOPS-CPDG-001"
    name = "Claim-Proof Distance Guard"

    _strong_terms = re.compile(
        r"\b(complete|completed|verified|deployed|live|operational|final|all|exhaustive|proven)\b",
        re.IGNORECASE,
    )

    def run(self, claim: Mapping[str, Any]) -> AlgorithmResult:
        statement = text(claim.get("statement"))
        sources = unique_text(sequence(claim.get("source_evidence")))
        readback = unique_text(sequence(claim.get("target_readback")))
        independent = unique_text(sequence(claim.get("independent_verification")))
        contrary = unique_text(sequence(claim.get("contrary_evidence")))
        actual_state = text(claim.get("actual_state"))
        requested_state = text(claim.get("requested_state"))
        inference_distance = clamp(number(claim.get("inference_distance"), 0.5))

        weights = {
            "source": 0.25,
            "execution": 0.20,
            "readback": 0.25,
            "independent": 0.20,
            "scope": 0.10,
        }
        layers = {
            "source": bool(sources),
            "execution": bool(claim.get("execution_receipt")),
            "readback": bool(readback),
            "independent": bool(independent),
            "scope": bool(statement and claim.get("scope_defined", False)),
        }
        proof_score = sum(weights[key] for key, passed in layers.items() if passed)
        proof_score = clamp(proof_score * (1.0 - inference_distance * 0.25))

        strong_claim = bool(self._strong_terms.search(statement))
        violations: list[str] = []
        if not statement:
            violations.append("CLAIM_STATEMENT_MISSING")
        if strong_claim and not layers["readback"]:
            violations.append("STRONG_CLAIM_WITHOUT_TARGET_READBACK")
        if strong_claim and proof_score < 0.80:
            violations.append("STRONG_CLAIM_PROOF_THRESHOLD_NOT_MET")
        if requested_state and actual_state and requested_state != actual_state:
            violations.append("REQUESTED_ACTUAL_STATE_MISMATCH")

        if contrary:
            status = "DISPUTED"
        elif proof_score >= 0.85 and layers["readback"] and layers["source"]:
            status = "VERIFIED_FINDING"
        elif proof_score >= 0.45 and layers["source"]:
            status = "SOURCE_SUPPORTED"
        elif statement:
            status = "UNVERIFIED"
        else:
            status = "BLOCKED_INVALID_CLAIM"

        safe_language = statement
        if status == "DISPUTED":
            safe_language = f"DISPUTED: {statement}"
        elif status == "UNVERIFIED":
            safe_language = f"UNVERIFIED: {statement}"
        elif status == "SOURCE_SUPPORTED":
            safe_language = f"SOURCE-SUPPORTED, READBACK LIMITED: {statement}"

        missing_layers = [key for key, passed in layers.items() if not passed]
        return AlgorithmResult(
            algorithm_id=self.algorithm_id,
            name=self.name,
            status=status,
            maturity="TESTED_LOCAL",
            output={
                "statement": statement,
                "safe_language": safe_language,
                "proof_layers": layers,
                "missing_proof_layers": missing_layers,
                "source_evidence": sources,
                "contrary_evidence": contrary,
                "requested_state": requested_state,
                "actual_state": actual_state,
                "proof_score": round(proof_score, 6),
                "promotion_permitted": status == "VERIFIED_FINDING" and not violations,
            },
            violations=tuple(violations),
            metrics={"proof_score": proof_score, "inference_distance": inference_distance},
            evidence_refs=tuple(sources + readback + independent),
        )
