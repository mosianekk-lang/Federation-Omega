from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import struct
import sys
import tempfile

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from bef_native_host import (  # noqa: E402
    EGRESS_SCHEMA,
    EncryptedSpool,
    TestProtector,
    _canonical_json,
    _sha256,
    run_once,
    validate_envelope,
)
from bef_spool import BefSpoolReader  # noqa: E402


def envelope(content: str = "private rendered content"):
    value = {
        "schema": EGRESS_SCHEMA,
        "version": "1.0",
        "conversationKey": "chat-1",
        "namespaceKey": "sovara",
        "source": {
            "provider": "CHATGPT_RENDERED_DOM",
            "pathId": "rendered-dom-companion",
            "title": "Design chat",
            "urlSha256": "a" * 64,
        },
        "fromAppendSequence": 1,
        "toAppendSequence": 1,
        "events": [{
            "appendSequence": 1,
            "sourceSequence": 1,
            "eventType": "MESSAGE",
            "content": content,
            "contentHash": "b" * 64,
            "eventHash": "c" * 64,
            "artifacts": [],
        }],
        "manifest": {
            "exactRenderedTranscriptComplete": True,
            "exactContextComplete": False,
            "integrityState": "HASH_CHAIN_VERIFIED",
            "firstSourceSequence": 1,
            "lastSourceSequence": 1,
            "latestRenderedMessageCount": 1,
            "capturedEventCount": 1,
            "missingRanges": [],
            "unresolvedArtifacts": [],
            "chainHeadSha256": "c" * 64,
        },
        "reason": "TEST",
        "createdAt": "2026-08-27T00:00:00Z",
    }
    value["envelopeSha256"] = _sha256(value)
    return value


def test_encrypted_spool_is_idempotent_and_plaintext_free():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        spool = EncryptedSpool(root, TestProtector())
        value = envelope("HIGHLY_PRIVATE_DESIGN_TEXT")
        first = spool.store(value)
        second = spool.store(value)
        assert first["state"] == "ENCRYPTED_SPOOL_WRITTEN"
        assert second["state"] == "ENCRYPTED_SPOOL_REUSED"
        encrypted = (root / "envelopes" / f"{value['envelopeSha256']}.dpapi").read_bytes()
        assert b"HIGHLY_PRIVATE_DESIGN_TEXT" not in encrypted
        assert spool.load(value["envelopeSha256"])["events"][0]["content"] == "HIGHLY_PRIVATE_DESIGN_TEXT"


def test_spool_reader_emits_observable_scope_evidence_not_provider_native():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        protector = TestProtector()
        spool = EncryptedSpool(root, protector)
        value = envelope()
        spool.store(value)
        reader = BefSpoolReader(root, protector=protector)
        evidence = reader.observable_scope_evidence("chat-1")
        assert evidence is not None
        assert evidence["capture_scope"] == "RENDERED_DOM"
        assert evidence["exact_rendered_transcript_complete"] is True
        assert evidence["provider_native_complete"] is False
        assert evidence["stored_encrypted"] is True
        assert evidence["evidence_fingerprint"] == value["envelopeSha256"]


def test_native_framing_returns_hash_bound_ack():
    with tempfile.TemporaryDirectory() as tmp:
        value = envelope()
        raw = _canonical_json(value).encode("utf-8")
        source = BytesIO(struct.pack("<I", len(raw)) + raw)
        target = BytesIO()
        spool = EncryptedSpool(Path(tmp), TestProtector())
        run_once(source, target, spool=spool)
        target.seek(0)
        size = struct.unpack("<I", target.read(4))[0]
        ack = json.loads(target.read(size).decode("utf-8"))
        assert ack["ok"] is True
        assert ack["envelopeSha256"] == value["envelopeSha256"]
        assert ack["toAppendSequence"] == 1
        assert ack["storedEncrypted"] is True


def test_native_validation_rejects_provider_native_claim_and_signed_locator():
    value = envelope()
    value["manifest"]["exactContextComplete"] = True
    value["envelopeSha256"] = _sha256({k: v for k, v in value.items() if k != "envelopeSha256"})
    try:
        validate_envelope(value)
        raise AssertionError("provider-native claim should be rejected")
    except ValueError as exc:
        assert str(exc) == "RENDERED_EGRESS_CANNOT_CLAIM_PROVIDER_NATIVE_EXACT"

    value = envelope()
    value["events"][0]["artifacts"] = [{"locator": "https://x.example/a?token=bad"}]
    value["envelopeSha256"] = _sha256({k: v for k, v in value.items() if k != "envelopeSha256"})
    try:
        validate_envelope(value)
        raise AssertionError("signed locator should be rejected")
    except ValueError as exc:
        assert str(exc) == "ARTIFACT_LOCATOR_NOT_REDACTED"
