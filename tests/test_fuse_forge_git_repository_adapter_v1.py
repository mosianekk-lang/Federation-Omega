from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import subprocess
import tempfile
import unittest

from federation.fuse_forge_git_repository_adapter_v1 import LocalGitRepositoryAdapter
from federation.fuse_forge_source_protection_v1 import (
    CheckResult, LeaseFence, SourceProposal, SovereignSourceProtection,
)


def run(repo: Path, *args: str) -> str:
    p=subprocess.run(["git","-C",str(repo),*args],text=True,capture_output=True,check=False)
    if p.returncode != 0:
        raise RuntimeError(f"git failed: {args}: {p.stderr}")
    return p.stdout.strip()


class ForgeGitAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.repo=Path(self.tmp.name)/"repo"
        self.repo.mkdir()
        subprocess.run(["git","init","-b","main",str(self.repo)],check=True,capture_output=True)
        run(self.repo,"config","user.name","FUSE Court")
        run(self.repo,"config","user.email","fuse@example.invalid")
        (self.repo/"value.txt").write_text("A\n")
        run(self.repo,"add","value.txt")
        run(self.repo,"commit","-m","A")
        self.before=run(self.repo,"rev-parse","refs/heads/main")
        run(self.repo,"checkout","-b","candidate")
        (self.repo/"value.txt").write_text("B\n")
        run(self.repo,"add","value.txt")
        run(self.repo,"commit","-m","B")
        self.head=run(self.repo,"rev-parse","HEAD")
        self.guard=SovereignSourceProtection()
        self.adapter=LocalGitRepositoryAdapter(self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def permit(self, *, head: str | None=None):
        proposal=SourceProposal(
            proposal_id="P1",
            base_sha=self.before,
            head_sha=head or self.head,
            author="owner",
            changed_paths=("value.txt",),
            signed_head=True,
            signature_evidence_ref="git-signature:verified",
        )
        lease=LeaseFence(lease_id="F296",fencing_token=296,state="ACTIVE",source_head=self.before)
        checks=tuple(CheckResult(x,"PASS",f"proof:{x}") for x in ("admission","contract","scan"))
        decision=self.guard.evaluate(
            current_main_sha=self.before,proposal=proposal,lease=lease,checks=checks
        )
        self.assertTrue(decision.allowed)
        return decision.permit

    def test_real_git_atomic_cas_and_exact_readback(self):
        receipt=self.adapter.apply_permit(self.permit())
        self.assertTrue(receipt.mutation_performed)
        self.assertFalse(receipt.network_used)
        self.assertFalse(receipt.provider_api_used)
        self.assertEqual(self.before,receipt.before_sha)
        self.assertEqual(self.head,receipt.after_sha)
        self.assertEqual(self.head,run(self.repo,"rev-parse","refs/heads/main"))

    def test_missing_permit_fails_before_mutation(self):
        with self.assertRaisesRegex(PermissionError,"PERMIT_REQUIRED"):
            self.adapter.apply_permit(None)  # type: ignore[arg-type]
        self.assertEqual(self.before,run(self.repo,"rev-parse","refs/heads/main"))

    def test_tampered_permit_rejected_before_mutation(self):
        permit=self.permit()
        tampered=replace(permit,permit_sha256="0"*64)
        with self.assertRaisesRegex(PermissionError,"PERMIT_INVALID"):
            self.adapter.apply_permit(tampered)
        self.assertEqual(self.before,run(self.repo,"rev-parse","refs/heads/main"))

    def test_stale_main_rejected_before_update(self):
        run(self.repo,"update-ref","refs/heads/main",self.head,self.before)
        with self.assertRaisesRegex(RuntimeError,"STALE_MAIN_CAS"):
            self.adapter.apply_permit(self.permit())
        self.assertEqual(self.head,run(self.repo,"rev-parse","refs/heads/main"))

    def test_missing_target_commit_rejected(self):
        permit=self.permit(head="f"*40)
        with self.assertRaisesRegex(ValueError,"TARGET_COMMIT_MISSING"):
            self.adapter.apply_permit(permit)
        self.assertEqual(self.before,run(self.repo,"rev-parse","refs/heads/main"))

    def test_atomic_git_update_ref_rejects_wrong_old_sha(self):
        p=subprocess.run(
            ["git","-C",str(self.repo),"update-ref","refs/heads/main",self.head,"e"*40],
            text=True,capture_output=True,check=False,
        )
        self.assertNotEqual(0,p.returncode)
        self.assertEqual(self.before,run(self.repo,"rev-parse","refs/heads/main"))

    def test_verified_rollback_restores_exact_before_sha(self):
        receipt=self.adapter.apply_permit(self.permit())
        rollback=self.adapter.rollback(receipt)
        self.assertTrue(rollback.mutation_performed)
        self.assertEqual("LOCAL_GIT_ROLLBACK_READBACK_VERIFIED",rollback.state)
        self.assertEqual(self.before,rollback.after_sha)
        self.assertEqual(self.before,run(self.repo,"rev-parse","refs/heads/main"))

    def test_tampered_mutation_receipt_cannot_rollback(self):
        receipt=self.adapter.apply_permit(self.permit())
        bad=replace(receipt,receipt_sha256="0"*64)
        with self.assertRaisesRegex(PermissionError,"RECEIPT_TAMPERED"):
            self.adapter.rollback(bad)
        self.assertEqual(self.head,run(self.repo,"rev-parse","refs/heads/main"))

    def test_stale_rollback_current_rejected(self):
        receipt=self.adapter.apply_permit(self.permit())
        run(self.repo,"update-ref","refs/heads/main",self.before,self.head)
        with self.assertRaisesRegex(RuntimeError,"ROLLBACK_STALE_CURRENT"):
            self.adapter.rollback(receipt)
        self.assertEqual(self.before,run(self.repo,"rev-parse","refs/heads/main"))

    def test_repository_fingerprint_binds_root(self):
        self.assertEqual(64,len(self.adapter.repository_fingerprint))
        self.assertEqual(self.adapter.repository_fingerprint,self.adapter.repository_fingerprint)


if __name__=="__main__":
    unittest.main()
