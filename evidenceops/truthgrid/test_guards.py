import pytest

from evidenceops.truthgrid.guards import (
    Mission,
    MissionLockDecision,
    MutationIntent,
    TruthGridGuard,
    TruthGridViolation,
)


def intent(**overrides):
    base = dict(
        sheet="SOURCE REGISTRY",
        operation="UPDATE",
        target_key="SRC-001",
        row_identity_resolved_by_key=True,
        values={"Status": "ACTIVE"},
        source_ids=("SRC-NATIVE-001",),
        receipt_ids=("GR-001",),
        provider_readback_planned=True,
    )
    base.update(overrides)
    return MutationIntent(**base)


def test_raw_integrity_rejected_outside_manifest():
    guard = TruthGridGuard()
    with pytest.raises(TruthGridViolation, match="RAW_INTEGRITY_OUTSIDE_MANIFEST"):
        guard.validate_mutation(intent(values={"Status": "ACTIVE", "Hash": "abc"}))


def test_raw_integrity_allowed_in_manifest():
    guard = TruthGridGuard()
    guard.validate_mutation(
        intent(
            sheet="INTEGRITY MANIFEST",
            values={"Hash": "abc", "Hash_Type": "SHA-256", "Hash_Scope": "LOCAL_EXPORT"},
        )
    )


def test_positional_update_rejected():
    guard = TruthGridGuard()
    with pytest.raises(TruthGridViolation, match="KEY_BOUND_TARGET_REQUIRED"):
        guard.validate_mutation(
            intent(target_key=None, row_identity_resolved_by_key=False)
        )


def test_ephemeral_gmail_attachment_id_cannot_be_durable_source_id():
    guard = TruthGridGuard()
    with pytest.raises(TruthGridViolation, match="EPHEMERAL_GMAIL_HANDLE"):
        guard.validate_mutation(
            intent(values={"Source_ID": "GMAIL_ATTACHMENT_ID:opaque-handle"})
        )


def test_attachment_id_requires_ephemeral_type():
    guard = TruthGridGuard()
    with pytest.raises(TruthGridViolation, match="GMAIL_ATTACHMENT_ID_TYPE_REQUIRED"):
        guard.validate_mutation(
            intent(values={"attachment_id": "opaque", "Identity_Type": "PROVIDER_NATIVE"})
        )


def test_revision_drift_rejected():
    guard = TruthGridGuard()
    with pytest.raises(TruthGridViolation, match="STALE_REVISION_TARGET"):
        guard.validate_mutation(
            intent(current_revision_id="r2", target_revision_id="r1")
        )


def test_role_does_not_promote_to_authority_without_instrument():
    guard = TruthGridGuard()
    with pytest.raises(TruthGridViolation, match="ROLE_REPRESENTATION_IS_NOT_AUTHORITY"):
        guard.validate_mutation(
            intent(
                values={"Authority_Status": "VERIFIED"},
                source_classifications=("ROLE_REPRESENTATION",),
            )
        )


def test_authority_can_promote_with_verified_authority_source_class():
    guard = TruthGridGuard()
    guard.validate_mutation(
        intent(
            values={"Authority_Status": "VERIFIED"},
            source_classifications=("DELEGATION_INSTRUMENT",),
        )
    )


def test_generic_release_promotion_requires_receipt():
    guard = TruthGridGuard()
    with pytest.raises(TruthGridViolation, match="RELEASE_PROMOTION_REQUIRES_RECEIPTS"):
        guard.validate_mutation(
            intent(values={"Release_Status": "RELEASE_CLEARED"}, receipt_ids=())
        )


def test_release_gate_named_schema_is_required():
    guard = TruthGridGuard()
    with pytest.raises(TruthGridViolation, match="RELEASE_RECEIPT_SCHEMA_MISSING"):
        guard.validate_mutation(
            intent(sheet="RELEASE GATES", values={"Gate_Receipt_ID": "GR-001"})
        )


def test_provider_readback_plan_is_mandatory():
    guard = TruthGridGuard()
    with pytest.raises(TruthGridViolation, match="PROVIDER_READBACK_REQUIRED"):
        guard.validate_mutation(intent(provider_readback_planned=False))


def test_foundation_lock_blocks_downstream_when_truthgrid_open():
    mission = Mission(
        mission_id="TRUTHGRID",
        complete=False,
        mandatory_open_dependencies=("RV-GLOBAL-001", "GEN-AUD-022"),
        downstream_missions=("188", "JE", "PAIA_DHET"),
    )
    assert (
        TruthGridGuard.mission_lock(mission, "188")
        == MissionLockDecision.STAY_ON_FOUNDATION
    )
    with pytest.raises(TruthGridViolation, match="FOUNDATION_COMPLETION_LOCK"):
        TruthGridGuard.assert_downstream_allowed(mission, "188")


def test_foundation_lock_allows_explicit_override():
    mission = Mission(
        mission_id="TRUTHGRID",
        complete=False,
        mandatory_open_dependencies=("RV-GLOBAL-001",),
        downstream_missions=("188",),
        explicit_user_override=True,
    )
    assert (
        TruthGridGuard.mission_lock(mission, "188")
        == MissionLockDecision.OVERRIDE_ALLOWED
    )


def test_completion_gate_is_minimum_gate_not_average_score():
    assert not TruthGridGuard.completion_gate(
        global_revalidation_closed=False,
        p0_closed=True,
        p1_closed=True,
        p2_closed=True,
        unresolved_gap_count=0,
        undispositioned_contradiction_count=0,
        genesis_parent_audits_passed=True,
        writer_canaries_passed=True,
        dashboard_generated_from_live_matrix=True,
    )


def test_completion_gate_passes_only_when_every_required_gate_closes():
    assert TruthGridGuard.completion_gate(
        global_revalidation_closed=True,
        p0_closed=True,
        p1_closed=True,
        p2_closed=True,
        unresolved_gap_count=0,
        undispositioned_contradiction_count=0,
        genesis_parent_audits_passed=True,
        writer_canaries_passed=True,
        dashboard_generated_from_live_matrix=True,
    )
