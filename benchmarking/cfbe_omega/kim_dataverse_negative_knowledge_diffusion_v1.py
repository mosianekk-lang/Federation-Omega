from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Sequence


@dataclass(frozen=True)
class FailureGene:
    gene_id: str
    failure_class: str
    fingerprint: str
    verified_repair: str
    regression_proof_refs: tuple[str, ...]
    receiver_scope: tuple[str, ...]
    authority_inherited: bool = False


@dataclass(frozen=True)
class DiffusionDecision:
    gene_id: str
    eligible_receivers: tuple[str, ...]
    blocked_receivers: tuple[str, ...]
    external_effect_authorized: bool
    receipt: str


def diffuse_failure_gene(
    gene: FailureGene,
    registered_receivers: Sequence[str],
    *,
    receiver_semantic_compatibility: dict[str, bool],
) -> DiffusionDecision:
    if gene.authority_inherited:
        raise ValueError("failure knowledge cannot inherit authority")
    if not gene.regression_proof_refs:
        raise ValueError("verified repair requires regression proof")
    registered = tuple(dict.fromkeys(registered_receivers))
    eligible = []
    blocked = []
    allowed_scope = set(gene.receiver_scope)
    for receiver in registered:
        if receiver not in allowed_scope or not receiver_semantic_compatibility.get(receiver, False):
            blocked.append(receiver)
        else:
            eligible.append(receiver)
    payload = {
        "gene_id": gene.gene_id,
        "eligible_receivers": sorted(eligible),
        "blocked_receivers": sorted(blocked),
        "external_effect_authorized": False,
        "authority_inherited": False,
    }
    receipt = "sha256:" + sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return DiffusionDecision(
        gene_id=gene.gene_id,
        eligible_receivers=tuple(sorted(eligible)),
        blocked_receivers=tuple(sorted(blocked)),
        external_effect_authorized=False,
        receipt=receipt,
    )
