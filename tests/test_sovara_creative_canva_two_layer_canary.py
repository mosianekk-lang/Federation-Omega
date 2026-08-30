from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from sovara.creative.canva_two_layer_canary import (
    CanvaCanaryDecision,
    CanvaCanaryState,
    CanvaCommitApproval,
    CanvaCommitReadback,
    CanvaCreateAuthority,
    CanvaCreateReadback,
    CanvaDraftAuthority,
    CanvaDraftObservation,
    CanvaEligibilityEvidence,
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
ROSTER_SHA = "a" * 64
SCHEMA_PROVENANCE_SHA = "b" * 64
ATTESTATION_SHA = "c" * 64
CREATE_LEDGER = ("selection-001", "create-authority-001")
DRAFT_LEDGER = CREATE_LEDGER + ("draft-authority-001",)
COMMIT_LEDGER = DRAFT_LEDGER + ("commit-approval-001",)


def contract(**overrides) -> CanvaInvariantContract:
    base = dict(
        schema="SOVARA_CANVA_TWO_LAYER_CANARY_CONTRACT_V1",
        invariant_id="SC-CANVA-TWO-LAYER-TEST-001",
        candidate_set_id="candidate-set-001",
        candidate_roster_sha256=ROSTER_SHA,
        expected_candidate_count=4,
        owner_selection_required=True,
        age_state_required="VERIFIED_ADULT_OR_SYNTHETIC",
        consent_state_required="AFFIRMATIVE_OR_NOT_APPLICABLE",
        rights_state_required="VERIFIED",
        asset_origin_state_required="VERIFIED",
        raw_sensitive_payload_allowed=False,
        connector_schema_snapshot_id="canva-schema-test",
        connector_schema_sha256=SCHEMA_SHA,
        connector_schema_provenance_sha256=SCHEMA_PROVENANCE_SHA,
        connector_schema_authenticated=True,
        connector_tools=(
            "create_design_from_candidate",
            "start_editing_transaction",
            "perform_editing_operations",
            "commit_editing_transaction",
            "cancel_editing_transaction",
            "get_design",
            "get_design_pages",
            "get_design_thumbnail",
            "delete_design",
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
        candidate_roster_sha256=ROSTER_SHA,
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


def eligibility(**overrides) -> CanvaEligibilityEvidence:
    base = dict(
        evidence_sha256=ELIGIBILITY_SHA,
        candidate_set_id="candidate-set-001",
        candidate_roster_sha256=ROSTER_SHA,
        candidate_id="candidate-003",
        age_state="VERIFIED_ADULT_OR_SYNTHETIC",
        consent_state="AFFIRMATIVE_OR_NOT_APPLICABLE",
        rights_state="VERIFIED",
        asset_origin_state="VERIFIED",
        privacy_eligible=True,
        candidate_membership_verified=True,
        trusted_surface_verified=True,
        attestation_sha256=ATTESTATION_SHA,
        issued_at="2026-08-30T11:29:00Z",
        expires_at="2026-08-30T12:30:00Z",
    )
    base.update(overrides)
    return CanvaEligibilityEvidence(**base)


def create_authority(**overrides) -> CanvaCreateAuthority:
    base = dict(
        authority_id="create-authority-001",
        selection_id="selection-001",
        invariant_id="SC-CANVA-TWO-LAYER-TEST-001",
        provider_name="CANVA",
        connector_schema_sha256=SCHEMA_SHA,
        brand_controls_sha256=BRAND_SHA,
        candidate_id="candidate-003",
        job_id="job-001",
        eligibility_evidence_sha256=ELIGIBILITY_SHA,
        exact_request_sha256=REQUEST_SHA,
        expected_owner_fingerprint_sha256=OWNER_SHA,
        expected_title_sha256=TITLE_SHA,
        runtime_identity="codex-apps:canva",
        credential_reference="connector:canva:current-user",
        privacy_eligible=True,
        create_effect_authorized=True,
        max_creations=1,
        maximum_cost_microunits=0,
        create_rollback_supported=True,
        create_rollback_tool="delete_design",
        create_rollback_proof_sha256="d" * 64,
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
        connector_schema_sha256=SCHEMA_SHA,
        brand_controls_sha256=BRAND_SHA,
        eligibility_evidence_sha256=ELIGIBILITY_SHA,
        runtime_identity="codex-apps:canva",
        credential_reference="connector:canva:current-user",
        design_id="design-001",
        owner_fingerprint_sha256=OWNER_SHA,
        title_sha256=TITLE_SHA,
        page_count=1,
        observed_cost_microunits=0,
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
        candidate_id="candidate-003",
        job_id="job-001",
        connector_schema_sha256=SCHEMA_SHA,
        brand_controls_sha256=BRAND_SHA,
        eligibility_evidence_sha256=ELIGIBILITY_SHA,
        operations_sha256=OPERATIONS_SHA,
        runtime_identity="codex-apps:canva",
        credential_reference="connector:canva:current-user",
        draft_effect_authorized=True,
        max_operations=3,
        maximum_cost_microunits=0,
        cancel_draft_supported=True,
        cancel_draft_proof_sha256="e" * 64,
        issued_at="2026-08-30T11:42:00Z",
        expires_at="2026-08-30T12:30:00Z",
        single_use=True,
    )
    base.update(overrides)
    return CanvaDraftAuthority(**base)


def draft_observation(**overrides) -> CanvaDraftObservation:
    base = dict(
        draft_authority_id="draft-authority-001",
        selection_id="selection-001",
        design_id="design-001",
        candidate_id="candidate-003",
        job_id="job-001",
        connector_schema_sha256=SCHEMA_SHA,
        brand_controls_sha256=BRAND_SHA,
        eligibility_evidence_sha256=ELIGIBILITY_SHA,
        runtime_identity="codex-apps:canva",
        credential_reference="connector:canva:current-user",
        transaction_id="transaction-001",
        operations_sha256=OPERATIONS_SHA,
        operations_applied_count=3,
        observed_cost_microunits=0,
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
        connector_schema_sha256=SCHEMA_SHA,
        brand_controls_sha256=BRAND_SHA,
        eligibility_evidence_sha256=ELIGIBILITY_SHA,
        runtime_identity="codex-apps:canva",
        credential_reference="connector:canva:current-user",
        operations_sha256=OPERATIONS_SHA,
        preview_sha256=PREVIEW_SHA,
        expected_post_commit_design_sha256=DESIGN_SHA,
        approved_by="OWNER",
        owner_authored=True,
        trusted_surface_verified=True,
        explicit_after_preview=True,
        commit_effect_authorized=True,
        maximum_cost_microunits=0,
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
        selection_id="selection-001",
        connector_schema_sha256=SCHEMA_SHA,
        brand_controls_sha256=BRAND_SHA,
        eligibility_evidence_sha256=ELIGIBILITY_SHA,
        runtime_identity="codex-apps:canva",
        credential_reference="connector:canva:current-user",
        operations_sha256=OPERATIONS_SHA,
        committed=True,
        approval_consumed=True,
        provider_native_readback=True,
        post_commit_design_sha256=DESIGN_SHA,
        post_commit_page_count=1,
        observed_cost_microunits=0,
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
            contract(), selection(explicit_not_inferred=False), eligibility(), create_authority(), evaluated_at=NOW
        )
        replayed = evaluate_candidate_conversion_readiness(
            contract(),
            selection(), eligibility(), create_authority(),
            evaluated_at=NOW,
            consumed_receipt_ids=("selection-001",),
        )
        self.assertEqual(CanvaCanaryState.HOLD_SELECTION_RECEIPT, inferred.state)
        self.assertEqual(CanvaCanaryState.HOLD_SELECTION_RECEIPT, replayed.state)

    def test_selection_does_not_self_authorize_create(self) -> None:
        decision = evaluate_candidate_conversion_readiness(
            contract(), selection(), eligibility(), None, evaluated_at=NOW
        )
        self.assertEqual(CanvaCanaryState.HOLD_CREATE_AUTHORITY, decision.state)

    def test_create_authority_must_bind_brand_and_rollback(self) -> None:
        mismatch = evaluate_candidate_conversion_readiness(
            contract(),
            selection(), eligibility(), create_authority(brand_controls_sha256="a" * 64),
            evaluated_at=NOW,
        )
        no_rollback = evaluate_candidate_conversion_readiness(
            contract(),
            selection(), eligibility(), create_authority(create_rollback_supported=False),
            evaluated_at=NOW,
        )
        self.assertEqual(CanvaCanaryState.HOLD_CREATE_AUTHORITY, mismatch.state)
        self.assertEqual(CanvaCanaryState.HOLD_CREATE_ROLLBACK, no_rollback.state)

    def test_exact_receipts_can_reach_one_candidate_conversion_ready(self) -> None:
        decision = evaluate_candidate_conversion_readiness(
            contract(), selection(), eligibility(), create_authority(), evaluated_at=NOW
        )
        self.assertEqual(CanvaCanaryState.READY_FOR_CANDIDATE_CONVERSION, decision.state)
        self.assertFalse(decision.ready_for_effect)
        self.assertFalse(decision.contract_preconditions_met)
        self.assertTrue(decision.envelope_consistent)

    def test_create_readback_requires_exact_candidate_and_forbids_export(self) -> None:
        mismatch = evaluate_create_readback(
            contract(),
            selection(), eligibility(), create_authority(),
            create_readback(candidate_id="candidate-004"),
            evaluated_at=NOW,
            consumed_receipt_ids=CREATE_LEDGER,
        )
        exported = evaluate_create_readback(
            contract(),
            selection(), eligibility(), create_authority(),
            create_readback(export_performed=True),
            evaluated_at=NOW,
            consumed_receipt_ids=CREATE_LEDGER,
        )
        self.assertEqual(CanvaCanaryState.HOLD_CREATE_READBACK, mismatch.state)
        self.assertEqual(CanvaCanaryState.HOLD_CREATE_READBACK, exported.state)
        self.assertIn("EXPORT_PERFORMED", exported.reasons)

    def test_create_readback_stops_at_separate_draft_authority(self) -> None:
        decision = evaluate_create_readback(
            contract(), selection(), eligibility(), create_authority(), create_readback(),
            evaluated_at=NOW, consumed_receipt_ids=CREATE_LEDGER
        )
        self.assertEqual(CanvaCanaryState.HOLD_DRAFT_AUTHORITY, decision.state)
        self.assertTrue(decision.receipt_validated)

    def test_draft_requires_cancel_capability_and_replay_protection(self) -> None:
        no_cancel = evaluate_draft_readiness(
            contract(),
            selection(), eligibility(), create_authority(),
            create_readback(),
            draft_authority(cancel_draft_supported=False),
            evaluated_at=NOW,
            consumed_receipt_ids=CREATE_LEDGER,
        )
        replayed = evaluate_draft_readiness(
            contract(),
            selection(), eligibility(), create_authority(),
            create_readback(),
            draft_authority(),
            evaluated_at=NOW,
            consumed_receipt_ids=DRAFT_LEDGER,
        )
        self.assertEqual(CanvaCanaryState.HOLD_DRAFT_ROLLBACK, no_cancel.state)
        self.assertEqual(CanvaCanaryState.HOLD_DRAFT_AUTHORITY, replayed.state)

    def test_exact_draft_authority_reaches_draft_only_ready(self) -> None:
        decision = evaluate_draft_readiness(
            contract(),
            selection(), eligibility(), create_authority(),
            create_readback(),
            draft_authority(),
            evaluated_at=NOW,
            consumed_receipt_ids=CREATE_LEDGER,
        )
        self.assertEqual(CanvaCanaryState.READY_FOR_DRAFT_EDIT, decision.state)
        self.assertFalse(decision.ready_for_effect)
        self.assertFalse(decision.contract_preconditions_met)
        self.assertTrue(decision.envelope_consistent)
        self.assertIn("COMMIT_AUTHORITY_FALSE", decision.reasons)

    def test_draft_preview_does_not_self_authorize_commit(self) -> None:
        decision = evaluate_commit_readiness(
            contract(),
            selection(), eligibility(), create_authority(),
            create_readback(),
            draft_authority(),
            draft_observation(),
            None,
            evaluated_at=NOW,
            consumed_receipt_ids=DRAFT_LEDGER,
        )
        self.assertEqual(CanvaCanaryState.HOLD_COMMIT_APPROVAL, decision.state)

    def test_commit_approval_must_be_after_exact_preview(self) -> None:
        early = evaluate_commit_readiness(
            contract(),
            selection(), eligibility(), create_authority(),
            create_readback(),
            draft_authority(),
            draft_observation(),
            approval(issued_at="2026-08-30T11:45:00Z"),
            evaluated_at=NOW,
            consumed_receipt_ids=DRAFT_LEDGER,
        )
        mismatch = evaluate_commit_readiness(
            contract(),
            selection(), eligibility(), create_authority(),
            create_readback(),
            draft_authority(),
            draft_observation(),
            approval(preview_sha256="a" * 64),
            evaluated_at=NOW,
            consumed_receipt_ids=DRAFT_LEDGER,
        )
        self.assertEqual(CanvaCanaryState.HOLD_COMMIT_APPROVAL, early.state)
        self.assertEqual(CanvaCanaryState.HOLD_COMMIT_APPROVAL, mismatch.state)

    def test_explicit_post_preview_approval_reaches_one_commit_ready(self) -> None:
        decision = evaluate_commit_readiness(
            contract(),
            selection(), eligibility(), create_authority(),
            create_readback(),
            draft_authority(),
            draft_observation(),
            approval(),
            evaluated_at=NOW,
            consumed_receipt_ids=DRAFT_LEDGER,
        )
        self.assertEqual(CanvaCanaryState.READY_FOR_COMMIT, decision.state)
        self.assertFalse(decision.ready_for_effect)
        self.assertFalse(decision.contract_preconditions_met)
        self.assertTrue(decision.envelope_consistent)

    def test_post_commit_readback_forbids_publish_and_requires_exact_binding(self) -> None:
        published = evaluate_saved_design_readback(
            contract(),
            selection(), eligibility(), create_authority(),
            create_readback(),
            draft_authority(),
            draft_observation(),
            approval(),
            commit_readback(publish_performed=True),
            evaluated_at=NOW,
            consumed_receipt_ids=COMMIT_LEDGER,
        )
        mismatch = evaluate_saved_design_readback(
            contract(),
            selection(), eligibility(), create_authority(),
            create_readback(),
            draft_authority(),
            draft_observation(),
            approval(),
            commit_readback(transaction_id="transaction-other"),
            evaluated_at=NOW,
            consumed_receipt_ids=COMMIT_LEDGER,
        )
        self.assertEqual(CanvaCanaryState.HOLD_COMMIT_READBACK, published.state)
        self.assertIn("PUBLISH_PERFORMED", published.reasons)
        self.assertEqual(CanvaCanaryState.HOLD_COMMIT_READBACK, mismatch.state)

    def test_complete_receipt_set_validates_only_one_saved_design_receipt(self) -> None:
        decision = evaluate_saved_design_readback(
            contract(),
            selection(), eligibility(), create_authority(),
            create_readback(),
            draft_authority(),
            draft_observation(),
            approval(),
            commit_readback(),
            evaluated_at=NOW,
            consumed_receipt_ids=COMMIT_LEDGER,
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

    def test_loader_rejects_nested_payload_and_bogus_connector_schema(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "governance"
            / "sovara_canva_two_layer_canary_contract_v1.json"
        )
        for mutate, message in (
            (lambda value: value.update({"metadata": {"candidate_id": "candidate-003"}}), "unknown fields"),
            (lambda value: value["connector_schema_snapshot"].update({"tools": {"noop": {}}}), "capability mismatch"),
            (
                lambda value: value["connector_schema_snapshot"]["tools"].update(
                    {"delete_design": {"effect": "PROVIDER_WRITE_DELETE", "required_bindings": ["design_id"]}}
                ),
                "capability mismatch",
            ),
            (
                lambda value: value["connector_schema_snapshot"]["semantic_invariants"].append(
                    "selected candidate_id is candidate-003"
                ),
                "semantic invariants mismatch",
            ),
        ):
            payload = json.loads(source.read_text())
            mutate(payload)
            snapshot = payload["connector_schema_snapshot"]
            payload["connector_schema_sha256"] = __import__("hashlib").sha256(
                json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            with tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / "bad.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    load_canva_invariant_contract(path)

    def test_loader_rejects_all_numeric_coercion(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "governance"
            / "sovara_canva_two_layer_canary_contract_v1.json"
        )
        for field, value in (
            ("expected_candidate_count", "4"),
            ("max_designs", True),
            ("max_draft_operations", 20.9),
        ):
            payload = json.loads(source.read_text())
            payload[field] = value
            with tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / "bad.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "literal JSON integer"):
                    load_canva_invariant_contract(path)
        payload = json.loads(source.read_text())
        payload["create_effect_authorized"] = "false"
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "literal JSON boolean"):
                load_canva_invariant_contract(path)

    def test_typed_eligibility_membership_and_roster_are_mandatory(self) -> None:
        for evidence in (
            eligibility(candidate_membership_verified=False),
            eligibility(candidate_roster_sha256="f" * 64),
            eligibility(consent_state="UNVERIFIED"),
        ):
            decision = evaluate_candidate_conversion_readiness(
                contract(), selection(), evidence, create_authority(), evaluated_at=NOW
            )
            self.assertEqual(CanvaCanaryState.HOLD_SELECTION_RECEIPT, decision.state)

        arbitrary = evaluate_candidate_conversion_readiness(
            contract(),
            selection(candidate_id="caller-claimed-candidate"),
            eligibility(candidate_id="caller-claimed-candidate"),
            create_authority(candidate_id="caller-claimed-candidate"),
            evaluated_at=NOW,
        )
        self.assertEqual(CanvaCanaryState.READY_FOR_CANDIDATE_CONVERSION, arbitrary.state)
        self.assertTrue(arbitrary.envelope_consistent)
        self.assertFalse(arbitrary.contract_preconditions_met)
        self.assertFalse(arbitrary.ready_for_effect)
        self.assertIn("UNAUTHENTICATED_ENVELOPE_ONLY", arbitrary.reasons)

    def test_raw_secret_unknown_cost_and_runtime_drift_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "opaque connector handle"):
            create_authority(credential_reference="sk-live-secret-material")
        with self.assertRaisesRegex(ValueError, "secret-shaped"):
            create_authority(credential_reference="connector:canva:sk-live-secret-material")
        with self.assertRaisesRegex(ValueError, "secret-shaped"):
            create_authority(credential_reference="connector:sk-live-secret-material:current-user")
        with self.assertRaisesRegex(ValueError, "zero-cost ceiling"):
            create_authority(maximum_cost_microunits=1)
        drift = evaluate_draft_readiness(
            contract(),
            selection(),
            eligibility(),
            create_authority(),
            create_readback(),
            draft_authority(runtime_identity="other-runtime"),
            evaluated_at=NOW,
            consumed_receipt_ids=CREATE_LEDGER,
        )
        self.assertEqual(CanvaCanaryState.HOLD_DRAFT_AUTHORITY, drift.state)
        with self.assertRaisesRegex(ValueError, "zero-cost ceiling"):
            draft_authority(maximum_cost_microunits=1)
        with self.assertRaisesRegex(ValueError, "zero-cost ceiling"):
            approval(maximum_cost_microunits=1)
        with self.assertRaisesRegex(ValueError, "zero-cost ceiling"):
            commit_readback(observed_cost_microunits=1)

    def test_public_decision_dto_cannot_forge_provider_authority(self) -> None:
        base = dict(
            state=CanvaCanaryState.READY_FOR_COMMIT,
            ready_for_effect=False,
            contract_preconditions_met=False,
            envelope_consistent=True,
            receipt_validated=True,
            next_gate="EXTERNAL_AUTHENTICATED_GATE",
            reasons=("UNAUTHENTICATED_ENVELOPE_ONLY",),
            truth_boundary="No provider authority.",
        )
        for field in ("ready_for_effect", "contract_preconditions_met"):
            forged = dict(base)
            forged[field] = True
            with self.assertRaisesRegex(ValueError, "cannot grant or claim provider authority"):
                CanvaCanaryDecision(**forged)

    def test_arbitrary_draft_cancel_digest_remains_envelope_only(self) -> None:
        decision = evaluate_draft_readiness(
            contract(), selection(), eligibility(), create_authority(), create_readback(),
            draft_authority(cancel_draft_proof_sha256="f" * 64), evaluated_at=NOW,
            consumed_receipt_ids=CREATE_LEDGER,
        )
        self.assertEqual(CanvaCanaryState.READY_FOR_DRAFT_EDIT, decision.state)
        self.assertFalse(decision.ready_for_effect)
        self.assertFalse(decision.contract_preconditions_met)
        self.assertIn("DRAFT_CANCEL_ENVELOPE_BOUND_NOT_AUTHENTICATED", decision.reasons)
        self.assertIn("UNAUTHENTICATED_ENVELOPE_ONLY", decision.reasons)

    def test_complete_lifecycle_is_strictly_monotonic(self) -> None:
        preselection = evaluate_candidate_conversion_readiness(
            contract(),
            selection(),
            eligibility(),
            create_authority(issued_at="2026-08-30T11:29:00Z"),
            evaluated_at=NOW,
        )
        preauthority_create = evaluate_create_readback(
            contract(),
            selection(),
            eligibility(),
            create_authority(),
            create_readback(created_at="2026-08-30T11:34:00Z", updated_at="2026-08-30T11:34:00Z"),
            evaluated_at=NOW,
            consumed_receipt_ids=CREATE_LEDGER,
        )
        predraft_preview = evaluate_commit_readiness(
            contract(),
            selection(),
            eligibility(),
            create_authority(),
            create_readback(),
            draft_authority(),
            draft_observation(previewed_at="2026-08-30T11:41:00Z"),
            approval(),
            evaluated_at=NOW,
            consumed_receipt_ids=DRAFT_LEDGER,
        )
        simultaneous_approval = evaluate_commit_readiness(
            contract(),
            selection(),
            eligibility(),
            create_authority(),
            create_readback(),
            draft_authority(),
            draft_observation(),
            approval(issued_at="2026-08-30T11:50:00Z"),
            evaluated_at=NOW,
            consumed_receipt_ids=DRAFT_LEDGER,
        )
        commit_before_approval = evaluate_saved_design_readback(
            contract(),
            selection(),
            eligibility(),
            create_authority(),
            create_readback(),
            draft_authority(),
            draft_observation(),
            approval(),
            commit_readback(post_commit_updated_at="2026-08-30T11:53:00Z"),
            evaluated_at=NOW,
            consumed_receipt_ids=COMMIT_LEDGER,
        )
        self.assertEqual(CanvaCanaryState.HOLD_CREATE_AUTHORITY, preselection.state)
        self.assertEqual(CanvaCanaryState.HOLD_CREATE_READBACK, preauthority_create.state)
        self.assertEqual(CanvaCanaryState.HOLD_DRAFT_PREVIEW, predraft_preview.state)
        self.assertEqual(CanvaCanaryState.HOLD_COMMIT_APPROVAL, simultaneous_approval.state)
        self.assertEqual(CanvaCanaryState.HOLD_COMMIT_READBACK, commit_before_approval.state)

    def test_consumption_ledger_propagates_to_terminal_gate(self) -> None:
        missing_draft = evaluate_commit_readiness(
            contract(), selection(), eligibility(), create_authority(), create_readback(),
            draft_authority(), draft_observation(), approval(), evaluated_at=NOW,
            consumed_receipt_ids=CREATE_LEDGER,
        )
        missing_approval = evaluate_saved_design_readback(
            contract(), selection(), eligibility(), create_authority(), create_readback(),
            draft_authority(), draft_observation(), approval(), commit_readback(), evaluated_at=NOW,
            consumed_receipt_ids=DRAFT_LEDGER,
        )
        self.assertEqual(CanvaCanaryState.HOLD_DRAFT_PREVIEW, missing_draft.state)
        self.assertEqual(CanvaCanaryState.HOLD_COMMIT_READBACK, missing_approval.state)
        one_shot_ledger = evaluate_saved_design_readback(
            contract(), selection(), eligibility(), create_authority(), create_readback(),
            draft_authority(), draft_observation(), approval(), commit_readback(), evaluated_at=NOW,
            consumed_receipt_ids=iter(COMMIT_LEDGER),
        )
        self.assertEqual(CanvaCanaryState.SAVED_DESIGN_RECEIPT_VALIDATED, one_shot_ledger.state)
        with self.assertRaisesRegex(ValueError, "duplicate transition"):
            evaluate_candidate_conversion_readiness(
                contract(), selection(), eligibility(), create_authority(), evaluated_at=NOW,
                consumed_receipt_ids=("selection-001", "selection-001"),
            )

    def test_current_connector_snapshot_cannot_invent_create_rollback(self) -> None:
        path = (
            Path(__file__).resolve().parents[1]
            / "governance"
            / "sovara_canva_two_layer_canary_contract_v1.json"
        )
        loaded = load_canva_invariant_contract(path)
        chosen = selection(
            invariant_id=loaded.invariant_id,
            connector_schema_sha256=loaded.connector_schema_sha256,
            candidate_set_id=loaded.candidate_set_id,
            candidate_roster_sha256=loaded.candidate_roster_sha256,
        )
        evidence = eligibility(
            candidate_set_id=loaded.candidate_set_id,
            candidate_roster_sha256=loaded.candidate_roster_sha256,
        )
        authority = create_authority(
            invariant_id=loaded.invariant_id,
            connector_schema_sha256=loaded.connector_schema_sha256,
        )
        decision = evaluate_candidate_conversion_readiness(
            loaded, chosen, evidence, authority, evaluated_at=NOW
        )
        self.assertEqual(CanvaCanaryState.HOLD_CREATE_ROLLBACK, decision.state)

    def test_package_exports_canva_and_openrouter_union(self) -> None:
        import sovara.creative as creative

        self.assertIs(CanvaEligibilityEvidence, creative.CanvaEligibilityEvidence)
        self.assertIn("source_only_canva_decision", creative.__all__)
        self.assertIn("supports_contract", creative.__all__)

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
