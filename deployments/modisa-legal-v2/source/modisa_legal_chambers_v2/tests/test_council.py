from modisa_v2.ids import new_id
from modisa_v2.schemas import (
    CouncilDecisionRequest,
    CouncilOpinion,
    CouncilRole,
    ProofAppendRequest,
    ProofType,
    RiskLevel,
)


def opinion(role, proof_id, disposition="QUALIFY"):
    return CouncilOpinion(
        opinion_id=new_id("OPN"),
        matter_id="MAT-C",
        mission_id="MIS-C",
        role=role,
        disposition=disposition,
        conclusion=f"{role.value} conclusion",
        proof_ids=[proof_id],
        confidence=0.8,
    )


def test_missing_council_role_holds(services):
    services.repo.ensure_matter("MAT-C")
    proof = services.ledger.append(
        ProofAppendRequest(
            matter_id="MAT-C",
            mission_id="MIS-C",
            proof_type=ProofType.SOURCE_READ,
            subject_id="SRC",
            actor_id="reader",
            payload={"ok": True},
        )
    )
    decision = services.council.decide(
        CouncilDecisionRequest(
            matter_id="MAT-C",
            mission_id="MIS-C",
            risk_level=RiskLevel.HIGH,
            opinions=[opinion(CouncilRole.APPLICANT, proof.proof_id)],
        )
    )
    assert decision.complete is False
    assert decision.disposition == "HOLD"


def test_full_verified_council_completes(services):
    services.repo.ensure_matter("MAT-C")
    proof = services.ledger.append(
        ProofAppendRequest(
            matter_id="MAT-C",
            mission_id="MIS-C",
            proof_type=ProofType.SOURCE_READ,
            subject_id="SRC",
            actor_id="reader",
            payload={"ok": True},
        )
    )
    roles = list(CouncilRole)
    opinions = [opinion(role, proof.proof_id) for role in roles]
    opinions[roles.index(CouncilRole.APPLICANT)] = opinion(CouncilRole.APPLICANT, proof.proof_id, "SUPPORT")
    opinions[roles.index(CouncilRole.RESPONDENT)] = opinion(CouncilRole.RESPONDENT, proof.proof_id, "OPPOSE")
    decision = services.council.decide(
        CouncilDecisionRequest(
            matter_id="MAT-C",
            mission_id="MIS-C",
            risk_level=RiskLevel.HIGH,
            opinions=opinions,
        )
    )
    assert decision.complete is True
    assert decision.disposition == "QUALIFY"
    assert services.ledger.get(decision.proof_ids[-1]).proof_type == ProofType.COUNCIL_REVIEW
