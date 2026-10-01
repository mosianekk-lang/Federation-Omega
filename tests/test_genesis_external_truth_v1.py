from __future__ import annotations

import unittest

from fuse_genesis.external_truth import (
    BooleanSchema,ExternalTruthError,ExternalTruthNormalizer,ReconciledTruth,
    StatusContract,TruthReceipt,TruthState,digest,parse_aware_time,require_verified_true
)

EPOCH="a"*64
OTHER="b"*64
NOW="2026-09-23T20:00:00+00:00"

class T(unittest.TestCase):
    def setUp(self): self.n=ExternalTruthNormalizer()

    def receipt(self,state=TruthState.VERIFIED_TRUE,**kw):
        v=dict(
            provider_id="provider-a",operation_id="op-1",subject_id="effect-1",
            source_epoch_digest=EPOCH,observed_at="2026-09-23T19:59:30+00:00",
            truth_state=state,semantic_code="ACTION_READBACK",
            raw_evidence={"applied":state is TruthState.VERIFIED_TRUE},
            transport_ok=True,raw_schema_id="provider-a:v1",
        ); v.update(kw); return self.n.make_receipt(**v)

    def test_01_literal_true(self): self.assertIs(self.n.normalize_boolean(True),TruthState.VERIFIED_TRUE)
    def test_02_literal_false(self): self.assertIs(self.n.normalize_boolean(False),TruthState.VERIFIED_FALSE)
    def test_03_string_false_invalid(self): self.assertIs(self.n.normalize_boolean("false"),TruthState.INVALID)
    def test_04_integer_one_invalid(self): self.assertIs(self.n.normalize_boolean(1),TruthState.INVALID)
    def test_05_explicit_provider_boolean_schema(self):
        s=BooleanSchema(true_values=("Y",),false_values=("N",))
        self.assertIs(self.n.normalize_boolean("Y",schema=s),TruthState.VERIFIED_TRUE)
        self.assertIs(self.n.normalize_boolean("N",schema=s),TruthState.VERIFIED_FALSE)
    def test_06_schema_mapping_is_exact_not_casefolded(self):
        s=BooleanSchema(true_values=("YES",),false_values=("NO",))
        self.assertIs(self.n.normalize_boolean("yes",schema=s),TruthState.INVALID)
    def test_07_status_contract_true(self):
        c=StatusContract(frozenset({"DONE"}),frozenset({"FAILED"}))
        self.assertIs(self.n.normalize_status("DONE",contract=c),TruthState.VERIFIED_TRUE)
    def test_08_status_contract_unknown_value_invalid(self):
        c=StatusContract(frozenset({"DONE"}),frozenset({"FAILED"}))
        self.assertIs(self.n.normalize_status("OK",contract=c),TruthState.INVALID)
    def test_09_transport_failure_is_unknown(self):
        self.assertIs(self.n.normalize_semantic_result(transport_ok=False,semantic={"applied":True}),TruthState.UNKNOWN)
    def test_10_transport_success_without_semantic_field_invalid(self):
        self.assertIs(self.n.normalize_semantic_result(transport_ok=True,semantic={}),TruthState.INVALID)
    def test_11_transport_success_string_false_invalid(self):
        self.assertIs(self.n.normalize_semantic_result(transport_ok=True,semantic={"applied":"false"}),TruthState.INVALID)
    def test_12_semantic_true(self):
        self.assertIs(self.n.normalize_semantic_result(transport_ok=True,semantic={"applied":True}),TruthState.VERIFIED_TRUE)
    def test_13_semantic_false(self):
        self.assertIs(self.n.normalize_semantic_result(transport_ok=True,semantic={"applied":False}),TruthState.VERIFIED_FALSE)
    def test_14_bad_epoch_rejected(self):
        with self.assertRaisesRegex(ExternalTruthError,"SOURCE_EPOCH"):
            self.receipt(source_epoch_digest="bad")
    def test_15_naive_timestamp_rejected(self):
        with self.assertRaisesRegex(ExternalTruthError,"TIMEZONE"):
            self.receipt(observed_at="2026-09-23T19:59:30")
    def test_16_timezone_normalized(self):
        self.assertEqual(parse_aware_time("2026-09-23T21:59:30+02:00").isoformat(),"2026-09-23T19:59:30+00:00")
    def test_17_current_receipt_preserves_truth(self):
        r=self.receipt()
        self.assertIs(self.n.classify_currentness(r,current_source_epoch=EPOCH,now=NOW,max_age_seconds=60),TruthState.VERIFIED_TRUE)
    def test_18_old_receipt_is_stale(self):
        r=self.receipt(observed_at="2026-09-23T19:00:00+00:00")
        self.assertIs(self.n.classify_currentness(r,current_source_epoch=EPOCH,now=NOW,max_age_seconds=60),TruthState.STALE)
    def test_19_old_source_epoch_is_stale(self):
        r=self.receipt(source_epoch_digest=OTHER)
        self.assertIs(self.n.classify_currentness(r,current_source_epoch=EPOCH,now=NOW,max_age_seconds=60),TruthState.STALE)
    def test_20_future_receipt_invalid(self):
        r=self.receipt(observed_at="2026-09-23T20:01:00+00:00")
        self.assertIs(self.n.classify_currentness(r,current_source_epoch=EPOCH,now=NOW,max_age_seconds=60),TruthState.INVALID)
    def test_21_conflicting_fresh_receipts_are_disputed(self):
        a=self.receipt(TruthState.VERIFIED_TRUE,operation_id="op-a")
        b=self.receipt(TruthState.VERIFIED_FALSE,operation_id="op-b")
        x=self.n.reconcile([a,b],subject_id="effect-1",current_source_epoch=EPOCH,now=NOW,max_age_seconds=60)
        self.assertIs(x.state,TruthState.DISPUTED)
    def test_22_last_write_wins_is_not_used(self):
        a=self.receipt(TruthState.VERIFIED_TRUE,operation_id="old",observed_at="2026-09-23T19:59:10+00:00")
        b=self.receipt(TruthState.VERIFIED_FALSE,operation_id="new",observed_at="2026-09-23T19:59:50+00:00")
        x=self.n.reconcile([a,b],subject_id="effect-1",current_source_epoch=EPOCH,now=NOW,max_age_seconds=60)
        self.assertIs(x.state,TruthState.DISPUTED)
    def test_23_same_true_receipts_reconcile_true(self):
        a=self.receipt(operation_id="a"); b=self.receipt(operation_id="b")
        self.assertIs(self.n.reconcile([a,b],subject_id="effect-1",current_source_epoch=EPOCH,now=NOW,max_age_seconds=60).state,TruthState.VERIFIED_TRUE)
    def test_24_unknown_does_not_override_verified_true(self):
        a=self.receipt(TruthState.VERIFIED_TRUE,operation_id="a")
        b=self.receipt(TruthState.UNKNOWN,operation_id="b")
        self.assertIs(self.n.reconcile([a,b],subject_id="effect-1",current_source_epoch=EPOCH,now=NOW,max_age_seconds=60).state,TruthState.VERIFIED_TRUE)
    def test_25_only_stale_receipts_reconcile_stale(self):
        a=self.receipt(observed_at="2026-09-23T18:00:00+00:00")
        self.assertIs(self.n.reconcile([a],subject_id="effect-1",current_source_epoch=EPOCH,now=NOW,max_age_seconds=60).state,TruthState.STALE)
    def test_26_no_receipts_is_unknown(self):
        self.assertIs(self.n.reconcile([],subject_id="effect-1",current_source_epoch=EPOCH,now=NOW,max_age_seconds=60).state,TruthState.UNKNOWN)
    def test_27_stale_conflict_does_not_override_fresh(self):
        fresh=self.receipt(TruthState.VERIFIED_TRUE,operation_id="fresh")
        stale=self.receipt(TruthState.VERIFIED_FALSE,operation_id="stale",observed_at="2026-09-23T18:00:00+00:00")
        self.assertIs(self.n.reconcile([fresh,stale],subject_id="effect-1",current_source_epoch=EPOCH,now=NOW,max_age_seconds=60).state,TruthState.VERIFIED_TRUE)
    def test_28_provider_id_required(self):
        with self.assertRaisesRegex(ExternalTruthError,"PROVIDER_ID"):
            self.receipt(provider_id="")
    def test_29_operation_id_required(self):
        with self.assertRaisesRegex(ExternalTruthError,"OPERATION_ID"):
            self.receipt(operation_id="")
    def test_30_subject_id_required(self):
        with self.assertRaisesRegex(ExternalTruthError,"SUBJECT_ID"):
            self.receipt(subject_id="")
    def test_31_transport_ok_must_be_literal_boolean(self):
        with self.assertRaisesRegex(ExternalTruthError,"TRANSPORT_OK"):
            self.receipt(transport_ok="true")
    def test_32_evidence_hash_is_content_bound(self):
        a=self.receipt(raw_evidence={"x":1}); b=self.receipt(raw_evidence={"x":2},operation_id="b")
        self.assertNotEqual(a.evidence_sha256,b.evidence_sha256)
    def test_33_receipt_digest_is_stable(self):
        a=self.receipt(); b=self.receipt()
        self.assertEqual(a.receipt_sha256,b.receipt_sha256)
    def test_34_receipt_digest_changes_with_semantics(self):
        a=self.receipt(); b=self.receipt(TruthState.VERIFIED_FALSE)
        self.assertNotEqual(a.receipt_sha256,b.receipt_sha256)
    def test_35_require_verified_true(self):
        self.assertTrue(require_verified_true(ReconciledTruth("x",TruthState.VERIFIED_TRUE,(),())))
    def test_36_require_verified_true_rejects_unknown(self):
        with self.assertRaisesRegex(ExternalTruthError,"VERIFIED_TRUE_REQUIRED"):
            require_verified_true(ReconciledTruth("x",TruthState.UNKNOWN,(),()))
    def test_37_max_age_must_be_positive(self):
        with self.assertRaisesRegex(ExternalTruthError,"MAX_AGE"):
            self.n.classify_currentness(self.receipt(),current_source_epoch=EPOCH,now=NOW,max_age_seconds=0)
    def test_38_raw_http_200_cannot_become_true_without_semantics(self):
        self.assertIs(self.n.normalize_semantic_result(transport_ok=True,semantic={"http":200}),TruthState.INVALID)
    def test_39_explicit_string_mapping_is_provider_contract_only(self):
        schema=BooleanSchema(true_values=("true",),false_values=("false",))
        self.assertIs(self.n.normalize_semantic_result(transport_ok=True,semantic={"applied":"false"},boolean_schema=schema),TruthState.VERIFIED_FALSE)
    def test_40_receipt_hash_length(self):
        self.assertEqual(len(self.receipt().receipt_sha256),64)

if __name__=="__main__": unittest.main(verbosity=2)
