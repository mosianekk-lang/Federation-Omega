from hashlib import sha256
from pathlib import Path
import json
import subprocess
import tempfile
import unittest

from federation.fuse_forge_virtual_executor_v1 import (
    VirtualExecutorProfile, VirtualForgeExecutor, VirtualTask,
    github_optionality_court,
)
from federation.fuse_forge_source_protection_v1 import CheckResult, LeaseFence, SourceProposal


def profile():
    return VirtualExecutorProfile(
        executor_id="FUSE-VIRTUAL-FORGE-001",
        runtime_class="EPHEMERAL_VIRTUAL_GENERAL_EXECUTOR",
        os_family="PORTABLE_POSIX",
        capabilities=("git","python","build","test","artifact","proof","recovery","source_protection","local_git_cas"),
    )


def _git(repo: Path, *args: str) -> str:
    p=subprocess.run(["git","-C",str(repo),*args],text=True,capture_output=True,check=False)
    if p.returncode != 0:
        raise RuntimeError(f"git failed: {args}: {p.stderr}")
    return p.stdout.strip()


def _protected_bare_repo(root: Path) -> tuple[Path,str,str]:
    work=root/"work"
    work.mkdir()
    subprocess.run(["git","init","-b","main",str(work)],check=True,capture_output=True)
    _git(work,"config","user.name","FUSE Dogfood")
    _git(work,"config","user.email","fuse@example.invalid")
    (work/"value.txt").write_text("A\n")
    _git(work,"add","value.txt")
    _git(work,"commit","-m","A")
    before=_git(work,"rev-parse","refs/heads/main")
    _git(work,"checkout","-b","candidate")
    (work/"value.txt").write_text("B\n")
    _git(work,"add","value.txt")
    _git(work,"commit","-m","B")
    head=_git(work,"rev-parse","HEAD")
    bare=root/"repos"/"protected.git"
    bare.parent.mkdir()
    subprocess.run(["git","clone","--bare",str(work),str(bare)],check=True,capture_output=True)
    return bare,before,head


class VirtualExecutorCourt(unittest.TestCase):
    def test_profile_never_claims_physical_device(self):
        p=profile(); p.validate(); self.assertFalse(p.physical_device); self.assertFalse(p.persistent_host_proven)

    def test_rejects_physical_claim(self):
        with self.assertRaises(ValueError):
            VirtualExecutorProfile("x","virtual","portable",("git","python","build","test","artifact","proof"), physical_device=True).validate()

    def test_rejects_arbitrary_shell(self):
        with self.assertRaises(PermissionError):
            VirtualTask("x",("bash","-lc","echo unsafe")).validate()

    def test_rejects_secret_environment(self):
        with self.assertRaises(PermissionError):
            VirtualTask("x",("python3","-c","print(1)"),environment=(("API_TOKEN","x"),)).validate()

    def test_workspace_escape_fails(self):
        with tempfile.TemporaryDirectory() as d:
            ex=VirtualForgeExecutor(d,profile())
            with self.assertRaises(ValueError):
                ex.run(VirtualTask("x",("python3","-c","print(1)"),cwd="../escape"))

    def test_python_worker_executes(self):
        with tempfile.TemporaryDirectory() as d:
            ex=VirtualForgeExecutor(d,profile())
            r=ex.run(VirtualTask("python-smoke",("python3","-c","print('FUSE_FORGE_OK')")))
            self.assertEqual(r.state,"SUCCEEDED"); self.assertFalse(r.physical_device_proof)
            self.assertEqual(len(r.receipt_digest),64)

    def test_local_bare_git_repo_replaces_remote_host_for_inner_loop(self):
        with tempfile.TemporaryDirectory() as d:
            ex=VirtualForgeExecutor(d,profile())
            r=ex.git_bare_repository("repos/forge.git")
            self.assertEqual(r.state,"SUCCEEDED")
            self.assertTrue((Path(d)/"repos/forge.git/HEAD").exists())

    def test_github_optionality_court(self):
        with tempfile.TemporaryDirectory() as d:
            ex=VirtualForgeExecutor(d,profile())
            g=ex.git_bare_repository("repos/forge.git")
            w=ex.run(VirtualTask("worker",("python3","-c","from hashlib import sha256; print(sha256(b'x').hexdigest())")))
            a=sha256(b"artifact").hexdigest()
            c=github_optionality_court(git_receipt=g,worker_receipt=w,artifact_digest=a)
            self.assertFalse(c.github_runtime_required)
            self.assertEqual(c.decision,"GITHUB_RUNTIME_OPTIONAL_LOCAL_VERIFIED")

    def test_raw_main_update_ref_is_blocked_by_executor(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bare,before,head=_protected_bare_repo(root)
            ex=VirtualForgeExecutor(root,profile())
            with self.assertRaisesRegex(PermissionError,"PROTECTED_MAIN_MUTATION"):
                ex.run(VirtualTask(
                    "raw-main-update",
                    ("git","update-ref","refs/heads/main",head,before),
                    cwd=str(bare.relative_to(root)),
                ))
            self.assertEqual(before,_git(bare,"rev-parse","refs/heads/main"))

    def test_git_c_main_commit_is_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            work=root/"mainrepo"
            work.mkdir()
            subprocess.run(["git","init","-b","main",str(work)],check=True,capture_output=True)
            _git(work,"config","user.name","FUSE Court")
            _git(work,"config","user.email","fuse@example.invalid")
            (work/"value.txt").write_text("A\n")
            _git(work,"add","value.txt")
            ex=VirtualForgeExecutor(root,profile())
            with self.assertRaisesRegex(PermissionError,"PROTECTED_MAIN_MUTATION"):
                ex.run(VirtualTask(
                    "raw-main-commit",
                    ("git","-C","mainrepo","commit","-m","bypass"),
                    cwd=".",
                ))

    def test_git_push_head_to_main_is_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            ex=VirtualForgeExecutor(root,profile())
            with self.assertRaisesRegex(PermissionError,"PROTECTED_MAIN_MUTATION"):
                ex.run(VirtualTask(
                    "raw-main-push",
                    ("git","push","origin","HEAD:main"),
                    cwd=".",
                ))

    def test_protected_source_admission_dogfoods_f295_f296(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bare,before,head=_protected_bare_repo(root)
            ex=VirtualForgeExecutor(root,profile())
            proposal=SourceProposal(
                proposal_id="DOGFOOD-1",base_sha=before,head_sha=head,author="FUSE",
                changed_paths=("value.txt",),signed_head=True,
                signature_evidence_ref="dogfood-signature:verified",
            )
            lease=LeaseFence(lease_id="FDOG",fencing_token=1,state="ACTIVE",source_head=before)
            checks=tuple(CheckResult(x,"PASS",f"dogfood-proof:{x}") for x in ("admission","contract","scan"))
            receipt,mutation=ex.protected_source_admission(
                repository_relative_path=str(bare.relative_to(root)),
                current_main_sha=before,proposal=proposal,lease=lease,checks=checks,
            )
            self.assertEqual("PROTECTED_LOCAL_GIT_ADMISSION_READBACK_VERIFIED",receipt.state)
            self.assertFalse(receipt.provider_native_protection_proof)
            self.assertFalse(receipt.physical_device_proof)
            self.assertFalse(receipt.persistent_host_proof)
            self.assertEqual(head,_git(bare,"rev-parse","refs/heads/main"))
            rollback=ex.protected_source_rollback(
                repository_relative_path=str(bare.relative_to(root)),
                mutation_receipt=mutation,
            )
            self.assertEqual("LOCAL_GIT_ROLLBACK_READBACK_VERIFIED",rollback.state)
            self.assertEqual(before,_git(bare,"rev-parse","refs/heads/main"))

    def test_failed_proof_check_blocks_before_git_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bare,before,head=_protected_bare_repo(root)
            ex=VirtualForgeExecutor(root,profile())
            proposal=SourceProposal(
                proposal_id="DOGFOOD-HELD",base_sha=before,head_sha=head,author="FUSE",
                changed_paths=("value.txt",),signed_head=True,
                signature_evidence_ref="dogfood-signature:verified",
            )
            lease=LeaseFence(lease_id="FDOG",fencing_token=1,state="ACTIVE",source_head=before)
            checks=(
                CheckResult("admission","PASS","proof:a"),
                CheckResult("contract","FAIL","proof:c"),
                CheckResult("scan","PASS","proof:s"),
            )
            with self.assertRaisesRegex(PermissionError,"ADMISSION_HELD"):
                ex.protected_source_admission(
                    repository_relative_path=str(bare.relative_to(root)),
                    current_main_sha=before,proposal=proposal,lease=lease,checks=checks,
                )
            self.assertEqual(before,_git(bare,"rev-parse","refs/heads/main"))

    def test_manifest_requires_protected_admission_by_default(self):
        root=Path(__file__).resolve().parents[1]
        m=json.loads((root/"governance/fuse_forge_convergence_v1.json").read_text())
        route=m["source_admission_route"]
        self.assertEqual("PROTECTED_LOCAL_GIT_CAS",route["default"])
        self.assertEqual("FORBIDDEN",route["generic_git_main_mutation"])
        self.assertEqual("FORBIDDEN",route["raw_git_dir_override_on_mutator"])
        self.assertTrue(route["post_mutation_readback_required"])
        self.assertTrue(route["rollback_required"])
        self.assertFalse(route["provider_native_protection_equivalence_claim"])

    def test_failed_worker_blocks_optionality_promotion(self):
        with tempfile.TemporaryDirectory() as d:
            ex=VirtualForgeExecutor(d,profile())
            g=ex.git_bare_repository("repos/forge.git")
            w=ex.run(VirtualTask("worker",("python3","-c","raise SystemExit(3)")))
            c=github_optionality_court(git_receipt=g,worker_receipt=w,artifact_digest="0"*64)
            self.assertEqual(c.decision,"HOLD")

if __name__ == "__main__": unittest.main()
