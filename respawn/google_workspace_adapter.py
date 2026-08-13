from __future__ import annotations

import io
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class GoogleWorkspaceBibleAdapter:
    """Provider adapter for the private Federation Bible Fabric.

    Uses Application Default Credentials / workload identity. No service-account
    key files are required or expected.
    """

    def __init__(self) -> None:
        self.sync_bus_id = os.getenv("FEDERATION_SYNC_BUS_SHEET_ID", "").strip()
        self.provider_writes = os.getenv("FEDERATION_PROVIDER_WRITES", "false").lower() == "true"
        if not self.sync_bus_id:
            raise RuntimeError("FEDERATION_SYNC_BUS_SHEET_ID is not configured")
        credentials, _ = google.auth.default(scopes=SCOPES)
        self.drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
        self.sheets = build("sheets", "v4", credentials=credentials, cache_discovery=False)

    @classmethod
    def configured(cls) -> bool:
        return bool(os.getenv("FEDERATION_SYNC_BUS_SHEET_ID", "").strip())

    def values(self, a1_range: str) -> List[List[str]]:
        result = self.sheets.spreadsheets().values().get(
            spreadsheetId=self.sync_bus_id,
            range=a1_range,
            valueRenderOption="FORMATTED_VALUE",
        ).execute()
        return result.get("values", [])

    @staticmethod
    def rows_as_dicts(values: List[List[str]]) -> List[Dict[str, str]]:
        if not values:
            return []
        headers = values[0]
        return [
            {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
            for row in values[1:]
        ]

    def system_record(self, system: str) -> Optional[Dict[str, str]]:
        rows = self.rows_as_dicts(self.values("Systems!A1:K250"))
        target = system.strip().lower()
        aliases = {
            "kaio omega": "kaio ω",
            "omega-autofix": "ω-autofix",
            "aeon-omega": "aeon-ω",
            "omega-scientia": "next frontier ai bible / ω-scientia",
            "caseforge-omega": "caseforge-ω",
        }
        target = aliases.get(target, target)
        for row in rows:
            if row.get("System", "").strip().lower() == target:
                return row
        return None

    def export_text(self, file_id: str, max_bytes: int = 300_000) -> str:
        if not file_id:
            return ""
        request = self.drive.files().export_media(fileId=file_id, mimeType="text/plain")
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
            if buffer.tell() >= max_bytes:
                break
        return buffer.getvalue()[:max_bytes].decode("utf-8", errors="replace")

    def recent_rows(self, sheet: str, max_rows: int = 50) -> List[Dict[str, str]]:
        values = self.values(f"'{sheet}'!A1:Z1000")
        rows = self.rows_as_dicts(values)
        return rows[-max_rows:]

    def bootstrap(self, system: str, matter: Optional[str] = None) -> Dict[str, Any]:
        record = self.system_record(system)
        if not record:
            raise RuntimeError(f"System is not registered in provider registry: {system}")
        bible_text = ""
        primary_id = record.get("Primary ID", "")
        if primary_id:
            try:
                bible_text = self.export_text(primary_id)
            except Exception as exc:
                bible_text = f"[PRIMARY_EXPORT_UNAVAILABLE: {type(exc).__name__}]"

        def relevant(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
            if not matter:
                return rows
            needle = matter.lower()
            filtered = [row for row in rows if needle in str(row).lower()]
            return filtered or rows[-10:]

        return {
            "provider": "google-workspace",
            "provider_readback": True,
            "system_record": record,
            "canonical_bible_text": bible_text,
            "recent_sync_events": relevant(self.recent_rows("Sync Events", 50)),
            "shared_learnings": self.recent_rows("Shared Learnings", 100),
            "open_conflicts": relevant(self.recent_rows("Conflict Queue", 50)),
            "respawn_bibliography": relevant(self.recent_rows("Respawn Bibliography", 50)),
            "read_at": utcnow(),
        }

    def append_row(self, sheet: str, row: List[str]) -> Dict[str, Any]:
        if not self.provider_writes:
            raise RuntimeError("FEDERATION_PROVIDER_WRITES is not enabled")
        result = self.sheets.spreadsheets().values().append(
            spreadsheetId=self.sync_bus_id,
            range=f"'{sheet}'!A:Z",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()
        return {
            "updated_range": result.get("updates", {}).get("updatedRange"),
            "updated_rows": result.get("updates", {}).get("updatedRows"),
        }

    def publish_delta(
        self,
        *,
        event_id: str,
        source_system: str,
        affected_systems: List[str],
        topic: str,
        summary: str,
        evidence_refs: List[str],
        chat_ref: Optional[str],
        status: str,
    ) -> Dict[str, Any]:
        proof = "; ".join(evidence_refs)
        sync = self.append_row(
            "Sync Events",
            [
                event_id,
                utcnow(),
                source_system,
                "; ".join(affected_systems),
                topic,
                "",
                summary,
                proof,
                status,
                "Published by Federation Respawn provider adapter",
            ],
        )
        bibliography = self.append_row(
            "Respawn Bibliography",
            [
                f"BIB-{event_id}",
                utcnow(),
                source_system,
                chat_ref or "",
                topic,
                summary,
                proof,
                status,
            ],
        )
        return {"sync_event": sync, "bibliography": bibliography, "provider": "google-workspace"}
