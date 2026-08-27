from __future__ import annotations

import argparse
import base64
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Protocol


EGRESS_SCHEMA = "CHATBRIDGE-OMEGA49-EDGE-EGRESS-1"
NATIVE_ACK_SCHEMA = "SOVARA-BEF-NATIVE-ACK-1"
MAX_MESSAGE_BYTES = 1_000_000
DEFAULT_HOST_NAME = "com.sovara.bef_edge"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(value: Any) -> str:
    raw = value.encode("utf-8") if isinstance(value, str) else _canonical_json(value).encode("utf-8")
    return _sha256_bytes(raw)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _spool_root() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_STATE_HOME")
    if not base:
        base = str(Path.home() / ".local" / "state")
    return Path(base) / "SOVARA" / "BEF" / "ChatBridgeSpool"


def validate_envelope(envelope: Mapping[str, Any]) -> Dict[str, Any]:
    if str(envelope.get("schema", "")) != EGRESS_SCHEMA:
        raise ValueError("SCHEMA_MISMATCH")
    conversation = str(envelope.get("conversationKey", "")).strip()
    namespace = str(envelope.get("namespaceKey", "")).strip()
    if not conversation:
        raise ValueError("CONVERSATION_REQUIRED")
    if not namespace:
        raise ValueError("NAMESPACE_REQUIRED")
    events = envelope.get("events")
    if not isinstance(events, list) or not events or len(events) > 100:
        raise ValueError("EVENT_COUNT_INVALID")
    raw = _canonical_json(envelope).encode("utf-8")
    if len(raw) > MAX_MESSAGE_BYTES:
        raise ValueError("ENVELOPE_TOO_LARGE")
    claimed_hash = str(envelope.get("envelopeSha256", ""))
    if len(claimed_hash) != 64:
        raise ValueError("ENVELOPE_HASH_MISSING")
    unhashed = dict(envelope)
    unhashed.pop("envelopeSha256", None)
    if _sha256(unhashed) != claimed_hash:
        raise ValueError("ENVELOPE_HASH_MISMATCH")
    if bool((envelope.get("manifest") or {}).get("exactContextComplete", False)):
        raise ValueError("RENDERED_EGRESS_CANNOT_CLAIM_PROVIDER_NATIVE_EXACT")
    previous = int(envelope.get("fromAppendSequence", 0) or 0) - 1
    for event in events:
        if not isinstance(event, Mapping):
            raise ValueError("EVENT_NOT_OBJECT")
        append = int(event.get("appendSequence", 0) or 0)
        if append <= previous:
            raise ValueError("EVENT_APPEND_ORDER_INVALID")
        previous = append
        for field in ("contentHash", "eventHash"):
            if len(str(event.get(field, ""))) != 64:
                raise ValueError("EVENT_HASH_INVALID")
        for artifact in event.get("artifacts") or []:
            locator = str((artifact or {}).get("locator", ""))
            if "?" in locator or "#" in locator:
                raise ValueError("ARTIFACT_LOCATOR_NOT_REDACTED")
    if int(events[0].get("appendSequence", 0)) != int(envelope.get("fromAppendSequence", 0)):
        raise ValueError("FIRST_APPEND_MISMATCH")
    if int(events[-1].get("appendSequence", 0)) != int(envelope.get("toAppendSequence", 0)):
        raise ValueError("LAST_APPEND_MISMATCH")
    return {
        "conversationKey": conversation,
        "namespaceKey": namespace,
        "envelopeSha256": claimed_hash,
        "fromAppendSequence": int(envelope.get("fromAppendSequence", 0)),
        "toAppendSequence": int(envelope.get("toAppendSequence", 0)),
        "eventCount": len(events),
    }


class Protector(Protocol):
    def protect(self, data: bytes) -> bytes: ...
    def unprotect(self, data: bytes) -> bytes: ...


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes) -> tuple[_DATA_BLOB, Any]:
    buffer = ctypes.create_string_buffer(data)
    return _DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


class WindowsDpapiProtector:
    """Encrypt/decrypt for the current Windows user using CryptProtectData."""

    CRYPTPROTECT_UI_FORBIDDEN = 0x1

    def __init__(self) -> None:
        if os.name != "nt":
            raise RuntimeError("WINDOWS_DPAPI_REQUIRED")
        self.crypt32 = ctypes.windll.crypt32
        self.kernel32 = ctypes.windll.kernel32

    def protect(self, data: bytes) -> bytes:
        in_blob, in_buffer = _blob(data)
        out_blob = _DATA_BLOB()
        ok = self.crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            "SOVARA-BEF-CHATBRIDGE",
            None,
            None,
            None,
            self.CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(out_blob),
        )
        _ = in_buffer
        if not ok:
            raise ctypes.WinError()
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            self.kernel32.LocalFree(out_blob.pbData)

    def unprotect(self, data: bytes) -> bytes:
        in_blob, in_buffer = _blob(data)
        out_blob = _DATA_BLOB()
        ok = self.crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            self.CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(out_blob),
        )
        _ = in_buffer
        if not ok:
            raise ctypes.WinError()
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            self.kernel32.LocalFree(out_blob.pbData)


class TestProtector:
    """Deterministic non-production protector used only by source tests."""

    prefix = b"SOVARA_TEST_PROTECTED_V1\x00"

    def protect(self, data: bytes) -> bytes:
        return self.prefix + base64.b64encode(data[::-1])

    def unprotect(self, data: bytes) -> bytes:
        if not data.startswith(self.prefix):
            raise ValueError("TEST_PROTECTOR_PREFIX_MISSING")
        return base64.b64decode(data[len(self.prefix):])[::-1]


class EncryptedSpool:
    def __init__(self, root: Path, protector: Protector) -> None:
        self.root = Path(root)
        self.protector = protector
        self.envelopes = self.root / "envelopes"
        self.receipts = self.root / "receipts"
        self.envelopes.mkdir(parents=True, exist_ok=True)
        self.receipts.mkdir(parents=True, exist_ok=True)

    def store(self, envelope: Mapping[str, Any]) -> Dict[str, Any]:
        verified = validate_envelope(envelope)
        digest = verified["envelopeSha256"]
        payload = _canonical_json(envelope).encode("utf-8")
        encrypted_path = self.envelopes / f"{digest}.dpapi"
        receipt_path = self.receipts / f"{digest}.json"
        reused = encrypted_path.exists() and receipt_path.exists()
        if not reused:
            encrypted = self.protector.protect(payload)
            tmp = encrypted_path.with_suffix(".tmp")
            tmp.write_bytes(encrypted)
            os.replace(tmp, encrypted_path)
            manifest = envelope.get("manifest") or {}
            source = envelope.get("source") or {}
            receipt = {
                "schema": "SOVARA-BEF-ENCRYPTED-SPOOL-RECEIPT-1",
                "receiptId": f"bef-spool-{digest[:20]}",
                "conversationKey": verified["conversationKey"],
                "namespaceKey": verified["namespaceKey"],
                "envelopeSha256": digest,
                "fromAppendSequence": verified["fromAppendSequence"],
                "toAppendSequence": verified["toAppendSequence"],
                "eventCount": verified["eventCount"],
                "sourceProvider": str(source.get("provider", "")),
                "exactRenderedTranscriptComplete": bool(manifest.get("exactRenderedTranscriptComplete", False)),
                "providerNativeComplete": False,
                "integrityState": str(manifest.get("integrityState", "")),
                "firstSourceSequence": manifest.get("firstSourceSequence"),
                "lastSourceSequence": manifest.get("lastSourceSequence"),
                "latestRenderedMessageCount": int(manifest.get("latestRenderedMessageCount", 0) or 0),
                "capturedEventCount": int(manifest.get("capturedEventCount", 0) or 0),
                "missingRanges": manifest.get("missingRanges", []),
                "unresolvedArtifacts": manifest.get("unresolvedArtifacts", []),
                "chainHeadSha256": str(manifest.get("chainHeadSha256", "")),
                "storedEncrypted": True,
                "encryptedObject": encrypted_path.name,
                "observedAt": _now(),
            }
            tmp_receipt = receipt_path.with_suffix(".tmp")
            tmp_receipt.write_text(_canonical_json(receipt), encoding="utf-8")
            os.replace(tmp_receipt, receipt_path)
        else:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        return {
            "schema": NATIVE_ACK_SCHEMA,
            "ok": True,
            "state": "ENCRYPTED_SPOOL_REUSED" if reused else "ENCRYPTED_SPOOL_WRITTEN",
            "receiptId": receipt["receiptId"],
            "envelopeSha256": digest,
            "toAppendSequence": verified["toAppendSequence"],
            "storedEncrypted": True,
            "observedAt": receipt["observedAt"],
        }

    def load(self, envelope_sha256: str) -> Dict[str, Any]:
        digest = str(envelope_sha256)
        encrypted = (self.envelopes / f"{digest}.dpapi").read_bytes()
        raw = self.protector.unprotect(encrypted)
        if _sha256(json.loads(raw.decode("utf-8")) | {}) != digest:
            # The envelope hash excludes its own envelopeSha256 field, so verify via contract.
            payload = json.loads(raw.decode("utf-8"))
            validate_envelope(payload)
            return payload
        return json.loads(raw.decode("utf-8"))


def _read_native_message(stream) -> Dict[str, Any]:
    header = stream.read(4)
    if len(header) != 4:
        raise EOFError("NATIVE_MESSAGE_HEADER_MISSING")
    length = struct.unpack("<I", header)[0]
    if length < 2 or length > MAX_MESSAGE_BYTES:
        raise ValueError("NATIVE_MESSAGE_LENGTH_INVALID")
    body = stream.read(length)
    if len(body) != length:
        raise EOFError("NATIVE_MESSAGE_TRUNCATED")
    return json.loads(body.decode("utf-8"))


def _write_native_message(stream, value: Mapping[str, Any]) -> None:
    body = _canonical_json(value).encode("utf-8")
    stream.write(struct.pack("<I", len(body)))
    stream.write(body)
    stream.flush()


def run_once(in_stream, out_stream, *, spool: EncryptedSpool) -> None:
    try:
        envelope = _read_native_message(in_stream)
        response = spool.store(envelope)
    except Exception as exc:
        response = {
            "schema": NATIVE_ACK_SCHEMA,
            "ok": False,
            "state": type(exc).__name__,
            "error": str(exc)[:400],
            "observedAt": _now(),
        }
    _write_native_message(out_stream, response)


def _self_test() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        protector = TestProtector()
        spool = EncryptedSpool(Path(tmpdir), protector)
        envelope = {
            "schema": EGRESS_SCHEMA,
            "version": "1.0",
            "conversationKey": "self-test-chat",
            "namespaceKey": "self-test",
            "source": {"provider": "CHATGPT_RENDERED_DOM", "urlSha256": "a" * 64},
            "fromAppendSequence": 1,
            "toAppendSequence": 1,
            "events": [{
                "appendSequence": 1,
                "content": "SENSITIVE_SELF_TEST_PAYLOAD",
                "contentHash": "b" * 64,
                "eventHash": "c" * 64,
                "artifacts": []
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
                "unresolvedArtifacts": []
            },
            "reason": "SELF_TEST",
            "createdAt": _now(),
        }
        unhashed = dict(envelope)
        envelope["envelopeSha256"] = _sha256(unhashed)
        ack = spool.store(envelope)
        encrypted = next((Path(tmpdir) / "envelopes").glob("*.dpapi")).read_bytes()
        if b"SENSITIVE_SELF_TEST_PAYLOAD" in encrypted:
            raise AssertionError("PLAINTEXT_LEAK_IN_ENCRYPTED_SPOOL")
        loaded = spool.load(envelope["envelopeSha256"])
        if loaded["events"][0]["content"] != "SENSITIVE_SELF_TEST_PAYLOAD":
            raise AssertionError("ENCRYPTED_ROUNDTRIP_FAILED")
        if not ack.get("storedEncrypted"):
            raise AssertionError("ENCRYPTED_ACK_REQUIRED")
    print("BEF_NATIVE_HOST_SELF_TEST_PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--spool-root")
    args = parser.parse_args(argv)
    if args.self_test:
        return _self_test()
    protector = WindowsDpapiProtector()
    root = Path(args.spool_root) if args.spool_root else _spool_root()
    spool = EncryptedSpool(root, protector)
    run_once(sys.stdin.buffer, sys.stdout.buffer, spool=spool)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
