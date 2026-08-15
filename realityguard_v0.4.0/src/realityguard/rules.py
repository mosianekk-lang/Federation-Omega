"""Deterministic rule evaluation. Rules never upgrade proof state."""

from __future__ import annotations

import re
from typing import Any

from .model import Claim, Evidence, Finding, LifecycleState
from .taxonomy import FAILURES


STATE_GATES = {
    LifecycleState.BUILT: "an inspectable artifact",
    LifecycleState.TESTED: "a passing test result",
    LifecycleState.STORED: "durable storage readback",
    LifecycleState.REGISTERED: "registry/provider registration receipt",
    LifecycleState.INSTALLED: "installation readback in the target environment",
    LifecycleState.BOUND: "binding to the intended account/session/runtime",
    LifecycleState.DEPLOYED: "deployment receipt for the target environment",
    LifecycleState.RUNNING: "current health or runtime observation",
    LifecycleState.READ_BACK: "semantic readback from the target system",
    LifecycleState.ACCEPTED: "explicit owner acceptance",
}


TEXT_SIGNALS = {
    "RG-001": (r"\b(?:prompt|document|manifest|blueprint|code) (?:is|means) (?:the )?(?:system|deployment|operation)\b",),
    "RG-002": (r"\b(?:activated|activate|now active|always on)\b",),
    "RG-003": (r"\b(?:tested locally|local test|created locally)\b.*\b(?:live|deployed|running)\b",),
    "RG-004": (r"\b(?:you can|here are the steps|if you want,? i can)\b",),
    "RG-005": (r"\b(?:only remaining boundary|cannot access|not available through)\b",),
    "RG-006": (r"\b(?:you need to|manually|copy and paste|install it yourself)\b",),
    "RG-007": (r"\b(?:all|entire|complete|full)\b.*\b(?:account|corpus|drive|conversations?)\b",),
    "RG-009": (r"\b(?:permanent memory|full continuity|moves with you|cross-chat continuity)\b",),
    "RG-011": (r"\b(?:you own|proud owner|your fully deployed|your live system)\b",),
    "RG-012": (r"\b(?:constitutional|sovereign|supreme|omega|infinite|v∞)\b",),
    "RG-019": (r"\b(?:agent|fleet|team|guardian) (?:is|are) (?:now )?(?:active|running|watching)\b",),
    "RG-020": (r"\b(?:permanently|universally|across all future chats|model has been modified)\b",),
    "RG-023": (r"\b(?:v∞|omega|100x|ultimate|supreme)\b",),
}


def missing_gates(proven: LifecycleState, claimed: LifecycleState) -> list[str]:
    return [STATE_GATES[state] for state in LifecycleState if proven < state <= claimed and state in STATE_GATES]


def _finding(code: str, severity: str, explanation: str, mitigation: list[str], refs: list[str] | None = None) -> Finding:
    title, _ = FAILURES[code]
    return Finding(code, title, severity, explanation, tuple(refs or ()), tuple(mitigation))


def evaluate(claim: Claim, evidence: list[Evidence], context: dict[str, Any], proven: LifecycleState) -> list[Finding]:
    findings: list[Finding] = []
    gap = int(claim.claimed_state) - int(proven)
    text = claim.text.lower()
    refs = [e.reference for e in evidence if e.reference]
    required = set(map(str, context.get("required_scope", claim.scope)))
    observed = set(map(str, context.get("observed_scope", ())))

    if gap > 0:
        code = "RG-001" if proven <= LifecycleState.BUILT else "RG-003"
        findings.append(_finding(
            code,
            "HIGH" if claim.claimed_state >= LifecycleState.DEPLOYED else "MEDIUM",
            f"Claimed {claim.claimed_state.name}, but admissible evidence reaches only {proven.name}.",
            [f"Relabel the state as {proven.name}.", "Name every missing proof gate before promotion."], refs,
        ))
    if claim.claimed_state >= LifecycleState.BOUND and not any(e.supports_state >= LifecycleState.BOUND and e.current for e in evidence):
        findings.append(_finding("RG-002", "HIGH", "No current target-runtime binding evidence exists.", ["Quarantine activation language until target binding is read back."]))
    if claim.ownership_asserted and proven < LifecycleState.READ_BACK:
        findings.append(_finding("RG-011", "CRITICAL", "Ownership is asserted without current possession, control and semantic readback evidence.", ["Replace ownership language with a precise artifact/custody statement.", "Require target-system readback and owner acceptance separately."]))
    if claim.completion_asserted and (gap > 0 or required - observed):
        missing = sorted(required - observed)
        findings.append(_finding("RG-015", "HIGH", f"Completion is not supported; unverified scope: {', '.join(missing) if missing else 'proof-state gap'}.", ["Block completion.", "Continue safe verification or report the exact bounded result."]))
    if required and observed and required - observed:
        findings.append(_finding("RG-007", "HIGH", f"Observed scope is partial: {len(observed)}/{len(required)} required dimensions.", ["Declare the denominator and missing dimensions.", "Do not use all, full or complete."]))
    if context.get("manual_user_task_avoidable"):
        findings.append(_finding("RG-006", "HIGH", "An avoidable task was transferred to the user.", ["Execute the authorized step automatically or state the genuine authority boundary."]))
    if context.get("action_available") and context.get("instructions_substituted"):
        findings.append(_finding("RG-004", "MEDIUM", "Instructions or options were supplied although the action was available and authorized.", ["Perform the action, verify it, then report the result."]))
    if context.get("draft_only") and re.search(r"\b(sent|published|released|deployed)\b", text):
        findings.append(_finding("RG-008", "HIGH", "Release language is used for a draft-only state.", ["Relabel as DRAFT/PREPARED and require provider receipt plus semantic readback."]))
    if context.get("shallow_or_paginated") and re.search(r"\b(all|entire|complete|full)\b", text):
        findings.append(_finding("RG-007", "CRITICAL", "A shallow or paginated retrieval is represented as total.", ["Fail closed on totality; enumerate pagination, recursion and connector boundaries."]))
    if context.get("metadata_only") and context.get("content_review_claimed"):
        findings.append(_finding("RG-018", "HIGH", "Metadata access is represented as underlying-content review.", ["Separate listed, fetched, parsed and substantively reviewed counts."]))
    if context.get("derivative_counted_as_source"):
        findings.append(_finding("RG-017", "MEDIUM", "Derived copies or indexes are counted as independent source records.", ["Deduplicate by provenance and report source versus derivative counts."]))
    if context.get("historical_receipt") and not context.get("fresh_readback"):
        findings.append(_finding("RG-013", "HIGH", "Historical evidence is being reused without current readback.", ["Mark the receipt stale and re-verify the target state."]))
    if context.get("transport_success") and not context.get("semantic_success"):
        findings.append(_finding("RG-014", "HIGH", "Transport success is not semantic proof of the requested outcome.", ["Inspect response meaning and read the changed state back."]))
    if context.get("self_generated_proof") and not any(e.independent for e in evidence):
        findings.append(_finding("RG-021", "CRITICAL", "Claim and proof were generated by the same source without independent observation.", ["Downgrade to self-reported.", "Require an external or independently reproducible readback."]))
    if context.get("ui_label_changed") and not context.get("underlying_semantics_changed"):
        findings.append(_finding("RG-022", "CRITICAL", "The interface label promises semantics the underlying action does not provide.", ["Block the UI claim or implement and test the continuation transport before exposing it."]))
    if context.get("authorization_missing") and claim.capability_asserted:
        findings.append(_finding("RG-016", "HIGH", "Capability is asserted without the authority needed to perform the target action.", ["Separate discoverable, callable, authorized and executed states."]))
    if context.get("boundary_disclosed_after_challenge"):
        findings.append(_finding("RG-010", "HIGH", "The decisive limitation was disclosed only after correction by the user.", ["Front-load the boundary and repair downstream assumptions created by the earlier claim."]))
    if context.get("persistent_agent_claim") and not context.get("persistent_runtime_proof"):
        findings.append(_finding("RG-019", "HIGH", "A persistent agent or fleet is claimed without scheduler/runtime proof.", ["Describe the role as a prompt pattern unless a persistent runtime is independently observed."]))
    if context.get("permanent_model_change_claim"):
        findings.append(_finding("RG-020", "CRITICAL", "A prompt-level instruction is represented as permanent model modification.", ["Limit the claim to the current configured scope and verify each surface independently."]))
    if context.get("version_label") and not context.get("maturity_evidence"):
        findings.append(_finding("RG-023", "MEDIUM", "A maturity-signalling version label lacks matching lifecycle evidence.", ["Use version labels only for artifact lineage; report maturity separately."]))
    if context.get("state_changed_since_proof"):
        findings.append(_finding("RG-024", "HIGH", "Proof predates a material environment or authentication change.", ["Invalidate cached status and repeat current readback."]))
    if context.get("governance_artifact") and not context.get("enforcement_runtime"):
        findings.append(_finding("RG-012", "HIGH", "Governance text exists without an enforcing runtime path.", ["Call it a governance specification, not enforced governance.", "Prove interception, decision and block/readback behavior."]))
    if context.get("checkpoint_only") and re.search(r"\b(permanent|full continuity|moves with you|cross-chat)\b", text):
        findings.append(_finding("RG-009", "HIGH", "A checkpoint artifact is represented as automatically bound continuity.", ["Distinguish stored context from injected, loaded and validated context."]))
    if context.get("objective_dropped_after_block"):
        findings.append(_finding("RG-025", "HIGH", "A valid desired capability was discarded when its unsupported status claim was blocked.", ["Keep the truth verdict and solution route separate.", "Route the objective through ADOPT, ADAPT, COMPOSE, PATCH_EXISTING or BUILD_NEW_ONLY_IF_GAP."]))
    if context.get("executor_continued_after_gate_failure"):
        findings.append(_finding("RG-026", "CRITICAL", "A downstream executor continued after its governing gate failed.", ["Quarantine the effect and reconcile it semantically.", "Separate gate consumption from execution or enforce a fail-fast command boundary."]))
    if context.get("new_build_without_reuse_preflight"):
        findings.append(_finding("RG-027", "HIGH", "New construction began without a current bounded capability inventory and reuse-first gap decision.", ["Stop the new-build path.", "Inventory current capability, suppress duplicates and route to adopt, adapt, compose or patch before proving a residual build gap."]))
    if context.get("reactive_only_correction"):
        findings.append(_finding("RG-028", "HIGH", "The failure was corrected only after owner challenge although a material-cycle control could have detected it earlier.", ["Invoke RealityGuard at the pre-action and material-cycle boundary.", "Add the original failure and healthy behavior to the regression set."]))
    if context.get("source_corrected_without_dependents"):
        findings.append(_finding("RG-029", "HIGH", "A corrected source state was not propagated to known dependent artifacts or routes.", ["Invalidate downstream state.", "Repair in dependency order and require semantic readback before promotion."]))
    if context.get("automatic_upgrade_without_governance"):
        findings.append(_finding("RG-030", "CRITICAL", "An automatic upgrade or promotion path lacks bounded evidence, rollback or an authority gate.", ["Quarantine the route.", "Require current inventory, failure and healthy tests, rollback and a single-use Formation permit."]))

    for code, patterns in TEXT_SIGNALS.items():
        if any(re.search(pattern, text, re.I) for pattern in patterns) and not any(f.code == code for f in findings):
            findings.append(_finding(code, "MEDIUM", "Risk-bearing language was detected and lacks enough structured proof to dismiss safely.", ["Request or attach structured proof; otherwise rewrite the statement at the proven state."]))
    return sorted(findings, key=lambda f: ({"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}[f.severity], f.code))
