#!/usr/bin/env python3
"""GNS4 hosted queue drain.

Consumes only explicitly allowlisted GNS4_HOSTED_WIF work from the canonical
ARCHITRON/GNS4 spreadsheet. Uses Google ADC/WIF credentials and performs no
external provider mutation beyond bounded control-plane row/proof updates.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

SPREADSHEET_ID = os.environ.get(
    "GNS4_SPREADSHEET_ID",
    "1LSVjK9YK6u2CMrvetOcXpun4VQnOh5cE6b3w6z_KTHg",
)
QUEUE_SHEET = "Scheduler_Dispatch_Queue_v3"
PROOF_SHEET = "Scheduler_Proof_v3"
HEALTH_SHEET = "Scheduler_Health_v4"
WORKER_VERSION = "GNS4-HOSTED-WIF-1.0.0"
ALLOWED_EXECUTOR = "GNS4_HOSTED_WIF"
ALLOWED_HANDLER = "GNS4_HOSTED_STATUS_CANARY"
QUEUED_STATUS = "QUEUED_EXTERNAL_ADAPTER"
FINAL_STATUS = "GNS4_HOSTED_STATUS_VERIFIED"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _session():
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    credentials, _ = google.auth.default(scopes=SCOPES)
    return AuthorizedSession(credentials)


def _url(path: str) -> str:
    return f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/{path}"


def _get_values(session, a1_range: str) -> list[list[str]]:
    from urllib.parse import quote

    response = session.get(_url(f"values/{quote(a1_range, safe='!:$')}"), timeout=30)
    response.raise_for_status()
    return response.json().get("values", [])


def _update_values(session, a1_range: str, values: list[list[Any]]) -> None:
    from urllib.parse import quote

    response = session.put(
        _url(f"values/{quote(a1_range, safe='!:$')}"),
        params={"valueInputOption": "RAW"},
        json={"range": a1_range, "majorDimension": "ROWS", "values": values},
        timeout=30,
    )
    response.raise_for_status()


def _append_values(session, a1_range: str, values: list[list[Any]]) -> None:
    from urllib.parse import quote

    response = session.post(
        _url(f"values/{quote(a1_range, safe='!:$')}:append"),
        params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
        json={"range": a1_range, "majorDimension": "ROWS", "values": values},
        timeout=30,
    )
    response.raise_for_status()


def _index(headers: list[str]) -> dict[str, int]:
    return {str(name): i for i, name in enumerate(headers)}


def _pad(row: list[str], size: int) -> list[str]:
    return list(row) + [""] * max(0, size - len(row))


def _find_candidate(values: list[list[str]]) -> tuple[int, list[str], dict[str, int]] | None:
    if not values:
        return None
    headers = [str(v) for v in values[0]]
    idx = _index(headers)
    required = {"dispatch_id", "executor", "handler", "status", "processed_at_utc", "result_json"}
    if not required.issubset(idx):
        raise RuntimeError(f"QUEUE_SCHEMA_MISMATCH:{sorted(required - set(idx))}")
    for sheet_row, raw in enumerate(values[1:], start=2):
        row = _pad([str(v) for v in raw], len(headers))
        if (
            row[idx["executor"]] == ALLOWED_EXECUTOR
            and row[idx["handler"]] == ALLOWED_HANDLER
            and row[idx["status"]] == QUEUED_STATUS
        ):
            return sheet_row, row, idx
    return None


def _claim(session, sheet_row: int, idx: dict[str, int]) -> None:
    status_col = idx["status"] + 1
    column = _column_letter(status_col)
    claim = "CLAIMED_GNS4_HOSTED"
    _update_values(session, f"{QUEUE_SHEET}!{column}{sheet_row}", [[claim]])
    readback = _get_values(session, f"{QUEUE_SHEET}!{column}{sheet_row}:{column}{sheet_row}")
    if not readback or str(readback[0][0]) != claim:
        raise RuntimeError("CLAIM_READBACK_MISMATCH")


def _column_letter(number: int) -> str:
    if number < 1:
        raise ValueError("column number must be >= 1")
    out = ""
    n = number
    while n:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def _finalize(
    session,
    sheet_row: int,
    row: list[str],
    idx: dict[str, int],
    result: dict[str, Any],
) -> None:
    row[idx["status"]] = FINAL_STATUS
    row[idx["processed_at_utc"]] = result["checkedAtUtc"]
    row[idx["result_json"]] = json.dumps(result, sort_keys=True, separators=(",", ":"))
    _update_values(session, f"{QUEUE_SHEET}!A{sheet_row}:N{sheet_row}", [row[:14]])

    readback = _get_values(session, f"{QUEUE_SHEET}!A{sheet_row}:N{sheet_row}")
    if not readback:
        raise RuntimeError("FINAL_READBACK_EMPTY")
    rb = _pad([str(v) for v in readback[0]], 14)
    if rb[idx["status"]] != FINAL_STATUS or rb[idx["processed_at_utc"]] != result["checkedAtUtc"]:
        raise RuntimeError("FINAL_READBACK_MISMATCH")
    try:
        parsed = json.loads(rb[idx["result_json"]])
    except Exception as exc:
        raise RuntimeError("FINAL_RESULT_JSON_INVALID") from exc
    if parsed.get("dispatchId") != result["dispatchId"] or parsed.get("status") != FINAL_STATUS:
        raise RuntimeError("FINAL_SEMANTIC_READBACK_MISMATCH")


def _append_proof(session, result: dict[str, Any]) -> str:
    proof_id = "GNS4PROOF-" + str(uuid.uuid4())
    evidence = dict(result)
    evidence["proofId"] = proof_id
    _append_values(
        session,
        f"{PROOF_SHEET}!A:J",
        [[
            proof_id,
            result["checkedAtUtc"],
            "GNS4_HOSTED_EXECUTION_SEMANTIC",
            result["dispatchId"],
            FINAL_STATUS,
            json.dumps(evidence, sort_keys=True, separators=(",", ":")),
            "GOOGLE_SHEETS_API_VIA_GITHUB_WIF",
            WORKER_VERSION,
            "HOSTED_WORKER_PROOF_SEPARATE_FROM_NATIVE_GAS_TRIGGER_PROOF",
            "VERIFIED",
        ]],
    )
    rows = _get_values(session, f"{PROOF_SHEET}!A:J")
    if not rows:
        raise RuntimeError("PROOF_READBACK_EMPTY")
    last = _pad([str(v) for v in rows[-1]], 10)
    if last[0] != proof_id or last[3] != result["dispatchId"] or last[4] != FINAL_STATUS or last[9] != "VERIFIED":
        raise RuntimeError("PROOF_READBACK_MISMATCH")
    return proof_id


def _upsert_health(session, result: dict[str, Any], proof_id: str) -> None:
    component = "GNS4-HOSTED-WIF-WORKER"
    rows = _get_values(session, f"{HEALTH_SHEET}!A:P")
    target_row = None
    for row_number, raw in enumerate(rows[1:], start=2):
        if raw and str(raw[0]) == component:
            target_row = row_number
            break
    health = [[
        component,
        "GITHUB_WIF_HOSTED_QUEUE_DRAIN",
        "RUNTIME_VERIFIED",
        "TRUE",
        "TRUE",
        "TRUE",
        result["checkedAtUtc"],
        "300",
        "720",
        "0",
        "0",
        "0",
        proof_id,
        "Continue bounded allowlisted queue draining; fail closed on schema/identity/readback drift.",
        "FALSE",
        "Only GNS4_HOSTED_WIF + GNS4_HOSTED_STATUS_CANARY is executable in v1.",
    ]]
    if target_row:
        _update_values(session, f"{HEALTH_SHEET}!A{target_row}:P{target_row}", health)
    else:
        _append_values(session, f"{HEALTH_SHEET}!A:P", health)


def run_once(session=None) -> dict[str, Any]:
    session = session or _session()
    values = _get_values(session, f"{QUEUE_SHEET}!A:N")
    candidate = _find_candidate(values)
    if candidate is None:
        return {
            "ok": True,
            "status": "GNS4_HOSTED_QUEUE_EMPTY",
            "workerVersion": WORKER_VERSION,
            "externalEffect": "NONE",
            "checkedAtUtc": utcnow(),
        }

    sheet_row, row, idx = candidate
    dispatch_id = row[idx["dispatch_id"]]
    _claim(session, sheet_row, idx)
    checked = utcnow()
    result = {
        "ok": True,
        "status": FINAL_STATUS,
        "handler": ALLOWED_HANDLER,
        "dispatchId": dispatch_id,
        "workerVersion": WORKER_VERSION,
        "executionHost": "GITHUB_ACTIONS_WIF",
        "googleIdentityBound": True,
        "controlPlaneSpreadsheetId": SPREADSHEET_ID,
        "provider": "GOOGLE_SHEETS_API",
        "semanticReadbackVerified": True,
        "emailSending": False,
        "externalEffect": "NONE",
        "truthBoundary": "CONTROL_PLANE_ROW_AND_PROOF_MUTATION_ONLY;NO_NATIVE_GAS_OR_EXTERNAL_PROVIDER_EFFECT",
        "checkedAtUtc": checked,
    }
    _finalize(session, sheet_row, row, idx, result)
    proof_id = _append_proof(session, result)
    result["proofId"] = proof_id
    _upsert_health(session, result, proof_id)
    return result


def main() -> int:
    try:
        result = run_once()
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "status": "GNS4_HOSTED_QUEUE_DRAIN_FAILED",
                    "errorType": type(exc).__name__,
                    "error": str(exc)[:1000],
                    "workerVersion": WORKER_VERSION,
                    "checkedAtUtc": utcnow(),
                },
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
