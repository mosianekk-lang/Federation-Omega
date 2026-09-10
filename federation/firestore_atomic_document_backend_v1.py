"""Firestore REST adapter for the resident execution atomic backend contract.

The adapter stores a canonical JSON payload plus a monotonically increasing
integer version.  Firestore's provider-issued ``updateTime`` is used as the
compare-and-swap precondition, so a competing writer cannot be overwritten by
the read/patch sequence.  No retry loop is included: callers must read back an
uncertain effect before deciding whether a materially different retry is safe.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .resident_execution_substrate_v1 import AtomicConflict, canonical


SCHEMA = "FUSE-FIRESTORE-ATOMIC-DOCUMENT-BACKEND-V1"
VERSION = "1.0.0"


class FirestoreTransportError(RuntimeError):
    """A redacted provider transport or semantic-readback failure."""


class JsonTransport(Protocol):
    def __call__(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, Any] | None,
    ) -> tuple[int, Mapping[str, Any]]: ...


def _default_transport(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: Mapping[str, Any] | None,
) -> tuple[int, Mapping[str, Any]]:
    payload = None if body is None else canonical(body).encode("utf-8")
    request = Request(url, data=payload, headers=dict(headers), method=method)
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed Google endpoint
            raw = response.read().decode("utf-8", "replace")
            return int(response.status), json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {}
        return int(exc.code), parsed
    except URLError as exc:
        raise FirestoreTransportError("FIRESTORE_TRANSPORT_UNAVAILABLE") from exc


class FirestoreAtomicDocumentBackend:
    """Linearizable-per-document backend using Firestore REST preconditions."""

    _SAFE = re.compile(r"^[A-Za-z0-9._()~-]+$")

    def __init__(
        self,
        *,
        project_id: str,
        access_token_provider: Callable[[], str],
        database_id: str = "(default)",
        collection: str = "fuse_resident_execution_v1",
        transport: JsonTransport = _default_transport,
    ) -> None:
        for label, value in (
            ("project_id", project_id),
            ("database_id", database_id),
            ("collection", collection),
        ):
            if not value or not self._SAFE.fullmatch(value):
                raise ValueError(f"FIRESTORE_IDENTIFIER_INVALID:{label}")
        self.project_id = project_id
        self.database_id = database_id
        self.collection = collection
        self._token_provider = access_token_provider
        self._transport = transport

    @staticmethod
    def _document_id(key: str) -> str:
        if not key:
            raise ValueError("ATOMIC_DOCUMENT_KEY_REQUIRED")
        return "d_" + sha256(key.encode("utf-8")).hexdigest()

    @property
    def _documents_base(self) -> str:
        project = quote(self.project_id, safe="")
        database = quote(self.database_id, safe="")
        return f"https://firestore.googleapis.com/v1/projects/{project}/databases/{database}/documents"

    def _headers(self) -> Mapping[str, str]:
        token = self._token_provider().strip()
        if not token:
            raise FirestoreTransportError("FIRESTORE_ACCESS_TOKEN_UNAVAILABLE")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def _call(
        self, method: str, url: str, body: Mapping[str, Any] | None = None
    ) -> tuple[int, Mapping[str, Any]]:
        return self._transport(method, url, self._headers(), body)

    @staticmethod
    def _body(version: int, value: Mapping[str, Any], key_sha256: str) -> dict[str, Any]:
        return {
            "fields": {
                "schema": {"stringValue": SCHEMA},
                "version": {"integerValue": str(version)},
                "payload_json": {"stringValue": canonical(dict(value))},
                "key_sha256": {"stringValue": key_sha256},
            }
        }

    @staticmethod
    def _decode(document: Mapping[str, Any]) -> tuple[int, dict[str, Any], str]:
        fields = document.get("fields")
        if not isinstance(fields, Mapping):
            raise FirestoreTransportError("FIRESTORE_DOCUMENT_FIELDS_MISSING")
        try:
            schema = fields["schema"]["stringValue"]
            version = int(fields["version"]["integerValue"])
            value = json.loads(fields["payload_json"]["stringValue"])
            update_time = str(document["updateTime"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise FirestoreTransportError("FIRESTORE_DOCUMENT_SEMANTICS_INVALID") from exc
        if schema != SCHEMA or version < 1 or not isinstance(value, dict) or not update_time:
            raise FirestoreTransportError("FIRESTORE_DOCUMENT_SEMANTICS_INVALID")
        return version, value, update_time

    def _read_document(self, key: str) -> tuple[int, dict[str, Any], str] | None:
        doc_id = self._document_id(key)
        status, body = self._call("GET", f"{self._documents_base}/{self.collection}/{doc_id}")
        if status == 404:
            return None
        if status != 200:
            raise FirestoreTransportError(f"FIRESTORE_READ_HTTP_{status}")
        return self._decode(body)

    def read(self, key: str) -> tuple[int, Mapping[str, Any]] | None:
        current = self._read_document(key)
        return None if current is None else (current[0], current[1])

    def create(self, key: str, value: Mapping[str, Any]) -> int:
        doc_id = self._document_id(key)
        key_hash = sha256(key.encode("utf-8")).hexdigest()
        url = f"{self._documents_base}/{self.collection}?" + urlencode({"documentId": doc_id})
        status, body = self._call("POST", url, self._body(1, value, key_hash))
        if status in {409, 412}:
            raise AtomicConflict("ATOMIC_CREATE_CONFLICT")
        if status != 200:
            raise FirestoreTransportError(f"FIRESTORE_CREATE_HTTP_{status}")
        version, observed, _ = self._decode(body)
        if version != 1 or observed != dict(value):
            raise FirestoreTransportError("FIRESTORE_CREATE_READBACK_MISMATCH")
        return version

    def compare_and_swap(
        self, key: str, expected_version: int, value: Mapping[str, Any]
    ) -> int:
        current = self._read_document(key)
        if current is None or current[0] != expected_version:
            actual = None if current is None else current[0]
            raise AtomicConflict(
                f"ATOMIC_CAS_CONFLICT:EXPECTED:{expected_version}:ACTUAL:{actual}"
            )
        _, _, update_time = current
        next_version = expected_version + 1
        doc_id = self._document_id(key)
        query = urlencode(
            [
                ("updateMask.fieldPaths", "schema"),
                ("updateMask.fieldPaths", "version"),
                ("updateMask.fieldPaths", "payload_json"),
                ("updateMask.fieldPaths", "key_sha256"),
                ("currentDocument.updateTime", update_time),
            ]
        )
        status, body = self._call(
            "PATCH",
            f"{self._documents_base}/{self.collection}/{doc_id}?{query}",
            self._body(next_version, value, sha256(key.encode("utf-8")).hexdigest()),
        )
        if status in {409, 412}:
            raise AtomicConflict("ATOMIC_CAS_PROVIDER_PRECONDITION_FAILED")
        if status != 200:
            raise FirestoreTransportError(f"FIRESTORE_CAS_HTTP_{status}")
        version, observed, _ = self._decode(body)
        if version != next_version or observed != dict(value):
            raise FirestoreTransportError("FIRESTORE_CAS_READBACK_MISMATCH")
        return version

    def delete_if_version(self, key: str, expected_version: int) -> bool:
        """Delete a conformance canary with provider-preconditioned cleanup."""
        current = self._read_document(key)
        if current is None:
            return False
        if current[0] != expected_version:
            raise AtomicConflict("ATOMIC_DELETE_VERSION_CONFLICT")
        doc_id = self._document_id(key)
        query = urlencode({"currentDocument.updateTime": current[2]})
        status, _ = self._call(
            "DELETE", f"{self._documents_base}/{self.collection}/{doc_id}?{query}"
        )
        if status in {409, 412}:
            raise AtomicConflict("ATOMIC_DELETE_PROVIDER_PRECONDITION_FAILED")
        if status not in {200, 204}:
            raise FirestoreTransportError(f"FIRESTORE_DELETE_HTTP_{status}")
        if self._read_document(key) is not None:
            raise FirestoreTransportError("FIRESTORE_DELETE_READBACK_MISMATCH")
        return True


__all__ = [
    "FirestoreAtomicDocumentBackend",
    "FirestoreTransportError",
    "JsonTransport",
    "SCHEMA",
    "VERSION",
]
