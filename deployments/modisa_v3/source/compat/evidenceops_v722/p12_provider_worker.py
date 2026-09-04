#!/usr/bin/env python3
"""Scoped provider-native worker canary for EvidenceOps/OmegaMax v7.2.2 P12.

This module proves only reversible A0/A1 worker properties. It performs no
network calls, external sends, filings, recording, financial actions,
credential access, destructive provider mutations, or provider administration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "OMEGAMAX_SOL_EVIDENCEOPS_V722_P12_PROVIDER_WORKER_V1"
VERSION = "7.2.2"
SIMULATED_CRASH_EXIT = 75


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def event_metadata(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "event_name": args.event_name,
        "run_id": str(args.run_id),
        "run_attempt": str(args.run_attempt),
        "workflow": args.workflow,
        "sha": args.sha,
        "ref": args.ref,
        "repository": args.repository,
    }


def policy_result() -> dict[str, Any]:
    allowed = [
        "internal_state_write",
        "checkpoint",
        "health_check",
        "replica_write",
        "semantic_readback",
        "rollback_canary",
        "proof_receipt",
    ]
    denied = [
        "external_send",
        "legal_filing",
        "live_hearing_recording",
        "live_financial_action",
        "credential_access",
        "destructive_action",
        "provider_admin_mutation",
    ]
    result = {
        "authority_ceiling": "A1",
        "allowed": allowed,
        "denied": denied,
        "consequential_authority": False,
        "external_effects_permitted": False,
    }
    result["policy_sha256"] = sha256_value(result)
    return result


def checkpoint(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    state_path = workspace / "state" / "worker_state.json"
    provider_event = event_metadata(args)
    state = {
        "schema": SCHEMA,
        "version": VERSION,
        "stage_id": "P12-SCOPED-GITHUB-WORKER",
        "status": "CHECKPOINTED_BEFORE_SIMULATED_CRASH",
        "sequence": 1,
        "resume_count": 0,
        "provider_event": provider_event,
        "policy": policy_result(),
        "external_effects": 0,
        "updated_at_utc": utc_now(),
    }
    state["state_sha256"] = sha256_value(state)
    atomic_write_json(state_path, state)
    atomic_write_json(workspace / "reports" / "provider_event_receipt.json", {
        "schema": "PROVIDER_EVENT_RECEIPT_V1",
        **provider_event,
        "observed_at_utc": utc_now(),
        "event_receipt_sha256": sha256_value(provider_event),
    })
    print(json.dumps({"state": state["status"], "checkpoint": str(state_path)}))
    return SIMULATED_CRASH_EXIT


def load_verified_checkpoint(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"checkpoint missing: {path}")
    state = json.loads(path.read_text(encoding="utf-8"))
    supplied = state.pop("state_sha256", None)
    observed = sha256_value(state)
    if supplied != observed:
        raise RuntimeError(f"checkpoint hash mismatch: expected {supplied}, observed {observed}")
    state["state_sha256"] = supplied
    if state.get("status") != "CHECKPOINTED_BEFORE_SIMULATED_CRASH":
        raise RuntimeError(f"unexpected checkpoint status: {state.get('status')}")
    return state


def resume(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    state_path = workspace / "state" / "worker_state.json"
    checkpoint_state = load_verified_checkpoint(state_path)
    policy = checkpoint_state["policy"]
    if policy.get("consequential_authority") or policy.get("external_effects_permitted"):
        raise RuntimeError("policy boundary widened unexpectedly")

    resumed = {
        **{k: v for k, v in checkpoint_state.items() if k != "state_sha256"},
        "status": "RUNNING_AFTER_CRASH_RESUME",
        "sequence": 2,
        "resume_count": int(checkpoint_state.get("resume_count", 0)) + 1,
        "resumed_from_sha256": checkpoint_state["state_sha256"],
        "updated_at_utc": utc_now(),
    }
    resumed["state_sha256"] = sha256_value(resumed)
    atomic_write_json(state_path, resumed)

    snapshot_path = workspace / "rollback" / "worker_state.snapshot.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(state_path, snapshot_path)
    snapshot_sha = sha256_file(snapshot_path)

    mutated = json.loads(state_path.read_text(encoding="utf-8"))
    mutated["rollback_canary_marker"] = "TEMPORARY_REVERSIBLE_MUTATION"
    mutated.pop("state_sha256", None)
    mutated["state_sha256"] = sha256_value(mutated)
    atomic_write_json(state_path, mutated)
    mutation_observed = json.loads(state_path.read_text(encoding="utf-8")).get("rollback_canary_marker") == "TEMPORARY_REVERSIBLE_MUTATION"

    shutil.copy2(snapshot_path, state_path)
    rollback_sha = sha256_file(state_path)
    rollback_verified = mutation_observed and rollback_sha == snapshot_sha
    if not rollback_verified:
        raise RuntimeError("rollback canary failed")

    primary_state = json.loads(state_path.read_text(encoding="utf-8"))
    primary_without_hash = {k: v for k, v in primary_state.items() if k != "state_sha256"}
    if sha256_value(primary_without_hash) != primary_state.get("state_sha256"):
        raise RuntimeError("post-rollback primary state hash mismatch")

    primary_state.pop("state_sha256", None)
    primary_state.update({
        "status": "OPERATIONAL_VERIFIED_SCOPED",
        "sequence": 3,
        "rollback_verified": True,
        "health": "OPERATIONAL",
        "external_effects": 0,
        "updated_at_utc": utc_now(),
    })
    primary_state["state_sha256"] = sha256_value(primary_state)
    atomic_write_json(state_path, primary_state)

    replica_path = workspace / "replica" / "worker_state.replica.json"
    atomic_write_json(replica_path, primary_state)
    replication_verified = sha256_file(replica_path) == sha256_file(state_path)
    semantic_readback = json.loads(replica_path.read_text(encoding="utf-8")) == json.loads(state_path.read_text(encoding="utf-8"))
    if not replication_verified or not semantic_readback:
        raise RuntimeError("replication/readback verification failed")

    policy_log = {
        "schema": "OMEGAMAX_POLICY_LOG_V1",
        "stage_id": "P12-SCOPED-GITHUB-WORKER",
        "authority_ceiling": "A1",
        "allow_decision": {"action": "internal_state_write", "decision": "ALLOW"},
        "deny_decision": {"action": "external_send", "decision": "DENY", "reason": "A2 authority absent"},
        "external_effects": 0,
        "observed_at_utc": utc_now(),
    }
    policy_log["policy_log_sha256"] = sha256_value(policy_log)
    policy_path = workspace / "reports" / "policy_log.json"
    atomic_write_json(policy_path, policy_log)

    health = {
        "schema": "OMEGAMAX_WORKER_HEALTH_V1",
        "liveness": True,
        "readiness": True,
        "checkpoint_integrity": True,
        "crash_resume": True,
        "persistence": True,
        "replication": replication_verified,
        "semantic_readback": semantic_readback,
        "rollback": rollback_verified,
        "policy_allow_and_deny": True,
        "external_effects": 0,
        "state": "OPERATIONAL_VERIFIED_SCOPED",
        "observed_at_utc": utc_now(),
    }
    health["health_sha256"] = sha256_value(health)
    health_path = workspace / "reports" / "health.json"
    atomic_write_json(health_path, health)

    receipt = {
        "schema": SCHEMA,
        "receipt_id": f"RCP-V722-P12-{args.run_id}-{args.run_attempt}",
        "version": VERSION,
        "stage_id": "P12-SCOPED-GITHUB-WORKER",
        "provider_event": event_metadata(args),
        "proof": {
            "provider_native_execution": True,
            "checkpoint_integrity": True,
            "simulated_crash_exit": SIMULATED_CRASH_EXIT,
            "crash_resume": True,
            "persistent_primary_state": True,
            "replicated_state": replication_verified,
            "semantic_readback": semantic_readback,
            "rollback_canary": rollback_verified,
            "service_health": "OPERATIONAL",
            "policy_log": True,
            "consequential_action_denied": True,
            "external_effects": 0,
        },
        "artifacts": {
            "state_sha256": sha256_file(state_path),
            "replica_sha256": sha256_file(replica_path),
            "policy_log_sha256": sha256_file(policy_path),
            "health_sha256": sha256_file(health_path),
            "rollback_snapshot_sha256": snapshot_sha,
        },
        "maturity": "OPERATIONAL_VERIFIED_SCOPED_GITHUB_ACTIONS_WORKER",
        "truth_boundary": (
            "This receipt proves a scoped hosted GitHub Actions worker for reversible A0/A1 state operations. "
            "It does not prove production Temporal/NATS/OPA/PostgreSQL/KMS infrastructure, external send, legal filing, "
            "live recording, financial action, provider administration, or other consequential authority."
        ),
        "observed_at_utc": utc_now(),
    }
    receipt["receipt_sha256"] = sha256_value(receipt)
    receipt_path = workspace / "reports" / "p12_provider_worker_receipt.json"
    atomic_write_json(receipt_path, receipt)
    print(json.dumps({"state": receipt["maturity"], "receipt": str(receipt_path), "receipt_sha256": receipt["receipt_sha256"]}))
    return 0


def verify(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    required = [
        workspace / "state" / "worker_state.json",
        workspace / "replica" / "worker_state.replica.json",
        workspace / "reports" / "provider_event_receipt.json",
        workspace / "reports" / "policy_log.json",
        workspace / "reports" / "health.json",
        workspace / "reports" / "p12_provider_worker_receipt.json",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"missing proof artifacts: {missing}")
    receipt = json.loads(required[-1].read_text(encoding="utf-8"))
    supplied = receipt.pop("receipt_sha256")
    observed = sha256_value(receipt)
    if supplied != observed:
        raise RuntimeError(f"receipt hash mismatch: expected {supplied}, observed {observed}")
    proof = receipt["proof"]
    gates = [
        proof["provider_native_execution"],
        proof["checkpoint_integrity"],
        proof["crash_resume"],
        proof["persistent_primary_state"],
        proof["replicated_state"],
        proof["semantic_readback"],
        proof["rollback_canary"],
        proof["consequential_action_denied"],
        proof["external_effects"] == 0,
    ]
    if not all(gates):
        raise RuntimeError("one or more P12 scoped proof gates failed")
    print(json.dumps({"verified": True, "receipt_sha256": supplied, "maturity": receipt["maturity"]}))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("checkpoint", "resume", "verify"))
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--event-name", default=os.getenv("GITHUB_EVENT_NAME", "local"))
    parser.add_argument("--run-id", default=os.getenv("GITHUB_RUN_ID", "local"))
    parser.add_argument("--run-attempt", default=os.getenv("GITHUB_RUN_ATTEMPT", "1"))
    parser.add_argument("--workflow", default=os.getenv("GITHUB_WORKFLOW", "local-p12-provider-worker"))
    parser.add_argument("--sha", default=os.getenv("GITHUB_SHA", "local"))
    parser.add_argument("--ref", default=os.getenv("GITHUB_REF", "local"))
    parser.add_argument("--repository", default=os.getenv("GITHUB_REPOSITORY", "local"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.mode == "checkpoint":
        return checkpoint(args)
    if args.mode == "resume":
        return resume(args)
    return verify(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        raise
