from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .hashing import sha256_file
from .ledger import EvidenceLedger


class EvidenceIndex:
    """SQLite-backed searchable index over transcript and translation records."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def build(self, ledger: EvidenceLedger) -> dict[str, Any]:
        segments = ledger.transcript_segments()
        translations = ledger.translations()
        reviews = ledger.human_reviews()
        latest_review: dict[str, dict[str, Any]] = {}
        for review in reviews:
            latest_review[review["segment_id"]] = review
        translation_by_segment: dict[str, list[dict[str, Any]]] = {}
        for translation in translations:
            translation_by_segment.setdefault(translation["segment_id"], []).append(translation)

        if self.path.exists():
            self.path.unlink()
        connection = self._connect()
        fts_enabled = True
        inserted = 0
        try:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE records (
                    row_id INTEGER PRIMARY KEY,
                    segment_id TEXT NOT NULL,
                    unit_id TEXT NOT NULL,
                    source_item_id TEXT NOT NULL,
                    start_seconds REAL NOT NULL,
                    end_seconds REAL NOT NULL,
                    speaker_label TEXT,
                    speaker_role TEXT,
                    source_language TEXT NOT NULL,
                    target_language TEXT,
                    original_text TEXT NOT NULL,
                    translated_text TEXT,
                    provider TEXT NOT NULL,
                    architecture_family TEXT NOT NULL,
                    confidence REAL,
                    review_state TEXT NOT NULL,
                    audio_window_sha256 TEXT,
                    source_sha256 TEXT,
                    provenance_json TEXT NOT NULL
                );
                CREATE INDEX idx_records_segment ON records(segment_id);
                CREATE INDEX idx_records_time ON records(start_seconds, end_seconds);
                CREATE INDEX idx_records_language ON records(source_language, target_language);
                """
            )
            try:
                connection.execute(
                    "CREATE VIRTUAL TABLE records_fts USING fts5(original_text, translated_text, content='records', content_rowid='row_id')"
                )
            except sqlite3.OperationalError:
                fts_enabled = False

            items = {row["item_id"]: row for row in ledger.evidence_items()}
            for segment in segments:
                review = latest_review.get(segment["segment_id"], {})
                segment_translations = translation_by_segment.get(segment["segment_id"], []) or [None]
                for translation in segment_translations:
                    source_item = items.get(segment["source_item_id"], {})
                    translated_text = translation["translated_text"] if translation else None
                    target_language = translation["target_language"] if translation else None
                    review_state = (
                        translation.get("review_state", "UNREVIEWED")
                        if translation
                        else review.get("state", "UNREVIEWED")
                    )
                    provenance = {
                        "segment": segment,
                        "translation": translation,
                        "review": review or None,
                    }
                    cursor = connection.execute(
                        """
                        INSERT INTO records (
                            segment_id, unit_id, source_item_id, start_seconds, end_seconds,
                            speaker_label, speaker_role, source_language, target_language,
                            original_text, translated_text, provider, architecture_family,
                            confidence, review_state, audio_window_sha256, source_sha256,
                            provenance_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            segment["segment_id"],
                            segment["unit_id"],
                            segment["source_item_id"],
                            segment["start_seconds"],
                            segment["end_seconds"],
                            segment.get("speaker_label"),
                            segment.get("speaker_role"),
                            segment["source_language"],
                            target_language,
                            segment["original_text"],
                            translated_text,
                            segment["provider"],
                            segment["architecture_family"],
                            segment.get("confidence"),
                            review_state,
                            review.get("audio_window_sha256"),
                            source_item.get("sha256"),
                            json.dumps(provenance, ensure_ascii=False, sort_keys=True),
                        ),
                    )
                    if fts_enabled:
                        connection.execute(
                            "INSERT INTO records_fts(rowid, original_text, translated_text) VALUES (?, ?, ?)",
                            (cursor.lastrowid, segment["original_text"], translated_text or ""),
                        )
                    inserted += 1
            connection.commit()
        finally:
            connection.close()
        return {
            "contract": "EVIDENCEOPS_AUDIO_SEARCH_INDEX_V1",
            "state": "BUILT",
            "path": str(self.path),
            "sha256": sha256_file(self.path),
            "record_count": inserted,
            "segment_count": len(segments),
            "translation_count": len(translations),
            "fts5_enabled": fts_enabled,
            "truth_boundary": (
                "Search results are discovery aids. The underlying transcript, translation, review and audio-window "
                "records remain the evidence source and must satisfy their release gates."
            ),
        }

    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        language: str | None = None,
        verified_only: bool = False,
    ) -> list[dict[str, Any]]:
        if not query.strip():
            raise ValueError("query cannot be blank")
        connection = self._connect()
        try:
            has_fts = bool(
                connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='records_fts'"
                ).fetchone()
            )
            filters = []
            parameters: list[Any] = []
            if language:
                filters.append("(r.source_language = ? OR r.target_language = ?)")
                parameters.extend([language, language])
            if verified_only:
                filters.append("r.review_state IN ('HUMAN_VERIFIED_SOURCE_TEXT', 'HUMAN_VERIFIED_TRANSLATION')")
            where_extra = f" AND {' AND '.join(filters)}" if filters else ""
            if has_fts:
                sql = f"""
                    SELECT r.*, bm25(records_fts) AS rank
                    FROM records_fts
                    JOIN records r ON r.row_id = records_fts.rowid
                    WHERE records_fts MATCH ? {where_extra}
                    ORDER BY rank, r.start_seconds
                    LIMIT ?
                """
                rows = connection.execute(sql, [query, *parameters, limit]).fetchall()
            else:
                like = f"%{query}%"
                sql = f"""
                    SELECT r.*, 0.0 AS rank
                    FROM records r
                    WHERE (r.original_text LIKE ? OR COALESCE(r.translated_text, '') LIKE ?) {where_extra}
                    ORDER BY r.start_seconds
                    LIMIT ?
                """
                rows = connection.execute(sql, [like, like, *parameters, limit]).fetchall()
            results = []
            for row in rows:
                record = dict(row)
                record["citation"] = (
                    f"audio:{record['source_item_id']}#segment={record['segment_id']}"
                    f"&t={record['start_seconds']:.3f}-{record['end_seconds']:.3f}"
                )
                record["provenance"] = json.loads(record.pop("provenance_json"))
                results.append(record)
            return results
        finally:
            connection.close()
