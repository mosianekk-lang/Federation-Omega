from __future__ import annotations

"""FASCG adapter for SOL 6.2 proof receipts.

This module consumes SOL 6.2 evidence; it does not reimplement SOL, execute a
provider, mint authority, or inherit production maturity.  Its purpose is to make
SOL's verified-state-transition semantics load-bearing in FASCG while preserving
the proof ladder.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

SOL62_PROGRAMME = "SOL-6.2-TRANSACTIONAL-SELF-VERIFYING-RUNTIME"
SOL62_REFERENCE_STATUS = "SOL_6_2_REFERENCE_RUNTIME_VERIFIED"
SOL62_HOSTED_CONTINUITY_STATE = "HOSTED_SEPARATE_RUN_STATE_CONTINUITY_VERIFIED"
PROVIDER_EFFECT_AUTHORIZED = False
AUTHORITY_MINTING_AUTHORIZED = False
PRODUCTION_PROMOTION_AUTHORIZED = False
TEN_X_VERIFIED = False


def _hash(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class Sol62AssistanceEvidence:
    reference_verified: bool
    hosted_continuity_verified: bool
    transactional_truth_spine_usable: bool
    proof_refs: tuple[str, ...]
    sol_receipt_sha256: str
    hosted_receipt_sha256: str | None
    fascg_promotion_ceiling: str = "HOSTED_SHADOW"
    provider_bound: bool = False
    operational_verified: bool = False
    sustained_value_verified: bool = False
    ten_x_verified: bool = False
    evidence_sha256: str = ""


def adapt_sol62_receipts(
    reference_receipt: Mapping[str, Any],
    *,
    proof_refs: Sequence[str],
    hosted_continuity_receipt: Mapping[str, Any] | None = None,
) -> Sol62AssistanceEvidence:
    refs = tuple(sorted({str(x).strip() for x in proof_refs if str(x).strip()}))
    if len(refs) < 2:
        raise ValueError("FASCG_SOL62_INDEPENDENT_PROOF_REFS_REQUIRED")
    if reference_receipt.get("programme") != SOL62_PROGRAMME or str(reference_receipt.get("version")) != "6.2":
        raise ValueError("FASCG_SOL62_REFERENCE_IDENTITY_MISMATCH")
    if reference_receipt.get("status") != SOL62_REFERENCE_STATUS:
        raise ValueError("FASCG_SOL62_REFERENCE_NOT_VERIFIED")
    gates = reference_receipt.get("gates")
    if not isinstance(gates, Mapping) or not gates or not all(bool(v) for v in gates.values()):
        raise ValueError("FASCG_SOL62_REFERENCE_GATES_INCOMPLETE")
    truth = reference_receipt.get("truth_boundary")
    if not isinstance(truth, Mapping):
        raise ValueError("FASCG_SOL62_TRUTH_BOUNDARY_REQUIRED")
    required_true = (
        "source_runtime_implemented",
        "deterministic_reference_proof",
        "provider_effect_proof_binding_enforced_in_reference_runtime",
    )
    if not all(truth.get(k) is True for k in required_true):
        raise ValueError("FASCG_SOL62_REFERENCE_TRUTH_REQUIRED")
    required_false = (
        "provider_live_production_cutover",
        "provider_identity_inherited",
        "continuous_background_execution",
        "market_superiority_claim",
    )
    if not all(truth.get(k) is False for k in required_false):
        raise ValueError("FASCG_SOL62_MATURITY_OVERCLAIM")

    hosted_ok = False
    hosted_sha: str | None = None
    if hosted_continuity_receipt is not None:
        state = str(hosted_continuity_receipt.get("state") or hosted_continuity_receipt.get("classification") or "")
        if state != SOL62_HOSTED_CONTINUITY_STATE:
            raise ValueError("FASCG_SOL62_HOSTED_CONTINUITY_NOT_VERIFIED")
        if hosted_continuity_receipt.get("provider_effect_authorized") is True:
            raise ValueError("FASCG_SOL62_HOSTED_EFFECT_INHERITANCE_FORBIDDEN")
        hosted_ok = True
        hosted_sha = str(hosted_continuity_receipt.get("receipt_sha256") or "")
        if len(hosted_sha) != 64:
            hosted_sha = _hash(hosted_continuity_receipt)

    sol_sha = str(reference_receipt.get("sha256") or "")
    if len(sol_sha) != 64:
        sol_sha = _hash(reference_receipt)
    body = {
        "schema": "FASCG-SOL62-ASSISTANCE-EVIDENCE-V1",
        "reference_sha256": sol_sha,
        "hosted_sha256": hosted_sha,
        "reference_verified": True,
        "hosted_continuity_verified": hosted_ok,
        "proof_refs": refs,
        "provider_bound": False,
        "operational_verified": False,
        "sustained_value_verified": False,
        "ten_x_verified": False,
    }
    return Sol62AssistanceEvidence(
        reference_verified=True,
        hosted_continuity_verified=hosted_ok,
        transactional_truth_spine_usable=True,
        proof_refs=refs,
        sol_receipt_sha256=sol_sha,
        hosted_receipt_sha256=hosted_sha,
        evidence_sha256=_hash(body),
    )
