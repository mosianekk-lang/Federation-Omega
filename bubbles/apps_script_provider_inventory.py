from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping
import urllib.error
import urllib.parse
import urllib.request


TARGETS = (
    (
        "ARCHON_CANONICAL",
        "1z4wkTnk3TF3NG6T-1f5PsSl08-3SFUQw4STcYwsiPptdGSVrfSE-4r_R",
    ),
    (
        "CHATOPS_FRESH",
        "1LqRdlFdDlSh79snZYidLk-rdxjR8zGtEnYfkJgB7iA2N98l_yi18Zfeu",
    ),
    (
        "ARCHON_SURFACE_TRANSLATOR",
        "12CrTP0YUQbUpBvLklf_tInjN_k3L5qt3Tkp-M9pIO_O4Cs8dsYRH7kPO",
    ),
)
PROOF_SPREADSHEET_ID = "1OsMaGUmAfv3iszkd6hbY6H1oNznYJ84uqtAga17xpj0"
PROOF_SHEET = "GAS_PRIMARY_PROVIDER_PROOF"
PROOF_RANGE = f"{PROOF_SHEET}!A:P"
PROOF_ID_RANGE = f"{PROOF_SHEET}!A2:A1000"
SCHEMA = "BUBBLES-GAS-PRIMARY-PROVIDER-PROOF-V1"
TRUTH_BOUNDARY = (
    "READ_ONLY_APPS_SCRIPT_CONTENT_AND_DEPLOYMENT_INVENTORY; "
    "SOURCE_AND_DEPLOYMENT_VALUES_NOT_RECORDED; "
    "INSTALLABLE_TRIGGERS_NOT_EXPOSED_BY_APPS_SCRIPT_REST_V1"
)

RequestJson = Callable[..., tuple[int, Any]]


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _request_json(
    url: str,
    *,
    access_token: str,
    method: str = "GET",
    body: Mapping[str, Any] | None = None,
    timeout: int = 30,
) -> tuple[int, Any]:
    data = None
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {access_token}",
    }
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        headers["content-type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            return int(response.status), json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw) if raw else {}
        except Exception:
            payload = {}
        return int(exc.code), payload
    except Exception as exc:  # pragma: no cover - provider runner dependent
        return 0, {"transport_error": type(exc).__name__}


def _content_inventory(
    script_id: str,
    *,
    access_token: str,
    request_json: RequestJson,
) -> dict[str, Any]:
    quoted = urllib.parse.quote(script_id, safe="")
    status, body = request_json(
        f"https://script.googleapis.com/v1/projects/{quoted}/content",
        access_token=access_token,
    )
    files = body.get("files", []) if status == 200 and isinstance(body, Mapping) else []
    return {
        "content_http_status": status,
        "file_count": len(files) if status == 200 else None,
        "content_sha256": _canonical_sha256(body) if status == 200 else None,
    }


def _deployment_inventory(
    script_id: str,
    *,
    access_token: str,
    request_json: RequestJson,
) -> dict[str, Any]:
    quoted = urllib.parse.quote(script_id, safe="")
    deployments: list[Any] = []
    page_token = ""
    page_count = 0
    last_status = 0
    while page_count < 20:
        query = {"pageSize": "50"}
        if page_token:
            query["pageToken"] = page_token
        url = (
            f"https://script.googleapis.com/v1/projects/{quoted}/deployments?"
            + urllib.parse.urlencode(query)
        )
        last_status, body = request_json(url, access_token=access_token)
        if last_status != 200 or not isinstance(body, Mapping):
            return {
                "deployment_http_status": last_status,
                "deployment_count": None,
                "deployment_inventory_sha256": None,
            }
        deployments.extend(body.get("deployments", []))
        page_count += 1
        page_token = str(body.get("nextPageToken", ""))
        if not page_token:
            return {
                "deployment_http_status": last_status,
                "deployment_count": len(deployments),
                "deployment_inventory_sha256": _canonical_sha256(deployments),
            }
    return {
        "deployment_http_status": 0,
        "deployment_count": None,
        "deployment_inventory_sha256": None,
    }


def _target_inventory(
    label: str,
    script_id: str,
    *,
    access_token: str,
    request_json: RequestJson,
) -> dict[str, Any]:
    content = _content_inventory(
        script_id,
        access_token=access_token,
        request_json=request_json,
    )
    deployments = _deployment_inventory(
        script_id,
        access_token=access_token,
        request_json=request_json,
    )
    proven = (
        content["content_http_status"] == 200
        and deployments["deployment_http_status"] == 200
    )
    return {
        "target_label": label,
        "script_id": script_id,
        **content,
        **deployments,
        "classification": "PROVIDER_READS_PROVEN" if proven else "PROVIDER_READS_UNPROVEN",
    }


def _receipt_id(source_sha: str, target: Mapping[str, Any]) -> str:
    binding = {
        "source_sha": source_sha,
        "target_label": target["target_label"],
        "script_id": target["script_id"],
        "content_sha256": target["content_sha256"],
        "deployment_inventory_sha256": target["deployment_inventory_sha256"],
    }
    return "GASPP-" + _canonical_sha256(binding)[:32]


def _sheet_values_url(cell_range: str, *, append: bool = False) -> str:
    quoted = urllib.parse.quote(cell_range, safe="")
    base = (
        "https://sheets.googleapis.com/v4/spreadsheets/"
        f"{PROOF_SPREADSHEET_ID}/values/{quoted}"
    )
    if not append:
        return base
    return (
        base
        + ":append?valueInputOption=RAW&insertDataOption=INSERT_ROWS"
        + "&includeValuesInResponse=false"
    )


def _existing_receipt_ids(
    *,
    access_token: str,
    request_json: RequestJson,
) -> tuple[int, set[str]]:
    status, body = request_json(
        _sheet_values_url(PROOF_ID_RANGE),
        access_token=access_token,
    )
    if status != 200 or not isinstance(body, Mapping):
        return status, set()
    values = body.get("values", [])
    return status, {
        str(row[0])
        for row in values
        if isinstance(row, list) and row and str(row[0]).strip()
    }


def _proof_row(
    target: Mapping[str, Any],
    *,
    receipt_id: str,
    recorded_at: str,
    source_sha: str,
    credential_alias: str,
) -> list[Any]:
    return [
        receipt_id,
        recorded_at,
        source_sha,
        credential_alias,
        True,
        target["target_label"],
        target["script_id"],
        target["content_http_status"],
        target["file_count"],
        target["content_sha256"],
        target["deployment_http_status"],
        target["deployment_count"],
        target["deployment_inventory_sha256"],
        200,
        target["classification"],
        TRUTH_BOUNDARY,
    ]


def run_provider_proof(
    *,
    access_token: str,
    source_sha: str,
    credential_alias: str,
    request_json: RequestJson = _request_json,
    now: datetime | None = None,
) -> dict[str, Any]:
    recorded_at = (now or datetime.now(timezone.utc)).isoformat()
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "recorded_at": recorded_at,
        "source_sha": source_sha,
        "credential_alias": credential_alias or "NONE",
        "google_authenticated": bool(access_token),
        "targets": [],
        "provider_reads_proven": False,
        "proof_sheet": {
            "spreadsheet_id": PROOF_SPREADSHEET_ID,
            "sheet_name": PROOF_SHEET,
            "read_http": None,
            "write_http": None,
            "rows_expected": len(TARGETS),
            "rows_preexisting": 0,
            "rows_appended": 0,
            "rows_confirmed": 0,
        },
        "trigger_inventory": {
            "proven": False,
            "classification": "NOT_EXPOSED_BY_APPS_SCRIPT_REST_V1",
        },
        "mutation_attempted": False,
        "credential_values_recorded": False,
        "classification": "GOOGLE_ACCESS_TOKEN_UNAVAILABLE",
        "truth_boundary": TRUTH_BOUNDARY,
    }
    if not access_token:
        return receipt

    targets = [
        _target_inventory(
            label,
            script_id,
            access_token=access_token,
            request_json=request_json,
        )
        for label, script_id in TARGETS
    ]
    receipt["targets"] = targets
    reads_proven = all(item["classification"] == "PROVIDER_READS_PROVEN" for item in targets)
    receipt["provider_reads_proven"] = reads_proven
    if not reads_proven:
        receipt["classification"] = "APPS_SCRIPT_PROVIDER_READS_UNPROVEN"
        return receipt

    ids = {_receipt_id(source_sha, target): target for target in targets}
    read_status, existing = _existing_receipt_ids(
        access_token=access_token,
        request_json=request_json,
    )
    receipt["proof_sheet"]["read_http"] = read_status
    if read_status != 200:
        receipt["classification"] = "PROOF_SHEET_READ_UNPROVEN"
        return receipt

    receipt["proof_sheet"]["rows_preexisting"] = len(set(ids) & existing)
    missing = [(receipt_id, target) for receipt_id, target in ids.items() if receipt_id not in existing]
    if missing:
        rows = [
            _proof_row(
                target,
                receipt_id=receipt_id,
                recorded_at=recorded_at,
                source_sha=source_sha,
                credential_alias=credential_alias or "UNKNOWN_AUTHENTICATED_ROUTE",
            )
            for receipt_id, target in missing
        ]
        receipt["mutation_attempted"] = True
        write_status, _ = request_json(
            _sheet_values_url(PROOF_RANGE, append=True),
            access_token=access_token,
            method="POST",
            body={"majorDimension": "ROWS", "values": rows},
        )
        receipt["proof_sheet"]["write_http"] = write_status
        if write_status != 200:
            receipt["classification"] = "PROOF_SHEET_APPEND_UNPROVEN"
            return receipt
        receipt["proof_sheet"]["rows_appended"] = len(rows)

    verify_status, confirmed = _existing_receipt_ids(
        access_token=access_token,
        request_json=request_json,
    )
    receipt["proof_sheet"]["readback_http"] = verify_status
    confirmed_count = len(set(ids) & confirmed) if verify_status == 200 else 0
    receipt["proof_sheet"]["rows_confirmed"] = confirmed_count
    if verify_status == 200 and confirmed_count == len(ids):
        receipt["classification"] = "GAS_PRIMARY_PROVIDER_PROOF_CONFIRMED"
    else:
        receipt["classification"] = "PROOF_SHEET_READBACK_UNPROVEN"
    return receipt


def _credential_alias_from_environment() -> str:
    routes = (
        "GCP_WIF_PAIR",
        "GENERIC_WIF_PAIR",
        "GCP_SA_KEY",
        "GCP_SERVICE_ACCOUNT_KEY",
        "GOOGLE_CREDENTIALS",
        "GOOGLE_SERVICE_ACCOUNT_KEY",
        "GCP_CREDENTIALS",
        "GOOGLE_GHA_CREDS_JSON",
        "GOOGLE_CLOUD_CREDENTIALS",
    )
    return next(
        (route for route in routes if os.environ.get(f"OUTCOME_{route}") == "success"),
        "UNKNOWN_AUTHENTICATED_ROUTE",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a redacted, append-only Apps Script provider inventory proof."
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    receipt = run_provider_proof(
        access_token=os.environ.get("GOOGLE_ACCESS_TOKEN", ""),
        source_sha=os.environ.get("GITHUB_SHA", ""),
        credential_alias=_credential_alias_from_environment(),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "classification": receipt["classification"],
                "provider_reads_proven": receipt["provider_reads_proven"],
                "rows_confirmed": receipt["proof_sheet"]["rows_confirmed"],
                "trigger_inventory": receipt["trigger_inventory"]["classification"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
