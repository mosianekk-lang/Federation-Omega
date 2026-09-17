"""Transactional, cancellation-aware on-demand regression cycles for v3.1."""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from . import bco_prime_baseline_registry_v3_1 as baseline
    from . import bco_prime_drift_harvest_v3_1 as drift
except ImportError:  # pragma: no cover
    import bco_prime_baseline_registry_v3_1 as baseline
    import bco_prime_drift_harvest_v3_1 as drift


SCHEMA = "BCO_PRIME_GOVERNED_CYCLE_V3_1"
VERSION = "3.1.0"
MAX_LEDGER_BYTES = 16 * 1024 * 1024


class CycleContractError(ValueError):
    pass


def _safe_local(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise CycleContractError("path must be a non-empty relative path")
    root = root.resolve()
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise CycleContractError("path traversal rejected")
    return candidate


def _cancelled(cancel_token: Mapping[str, Any], mission_version: int, checkpoint: str) -> bool:
    if not isinstance(cancel_token, Mapping):
        raise CycleContractError("cancel token must be an object")
    token_version = cancel_token.get("mission_version")
    if type(token_version) is not int:
        raise CycleContractError("cancel token mission_version must be an integer")
    return cancel_token.get("cancelled") is True or token_version != mission_version or checkpoint in set(cancel_token.get("cancel_at", []))


def cancelled_receipt(mission_id: str, mission_version: int, checkpoint: str) -> dict[str, Any]:
    result = {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "CANCELLED",
        "mission_id": mission_id,
        "mission_version": mission_version,
        "checkpoint": checkpoint,
        "commitPerformed": False,
        "baselineAdvanceAuthorized": False,
        "sourceMutationAuthorized": False,
        "stablePromotionAuthorized": False,
        "providerEffectAuthorized": False,
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }
    result["receipt_sha256"] = drift.digest(result)
    return result


def _verify_ledger(path: Path) -> tuple[str, int]:
    previous = "GENESIS"
    count = 0
    if not path.exists():
        return previous, count
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_LEDGER_BYTES:
        raise CycleContractError("scoreboard ledger is unsafe")
    with path.open(encoding="utf-8") as handle:
        for count, line in enumerate(handle, 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CycleContractError(f"scoreboard ledger invalid at line {count}") from exc
            if row.get("sequence") != count or row.get("previous_hash") != previous:
                raise CycleContractError("scoreboard ledger chain invalid")
            claimed = row.pop("event_hash", None)
            if claimed != drift.digest(row):
                raise CycleContractError("scoreboard ledger hash invalid")
            previous = str(claimed)
    return previous, count


def _append_scoreboard(path: Path, cycle_id: str, scoreboard: Mapping[str, Any], proof_refs: Sequence[str]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        previous, count = _verify_ledger(path)
        row = {
            "schema": "BCO_PRIME_SCOREBOARD_EVENT_V3_1",
            "sequence": count + 1,
            "cycle_id": cycle_id,
            "scoreboard_sha256": scoreboard.get("receipt_sha256"),
            "scoreboard_state": scoreboard.get("state"),
            "proof_refs": sorted(set(str(item) for item in proof_refs)),
            "previous_hash": previous,
        }
        row["event_hash"] = drift.digest(row)
        encoded = (baseline.canonical_json(row) + "\n").encode("utf-8")
        if os.fstat(descriptor).st_size + len(encoded) > MAX_LEDGER_BYTES:
            raise CycleContractError("scoreboard ledger size limit exceeded")
        os.write(descriptor, encoded)
        os.fsync(descriptor)
        return row
    finally:
        os.close(descriptor)


class GovernedCycleRunner:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.lock_path = _safe_local(self.workspace_root, ".bco_v3_1_cycle.lock")

    def run(
        self,
        *,
        cycle_id: str,
        mission_id: str,
        mission_version: int,
        cancel_token: Mapping[str, Any],
        baseline_envelope: Mapping[str, Any],
        monitored_root: Path,
        expected_public_key_fingerprint: str | None,
        minimum_generation: int,
        policies: Mapping[str, Any],
        capabilities: Sequence[Mapping[str, Any]],
        test_results: Mapping[str, Any],
        result_assertions: Mapping[str, Any],
        coverage_complete: bool,
        previous_scoreboard_state: str | None = None,
        current_scan: Mapping[str, Any] | None = None,
        previous_scan: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not cycle_id or not mission_id or type(mission_version) is not int or mission_version < 1:
            raise CycleContractError("cycle and mission identity are required")
        if _cancelled(cancel_token, mission_version, "PRE_LOCK"):
            return cancelled_receipt(mission_id, mission_version, "PRE_LOCK")
        descriptor = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise CycleContractError("CONCURRENT_CYCLE_CONFLICT") from exc
            if _cancelled(cancel_token, mission_version, "PRE_COMPARE"):
                return cancelled_receipt(mission_id, mission_version, "PRE_COMPARE")
            report = drift.detect_drift(
                baseline_envelope,
                root=monitored_root,
                expected_public_key_fingerprint=expected_public_key_fingerprint,
                minimum_generation=minimum_generation,
                policies=policies,
                capabilities=capabilities,
                test_results=test_results,
                result_assertions=result_assertions,
                coverage_complete=coverage_complete,
            )
            if _cancelled(cancel_token, mission_version, "POST_COMPARE"):
                return cancelled_receipt(mission_id, mission_version, "POST_COMPARE")
            scan_diff = None
            if current_scan is not None:
                if current_scan.get("coverage_complete") is not True:
                    report["events"].append({"class": "PARTIAL_OR_UNKNOWN", "severity": "HARD", "evidence": current_scan.get("receipt_sha256")})
                    report["hard_veto"] = True
                    report["state"] = "DRIFT_DETECTED"
                    report["receipt_sha256"] = drift.digest({key: value for key, value in report.items() if key != "receipt_sha256"})
                if previous_scan is not None:
                    scan_diff = drift.diff_capability_scans(previous_scan, current_scan)
            if _cancelled(cancel_token, mission_version, "PRE_CANDIDATE"):
                return cancelled_receipt(mission_id, mission_version, "PRE_CANDIDATE")
            scoreboard = drift.regression_scoreboard(report, previous_state=previous_scoreboard_state)
            repair = drift.shadow_repair_plan(report, str(baseline_envelope.get("body_sha256") or ""))
            if _cancelled(cancel_token, mission_version, "PRE_COMMIT"):
                return cancelled_receipt(mission_id, mission_version, "PRE_COMMIT")
            ledger_path = _safe_local(self.workspace_root, "scoreboards/cycle_scoreboard_v3_1.jsonl")
            proof_refs = [report["receipt_sha256"], scoreboard["receipt_sha256"], repair["receipt_sha256"]]
            if scan_diff:
                proof_refs.append(scan_diff["receipt_sha256"])
            ledger_event = _append_scoreboard(ledger_path, cycle_id, scoreboard, proof_refs)
            result = {
                "schema": SCHEMA,
                "version": VERSION,
                "state": scoreboard["state"],
                "mission_id": mission_id,
                "mission_version": mission_version,
                "cycle_id": cycle_id,
                "drift_report": report,
                "scan_diff": scan_diff,
                "scoreboard": scoreboard,
                "shadow_repair_plan": repair,
                "ledger_event_hash": ledger_event["event_hash"],
                "commitPerformed": True,
                "baselineAdvanceAuthorized": False,
                "sourceMutationAuthorized": False,
                "stablePromotionAuthorized": False,
                "providerEffectAuthorized": False,
                "manualUserTasks": [],
                "ownerActionRequired": False,
            }
            result["receipt_sha256"] = drift.digest(result)
            return result
        finally:
            os.close(descriptor)


def rollback_control_pointer(
    workspace_root: Path,
    *,
    expected_current_baseline_sha256: str,
    target_baseline_path: str,
    target_baseline_sha256: str,
) -> dict[str, Any]:
    if not all((expected_current_baseline_sha256, target_baseline_path, target_baseline_sha256)):
        raise CycleContractError("rollback binding is incomplete")
    root = workspace_root.resolve()
    pointer = _safe_local(root, "baseline_pointer_v3_1.json")
    if pointer.exists():
        current = json.loads(pointer.read_text(encoding="utf-8"))
        if current.get("baseline_sha256") != expected_current_baseline_sha256:
            raise CycleContractError("ROLLBACK_POINTER_MISMATCH_OR_REPLAY")
    target = _safe_local(root, target_baseline_path)
    if not target.is_file() or baseline.digest(json.loads(target.read_text(encoding="utf-8"))) != target_baseline_sha256:
        raise CycleContractError("rollback target is unavailable or mismatched")
    value = {
        "schema": "BCO_PRIME_BASELINE_POINTER_V3_1",
        "baseline_path": target.relative_to(root).as_posix(),
        "baseline_sha256": target_baseline_sha256,
        "sourceMutationAuthorized": False,
        "providerEffectAuthorized": False,
    }
    temporary = pointer.with_suffix(".tmp")
    temporary.write_text(baseline.canonical_json(value) + "\n", encoding="utf-8")
    os.replace(temporary, pointer)
    result = {
        "schema": "BCO_PRIME_CONTROL_POINTER_ROLLBACK_V3_1",
        "state": "ROLLED_BACK_CONTROL_POINTER_ONLY",
        "baseline_sha256": target_baseline_sha256,
        "sourceMutationAuthorized": False,
        "stablePromotionAuthorized": False,
        "providerEffectAuthorized": False,
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }
    result["receipt_sha256"] = drift.digest(result)
    return result


__all__ = ["CycleContractError", "GovernedCycleRunner", "cancelled_receipt", "rollback_control_pointer"]
