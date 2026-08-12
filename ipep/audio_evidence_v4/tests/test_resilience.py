from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from evidenceops_audio_v4.index import EvidenceIndex
from evidenceops_audio_v4.ledger import EvidenceLedger, utc_now
from evidenceops_audio_v4.models import TranscriptSegment, UnitReceipt
from evidenceops_audio_v4.resilience import probe_workspace


TOKEN_SHA = hashlib.sha256(b"patch-test-token").hexdigest()


def make_workspace(root: Path) -> Path:
    workspace = root / "workspace"
    ledger = EvidenceLedger.create(
        workspace,
        matter="PATCH-TEST",
        case_wall="CASE-WALL-PATCH-TEST",
        owner="Kim Kagiso Mosiane",
    )
    source = root / "source.bin"
    source.write_bytes(b"patch-synthetic-audio")
    item = ledger.ingest_file(source, item_id="UNIT-001", evidence_class="PRIMARY_SOURCE", actor="patch-test")
    ledger.register_unit_receipt(
        UnitReceipt(
            unit_id="UNIT-001",
            source_item_id="UNIT-001",
            source_sha256=item.sha256,
            provider="synthetic-asr",
            architecture_family="patch-test",
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
        actor="patch-test",
    )
    ledger.register_transcript_segments(
        [
            TranscriptSegment(
                segment_id="SEG-001",
                unit_id="UNIT-001",
                source_item_id="UNIT-001",
                start_seconds=1.0,
                end_seconds=3.0,
                original_text="Synthetic resilience evidence.",
                source_language="en",
                provider="synthetic-asr",
                architecture_family="patch-test",
                confidence=0.9,
            )
        ],
        actor="patch-test",
    )
    EvidenceIndex(ledger.index_dir / "evidence-search.sqlite3").build(ledger)
    return workspace


class PatchResilienceTests(unittest.TestCase):
    def test_resilience_probe_passes_and_restart_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = make_workspace(Path(tmp))
            receipt = probe_workspace(workspace, token_sha256=TOKEN_SHA)
            self.assertEqual("PASS", receipt.state)
            self.assertTrue(receipt.restart_stable)
            self.assertEqual("PASS", receipt.accounting_state)
            self.assertEqual("PASS", receipt.custody_state)
            self.assertTrue(receipt.index_sha256 and len(receipt.index_sha256) == 64)

    def test_missing_index_fails_closed_without_rebuilding_silently(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = make_workspace(Path(tmp))
            (workspace / "index" / "evidence-search.sqlite3").unlink()
            receipt = probe_workspace(workspace, token_sha256=TOKEN_SHA)
            self.assertEqual("FAIL", receipt.state)
            self.assertTrue(any(item.startswith("LOAD_OR_STATE_FAILURE:LedgerError") for item in receipt.failures))
            self.assertFalse(receipt.restart_stable)

    def test_tampered_custody_chain_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = make_workspace(Path(tmp))
            custody = workspace / "ledger" / "custody_events.jsonl"
            lines = custody.read_text(encoding="utf-8").splitlines()
            event = json.loads(lines[-1])
            event["action"] = "TAMPERED_ACTION"
            lines[-1] = json.dumps(event, sort_keys=True)
            custody.write_text("\n".join(lines) + "\n", encoding="utf-8")
            receipt = probe_workspace(workspace, token_sha256=TOKEN_SHA)
            self.assertEqual("FAIL", receipt.state)
            self.assertIn("CUSTODY_CHAIN_FAILED", receipt.failures)

    def test_bad_token_digest_configuration_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = make_workspace(Path(tmp))
            receipt = probe_workspace(workspace, token_sha256="not-a-digest")
            self.assertEqual("FAIL", receipt.state)
            self.assertTrue(any(item.startswith("LOAD_OR_STATE_FAILURE:ValueError") for item in receipt.failures))


if __name__ == "__main__":
    unittest.main()
