from __future__ import annotations

from pathlib import Path

from alpha_omega_v30.cross_system_reconciliation import CrossSystemReconciler, SystemObservation
from alpha_omega_v30.prove_p13_p15 import build_proof
from alpha_omega_v30.succession import InstitutionalSuccessionPlanner, PhaseStatus, SuccessionContract


def observation(system: str, state: dict, *, evidence: str = "E1") -> SystemObservation:
    return SystemObservation(
        system=system,
        entity_id="entity-1",
        intended=state,
        declared=state,
        observed=state,
        proven=state,
        outcome=state,
        evidence_ref=evidence,
        observed_at="2026-08-03T12:00:00Z",
    )


def test_cross_system_reconciler_accepts_matching_fresh_truth(tmp_path: Path) -> None:
    state = {"version": "1", "healthy": True}
    result = CrossSystemReconciler(tmp_path / "ledger.jsonl").reconcile(
        [observation("github", state), observation("registry", state, evidence="E2")],
        now="2026-08-03T12:05:00Z",
        max_age_seconds=600,
    )
    assert result["valid"]
    assert result["local_gap_count"] == 0
    assert result["cross_system_gaps"] == []
    assert result["persistence_verified"]


def test_cross_system_reconciler_detects_conflict_and_staleness(tmp_path: Path) -> None:
    first = observation("github", {"version": "1"})
    second = SystemObservation(
        system="registry",
        entity_id="entity-1",
        intended={"version": "2"},
        declared={"version": "2"},
        observed={"version": "2"},
        proven={"version": "2"},
        outcome={"version": "2"},
        evidence_ref="E2",
        observed_at="2026-08-03T10:00:00Z",
    )
    result = CrossSystemReconciler(tmp_path / "ledger.jsonl").reconcile(
        [first, second],
        now="2026-08-03T12:05:00Z",
        max_age_seconds=600,
    )
    assert result["valid"] is False
    assert result["cross_system_gaps"]
    assert any(item["gaps"]["stale"] for item in result["observations"])


def test_succession_planner_preserves_blockers_and_readback(tmp_path: Path) -> None:
    planner = InstitutionalSuccessionPlanner()
    bundle = planner.evaluate(
        [
            PhaseStatus("P01", "VERIFIED", ("A1",), "github", True),
            PhaseStatus("P02", "BLOCKED", ("A2",), "github", False, ("OWNER_AUTHORITY",)),
        ],
        SuccessionContract(
            source_commit="abc",
            programme_id="programme",
            owner="owner",
            recovery_runbook="recover",
            rollback_runbook="rollback",
            authority_model="owner reserved",
            proof_index=("A1", "A2"),
        ),
        {"github": "FRESH_VERIFIED", "cloud": "UNVERIFIED"},
    )
    assert bundle["maturity_status"] == "READINESS_VERIFIED_INSTITUTIONAL_COMPLETION_BLOCKED"
    assert "P02:OWNER_AUTHORITY" in bundle["blockers"]
    assert "PROVIDER:cloud:UNVERIFIED" in bundle["blockers"]
    persisted = planner.persist(bundle, tmp_path / "succession.json")
    assert persisted["readback_verified"]


def test_provider_proof_runner_records_truthful_completion_boundary(tmp_path: Path) -> None:
    receipt = build_proof(tmp_path / "proof")
    p13 = receipt["phases"]["P13"]
    p15 = receipt["phases"]["P15"]
    assert p13["status"] == "REFERENCE_RECONCILIATION_VERIFIED_PROVIDER_WRITEBACK_REQUIRED"
    assert p13["reconciliation"]["valid"]
    assert p13["conflict_detection"]["valid"]
    assert p15["status"] == "READINESS_VERIFIED_INSTITUTIONAL_COMPLETION_BLOCKED"
    assert p15["persistence"]["readback_verified"]
    blockers = set(p15["succession"]["blockers"])
    assert "P09:CLOUD_RUN_PROVIDER_AUTHORITY" in blockers
    assert "P10:EXTERNAL_MARKET_PROOF" in blockers
    assert "P13:LIVE_CROSS_SYSTEM_PROVIDER_WRITEBACK" in blockers
    assert (tmp_path / "proof" / "p13_p15_receipt.json").is_file()
    assert (tmp_path / "proof" / "cross_system_ledger.jsonl").is_file()
    assert (tmp_path / "proof" / "succession_bundle.json").is_file()
