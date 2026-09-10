from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse
import unittest

from federation.firestore_atomic_document_backend_v1 import (
    FirestoreAtomicDocumentBackend,
    FirestoreTransportError,
)
from federation.resident_execution_substrate_v1 import AtomicConflict, ProviderConformanceKit


class FakeFirestoreTransport:
    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}
        self.clock = 0
        self.conflict_on_next_patch = False
        self.authorization_headers: list[str] = []

    def _stamp(self) -> str:
        self.clock += 1
        return f"2026-09-11T00:00:{self.clock:02d}.000000Z"

    def __call__(self, method, url, headers, body):
        self.authorization_headers.append(headers.get("Authorization", ""))
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        if method == "POST":
            doc_id = query["documentId"][0]
            if doc_id in self.docs:
                return 409, {"error": {"status": "ALREADY_EXISTS"}}
            doc = {**body, "updateTime": self._stamp()}
            self.docs[doc_id] = doc
            return 200, doc
        doc_id = parsed.path.rsplit("/", 1)[-1]
        if method == "GET":
            return (200, self.docs[doc_id]) if doc_id in self.docs else (404, {})
        if method == "PATCH":
            if self.conflict_on_next_patch:
                self.conflict_on_next_patch = False
                return 412, {"error": {"status": "FAILED_PRECONDITION"}}
            current = self.docs.get(doc_id)
            expected = query.get("currentDocument.updateTime", [""])[0]
            if current is None or current["updateTime"] != expected:
                return 412, {"error": {"status": "FAILED_PRECONDITION"}}
            doc = {**body, "updateTime": self._stamp()}
            self.docs[doc_id] = doc
            return 200, doc
        if method == "DELETE":
            current = self.docs.get(doc_id)
            expected = query.get("currentDocument.updateTime", [""])[0]
            if current is None:
                return 404, {}
            if current["updateTime"] != expected:
                return 412, {"error": {"status": "FAILED_PRECONDITION"}}
            del self.docs[doc_id]
            return 200, {}
        return 405, {}


def factory(transport=None, token="token-private"):
    selected = transport or FakeFirestoreTransport()
    return FirestoreAtomicDocumentBackend(
        project_id="sov-hybrid-suite",
        access_token_provider=lambda: token,
        transport=selected,
    )


def test_provider_conformance_uses_firestore_update_time_cas():
    transport = FakeFirestoreTransport()
    receipt = ProviderConformanceKit().run(lambda: factory(transport))
    assert receipt.state == "CONFORMANT_LOCAL_COURT"
    assert receipt.checks[-1] == "READBACK_EXACT"


def test_provider_precondition_conflict_fails_closed():
    transport = FakeFirestoreTransport()
    backend = factory(transport)
    backend.create("k", {"value": 1})
    transport.conflict_on_next_patch = True
    with unittest.TestCase().assertRaisesRegex(AtomicConflict, "PROVIDER_PRECONDITION"):
        backend.compare_and_swap("k", 1, {"value": 2})


def test_cleanup_is_version_gated_and_read_back_absent():
    transport = FakeFirestoreTransport()
    backend = factory(transport)
    backend.create("canary", {"value": "bounded"})
    with unittest.TestCase().assertRaisesRegex(AtomicConflict, "DELETE_VERSION_CONFLICT"):
        backend.delete_if_version("canary", 2)
    assert backend.delete_if_version("canary", 1) is True
    assert backend.read("canary") is None


def test_payload_round_trips_as_canonical_json():
    transport = FakeFirestoreTransport()
    backend = factory(transport)
    payload = {"z": [2, 1], "a": {"enabled": True}}
    backend.create("roundtrip", payload)
    assert backend.read("roundtrip") == (1, payload)
    stored = next(iter(transport.docs.values()))
    assert json.loads(stored["fields"]["payload_json"]["stringValue"]) == payload


def test_tokens_are_runtime_only_and_errors_are_redacted():
    class Denied(FakeFirestoreTransport):
        def __call__(self, method, url, headers, body):
            self.authorization_headers.append(headers["Authorization"])
            return 403, {"error": {"message": "provider detail"}}

    transport = Denied()
    backend = factory(transport, token="sensitive-runtime-token")
    with unittest.TestCase().assertRaises(FirestoreTransportError) as exc:
        backend.read("private")
    assert "sensitive-runtime-token" not in str(exc.exception)
    assert transport.authorization_headers == ["Bearer sensitive-runtime-token"]


def test_invalid_identifiers_and_empty_keys_fail_before_transport():
    with unittest.TestCase().assertRaisesRegex(ValueError, "project_id"):
        FirestoreAtomicDocumentBackend(
            project_id="bad/project",
            access_token_provider=lambda: "token",
        )
    with unittest.TestCase().assertRaisesRegex(ValueError, "KEY_REQUIRED"):
        factory().read("")


class FirestoreAtomicBackendUnittestBridge(unittest.TestCase):
    test_provider_conformance_uses_firestore_update_time_cas = staticmethod(
        test_provider_conformance_uses_firestore_update_time_cas
    )
    test_provider_precondition_conflict_fails_closed = staticmethod(
        test_provider_precondition_conflict_fails_closed
    )
    test_cleanup_is_version_gated_and_read_back_absent = staticmethod(
        test_cleanup_is_version_gated_and_read_back_absent
    )
    test_payload_round_trips_as_canonical_json = staticmethod(
        test_payload_round_trips_as_canonical_json
    )
    test_tokens_are_runtime_only_and_errors_are_redacted = staticmethod(
        test_tokens_are_runtime_only_and_errors_are_redacted
    )
    test_invalid_identifiers_and_empty_keys_fail_before_transport = staticmethod(
        test_invalid_identifiers_and_empty_keys_fail_before_transport
    )
