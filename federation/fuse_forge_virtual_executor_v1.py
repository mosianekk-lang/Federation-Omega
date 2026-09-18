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

SCHEMA = "FUSE-FORGE-VIRTUAL-EXECUTOR-V1"
VERSION = "1.0.0"
_ALLOWED_BINARIES = {"python", "python3", "git"}
_FORBIDDEN_ENV_MARKERS = ("TOKEN", "SECRET", "PASSWORD", "PRIVATE_KEY", "CREDENTIAL")


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

    def run(self, task: VirtualTask) -> VirtualTaskReceipt:
        task.validate()
        cwd = _path(self.root, task.cwd)
        cwd.mkdir(parents=True, exist_ok=True)
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
