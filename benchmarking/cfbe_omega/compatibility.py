from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class CompatibilityResult:
    compatible: bool
    reusable_for: tuple[str, ...]
    not_sufficient_for: tuple[str, ...]
    gaps: tuple[str, ...]


def assess_drive_receipt_contract(receipt: Mapping[str, Any]) -> CompatibilityResult:
    """Assess whether a prior-generation Drive proof receipt can feed v3 evidence.

    This function does not perform a provider write and does not grant authority.
    It only checks whether an already-produced receipt has enough structure to be
    normalized as evidence for a newer system's independent reconciliation path.
    """
    required_sections = (
        "discover",
        "authority",
        "snapshot",
        "deploy",
        "execute",
        "readback",
        "health",
        "persistence",
        "rollback",
        "proof",
    )
    missing = tuple(section for section in required_sections if section not in receipt)
    if missing:
        return CompatibilityResult(
            compatible=False,
            reusable_for=(),
            not_sufficient_for=(
                "provider_write",
                "authority_grant",
                "maturity_inheritance",
            ),
            gaps=tuple(f"missing:{section}" for section in missing),
        )

    proof = receipt.get("proof", {})
    proof_ref = proof.get("receipt_id")
    if not proof_ref:
        return CompatibilityResult(
            compatible=False,
            reusable_for=(),
            not_sufficient_for=(
                "provider_write",
                "authority_grant",
                "maturity_inheritance",
            ),
            gaps=("missing:proof.receipt_id",),
        )

    return CompatibilityResult(
        compatible=True,
        reusable_for=(
            "evidence_normalization",
            "readback_validation",
            "rollback_validation",
            "cross_system_reconciliation_input",
        ),
        not_sufficient_for=(
            "provider_write",
            "authority_grant",
            "maturity_inheritance",
        ),
        gaps=(),
    )


def normalize_drive_receipt_for_v3(
    receipt: Mapping[str, Any],
    *,
    entity_id: str,
    observed_at: str,
) -> dict[str, Any]:
    """Create a v3-shaped observation from a compatible proof receipt.

    The output is deliberately evidence-only. It is suitable for the v3
    cross-system reconciler, but a live action remains separately gated.
    """
    assessment = assess_drive_receipt_contract(receipt)
    if not assessment.compatible:
        raise ValueError(f"incompatible receipt: {assessment.gaps}")

    proof_ref = str(receipt["proof"]["receipt_id"])
    observed = {
        "discover": receipt["discover"],
        "authority": receipt["authority"],
        "snapshot": receipt["snapshot"],
        "deploy": receipt["deploy"],
        "execute": receipt["execute"],
        "readback": receipt["readback"],
        "health": receipt["health"],
        "persistence": receipt["persistence"],
        "rollback": receipt["rollback"],
    }
    return {
        "system": "alpha_omega_prior_drive_proof",
        "entity_id": entity_id,
        "intended": observed,
        "declared": observed,
        "observed": observed,
        "proven": observed,
        "outcome": observed,
        "evidence_ref": proof_ref,
        "observed_at": observed_at,
        "truth_boundary": {
            "evidence_only": True,
            "provider_write_performed_here": False,
            "authority_inherited": False,
            "maturity_inherited": False,
        },
    }

