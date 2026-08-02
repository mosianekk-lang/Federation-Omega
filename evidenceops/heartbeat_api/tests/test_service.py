from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from evidenceops.heartbeat_api.service import create_app

from .helpers import ingest_request, runtime


class ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app(runtime()))
        self.headers = {"X-EvidenceOps-Internal-Auth": "T" * 32}

    def test_health_is_minimal_and_internal_routes_require_auth(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"ok", "service_code", "schema_version"})
        denied = self.client.get("/v1/status")
        self.assertEqual(denied.status_code, 401)
        self.assertNotIn("T" * 32, denied.text)

    def test_ready_status_ingest_fetch_and_readback(self) -> None:
        self.assertEqual(self.client.get("/ready", headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get("/v1/status", headers=self.headers).json()["authority_ceiling"], "A0")
        body = ingest_request().model_dump(mode="json")
        ingested = self.client.post("/v1/ingest", headers=self.headers, json=body)
        self.assertEqual(ingested.status_code, 200, ingested.text)
        result = ingested.json()
        fetched = self.client.get("/v1/resources/" + result["resource_id"], headers=self.headers)
        self.assertEqual(fetched.status_code, 200)
        readback = self.client.get("/v1/readback/" + body["idempotency_hash"], headers=self.headers)
        self.assertEqual(readback.status_code, 200)
        self.assertTrue(readback.json()["verified"])

    def test_invalid_body_is_sanitized(self) -> None:
        body = ingest_request().model_dump(mode="json")
        body["content"] = "do-not-reflect-this-value"
        response = self.client.post("/v1/ingest", headers=self.headers, json=body)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json(), {"error_code": "METADATA_REQUEST_REJECTED"})
        self.assertNotIn("do-not-reflect-this-value", response.text)

    def test_oversized_body_is_rejected_before_schema_processing(self) -> None:
        response = self.client.post(
            "/v1/ingest",
            headers={**self.headers, "Content-Type": "application/json"},
            content=b"x" * (64 * 1024 + 1),
        )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json(), {"error_code": "REQUEST_BODY_TOO_LARGE"})


if __name__ == "__main__":
    unittest.main()
