from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from .canonical import sha256_bytes
from .legal_graph import LegalGraph
from .proof_ledger import ProofLedger
from .schemas import (
    AuthorityRecord,
    AuthorityRegisterRequest,
    ProofAppendRequest,
    ProofType,
)
from .source_policy import enforce_primary_source


class PrimaryLawResearchService:
    """Primary-source retrieval and proposition registration.

    It verifies the network source and content hash. It does not infer that a statute is
    current or a judgment remains good law unless a separate treatment proof is issued.
    """

    def __init__(self, graph: LegalGraph, ledger: ProofLedger, max_bytes: int = 25_000_000):
        self.graph = graph
        self.ledger = ledger
        self.max_bytes = max_bytes

    def fetch(self, url: str) -> tuple[bytes, str, str]:
        enforce_primary_source(url)
        with httpx.Client(follow_redirects=True, timeout=30.0) as client:
            response = client.get(url, headers={"User-Agent": "MODISA-Legal-OS/2.0"})
            response.raise_for_status()
            final_url = str(response.url)
            enforce_primary_source(final_url)
            content = response.content
        if len(content) > self.max_bytes:
            raise ValueError("Authority source exceeds configured maximum")
        return content, final_url, response.headers.get("content-type", "application/octet-stream")

    def retrieve_and_register(
        self,
        request: AuthorityRegisterRequest,
        actor_id: str,
    ) -> tuple[AuthorityRecord, str, str]:
        content, final_url, content_type = self.fetch(request.source_url)
        actual_hash = sha256_bytes(content)
        if request.content_hash and request.content_hash != actual_hash:
            raise ValueError("Authority content hash does not match retrieved source")
        revised = request.model_copy(update={"source_url": final_url, "content_hash": actual_hash})
        authority = self.graph.register_authority(revised)
        read_proof = self.ledger.append(
            ProofAppendRequest(
                matter_id=request.matter_id,
                mission_id=request.mission_id,
                proof_type=ProofType.SOURCE_READ,
                subject_id=authority.authority_id,
                actor_id=actor_id,
                source_ids=[authority.authority_id],
                payload={
                    "source_url": final_url,
                    "content_hash": actual_hash,
                    "content_type": content_type,
                    "byte_size": len(content),
                    "retrieved_at": datetime.now(UTC).isoformat(),
                    "primary_source_domain_enforced": True,
                },
            )
        )
        law_proof = self.ledger.append(
            ProofAppendRequest(
                matter_id=request.matter_id,
                mission_id=request.mission_id,
                proof_type=ProofType.LAW_CHECK,
                subject_id=authority.authority_id,
                actor_id=actor_id,
                source_ids=[authority.authority_id],
                payload={
                    "citation": authority.citation,
                    "proposition": authority.proposition,
                    "source_url": final_url,
                    "content_hash": actual_hash,
                    "current_primary_authority_checked": True,
                    "current_as_of": datetime.now(UTC).date().isoformat(),
                    "treatment_check_separate": True,
                },
            )
        )
        return authority, read_proof.proof_id, law_proof.proof_id

    def record_treatment_check(
        self,
        *,
        matter_id: str,
        mission_id: str,
        authority_ids: list[str],
        actor_id: str,
        amendment_sources: list[str],
        subsequent_treatment_sources: list[str],
        conclusion: str,
    ) -> str:
        if not authority_ids:
            raise ValueError("At least one authority is required")
        for authority_id in authority_ids:
            if self.graph.get_authority(authority_id) is None:
                raise ValueError(f"Unknown authority: {authority_id}")
        if not amendment_sources and not subsequent_treatment_sources:
            raise ValueError("Treatment check requires amendment or subsequent-treatment sources")
        proof = self.ledger.append(
            ProofAppendRequest(
                matter_id=matter_id,
                mission_id=mission_id,
                proof_type=ProofType.AUTHORITY_TREATMENT,
                subject_id=authority_ids[0],
                actor_id=actor_id,
                source_ids=[*authority_ids, *amendment_sources, *subsequent_treatment_sources],
                payload={
                    "authority_ids": authority_ids,
                    "amendment_sources": amendment_sources,
                    "subsequent_treatment_sources": subsequent_treatment_sources,
                    "amendment_and_subsequent_treatment_checked": True,
                    "conclusion": conclusion,
                },
            )
        )
        return proof.proof_id

    def record_contrary_search(
        self,
        *,
        matter_id: str,
        mission_id: str,
        actor_id: str,
        query: str,
        searched_source_ids: list[str],
        contrary_items: list[dict[str, Any]],
        search_scope: str,
    ) -> str:
        if len(query.strip()) < 3:
            raise ValueError("Contrary-search query is required")
        if not searched_source_ids:
            raise ValueError("Contrary search must identify inspected sources")
        proof = self.ledger.append(
            ProofAppendRequest(
                matter_id=matter_id,
                mission_id=mission_id,
                proof_type=ProofType.CONTRARY_SEARCH,
                subject_id=mission_id,
                actor_id=actor_id,
                source_ids=searched_source_ids,
                payload={
                    "query": query,
                    "search_scope": search_scope,
                    "searched_source_ids": searched_source_ids,
                    "contrary_items": contrary_items,
                    "search_performed": True,
                },
            )
        )
        return proof.proof_id
