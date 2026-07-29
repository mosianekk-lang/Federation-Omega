from pathlib import Path

from modisa_v2.ids import new_id
from modisa_v2.schemas import (
    AuthorityRegisterRequest,
    ClaimCreateRequest,
    ClaimKind,
    ClaimLinkRequest,
    CouncilDecisionRequest,
    CouncilOpinion,
    CouncilRole,
    EvidenceIngestRequest,
    LinkType,
    ProofAppendRequest,
    ProofState,
    ProofType,
    ReleaseDecision,
    ReleaseRequest,
    RiskLevel,
)


def build_releasable_mission(services, settings):
    matter_id, mission_id = "MAT-R", "MIS-R"
    services.repo.ensure_matter(matter_id, "Release Test", "South Africa", "CCMA")
    source = settings.data_root / "record.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("A notice was sent on 28 July 2026.", encoding="utf-8")
    evidence, _, _ = services.vault.ingest(
        EvidenceIngestRequest(matter_id=matter_id, mission_id=mission_id, path=str(source)),
        "ingestor",
    )
    _, read_proof = services.vault.read_verified(evidence.evidence_id, mission_id, "reader")
    authority = services.graph.register_authority(
        AuthorityRegisterRequest(
            matter_id=matter_id,
            mission_id=mission_id,
            citation="Test Act 1 of 2026",
            title="Test Act",
            authority_type="STATUTE",
            source_url="https://www.gov.za/documents/test-act",
            proposition="The forum may grant the remedy.",
            binding_level="BINDING",
            content_hash="a" * 64,
        )
    )
    fact = services.graph.create_claim(
        ClaimCreateRequest(
            matter_id=matter_id,
            mission_id=mission_id,
            kind=ClaimKind.FACT,
            proposition="The notice was sent.",
            proof_state=ProofState.FACT_NATIVE_VERIFIED,
        )
    )
    legal = services.graph.create_claim(
        ClaimCreateRequest(
            matter_id=matter_id,
            mission_id=mission_id,
            kind=ClaimKind.LEGAL,
            proposition="The forum may grant the requested remedy.",
            proof_state=ProofState.LEGAL_PROPOSITION_CURRENT,
        )
    )
    services.graph.link_claim(
        ClaimLinkRequest(
            claim_id=fact.claim_id,
            object_id=evidence.evidence_id,
            object_type="EVIDENCE",
            link_type=LinkType.SUPPORTS,
        )
    )
    services.graph.link_claim(
        ClaimLinkRequest(
            claim_id=legal.claim_id,
            object_id=authority.authority_id,
            object_type="AUTHORITY",
            link_type=LinkType.AUTHORITY_SUPPORTS,
        )
    )
    proof_ids = [
        services.proof_services.mission_scope(
            matter_id=matter_id,
            mission_id=mission_id,
            actor_id="scope",
            exact_question="Can the matter be released?",
            jurisdiction="South Africa",
            forum="CCMA",
            risk_level="HIGH",
            external_boundary="approval-gated",
        ),
        read_proof,
        services.proof_services.source_completeness(
            matter_id=matter_id,
            mission_id=mission_id,
            actor_id="completeness",
            expected_source_ids=[evidence.evidence_id],
            inspected_source_ids=[evidence.evidence_id],
            missing_source_ids=[],
            method="single source manifest",
        ),
        services.proof_services.fact_classification(
            matter_id=matter_id,
            mission_id=mission_id,
            actor_id="classifier",
            claim_ids=[fact.claim_id, legal.claim_id],
        ),
        services.research.record_contrary_search(
            matter_id=matter_id,
            mission_id=mission_id,
            actor_id="red-team",
            query="Evidence contradicting the notice and remedy proposition",
            searched_source_ids=[evidence.evidence_id, authority.authority_id],
            contrary_items=[],
            search_scope="registered matter evidence and authority",
        ),
        services.proof_services.privacy_classification(
            matter_id=matter_id,
            mission_id=mission_id,
            actor_id="privacy",
            object_id=matter_id,
            privacy_tier="P2_CONFIDENTIAL",
            privilege_claimed=False,
        ),
    ]
    law = services.ledger.append(
        ProofAppendRequest(
            matter_id=matter_id,
            mission_id=mission_id,
            proof_type=ProofType.LAW_CHECK,
            subject_id=authority.authority_id,
            actor_id="authority",
            source_ids=[authority.authority_id],
            payload={"current_primary_authority_checked": True},
        )
    )
    treatment = services.ledger.append(
        ProofAppendRequest(
            matter_id=matter_id,
            mission_id=mission_id,
            proof_type=ProofType.AUTHORITY_TREATMENT,
            subject_id=authority.authority_id,
            actor_id="authority",
            source_ids=[authority.authority_id],
            payload={"amendment_and_subsequent_treatment_checked": True},
        )
    )
    forum = services.proof_services.forum_power(
        matter_id=matter_id,
        mission_id=mission_id,
        actor_id="procedure",
        forum="CCMA",
        remedy="Test remedy",
        authority_ids=[authority.authority_id],
        conclusion="Within power for test purposes.",
    )
    proof_ids.extend([law.proof_id, treatment.proof_id, forum])
    opinions = []
    for role in CouncilRole:
        disposition = "QUALIFY"
        if role == CouncilRole.APPLICANT:
            disposition = "SUPPORT"
        elif role == CouncilRole.RESPONDENT:
            disposition = "OPPOSE"
        opinions.append(
            CouncilOpinion(
                opinion_id=new_id("OPN"),
                matter_id=matter_id,
                mission_id=mission_id,
                role=role,
                disposition=disposition,
                conclusion=f"{role.value} reviewed the record.",
                proof_ids=proof_ids,
                confidence=0.8,
            )
        )
    council = services.council.decide(
        CouncilDecisionRequest(
            matter_id=matter_id,
            mission_id=mission_id,
            risk_level=RiskLevel.HIGH,
            opinions=opinions,
        )
    )
    assert council.complete
    return matter_id, mission_id, [fact.claim_id, legal.claim_id]


def test_release_passes_only_with_proof_graph(services, settings):
    matter_id, mission_id, claim_ids = build_releasable_mission(services, settings)
    result = services.release_engine.evaluate(
        ReleaseRequest(
            matter_id=matter_id,
            mission_id=mission_id,
            risk_level=RiskLevel.HIGH,
            claim_ids=claim_ids,
        )
    )
    assert result.decision == ReleaseDecision.RELEASE
    assert result.release_receipt_id
    assert services.release_engine.get_receipt(result.release_receipt_id) is not None


def test_release_rejects_boolean_free_missing_proofs(services):
    services.repo.ensure_matter("MAT-M")
    result = services.release_engine.evaluate(
        ReleaseRequest(
            matter_id="MAT-M",
            mission_id="MIS-M",
            risk_level=RiskLevel.HIGH,
        )
    )
    assert result.decision in {
        ReleaseDecision.HOLD_FOR_EVIDENCE,
        ReleaseDecision.HOLD_FOR_COUNCIL,
        ReleaseDecision.REJECT_FALSE_CERTAINTY,
    }
    assert result.release_receipt_id is None
