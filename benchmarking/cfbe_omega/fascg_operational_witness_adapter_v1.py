from __future__ import annotations

"""Consume the existing AutoPilot Operational Witness Fabric receipt for FASCG.

The upstream witness is independent operational evidence generated after a successful
Bubbles main-push run.  This adapter binds it to the exact FASCG source SHA and may
supply HOSTED_SHADOW or PROVIDER_BOUND promotion evidence.  A single witness can
never prove CANARY, OPERATIONAL, SUSTAINED_VALUE, or 10x.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from benchmarking.cfbe_omega.fascg_production_runtime_v1 import (
    ProductionStage, PromotionEvidence,
)

SCHEMA = "FASCG-AUTOPILOT-OPERATIONAL-WITNESS-ADAPTER-V1"
PROVIDER_EFFECT_AUTHORIZED = False
STABLE_PROMOTION_AUTHORIZED = False
TEN_X_VERIFIED = False


def _hash(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class OperationalWitnessEvidence:
    source_sha: str
    upstream_status: str
    selected_stage: ProductionStage
    execution_verified: bool
    host_readback_verified: bool
    external_provider_readback_verified: bool
    verified_surface_count: int
    proof_refs: tuple[str, ...]
    promotion_evidence: PromotionEvidence
    operational_verified: bool = False
    sustained_value_verified: bool = False
    ten_x_verified: bool = False
    receipt_sha256: str = ""


def adapt_operational_witness(
    receipt: Mapping[str, Any],
    *,
    expected_source_sha: str,
    proof_refs: Sequence[str],
    safety_score: float = 1.0,
    reliability_score: float = 1.0,
    owner_value_score: float = 0.0,
) -> OperationalWitnessEvidence:
    refs = tuple(sorted({str(x).strip() for x in proof_refs if str(x).strip()}))
    if len(refs) < 2:
        raise ValueError("FASCG_WITNESS_INDEPENDENT_PROOF_REFS_REQUIRED")
    source_sha = str(receipt.get("source_head_sha") or "")
    if source_sha != expected_source_sha:
        raise ValueError("FASCG_WITNESS_SOURCE_SHA_MISMATCH")
    if receipt.get("provider_effect_authorized") is not False:
        raise ValueError("FASCG_WITNESS_PROVIDER_EFFECT_FLAG_INVALID")
    if receipt.get("stable_promotion_authorized") is not False:
        raise ValueError("FASCG_WITNESS_STABLE_PROMOTION_INHERITANCE_FORBIDDEN")
    if receipt.get("full_autopilot_runtime_proven") is not False:
        raise ValueError("FASCG_WITNESS_FULL_RUNTIME_INHERITANCE_FORBIDDEN")

    execution = receipt.get("execution_witness")
    host = receipt.get("host_readback_witness")
    if not isinstance(execution, Mapping) or execution.get("kind") != "EXECUTION" or execution.get("verified") is not True:
        raise ValueError("FASCG_WITNESS_EXECUTION_REQUIRED")
    if not isinstance(host, Mapping) or host.get("kind") != "READBACK" or host.get("verified") is not True or host.get("independent") is not True:
        raise ValueError("FASCG_WITNESS_INDEPENDENT_HOST_READBACK_REQUIRED")

    status = str(receipt.get("status") or "")
    surfaces = int(receipt.get("verified_surface_count") or 0)
    readback = receipt.get("readback_witness")
    external_verified = (
        status == "WITNESS_EXECUTION_HOST_AND_EXTERNAL_READBACK_VERIFIED"
        and surfaces > 0
        and isinstance(readback, Mapping)
        and readback.get("kind") == "READBACK"
        and readback.get("verified") is True
        and readback.get("independent") is True
    )
    if status not in {
        "WITNESS_EXECUTION_HOST_AND_EXTERNAL_READBACK_VERIFIED",
        "WITNESS_EXECUTION_AND_HOST_READBACK_VERIFIED_EXTERNAL_READBACK_HELD",
    }:
        raise ValueError("FASCG_WITNESS_STATUS_INVALID")
    stage = ProductionStage.PROVIDER_BOUND if external_verified else ProductionStage.HOSTED_SHADOW
    promotion = PromotionEvidence(
        stage=stage,
        source_sha=source_sha,
        proof_refs=refs,
        independent_verifier_refs=("autopilot-operational-witness", "bubbles-provider-readback" if external_verified else "github-host-readback"),
        provider_native_readback=external_verified,
        rollback_available=True,
        safety_score=safety_score,
        reliability_score=reliability_score,
        owner_value_score=owner_value_score,
        sustained_windows=0,
    ).validate()
    body = {
        "schema": SCHEMA,
        "source_sha": source_sha,
        "upstream_status": status,
        "selected_stage": stage.value,
        "execution_verified": True,
        "host_readback_verified": True,
        "external_provider_readback_verified": external_verified,
        "verified_surface_count": surfaces,
        "proof_refs": refs,
        "operational_verified": False,
        "sustained_value_verified": False,
        "ten_x_verified": False,
    }
    return OperationalWitnessEvidence(
        source_sha=source_sha,
        upstream_status=status,
        selected_stage=stage,
        execution_verified=True,
        host_readback_verified=True,
        external_provider_readback_verified=external_verified,
        verified_surface_count=surfaces,
        proof_refs=refs,
        promotion_evidence=promotion,
        operational_verified=False,
        sustained_value_verified=False,
        ten_x_verified=False,
        receipt_sha256=_hash(body),
    )


__all__ = [
    "SCHEMA", "PROVIDER_EFFECT_AUTHORIZED", "STABLE_PROMOTION_AUTHORIZED", "TEN_X_VERIFIED",
    "OperationalWitnessEvidence", "adapt_operational_witness",
]
