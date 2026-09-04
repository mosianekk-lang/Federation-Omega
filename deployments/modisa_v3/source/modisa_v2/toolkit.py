from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .approvals import ApprovalService
from .config import Settings
from .evidence_vault import EvidenceVault
from .inventory import InventoryLimits, append_inventory_proof, inventory_path
from .legal_graph import LegalGraph
from .proof_services import DeterministicProofServices
from .release_engine import ProofBoundReleaseEngine
from .research import PrimaryLawResearchService
from .schemas import (
    ApprovalCreateRequest,
    AuthorityRegisterRequest,
    ClaimCreateRequest,
    ClaimLinkRequest,
    EvidenceIngestRequest,
    ReleaseRequest,
)


class ToolFactory:
    def __init__(
        self,
        *,
        settings: Settings,
        vault: EvidenceVault,
        graph: LegalGraph,
        proofs: DeterministicProofServices,
        research: PrimaryLawResearchService,
        approvals: ApprovalService,
        release_engine: ProofBoundReleaseEngine,
    ):
        self.settings = settings
        self.vault = vault
        self.graph = graph
        self.proofs = proofs
        self.research = research
        self.approvals = approvals
        self.release_engine = release_engine

    def _resolve_allowed_path(self, raw_path: str) -> Path:
        candidate = Path(raw_path).expanduser().resolve()
        if not any(candidate == root or root in candidate.parents for root in self.settings.authorised_read_roots):
            raise ValueError("Path is outside authorised roots")
        return candidate

    def build(self) -> list[Any]:
        try:
            from agents import function_tool
        except ImportError as exc:
            raise RuntimeError("openai-agents is not installed") from exc

        @function_tool
        def ingest_evidence(
            matter_id: str,
            mission_id: str,
            path: str,
            actor_id: str,
            metadata_json: str = "{}",
        ) -> str:
            """Copy a native file into the evidence vault, hash it, scan it and read back metadata."""
            request = EvidenceIngestRequest(
                matter_id=matter_id,
                mission_id=mission_id,
                path=str(self._resolve_allowed_path(path)),
                metadata=json.loads(metadata_json),
            )
            evidence, hash_proof, injection_proof = self.vault.ingest(request, actor_id)
            return json.dumps(
                {
                    "evidence": evidence.model_dump(mode="json"),
                    "hash_proof_id": hash_proof,
                    "prompt_injection_proof_id": injection_proof,
                },
                default=str,
            )

        @function_tool
        def inspect_recursive_container(
            matter_id: str,
            mission_id: str,
            subject_id: str,
            path: str,
            actor_id: str,
            source_ids_json: str,
            application_visible_count: int | None = None,
            application_attachment_count: int | None = None,
            application_inline_count: int | None = None,
        ) -> str:
            """Inventory EML/ZIP/directory content with resource limits and append a signed proof."""
            resolved = self._resolve_allowed_path(path)
            limits = InventoryLimits(
                max_file_bytes=self.settings.max_file_bytes,
                max_parts=self.settings.max_mime_parts,
                max_depth=self.settings.max_mime_depth,
                max_decoded_bytes=self.settings.max_decoded_bytes,
                max_zip_entries=self.settings.max_zip_entries,
                max_zip_expanded_bytes=self.settings.max_zip_expanded_bytes,
                max_zip_ratio=self.settings.max_zip_ratio,
            )
            result = inventory_path(
                resolved,
                application_visible_count=application_visible_count,
                application_attachment_count=application_attachment_count,
                application_inline_count=application_inline_count,
                limits=limits,
            )
            proof_id = append_inventory_proof(
                self.vault.ledger,
                matter_id=matter_id,
                mission_id=mission_id,
                subject_id=subject_id,
                actor_id=actor_id,
                source_ids=json.loads(source_ids_json),
                result=result,
            )
            return json.dumps({"inventory": result.model_dump(mode="json"), "proof_id": proof_id}, default=str)

        @function_tool
        def create_claim(input_json: str) -> str:
            """Create a typed fact, legal, procedural, deadline, remedy or privilege claim."""
            claim = self.graph.create_claim(ClaimCreateRequest.model_validate_json(input_json))
            return claim.model_dump_json()

        @function_tool
        def link_claim(input_json: str) -> str:
            """Link a claim to registered evidence, authority, proof, element or contrary claim."""
            link_id = self.graph.link_claim(ClaimLinkRequest.model_validate_json(input_json))
            return json.dumps({"link_id": link_id})

        @function_tool
        def retrieve_primary_authority(input_json: str, actor_id: str) -> str:
            """Retrieve an approved primary-law URL, verify its hash and register proposition proof."""
            request = AuthorityRegisterRequest.model_validate_json(input_json)
            authority, read_proof, law_proof = self.research.retrieve_and_register(request, actor_id)
            return json.dumps(
                {
                    "authority": authority.model_dump(mode="json"),
                    "source_read_proof_id": read_proof,
                    "law_check_proof_id": law_proof,
                },
                default=str,
            )

        @function_tool
        def record_authority_treatment(
            matter_id: str,
            mission_id: str,
            authority_ids_json: str,
            actor_id: str,
            amendment_sources_json: str,
            subsequent_treatment_sources_json: str,
            conclusion: str,
        ) -> str:
            """Bind amendment and subsequent-treatment checks to registered authorities."""
            proof_id = self.research.record_treatment_check(
                matter_id=matter_id,
                mission_id=mission_id,
                authority_ids=json.loads(authority_ids_json),
                actor_id=actor_id,
                amendment_sources=json.loads(amendment_sources_json),
                subsequent_treatment_sources=json.loads(subsequent_treatment_sources_json),
                conclusion=conclusion,
            )
            return json.dumps({"proof_id": proof_id})

        @function_tool
        def record_contrary_search(
            matter_id: str,
            mission_id: str,
            actor_id: str,
            query: str,
            searched_source_ids_json: str,
            contrary_items_json: str,
            search_scope: str,
        ) -> str:
            """Record a bounded contrary-evidence search over identified sources."""
            proof_id = self.research.record_contrary_search(
                matter_id=matter_id,
                mission_id=mission_id,
                actor_id=actor_id,
                query=query,
                searched_source_ids=json.loads(searched_source_ids_json),
                contrary_items=json.loads(contrary_items_json),
                search_scope=search_scope,
            )
            return json.dumps({"proof_id": proof_id})

        @function_tool
        def classify_claims(
            matter_id: str, mission_id: str, actor_id: str, claim_ids_json: str
        ) -> str:
            """Verify that registered claims separate facts, allegations, inferences and unknowns."""
            proof_id = self.proofs.fact_classification(
                matter_id=matter_id,
                mission_id=mission_id,
                actor_id=actor_id,
                claim_ids=json.loads(claim_ids_json),
            )
            return json.dumps({"proof_id": proof_id})

        @function_tool
        def request_external_action_approval(input_json: str) -> str:
            """Create an exact-parameter owner approval request; this does not execute the action."""
            approval = self.approvals.create(ApprovalCreateRequest.model_validate_json(input_json))
            return approval.model_dump_json()

        @function_tool
        def evaluate_proof_bound_release(input_json: str, actor_id: str) -> str:
            """Run the proof-bound release engine. The model cannot override its decision."""
            result = self.release_engine.evaluate(ReleaseRequest.model_validate_json(input_json), actor_id)
            return result.model_dump_json()

        return [
            ingest_evidence,
            inspect_recursive_container,
            create_claim,
            link_claim,
            retrieve_primary_authority,
            record_authority_treatment,
            record_contrary_search,
            classify_claims,
            request_external_action_approval,
            evaluate_proof_bound_release,
        ]
