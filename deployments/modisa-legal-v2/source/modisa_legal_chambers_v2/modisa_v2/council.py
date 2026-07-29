from __future__ import annotations

from collections import Counter
from typing import Iterable

from .db import Repository
from .ids import new_id
from .proof_ledger import ProofLedger
from .schemas import (
    CouncilDecision,
    CouncilDecisionRequest,
    CouncilOpinion,
    CouncilRole,
    ProofAppendRequest,
    ProofType,
    RiskLevel,
)


FULL_COUNCIL = frozenset(CouncilRole)
HIGH_COUNCIL = frozenset(
    {
        CouncilRole.APPLICANT,
        CouncilRole.RESPONDENT,
        CouncilRole.NEUTRAL_ADJUDICATOR,
        CouncilRole.EVIDENCE_EXAMINER,
        CouncilRole.AUTHORITY_VERIFIER,
        CouncilRole.PROCEDURAL_AUDITOR,
        CouncilRole.INSPECTOR_GENERAL,
    }
)
MEDIUM_COUNCIL = frozenset(
    {
        CouncilRole.APPLICANT,
        CouncilRole.RESPONDENT,
        CouncilRole.NEUTRAL_ADJUDICATOR,
        CouncilRole.INSPECTOR_GENERAL,
    }
)


class CouncilEngine:
    def __init__(self, repo: Repository, ledger: ProofLedger):
        self.repo = repo
        self.ledger = ledger

    @staticmethod
    def required_roles(risk: RiskLevel) -> frozenset[CouncilRole]:
        if risk == RiskLevel.CRITICAL:
            return FULL_COUNCIL
        if risk == RiskLevel.HIGH:
            return HIGH_COUNCIL
        return MEDIUM_COUNCIL

    def _validate_opinion_proofs(self, opinion: CouncilOpinion) -> list[str]:
        failures: list[str] = []
        for proof_id in opinion.proof_ids:
            proof = self.ledger.get(proof_id)
            if proof is None:
                failures.append(f"{opinion.role.value}: missing proof {proof_id}")
                continue
            valid, reason = self.ledger.verify_record(proof)
            if not valid:
                failures.append(f"{opinion.role.value}: invalid proof {proof_id}: {reason}")
            elif proof.matter_id != opinion.matter_id or proof.mission_id != opinion.mission_id:
                failures.append(f"{opinion.role.value}: proof scope mismatch {proof_id}")
        return failures

    def persist_opinion(self, opinion: CouncilOpinion) -> None:
        self.repo.ensure_matter(opinion.matter_id)
        self.repo.execute(
            """INSERT INTO council_opinions(
               opinion_id,matter_id,mission_id,role,disposition,conclusion,supported_claims_json,
               challenged_claims_json,proof_ids_json,risks_json,confidence,created_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(matter_id,mission_id,role) DO UPDATE SET
                 opinion_id=excluded.opinion_id,
                 disposition=excluded.disposition,
                 conclusion=excluded.conclusion,
                 supported_claims_json=excluded.supported_claims_json,
                 challenged_claims_json=excluded.challenged_claims_json,
                 proof_ids_json=excluded.proof_ids_json,
                 risks_json=excluded.risks_json,
                 confidence=excluded.confidence,
                 created_at=excluded.created_at""",
            (
                opinion.opinion_id,
                opinion.matter_id,
                opinion.mission_id,
                opinion.role.value,
                opinion.disposition,
                opinion.conclusion,
                self.repo.dumps(opinion.supported_claim_ids),
                self.repo.dumps(opinion.challenged_claim_ids),
                self.repo.dumps(opinion.proof_ids),
                self.repo.dumps(opinion.material_risks),
                opinion.confidence,
                opinion.created_at.isoformat(),
            ),
        )

    def decide(self, request: CouncilDecisionRequest, actor_id: str = "council-engine") -> CouncilDecision:
        required = self.required_roles(request.risk_level)
        by_role = {opinion.role: opinion for opinion in request.opinions}
        missing = sorted(required - set(by_role), key=lambda role: role.value)
        failures: list[str] = []
        all_proof_ids: list[str] = []
        for opinion in request.opinions:
            if opinion.matter_id != request.matter_id or opinion.mission_id != request.mission_id:
                failures.append(f"{opinion.role.value}: opinion scope mismatch")
            failures.extend(self._validate_opinion_proofs(opinion))
            all_proof_ids.extend(opinion.proof_ids)
            self.persist_opinion(opinion)

        if missing or failures:
            summary = "Council is incomplete or contains unverified opinions."
            if missing:
                summary += " Missing roles: " + ", ".join(role.value for role in missing) + "."
            if failures:
                summary += " Verification failures: " + "; ".join(failures) + "."
            return CouncilDecision(
                complete=False,
                disposition="HOLD",
                missing_roles=missing,
                conflicts=failures,
                proof_ids=list(dict.fromkeys(all_proof_ids)),
                summary=summary,
            )

        dispositions = Counter(opinion.disposition for opinion in request.opinions if opinion.role in required)
        neutral = by_role[CouncilRole.NEUTRAL_ADJUDICATOR].disposition
        inspector = by_role[CouncilRole.INSPECTOR_GENERAL].disposition
        if "HOLD" in {neutral, inspector}:
            disposition = "HOLD"
        elif neutral == inspector:
            disposition = neutral
        elif dispositions["QUALIFY"] > 0:
            disposition = "QUALIFY"
        else:
            disposition = "HOLD"
        conflicts = []
        if by_role[CouncilRole.APPLICANT].disposition == by_role[CouncilRole.RESPONDENT].disposition:
            conflicts.append("Applicant and respondent chambers returned the same stance; adversarial independence should be reviewed.")
        if neutral != inspector:
            conflicts.append("Neutral adjudicator and Inspector-General differ; final release must remain bounded.")
        proof = self.ledger.append(
            ProofAppendRequest(
                matter_id=request.matter_id,
                mission_id=request.mission_id,
                proof_type=ProofType.COUNCIL_REVIEW,
                subject_id=new_id("COUNCIL"),
                actor_id=actor_id,
                source_ids=[],
                payload={
                    "required_roles": sorted(role.value for role in required),
                    "opinion_ids": [opinion.opinion_id for opinion in request.opinions],
                    "dispositions": dict(dispositions),
                    "final_disposition": disposition,
                    "conflicts": conflicts,
                    "underlying_proof_ids": list(dict.fromkeys(all_proof_ids)),
                },
            )
        )
        return CouncilDecision(
            complete=True,
            disposition=disposition,
            conflicts=conflicts,
            proof_ids=[*list(dict.fromkeys(all_proof_ids)), proof.proof_id],
            summary=(
                f"Verified {len(required)}-role adversarial council completed. "
                f"Neutral disposition: {neutral}; Inspector-General: {inspector}; final: {disposition}."
            ),
        )
