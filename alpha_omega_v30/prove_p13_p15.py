from __future__ import annotations

import argparse
import json
from pathlib import Path

from .cross_system_reconciliation import CrossSystemReconciler, SystemObservation
from .succession import InstitutionalSuccessionPlanner, PhaseStatus, SuccessionContract


def _phase(
    phase_id: str,
    status: str,
    evidence: str,
    provider: str = "github-actions",
    operational: bool = True,
    blockers: tuple[str, ...] = (),
) -> PhaseStatus:
    return PhaseStatus(phase_id, status, (evidence,), provider, operational, blockers)


def build_proof(workspace: Path) -> dict:
    workspace.mkdir(parents=True, exist_ok=True)
    checkpoint = json.loads(
        (Path(__file__).parent / "checkpoint_20260803.json").read_text(encoding="utf-8")
    )

    reconciler = CrossSystemReconciler(workspace / "cross_system_ledger.jsonl")
    state = {
        "release": "v3-reference",
        "health": "verified",
        "proof_digest": checkpoint["verified_releases"][-1]["artifact_digest"],
    }
    observations = [
        SystemObservation(
            system="github-actions",
            entity_id="alpha-omega-v3-reference",
            intended=state,
            declared=state,
            observed=state,
            proven=state,
            outcome=state,
            evidence_ref="artifact:8855371809",
            observed_at="2026-08-03T12:12:21Z",
        ),
        SystemObservation(
            system="checkpoint-registry",
            entity_id="alpha-omega-v3-reference",
            intended=state,
            declared=state,
            observed=state,
            proven=state,
            outcome=state,
            evidence_ref="checkpoint:AO-V30-20260803-VERIFIED",
            observed_at="2026-08-03T12:12:21Z",
        ),
    ]
    reconciled = reconciler.reconcile(
        observations,
        now="2026-08-03T12:15:00Z",
        max_age_seconds=3600,
    )
    if not reconciled["valid"] or not reconciled["persistence_verified"]:
        raise SystemExit("P13 reference reconciliation proof failed")

    conflict_state = {**state, "health": "degraded"}
    conflict = reconciler.reconcile(
        [
            observations[0],
            SystemObservation(
                system="conflict-fixture",
                entity_id="alpha-omega-v3-reference",
                intended=state,
                declared=conflict_state,
                observed=conflict_state,
                proven=conflict_state,
                outcome=conflict_state,
                evidence_ref="fixture:conflict",
                observed_at="2026-08-03T12:14:00Z",
            ),
        ],
        now="2026-08-03T12:15:00Z",
        max_age_seconds=3600,
    )
    if conflict["valid"] or not conflict["cross_system_gaps"]:
        raise SystemExit("P13 conflict detection proof failed")

    releases = checkpoint["verified_releases"]
    phases = [
        _phase("P01", "OPERATIONAL_VERIFIED_GITHUB_ACTIONS", str(releases[0]["artifact_id"])),
        _phase("P02", "OPERATIONAL_VERIFIED_GITHUB_ACTIONS", str(releases[0]["artifact_id"])),
        _phase("P03", "OPERATIONAL_VERIFIED_GITHUB_ACTIONS", str(releases[0]["artifact_id"])),
        _phase("P04", "OPERATIONAL_VERIFIED_GITHUB_ACTIONS", str(releases[0]["artifact_id"])),
        _phase("P05", "OPERATIONAL_VERIFIED_GITHUB_ACTIONS", str(releases[0]["artifact_id"])),
        _phase("P06", "OPERATIONAL_VERIFIED_GITHUB_ACTIONS", str(releases[1]["artifact_id"])),
        _phase("P07", "OPERATIONAL_VERIFIED_GITHUB_ACTIONS", str(releases[1]["artifact_id"])),
        _phase("P08", "OPERATIONAL_VERIFIED_GITHUB_ACTIONS", str(releases[1]["artifact_id"])),
        _phase(
            "P09",
            "REFERENCE_PROVIDER_VERIFIED",
            str(releases[2]["artifact_id"]),
            blockers=("CLOUD_RUN_PROVIDER_AUTHORITY",),
        ),
        _phase(
            "P10",
            "EXPERIMENT_ENGINE_VERIFIED_MARKET_PROOF_REQUIRED",
            str(releases[2]["artifact_id"]),
            blockers=("EXTERNAL_MARKET_PROOF",),
        ),
        _phase("P11", "OPERATIONAL_VERIFIED_GITHUB_ACTIONS", str(releases[0]["artifact_id"])),
        _phase("P12", "OPERATIONAL_VERIFIED_GITHUB_ACTIONS", str(releases[0]["artifact_id"])),
        _phase(
            "P13",
            "REFERENCE_RECONCILIATION_VERIFIED_PROVIDER_WRITEBACK_REQUIRED",
            reconciled["ledger_entry"],
            provider="github-actions-reference",
            operational=False,
            blockers=("LIVE_CROSS_SYSTEM_PROVIDER_WRITEBACK",),
        ),
        _phase("P14", "SYMBOLIC_CORE_VERIFIED", str(releases[2]["artifact_id"])),
    ]

    contract = SuccessionContract(
        source_commit="77c7af304886d2b994f1783d73161d8b5bb702e4",
        programme_id=checkpoint["programme_id"],
        owner="Kim Kagiso Mosiane",
        recovery_runbook="Restore the last verified merge commit and its proof artifact, then replay provider receipts in dependency order.",
        rollback_runbook="Revert the candidate provider state to the stored snapshot; verify exact state readback and hash-chain continuity.",
        authority_model="Owner-reserved authority for consequential external releases, financial commitments, credentials and contracts.",
        proof_index=tuple(
            f"artifact:{item['artifact_id']}:{item['artifact_digest']}" for item in releases
        ),
    )
    provider_authority = {
        "github": "FRESH_VERIFIED",
        "google_drive_read": "FRESH_VERIFIED",
        "google_drive_write": "UNVERIFIED",
        "cloud_run": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
        "external_market": "MARKET_PROOF_REQUIRED",
    }
    planner = InstitutionalSuccessionPlanner()
    succession = planner.evaluate(phases, contract, provider_authority)
    persistence = planner.persist(succession, workspace / "succession_bundle.json")
    if succession["maturity_status"] != "READINESS_VERIFIED_INSTITUTIONAL_COMPLETION_BLOCKED":
        raise SystemExit("P15 maturity boundary failed")
    if not persistence["readback_verified"]:
        raise SystemExit("P15 succession readback failed")

    required_blockers = {
        "P09:CLOUD_RUN_PROVIDER_AUTHORITY",
        "P10:EXTERNAL_MARKET_PROOF",
        "P13:LIVE_CROSS_SYSTEM_PROVIDER_WRITEBACK",
        "PROVIDER:cloud_run:PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
        "PROVIDER:external_market:MARKET_PROOF_REQUIRED",
        "PROVIDER:google_drive_write:UNVERIFIED",
    }
    if not required_blockers.issubset(set(succession["blockers"])):
        raise SystemExit("P15 blocker register is incomplete")

    receipt = {
        "programme_id": checkpoint["programme_id"],
        "checkpoint_id": checkpoint["checkpoint_id"],
        "phases": {
            "P13": {
                "status": "REFERENCE_RECONCILIATION_VERIFIED_PROVIDER_WRITEBACK_REQUIRED",
                "reconciliation": reconciled,
                "conflict_detection": {
                    "valid": not conflict["valid"],
                    "cross_system_gaps": conflict["cross_system_gaps"],
                    "ledger_entry": conflict["ledger_entry"],
                },
            },
            "P15": {
                "status": succession["maturity_status"],
                "succession": succession,
                "persistence": persistence,
            },
        },
        "truth_boundary": checkpoint["truth_boundary"],
    }
    (workspace / "p13_p15_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8"
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path("p13_p15_workspace"))
    args = parser.parse_args()
    print(json.dumps(build_proof(args.workspace), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
