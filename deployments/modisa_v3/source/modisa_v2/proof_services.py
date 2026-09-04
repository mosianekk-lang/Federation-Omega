from __future__ import annotations

from typing import Any

from .legal_graph import LegalGraph
from .proof_ledger import ProofLedger
from .schemas import ProofAppendRequest, ProofType


class DeterministicProofServices:
    def __init__(self, graph: LegalGraph, ledger: ProofLedger):
        self.graph = graph
        self.ledger = ledger

    def mission_scope(
        self,
        *,
        matter_id: str,
        mission_id: str,
        actor_id: str,
        exact_question: str,
        jurisdiction: str,
        forum: str,
        risk_level: str,
        external_boundary: str,
    ) -> str:
        proof = self.ledger.append(
            ProofAppendRequest(
                matter_id=matter_id,
                mission_id=mission_id,
                proof_type=ProofType.MISSION_SCOPE,
                subject_id=mission_id,
                actor_id=actor_id,
                payload={
                    "exact_question": exact_question,
                    "jurisdiction": jurisdiction,
                    "forum": forum,
                    "risk_level": risk_level,
                    "external_boundary": external_boundary,
                },
            )
        )
        return proof.proof_id

    def source_completeness(
        self,
        *,
        matter_id: str,
        mission_id: str,
        actor_id: str,
        expected_source_ids: list[str],
        inspected_source_ids: list[str],
        missing_source_ids: list[str],
        method: str,
    ) -> str:
        expected = set(expected_source_ids)
        inspected = set(inspected_source_ids)
        missing = set(missing_source_ids) | (expected - inspected)
        complete = bool(expected) and not missing and expected.issubset(inspected)
        proof = self.ledger.append(
            ProofAppendRequest(
                matter_id=matter_id,
                mission_id=mission_id,
                proof_type=ProofType.SOURCE_COMPLETENESS,
                subject_id=mission_id,
                actor_id=actor_id,
                source_ids=sorted(inspected),
                payload={
                    "expected_source_ids": sorted(expected),
                    "inspected_source_ids": sorted(inspected),
                    "missing_source_ids": sorted(missing),
                    "complete": complete,
                    "method": method,
                },
            )
        )
        return proof.proof_id

    def fact_classification(
        self,
        *,
        matter_id: str,
        mission_id: str,
        actor_id: str,
        claim_ids: list[str],
    ) -> str:
        classifications: list[dict[str, Any]] = []
        for claim_id in claim_ids:
            claim = self.graph.get_claim(claim_id)
            if claim is None:
                raise ValueError(f"Unknown claim: {claim_id}")
            status = self.graph.claim_support_status(claim_id)
            classifications.append(
                {
                    "claim_id": claim_id,
                    "kind": claim.kind.value,
                    "proof_state": claim.proof_state.value,
                    "support_count": status["support_count"],
                    "contradiction_count": status["contradiction_count"],
                }
            )
        proof = self.ledger.append(
            ProofAppendRequest(
                matter_id=matter_id,
                mission_id=mission_id,
                proof_type=ProofType.FACT_CLASSIFICATION,
                subject_id=mission_id,
                actor_id=actor_id,
                source_ids=claim_ids,
                payload={"claims": classifications, "fact_inference_unknown_separated": True},
            )
        )
        return proof.proof_id

    def forum_power(
        self,
        *,
        matter_id: str,
        mission_id: str,
        actor_id: str,
        forum: str,
        remedy: str,
        authority_ids: list[str],
        conclusion: str,
    ) -> str:
        if not authority_ids:
            raise ValueError("Forum-power proof requires authority")
        for authority_id in authority_ids:
            if self.graph.get_authority(authority_id) is None:
                raise ValueError(f"Unknown authority: {authority_id}")
        proof = self.ledger.append(
            ProofAppendRequest(
                matter_id=matter_id,
                mission_id=mission_id,
                proof_type=ProofType.FORUM_POWER,
                subject_id=forum,
                actor_id=actor_id,
                source_ids=authority_ids,
                payload={"forum": forum, "remedy": remedy, "conclusion": conclusion, "authority_ids": authority_ids},
            )
        )
        return proof.proof_id

    def deadline_characterisation(
        self,
        *,
        matter_id: str,
        mission_id: str,
        actor_id: str,
        deadline: str,
        classification: str,
        authority_ids: list[str],
        source_ids: list[str],
        reasoning: str,
    ) -> str:
        allowed = {"STATUTORY", "RULE_BASED", "CONTRACTUAL", "REQUESTED_RESPONSE_PERIOD", "INTERNAL_TARGET", "UNKNOWN"}
        if classification not in allowed:
            raise ValueError("Unknown deadline classification")
        proof = self.ledger.append(
            ProofAppendRequest(
                matter_id=matter_id,
                mission_id=mission_id,
                proof_type=ProofType.DEADLINE_CHARACTERISATION,
                subject_id=deadline,
                actor_id=actor_id,
                source_ids=[*authority_ids, *source_ids],
                payload={"deadline": deadline, "classification": classification, "reasoning": reasoning, "authority_ids": authority_ids},
            )
        )
        return proof.proof_id

    def privacy_classification(
        self,
        *,
        matter_id: str,
        mission_id: str,
        actor_id: str,
        object_id: str,
        privacy_tier: str,
        privilege_claimed: bool,
        privilege_basis: dict[str, Any] | None = None,
    ) -> str:
        basis = privilege_basis or {}
        if privilege_claimed:
            required = {"lawyer_client_relationship", "dominant_legal_purpose", "confidentiality_preserved"}
            if not required.issubset({key for key, value in basis.items() if value is True}):
                raise ValueError("Privilege cannot be claimed without a complete legal basis")
        proof = self.ledger.append(
            ProofAppendRequest(
                matter_id=matter_id,
                mission_id=mission_id,
                proof_type=ProofType.PRIVACY_CLASSIFICATION,
                subject_id=object_id,
                actor_id=actor_id,
                source_ids=[object_id],
                payload={"privacy_tier": privacy_tier, "privilege_claimed": privilege_claimed, "privilege_basis": basis},
            )
        )
        return proof.proof_id

    def write_readback(
        self,
        *,
        matter_id: str,
        mission_id: str,
        actor_id: str,
        object_id: str,
        write_hash: str,
        readback_hash: str,
        location: str,
    ) -> str:
        if write_hash != readback_hash:
            raise ValueError("Write and readback hashes differ")
        proof = self.ledger.append(
            ProofAppendRequest(
                matter_id=matter_id,
                mission_id=mission_id,
                proof_type=ProofType.WRITE_READBACK,
                subject_id=object_id,
                actor_id=actor_id,
                source_ids=[object_id],
                payload={"write_hash": write_hash, "readback_hash": readback_hash, "location": location, "match": True},
            )
        )
        return proof.proof_id
