from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from bef_native_host import EncryptedSpool, WindowsDpapiProtector, _spool_root


class BefSpoolReader:
    """Same-user read adapter for the BEF encrypted provenance spool."""

    def __init__(self, root: Optional[Path] = None, protector=None) -> None:
        self.root = Path(root) if root else _spool_root()
        self.spool = EncryptedSpool(
            self.root,
            protector if protector is not None else WindowsDpapiProtector(),
        )

    def receipts(self, conversation_key: Optional[str] = None) -> list[Dict[str, Any]]:
        rows = []
        for path in sorted((self.root / "receipts").glob("*.json")):
            row = json.loads(path.read_text(encoding="utf-8"))
            if conversation_key and str(row.get("conversationKey", "")) != conversation_key:
                continue
            rows.append(row)
        rows.sort(
            key=lambda row: (
                int(row.get("toAppendSequence", 0) or 0),
                str(row.get("observedAt", "")),
            )
        )
        return rows

    def envelopes(self, conversation_key: str) -> Iterable[Dict[str, Any]]:
        for receipt in self.receipts(conversation_key):
            yield self.spool.load(str(receipt["envelopeSha256"]))

    def latest_receipt(self, conversation_key: str) -> Optional[Dict[str, Any]]:
        rows = self.receipts(conversation_key)
        return rows[-1] if rows else None

    def observable_scope_evidence(self, conversation_key: str) -> Optional[Dict[str, Any]]:
        receipt = self.latest_receipt(conversation_key)
        if not receipt:
            return None
        envelope = self.spool.load(str(receipt["envelopeSha256"]))
        manifest = envelope.get("manifest") or {}
        source = envelope.get("source") or {}
        return {
            "capture_scope": "RENDERED_DOM",
            "source_provider": str(source.get("provider", "CHATGPT_RENDERED_DOM")),
            "provider_native_complete": False,
            "exact_rendered_transcript_complete": bool(
                manifest.get("exactRenderedTranscriptComplete", False)
            ),
            "integrity_state": str(manifest.get("integrityState", "")),
            "missing_ranges": manifest.get("missingRanges", []),
            "unresolved_artifacts": manifest.get("unresolvedArtifacts", []),
            "first_source_sequence": manifest.get("firstSourceSequence"),
            "last_source_sequence": manifest.get("lastSourceSequence"),
            "latest_rendered_message_count": int(
                manifest.get("latestRenderedMessageCount", 0) or 0
            ),
            "captured_event_count": int(manifest.get("capturedEventCount", 0) or 0),
            "chain_head_sha256": str(manifest.get("chainHeadSha256", "")),
            "evidence_fingerprint": str(receipt.get("envelopeSha256", "")),
            "spool_receipt_id": str(receipt.get("receiptId", "")),
            "stored_encrypted": bool(receipt.get("storedEncrypted", False)),
            "truth_boundary": (
                "FULL_OBSERVABLE_RENDERED_CHAT_EVIDENCE_ONLY / "
                "PROVIDER_NATIVE_HIDDEN_EVENTS_NOT_INFERRED"
            ),
        }


__all__ = ["BefSpoolReader"]
