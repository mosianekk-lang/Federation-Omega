"""Deterministic owner-intent policy. It audits; it never executes."""

from __future__ import annotations

import hashlib
import json
from .contracts import ActionKind, AuditRequest, AuditResult, RequestedEffect, Verdict


POLICY_VERSION = "SIG-POLICY-2.0"

POLICY_FINGERPRINT = hashlib.sha256(json.dumps(
    {
        "policy_version": POLICY_VERSION,
        "allowed_action_kinds": [item.value for item in ActionKind],
        "prohibited_effects": [item.value for item in RequestedEffect],
        "immutable_outputs": {
            "authorizes_action": False,
            "effect_performed": False,
            "release_authority": "NONE",
        },
    },
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")).hexdigest()


def evaluate(
    request: AuditRequest,
    *,
    delivered_output_count: int = 0,
    output_ledger_hash: str = "0" * 64,
    output_ledger_verified: bool = False,
    advisory_available: bool = False,
    continuity_attestation_verified: bool = False,
) -> AuditResult:
    """Evaluate one request using fail-closed, non-generative policy rules."""

    action = request.proposed_action
    reasons: set[str] = set()
    conditions: set[str] = set()

    if not request.local_bible_hash_chain_valid:
        reasons.add("LOCAL_BIBLE_HASH_CHAIN_INVALID")
    if not request.mission_current:
        reasons.add("STALE_MISSION")
    if not request.source_fingerprints_current:
        reasons.add("STALE_SOURCE_FINGERPRINT")
    if not request.requirements_current:
        reasons.add("STALE_REQUIREMENTS")
    if request.policy_hash != POLICY_FINGERPRINT:
        reasons.add("STALE_POLICY")
    if not continuity_attestation_verified:
        reasons.add("CONTINUITY_ATTESTATION_UNVERIFIED")
    if request.manual_user_task_count or action.user_burden > 0:
        reasons.add("AVOIDABLE_MANUAL_USER_TASK")
    if action.estimated_cost > 0 or action.recurring_cost > 0:
        reasons.add("UNAUTHORISED_COST")

    for effect in action.requested_effects:
        reasons.add(f"PROHIBITED_EFFECT_{effect.value}")

    # The guardian is advisory-only. Formation permits never expand its authority.
    if action.authority_class != "A0":
        reasons.add("EFFECT_AUTHORITY_PROHIBITED")

    deployed = action.state_claims.get("deployed") is True
    proven = action.state_claims.get("proven") is True
    autonomous = action.state_claims.get("autonomous") is True
    if deployed and not action.proof.get("deployment_readback"):
        reasons.add("DEPLOYMENT_OVERCLAIM")
    if proven and not (
        action.proof.get("semantic_verification")
        and action.proof.get("independent_attestation")
    ):
        reasons.add("PROOF_OVERCLAIM")
    if autonomous and not (
        action.proof.get("live_scheduler")
        and action.proof.get("live_canary")
        and action.proof.get("trusted_runtime_attestation")
    ):
        reasons.add("AUTONOMY_OVERCLAIM")

    if delivered_output_count < 0:
        reasons.add("OUTPUT_LEDGER_COUNT_INVALID")
    if not output_ledger_verified:
        conditions.add("OUTPUT_LEDGER_READBACK_REQUIRED")
    if not advisory_available:
        conditions.add("ADVISORY_PROVIDER_UNAVAILABLE")
    cadence_due = (delivered_output_count + 1) % request.cadence_every == 0
    if cadence_due:
        conditions.add("FIFTH_OUTPUT_UPDATE_DUE")
    if not action.reversible:
        conditions.add("IRREVERSIBILITY_REQUIRES_EXPLICIT_OWNER_DECISION")
    if action.authority_class == "A0" and action.formation_gate_decision:
        conditions.add("A0_ADVISORY_ONLY")

    if action.owner_decision_required:
        verdict = Verdict.SOVEREIGN_DECISION_REQUIRED
        reasons.add("NON_DELEGABLE_OWNER_DECISION")
    elif reasons:
        verdict = Verdict.BLOCK
    elif conditions:
        verdict = Verdict.ALIGN_WITH_CONDITIONS
    else:
        verdict = Verdict.ALIGN

    blocked = verdict in {Verdict.BLOCK, Verdict.SOVEREIGN_DECISION_REQUIRED}
    requirement_matrix = tuple(
        {
            "requirement_id": requirement_id,
            "status": "BLOCKED" if blocked else "VERIFIED",
        }
        for requirement_id in sorted(set(request.requirement_ids))
    )
    source_trace = tuple(
        {"source_id": source_id, "sha256": source_hash}
        for source_id, source_hash in sorted(request.source_hashes.items())
    )
    return AuditResult(
        verdict=verdict,
        reason_codes=tuple(sorted(reasons)),
        conditions=tuple(sorted(conditions)),
        requirement_matrix=requirement_matrix,
        source_trace=source_trace,
        cadence_due=cadence_due,
        delivered_output_count=delivered_output_count,
        output_ledger_hash=output_ledger_hash,
        output_ledger_verified=output_ledger_verified,
        advisory_available=advisory_available,
        policy_version=POLICY_VERSION,
        input_hash=request.input_hash,
    )
