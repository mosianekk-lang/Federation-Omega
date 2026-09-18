"""Bounded Self-Hosting R&D challenger harness v1.

This module is deliberately local-only. It reuses FUSE Virtual Forge, permits a
small Python build/test surface, records deterministic evidence, and never
authorizes provider, production, IAM, network, or source-main effects.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Iterable

from .fuse_forge_virtual_executor_v1 import (
    VirtualExecutorProfile,
    VirtualForgeExecutor,
    VirtualTask,
    VirtualTaskReceipt,
)

SCHEMA = "FUSE-SELF-HOSTING-RD-CHALLENGER-RECEIPT-V1"
VERSION = "1.0.0"
_ALLOWED_STAGES = {"BUILD", "TEST"}
_ALLOWED_MODULES = {"compileall", "unittest"}
_NETWORK_MARKERS = ("http://", "https://", "ssh://", "git@", "ftp://")


def _digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _safe_path(root: Path, value: str) -> Path:
    root = root.resolve()
    path = (root / value).resolve()
    if path != root and root not in path.parents:
        raise ValueError("CHALLENGER_WORKSPACE_ESCAPE")
    return path


@dataclass(frozen=True, slots=True)
class ChallengerTaskSpec:
    stage: str
    task_id: str
    argv: tuple[str, ...]
    cwd: str = "."
    timeout_seconds: int = 180

    def validate(self) -> None:
        if self.stage not in _ALLOWED_STAGES:
            raise ValueError("CHALLENGER_STAGE_NOT_ALLOWED")
        if not self.task_id.strip() or len(self.argv) < 3:
            raise ValueError("CHALLENGER_TASK_INVALID")
        binary = Path(self.argv[0]).name.lower()
        if binary not in {"python", "python3"}:
            raise PermissionError("CHALLENGER_BINARY_NOT_ALLOWED")
        if self.argv[1] != "-m" or self.argv[2] not in _ALLOWED_MODULES:
            raise PermissionError("CHALLENGER_PYTHON_MODULE_NOT_ALLOWED")
        if "-c" in self.argv:
            raise PermissionError("CHALLENGER_INLINE_CODE_FORBIDDEN")
        if not (1 <= self.timeout_seconds <= 900):
            raise ValueError("CHALLENGER_TIMEOUT_OUT_OF_RANGE")
        for token in self.argv:
            lowered = str(token).lower()
            if any(marker in lowered for marker in _NETWORK_MARKERS):
                raise PermissionError("CHALLENGER_NETWORK_REFERENCE_FORBIDDEN")
        if ".." in Path(self.cwd).parts:
            raise ValueError("CHALLENGER_CWD_ESCAPE")


@dataclass(frozen=True, slots=True)
class ArtifactExpectation:
    path: str
    sha256: str

    def validate(self) -> None:
        if not self.path.strip():
            raise ValueError("ARTIFACT_PATH_REQUIRED")
        if len(self.sha256) != 64 or any(c not in "0123456789abcdef" for c in self.sha256.lower()):
            raise ValueError("ARTIFACT_SHA256_REQUIRED")


@dataclass(frozen=True, slots=True)
class ChallengerPlan:
    candidate_id: str
    source_epoch: str
    owner_goal_digest: str
    build_tasks: tuple[ChallengerTaskSpec, ...]
    test_tasks: tuple[ChallengerTaskSpec, ...]
    artifacts: tuple[ArtifactExpectation, ...]
    external_runtime_dependencies: tuple[str, ...] = ()
    rollback_ref: str = ""
    disconnected_required: bool = True

    def validate(self) -> None:
        if not self.candidate_id.strip() or not self.source_epoch.strip():
            raise ValueError("CHALLENGER_ID_AND_SOURCE_EPOCH_REQUIRED")
        if len(self.owner_goal_digest) != 64:
            raise ValueError("OWNER_GOAL_DIGEST_REQUIRED")
        if not self.build_tasks or not self.test_tasks or not self.artifacts:
            raise ValueError("BUILD_TEST_AND_ARTIFACT_EVIDENCE_REQUIRED")
        for task in (*self.build_tasks, *self.test_tasks):
            task.validate()
        if any(task.stage != "BUILD" for task in self.build_tasks):
            raise ValueError("BUILD_STAGE_MISMATCH")
        if any(task.stage != "TEST" for task in self.test_tasks):
            raise ValueError("TEST_STAGE_MISMATCH")
        for artifact in self.artifacts:
            artifact.validate()
        if not self.rollback_ref.strip():
            raise ValueError("ROLLBACK_REF_REQUIRED")
        if not self.disconnected_required:
            raise ValueError("DISCONNECTED_REBUILD_MUST_BE_REQUIRED")

    @property
    def plan_digest(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True, slots=True)
class StableTaskEvidence:
    stage: str
    task_id: str
    task_digest: str
    exit_code: int
    state: str
    stdout_sha256: str
    stderr_sha256: str

    @classmethod
    def from_receipt(cls, stage: str, receipt: VirtualTaskReceipt) -> "StableTaskEvidence":
        return cls(
            stage=stage,
            task_id=receipt.task_id,
            task_digest=receipt.task_digest,
            exit_code=receipt.exit_code,
            state=receipt.state,
            stdout_sha256=receipt.stdout_sha256,
            stderr_sha256=receipt.stderr_sha256,
        )


@dataclass(frozen=True, slots=True)
class ArtifactEvidence:
    path: str
    expected_sha256: str
    observed_sha256: str
    matches: bool


@dataclass(frozen=True, slots=True)
class ChallengerReceipt:
    schema: str
    version: str
    candidate_id: str
    source_epoch: str
    plan_digest: str
    task_evidence: tuple[StableTaskEvidence, ...]
    artifact_evidence: tuple[ArtifactEvidence, ...]
    reproducibility_fingerprint: str
    all_tasks_succeeded: bool
    reproducible_artifacts: bool
    dependency_exit: bool
    disconnected_rebuild: bool
    rollback_ready: bool
    challenger_ready: bool
    provider_effect_authorized: bool
    production_activation_authorized: bool
    physical_device_proof: bool
    persistent_host_proof: bool
    matched_eval_proven: bool
    owner_value_proven: bool
    independent_judge_ack: bool

    @property
    def receipt_digest(self) -> str:
        return _digest(asdict(self))


def default_profile() -> VirtualExecutorProfile:
    return VirtualExecutorProfile(
        executor_id="FUSE-VIRTUAL-FORGE-SELF-HOSTING-RD-001",
        runtime_class="EPHEMERAL_VIRTUAL_GENERAL_EXECUTOR",
        os_family="PORTABLE_POSIX",
        capabilities=("git", "python", "build", "test", "artifact", "proof", "recovery", "source_protection", "local_git_cas"),
        authority_class="A1_INTERNAL",
        effect_ceiling="LOCAL_WORKSPACE",
        physical_device=False,
        persistent_host_proven=False,
    )


def _run_specs(executor: VirtualForgeExecutor, specs: Iterable[ChallengerTaskSpec]) -> list[StableTaskEvidence]:
    out: list[StableTaskEvidence] = []
    for spec in specs:
        receipt = executor.run(VirtualTask(
            task_id=spec.task_id,
            argv=spec.argv,
            cwd=spec.cwd,
            timeout_seconds=spec.timeout_seconds,
        ))
        out.append(StableTaskEvidence.from_receipt(spec.stage, receipt))
    return out


def execute_challenger(
    plan: ChallengerPlan,
    workspace_root: str | os.PathLike[str],
    profile: VirtualExecutorProfile | None = None,
) -> ChallengerReceipt:
    plan.validate()
    root = Path(workspace_root).resolve()
    executor = VirtualForgeExecutor(root, profile or default_profile())
    task_evidence = _run_specs(executor, (*plan.build_tasks, *plan.test_tasks))

    artifacts: list[ArtifactEvidence] = []
    for expected in plan.artifacts:
        path = _safe_path(root, expected.path)
        observed = sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
        artifacts.append(ArtifactEvidence(
            path=expected.path,
            expected_sha256=expected.sha256.lower(),
            observed_sha256=observed,
            matches=observed == expected.sha256.lower(),
        ))

    all_tasks_succeeded = all(x.exit_code == 0 and x.state == "SUCCEEDED" for x in task_evidence)
    reproducible_artifacts = all(x.matches for x in artifacts)
    dependency_exit = not plan.external_runtime_dependencies
    disconnected_rebuild = plan.disconnected_required
    rollback_ready = bool(plan.rollback_ref.strip())

    stable_projection = {
        "plan_digest": plan.plan_digest,
        "tasks": [
            {"stage": x.stage, "task_id": x.task_id, "task_digest": x.task_digest, "exit_code": x.exit_code, "state": x.state}
            for x in task_evidence
        ],
        "artifacts": [asdict(x) for x in artifacts],
        "dependency_exit": dependency_exit,
        "disconnected_rebuild": disconnected_rebuild,
        "rollback_ready": rollback_ready,
    }
    fingerprint = _digest(stable_projection)
    challenger_ready = all_tasks_succeeded and reproducible_artifacts and dependency_exit and disconnected_rebuild and rollback_ready

    return ChallengerReceipt(
        schema=SCHEMA,
        version=VERSION,
        candidate_id=plan.candidate_id,
        source_epoch=plan.source_epoch,
        plan_digest=plan.plan_digest,
        task_evidence=tuple(task_evidence),
        artifact_evidence=tuple(artifacts),
        reproducibility_fingerprint=fingerprint,
        all_tasks_succeeded=all_tasks_succeeded,
        reproducible_artifacts=reproducible_artifacts,
        dependency_exit=dependency_exit,
        disconnected_rebuild=disconnected_rebuild,
        rollback_ready=rollback_ready,
        challenger_ready=challenger_ready,
        provider_effect_authorized=False,
        production_activation_authorized=False,
        physical_device_proof=False,
        persistent_host_proof=False,
        matched_eval_proven=False,
        owner_value_proven=False,
        independent_judge_ack=False,
    )
