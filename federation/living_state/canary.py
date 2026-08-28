from __future__ import annotations

"""Deterministic learning helper and no-effect living-state canary."""

from typing import Any, Sequence

from .types import *
from .model import LivingWorldModel

def learning_event(
    *,
    learning_class: LearningClass,
    fingerprint: str,
    observed_at: str,
    matter_scope: str,
    route_id: str,
    signal: str,
    diagnosis: str,
    hypothesis: str,
    test_ref: str,
    result_ref: str,
    proof_refs: Sequence[str],
    recurrence: int,
    independent_evidence: bool,
    privacy_sensitive: bool = False,
) -> LearningEvent:
    body = {
        "learning_class": learning_class,
        "fingerprint": fingerprint,
        "observed_at": observed_at,
        "matter_scope": matter_scope,
        "route_id": route_id,
        "signal": signal,
        "diagnosis": diagnosis,
        "hypothesis": hypothesis,
        "test_ref": test_ref,
        "result_ref": result_ref,
        "proof_refs": tuple(sorted(set(proof_refs))),
        "recurrence": recurrence,
        "independent_evidence": independent_evidence,
        "privacy_sensitive": privacy_sensitive,
    }
    return LearningEvent(learning_id=f"FLSL-{digest(body)[:24].upper()}", **body).validate()


def run_living_fabric_canary() -> dict[str, Any]:
    now = "2026-08-28T04:00:00+00:00"
    model = LivingWorldModel()

    p_source = Provenance("source", "proof-source", "2026-08-28T03:50:00+00:00", ProofMaturity.DETERMINISTIC_TESTED, 3600, 0.8)
    p_provider = Provenance("provider", "proof-provider", "2026-08-28T03:55:00+00:00", ProofMaturity.PROVIDER_READBACK, 3600, 0.95)
    model.observe_node(WorldNode("surface:GITHUB", NodeKind.SURFACE, "GitHub", "READY", {}, p_source))
    model.observe_node(WorldNode("surface:GITHUB", NodeKind.SURFACE, "GitHub", "DEGRADED", {}, p_provider))
    estimate = model.state_estimate("surface:GITHUB", now=now)

    model.observe_node(WorldNode("control:A", NodeKind.CONTROL, "A", "ACTIVE", {}, Provenance("ctl", "p-a", now, ProofMaturity.DETERMINISTIC_TESTED, 3600, 0.9, matter_scope="GLOBAL")))
    model.observe_node(WorldNode("system:B", NodeKind.SYSTEM, "B", "ACTIVE", {}, Provenance("sys", "p-b", now, ProofMaturity.DETERMINISTIC_TESTED, 3600, 0.9, matter_scope="GLOBAL")))
    causal = WorldEdge(
        "edge:causal:A:B", "control:A", "system:B", EdgeKind.CAUSES,
        Provenance("experiment", "cause-proof", now, ProofMaturity.RECEIPT_VERIFIED, 3600, 0.95),
        0.9, CausalStatus.VERIFIED,
        CausalEvidence(True, True, False, True, False, ("cause-proof",)),
    )
    model.observe_edge(causal)
    correlation_rejected = False
    try:
        model.observe_edge(WorldEdge(
            "edge:bad-cause", "control:A", "system:B", EdgeKind.CAUSES,
            Provenance("correlation", "corr-proof", now, ProofMaturity.DETERMINISTIC_TESTED, 3600, 0.7),
            0.7, CausalStatus.CANDIDATE, CausalEvidence(temporal_order=True, evidence_refs=("corr-proof",)),
        ))
    except ValueError:
        correlation_rejected = True

    for route, domain, successes in (("route:A", "FD:GITHUB", (1, 1, 1)), ("route:B", "FD:GOOGLE", (1, 1, 0)), ("route:C", "FD:GITHUB", (1, 0, 0))):
        for idx, success in enumerate(successes):
            model.observe_route_telemetry(RouteTelemetry(
                route, "mission:M", f"2026-08-28T03:{40+idx:02d}:00+00:00", bool(success),
                latency_ms=100 + 20 * idx, cost_units=0.1, owner_burden=0.1,
                proof_freshness=0.9, proof_strength=0.9, risk=0.1,
                failure_domains=(domain,), proof_ref=f"route-proof-{route}-{idx}",
            ))
    portfolio = model.route_portfolio()

    context = ContextState(
        "context:chat", 920, 1000, 0.35, 15,
        verified_facts=("VF",), adverse_evidence=("AE",), contradictions=("CX",), gaps=("GAP",),
        blockers=("BLOCK",), decisions=("DEC",), source_refs=("SRC",),
    )
    model.observe_context(context)

    l1 = learning_event(
        learning_class=LearningClass.OWNER_CORRECTION,
        fingerprint="STALE_ROUTE_SELECTION",
        observed_at=now,
        matter_scope="GLOBAL",
        route_id="route:A",
        signal="owner corrected stale route",
        diagnosis="freshness control did not fire",
        hypothesis="hard freshness gate prevents recurrence",
        test_ref="test:freshness",
        result_ref="result:pass",
        proof_refs=("owner-correction",),
        recurrence=2,
        independent_evidence=True,
    )
    model.observe_learning(l1)

    lease = MissionLease(
        "mission:M", "a" * 40, 1, ("federation/living_state",),
        "2026-08-28T03:00:00+00:00", "2026-08-28T05:00:00+00:00", False,
    )
    stale_disjoint = model.arbitrate_mission_write(
        lease=lease, now=now, current_main_sha="b" * 40,
        current_main_changed_paths=("docs/unrelated.md",), concurrent_workstream_paths=(),
    )
    fresh = model.arbitrate_mission_write(
        lease=lease, now=now, current_main_sha="a" * 40,
        current_main_changed_paths=(), concurrent_workstream_paths=(),
    )

    decision = model.plan((
        PlannerCandidate("probe", 0.5, 0.9, 0.8, 1.0, 0.1, 0.1, 0.0, proof_ref="probe-proof"),
        PlannerCandidate("deploy", 1.0, 0.2, 0.4, 0.1, 0.8, 0.8, 0.2, external_effect=True, proof_ref="deploy-proof"),
    ))

    weak = EvolutionCandidate("candidate:weak", "route", True, True, False, True, 0.5, 0.8, 5, ("p",))
    strong = EvolutionCandidate("candidate:strong", "route", True, True, True, True, 0.5, 0.8, 5, ("p1", "p2"))

    model.observe_benchmark("candidate:strong", "2026-08-01T00:00:00+00:00", "benchmark-proof")

    twin = {
        "system_id": "TEST_TWIN",
        "runtime_state": "RUNTIME_VERIFIED",
        "semantic_state": "RUNTIME_SEMANTIC_VERIFIED",
        "readback_state": "RUNTIME_READBACK",
        "proof_ref": "twin-proof",
        "source_ref": "twin-source",
        "observed_at": now,
        "ttl_seconds": 3600,
        "confidence": 0.88,
        "authority_ceiling": "A1_INTERNAL",
    }
    model.ingest_capability_twin(twin)
    model.ingest_awareness_result({
        "receipt_sha256": "awareness-receipt",
        "routes": ({"alias": "GOOGLE", "provider": "Google", "state": "READY", "score": 80, "runtime_readback": "REQUIRED"},),
        "opportunities": ({"opportunity_id": "OPP-1", "title": "Probe Google", "current_state": "UNPROBED", "opportunity_class": "PROVIDER_PROBE", "buildable_now": False, "priority": 70},),
    }, observed_at=now)
    model.ingest_omega4_snapshot(
        missions=({"mission_id": "M2", "project_id": "P2", "objective": "Objective", "current_stage": "ACTIVE", "active_lanes": ("L",), "blockers": (), "executable_next": True},),
        capabilities=({"capability_id": "CAP2", "role": "Role", "tags": ("routing",), "active": True},),
        metrics={"success": 1.0}, observed_at=now,
    )

    snapshot = model.snapshot(now=now)
    checks = {
        "provider_readback_outranks_source": estimate.state == "DEGRADED",
        "split_brain_detected": estimate.split_brain,
        "causal_edge_requires_causal_evidence": correlation_rejected,
        "verified_causal_edge_admitted": "edge:causal:A:B" in model._edges,
        "route_champion_selected": bool(portfolio.champion),
        "failure_domain_diverse_shadow": bool(portfolio.shadows) and portfolio.shadows[0] == "route:B",
        "context_requests_handoff": context.action() == "CHECKPOINT_AND_HANDOFF",
        "context_protects_adverse": "AE" in context.protected_items and "CX" in context.protected_items,
        "owner_correction_recurs_to_scientist": l1.escalation == "OMEGA_SCIENTIST_REVIEW",
        "owner_correction_global_promotion_bounded": l1.global_promotion_allowed,
        "stale_disjoint_requests_reconvergence": stale_disjoint.disposition == "FAST_RECONVERGE",
        "fresh_lease_can_write_internal": fresh.allowed,
        "planner_selects_high_information_probe": decision.selected_action_id == "probe",
        "planner_rejects_effect_executor": "deploy" in decision.rejected and not decision.external_effect_executed,
        "weak_evolution_stays_shadow": weak.state == EvolutionState.SHADOW,
        "strong_evolution_becomes_eligible": strong.state == EvolutionState.PROMOTION_ELIGIBLE,
        "benchmark_debt_detected": model.debt_report(now=now)["benchmark_debt"] == 1,
        "predictions_are_effect_free": all(not item["external_effect"] for item in model.predictions(now=now)),
        "reflexes_are_effect_free": all(not item["external_effect"] for item in model.reflexes(now=now)),
        "capability_twin_adapter_present": "capability:TEST_TWIN" in model.current_nodes(),
        "awareness_adapter_present": "route:GOOGLE" in model.current_nodes(),
        "omega4_adapter_present": "mission:M2" in model.current_nodes(),
        "event_chain_valid": model.verify_event_chain(),
        "snapshot_hash_bound": bool(snapshot["snapshot_sha256"]),
        "truth_boundary_no_background_claim": snapshot["truth_boundary"]["continuous_unattended_runtime_claimed"] is False,
        "zero_external_effects": model.external_effects == 0 and snapshot["external_effects"] == 0,
    }
    return {
        "schema": "FEDERATION-LIVING-STATE-CANARY-V1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "count": len(checks),
        "checks": checks,
        "external_effects": model.external_effects,
        "event_count": model.event_count,
        "snapshot_sha256": snapshot["snapshot_sha256"],
        "receipt_sha256": digest({"checks": checks, "snapshot_sha256": snapshot["snapshot_sha256"], "external_effects": model.external_effects}),
        "truth_boundary": snapshot["truth_boundary"],
    }
