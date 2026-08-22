#!/usr/bin/env python3
"""Resumable 24-hour controller for the SOVARA v40 recovery canary."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Callable

from run_durable_recovery_canary_v40 import run_canary


SOAK_CONTRACT = "SOVARA_DURABLE_RECOVERY_SOAK_V41"
RECEIPT_CONTRACT = "SOVARA_DURABLE_RECOVERY_SOAK_RECEIPT_V41"
EXPECTED_DURATION_HOURS = 24
CADENCE_SECONDS = 3600
MINIMUM_CYCLES = 25
DEFAULT_SOAK_ID = "SOVARA-V41-24H-SOAK"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class SoakCorruption(RuntimeError):
    """Raised when persisted state or ledger evidence cannot be trusted."""


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps require timezone information")
    return value.astimezone(timezone.utc)


def _utc_text(value: datetime) -> str:
    return _utc(value).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise SoakCorruption("invalid UTC timestamp") from exc
    if parsed.tzinfo is None:
        raise SoakCorruption("timestamp is not timezone aware")
    return parsed.astimezone(timezone.utc)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name and Path(temporary_name).exists():
            Path(temporary_name).unlink()


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _load_state(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SoakCorruption("state is missing or invalid") from exc
    required = {
        "contract", "soakId", "startAt", "expectedEndAt", "status",
        "cycleCount", "passedCycles", "failedCycles", "ledgerHeadSha256",
    }
    if not isinstance(value, dict) or not required.issubset(value):
        raise SoakCorruption("state schema is incomplete")
    if value["contract"] != SOAK_CONTRACT:
        raise SoakCorruption("state contract mismatch")
    return value


def _new_state(soak_id: str, start_at: datetime) -> dict[str, Any]:
    start_at = _utc(start_at)
    return {
        "contract": SOAK_CONTRACT,
        "soakId": soak_id,
        "startAt": _utc_text(start_at),
        "expectedEndAt": _utc_text(
            start_at + timedelta(hours=EXPECTED_DURATION_HOURS)
        ),
        "expectedDurationHours": EXPECTED_DURATION_HOURS,
        "cadenceSeconds": CADENCE_SECONDS,
        "minimumCycles": MINIMUM_CYCLES,
        "status": "RUNNING",
        "cycleCount": 0,
        "passedCycles": 0,
        "failedCycles": 0,
        "ledgerHeadSha256": "",
        "lastCycleId": None,
        "updatedAt": _utc_text(start_at),
        "failureCode": None,
    }


def validate_ledger(path: Path, state: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate every JSONL record, fixed schedule timestamp and hash link."""
    if not path.exists():
        records: list[dict[str, Any]] = []
    else:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            records = [json.loads(line) for line in lines if line.strip()]
        except (OSError, json.JSONDecodeError) as exc:
            raise SoakCorruption("ledger is not valid JSONL") from exc
    start_at = _parse_utc(state["startAt"])
    previous = ""
    cycle_ids: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise SoakCorruption("ledger record is not an object")
        event_hash = record.get("eventSha256")
        binding = {key: value for key, value in record.items() if key != "eventSha256"}
        expected_schedule = _utc_text(start_at + timedelta(seconds=index * CADENCE_SECONDS))
        if (
            record.get("contract") != "SOVARA_DURABLE_RECOVERY_SOAK_EVENT_V41"
            or record.get("soakId") != state["soakId"]
            or record.get("sequence") != index + 1
            or record.get("scheduledAt") != expected_schedule
            or record.get("prevSha256") != previous
            or event_hash != _sha256(binding)
            or record.get("status") not in {"PASS", "FAIL"}
        ):
            raise SoakCorruption("ledger chain or schedule validation failed")
        cycle_id = record.get("cycleId")
        if not isinstance(cycle_id, str) or not _SAFE_ID.fullmatch(cycle_id):
            raise SoakCorruption("ledger cycle ID is invalid")
        if cycle_id in cycle_ids:
            raise SoakCorruption("ledger contains a duplicate cycle ID")
        cycle_ids.add(cycle_id)
        previous = event_hash
    return records


def _derived_state(
    state: dict[str, Any], records: list[dict[str, Any]]
) -> dict[str, Any]:
    count = len(records)
    passed = sum(record["status"] == "PASS" for record in records)
    failed = count - passed
    head = records[-1]["eventSha256"] if records else ""
    stored_count = state.get("cycleCount")
    if not isinstance(stored_count, int) or stored_count < 0 or stored_count > count:
        raise SoakCorruption("state is ahead of its ledger")
    prefix_head = records[stored_count - 1]["eventSha256"] if stored_count else ""
    if state.get("ledgerHeadSha256") != prefix_head:
        raise SoakCorruption("state and ledger head disagree")
    if stored_count == count and (
        state.get("passedCycles") != passed or state.get("failedCycles") != failed
    ):
        raise SoakCorruption("state counters disagree with ledger")

    reconciled = dict(state)
    reconciled.update(
        {
            "cycleCount": count,
            "passedCycles": passed,
            "failedCycles": failed,
            "ledgerHeadSha256": head,
            "lastCycleId": records[-1]["cycleId"] if records else None,
        }
    )
    last_execution = _parse_utc(records[-1]["executedAt"]) if records else None
    end_at = _parse_utc(state["expectedEndAt"])
    if failed:
        reconciled["status"] = "FAIL"
        reconciled["failureCode"] = "CANARY_CYCLE_FAILED"
    elif count >= MINIMUM_CYCLES and last_execution is not None and last_execution >= end_at:
        reconciled["status"] = "PASS"
        reconciled["failureCode"] = None
    else:
        reconciled["status"] = "RUNNING"
        reconciled["failureCode"] = None
    if stored_count < count:
        reconciled["updatedAt"] = records[-1]["executedAt"]
    return reconciled


def _receipt(state: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    next_cycle_at = None
    if state["status"] == "RUNNING":
        start = _parse_utc(state["startAt"])
        next_cycle_at = _utc_text(
            start + timedelta(seconds=state["cycleCount"] * CADENCE_SECONDS)
        )
    last = records[-1] if records else None
    return {
        "contract": RECEIPT_CONTRACT,
        "soakId": state["soakId"],
        "status": state["status"],
        "startAt": state["startAt"],
        "expectedEndAt": state["expectedEndAt"],
        "expectedDurationHours": EXPECTED_DURATION_HOURS,
        "minimumCycles": MINIMUM_CYCLES,
        "cycleCount": state["cycleCount"],
        "passedCycles": state["passedCycles"],
        "failedCycles": state["failedCycles"],
        "nextCycleAt": next_cycle_at,
        "ledgerHeadSha256": state["ledgerHeadSha256"],
        "lastCycle": (
            {
                "cycleId": last["cycleId"],
                "scheduledAt": last["scheduledAt"],
                "executedAt": last["executedAt"],
                "status": last["status"],
                "canaryProofSha256": last["canaryProofSha256"],
            }
            if last else None
        ),
        "failureCode": state.get("failureCode"),
        "sanitized": True,
    }


def _fail_closed(
    state_path: Path,
    receipt_path: Path,
    state: dict[str, Any] | None,
    failure_code: str,
) -> dict[str, Any]:
    if state is None:
        state = _new_state(DEFAULT_SOAK_ID, datetime.now(timezone.utc))
    state = dict(state)
    state["status"] = "FAIL"
    state["failureCode"] = failure_code
    _atomic_write_json(state_path, state)
    receipt = _receipt(state, [])
    receipt["cycleCount"] = state.get("cycleCount", 0)
    receipt["passedCycles"] = state.get("passedCycles", 0)
    receipt["failedCycles"] = state.get("failedCycles", 0)
    receipt["ledgerHeadSha256"] = state.get("ledgerHeadSha256", "")
    _atomic_write_json(receipt_path, receipt)
    return receipt


def run_tick(
    *,
    state_path: Path,
    ledger_path: Path,
    receipt_path: Path,
    now: datetime,
    start_at: datetime | None = None,
    soak_id: str = DEFAULT_SOAK_ID,
    cycle_id: str | None = None,
    canary_runner: Callable[[Path], dict[str, object]] = run_canary,
) -> dict[str, Any]:
    """Validate, execute at most one due cycle, persist, and return a receipt."""
    now = _utc(now)
    state: dict[str, Any] | None = None
    try:
        if state_path.exists():
            state = _load_state(state_path)
        else:
            if ledger_path.exists() and ledger_path.read_text(encoding="utf-8").strip():
                raise SoakCorruption("ledger exists without state")
            if not _SAFE_ID.fullmatch(soak_id):
                raise SoakCorruption("soak ID is invalid")
            state = _new_state(soak_id, start_at or now)
            _atomic_write_json(state_path, state)
            _atomic_write_text(ledger_path, "")

        records = validate_ledger(ledger_path, state)
        reconciled = _derived_state(state, records)
        if reconciled != state:
            state = reconciled
            _atomic_write_json(state_path, state)
        if state["status"] in {"PASS", "FAIL"}:
            receipt = _receipt(state, records)
            _atomic_write_json(receipt_path, receipt)
            return receipt

        if cycle_id is not None and not _SAFE_ID.fullmatch(cycle_id):
            raise SoakCorruption("cycle ID is invalid")
        if cycle_id is not None and any(
            record["cycleId"] == cycle_id for record in records
        ):
            receipt = _receipt(state, records)
            _atomic_write_json(receipt_path, receipt)
            return receipt

        sequence = len(records) + 1
        scheduled_at = _parse_utc(state["startAt"]) + timedelta(
            seconds=(sequence - 1) * CADENCE_SECONDS
        )
        if now < scheduled_at:
            receipt = _receipt(state, records)
            _atomic_write_json(receipt_path, receipt)
            return receipt
        selected_cycle_id = cycle_id or f"{state['soakId']}:cycle:{sequence - 1:02d}"

        failure_code = None
        with tempfile.TemporaryDirectory() as directory:
            try:
                canary = canary_runner(Path(directory) / "canary.json")
                assertions_value = canary.get("assertions")
                assertions = (
                    {
                        str(key): value
                        for key, value in assertions_value.items()
                        if isinstance(key, str) and isinstance(value, bool)
                    }
                    if isinstance(assertions_value, dict) else {}
                )
                proof_hash = canary.get("proofSha256")
                if not isinstance(proof_hash, str) or not _SHA256.fullmatch(proof_hash):
                    raise ValueError("canary proof hash missing")
                cycle_passed = (
                    canary.get("status") == "PASS"
                    and bool(assertions)
                    and all(assertions.values())
                )
                if not cycle_passed:
                    failure_code = "CANARY_ASSERTION_FAILED"
                final_chain = canary.get("finalEventChain")
                chain_head = (
                    final_chain.get("headSha256")
                    if isinstance(final_chain, dict) else None
                )
                if chain_head is not None and (
                    not isinstance(chain_head, str) or not _SHA256.fullmatch(chain_head)
                ):
                    raise ValueError("canary chain hash invalid")
                canary_contract = str(canary.get("contract", "UNKNOWN"))[:80]
            except Exception as exc:  # fail closed without persisting raw exception text
                assertions = {}
                proof_hash = hashlib.sha256(type(exc).__name__.encode()).hexdigest()
                chain_head = None
                canary_contract = "CANARY_EXECUTION_FAILED"
                cycle_passed = False
                failure_code = f"CANARY_EXCEPTION_{type(exc).__name__.upper()}"

        binding: dict[str, Any] = {
            "contract": "SOVARA_DURABLE_RECOVERY_SOAK_EVENT_V41",
            "soakId": state["soakId"],
            "sequence": sequence,
            "cycleId": selected_cycle_id,
            "scheduledAt": _utc_text(scheduled_at),
            "executedAt": _utc_text(now),
            "status": "PASS" if cycle_passed else "FAIL",
            "canaryContract": canary_contract,
            "canaryAssertions": assertions,
            "canaryProofSha256": proof_hash,
            "canaryEventHeadSha256": chain_head,
            "failureCode": failure_code,
            "prevSha256": records[-1]["eventSha256"] if records else "",
        }
        event = {**binding, "eventSha256": _sha256(binding)}
        records.append(event)
        ledger_text = "".join(
            json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
            for record in records
        )
        _atomic_write_text(ledger_path, ledger_text)
        state = _derived_state(state, records)
        state["updatedAt"] = _utc_text(now)
        _atomic_write_json(state_path, state)
        receipt = _receipt(state, records)
        _atomic_write_json(receipt_path, receipt)
        return receipt
    except SoakCorruption:
        return _fail_closed(state_path, receipt_path, state, "STATE_OR_LEDGER_CORRUPTION")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, default=Path("DURABLE_SOAK_STATE_V41.json"))
    parser.add_argument("--ledger", type=Path, default=Path("DURABLE_SOAK_LEDGER_V41.jsonl"))
    parser.add_argument("--receipt", type=Path, default=Path("DURABLE_SOAK_RECEIPT_V41.json"))
    parser.add_argument("--soak-id", default=DEFAULT_SOAK_ID)
    parser.add_argument("--cycle-id")
    parser.add_argument("--at", help="UTC execution timestamp; defaults to current UTC")
    parser.add_argument("--start-at", help="Immutable UTC start for first initialization")
    args = parser.parse_args()
    now = _parse_utc(args.at) if args.at else datetime.now(timezone.utc)
    start_at = _parse_utc(args.start_at) if args.start_at else None
    receipt = run_tick(
        state_path=args.state,
        ledger_path=args.ledger,
        receipt_path=args.receipt,
        now=now,
        start_at=start_at,
        soak_id=args.soak_id,
        cycle_id=args.cycle_id,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 1 if receipt["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
