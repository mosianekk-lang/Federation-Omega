#!/usr/bin/env python3
"""Google Cloud Storage durable mission store for SOVARA SIC v2.

Uses generation-match preconditions so concurrent writers cannot silently
overwrite mission state. Credentials are resolved by Google ADC at runtime and
are never accepted as function arguments or persisted in mission records.
"""

from __future__ import annotations

from dataclasses import asdict
import json
from typing import Any

from sovara_sovereign_intelligence_court_v2 import CourtResult, MissionSnapshot


class GCSMissionStore:
    def __init__(self, *, bucket_name: str, prefix: str = "sovara/sic-v2", client: Any | None = None):
        if not bucket_name or "/" in bucket_name:
            raise ValueError("VALID_GCS_BUCKET_NAME_REQUIRED")
        try:
            from google.cloud import storage
        except Exception as exc:  # pragma: no cover - deployment dependency boundary
            raise RuntimeError("GOOGLE_CLOUD_STORAGE_DEPENDENCY_NOT_INSTALLED") from exc
        self._storage = storage
        self.client = client or storage.Client()
        self.bucket = self.client.bucket(bucket_name)
        self.prefix = prefix.strip("/")

    def _name(self, mission_id: str, leaf: str) -> str:
        return f"{self.prefix}/{mission_id}/{leaf}"

    @staticmethod
    def _encode(payload: dict[str, Any]) -> bytes:
        return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")

    def _read(self, name: str) -> tuple[dict[str, Any], int] | None:
        blob = self.bucket.get_blob(name)
        if blob is None:
            return None
        raw = blob.download_as_bytes()
        return json.loads(raw.decode("utf-8")), int(blob.generation)

    def _cas_write(self, name: str, payload: dict[str, Any]) -> None:
        existing = self._read(name)
        expected_generation = existing[1] if existing is not None else 0
        blob = self.bucket.blob(name)
        try:
            blob.upload_from_string(
                self._encode(payload),
                content_type="application/json",
                if_generation_match=expected_generation,
            )
        except Exception as exc:
            if type(exc).__name__ in {"PreconditionFailed", "Conflict"}:
                raise RuntimeError("MISSION_STATE_CAS_CONFLICT") from exc
            raise

    def load_snapshot(self, mission_id: str) -> MissionSnapshot | None:
        item = self._read(self._name(mission_id, "snapshot.json"))
        return MissionSnapshot(**item[0]) if item else None

    def save_snapshot(self, snapshot: MissionSnapshot) -> None:
        self._cas_write(self._name(snapshot.mission_id, "snapshot.json"), asdict(snapshot))

    def load_result(self, mission_id: str) -> CourtResult | None:
        item = self._read(self._name(mission_id, "sealed-result.json"))
        if not item:
            return None
        result = CourtResult(**item[0])
        from sovara_sovereign_intelligence_court_v2 import _canonical_json, _sha256_text

        expected = result.result_sha256
        material = asdict(result)
        material["result_sha256"] = None
        actual = _sha256_text(_canonical_json(material))
        if not expected or expected != actual:
            raise RuntimeError("SEALED_RESULT_HASH_MISMATCH")
        return result

    def save_result(self, result: CourtResult) -> None:
        name = self._name(result.mission_id, "sealed-result.json")
        existing = self._read(name)
        payload = asdict(result)
        if existing is not None:
            if existing[0] == payload:
                return
            raise RuntimeError("SEALED_RESULT_ALREADY_EXISTS_WITH_DIFFERENT_CONTENT")
        blob = self.bucket.blob(name)
        try:
            blob.upload_from_string(
                self._encode(payload),
                content_type="application/json",
                if_generation_match=0,
            )
        except Exception as exc:
            if type(exc).__name__ in {"PreconditionFailed", "Conflict"}:
                raise RuntimeError("SEALED_RESULT_CREATE_CONFLICT") from exc
            raise
