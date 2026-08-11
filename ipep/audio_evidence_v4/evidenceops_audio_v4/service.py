from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .hashing import sha256_file
from .index import EvidenceIndex
from .ledger import EvidenceLedger, LedgerError


SERVICE_CONTRACT = "EVIDENCEOPS_AUDIO_V4_READONLY_SERVICE_V1"
ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


@dataclass(frozen=True)
class ServiceState:
    workspace: Path
    ledger: EvidenceLedger
    index: EvidenceIndex
    token_sha256: str

    @classmethod
    def load(cls, workspace: str | Path, *, token_sha256: str) -> "ServiceState":
        root = Path(workspace).resolve()
        ledger = EvidenceLedger(root)
        if not ledger.workspace_manifest_path.is_file():
            raise LedgerError("workspace manifest is missing")
        manifest = ledger.read_workspace_manifest()
        if manifest.get("contract") != EvidenceLedger.CONTRACT:
            raise LedgerError("workspace contract mismatch")
        if len(token_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in token_sha256.lower()):
            raise ValueError("token_sha256 must be a hexadecimal SHA-256")
        index_path = ledger.index_dir / "evidence-search.sqlite3"
        if not index_path.is_file():
            raise LedgerError("search index is missing; run evidenceops-audio-v4 index first")
        return cls(
            workspace=root,
            ledger=ledger,
            index=EvidenceIndex(index_path),
            token_sha256=token_sha256.lower(),
        )

    def authorized(self, authorization: str | None) -> bool:
        if not authorization or not authorization.startswith("Bearer "):
            return False
        token = authorization.removeprefix("Bearer ").strip()
        if not token:
            return False
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return hmac.compare_digest(digest, self.token_sha256)

    def health(self) -> dict[str, Any]:
        manifest = self.ledger.read_workspace_manifest()
        return {
            "ok": True,
            "contract": SERVICE_CONTRACT,
            "mode": "READ_ONLY",
            "workspace_contract": manifest.get("contract"),
            "index_sha256": sha256_file(self.index.path),
            "truth_boundary": (
                "This service exposes authenticated discovery/search over an existing EvidenceOps Audio v4 workspace. "
                "It does not certify transcripts, identify speakers biometrically, decide admissibility, or mutate evidence."
            ),
        }

    def readiness(self) -> dict[str, Any]:
        manifest = self.ledger.read_workspace_manifest()
        accounting = self.ledger.audit_unit_accounting()
        return {
            "ready": accounting.get("state") == "PASS",
            "contract": SERVICE_CONTRACT,
            "matter": manifest.get("matter"),
            "case_wall": manifest.get("case_wall"),
            "accounting_state": accounting.get("state"),
            "processed_unit_count": accounting.get("processed_unit_count"),
            "structured_segment_count": accounting.get("structured_segment_count"),
            "index_sha256": sha256_file(self.index.path),
        }

    def audit(self) -> dict[str, Any]:
        manifest = self.ledger.read_workspace_manifest()
        accounting = self.ledger.audit_unit_accounting()
        return {
            "contract": SERVICE_CONTRACT,
            "mode": "READ_ONLY",
            "workspace": {
                "workspace_id": manifest.get("workspace_id"),
                "matter": manifest.get("matter"),
                "case_wall": manifest.get("case_wall"),
                "confidentiality": manifest.get("confidentiality"),
            },
            "unit_accounting": accounting,
            "counts": {
                "evidence_items": len(self.ledger.evidence_items()),
                "custody_events": len(self.ledger.custody_events()),
                "unit_receipts": len(self.ledger.unit_receipts()),
                "transcript_segments": len(self.ledger.transcript_segments()),
                "translations": len(self.ledger.translations()),
                "human_reviews": len(self.ledger.human_reviews()),
            },
            "index": {
                "path_name": self.index.path.name,
                "sha256": sha256_file(self.index.path),
            },
            "truth_boundary": (
                "Audit output reports machine-observable workspace state only. It is not a transcript certification, "
                "speaker-identity finding, legal conclusion, or admissibility ruling."
            ),
        }

    def search(self, payload: dict[str, Any]) -> dict[str, Any]:
        query = payload.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-blank string")
        if len(query) > 500:
            raise ValueError("query exceeds 500 characters")
        limit = payload.get("limit", 20)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
            raise ValueError("limit must be an integer from 1 to 50")
        language = payload.get("language")
        if language is not None and (not isinstance(language, str) or not language.strip() or len(language) > 32):
            raise ValueError("language must be a short non-blank string")
        verified_only = payload.get("verified_only", False)
        if not isinstance(verified_only, bool):
            raise ValueError("verified_only must be boolean")

        raw_results = self.index.search(
            query.strip(),
            limit=limit,
            language=language.strip() if isinstance(language, str) else None,
            verified_only=verified_only,
        )
        results = []
        for row in raw_results:
            results.append(
                {
                    "segment_id": row["segment_id"],
                    "source_item_id": row["source_item_id"],
                    "start_seconds": row["start_seconds"],
                    "end_seconds": row["end_seconds"],
                    "speaker_role": row.get("speaker_role"),
                    "source_language": row["source_language"],
                    "target_language": row.get("target_language"),
                    "original_text": row["original_text"],
                    "translated_text": row.get("translated_text"),
                    "provider": row["provider"],
                    "architecture_family": row["architecture_family"],
                    "confidence": row.get("confidence"),
                    "review_state": row["review_state"],
                    "audio_window_sha256": row.get("audio_window_sha256"),
                    "source_sha256": row.get("source_sha256"),
                    "citation": row["citation"],
                }
            )
        return {
            "contract": SERVICE_CONTRACT,
            "query": query.strip(),
            "verified_only": verified_only,
            "count": len(results),
            "results": results,
            "truth_boundary": (
                "Search results are discovery aids and inherit the review state shown per result. "
                "UNREVIEWED text must not be represented as a verified quotation."
            ),
        }


class _Handler(BaseHTTPRequestHandler):
    server_version = "EvidenceOpsAudioV4ReadOnly/1.0"

    @property
    def state(self) -> ServiceState:
        return self.server.service_state  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: object) -> None:
        return

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _require_auth(self) -> bool:
        if self.state.authorized(self.headers.get("authorization")):
            return True
        self._json(401, {"error": "unauthorized", "contract": SERVICE_CONTRACT})
        return False

    def _read_payload(self) -> dict[str, Any]:
        content_length = self.headers.get("content-length")
        if content_length is None:
            raise ValueError("content-length required")
        size = int(content_length)
        if size < 0 or size > 32_768:
            raise ValueError("request body too large")
        raw = self.rfile.read(size)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def do_GET(self) -> None:  # noqa: N802
        if not self._require_auth():
            return
        try:
            if self.path == "/health":
                self._json(200, self.state.health())
            elif self.path == "/ready":
                payload = self.state.readiness()
                self._json(200 if payload["ready"] else 503, payload)
            elif self.path == "/v1/audit":
                self._json(200, self.state.audit())
            else:
                self._json(404, {"error": "not_found", "contract": SERVICE_CONTRACT})
        except (LedgerError, OSError, ValueError) as exc:
            self._json(500, {"error": "service_state_error", "detail": str(exc), "contract": SERVICE_CONTRACT})

    def do_POST(self) -> None:  # noqa: N802
        if not self._require_auth():
            return
        if self.path != "/v1/search":
            self._json(404, {"error": "not_found", "contract": SERVICE_CONTRACT})
            return
        try:
            self._json(200, self.state.search(self._read_payload()))
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"error": "invalid_request", "detail": str(exc), "contract": SERVICE_CONTRACT})
        except (LedgerError, OSError) as exc:
            self._json(500, {"error": "service_state_error", "detail": str(exc), "contract": SERVICE_CONTRACT})


def create_server(
    workspace: str | Path,
    *,
    token_sha256: str,
    host: str = "127.0.0.1",
    port: int = 0,
) -> ThreadingHTTPServer:
    if host not in ALLOWED_HOSTS:
        raise ValueError("read-only service is loopback-only; use a provider auth proxy before non-loopback exposure")
    if not 0 <= int(port) <= 65535:
        raise ValueError("port out of range")
    state = ServiceState.load(workspace, token_sha256=token_sha256)
    server = ThreadingHTTPServer((host, int(port)), _Handler)
    server.service_state = state  # type: ignore[attr-defined]
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EvidenceOps Audio v4 authenticated read-only search service")
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    token_sha256 = os.environ.get("IPEP_SERVICE_TOKEN_SHA256", "").strip().lower()
    if not token_sha256:
        parser.error("IPEP_SERVICE_TOKEN_SHA256 is required")
    server = create_server(args.workspace, token_sha256=token_sha256, host=args.host, port=args.port)
    print(
        json.dumps(
            {
                "contract": SERVICE_CONTRACT,
                "state": "LISTENING",
                "host": args.host,
                "port": server.server_address[1],
                "mode": "READ_ONLY",
                "truth_boundary": "Local loopback runtime only; provider deployment is a separate proof gate.",
            },
            sort_keys=True,
        )
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
