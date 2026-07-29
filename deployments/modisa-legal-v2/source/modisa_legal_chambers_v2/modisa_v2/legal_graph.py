from __future__ import annotations

from datetime import datetime
from typing import Any

from .db import Repository
from .ids import new_id
from .schemas import (
    AuthorityRecord,
    AuthorityRegisterRequest,
    ClaimCreateRequest,
    ClaimLinkRequest,
    ClaimRecord,
    LinkType,
)
from .source_policy import enforce_primary_source


class LegalGraph:
    def __init__(self, repo: Repository):
        self.repo = repo

    def create_claim(self, request: ClaimCreateRequest) -> ClaimRecord:
        self.repo.ensure_matter(request.matter_id)
        claim_id = new_id("CLAIM")
        created_at = datetime.fromisoformat(self.repo.now())
        self.repo.execute(
            """
            INSERT INTO claims(claim_id,matter_id,mission_id,kind,proposition,proof_state,materiality,status,created_at)
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                claim_id,
                request.matter_id,
                request.mission_id,
                request.kind.value,
                request.proposition,
                request.proof_state.value,
                request.materiality,
                "ACTIVE",
                created_at.isoformat(),
            ),
        )
        return ClaimRecord(
            claim_id=claim_id,
            matter_id=request.matter_id,
            mission_id=request.mission_id,
            kind=request.kind,
            proposition=request.proposition,
            proof_state=request.proof_state,
            materiality=request.materiality,
            status="ACTIVE",
            created_at=created_at,
        )

    @staticmethod
    def _claim_from_row(row: Any) -> ClaimRecord:
        from .schemas import ClaimKind, ProofState

        return ClaimRecord(
            claim_id=row["claim_id"],
            matter_id=row["matter_id"],
            mission_id=row["mission_id"],
            kind=ClaimKind(row["kind"]),
            proposition=row["proposition"],
            proof_state=ProofState(row["proof_state"]),
            materiality=row["materiality"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def get_claim(self, claim_id: str) -> ClaimRecord | None:
        row = self.repo.fetch_one("SELECT * FROM claims WHERE claim_id=?", (claim_id,))
        return self._claim_from_row(row) if row else None

    def list_claims(self, matter_id: str, mission_id: str | None = None) -> list[ClaimRecord]:
        if mission_id:
            rows = self.repo.fetch_all(
                "SELECT * FROM claims WHERE matter_id=? AND mission_id=? ORDER BY created_at",
                (matter_id, mission_id),
            )
        else:
            rows = self.repo.fetch_all(
                "SELECT * FROM claims WHERE matter_id=? ORDER BY created_at", (matter_id,)
            )
        return [self._claim_from_row(row) for row in rows]

    def link_claim(self, request: ClaimLinkRequest) -> str:
        claim = self.get_claim(request.claim_id)
        if claim is None:
            raise ValueError("Unknown claim")
        existence_queries = {
            "EVIDENCE": ("SELECT 1 FROM evidence_objects WHERE evidence_id=?", request.object_id),
            "AUTHORITY": ("SELECT 1 FROM authorities WHERE authority_id=?", request.object_id),
            "CLAIM": ("SELECT 1 FROM claims WHERE claim_id=?", request.object_id),
            "PROOF": ("SELECT 1 FROM proof_records WHERE proof_id=?", request.object_id),
        }
        if request.object_type in existence_queries:
            query, value = existence_queries[request.object_type]
            if self.repo.fetch_one(query, (value,)) is None:
                raise ValueError(f"Unknown linked {request.object_type.lower()}: {request.object_id}")
        link_id = new_id("LINK")
        self.repo.execute(
            """
            INSERT INTO claim_links(link_id,claim_id,object_id,object_type,link_type,weight,notes,created_at)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                link_id,
                request.claim_id,
                request.object_id,
                request.object_type,
                request.link_type.value,
                request.weight,
                request.notes,
                self.repo.now(),
            ),
        )
        return link_id

    def links_for_claim(self, claim_id: str) -> list[dict[str, Any]]:
        rows = self.repo.fetch_all(
            "SELECT * FROM claim_links WHERE claim_id=? ORDER BY created_at", (claim_id,)
        )
        return [dict(row) for row in rows]

    def claim_support_status(self, claim_id: str) -> dict[str, Any]:
        claim = self.get_claim(claim_id)
        if claim is None:
            return {"exists": False, "supported": False, "reason": "unknown claim"}
        links = self.links_for_claim(claim_id)
        support = [link for link in links if link["link_type"] in {LinkType.SUPPORTS.value, LinkType.AUTHORITY_SUPPORTS.value, LinkType.SATISFIES_ELEMENT.value}]
        contradictions = [link for link in links if link["link_type"] == LinkType.CONTRADICTS.value]
        authority_support = [link for link in links if link["object_type"] == "AUTHORITY" and link["link_type"] == LinkType.AUTHORITY_SUPPORTS.value]
        evidence_support = [link for link in links if link["object_type"] == "EVIDENCE" and link["link_type"] == LinkType.SUPPORTS.value]
        return {
            "exists": True,
            "claim": claim,
            "support_count": len(support),
            "contradiction_count": len(contradictions),
            "authority_support_count": len(authority_support),
            "evidence_support_count": len(evidence_support),
            "supported": bool(support),
        }

    def register_authority(self, request: AuthorityRegisterRequest) -> AuthorityRecord:
        self.repo.ensure_matter(request.matter_id)
        domain = enforce_primary_source(request.source_url)
        authority_id = new_id("AUTH")
        created_at = datetime.fromisoformat(self.repo.now())
        self.repo.execute(
            """
            INSERT INTO authorities(
              authority_id,matter_id,mission_id,citation,title,authority_type,jurisdiction,
              source_url,source_domain,proposition,binding_level,effective_from,effective_to,
              content_hash,superseded_by,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                authority_id,
                request.matter_id,
                request.mission_id,
                request.citation,
                request.title,
                request.authority_type,
                request.jurisdiction,
                request.source_url,
                domain,
                request.proposition,
                request.binding_level,
                request.effective_from,
                request.effective_to,
                request.content_hash,
                request.superseded_by,
                created_at.isoformat(),
            ),
        )
        return AuthorityRecord(
            authority_id=authority_id,
            matter_id=request.matter_id,
            citation=request.citation,
            title=request.title,
            authority_type=request.authority_type,
            jurisdiction=request.jurisdiction,
            source_url=request.source_url,
            source_domain=domain,
            proposition=request.proposition,
            binding_level=request.binding_level,
            effective_from=request.effective_from,
            effective_to=request.effective_to,
            content_hash=request.content_hash,
            superseded_by=request.superseded_by,
            created_at=created_at,
        )

    def get_authority(self, authority_id: str) -> AuthorityRecord | None:
        row = self.repo.fetch_one("SELECT * FROM authorities WHERE authority_id=?", (authority_id,))
        if row is None:
            return None
        return AuthorityRecord(
            authority_id=row["authority_id"],
            matter_id=row["matter_id"],
            citation=row["citation"],
            title=row["title"],
            authority_type=row["authority_type"],
            jurisdiction=row["jurisdiction"],
            source_url=row["source_url"],
            source_domain=row["source_domain"],
            proposition=row["proposition"],
            binding_level=row["binding_level"],
            effective_from=row["effective_from"],
            effective_to=row["effective_to"],
            content_hash=row["content_hash"],
            superseded_by=row["superseded_by"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
