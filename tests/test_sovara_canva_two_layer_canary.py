from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from sovara.creative.canva_two_layer_canary import (
    CanvaCanaryState,
    CanvaCommitApproval,
    CanvaCommitReadback,
    CanvaCreateAuthority,
    CanvaCreateReadback,
    CanvaDraftAuthority,
    CanvaDraftObservation,
    CanvaInvariantContract,
    CanvaOwnerSelectionReceipt,
    evaluate_candidate_conversion_readiness,
    evaluate_commit_readiness,
    evaluate_create_readback,
    evaluate_draft_readiness,
    evaluate_saved_design_readback,
    load_canva_invariant_contract,
    source_only_canva_decision,
)


NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
SCHEMA_SHA = "1" * 64
BRAND_SHA = "2" * 64
ELIGIBILITY_SHA = "3" * 64
REQUEST_SHA = "4" * 64
OPERATIONS_SHA = "5" * 64
PREVIEW_SHA = "6" * 64
OWNER_SHA = "7" * 64
TITLE_SHA = "8" * 64
DESIGN_SHA = "9" * 64


def contract(**overrides) -> CanvaInvariantContract:
    base = dict(
        schema="SOVARA_CANVA_TWO_LAYER_CANARY_CONTRACT_V1",
        invariant_id="SC-CANVA-TWO-LAYER-TEST-001",
        candidate_set_id="candidate-set-001",
        expected_candidate_count=4,
        owner_selection_required=True,
        age_state_required="VERIFIED_ADULT_OR_SYNTHETIC",
        consent_state_required="AFFIRMATIVE_OR_NOT_APPLICABLE",
        rights_state_required="VERIFIED",
        asset_origin_state_required="VERIFIED",
        raw_sensitive_payload_allowed=False,
        connector_schema_snapshot_id="canva-schema-test",
        connector_schema_sha256=SCHEMA_SHA,
        connector_tools=(
            "create_design_from_candidate",
            "start_editing_transaction",
            "perform_editing_operations",
            "commit_editing_transaction",
            "cancel_editing_transaction",
            "get_design",
        ),
        schema_checked_at="2026-08-30T10:00:00Z",
        schema_expires_at="2026-08-30T14:00:00Z",
        max_designs=1,
        max_draft_operations=20,
        create_effect_authorized=False,
        draft_effect_authorized=False,
        commit_effect_authorized=False,
        export_allowed=False,
        download_allowed=False,
        share_allowed=False,
        publish_allowed=False,
        required_readbacks=(
            "CREATE_REQUEST_BINDING",
            "DESIGN_METADATA",
            "DRAFT_TRANSACTION",
            "OWNER_PREVIEW",
            "COMMIT_RESULT",
            "POST_COMMIT_DESIGN_METADATA",
        ),
        rollback_requirements=("CREATE_ROLLBACK", "DRAFT_CANCEL"),
    )
    base.update(overrides)
    return CanvaInvariantContract(**base)


def selection(**overrides) -> CanvaOwnerSelectionReceipt:
    base = dict(
        selection_id="selection-001",
        invariant_id="SC-CANVA-TWO-LAYER-TEST-001",
        connector_schema_sha256=SCHEMA_SHA,
        candidate_set_id="candidate-set-001",
        candidate_id="candidate-003",
        job_id="job-001",
        brand_controls_sha256=BRAND_SHA,
        eligibility_evidence_sha256=ELIGIBILITY_SHA,
        selected_by="OWNER",
        owner_authored=True,
        trusted_surface_verified=True,
        explicit_not_inferred=True,
        issued_at="2026-08-30T11:30:00Z",
        expires_at="2026-08-30T12:30:00Z",
        single_use=True,
    )
    base.update(overrides)
    return CanvaOwnerSelectionReceipt(**base)


def create_authority(**overrides) -> CanvaCreateAuthority:
    base = dict(
        authority_id="create-authority-001",
        selection_id="selection-001",
        invariant_id="SC-CANVA-TWO-LAYER-TEST-001",
        provider_name="CANVA",
        connector_schema_sha256=SCHEMA_SHA,
        brand_controls_sha256=BRAND_SHA,
        exact_request_sha256=REQUEST_SHA,
        runtime_identity="codex-apps:canva",
        credential_reference="connector:canva:current-user",
        privacy_eligible=True,
        create_effect_authorized=True,
        max_creations=1,
        create_rollback_supported=True,
        create_rollback_proof_ref="provider-capability:delete-or-archive-created-design",
        issued_at="2026-08-30T11:35:00Z",
        expires_at="2026-08-30T12:30:00Z",
        single_use=True,
    )
    base.update(overrides)
    return CanvaCreateAuthority(**base)


def create_readback(**overrides) -> CanvaCreateReadback:
    base = dict(
        authority_id="create-authority-001",
        selection_id="selection-001",
        exact_request_sha256=REQUEST_SHA,
        job_id="job-001",
        candidate_id="candidate-003",
        design_id="design-001",
        owner_fingerprint_sha256=OWNER_SHA,
        title_sha256=TITLE_SHA,
        page_count=1,
        created_at="2026-08-30T11:40:00Z",
        updated_at="2026-08-30T11:40:00Z",
        provider_native_readback=True,
        authority_consumed=True,
        proof_ref="canva:get_design:design-001",
    )
    base.update(overrides)
    return CanvaCreateReadback(**base)


def draft_authority(**overrides) -> CanvaDraftAuthority:
    base = dict(
        authority_id="draft-authority-001",
        create_authority_id="create-authority-001",
        selection_id="selection-001",
        design_id="design-001",
        connector_schema_sha256=SCHEMA_SHA,
        brand_controls_sha256=BRAND_SHA,
        operations_sha256=OPERATIONS_SHA,
        runtime_identity="codex-apps:canva",
        credential_reference="connector:canva:current-user",
        draft_effect_authorized=True,
        max_operations=3,
        cancel_draft_supported=True,
        cancel_draft_proof_ref="canva:cancel_editing_transaction",
        issued_at="2026-08-30T11:42:00Z",
        expires_at="2026-08-30T12:30:00Z",
        single_use=True,
    )
    base.update(overrides)
    return CanvaDraftAuthority(**base)


def draft_observation(**overrides) -> CanvaDraftObservation:
    base = dict(
        draft_authority_id="draft-authority-001",
        design_id="design-001",
        transaction_id="transaction-001",
        operations_sha256=OPERATIONS_SHA,
        operations_applied_count=3,
        draft_only=True,
        provider_native_readback=True,
        authority_consumed=True,
        preview_ref="canva:get_design_thumbnail:transaction-001",
        preview_sha256=PREVIEW_SHA,
        previewed_at="2026-08-30T11:50:00Z",
        proof_ref="canva:draft-receipt:transaction-001",
    )
    base.update(overrides)
    return CanvaDraftObservation(**base)


def approval(**overrides) -> CanvaCommitApproval:
    base = dict(
        approval_id="commit-approval-001",
        selection_id="selection-001",
        design_id="design-001",
        transaction_id="transaction-001",
        operations_sha256=OPERATIONS_SHA,
        preview_sha256=PREVIEW_SHA,
        approved_by="OWNER",
        owner_authored=True,
        trusted_surface_verified=True,
        explicit_after_preview=True,
        commit_effect_authorized=True,
        issued_at="2026-08-30T11:55:00Z",
        expires_at="2026-08-30T12:15:00Z",
        single_use=True,
    )
    base.update(overrides)
    return CanvaCommitApproval(**base)


def commit_readback(**overrides) -> CanvaCommitReadback:
    base = dict(
        approval_id="commit-approval-001",
        design_id="design-001",
        transaction_id="transaction-001",
        operations_sha256=OPERATIONS_SHA,
        committed=True,
        approval_consumed=True,
        provider_native_readback=True,
        post_commit_design_sha256=DESIGN_SHA,
        post_commit_page_count=1,
        post_commit_updated_at="2026-08-30T11:58:00Z",
        proof_ref="canva:get_design:post-commit:design-001",
    )
    base.update(overrides)
    return CanvaCommitReadback(**base)


class SovaraCanvaTwoLayerCanaryTests(unittest.TestCase):
    def test_candidate_neutral_source_contract_stops_at_owner_selection(self) -> None:
        decision = source_only_canva_decision(contract(), evaluated_at=NOW)
        self.assertEqual(CanvaCanaryState.HOLD_OWNER_SELECTION, decision.state)
        self.assertFalse(decision.ready_for_effect)
        self.assertIn("issues no provider authority", decision.truth_boundary)

    def test_stale_schema_holds_before_owner_or_provider_effect(self) -> None:
        decision = source_only_canva_decision(
            contract(schema_expires_at="2026-08-30T11:59:59Z"), evaluated_at=NOW
        )
        self.assertEqual(CanvaCanaryState.HOLD_SCHEMA_FRESHNESS, decision.state)

    def test_inferred_or_replayed_selection_is_rejected(self) -> None:
        inferred = evaluate_candidate_conversion_readiness(
            contract(), selection(explicit_not_inferred=False), create_authority(), evaluated_at=NOW
        )
        replayed = evaluate_candidate_conversion_readiness(
            contract(),
            selection(),
            create_authority(),
            evaluated_at=NOW,
            consumed_receipt_ids=("selection-001",),
        )
        self.assertEqual(CanvaCanaryState.HOLD_SELECTION_RECEIPT, inferred.state)
        self.assertEqual(CanvaCanaryState.HOLD_SELECTION_RECEIPT, replayed.state)

    def test_selection_does_not_self_authorize_create(self) -> None:
        decision = evaluate_candidate_conversion_readiness(
            contract(), selection(), None, evaluated_at=NOW
        )
        self.assertEqual(CanvaCanaryState.HOLD_CREATE_AUTHORITY, decision.state)

    def test_create_authority_must_bind_brand_and_rollback(self) -> None:
        mismatch = evaluate_candidate_conversion_readiness(
            contract(),
            selection(),
            create_authority(brand_controls_sha256="a" * 64),
            evaluated_at=NOW,
        )
        no_rollback = evaluate_candidate_conversion_readiness(
            contract(),
            selection(),
            create_authority(create_rollback_supported=False, create_rollback_proof_ref=""),
            evaluated_at=NOW,
        )
        self.assertEqual(CanvaCanaryState.HOLD_CREATE_AUTHORITY, mismatch.state)
        self.assertEqual(CanvaCanaryState.HOLD_CREATE_ROLLBACK, no_rollback.state)

    def test_exact_receipts_can_reach_one_candidate_conversion_ready(self) -> None:
        decision = evaluate_candidate_conversion_readiness(
            contract(), selection(), create_authority(), evaluated_at=NOW
        )
        self.assertEqual(CanvaCanaryState.READY_FOR_CANDIDATE_CONVERSION, decision.state)
        self.assertTrue(decision.ready_for_effect)

    def test_create_readback_requires_exact_candidate_and_forbids_export(self) -> None:
        mismatch = evaluate_create_readback(
            contract(),
            selection(),
            create_authority(),
            create_readback(candidate_id="candidate-004"),
            evaluated_at=NOW,
        )
        exported = evaluate_create_readback(
            contract(),
            selection(),
            create_authority(),
            create_readback(export_performed=True),
            evaluated_at=NOW,
        )
        self.assertEqual(CanvaCanaryState.HOLD_CREATE_READBACK, mismatch.state)
        self.assertEqual(CanvaCanaryState.HOLD_CREATE_READBACK, exported.state)
        self.assertIn("EXPORT_PERFORMED", exported.reasons)

    def test_create_readback_stops_at_separate_draft_authority(self) -> None:
        decision = evaluate_create_readback(
            contract(), selection(), create_authority(), create_readback(), evaluated_at=NOW
        )
        self.assertEqual(CanvaCanaryState.HOLD_DRAFT_AUTHORITY, decision.state)
        self.assertTrue(decision.receipt_validated)

    def test_draft_requires_cancel_capability_and_replay_protection(self) -> None:
        no_cancel = evaluate_draft_readiness(
            contract(),
            selection(),
            create_authority(),
            create_readback(),
            draft_authority(cancel_draft_supported=False, cancel_draft_proof_ref=""),
            evaluated_at=NOW,
        )
        replayed = evaluate_draft_readiness(
            contract(),
            selection(),
            create_authority(),
            create_readback(),
            draft_authority(),
            evaluated_at=NOW,
            consumed_receipt_ids=("draft-authority-001",),
        )
        self.assertEqual(CanvaCanaryState.HOLD_DRAFT_ROLLBACK, no_cancel.state)
        self.assertEqual(CanvaCanaryState.HOLD_DRAFT_AUTHORITY, replayed.state)

    def test_exact_draft_authority_reaches_draft_only_ready(self) -> None:
        decision = evaluate_draft_readiness(
            contract(),
            selection(),
            create_authority(),
            create_readback(),
            draft_authority(),
            evaluated_at=NOW,
        )
        self.assertEqual(CanvaCanaryState.READY_FOR_DRAFT_EDIT, decision.state)
        self.assertTrue(decision.ready_for_effect)
        self.assertIn("COMMIT_AUTHORITY_FALSE", decision.reasons)

    def test_draft_preview_does_not_self_authorize_commit(self) -> None:
        decision = evaluate_commit_readiness(
            contract(),
            selection(),
            create_authority(),
            create_readback(),
            draft_authority(),
            draft_observation(),
            None,
            evaluated_at=NOW,
        )
        self.assertEqual(CanvaCanaryState.HOLD_COMMIT_APPROVAL, decision.state)

    def test_commit_approval_must_be_after_exact_preview(self) -> None:
        early = evaluate_commit_readiness(
            contract(),
            selection(),
            create_authority(),
            create_readback(),
            draft_authority(),
            draft_observation(),
            approval(issued_at="2026-08-30T11:45:00Z"),
            evaluated_at=NOW,
        )
        mismatch = evaluate_commit_readiness(
            contract(),
            selection(),
            create_authority(),
            create_readback(),
            draft_authority(),
            draft_observation(),
            approval(preview_sha256="a" * 64),
            evaluated_at=NOW,
        )
        self.assertEqual(CanvaCanaryState.HOLD_COMMIT_APPROVAL, early.state)
        self.assertEqual(CanvaCanaryState.HOLD_COMMIT_APPROVAL, mismatch.state)

    def test_explicit_post_preview_approval_reaches_one_commit_ready(self) -> None:
        decision = evaluate_commit_readiness(
            contract(),
            selection(),
            create_authority(),
            create_readback(),
            draft_authority(),
            draft_observation(),
            approval(),
            evaluated_at=NOW,
        )
        self.assertEqual(CanvaCanaryState.READY_FOR_COMMIT, decision.state)
        self.assertTrue(decision.ready_for_effect)

    def test_post_commit_readback_forbids_publish_and_requires_exact_binding(self) -> None:
        published = evaluate_saved_design_readback(
            contract(),
            selection(),
            create_authority(),
            create_readback(),
            draft_authority(),
            draft_observation(),
            approval(),
            commit_readback(publish_performed=True),
            evaluated_at=NOW,
        )
        mismatch = evaluate_saved_design_readback(
            contract(),
            selection(),
            create_authority(),
            create_readback(),
            draft_authority(),
            draft_observation(),
            approval(),
            commit_readback(transaction_id="transaction-other"),
            evaluated_at=NOW,
        )
        self.assertEqual(CanvaCanaryState.HOLD_COMMIT_READBACK, published.state)
        self.assertIn("PUBLISH_PERFORMED", published.reasons)
        self.assertEqual(CanvaCanaryState.HOLD_COMMIT_READBACK, mismatch.state)

    def test_complete_receipt_set_validates_only_one_saved_design_receipt(self) -> None:
        decision = evaluate_saved_design_readback(
            contract(),
            selection(),
            create_authority(),
            create_readback(),
            draft_authority(),
            draft_observation(),
            approval(),
            commit_readback(),
            evaluated_at=NOW,
        )
        self.assertEqual(CanvaCanaryState.SAVED_DESIGN_RECEIPT_VALIDATED, decision.state)
        self.assertTrue(decision.receipt_validated)
        self.assertFalse(decision.ready_for_effect)
        self.assertIn("does not prove export", decision.truth_boundary)
        self.assertIn("receipt provenance", decision.truth_boundary)

    def test_governance_contract_loads_and_contains_no_candidate_choice(self) -> None:
        path = (
            Path(__file__).resolve().parents[1]
            / "governance"
            / "sovara_canva_two_layer_canary_contract_v1.json"
        )
        loaded = load_canva_invariant_contract(path)
        self.assertEqual(4, loaded.expected_candidate_count)
        self.assertFalse(loaded.create_effect_authorized)
        self.assertNotIn("candidate_id", json.loads(path.read_text()))

    def test_loader_rejects_candidate_choice_leaked_into_layer_one(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "governance"
            / "sovara_canva_two_layer_canary_contract_v1.json"
        )
        payload = json.loads(source.read_text())
        payload["candidate_id"] = "candidate-003"
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "selection fields"):
                load_canva_invariant_contract(path)

    def test_source_contract_cannot_self_authorize_any_provider_effect(self) -> None:
        for field in (
            "create_effect_authorized",
            "draft_effect_authorized",
            "commit_effect_authorized",
            "export_allowed",
            "download_allowed",
            "share_allowed",
            "publish_allowed",
        ):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "cannot authorize effects"):
                    contract(**{field: True})

    def test_authority_booleans_and_counts_cannot_be_string_coerced(self) -> None:
        with self.assertRaisesRegex(ValueError, "literal true/false"):
            create_authority(create_effect_authorized="false")
        with self.assertRaisesRegex(ValueError, "not a coerced value"):
            draft_authority(max_operations=True)


if __name__ == "__main__":
    unittest.main()
