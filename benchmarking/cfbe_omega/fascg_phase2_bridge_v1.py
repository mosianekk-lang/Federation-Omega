from __future__ import annotations

"""FASCG adapter for the admitted/bounded AO-CEF Phase-2 empirical shadow receipt.

The adapter consumes a receipt produced by the separate AO-CEF Phase-2 court. It
never invokes a model/provider itself and cannot upgrade shadow evidence into
provider-bound, canary, operational, sustained-value, or 10x proof.
"""

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

PHASE2_SCHEMA = "CFBE_AO_COGNITIVE_EVOLUTION_PHASE2_RECEIPT_V1"
PROVIDER_EFFECT_AUTHORIZED = False
MODEL_INFERENCE_AUTHORIZED = False
PRODUCTION_SELF_MUTATION_AUTHORIZED = False
TEN_X_VERIFIED = False


def _hash(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


class Phase2Disposition(StrEnum):
    PROMOTE_SHADOW_CANDIDATE = "PROMOTE_SHADOW_CANDIDATE"
    RETAIN_NO_ADVANTAGE = "RETAIN_NO_ADVANTAGE"
    REJECT_PROTECTED_GATE = "REJECT_PROTECTED_GATE"
    HOLD_INCOMPLETE = "HOLD_INCOMPLETE"


@dataclass(frozen=True, slots=True)
class Phase2EvolutionEvidence:
    receipt_sha256: str
    disposition: Phase2Disposition
    accuracy_delta: float
    transfer_floor: float
    protected_fault_catch_rate: float
    independent_model_count: int
    independent_harness_count: int
    provider_proof_refs: tuple[str, ...]
    promotion_ceiling: str = "HOSTED_SHADOW"
    provider_bound: bool = False
    operational_verified: bool = False
    ten_x_verified: bool = False

    @property
    def eligible_for_shadow_evolution(self) -> bool:
        return self.disposition == Phase2Disposition.PROMOTE_SHADOW_CANDIDATE


def adapt_phase2_receipt(receipt: Mapping[str, Any], *, provider_proof_refs: Sequence[str]) -> Phase2EvolutionEvidence:
    if receipt.get("schema") != PHASE2_SCHEMA:
        raise ValueError("FASCG_PHASE2_SCHEMA_MISMATCH")
    if receipt.get("provider_mutation_performed") is not False:
        raise ValueError("FASCG_PHASE2_PROVIDER_MUTATION_FORBIDDEN")
    if receipt.get("model_output_self_certification_allowed") is not False:
        raise ValueError("FASCG_PHASE2_SELF_CERTIFICATION_FORBIDDEN")
    if receipt.get("ten_x_proven") is not False:
        raise ValueError("FASCG_PHASE2_TEN_X_INHERITANCE_FORBIDDEN")
    refs = tuple(sorted({str(x).strip() for x in provider_proof_refs if str(x).strip()}))
    if len(refs) < 2:
        raise ValueError("FASCG_PHASE2_INDEPENDENT_PROOF_REFS_REQUIRED")

    transfer = receipt.get("transfer_scores")
    if not isinstance(transfer, Mapping) or not transfer:
        raise ValueError("FASCG_PHASE2_TRANSFER_SCORES_REQUIRED")
    transfer_floor = min(float(v) for v in transfer.values())
    critical = float(receipt.get("aocef_critical_fault_catch_rate") or 0.0)
    trial_count = int(receipt.get("trial_count") or 0)
    expected = int(receipt.get("expected_trial_count") or 0)
    state = str(receipt.get("state") or "")
    protected = bool(receipt.get("protected_gate_passed"))
    delta = float(receipt.get("accuracy_delta") or 0.0)

    if trial_count != expected or expected < 1 or state == "PH2_INCOMPLETE_REPLICATION":
        disposition = Phase2Disposition.HOLD_INCOMPLETE
    elif not protected or transfer_floor < 0.80 or critical < 1.0 or state == "PH2_PROTECTED_GATE_FAILED":
        disposition = Phase2Disposition.REJECT_PROTECTED_GATE
    elif state == "PH2_EMPIRICAL_ADVANTAGE_CANDIDATE" and delta > 0:
        disposition = Phase2Disposition.PROMOTE_SHADOW_CANDIDATE
    else:
        disposition = Phase2Disposition.RETAIN_NO_ADVANTAGE

    supplied_digest = str(receipt.get("receipt_sha256") or "")
    if len(supplied_digest) != 64:
        supplied_digest = _hash(receipt)

    return Phase2EvolutionEvidence(
        receipt_sha256=supplied_digest,
        disposition=disposition,
        accuracy_delta=round(delta, 6),
        transfer_floor=round(transfer_floor, 6),
        protected_fault_catch_rate=round(critical, 6),
        independent_model_count=int(receipt.get("independent_model_count") or 0),
        independent_harness_count=int(receipt.get("independent_harness_count") or 0),
        provider_proof_refs=refs,
    )
