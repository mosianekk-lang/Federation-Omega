from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .canonical import sha256_text
from .db import Repository
from .ids import new_id
from .legal_graph import LegalGraph
from .proof_ledger import ProofLedger
from .schemas import ProofAppendRequest, ProofType


@dataclass(frozen=True)
class KnowledgeHit:
    chunk_id: str
    document_id: str
    authority_id: str
    title: str
    source_url: str
    ordinal: int
    text: str
    score: float


class LegalKnowledgePlane:
    """Versioned primary-law corpus with verified hashes and local full-text retrieval."""

    def __init__(self, repo: Repository, graph: LegalGraph, ledger: ProofLedger):
        self.repo = repo
        self.graph = graph
        self.ledger = ledger

    @staticmethod
    def chunk_text(text: str, size: int = 1_800, overlap: int = 200) -> list[str]:
        clean = " ".join(text.replace("\x00", " ").split())
        if not clean:
            return []
        chunks: list[str] = []
        start = 0
        while start < len(clean):
            end = min(len(clean), start + size)
            if end < len(clean):
                boundary = clean.rfind(" ", start + max(size // 2, 1), end)
                if boundary > start:
                    end = boundary
            chunks.append(clean[start:end])
            if end >= len(clean):
                break
            start = max(start + 1, end - overlap)
        return chunks

    def ingest(
        self,
        *,
        authority_id: str,
        matter_id: str,
        mission_id: str,
        actor_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[str, list[str], str]:
        authority = self.graph.get_authority(authority_id)
        if authority is None:
            raise ValueError("Unknown authority")
        if authority.matter_id != matter_id:
            raise ValueError("Authority matter scope mismatch")
        source_hash = sha256_text(text)
        if authority.content_hash != source_hash:
            raise ValueError("Knowledge text hash differs from registered authority hash")
        chunks = self.chunk_text(text)
        if not chunks:
            raise ValueError("Authority text is empty")
        document_id = new_id("LDOC")
        created_at = self.repo.now()
        with self.repo.connect(immediate=True) as conn:
            existing = conn.execute(
                "SELECT document_id FROM legal_documents WHERE authority_id=? AND source_hash=?",
                (authority_id, source_hash),
            ).fetchone()
            if existing:
                document_id = existing["document_id"]
                rows = conn.execute(
                    "SELECT chunk_id FROM legal_chunks WHERE document_id=? ORDER BY ordinal", (document_id,)
                ).fetchall()
                chunk_ids = [row["chunk_id"] for row in rows]
            else:
                conn.execute(
                    """INSERT INTO legal_documents(
                       document_id,authority_id,matter_id,title,source_url,source_hash,effective_from,
                       effective_to,superseded_by,chunk_count,created_at
                       ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        document_id,
                        authority_id,
                        matter_id,
                        authority.title,
                        authority.source_url,
                        source_hash,
                        authority.effective_from,
                        authority.effective_to,
                        authority.superseded_by,
                        len(chunks),
                        created_at,
                    ),
                )
                chunk_ids = []
                for ordinal, chunk in enumerate(chunks):
                    chunk_id = new_id("LCH")
                    chunk_ids.append(chunk_id)
                    conn.execute(
                        "INSERT INTO legal_chunks(chunk_id,document_id,ordinal,text,text_hash,metadata_json) VALUES(?,?,?,?,?,?)",
                        (chunk_id, document_id, ordinal, chunk, sha256_text(chunk), self.repo.dumps(metadata or {})),
                    )
                    conn.execute(
                        "INSERT INTO legal_chunks_fts(chunk_id,document_id,text) VALUES(?,?,?)",
                        (chunk_id, document_id, chunk),
                    )
        proof = self.ledger.append(
            ProofAppendRequest(
                matter_id=matter_id,
                mission_id=mission_id,
                proof_type=ProofType.LAW_CHECK,
                subject_id=document_id,
                actor_id=actor_id,
                source_ids=[authority_id, document_id, *chunk_ids],
                payload={
                    "authority_id": authority_id,
                    "document_id": document_id,
                    "source_hash": source_hash,
                    "chunk_count": len(chunk_ids),
                    "current_primary_authority_checked": True,
                    "knowledge_plane_ingested": True,
                },
            )
        )
        return document_id, chunk_ids, proof.proof_id

    def search(self, *, matter_id: str, query: str, top_k: int = 8) -> list[KnowledgeHit]:
        if len(query.strip()) < 2:
            return []
        rows = self.repo.fetch_all(
            """
            SELECT c.chunk_id,c.document_id,c.ordinal,c.text,d.authority_id,d.title,d.source_url,
                   bm25(legal_chunks_fts) AS score
            FROM legal_chunks_fts
            JOIN legal_chunks c ON c.chunk_id=legal_chunks_fts.chunk_id
            JOIN legal_documents d ON d.document_id=c.document_id
            WHERE legal_chunks_fts MATCH ? AND d.matter_id=? AND d.superseded_by IS NULL
            ORDER BY score LIMIT ?
            """,
            (query, matter_id, top_k),
        )
        return [
            KnowledgeHit(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                authority_id=row["authority_id"],
                title=row["title"],
                source_url=row["source_url"],
                ordinal=int(row["ordinal"]),
                text=row["text"],
                score=float(row["score"]),
            )
            for row in rows
        ]
