from __future__ import annotations

import sys
from pathlib import Path

import pytest

from alpha_omega_v30.capability_market import CapabilityRegistry, CapabilitySpec
from alpha_omega_v30.chaos_factory import ChaosCase, ChaosFactory
from alpha_omega_v30.prove_p06_p08 import build_proof
from alpha_omega_v30.sandbox_fleet import OperationalSandbox, ReceiptLedger, SandboxPolicy, SandboxTask


def sandbox(tmp_path: Path, **overrides) -> OperationalSandbox:
    values = {
        "timeout_seconds": 0.2,
        "max_output_bytes": 256,
        "max_artifact_bytes": 10_000,
        "allowed_executables": (sys.executable,),
    }
    values.update(overrides)
    return OperationalSandbox(SandboxPolicy(**values), ReceiptLedger(tmp_path / "ledger.jsonl"))


def test_sandbox_executes_reads_back_persists_and_rolls_back(tmp_path: Path) -> None:
    result = sandbox(tmp_path).run(
        SandboxTask(
            task_id="healthy",
            command=(
                sys.executable,
                "-c",
                "from pathlib import Path; Path('out.txt').write_text('verified', encoding='utf-8')",
            ),
            export_paths=("out.txt",),
        )
    )
    assert result["status"] == "PASS"
    assert result["artifacts"]["out.txt"]["text"] == "verified"
    assert result["execution_verified"]
    assert result["readback_verified"]
    assert result["health_verified"]
    assert result["persistence_verified"]
    assert result["rollback_verified"]


def test_sandbox_rejects_path_escape_and_executable_escape(tmp_path: Path) -> None:
    fleet = sandbox(tmp_path)
    with pytest.raises(ValueError):
        fleet.run(
            SandboxTask(
                task_id="escape",
                command=(sys.executable, "-c", "print('no')"),
                export_paths=("../secret",),
            )
        )
    with pytest.raises(PermissionError):
        fleet.run(SandboxTask(task_id="binary", command=("/bin/echo", "no")))


def test_sandbox_contains_timeout_and_output_limit(tmp_path: Path) -> None:
    fleet = sandbox(tmp_path)
    timed = fleet.run(
        SandboxTask(task_id="timeout", command=(sys.executable, "-c", "import time; time.sleep(1)"))
    )
    noisy = fleet.run(
        SandboxTask(task_id="noisy", command=(sys.executable, "-c", "print('x' * 1000)"))
    )
    assert timed["status"] == "TIMEOUT"
    assert noisy["status"] == "OUTPUT_LIMIT"
    assert timed["rollback_verified"] and noisy["rollback_verified"]


def test_capability_registry_fitness_selection_and_lineage(tmp_path: Path) -> None:
    registry = CapabilityRegistry(tmp_path / "registry.jsonl")
    first = CapabilitySpec(
        capability_id="sandbox",
        version="1.0.0",
        purpose="base",
        interfaces=("execute",),
        providers=("github-actions",),
        fitness={"correctness": 0.9, "reliability": 0.9, "cost_efficiency": 0.8},
    )
    first_record = registry.register(first)
    second = CapabilitySpec(
        capability_id="sandbox",
        version="1.1.0",
        purpose="evolved",
        interfaces=("execute", "chaos-test"),
        providers=("github-actions",),
        fitness={"correctness": 1.0, "reliability": 1.0, "cost_efficiency": 0.8},
        parent_fingerprint=first_record["fingerprint"],
    )
    second_record = registry.register(second)
    selected = registry.resolve(("execute", "chaos-test"), "github-actions")
    assert selected is not None
    assert selected["fingerprint"] == second_record["fingerprint"]
    assert registry.lineage(second_record["fingerprint"]) == [
        second_record["fingerprint"],
        first_record["fingerprint"],
    ]
    assert registry.verify()["valid"]


def test_capability_release_is_immutable(tmp_path: Path) -> None:
    registry = CapabilityRegistry(tmp_path / "registry.jsonl")
    registry.register(
        CapabilitySpec(
            capability_id="x",
            version="1.0.0",
            purpose="first",
            interfaces=("a",),
            providers=("github-actions",),
        )
    )
    with pytest.raises(ValueError):
        registry.register(
            CapabilitySpec(
                capability_id="x",
                version="1.0.0",
                purpose="mutated",
                interfaces=("a",),
                providers=("github-actions",),
            )
        )


def test_chaos_factory_requires_complete_containment(tmp_path: Path) -> None:
    fleet = sandbox(tmp_path)
    report = ChaosFactory(fleet).run(
        [
            ChaosCase(
                name="exit",
                task=SandboxTask(task_id="exit", command=(sys.executable, "-c", "import sys; sys.exit(3)")),
                expected_status="NONZERO_EXIT",
            )
        ]
    )
    assert report["valid"]
    assert report["recovery_score"] == 1.0


def test_provider_proof_runner_writes_complete_receipt(tmp_path: Path) -> None:
    receipt = build_proof(tmp_path / "proof")
    assert receipt["phases"]["P06"]["status"] == "OPERATIONAL_VERIFIED_GITHUB_ACTIONS"
    assert receipt["phases"]["P07"]["registry"]["valid"]
    assert receipt["phases"]["P08"]["chaos"]["valid"]
    assert (tmp_path / "proof" / "p06_p08_receipt.json").is_file()
    assert (tmp_path / "proof" / "sandbox_ledger.jsonl").is_file()
    assert (tmp_path / "proof" / "capability_registry.jsonl").is_file()
    assert (tmp_path / "proof" / "chaos_report.json").is_file()
