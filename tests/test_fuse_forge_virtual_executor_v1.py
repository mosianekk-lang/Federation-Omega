from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from federation.fuse_forge_virtual_executor_v1 import (
    VirtualExecutorProfile, VirtualForgeExecutor, VirtualTask,
    github_optionality_court,
)


def profile():
    return VirtualExecutorProfile(
        executor_id="FUSE-VIRTUAL-FORGE-001",
        runtime_class="EPHEMERAL_VIRTUAL_GENERAL_EXECUTOR",
        os_family="PORTABLE_POSIX",
        capabilities=("git","python","build","test","artifact","proof","recovery"),
    )


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

    def test_failed_worker_blocks_optionality_promotion(self):
        with tempfile.TemporaryDirectory() as d:
            ex=VirtualForgeExecutor(d,profile())
            g=ex.git_bare_repository("repos/forge.git")
            w=ex.run(VirtualTask("worker",("python3","-c","raise SystemExit(3)")))
            c=github_optionality_court(git_receipt=g,worker_receipt=w,artifact_digest="0"*64)
            self.assertEqual(c.decision,"HOLD")

if __name__ == "__main__": unittest.main()
