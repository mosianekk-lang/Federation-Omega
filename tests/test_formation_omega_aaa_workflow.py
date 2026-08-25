from formation_omega.aaa_workflow import (
    AAALearningEvent,
    CapabilityStage,
    CapabilityState,
    EvidenceObservation,
    RouteAttempt,
    RouteOutcome,
    SourceCapabilitySnapshot,
    abstract_learning,
    activate_learning,
    adapt_learning,
    choose_operational_route,
    resolve_current_truth,
    route_retry_decision,
    source_upgrade_decision,
)
from formation_omega.powerhouse import ProofState


def test_fresh_native_export_controls_truth_but_preserves_contradiction():
    resolution = resolve_current_truth(
        (
            EvidenceObservation(
                "provider-export",
                "sovara_namespace_present",
                False,
                "NATIVE_AUTHENTICATED_SOURCE",
                "2026-08-25T09:30:00+00:00",
                ProofState.VERIFIED,
                current=True,
                semantic_readback=True,
            ),
            EvidenceObservation(
                "live-bible-rev50",
                "sovara_namespace_present",
                True,
                "CURRENT_FORMATION_MASTER",
                "2026-08-25T05:30:00+00:00",
                ProofState.SUPPORTED,
                current=True,
            ),
        )
    )
    assert resolution.selected.observation_id == "provider-export"
    assert resolution.selected.value is False
    assert resolution.contradiction is not None
    assert resolution.promotion_allowed is False


def test_stale_native_record_does_not_beat_current_verified_projection():
    resolution = resolve_current_truth(
        (
            EvidenceObservation(
                "stale-provider",
                "scope_state",
                "MISSING",
                "NATIVE_AUTHENTICATED_SOURCE",
                "2026-06-24T19:00:00+00:00",
                ProofState.VERIFIED,
                current=False,
            ),
            EvidenceObservation(
                "current-source",
                "scope_state",
                "PRESENT",
                "CURRENT_FORMATION_MASTER",
                "2026-08-25T09:00:00+00:00",
                ProofState.VERIFIED,
                current=True,
            ),
        )
    )
    assert resolution.selected.value == "PRESENT"


def test_unchanged_failed_route_is_suppressed():
    history = (
        RouteAttempt(
            "queue-1",
            "source deploy",
            "architron-queue-v1",
            "consumer-stale",
            RouteOutcome.FAILURE,
            "2026-08-25T08:00:00+00:00",
        ),
    )
    decision = route_retry_decision(
        RouteAttempt(
            "queue-2",
            "source deploy",
            "architron-queue-v1",
            "consumer-stale",
            RouteOutcome.NEAR_MISS,
            "2026-08-25T09:00:00+00:00",
        ),
        history,
    )
    assert decision.retry_allowed is False


def test_material_precondition_change_allows_bounded_reprobe():
    history = (
        RouteAttempt(
            "auth-old",
            "get project content",
            "foaa-getcontent",
            "manifest-no-script-projects",
            RouteOutcome.FAILURE,
            "2026-06-24T19:00:00+00:00",
        ),
    )
    decision = route_retry_decision(
        RouteAttempt(
            "auth-new",
            "get project content",
            "foaa-getcontent",
            "manifest-script-projects-present",
            RouteOutcome.NEAR_MISS,
            "2026-08-25T09:00:00+00:00",
        ),
        history,
    )
    assert decision.retry_allowed is True
    assert decision.material_precondition_change is True


def test_capability_stage_does_not_inherit_authority_from_presence():
    state = CapabilityState("Apps Script updateContent", True, False, False, False)
    assert state.stage == CapabilityStage.PRESENT


def test_semantic_verification_requires_full_capability_chain():
    state = CapabilityState("Apps Script updateContent", True, True, True, True)
    assert state.stage == CapabilityStage.SEMANTICALLY_VERIFIED


def test_source_upgrade_rejects_loss_of_live_formation_capability():
    live = SourceCapabilitySnapshot(
        "live-v2",
        frozenset({"FO_GAS_CORE", "MODISA_FORMATION_ENGINE"}),
        ("foGasStatus", "runFormationEngine"),
    )
    candidate = SourceCapabilitySnapshot(
        "staged-v2.3",
        frozenset({"FO_GAS_CORE"}),
        ("foGasStatus",),
    )
    decision = source_upgrade_decision(live, candidate)
    assert decision.allowed is False
    assert decision.missing_capabilities == ("MODISA_FORMATION_ENGINE",)


def test_source_upgrade_rejects_duplicate_globals():
    decision = source_upgrade_decision(
        SourceCapabilitySnapshot("live", frozenset({"A"}), ("status",)),
        SourceCapabilitySnapshot("candidate", frozenset({"A"}), ("status", "status")),
    )
    assert decision.allowed is False
    assert decision.duplicate_global_functions == ("status",)


def test_route_selection_excludes_unchanged_failed_route_and_reduces_owner_burden():
    history = (
        RouteAttempt(
            "old-queue",
            "read source",
            "queue-read",
            "stale-consumer",
            RouteOutcome.BLOCKED,
            "2026-08-25T08:00:00+00:00",
        ),
    )
    selected = choose_operational_route(
        "read source",
        (
            {
                "name": "queue",
                "route_fingerprint": "queue-read",
                "precondition_fingerprint": "stale-consumer",
                "complete": True,
                "authorised": True,
                "reversible": True,
                "burden": 1,
                "proof_quality": 0.6,
            },
            {
                "name": "drive-raw-export",
                "route_fingerprint": "drive-raw-export",
                "precondition_fingerprint": "connector-callable",
                "complete": True,
                "authorised": True,
                "reversible": True,
                "burden": 2,
                "proof_quality": 0.95,
            },
        ),
        history,
    )
    assert selected["name"] == "drive-raw-export"


def test_aaa_cycle_abstracts_adapts_and_activates_chat_learning():
    events = (
        AAALearningEvent(
            "evt-1",
            "EVIDENCE_CONTRADICTION",
            "resolve runtime source",
            "provider export contradicted summary",
            ("provider-export", "live-bible"),
        ),
        AAALearningEvent(
            "evt-2",
            "UNCHANGED_ROUTE_FAILURE",
            "execute queue",
            "same queue route remained stale",
            ("queue-readback",),
        ),
        AAALearningEvent(
            "evt-3",
            "SOURCE_CAPABILITY_LOSS",
            "deploy FO-GAS v2.3",
            "candidate omitted live formation engine",
            ("live-export", "candidate-diff"),
        ),
    )
    genes = abstract_learning(events)
    adapted = adapt_learning(
        genes,
        {"evidence_resolution", "route_memory", "source_diff", "route_selection"},
    )
    report = activate_learning(adapted, tests_passed=True, regression_free=True)
    assert len(genes) == 3
    assert len(report.activated_controls) == 3
    assert report.held_controls == ()


def test_external_activation_remains_held_without_external_authority():
    genes = abstract_learning(
        (AAALearningEvent("evt", "OWNER_BURDEN", "workflow", "burden", ("e1",)),)
    )
    report = activate_learning(
        genes,
        tests_passed=True,
        regression_free=True,
        external_effect_required=True,
        external_authority_verified=False,
    )
    assert report.activated_controls == ()
    assert len(report.held_controls) == 1
