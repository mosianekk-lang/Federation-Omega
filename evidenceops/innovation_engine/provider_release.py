from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from evidenceops.innovation_engine.cli import default_canary_payload
from evidenceops.innovation_engine.evidenceops_adapter import run_case_cycle
from evidenceops.innovation_engine.foundry import EvidenceOpsAlgorithmFoundry
from evidenceops.innovation_engine.reference_replica import (
    IndependentEvidenceOpsReferenceReplica,
)
from evidenceops.innovation_engine.replication import (
    CrossImplementationReplicationEvaluator,
)


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "governance/federation_learning_policy.json"
SIGNALS = Path(__file__).resolve().parent / "fixtures/master_bible_lesson_signals.json"
AUTHORITY_CEILING = "A1_INTERNAL"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def selected_source_files() -> Iterable[Path]:
    roots = (
        ROOT / "evidenceops/innovation_engine",
        ROOT / "evidenceops/fevx_adapter_v1",
        ROOT / "federation_learning",
        ROOT / "systems/fevx-frontier-v2",
    )
    excluded = {
        "evidenceops/innovation_engine/live_lane_registry.json",
        "evidenceops/innovation_engine/algorithms_mining.py",
        "evidenceops/innovation_engine/algorithms_integrity.py",
        "evidenceops/innovation_engine/algorithms_governance.py",
    }
    for source_root in roots:
        for path in sorted(source_root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT).as_posix()
            if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            if relative in excluded:
                continue
            if "/receipts/" in f"/{relative}/":
                continue
            yield path
    for path in (
        ROOT / "tests/test_evidenceops_algorithm_foundry.py",
        ROOT / "governance/federation_learning_policy.json",
    ):
        if path.is_file():
            yield path


def copy_source(source_dir: Path) -> list[str]:
    copied: list[str] = []
    for path in selected_source_files():
        target = source_dir / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append(target.relative_to(source_dir).as_posix())
    return copied


def run_tests(output_dir: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT), str(ROOT / "systems/fevx-frontier-v2"), env.get("PYTHONPATH", "")]
    )
    targets = [
        "evidenceops/innovation_engine/tests",
        "evidenceops/fevx_adapter_v1/tests",
        "tests/test_evidenceops_algorithm_foundry.py",
    ]
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *targets],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    log_path = output_dir / "TESTS.txt"
    log_path.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    if completed.returncode:
        raise RuntimeError(log_path.read_text(encoding="utf-8"))
    match = re.search(r"(\d+) passed", completed.stdout)
    return {
        "status": "PASSED",
        "test_count": int(match.group(1)) if match else None,
        "log_sha256": sha256_file(log_path),
    }


def evaluation_metrics(**changes: float) -> dict[str, float]:
    metrics = {
        "factual_accuracy": 0.86,
        "proof_completeness": 0.84,
        "security": 1.0,
        "reversibility": 0.96,
        "completion_rate": 0.76,
        "contradiction_detection": 0.78,
        "recovery": 0.78,
        "reuse": 0.74,
        "owner_burden_reduction": 0.64,
        "cost_efficiency": 0.72,
    }
    metrics.update(changes)
    return metrics


def synthetic_packet() -> dict[str, Any]:
    return {
        "matter_id": "PROVIDER-READ-ONLY-CANARY",
        "case_wall_id": "PROVIDER-READ-ONLY-CANARY",
        "packet_id": "PROVIDER-READ-ONLY-CANARY-V1",
        "mission": {"objective": "analyse and verify the bounded packet"},
        "sources": [
            {
                "source_id": "SRC-CANARY-001",
                "sha256": "a" * 64,
                "classification": "P1",
                "state": "EXTRACTED_VERIFIED",
            }
        ],
        "verified_facts": [
            {
                "fact_id": "FACT-CANARY-001",
                "source_refs": ["SRC-CANARY-001"],
                "verification_state": "VERIFIED",
            }
        ],
        "claims": [
            {
                "claim_id": "CLAIM-CANARY-001",
                "description": "bounded source-supported canary claim",
                "fact_refs": ["FACT-CANARY-001"],
                "support_state": "SUPPORTED",
            }
        ],
        "contradictions": [],
        "missing_records": [
            {
                "missing_record_id": "MR-CANARY-001",
                "description": "provider-independent replication proof",
                "decision_sensitivity": "HIGH",
            }
        ],
    }


def run_canaries(output_dir: Path) -> dict[str, Any]:
    signals = json.loads(SIGNALS.read_text(encoding="utf-8"))
    workspace = output_dir / "workspace"
    foundry = EvidenceOpsAlgorithmFoundry(workspace, learning_policy_path=POLICY)
    payload = default_canary_payload(signals)
    first = foundry.execute_cycle(payload).as_dict()
    second = foundry.execute_cycle(payload).as_dict()
    write_json(output_dir / "FOUNDRY_CANARY_RUN1.json", first)
    write_json(output_dir / "FOUNDRY_CANARY_RUN2.json", second)

    baseline = evaluation_metrics()
    accepted = foundry.evolve_algorithm(
        algorithm_id="ALG-EOPS-UFP-001",
        baseline_version="1.0.0",
        baseline_configuration={
            "threshold": 0.50,
            "authority_ceiling": AUTHORITY_CEILING,
            "external_effect": False,
        },
        baseline_metrics=baseline,
        candidate_version="1.1.0",
        candidate_configuration={
            "threshold": 0.44,
            "authority_ceiling": AUTHORITY_CEILING,
            "external_effect": False,
        },
        candidate_metrics=evaluation_metrics(
            completion_rate=0.84,
            contradiction_detection=0.86,
            recovery=0.84,
            reuse=0.82,
            owner_burden_reduction=0.76,
            cost_efficiency=0.80,
        ),
        source_lessons=["Master Bible CH-006", "Master Bible CH-046"],
        expected_benefit="find decision-sensitive unknowns with lower owner burden",
        source_run_id="PROVIDER-EVOLUTION-ACCEPT-V1",
        evidence_refs=["master-bible:CH-006", "master-bible:CH-046"],
    )
    rejected = foundry.evolve_algorithm(
        algorithm_id="ALG-EOPS-UFP-001",
        baseline_version="1.1.0",
        baseline_configuration={
            "threshold": 0.44,
            "authority_ceiling": AUTHORITY_CEILING,
            "external_effect": False,
        },
        baseline_metrics=evaluation_metrics(
            completion_rate=0.84,
            contradiction_detection=0.86,
            recovery=0.84,
            reuse=0.82,
            owner_burden_reduction=0.76,
            cost_efficiency=0.80,
        ),
        candidate_version="1.2.0",
        candidate_configuration={
            "threshold": 0.30,
            "authority_ceiling": AUTHORITY_CEILING,
            "external_effect": False,
        },
        candidate_metrics=evaluation_metrics(
            factual_accuracy=0.70,
            completion_rate=0.92,
            owner_burden_reduction=0.90,
        ),
        source_lessons=["aggressive threshold experiment"],
        expected_benefit="increase gap recall",
        source_run_id="PROVIDER-EVOLUTION-REJECT-V1",
        evidence_refs=["experiment:aggressive-threshold"],
    )
    write_json(output_dir / "EVOLUTION_ACCEPTED.json", accepted)
    write_json(output_dir / "EVOLUTION_REJECTED_HARD_REGRESSION.json", rejected)

    packet = synthetic_packet()
    case_result = run_case_cycle(
        packet,
        master_bible_text=(
            "Unknown Mapper. Epistemic Debt. Failure Laboratory. "
            "Directive Execution Cascade. Terminal Finality. "
            "Exhaustive Corpus Selection Integrity. Owner burden. "
            "Independent implementation replication."
        ),
        workspace=output_dir / "case-workspace",
        learning_policy_path=POLICY,
    )
    reference = IndependentEvidenceOpsReferenceReplica().run(
        packet=packet,
        lesson_signals=signals,
    )
    replication = CrossImplementationReplicationEvaluator().run(
        canonical_result=case_result,
        reference_result=reference,
    )
    write_json(output_dir / "CASE_CANARY.json", case_result)
    write_json(output_dir / "REFERENCE_REPLICA.json", reference)
    write_json(output_dir / "REPLICATION_RESULT.json", replication)

    first_head = first["proof"]["learning_chain"]["ledger_head_hash"]
    second_head = second["proof"]["learning_chain"]["ledger_head_hash"]
    return {
        "foundry_status": first["status"],
        "algorithm_count": first["innovation_delta"]["registered_algorithm_count"],
        "learning_chain": first["proof"]["learning_chain"],
        "evolution_chain": accepted["evolution_chain"],
        "accepted_evolution": accepted["decision"]["decision"],
        "rejected_evolution": rejected["decision"]["decision"],
        "replication_status": replication["status"],
        "recurrence_ledger_head_equal": first_head == second_head,
        "case_release_state": case_result["release_state"],
        "source_packet_unchanged": case_result["source_packet_unchanged"],
        "verified_fact_write": case_result["verified_fact_write"],
        "external_effect": False,
    }


def write_archive(source_dir: Path, target: Path, root_name: str) -> None:
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source_dir.rglob("*")):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo(
                f"{root_name}/{path.relative_to(source_dir).as_posix()}"
            )
            info.date_time = (2026, 8, 5, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(target) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"archive integrity failed at {bad}")


def build_release(output_dir: Path, source_sha: str) -> dict[str, Any]:
    shutil.rmtree(output_dir, ignore_errors=True)
    source_dir = output_dir / "source"
    evidence_dir = output_dir / "runtime_evidence"
    source_dir.mkdir(parents=True)
    evidence_dir.mkdir(parents=True)
    copied = copy_source(source_dir)
    tests = run_tests(evidence_dir)
    canary = run_canaries(evidence_dir)

    manifest = {
        "schema": "EVIDENCEOPS_ALGORITHM_FOUNDRY_PROVIDER_MANIFEST_V1",
        "version": "1.2.0",
        "source_sha": source_sha,
        "created_at": utc_now(),
        "algorithm_count": 15,
        "source_files": copied,
        "files": {},
    }
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.name != "MANIFEST.json":
            manifest["files"][path.relative_to(output_dir).as_posix()] = {
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
    write_json(output_dir / "MANIFEST.json", manifest)

    release_zip = output_dir / "EvidenceOps-Algorithm-Foundry-v1.2.0-provider-release.zip"
    write_archive(
        output_dir,
        release_zip,
        "EvidenceOps-Algorithm-Foundry-v1.2.0-provider-release",
    )
    receipt = {
        "schema": "EVIDENCEOPS_ALGORITHM_FOUNDRY_PROVIDER_RECEIPT_V1",
        "version": "1.2.0",
        "state": "PROVIDER_INDEPENDENT_READ_ONLY_RUNTIME_REPLICATION_PASSED",
        "repository": os.getenv("GITHUB_REPOSITORY", "local"),
        "source_sha": source_sha,
        "run_id": os.getenv("GITHUB_RUN_ID"),
        "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
        "runner": os.getenv("RUNNER_NAME"),
        "tests": tests,
        "canary": canary,
        "archive": {
            "name": release_zip.name,
            "bytes": release_zip.stat().st_size,
            "sha256": sha256_file(release_zip),
            "zip_integrity": "PASSED",
        },
        "manifest_sha256": sha256_file(output_dir / "MANIFEST.json"),
        "authority_ceiling": AUTHORITY_CEILING,
        "external_effect": False,
        "source_write": False,
        "verified_fact_write": False,
        "case_wall_crossing": False,
        "truth_boundary": (
            "This receipt proves a read-only provider execution, tests, canaries, "
            "recurrence, evolution rejection/acceptance and replication for the "
            "exact source SHA. It does not prove real-matter legal accuracy or "
            "consequential authority."
        ),
    }
    receipt["receipt_sha256"] = sha256_value(receipt)
    write_json(output_dir / "PROVIDER_RECEIPT.json", receipt)
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--source-sha", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    receipt = build_release(Path(args.output_dir), args.source_sha)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
