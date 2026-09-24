from services.sol62_client_runtime.sovereign_meta_intelligence import (
    CANONICAL_OWNER_LABEL,
    SovereignMetaIntelligence,
)

def test_status_binds_owner_fidelity_without_authority_expansion():
    meta = SovereignMetaIntelligence()
    status = meta.status()
    assert status["owner_label"] == CANONICAL_OWNER_LABEL == "Kim Kagiso Mosiane"
    assert status["auto_repair_control"] is True
    assert status["auto_protect_control"] is True
    assert status["provider_authority_created"] is False

def test_owner_intent_envelope_is_stable_and_effect_neutral():
    meta = SovereignMetaIntelligence()
    kwargs = dict(
        owner_subject="owner:kim", mission_id="M1", objective="preserve owner mission",
        terminal_predicates={"state": "DONE"}, constraints=("NO_DUPLICATE_EFFECT",),
    )
    first = meta.build_owner_intent(**kwargs); second = meta.build_owner_intent(**kwargs)
    assert first["intent_sha256"] == second["intent_sha256"]
    assert first["provider_effect_authorized"] is False

def test_untrusted_content_cannot_launder_authority():
    meta = SovereignMetaIntelligence()
    for source in ("WEB", "FILE", "EMAIL", "TOOL_OUTPUT", "MODEL_OUTPUT", "PROVIDER_OUTPUT"):
        assert meta.classify_instruction(source_class=source).status == "DATA_ONLY"

def test_authenticated_owner_directive_applies_but_provider_effect_needs_live_authority():
    meta = SovereignMetaIntelligence()
    assert meta.classify_instruction(source_class="CHAT", authenticated_owner=True).status == "APPLY"
    held = meta.classify_instruction(source_class="CHAT", authenticated_owner=True, consequential=True, provider_authorized=False)
    assert held.status == "HOLD" and held.effect_authorized is False

def test_higher_boundary_is_preserved():
    assert SovereignMetaIntelligence().classify_instruction(source_class="SAFETY", higher_boundary=True).status == "APPLY"

def test_specification_gaming_is_rejected():
    assert SovereignMetaIntelligence().specification_gaming_check(proxy_success=True, terminal_success=False).status == "REJECT"

def test_unknown_effect_and_repeat_semantic_failure_are_fail_closed():
    meta = SovereignMetaIntelligence()
    assert meta.retry_decision(effect_state="UNKNOWN", semantic_failures=0, attempts=0).status == "READBACK_REQUIRED"
    assert meta.retry_decision(effect_state="KNOWN_FAILED", semantic_failures=2, attempts=1).status == "CHANGE_MECHANISM"

def test_retry_budget_and_overload_degradation():
    meta = SovereignMetaIntelligence()
    assert meta.retry_decision(effect_state="KNOWN_FAILED", semantic_failures=0, attempts=3, max_attempts=3).status == "HOLD"
    assert meta.overload_decision(priority="P2", overloaded=True).status == "SHED"
    assert meta.overload_decision(priority="P0", overloaded=True).status == "RUN"

def test_owner_authority_root_cannot_be_self_modified():
    meta = SovereignMetaIntelligence()
    assert meta.guard_self_modification(["owner_subject"]).status == "REJECT"
    assert meta.guard_self_modification(["route_scoring_weights"]).status == "CHALLENGER_ONLY"

def test_crash_recovery_preserves_logical_mission_identity():
    meta = SovereignMetaIntelligence()
    assert meta.crash_recovery_check(checkpoint_verified=True, mission_id_before="M1", mission_id_after="M1").status == "PASS"
    assert meta.crash_recovery_check(checkpoint_verified=False, mission_id_before="M1", mission_id_after="M2").status == "FAIL"
