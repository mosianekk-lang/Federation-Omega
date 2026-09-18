from __future__ import annotations

import json
import unittest
from pathlib import Path

from federation.fuse_forge_source_protection_v1 import (
    CheckResult, LeaseFence, QueueCandidate, SourceProposal, SovereignSourceProtection,
)

MAIN="1"*40
HEAD="2"*40
MERGE="3"*40


def proposal(**overrides):
    data=dict(
        proposal_id="P1",base_sha=MAIN,head_sha=HEAD,author="owner",
        changed_paths=("a.py","tests/test_a.py"),signed_head=True,direct_main_write=False,
    )
    data.update(overrides)
    return SourceProposal(**data)


def lease(**overrides):
    data=dict(lease_id="F1",fencing_token=1,state="ACTIVE",source_head=MAIN)
    data.update(overrides)
    return LeaseFence(**data)


def checks(state="PASS"):
    return tuple(CheckResult(x,state,f"proof:{x}") for x in ("admission","contract","scan"))


class ForgeProtectionTests(unittest.TestCase):
    def setUp(self):
        self.guard=SovereignSourceProtection()

    def test_happy_path_emits_effect_free_permit(self):
        d=self.guard.evaluate(current_main_sha=MAIN,proposal=proposal(),lease=lease(),checks=checks())
        self.assertTrue(d.allowed)
        self.assertEqual("PERMIT_READY",d.state)
        self.assertFalse(d.permit.external_effect_authorized)
        self.assertTrue(self.guard.verify_permit(d.permit))

    def test_direct_main_rejected(self):
        d=self.guard.evaluate(current_main_sha=MAIN,proposal=proposal(direct_main_write=True),lease=lease(),checks=checks())
        self.assertIn("DIRECT_MAIN_WRITE_FORBIDDEN",d.reasons)

    def test_unsigned_head_rejected(self):
        d=self.guard.evaluate(current_main_sha=MAIN,proposal=proposal(signed_head=False),lease=lease(),checks=checks())
        self.assertIn("SIGNED_HEAD_REQUIRED",d.reasons)

    def test_stale_main_rejected(self):
        d=self.guard.evaluate(current_main_sha="4"*40,proposal=proposal(),lease=lease(source_head="4"*40),checks=checks())
        self.assertIn("STALE_MAIN_CAS",d.reasons)

    def test_inactive_fence_rejected(self):
        d=self.guard.evaluate(current_main_sha=MAIN,proposal=proposal(),lease=lease(state="RELEASED"),checks=checks())
        self.assertIn("ACTIVE_FENCE_REQUIRED",d.reasons)

    def test_fence_source_mismatch_rejected(self):
        d=self.guard.evaluate(current_main_sha=MAIN,proposal=proposal(),lease=lease(source_head="4"*40),checks=checks())
        self.assertIn("FENCE_SOURCE_HEAD_MISMATCH",d.reasons)

    def test_missing_check_rejected(self):
        d=self.guard.evaluate(current_main_sha=MAIN,proposal=proposal(),lease=lease(),checks=checks()[:2])
        self.assertIn("MISSING_CHECK:scan",d.reasons)

    def test_failed_check_rejected(self):
        rows=list(checks())
        rows[1]=CheckResult("contract","FAIL","proof:contract")
        d=self.guard.evaluate(current_main_sha=MAIN,proposal=proposal(),lease=lease(),checks=rows)
        self.assertIn("FAILED_CHECK:contract",d.reasons)

    def test_permit_is_deterministic(self):
        a=self.guard.evaluate(current_main_sha=MAIN,proposal=proposal(),lease=lease(),checks=checks())
        b=self.guard.evaluate(current_main_sha=MAIN,proposal=proposal(),lease=lease(),checks=checks())
        self.assertEqual(a.permit.permit_sha256,b.permit.permit_sha256)

    def test_dependency_queue_is_deterministic(self):
        rows=(
            QueueCandidate("A",2,2,()),
            QueueCandidate("B",9,1,("A",)),
            QueueCandidate("C",5,1,()),
        )
        self.assertEqual(("C","A","B"),self.guard.order_queue(rows))

    def test_dependency_cycle_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"CYCLE"):
            self.guard.order_queue((
                QueueCandidate("A",1,1,("B",)),
                QueueCandidate("B",1,2,("A",)),
            ))

    def test_unknown_dependency_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"UNKNOWN"):
            self.guard.order_queue((QueueCandidate("A",1,1,("MISSING",)),))

    def test_merge_commit_readback(self):
        d=self.guard.evaluate(current_main_sha=MAIN,proposal=proposal(),lease=lease(),checks=checks())
        r=self.guard.verify_merge_readback(
            permit=d.permit,before_main_sha=MAIN,after_main_sha=MERGE,
            observed_head_sha=HEAD,after_parent_shas=(MAIN,HEAD),
        )
        self.assertTrue(r.verified)
        self.assertEqual(MAIN,r.rollback_target_sha)

    def test_bad_readback_holds(self):
        d=self.guard.evaluate(current_main_sha=MAIN,proposal=proposal(),lease=lease(),checks=checks())
        r=self.guard.verify_merge_readback(
            permit=d.permit,before_main_sha=MAIN,after_main_sha=MERGE,
            observed_head_sha="4"*40,after_parent_shas=(MAIN,HEAD),
        )
        self.assertFalse(r.verified)

    def test_manifest_binds_provider_neutral_protection(self):
        root=Path(__file__).resolve().parents[1]
        m=json.loads((root/"governance/fuse_forge_convergence_v1.json").read_text())
        p=m["source_protection"]
        self.assertTrue(p["provider_neutral"])
        self.assertFalse(p["github_admin_required"])
        self.assertFalse(p["provider_native_protection_equivalence_claim"])
        self.assertIn("source_protection",m["virtual_executor"]["capabilities"])


if __name__=="__main__":
    unittest.main()
