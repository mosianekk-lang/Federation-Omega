from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from .core import (
    AdmissionReport,
    ProofManifest,
    ProofPolicy,
    ProofRunner,
    RiskTier,
    RunnerError,
    TestExecutionResult,
    proof_key_for_test,
    sha256_bytes,
    sha256_json,
)


@dataclass(frozen=True)
class HermeticFallbackExecution:
    result: TestExecutionResult
    stdout: bytes
    stderr: bytes
    head_sha: str
    clean_checkout_verified: bool


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )


def _is_git_checkout(repo_root: Path) -> bool:
    probe = _git(repo_root, "rev-parse", "--is-inside-work-tree")
    return probe.returncode == 0 and probe.stdout.strip() == b"true"


def _argv(spec) -> list[str]:
    if spec.kind == "unittest_glob":
        return [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            spec.target,
            "-v",
        ]
    if spec.kind == "unittest_module":
        return [sys.executable, "-m", "unittest", spec.target, "-v"]
    if spec.kind == "compileall":
        return [sys.executable, "-m", "compileall", "-q", spec.target]
    raise RunnerError(f"unsupported hermetic test kind: {spec.kind}")


def run_hermetic_r5_fallback(
    *,
    policy: ProofPolicy,
    manifest: ProofManifest,
    repo_root: str | Path,
) -> HermeticFallbackExecution | None:
    """Run the R5 full-federation fallback from a pristine exact-head worktree.

    Returns None when the fallback is not selected or the supplied root is not a
    Git checkout (the latter keeps small in-memory/unit harnesses compatible).
    In a real Git checkout, failure to materialize the exact manifest head is a
    fail-closed RunnerError.
    """

    selected_ids = {item.test_id for item in manifest.selected_tests}
    if policy.fallback_test_id not in selected_ids:
        return None
    if manifest.impact.risk < RiskTier.R5_RELEASE:
        return None

    root = Path(repo_root).resolve()
    if not _is_git_checkout(root):
        return None

    spec = policy.tests[policy.fallback_test_id]
    if spec.hard_always_run:
        raise RunnerError("R5_HERMETIC_FALLBACK_MUST_NOT_BE_HARD_CACHE_BYPASS")

    commit_probe = _git(root, "cat-file", "-e", f"{manifest.head_sha}^{{commit}}")
    if commit_probe.returncode != 0:
        raise RunnerError("R5_HERMETIC_HEAD_UNAVAILABLE")

    runtime_identity = ProofRunner(policy=policy, repo_root=root).runtime_identity()
    original_key = proof_key_for_test(
        repo_root=root,
        manifest=manifest,
        policy=policy,
        spec=spec,
        runtime_identity=runtime_identity,
    )

    temp_root = Path(tempfile.mkdtemp(prefix="proofos-r5-hermetic-"))
    checkout = temp_root / "checkout"
    added = False
    try:
        add = _git(
            root,
            "worktree",
            "add",
            "--detach",
            "--force",
            str(checkout),
            manifest.head_sha,
        )
        if add.returncode != 0:
            raise RunnerError(
                "R5_HERMETIC_WORKTREE_ADD_FAILED:"
                + sha256_bytes((add.stdout or b"") + (add.stderr or b""))
            )
        added = True

        clean_head = _git(checkout, "rev-parse", "HEAD")
        if clean_head.returncode != 0 or clean_head.stdout.decode().strip() != manifest.head_sha:
            raise RunnerError("R5_HERMETIC_HEAD_MISMATCH")

        clean_key = proof_key_for_test(
            repo_root=checkout,
            manifest=manifest,
            policy=policy,
            spec=spec,
            runtime_identity=runtime_identity,
        )
        if clean_key != original_key:
            raise RunnerError("R5_HERMETIC_PROOF_KEY_DRIFT")

        start = time.monotonic()
        try:
            process = subprocess.run(
                _argv(spec),
                cwd=checkout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=spec.timeout_seconds,
                check=False,
                env={
                    **os.environ,
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "GIT_TERMINAL_PROMPT": "0",
                    "PROOFOS_HERMETIC_R5": "1",
                },
            )
            stdout = process.stdout or b""
            stderr = process.stderr or b""
            result = TestExecutionResult(
                spec.test_id,
                "PASS" if process.returncode == 0 else "FAIL",
                process.returncode,
                time.monotonic() - start,
                original_key,
                sha256_bytes(stdout),
                sha256_bytes(stderr),
                spec.failure_class,
                spec.block_scope,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or b""
            stderr = exc.stderr or b""
            result = TestExecutionResult(
                spec.test_id,
                "FAIL_TIMEOUT",
                124,
                time.monotonic() - start,
                original_key,
                sha256_bytes(stdout),
                sha256_bytes(stderr),
                spec.failure_class,
                spec.block_scope,
            )
        return HermeticFallbackExecution(
            result=result,
            stdout=stdout,
            stderr=stderr,
            head_sha=manifest.head_sha,
            clean_checkout_verified=True,
        )
    finally:
        if added:
            _git(root, "worktree", "remove", "--force", str(checkout))
            _git(root, "worktree", "prune")
        shutil.rmtree(temp_root, ignore_errors=True)


def enforce_hermetic_fallback(
    report: AdmissionReport,
    execution: HermeticFallbackExecution | None,
    *,
    fallback_test_id: str,
) -> AdmissionReport:
    """Make the clean exact-head R5 result authoritative in the admission report."""

    if execution is None:
        return report
    replacement = execution.result
    results = tuple(
        replacement if item.test_id == fallback_test_id else item
        for item in report.results
    )
    if not any(item.test_id == fallback_test_id for item in results):
        raise RunnerError("R5_HERMETIC_FALLBACK_RESULT_MISSING_FROM_REPORT")

    failure_label = f"{fallback_test_id}:{replacement.failure_class}"
    blocking = {
        item for item in report.blocking_failures if not item.startswith(f"{fallback_test_id}:")
    }
    scoped = {
        item for item in report.scoped_failures if not item.startswith(f"{fallback_test_id}:")
    }
    if not (replacement.status.startswith("PASS") or replacement.status.startswith("SKIPPED")):
        blocking.add(failure_label)
        if replacement.block_scope != "GLOBAL":
            scoped.add(failure_label)

    status = "PASS" if not blocking else "FAIL"
    payload = {
        "manifest_sha256": report.manifest_sha256,
        "results": [item.to_dict() for item in results],
        "blocking_failures": sorted(blocking),
        "scoped_failures": sorted(scoped),
        "status": status,
    }
    return AdmissionReport(
        report.manifest_sha256,
        results,
        tuple(sorted(blocking)),
        tuple(sorted(scoped)),
        status,
        sha256_json(payload),
    )


__all__ = [
    "HermeticFallbackExecution",
    "enforce_hermetic_fallback",
    "run_hermetic_r5_fallback",
]
