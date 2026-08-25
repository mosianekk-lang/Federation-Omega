import json
from pathlib import Path

from formation_omega.powerhouse import (
    FormationOmega,
    ProofState,
    ReleaseGate,
    SurfaceReadback,
    precedence_rank,
)


def test_upgrade_manifest_has_exactly_100_unique_controls():
    manifest = json.loads(
        Path("formation_omega/upgrade_manifest.json").read_text(encoding="utf-8")
    )
    ids = [item["id"] for item in manifest["upgrades"]]
    assert len(ids) == 100
    assert len(set(ids)) == 100
    assert ids[0] == "FUP-001"
    assert ids[-1] == "FUP-100"


def test_evidenceops_ceiling_downgrades_legacy_overclaim():
    decision = FormationOmega.claim_decision(ProofState.VERIFIED, ProofState.CONTESTED)
    assert decision.downgraded is True
    assert decision.permitted == ProofState.CONTESTED
    assert (
        FormationOmega.legacy_counsel_classification(
            ProofState.VERIFIED, ProofState.CONTESTED
        )
        == "LEGAL_VULNERABILITY"
    )


def test_disproved_requires_disproof_evidence():
    decision = FormationOmega.claim_decision(ProofState.DISPROVED, ProofState.VERIFIED)
    assert decision.downgraded is True
    assert decision.permitted == ProofState.VERIFIED


def test_negative_search_is_not_nonexistence():
    assert FormationOmega.negative_evidence_guard(False) == "NOT_FOUND_IN_SEARCHED_SCOPE"


def test_surface_harmonisation_requires_exact_local_readback():
    verified = SurfaceReadback(
        surface="GitHub",
        expected_semantics="formation-omega@1.0",
        observed_semantics="formation-omega@1.0",
        authority_verified=True,
        target_verified=True,
        version_verified=True,
    )
    stale = SurfaceReadback(
        surface="ProviderRuntime",
        expected_semantics="formation-omega@1.0",
        observed_semantics=None,
        authority_verified=False,
        target_verified=True,
        version_verified=False,
    )
    assert FormationOmega.surface_harmonized(verified) is True
    assert FormationOmega.all_surfaces_harmonized((verified, stale)) is False


def test_research_does_not_imply_effect_authority():
    assert FormationOmega.research_state_is_effect_authority(True, False) is False
    assert FormationOmega.research_state_is_effect_authority(True, True) is True


def test_timing_does_not_alone_prove_causation():
    assert FormationOmega.temporal_sequence_proves_causation(True, False) is False
    assert FormationOmega.temporal_sequence_proves_causation(True, True) is True


def test_electronic_work_does_not_alone_prove_physical_attendance():
    assert FormationOmega.electronic_work_proves_physical_attendance(True, False) is False
    assert FormationOmega.electronic_work_proves_physical_attendance(True, True) is True


def test_smallest_sufficient_decision_prefers_lowest_burden_complete_route():
    selected = FormationOmega.smallest_sufficient_decision(
        "confirm current case state",
        (
            {
                "name": "full investigation",
                "complete": True,
                "authorised": True,
                "reversible": True,
                "burden": 10,
                "proof_quality": 0.95,
            },
            {
                "name": "administrative confirmation",
                "complete": True,
                "authorised": True,
                "reversible": True,
                "burden": 2,
                "proof_quality": 0.85,
            },
        ),
    )
    assert selected["name"] == "administrative confirmation"


def test_release_gate_holds_owner_reserved_effect_until_approval():
    held = ReleaseGate(
        proof_ok=True,
        legal_accuracy_ok=True,
        privacy_ok=True,
        target_authority_ok=True,
        version_ok=True,
        semantic_readback_ok=True,
        rollback_ok=True,
        owner_approval_required=True,
        owner_approved=False,
    )
    released = ReleaseGate(
        proof_ok=True,
        legal_accuracy_ok=True,
        privacy_ok=True,
        target_authority_ok=True,
        version_ok=True,
        semantic_readback_ok=True,
        rollback_ok=True,
        owner_approval_required=True,
        owner_approved=True,
    )
    assert FormationOmega.release_allowed(held) is False
    assert FormationOmega.release_allowed(released) is True


def test_native_source_has_stronger_precedence_than_legacy_counsel():
    assert precedence_rank("NATIVE_AUTHENTICATED_SOURCE") < precedence_rank(
        "LEXAZANIA_LEGAL_ADVERSARIAL_COUNSEL"
    )
