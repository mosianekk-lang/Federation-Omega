"""FUSE Forge virtual executor v1.

Provider-neutral, local-first engineering worker used when a physical owner device is
not available. It is deliberately not a Windows/device simulator: physical-device
predicates remain separate proof gates.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import time

from .fuse_forge_git_repository_adapter_v1 import GitMutationReceipt, GitRollbackReceipt, LocalGitRepositoryAdapter
from .fuse_forge_source_protection_v1 import CheckResult, LeaseFence, SourceProposal, SovereignSourceProtection

SCHEMA = "FUSE-FORGE-VIRTUAL-EXECUTOR-V1"
VERSION = "1.0.0"
_ALLOWED_BINARIES = {"python", "python3", "git"}
_FORBIDDEN_ENV_MARKERS = ("TOKEN", "SECRET", "PASSWORD", "PRIVATE_KEY", "CREDENTIAL")
_PROTECTED_MAIN_REF = "refs/heads/main"
_GIT_MAIN_MUTATORS = {"update-ref", "branch", "checkout", "switch", "reset", "merge", "rebase", "commit", "cherry-pick", "push"}


def _digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _path(root: Path, value: str | os.PathLike[str]) -> Path:
    root = root.resolve()
    p = (root / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    if p != root and root not in p.parents:
        raise ValueError("WORKSPACE_ESCAPE")
    return p


@dataclass(frozen=True, slots=True)
class VirtualExecutorProfile:
    executor_id: str
    runtime_class: str
    os_family: str
    capabilities: tuple[str, ...]
    authority_class: str = "A1_INTERNAL"
    effect_ceiling: str = "LOCAL_WORKSPACE"
    physical_device: bool = False
    persistent_host_proven: bool = False

    def validate(self) -> None:
        if not self.executor_id.strip():
            raise ValueError("EXECUTOR_ID_REQUIRED")
        if self.physical_device:
            raise ValueError("VIRTUAL_EXECUTOR_MUST_NOT_CLAIM_PHYSICAL_DEVICE")
        required = {"git", "python", "build", "test", "artifact", "proof"}
        if not required.issubset(set(self.capabilities)):
            raise ValueError("VIRTUAL_EXECUTOR_CORE_CAPABILITY_GAP")


@dataclass(frozen=True, slots=True)
class VirtualTask:
    task_id: str
    argv: tuple[str, ...]
    cwd: str = "."
    timeout_seconds: int = 120
    environment: tuple[tuple[str, str], ...] = ()

    def validate(self) -> None:
        if not self.task_id.strip() or not self.argv:
            raise ValueError("TASK_ID_AND_ARGV_REQUIRED")
        binary = Path(self.argv[0]).name.lower()
        if binary not in _ALLOWED_BINARIES:
            raise PermissionError("VIRTUAL_EXECUTOR_BINARY_NOT_ALLOWED")
        if not (1 <= self.timeout_seconds <= 900):
            raise ValueError("TASK_TIMEOUT_OUT_OF_RANGE")
        for key, _ in self.environment:
            if any(marker in key.upper() for marker in _FORBIDDEN_ENV_MARKERS):
                raise PermissionError("SECRET_BEARING_ENV_NOT_ALLOWED")

    @property
    def task_digest(self) -> str:
        return _digest({"task_id": self.task_id, "argv": self.argv, "cwd": self.cwd, "environment": self.environment})


@dataclass(frozen=True, slots=True)
class VirtualTaskReceipt:
    schema: str
    executor_id: str
    task_id: str
    task_digest: str
    exit_code: int
    stdout_sha256: str
    stderr_sha256: str
    duration_ms: int
    started_at_ns: int
    finished_at_ns: int
    state: str
    physical_device_proof: bool

    @property
    def receipt_digest(self) -> str:
        return _digest(asdict(self))


class VirtualForgeExecutor:
    def __init__(self, workspace_root: str | os.PathLike[str], profile: VirtualExecutorProfile):
        profile.validate()
        self.root = Path(workspace_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.profile = profile

    def _enforce_protected_main_boundary(self, task: VirtualTask, cwd: Path) -> None:
        if Path(task.argv[0]).name.lower() != "git":
            return
        argv=tuple(str(x) for x in task.argv[1:])
        mutating=any(token in _GIT_MAIN_MUTATORS for token in argv)
        if not mutating:
            return
        lowered={token.lower() for token in argv}
        explicit_main=(
            _PROTECTED_MAIN_REF in argv
            or "main" in lowered
            or any(token.endswith(":refs/heads/main") or token.endswith(":main") for token in argv)
        )
        if explicit_main:
            raise PermissionError("PROTECTED_MAIN_MUTATION_REQUIRES_FORGE_ADAPTER")
        effective_cwd=cwd
        if "-C" in argv:
            i=argv.index("-C")
            if i+1 >= len(argv):
                raise ValueError("GIT_C_DIRECTORY_REQUIRED")
            effective_cwd=_path(cwd,argv[i+1])
        if any(token.startswith("--git-dir") for token in argv):
            raise PermissionError("PROTECTED_GIT_DIR_OVERRIDE_REQUIRES_FORGE_ADAPTER")
        probe=subprocess.run(
            ["git","-C",str(effective_cwd),"symbolic-ref","--quiet","--short","HEAD"],
            capture_output=True,text=True,check=False,
            env={"PATH":os.environ.get("PATH",""),"GIT_TERMINAL_PROMPT":"0"},
        )
        if probe.returncode == 0 and probe.stdout.strip() == "main":
            raise PermissionError("PROTECTED_MAIN_MUTATION_REQUIRES_FORGE_ADAPTER")

    def run(self, task: VirtualTask) -> VirtualTaskReceipt:
        task.validate()
        cwd = _path(self.root, task.cwd)
        cwd.mkdir(parents=True, exist_ok=True)
        self._enforce_protected_main_boundary(task, cwd)
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONNOUSERSITE": "1"}
        env.update(dict(task.environment))
        start_ns = time.time_ns()
        proc = subprocess.run(
            list(task.argv), cwd=str(cwd), env=env, capture_output=True, text=False,
            timeout=task.timeout_seconds, check=False,
        )
        finish_ns = time.time_ns()
        return VirtualTaskReceipt(
            schema=SCHEMA,
            executor_id=self.profile.executor_id,
            task_id=task.task_id,
            task_digest=task.task_digest,
            exit_code=proc.returncode,
            stdout_sha256=sha256(proc.stdout).hexdigest(),
            stderr_sha256=sha256(proc.stderr).hexdigest(),
            duration_ms=max(0, (finish_ns - start_ns) // 1_000_000),
            started_at_ns=start_ns,
            finished_at_ns=finish_ns,
            state="SUCCEEDED" if proc.returncode == 0 else "FAILED",
            physical_device_proof=False,
        )

    def git_bare_repository(self, relative_path: str) -> VirtualTaskReceipt:
        target = _path(self.root, relative_path)
        rel = str(target.relative_to(self.root))
        return self.run(VirtualTask(
            task_id="git-bare-init:" + rel,
            argv=("git", "init", "--bare", rel),
            cwd=".",
        ))

    def protected_source_admission(
        self,
        *,
        repository_relative_path: str,
        current_main_sha: str,
        proposal: SourceProposal,
        lease: LeaseFence,
        checks: tuple[CheckResult, ...],
    ) -> tuple[ProtectedSourceAdmissionReceipt, GitMutationReceipt]:
        target=_path(self.root, repository_relative_path)
        guard=SovereignSourceProtection()
        decision=guard.evaluate(
            current_main_sha=current_main_sha,
            proposal=proposal,
            lease=lease,
            checks=checks,
        )
        if not decision.allowed or decision.permit is None:
            raise PermissionError("FORGE_PROTECTED_SOURCE_ADMISSION_HELD")
        adapter=LocalGitRepositoryAdapter(target)
        if adapter.read_main() != current_main_sha:
            raise RuntimeError("FORGE_EXECUTOR_MAIN_READBACK_MISMATCH")
        mutation=adapter.apply_permit(decision.permit)
        receipt=ProtectedSourceAdmissionReceipt(
            schema="FUSE-FORGE-PROTECTED-SOURCE-ADMISSION-RECEIPT-V1",
            executor_id=self.profile.executor_id,
            proposal_id=proposal.proposal_id,
            protection_receipt_sha256=decision.receipt_sha256,
            permit_sha256=decision.permit.permit_sha256,
            git_mutation_receipt_sha256=mutation.receipt_sha256,
            before_sha=mutation.before_sha,
            after_sha=mutation.after_sha,
            state="PROTECTED_LOCAL_GIT_ADMISSION_READBACK_VERIFIED",
            provider_native_protection_proof=False,
            physical_device_proof=False,
            persistent_host_proof=False,
        )
        return receipt,mutation

    def protected_source_rollback(
        self,
        *,
        repository_relative_path: str,
        mutation_receipt: GitMutationReceipt,
    ) -> GitRollbackReceipt:
        target=_path(self.root, repository_relative_path)
        return LocalGitRepositoryAdapter(target).rollback(mutation_receipt)


@dataclass(frozen=True, slots=True)
class ProtectedSourceAdmissionReceipt:
    schema: str
    executor_id: str
    proposal_id: str
    protection_receipt_sha256: str
    permit_sha256: str
    git_mutation_receipt_sha256: str
    before_sha: str
    after_sha: str
    state: str
    provider_native_protection_proof: bool
    physical_device_proof: bool
    persistent_host_proof: bool

    @property
    def receipt_digest(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True, slots=True)
class OptionalityCourtResult:
    github_runtime_required: bool
    local_git_ready: bool
    local_worker_ready: bool
    artifact_proof_ready: bool
    decision: str


def github_optionality_court(*, git_receipt: VirtualTaskReceipt, worker_receipt: VirtualTaskReceipt,
                             artifact_digest: str) -> OptionalityCourtResult:
    local_git = git_receipt.state == "SUCCEEDED" and git_receipt.exit_code == 0
    worker = worker_receipt.state == "SUCCEEDED" and worker_receipt.exit_code == 0
    artifact = len(artifact_digest) == 64 and all(c in "0123456789abcdef" for c in artifact_digest)
    ok = local_git and worker and artifact
    return OptionalityCourtResult(
        github_runtime_required=False,
        local_git_ready=local_git,
        local_worker_ready=worker,
        artifact_proof_ready=artifact,
        decision="GITHUB_RUNTIME_OPTIONAL_LOCAL_VERIFIED" if ok else "HOLD",
    )
