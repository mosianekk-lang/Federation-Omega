from __future__ import annotations

import sys
from pathlib import Path

import pytest

from alpha_omega_v30.capability_market import CapabilityRegistry, CapabilitySpec
from alpha_omega_v30.sandbox_fleet import OperationalSandbox, ReceiptLedger, SandboxPolicy
from federation.idea_system_build_runtime import (
    BuildCandidate,
    CapabilityQualification,
    CapabilityRegistryDiscovery,
    IdeaSystemBuildRuntime,
    PersistentWorkspace,
)


class RepairingGenerator:
    def __init__(self, *, repeat_failure: bool = False) -> None:
        self.repeat_failure = repeat_failure

    def propose(self, plan, current_files, failure_receipt):
        if failure_receipt is None or self.repeat_failure:
            return BuildCandidate(
                candidate_id="first",
                files={
                    "app.py": "raise SystemExit(1)\n",
                    "result.txt": "candidate\n",
                },
                validation_command=(sys.executable, "app.py"),
                export_paths=("result.txt",),
                rationale="initial candidate",
            )
        return BuildCandidate(
            candidate_id="repair",
            files={
                "app.py": "from pathlib import Path\nPath('result.txt').write_text('verified', encoding='utf-8')\n",
                "result.txt": "stale\n",
            },
            validation_command=(sys.executable, "app.py"),
            export_paths=("result.txt",),
            rationale="failure-derived repair",
        )


def make_runtime(tmp_path: Path, *, qualified: bool = True) -> IdeaSystemBuildRuntime:
    registry = CapabilityRegistry(tmp_path / "capability_registry.jsonl")
    record = registry.register(
        CapabilitySpec(
            capability_id="operational-sandbox-fleet",
            version="1.1.0",
            purpose="Disposable process sandbox with receipt ledger and chaos containment",
            interfaces=("execute", "artifact-export", "receipt-ledger", "chaos-test"),
            providers=("github-actions",),
            fitness={"correctness": 1.0, "reliability": 1.0, "cost_efficiency": 0.9},
            proof_refs=("PROOF-P06",),
        )
    )
    quals = (
        CapabilityQualification(
            record["fingerprint"],
            "OPERATIONAL_VERIFIED",
            ("PROOF-P06",),
        ),
    ) if qualified else ()
    discovery = CapabilityRegistryDiscovery(
        registry,
        qualifications=quals,
        aliases={
            "operational-sandbox-fleet": (
                "CODE_SANDBOX",
                "TEST_EVALUATION",
            )
        },
    )
    sandbox = OperationalSandbox(
        SandboxPolicy(
            timeout_seconds=1.0,
            max_output_bytes=2048,
            max_artifact_bytes=100_000,
            allowed_executables=(sys.executable,),
        ),
        ReceiptLedger(tmp_path / "sandbox_ledger.jsonl"),
    )
    return IdeaSystemBuildRuntime(
        discovery,
        PersistentWorkspace(tmp_path / "workspace.jsonl"),
        sandbox,
    )


def test_unqualified_registry_presence_never_becomes_reusable(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path, qualified=False)
    records = runtime.discovery.records()
    assert len(records) == 1
    assert records[0].evidence_state == "CANDIDATE"
    assert not records[0].reusable
    assert runtime.discovery.snapshot()["qualified_reusable_count"] == 0


def test_qualified_registry_capability_is_reused_by_idea_compiler(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    plan = runtime.plan(
        "Build a small API and test it.",
        source_frontier="main@test",
    )
    decisions = {item.requirement: item for item in plan.capability_decisions}
    assert decisions["CODE_SANDBOX"].strategy == "REUSE"
    assert "operational-sandbox-fleet" in decisions["CODE_SANDBOX"].candidate_ids


def test_successful_repair_promotes_persistent_workspace(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    plan = runtime.plan("Build a small API.", source_frontier="main@test")
    receipt = runtime.build(plan, RepairingGenerator(), max_attempts=2)
    assert receipt.final_status == "VERIFIED_BUILD_CANDIDATE"
    assert receipt.promoted_revision is not None
    assert receipt.attempts == 2
    assert receipt.external_effects == 0
    assert not receipt.provider_effect_authorized
    assert runtime.workspace.verify()["valid"]
    assert runtime.workspace.current_files()["result.txt"] == "verified"

    restored = PersistentWorkspace(tmp_path / "workspace.jsonl")
    assert restored.verify()["current_revision"] == receipt.promoted_revision
    assert restored.current_files()["result.txt"] == "verified"
    assert "app.py" in restored.current_files()


def test_failed_candidate_is_not_promoted(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    plan = runtime.plan("Build a small API.", source_frontier="main@test")
    receipt = runtime.build(plan, RepairingGenerator(repeat_failure=True), max_attempts=1)
    assert receipt.final_status == "FAILED"
    assert receipt.promoted_revision is None
    assert runtime.workspace.current_revision() is None


def test_unchanged_retry_is_blocked(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    plan = runtime.plan("Build a small API.", source_frontier="main@test")
    receipt = runtime.build(plan, RepairingGenerator(repeat_failure=True), max_attempts=2)
    assert receipt.final_status == "UNCHANGED_RETRY_BLOCKED"
    assert receipt.attempts == 1
    assert runtime.workspace.current_revision() is None


def test_unsafe_workspace_path_fails_closed() -> None:
    candidate = BuildCandidate(
        candidate_id="bad",
        files={"../escape.py": "print('no')"},
        validation_command=(sys.executable, "escape.py"),
    )
    with pytest.raises(ValueError, match="unsafe workspace path"):
        candidate.normalized_files()


def test_workspace_rejects_nonpassing_promotion(tmp_path: Path) -> None:
    workspace = PersistentWorkspace(tmp_path / "workspace.jsonl")
    candidate = BuildCandidate(
        candidate_id="x",
        files={"a.py": "print('x')"},
        validation_command=(sys.executable, "a.py"),
    )
    revision = workspace.stage(
        plan_digest="PLAN",
        candidate=candidate,
        parent_revision=None,
    )
    with pytest.raises(ValueError, match="only a passing"):
        workspace.promote(
            revision_id=revision,
            sandbox_receipt={"status": "NONZERO_EXIT"},
        )


def test_consequential_idea_still_does_not_grant_provider_effect_authority(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    plan = runtime.plan(
        "Build the release, deploy to production and publish it.",
        source_frontier="main@test",
    )
    assert plan.mission_ir.effect_class == "CONSEQUENTIAL_EFFECT"
    assert plan.mission_ir.owner_approval_required
    receipt = runtime.build(plan, RepairingGenerator(), max_attempts=2)
    assert receipt.final_status == "VERIFIED_BUILD_CANDIDATE"
    assert receipt.external_effects == 0
    assert not receipt.provider_effect_authorized
