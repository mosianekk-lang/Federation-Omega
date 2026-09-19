"""Proof-bound BMF provider-row capture for KDV read continuity.

This module is deliberately not a Google client. A separately authenticated
reader supplies a provider-read row set. The compiler validates the exact BMF
shape, normalizes rows through FKCM, derives an immutable row-set identity, and
delegates deterministic AS_OF packaging to KDV_READ_CONTINUITY_V1.

No write, provider mutation, cutover, or canonical authority is exposed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from federation.fkcm_v1.adapter import from_bmf_row
from federation.kdv_read_continuity_v1 import (
    ContinuitySnapshot,
    build_continuity_snapshot,
)

SCHEMA = "FUSE-KDV-READ-CONTINUITY-CAPTURE-V1"
VERSION = "1.0.0"

REQUIRED_BMF_FIELDS = frozenset({
    "event_id",
    "stream_id",
    "stream_version",
    "event_type",
    "recorded_at",
    "valid_at",
    "idempotency_key",
    "truth_class",
    "privacy_class",
    "payload_json",
    "source_refs_json",
    "directive_id",
    "mission_id",
    "workstream_id",
    "supersedes_json",
    "event_sha256",
    "provider_persisted_at_sast",
    "proof_refs_json",
    "causal_parent_ids_json",
    "contradicts_json",
    "schema_version",
})
_JSON_OBJECT_FIELDS = ("payload_json",)
_JSON_ARRAY_FIELDS = (
    "source_refs_json",
    "supersedes_json",
    "proof_refs_json",
    "causal_parent_ids_json",
    "contradicts_json",
)


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _sha(value: bytes) -> str:
    return sha256(value).hexdigest()


def _required(value: Any, code: str) -> str:
    text=str(value or "").strip()
    if not text:
        raise ValueError(code)
    return text


def _hex64(value: Any, code: str) -> str:
    text=str(value or "").strip().lower()
    if len(text)!=64 or any(c not in "0123456789abcdef" for c in text):
        raise ValueError(code)
    return text


def _parse_json(raw: Any, *, field: str, kind: type) -> Any:
    if isinstance(raw, kind):
        return raw
    try:
        value=json.loads(str(raw))
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"KDV_CAPTURE_JSON_INVALID:{field}") from exc
    if not isinstance(value, kind):
        raise ValueError(f"KDV_CAPTURE_JSON_TYPE_INVALID:{field}")
    return value


def _normalized_row(row: Mapping[str, Any]) -> dict[str, Any]:
    missing=sorted(REQUIRED_BMF_FIELDS-set(row))
    if missing:
        raise ValueError("KDV_CAPTURE_BMF_FIELDS_MISSING:"+",".join(missing))
    out={key:row.get(key,"") for key in sorted(REQUIRED_BMF_FIELDS)}
    for field in (
        "event_id","stream_id","stream_version","event_type","recorded_at",
        "valid_at","idempotency_key","truth_class","privacy_class",
        "provider_persisted_at_sast","schema_version",
    ):
        _required(out[field],f"KDV_CAPTURE_REQUIRED:{field}")
    _hex64(out["event_sha256"],"KDV_CAPTURE_EVENT_SHA256_INVALID")
    for field in _JSON_OBJECT_FIELDS:
        out[field]=_parse_json(out[field],field=field,kind=dict)
    for field in _JSON_ARRAY_FIELDS:
        out[field]=_parse_json(out[field],field=field,kind=list)
    return out


@dataclass(frozen=True, slots=True)
class CaptureReceipt:
    schema: str
    version: str
    source_ref: str
    observed_at: str
    provider_read_verified_at_capture: bool
    row_count: int
    stream_count: int
    normalized_event_count: int
    rowset_sha256: str
    provider_event_hashset_sha256: str
    source_revision: str
    continuity_archive_sha256: str
    continuity_projection_sha256: str
    canonical_authority: bool
    write_authority: bool
    provider_effect_authorized: bool
    runtime_deployment_proven: bool
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class CapturePackage:
    snapshot: ContinuitySnapshot
    receipt: CaptureReceipt


def capture_provider_bmf_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    source_ref: str,
    observed_at: str,
    schema_sha256: str,
    provider_read_verified_at_capture: bool,
) -> CapturePackage:
    if provider_read_verified_at_capture is not True:
        raise ValueError("KDV_CAPTURE_REQUIRES_VERIFIED_PROVIDER_READ")
    source_ref=_required(source_ref,"KDV_CAPTURE_SOURCE_REF_REQUIRED")
    observed_at=_required(observed_at,"KDV_CAPTURE_OBSERVED_AT_REQUIRED")
    _hex64(schema_sha256,"KDV_CAPTURE_SCHEMA_SHA256_INVALID")
    if not rows:
        raise ValueError("KDV_CAPTURE_ROWS_REQUIRED")

    normalized=tuple(_normalized_row(row) for row in rows)
    event_ids=[str(row["event_id"]) for row in normalized]
    if len(event_ids)!=len(set(event_ids)):
        raise ValueError("KDV_CAPTURE_DUPLICATE_EVENT_ID")
    stream_versions=[(str(row["stream_id"]),str(row["stream_version"])) for row in normalized]
    if len(stream_versions)!=len(set(stream_versions)):
        raise ValueError("KDV_CAPTURE_DUPLICATE_STREAM_VERSION")

    stable_rows=tuple(sorted(normalized,key=lambda row:(
        str(row["stream_id"]),float(str(row["stream_version"])),str(row["event_id"])
    )))
    rowset_sha=_sha(_canonical(stable_rows))
    provider_hashes=tuple(sorted(str(row["event_sha256"]).lower() for row in stable_rows))
    provider_hashset_sha=_sha(_canonical(provider_hashes))
    source_revision=f"kdv-bmf-snapshot-sha256:{rowset_sha}"

    events=tuple(from_bmf_row(row) for row in stable_rows)
    snapshot=build_continuity_snapshot(
        events,
        source_id="KIM_DATAVERSE:BMF_SHADOW_EVENTS",
        source_revision=source_revision,
        observed_at=observed_at,
        schema_sha256=schema_sha256,
        provider_read_verified_at_capture=True,
    )
    payload={
        "schema":SCHEMA,
        "version":VERSION,
        "source_ref":source_ref,
        "observed_at":observed_at,
        "provider_read_verified_at_capture":True,
        "row_count":len(stable_rows),
        "stream_count":len({str(row["stream_id"]) for row in stable_rows}),
        "normalized_event_count":len(events),
        "rowset_sha256":rowset_sha,
        "provider_event_hashset_sha256":provider_hashset_sha,
        "source_revision":source_revision,
        "continuity_archive_sha256":snapshot.archive_sha256,
        "continuity_projection_sha256":snapshot.projection_sha256,
        "canonical_authority":False,
        "write_authority":False,
        "provider_effect_authorized":False,
        "runtime_deployment_proven":False,
    }
    return CapturePackage(
        snapshot=snapshot,
        receipt=CaptureReceipt(**payload,receipt_sha256=_sha(_canonical(payload))),
    )


__all__=[
    "CapturePackage",
    "CaptureReceipt",
    "REQUIRED_BMF_FIELDS",
    "capture_provider_bmf_rows",
]
