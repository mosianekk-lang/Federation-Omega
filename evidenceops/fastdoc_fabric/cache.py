from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Iterable, Mapping, Any

from .models import PagePacket, SearchHit


def _options_digest(options: Mapping[str, Any] | None) -> str:
    payload = json.dumps(options or {}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class SQLitePageStore:
    """Content-addressed page cache plus lightweight full-text retrieval.

    The cache key binds document bytes, page number, extractor identity/version,
    and extraction options so stale results cannot silently survive a parser change.
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS page_cache (
                document_sha TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                extractor TEXT NOT NULL,
                extractor_version TEXT NOT NULL,
                options_sha TEXT NOT NULL,
                text TEXT NOT NULL,
                block_count INTEGER NOT NULL,
                image_count INTEGER NOT NULL,
                extraction_ms REAL NOT NULL,
                metadata_json TEXT NOT NULL,
                PRIMARY KEY(document_sha,page_number,extractor,extractor_version,options_sha)
            )
            """
        )
        self._fts = True
        try:
            self.conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS page_fts USING fts5(document_sha UNINDEXED,page_number UNINDEXED,text,tokenize='unicode61')"
            )
        except sqlite3.OperationalError:
            self._fts = False
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS page_fts_fallback(document_sha TEXT,page_number INTEGER,text TEXT,PRIMARY KEY(document_sha,page_number))"
            )
        self.conn.commit()

    @property
    def fts_enabled(self) -> bool:
        return self._fts

    def get(
        self,
        document_sha: str,
        page_number: int,
        extractor: str,
        extractor_version: str,
        options: Mapping[str, Any] | None = None,
    ) -> PagePacket | None:
        row = self.conn.execute(
            """SELECT text,block_count,image_count,extraction_ms,metadata_json
               FROM page_cache WHERE document_sha=? AND page_number=? AND extractor=? AND extractor_version=? AND options_sha=?""",
            (document_sha, page_number, extractor, extractor_version, _options_digest(options)),
        ).fetchone()
        if not row:
            return None
        return PagePacket(
            page_number=page_number,
            text=row[0],
            block_count=int(row[1]),
            image_count=int(row[2]),
            extraction_ms=float(row[3]),
            extractor=extractor,
            extractor_version=extractor_version,
            metadata=json.loads(row[4]),
        )

    def put(self, document_sha: str, packet: PagePacket, options: Mapping[str, Any] | None = None) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO page_cache
               (document_sha,page_number,extractor,extractor_version,options_sha,text,block_count,image_count,extraction_ms,metadata_json)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                document_sha,
                packet.page_number,
                packet.extractor,
                packet.extractor_version,
                _options_digest(options),
                packet.text,
                packet.block_count,
                packet.image_count,
                packet.extraction_ms,
                json.dumps(dict(packet.metadata), sort_keys=True),
            ),
        )
        if self._fts:
            self.conn.execute("DELETE FROM page_fts WHERE document_sha=? AND page_number=?", (document_sha, packet.page_number))
            self.conn.execute("INSERT INTO page_fts(document_sha,page_number,text) VALUES (?,?,?)", (document_sha, packet.page_number, packet.text))
        else:
            self.conn.execute(
                "INSERT OR REPLACE INTO page_fts_fallback(document_sha,page_number,text) VALUES (?,?,?)",
                (document_sha, packet.page_number, packet.text),
            )

    def put_many(self, document_sha: str, packets: Iterable[PagePacket], options: Mapping[str, Any] | None = None) -> None:
        for packet in packets:
            self.put(document_sha, packet, options)
        self.conn.commit()

    def cached_page_numbers(
        self,
        document_sha: str,
        extractor: str,
        extractor_version: str,
        options: Mapping[str, Any] | None = None,
    ) -> set[int]:
        rows = self.conn.execute(
            "SELECT page_number FROM page_cache WHERE document_sha=? AND extractor=? AND extractor_version=? AND options_sha=?",
            (document_sha, extractor, extractor_version, _options_digest(options)),
        )
        return {int(r[0]) for r in rows}

    def search(self, document_sha: str, query: str, limit: int = 8) -> list[SearchHit]:
        terms = [t for t in query.replace('"', ' ').split() if t]
        if not terms:
            return []
        if self._fts:
            fts_query = " OR ".join(f'"{t}"' for t in terms)
            rows = self.conn.execute(
                """SELECT page_number, bm25(page_fts), snippet(page_fts,2,'[',']','...',18)
                   FROM page_fts WHERE page_fts MATCH ? AND document_sha=? ORDER BY bm25(page_fts) LIMIT ?""",
                (fts_query, document_sha, int(limit)),
            ).fetchall()
            return [SearchHit(int(p), float(score), snippet) for p, score, snippet in rows]
        pattern = "%" + "%".join(terms) + "%"
        rows = self.conn.execute(
            "SELECT page_number,text FROM page_fts_fallback WHERE document_sha=? AND text LIKE ? LIMIT ?",
            (document_sha, pattern, int(limit)),
        ).fetchall()
        return [SearchHit(int(p), 0.0, text[:300]) for p, text in rows]

    def close(self) -> None:
        self.conn.close()
