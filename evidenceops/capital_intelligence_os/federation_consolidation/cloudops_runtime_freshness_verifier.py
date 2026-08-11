from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

SCHEMA = "FEDOMEGA-CLOUDOPS-RUNTIME-FRESHNESS-1"
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile("github" + r"_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
)


class FreshnessError(RuntimeError):
    """Fail-closed CloudOps evidence validation error."""


@dataclass(frozen=True)
class EvidenceFinding:
    source: str
    category: str
    state: str
    observed_at: str | None
    age_seconds: float | None
    detail: str
    current: bool
    semantic_valid: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def reject_secret_material(value: Any, path: str = "payload") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in {
                "token", "secret", "password", "api_key",
                "credential_value", "private_key",
            }:
                raise FreshnessError(f"secret-bearing field prohibited: {path}.{key}")
            reject_secret_material(item, f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            reject_secret_material(item, f"{path}[{index}]")
    elif isinstance(value, str) and any(pattern.search(value) for pattern in SECRET_PATTERNS):
        raise FreshnessError(f"secret-shaped value prohibited at {path}")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise FreshnessError("timestamps must include a timezone")
    return value.astimezone(timezone.utc)


def parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return datetime.combine(date.fromisoformat(text), datetime.min.time(), timezone.utc)
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise FreshnessError(f"invalid ISO-8601 timestamp: {text}") from exc
    return _utc(parsed)


def _age(observed: datetime | None, now: datetime) -> float | None:
    if observed is None:
        return None
    seconds = (_utc(now) - observed).total_seconds()
    if seconds < -30:
        raise FreshnessError("evidence timestamp is in the future")
    return max(0.0, round(seconds, 6))


def _row_dicts(table: Sequence[Sequence[Any]]) -> list[dict[str, Any]]:
    if not table:
        return []
    headers = [str(item) for item in table[0]]
    return [
        dict(zip(headers, row, strict=False))
        for row in table[1:]
        if any(str(item).strip() for item in row)
    ]


def _latest(
    rows: Sequence[Mapping[str, Any]], timestamp_field: str
) -> tuple[dict[str, Any] | None, datetime | None]:
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for row in rows:
        observed = parse_timestamp(row.get(timestamp_field))
        if observed is not None:
            candidates.append((observed, dict(row)))
    if not candidates:
        return None, None
    observed, row = max(candidates, key=lambda item: item[0])
    return row, observed


def _health_finding(
    table: Sequence[Sequence[Any]], *, now: datetime, ttl_seconds: int
) -> EvidenceFinding:
    rows = _row_dicts(table)
    health_rows = [
        row for row in rows
        if str(row.get("checkType", "")).upper() == "RUNTIME_HEALTH"
    ]
    row, observed = _latest(health_rows, "timestamp")
    if row is None:
        return EvidenceFinding(
            "Health", "RUNTIME_LIVENESS", "MISSING_EVIDENCE", None, None,
            "No timestamped RUNTIME_HEALTH row", False, False,
        )
    age = _age(observed, now)
    try:
        details = json.loads(str(row.get("detailsJson", "")))
    except json.JSONDecodeError:
        return EvidenceFinding(
            "Health", "RUNTIME_LIVENESS", "INVALID_EVIDENCE",
            observed.isoformat(), age, "Latest detailsJson is malformed", False, False,
        )
    body = details.get("body", {})
    semantic = (
        str(row.get("status", "")).upper() == "DONE"
        and details.get("status") == "DONE"
        and details.get("httpStatus") == 200
        and body.get("ok") is True
        and (
            str(body.get("status", "")).lower() in {"live", "done"}
            or body.get("healthOk") is True
        )
    )
    current = bool(semantic and age is not None and age <= ttl_seconds)
    state = (
        "CURRENT_VERIFIED" if current
        else "STALE_HISTORICAL_EVIDENCE" if semantic
        else "INVALID_EVIDENCE"
    )
    service = body.get("service") or body.get("runtime") or body.get("cloudRunService")
    return EvidenceFinding(
        "Health", "RUNTIME_LIVENESS", state, observed.isoformat(), age,
        f"Latest runtime health HTTP={details.get('httpStatus')} service={service}",
        current, semantic,
    )


def _runtime_control_finding(
    table: Sequence[Sequence[Any]], *, now: datetime, ttl_seconds: int
) -> EvidenceFinding:
    rows = _row_dicts(table)
    dated = []
    for row in rows:
        match = re.search(
            r"(20\d{2}-\d{2}-\d{2}(?:T[0-9:.+-]+Z?)?)",
            str(row.get("Proof_Source", "")),
        )
        if match:
            copied = dict(row)
            copied["_timestamp"] = match.group(1)
            dated.append(copied)
    row, observed = _latest(dated, "_timestamp")
    if row is None:
        return EvidenceFinding(
            "Runtime_Control", "ROUTE_CONSTRAINT", "UNDATED_SOURCE_ONLY",
            None, None, "No timestamped runtime-control proof", False, True,
        )
    age = _age(observed, now)
    corrected = str(row.get("Corrected_State", ""))
    status = str(row.get("Status", "")).upper()
    blocking = any(
        token in status for token in ("CONSTRAINT", "OPEN", "BLOCKED")
    ) or any(
        token in corrected.lower()
        for token in ("resolve", "stale", "not processing", "404")
    )
    current = bool(age is not None and age <= ttl_seconds)
    if current and blocking:
        state = "CURRENT_CONSTRAINT_VERIFIED"
    elif blocking:
        state = "STALE_CONSTRAINT_EVIDENCE"
    elif current:
        state = "CURRENT_ROUTE_STATE"
    else:
        state = "STALE_ROUTE_EVIDENCE"
    return EvidenceFinding(
        "Runtime_Control", "ROUTE_CONSTRAINT", state,
        observed.isoformat(), age, corrected or status, current, True,
    )


def _processor_finding(
    table: Sequence[Sequence[Any]], *, now: datetime, ttl_seconds: int
) -> EvidenceFinding:
    rows = _row_dicts(table)
    row, observed = _latest(rows, "Timestamp")
    if row is None:
        return EvidenceFinding(
            "Processor_Health_Probe", "QUEUE_PROCESSOR", "MISSING_EVIDENCE",
            None, None, "No timestamped processor proof", False, False,
        )
    age = _age(observed, now)
    classification = str(row.get("Classification", "")).upper()
    status = str(row.get("Current_Status", "")).upper()
    healthy = (
        classification in {"PROCESSOR_ACTIVE", "CURRENT_PROCESSING_VERIFIED"}
        and status in {"ACTIVE", "VERIFIED"}
    )
    current = bool(healthy and age is not None and age <= ttl_seconds)
    if current:
        state = "CURRENT_VERIFIED"
    elif age is not None and age <= ttl_seconds:
        state = "CURRENT_PROCESSOR_CONSTRAINT"
    else:
        state = "STALE_PROCESSOR_EVIDENCE"
    return EvidenceFinding(
        "Processor_Health_Probe", "QUEUE_PROCESSOR", state,
        observed.isoformat(), age,
        f"{classification}/{status}: {row.get('Observed_State', '')}",
        current, True,
    )


def _authority_finding(
    table: Sequence[Sequence[Any]], *, now: datetime, ttl_seconds: int
) -> EvidenceFinding:
    rows = _row_dicts(table)
    row, observed = _latest(rows, "Timestamp")
    if row is None:
        return EvidenceFinding(
            "Cloud_Authority_Probe_Log", "PROVIDER_AUTHORITY", "MISSING_EVIDENCE",
            None, None, "No timestamped authority probe", False, False,
        )
    age = _age(observed, now)
    status = str(row.get("Status", "")).upper()
    blocker = str(row.get("Blocker", "")).strip()
    current = bool(age is not None and age <= ttl_seconds)
    if current and status in {"DONE", "VERIFIED"}:
        state = "CURRENT_AUTHORITY_READBACK"
    elif current:
        state = "CURRENT_CONSTRAINT_VERIFIED"
    else:
        state = "STALE_AUTHORITY_EVIDENCE"
    return EvidenceFinding(
        "Cloud_Authority_Probe_Log", "PROVIDER_AUTHORITY", state,
        observed.isoformat(), age,
        f"{status}: {blocker or row.get('Actual_Result', '')}", current, True,
    )


def _automation_finding(table: Sequence[Sequence[Any]]) -> EvidenceFinding:
    rows = _row_dicts(table)
    states = {str(row.get("State", "")).upper() for row in rows}
    blocking = sorted(
        state for state in states
        if any(token in state for token in ("BLOCKED", "PENDING", "STALE", "NO_POST"))
    )
    detail = ", ".join(blocking[:8]) if blocking else "No blocking automation states recorded"
    return EvidenceFinding(
        "Automation_Status", "AUTOMATION_CONTROL", "UNDATED_SOURCE_ONLY",
        None, None, detail, False, True,
    )


def _os_proof_finding(table: Sequence[Sequence[Any]]) -> EvidenceFinding:
    rows = _row_dicts(table)
    statuses = {str(row.get("Proof_Status", "")).upper() for row in rows}
    partial = sorted(
        status for status in statuses if "PARTIAL" in status or "HELD" in status
    )
    return EvidenceFinding(
        "OS_Proof_Ledger", "CONTROL_PLANE_PROOF", "UNDATED_SOURCE_ONLY",
        None, None,
        ", ".join(partial[:8]) if partial
        else "Control-plane proof rows exist without observation timestamps",
        False, True,
    )


def verify_cloudops_runtime_freshness(
    *,
    tables: Mapping[str, Sequence[Sequence[Any]]],
    observed_at: datetime,
    runtime_ttl_seconds: int = 3600,
    processor_ttl_seconds: int = 86400,
    route_ttl_seconds: int = 7 * 86400,
    authority_ttl_seconds: int = 7 * 86400,
) -> dict[str, Any]:
    reject_secret_material(tables, "tables")
    now = _utc(observed_at)
    required = {
        "Health", "Runtime_Control", "Automation_Status",
        "Cloud_Authority_Probe_Log", "Processor_Health_Probe", "OS_Proof_Ledger",
    }
    missing = sorted(required - set(tables))
    if missing:
        raise FreshnessError(f"missing required CloudOps tables: {missing}")
    findings = [
        _health_finding(tables["Health"], now=now, ttl_seconds=runtime_ttl_seconds),
        _runtime_control_finding(
            tables["Runtime_Control"], now=now, ttl_seconds=route_ttl_seconds
        ),
        _processor_finding(
            tables["Processor_Health_Probe"], now=now,
            ttl_seconds=processor_ttl_seconds,
        ),
        _authority_finding(
            tables["Cloud_Authority_Probe_Log"], now=now,
            ttl_seconds=authority_ttl_seconds,
        ),
        _automation_finding(tables["Automation_Status"]),
        _os_proof_finding(tables["OS_Proof_Ledger"]),
    ]
    by_category = {finding.category: finding for finding in findings}
    invalid = [finding for finding in findings if not finding.semantic_valid]
    current_runtime = (
        by_category["RUNTIME_LIVENESS"].state == "CURRENT_VERIFIED"
        and by_category["QUEUE_PROCESSOR"].state == "CURRENT_VERIFIED"
        and by_category["ROUTE_CONSTRAINT"].state != "CURRENT_CONSTRAINT_VERIFIED"
    )
    if invalid:
        status = "INVALID_OR_MISSING_EVIDENCE"
    elif current_runtime:
        status = "CURRENT_RUNTIME_VERIFIED"
    elif by_category["RUNTIME_LIVENESS"].state == "STALE_HISTORICAL_EVIDENCE":
        status = "STALE_RUNTIME_PROOF_CURRENT_CONSTRAINTS_ONLY"
    else:
        status = "RUNTIME_NOT_CURRENTLY_VERIFIED"
    latest_timestamp = max(
        (
            parse_timestamp(finding.observed_at)
            for finding in findings
            if finding.observed_at
        ),
        default=None,
    )
    result = {
        "schema": SCHEMA,
        "status": status,
        "observed_at": now.isoformat(),
        "current_runtime_verified": current_runtime,
        "latest_timestamped_evidence_at": (
            latest_timestamp.isoformat() if latest_timestamp else None
        ),
        "findings": [finding.to_dict() for finding in findings],
        "open_gaps": sorted({
            "FRESH_RUNTIME_LIVENESS_READBACK",
            "FRESH_QUEUE_PROCESSOR_READBACK",
            "AUTHORITATIVE_RUNTIME_ENDPOINT_OR_INGRESS",
            "PROVIDER_AUTHORITY_OR_APPROVAL",
        } if not current_runtime else set()),
        "historical_success_preserved": True,
        "stored_done_label_proves_current_runtime": False,
        "credential_value_recorded": False,
        "provider_mutation_performed": False,
        "external_effect_performed": False,
    }
    result["receipt_sha256"] = canonical_sha256(result)
    return result
