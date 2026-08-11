from __future__ import annotations

import hashlib
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from evidenceops_audio_v4.index import EvidenceIndex
from evidenceops_audio_v4.ledger import EvidenceLedger, utc_now
from evidenceops_audio_v4.models import HumanReview, TranscriptSegment, UnitReceipt
from evidenceops_audio_v4.service import SERVICE_CONTRACT, ServiceState, create_server


class ReadOnlyServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        self.token = "ipep-test-token-not-a-secret"
        self.token_sha256 = hashlib.sha256(self.token.encode("utf-8")).hexdigest()
        ledger = EvidenceLedger.create(
            self.workspace,
            matter="TEST-001",
            case_wall="CASE-WALL-TEST-001",
            owner="Kim Kagiso Mosiane",
        )
        source = self.root / "source.bin"
        source.write_bytes(b"synthetic-audio-fixture")
        item = ledger.ingest_file(
            source,
            item_id="UNIT-001",
            evidence_class="PRIMARY_SOURCE",
            actor="test",
        )
        ledger.register_unit_receipt(
            UnitReceipt(
                unit_id="UNIT-001",
                source_item_id="UNIT-001",
                source_sha256=item.sha256,
                provider="synthetic-asr",
                architecture_family="test-architecture",
                start_seconds=0.0,
                end_seconds=60.0,
                state="EMITTED_SEGMENTS",
                segment_count=1,
                raw_response_sha256="a" * 64,
                command_receipt_sha256="b" * 64,
                provider_exit_code=0,
                created_at=utc_now(),
                language="en",
            ),
            actor="test",
        )
        segment = TranscriptSegment(
            segment_id="SEG-001",
            unit_id="UNIT-001",
            source_item_id="UNIT-001",
            start_seconds=12.5,
            end_seconds=18.0,
            original_text="The jurisdiction point was raised.",
            source_language="en",
            provider="synthetic-asr",
            architecture_family="test-architecture",
            confidence=0.91,
            speaker_role="WITNESS",
            word_timestamps_present=True,
            raw_response_sha256="a" * 64,
        )
        ledger.register_transcript_segments([segment], actor="test")
        ledger.register_human_review(
            HumanReview(
                review_id="REV-001",
                segment_id="SEG-001",
                reviewer="human-reviewer",
                reviewed_at=utc_now(),
                state="HUMAN_VERIFIED_SOURCE_TEXT",
                verified_source_text=segment.original_text,
                verified_translation_text=None,
                speaker_role_verified=True,
                legal_entities_verified=True,
                audio_window_item_id=None,
                audio_window_sha256=None,
                notes="synthetic test review",
            ),
            actor="test",
        )
        EvidenceIndex(ledger.index_dir / "evidence-search.sqlite3").build(ledger)
        self.server = create_server(
            self.workspace,
            token_sha256=self.token_sha256,
            host="127.0.0.1",
            port=0,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address[:2]
        self.base = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, method: str, path: str, payload: dict | None = None, *, auth: bool = True):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"content-type": "application/json"}
        if auth:
            headers["authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_unauthorized_requests_fail_closed(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("GET", "/health", auth=False)
        self.assertEqual(401, caught.exception.code)

    def test_health_and_readiness_are_semantic(self) -> None:
        status, health = self.request("GET", "/health")
        self.assertEqual(200, status)
        self.assertTrue(health["ok"])
        self.assertEqual(SERVICE_CONTRACT, health["contract"])
        self.assertEqual("READ_ONLY", health["mode"])
        self.assertEqual(64, len(health["index_sha256"]))
        status, ready = self.request("GET", "/ready")
        self.assertEqual(200, status)
        self.assertTrue(ready["ready"])
        self.assertEqual("PASS", ready["accounting_state"])
        self.assertEqual(1, ready["processed_unit_count"])
        self.assertEqual(1, ready["structured_segment_count"])

    def test_search_returns_stable_provenance_citation(self) -> None:
        status, result = self.request(
            "POST",
            "/v1/search",
            {"query": "jurisdiction", "verified_only": True, "limit": 5},
        )
        self.assertEqual(200, status)
        self.assertEqual(1, result["count"])
        row = result["results"][0]
        self.assertEqual("SEG-001", row["segment_id"])
        self.assertEqual("HUMAN_VERIFIED_SOURCE_TEXT", row["review_state"])
        self.assertEqual("audio:UNIT-001#segment=SEG-001&t=12.500-18.000", row["citation"])
        self.assertNotIn("provenance", row)

    def test_unreviewed_or_verified_state_is_explicit_not_inferred(self) -> None:
        state = ServiceState.load(self.workspace, token_sha256=self.token_sha256)
        result = state.search({"query": "jurisdiction", "verified_only": False})
        self.assertEqual("HUMAN_VERIFIED_SOURCE_TEXT", result["results"][0]["review_state"])
        self.assertIn("UNREVIEWED text must not be represented as a verified quotation", result["truth_boundary"])

    def test_audit_exposes_counts_without_certification_claim(self) -> None:
        status, audit = self.request("GET", "/v1/audit")
        self.assertEqual(200, status)
        self.assertEqual("TEST-001", audit["workspace"]["matter"])
        self.assertEqual("CASE-WALL-TEST-001", audit["workspace"]["case_wall"])
        self.assertEqual(1, audit["counts"]["transcript_segments"])
        self.assertIn("not a transcript certification", audit["truth_boundary"])

    def test_search_validation_is_bounded(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("POST", "/v1/search", {"query": "jurisdiction", "limit": 51})
        self.assertEqual(400, caught.exception.code)

    def test_non_loopback_binding_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "loopback-only"):
            create_server(self.workspace, token_sha256=self.token_sha256, host="0.0.0.0", port=0)


if __name__ == "__main__":
    unittest.main()
