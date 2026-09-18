"""FUSE Forge local Git repository adapter v1.

Consumes an effect-free F295 MergePermit and applies it to a local Git repository
using atomic compare-and-swap via git update-ref. It does not use GitHub APIs,
network access, credentials, or provider-native branch controls.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from .fuse_forge_source_protection_v1 import MergePermit, SovereignSourceProtection

SCHEMA="FUSE-FORGE-GIT-REPOSITORY-ADAPTER-V1"
VERSION="1.0.0"
_MAIN_REF="refs/heads/main"


def _digest(value: object) -> str:
    return sha256(json.dumps(value,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class GitMutationReceipt:
    schema: str
    version: str
    repository_fingerprint: str
    ref: str
    permit_sha256: str
    before_sha: str
    requested_sha: str
    after_sha: str
    rollback_target_sha: str
    state: str
    mutation_performed: bool
    network_used: bool
    provider_api_used: bool
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class GitRollbackReceipt:
    schema: str
    version: str
    repository_fingerprint: str
    ref: str
    source_receipt_sha256: str
    before_sha: str
    rollback_sha: str
    after_sha: str
    state: str
    mutation_performed: bool
    receipt_sha256: str


class LocalGitRepositoryAdapter:
    """Permit-gated local Git ref adapter with atomic CAS and exact readback."""

    def __init__(self, repository: str | Path) -> None:
        self.repo=Path(repository).resolve()
        if not self.repo.exists():
            raise ValueError("FORGE_GIT_REPOSITORY_NOT_FOUND")
        probe=self._git("rev-parse","--is-bare-repository",check=False)
        if probe.returncode != 0 or probe.stdout.strip() not in {"true","false"}:
            raise ValueError("FORGE_GIT_REPOSITORY_INVALID")
        self.is_bare=probe.stdout.strip()=="true"
        if self.is_bare:
            git_dir=self._git("rev-parse","--absolute-git-dir").stdout.strip()
            if Path(git_dir).resolve() != self.repo:
                raise ValueError("FORGE_GIT_REPOSITORY_ROOT_MISMATCH")
        else:
            top=self._git("rev-parse","--show-toplevel").stdout.strip()
            if Path(top).resolve() != self.repo:
                raise ValueError("FORGE_GIT_REPOSITORY_ROOT_MISMATCH")

    def _git(self,*args: str,check: bool=True) -> subprocess.CompletedProcess[str]:
        import os
        p=subprocess.run(
            ["git","-C",str(self.repo),*args],
            text=True,capture_output=True,check=False,
            env={"PATH":os.environ.get("PATH",""),"GIT_TERMINAL_PROMPT":"0"},
        )
        if check and p.returncode != 0:
            raise RuntimeError("FORGE_GIT_COMMAND_FAILED:"+_digest({"args":args,"stderr":p.stderr}))
        return p

    @property
    def repository_fingerprint(self) -> str:
        git_dir=self._git("rev-parse","--absolute-git-dir").stdout.strip()
        return _digest({"root":str(self.repo),"git_dir":str(Path(git_dir).resolve()),"bare":self.is_bare})

    def read_main(self) -> str:
        out=self._git("rev-parse",_MAIN_REF).stdout.strip()
        if len(out)!=40:
            raise RuntimeError("FORGE_GIT_MAIN_READBACK_INVALID")
        return out

    def _assert_commit_exists(self, sha: str) -> None:
        p=self._git("cat-file","-e",f"{sha}^{{commit}}",check=False)
        if p.returncode != 0:
            raise ValueError("FORGE_GIT_TARGET_COMMIT_MISSING")

    def apply_permit(self, permit: MergePermit) -> GitMutationReceipt:
        if not isinstance(permit, MergePermit):
            raise PermissionError("FORGE_GIT_PERMIT_REQUIRED")
        if not SovereignSourceProtection.verify_permit(permit):
            raise PermissionError("FORGE_GIT_PERMIT_INVALID")
        if permit.external_effect_authorized:
            raise PermissionError("FORGE_GIT_EXTERNAL_EFFECT_PERMIT_FORBIDDEN")

        before=self.read_main()
        if before != permit.expected_main_sha:
            raise RuntimeError("FORGE_GIT_STALE_MAIN_CAS")
        self._assert_commit_exists(permit.expected_head_sha)

        p=self._git(
            "update-ref",_MAIN_REF,permit.expected_head_sha,permit.expected_main_sha,
            check=False,
        )
        if p.returncode != 0:
            raise RuntimeError("FORGE_GIT_ATOMIC_CAS_REJECTED")
        after=self.read_main()
        if after != permit.expected_head_sha:
            raise RuntimeError("FORGE_GIT_POST_UPDATE_READBACK_MISMATCH")

        body={
            "schema":SCHEMA,"version":VERSION,
            "repository_fingerprint":self.repository_fingerprint,
            "ref":_MAIN_REF,"permit_sha256":permit.permit_sha256,
            "before_sha":before,"requested_sha":permit.expected_head_sha,
            "after_sha":after,"rollback_target_sha":before,
            "state":"LOCAL_GIT_CAS_APPLIED_READBACK_VERIFIED",
            "mutation_performed":True,"network_used":False,"provider_api_used":False,
        }
        return GitMutationReceipt(**body,receipt_sha256=_digest(body))

    def rollback(self, receipt: GitMutationReceipt) -> GitRollbackReceipt:
        body0=asdict(receipt)
        digest=body0.pop("receipt_sha256")
        if digest != _digest(body0):
            raise PermissionError("FORGE_GIT_SOURCE_RECEIPT_TAMPERED")
        if receipt.repository_fingerprint != self.repository_fingerprint:
            raise PermissionError("FORGE_GIT_SOURCE_RECEIPT_REPOSITORY_MISMATCH")
        if receipt.state != "LOCAL_GIT_CAS_APPLIED_READBACK_VERIFIED" or not receipt.mutation_performed:
            raise PermissionError("FORGE_GIT_ROLLBACK_SOURCE_RECEIPT_INVALID")

        before=self.read_main()
        if before != receipt.after_sha:
            raise RuntimeError("FORGE_GIT_ROLLBACK_STALE_CURRENT")
        self._assert_commit_exists(receipt.rollback_target_sha)

        p=self._git(
            "update-ref",_MAIN_REF,receipt.rollback_target_sha,receipt.after_sha,
            check=False,
        )
        if p.returncode != 0:
            raise RuntimeError("FORGE_GIT_ROLLBACK_CAS_REJECTED")
        after=self.read_main()
        if after != receipt.rollback_target_sha:
            raise RuntimeError("FORGE_GIT_ROLLBACK_READBACK_MISMATCH")

        body={
            "schema":"FUSE-FORGE-GIT-ROLLBACK-RECEIPT-V1","version":VERSION,
            "repository_fingerprint":self.repository_fingerprint,"ref":_MAIN_REF,
            "source_receipt_sha256":receipt.receipt_sha256,
            "before_sha":before,"rollback_sha":receipt.rollback_target_sha,
            "after_sha":after,"state":"LOCAL_GIT_ROLLBACK_READBACK_VERIFIED",
            "mutation_performed":True,
        }
        return GitRollbackReceipt(**body,receipt_sha256=_digest(body))
