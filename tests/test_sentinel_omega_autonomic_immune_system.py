from datetime import datetime, timedelta, timezone

from federation.sentinel_omega.autonomic_immune_system import (
    AuthorityTier,
    AutonomicImmuneController,
    BreakerState,
    CircuitBreaker,
    CreativeTimeSLO,
    CreativeTimeSample,
    DependencyGraph,
    FailureFingerprint,
    RepairAttempt,
    RepairMemory,
    RepairRunbook,
    RemediationDisposition,
    SelfTestCheck,
    SelfTestReport,
)


NOW = datetime(2026, 9, 3, 0, 0, tzinfo=timezone.utc)


def fingerprint():
    return FailureFingerprint(
        target="apps-script-sentinel",
        failure_class="stale_heartbeat",
        error_signature="heartbeat age exceeded threshold",
        dependency_epoch="dep-7",
        provider_epoch="gas-4",
        source_epoch="main-1",
    )


def test_fingerprint_is_stable_under_whitespace_and_case():
    a = fingerprint()
    b = FailureFingerprint(
        target="APPS-SCRIPT-SENTINEL",
        failure_class="STALE_HEARTBEAT",
        error_signature=" heartbeat   age EXCEEDED threshold ",
        dependency_epoch="dep-7",
        provider_epoch="gas-4",
        source_epoch="main-1",
    )
    assert a.digest() == b.digest()


def test_repair_memory_prevents_blind_retry_until_epoch_changes():
    fp = fingerprint()
    runbook = RepairRunbook(
        runbook_id="RB-HEARTBEAT-1",
        failure_classes=("stale_heartbeat",),
        max_authority=AuthorityTier.A1_INTERNAL,
        reversible=True,
        route_family="gas-trigger-repair",
    )
    memory = RepairMemory().with_attempt(
        RepairAttempt(
            fingerprint_digest=fp.digest(),
            runbook_id=runbook.runbook_id,
            route_family=runbook.route_family,
            attempted_at=NOW,
            result="FAILED",
            state_epoch="epoch-1",
        )
    )
    assert memory.unchanged_route_failed(fp, runbook, state_epoch="epoch-1")
    assert not memory.unchanged_route_failed(fp, runbook, state_epoch="epoch-2")


def test_controller_selects_lowest_authority_safe_repair_with_proof():
    fp = fingerprint()
    graph = DependencyGraph(
        {"apps-script-sentinel": {"queue", "sync-bus"}, "queue": {"creative-session"}}
    )
    runbooks = [
        RepairRunbook(
            runbook_id="RB-A2",
            failure_classes=("stale_heartbeat",),
            max_authority=AuthorityTier.A2_REVERSIBLE_PROVIDER,
            reversible=True,
            rollback_ref="trigger-backup",
        ),
        RepairRunbook(
            runbook_id="RB-A1",
            failure_classes=("stale_heartbeat",),
            max_authority=AuthorityTier.A1_INTERNAL,
            reversible=True,
            rollback_ref="config-snapshot",
        ),
    ]
    decision = AutonomicImmuneController(
        runbooks=runbooks, dependency_graph=graph
    ).decide(
        fp,
        authority_ceiling=AuthorityTier.A2_REVERSIBLE_PROVIDER,
        state_epoch="e1",
    )
    assert decision.disposition == RemediationDisposition.AUTO_REPAIR
    assert decision.runbook_id == "RB-A1"
    assert decision.owner_interrupt_required is False
    assert decision.affected_nodes == ("creative-session", "queue", "sync-bus")
    assert "CANARY" in decision.proof_requirements
    assert "SEMANTIC_READBACK" in decision.proof_requirements


def test_controller_reroutes_instead_of_repeating_failed_route():
    fp = fingerprint()
    runbook = RepairRunbook(
        runbook_id="RB-1",
        failure_classes=("stale_heartbeat",),
        max_authority=AuthorityTier.A1_INTERNAL,
        reversible=True,
        route_family="route-a",
    )
    memory = RepairMemory(
        (
            RepairAttempt(
                fingerprint_digest=fp.digest(),
                runbook_id="RB-1",
                route_family="route-a",
                attempted_at=NOW,
                result="FAILED",
                state_epoch="e1",
            ),
        )
    )
    decision = AutonomicImmuneController(
        runbooks=(runbook,), memory=memory
    ).decide(
        fp,
        authority_ceiling=AuthorityTier.A1_INTERNAL,
        state_epoch="e1",
        safe_alternate_routes=("route-a", "route-b"),
    )
    assert decision.disposition == RemediationDisposition.REROUTE
    assert decision.reason == "safe_alternate_route:route-b"
    assert not decision.owner_interrupt_required


def test_controller_escalates_only_when_known_repair_exceeds_authority():
    fp = fingerprint()
    runbook = RepairRunbook(
        runbook_id="RB-IAM",
        failure_classes=("stale_heartbeat",),
        max_authority=AuthorityTier.A3_OWNER_RESERVED,
        reversible=False,
    )
    decision = AutonomicImmuneController(runbooks=(runbook,)).decide(
        fp,
        authority_ceiling=AuthorityTier.A1_INTERNAL,
        state_epoch="e1",
    )
    assert decision.disposition == RemediationDisposition.ESCALATE_OWNER
    assert decision.owner_interrupt_required


def test_circuit_breaker_opens_and_allows_half_open_probe_after_cooldown():
    breaker = CircuitBreaker(failure_threshold=2, cooldown=timedelta(minutes=5))
    breaker.record_failure(NOW)
    assert breaker.state == BreakerState.CLOSED
    breaker.record_failure(NOW + timedelta(seconds=10))
    assert breaker.state == BreakerState.OPEN
    assert not breaker.allow_probe(NOW + timedelta(minutes=2))
    assert breaker.allow_probe(NOW + timedelta(minutes=6))
    assert breaker.state == BreakerState.HALF_OPEN
    breaker.record_success()
    assert breaker.state == BreakerState.CLOSED


def test_creative_time_slo_measures_owner_protection():
    slo = CreativeTimeSLO()
    metrics = slo.evaluate(
        [
            CreativeTimeSample(
                incident_id="i1",
                detected_at=NOW,
                resolved_at=NOW + timedelta(seconds=60),
                owner_interrupted=False,
            ),
            CreativeTimeSample(
                incident_id="i2",
                detected_at=NOW,
                resolved_at=NOW + timedelta(seconds=120),
                owner_interrupted=True,
            ),
            CreativeTimeSample(
                incident_id="i3",
                detected_at=NOW,
                resolved_at=None,
                owner_interrupted=False,
            ),
        ]
    )
    assert metrics.routine_incidents == 3
    assert metrics.auto_resolved_without_owner == 1
    assert metrics.owner_interruptions == 1
    assert metrics.protection_rate == 1 / 3
    assert metrics.mean_time_to_resolve_seconds == 90.0


def test_self_test_report_fails_closed():
    report = SelfTestReport(
        checked_at=NOW,
        checks=(
            SelfTestCheck("heartbeat", True, "p1"),
            SelfTestCheck("repair-readback", False, "p2"),
        ),
    )
    assert report.healthy is False
    assert report.failed_checks == ("repair-readback",)
