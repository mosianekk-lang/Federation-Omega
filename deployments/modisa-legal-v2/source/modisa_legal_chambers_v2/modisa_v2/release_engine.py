from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from .canonical import sha256_json
from .db import Repository
from .ids import new_id
from .legal_graph import LegalGraph
from .proof_ledger import ProofLedger
from .schemas import (
    ClaimKind,
    LinkType,
    ProofAppendRequest,
    ProofRecord,
    ProofType,
    ReleaseDecision,
    ReleaseRequest,
    ReleaseResult,
    RiskLevel,
)


BASE_HIGH_PROOFS = {
    ProofType.MISSION_SCOPE,
    ProofType.SOURCE_READ,
    ProofType.SOURCE_COMPLETENESS,
    ProofType.FACT_CLASSIFICATION,
    ProofType.CONTRARY_SEARCH,
    ProofType.PRIVACY_CLASSIFICATION,
}

BASE_MEDIUM_PROOFS = {
    ProofType.MISSION_SCOPE,
    ProofType.SOURCE_READ,
    ProofType.FACT_CLASSIFICATION,
    ProofType.CONTRARY_SEARCH,
}


class ProofBoundReleaseEngine:
    """Calculates release from verified proof records and graph links.

    The model cannot pass this gate by returning Boolean assurances. Every requirement must
    resolve to a signed record, a claim link or an independently read-back action receipt.
    """

    def __init__(self, repo: Repository, ledger: ProofLedger, graph: LegalGraph):
        self.repo = repo
        self.ledger = ledger
        self.graph = graph

    @staticmethod
    def _required_types(request: ReleaseRequest) -> set[ProofType]:
        required = set(BASE_HIGH_PROOFS if request.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL} else BASE_MEDIUM_PROOFS)
        if request.requirements.legal_analysis:
            required.add(ProofType.LAW_CHECK)
        if request.requirements.current_law_required:
            required.add(ProofType.AUTHORITY_TREATMENT)
        if request.requirements.forum_power_required:
            required.add(ProofType.FORUM_POWER)
        if request.requirements.deadline_analysis_required:
            required.add(ProofType.DEADLINE_CHARACTERISATION)
        if request.requirements.recursive_inventory_required:
            required.add(ProofType.INVENTORY_RECONCILIATION)
        if request.requirements.privacy_review_required:
            required.add(ProofType.PRIVACY_CLASSIFICATION)
        if request.requirements.write_performed:
            required.add(ProofType.WRITE_READBACK)
        if request.requirements.council_required and request.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            required.add(ProofType.COUNCIL_REVIEW)
        return required

    def _validate_claims(self, request: ReleaseRequest) -> list[str]:
        failures: list[str] = []
        for claim_id in request.claim_ids:
            claim = self.graph.get_claim(claim_id)
            if claim is None:
                failures.append(f"unknown claim: {claim_id}")
                continue
            if claim.matter_id != request.matter_id or claim.mission_id != request.mission_id:
                failures.append(f"claim scope mismatch: {claim_id}")
                continue
            status = self.graph.claim_support_status(claim_id)
            if not status.get("supported"):
                failures.append(f"claim has no supporting link: {claim_id}")
            if claim.kind == ClaimKind.FACT and int(status.get("evidence_support_count", 0)) == 0:
                failures.append(f"fact claim lacks evidence support: {claim_id}")
            if claim.kind in {ClaimKind.LEGAL, ClaimKind.PROCEDURAL, ClaimKind.REMEDY, ClaimKind.DEADLINE, ClaimKind.PRIVILEGE} and int(status.get("authority_support_count", 0)) == 0:
                failures.append(f"legal/procedural claim lacks authority support: {claim_id}")
        return failures

    def _mission_proofs(self, request: ReleaseRequest) -> list[ProofRecord]:
        records = self.ledger.list_for_mission(request.matter_id, request.mission_id)
        if request.proof_ids:
            selected = set(request.proof_ids)
            records = [record for record in records if record.proof_id in selected]
        return records

    def _validate_proofs(self, request: ReleaseRequest, records: list[ProofRecord]) -> tuple[list[str], dict[ProofType, list[ProofRecord]]]:
        failures: list[str] = []
        by_type: dict[ProofType, list[ProofRecord]] = defaultdict(list)
        for record in records:
            if record.matter_id != request.matter_id or record.mission_id != request.mission_id:
                failures.append(f"proof scope mismatch: {record.proof_id}")
                continue
            valid, reason = self.ledger.verify_record(record)
            if not valid:
                failures.append(f"invalid proof {record.proof_id}: {reason}")
                continue
            by_type[record.proof_type].append(record)

        for required in sorted(self._required_types(request), key=lambda item: item.value):
            if required not in by_type:
                failures.append(f"missing proof type: {required.value}")

        completeness = by_type.get(ProofType.SOURCE_COMPLETENESS, [])
        if completeness and not any(bool(record.payload.get("complete")) for record in completeness):
            failures.append("source completeness was not established")

        inventories = by_type.get(ProofType.INVENTORY_RECONCILIATION, [])
        if request.requirements.recursive_inventory_required and inventories:
            allowed = {"VERIFIED", "VERIFIED_WITH_CATEGORY_DIFFERENCE"}
            if not any(record.payload.get("completeness_state") in allowed for record in inventories):
                failures.append("recursive inventory remains unverified")

        law_checks = by_type.get(ProofType.LAW_CHECK, [])
        if request.requirements.legal_analysis and law_checks:
            if not any(bool(record.payload.get("current_primary_authority_checked")) for record in law_checks):
                failures.append("current primary authority check not proven")

        treatment = by_type.get(ProofType.AUTHORITY_TREATMENT, [])
        if request.requirements.current_law_required and treatment:
            if not any(bool(record.payload.get("amendment_and_subsequent_treatment_checked")) for record in treatment):
                failures.append("amendment or subsequent treatment check not proven")

        contrary = by_type.get(ProofType.CONTRARY_SEARCH, [])
        if contrary and not any(bool(record.payload.get("search_performed")) for record in contrary):
            failures.append("contrary-evidence search not proven")

        councils = by_type.get(ProofType.COUNCIL_REVIEW, [])
        if request.requirements.council_required and request.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL} and councils:
            acceptable = [record for record in councils if record.payload.get("final_disposition") not in {None, "HOLD"}]
            if not acceptable:
                failures.append("adversarial council did not clear the matter for release")

        return failures, by_type

    def _validate_external_action(self, request: ReleaseRequest) -> list[str]:
        receipt_id = request.requirements.external_action_id
        if not receipt_id:
            return []
        row = self.repo.fetch_one(
            "SELECT * FROM action_receipts WHERE action_receipt_id=?", (receipt_id,)
        )
        if row is None:
            return ["external action receipt does not exist"]
        failures: list[str] = []
        if row["matter_id"] != request.matter_id or row["mission_id"] != request.mission_id:
            failures.append("external action receipt scope mismatch")
        if row["readback_status"] not in {"CONFIRMED", "DELIVERED", "READBACK_VERIFIED", "SUCCESS"}:
            failures.append("external action provider readback is not confirmed")
        for key in ("execution_proof_id", "readback_proof_id"):
            proof = self.ledger.get(row[key])
            if proof is None:
                failures.append(f"external action missing {key}")
            else:
                valid, reason = self.ledger.verify_record(proof)
                if not valid:
                    failures.append(f"external action invalid {key}: {reason}")
        return failures

    def evaluate(self, request: ReleaseRequest, actor_id: str = "release-engine") -> ReleaseResult:
        chain = self.ledger.verify_chain(request.matter_id)
        if not chain.valid:
            return ReleaseResult(
                decision=ReleaseDecision.REJECT_FALSE_CERTAINTY,
                failed_requirements=[f"proof chain invalid: {chain.reason}"],
            )
        records = self._mission_proofs(request)
        proof_failures, _ = self._validate_proofs(request, records)
        claim_failures = self._validate_claims(request)
        action_failures = self._validate_external_action(request)
        failures = [*proof_failures, *claim_failures, *action_failures]

        if action_failures:
            decision = ReleaseDecision.HOLD_FOR_APPROVAL
        elif any("source completeness" in failure or "inventory" in failure for failure in failures):
            decision = ReleaseDecision.HOLD_FOR_EVIDENCE
        elif any("council" in failure for failure in failures):
            decision = ReleaseDecision.HOLD_FOR_COUNCIL
        elif failures:
            decision = ReleaseDecision.REJECT_FALSE_CERTAINTY
        elif request.noncritical_unknowns:
            decision = ReleaseDecision.RELEASE_WITH_BOUNDED_CAVEAT
        else:
            decision = ReleaseDecision.RELEASE

        if decision not in {ReleaseDecision.RELEASE, ReleaseDecision.RELEASE_WITH_BOUNDED_CAVEAT}:
            return ReleaseResult(
                decision=decision,
                verified_proof_ids=[record.proof_id for record in records],
                failed_requirements=failures,
                caveats=["Release was withheld by the proof-bound gate."],
                proof_chain_head=chain.head_hash,
            )

        release_proof = self.ledger.append(
            ProofAppendRequest(
                matter_id=request.matter_id,
                mission_id=request.mission_id,
                proof_type=ProofType.RELEASE_DECISION,
                subject_id=new_id("RELEASE"),
                actor_id=actor_id,
                source_ids=request.claim_ids,
                payload={
                    "decision": decision.value,
                    "claim_ids": request.claim_ids,
                    "verified_proof_ids": [record.proof_id for record in records],
                    "requirements": request.requirements.model_dump(mode="json"),
                    "noncritical_unknowns": request.noncritical_unknowns,
                    "pre_release_chain_head": chain.head_hash,
                },
            )
        )
        post_chain = self.ledger.verify_chain(request.matter_id)
        if not post_chain.valid:
            return ReleaseResult(
                decision=ReleaseDecision.REJECT_FALSE_CERTAINTY,
                failed_requirements=["release proof could not be verified in the chain"],
            )
        receipt_id = new_id("RLS")
        receipt_payload = {
            "release_receipt_id": receipt_id,
            "matter_id": request.matter_id,
            "mission_id": request.mission_id,
            "decision": decision.value,
            "claim_ids": request.claim_ids,
            "proof_ids": [record.proof_id for record in records] + [release_proof.proof_id],
            "chain_head": post_chain.head_hash,
            "caveats": request.noncritical_unknowns,
        }
        self.repo.execute(
            """INSERT INTO release_receipts(
               release_receipt_id,matter_id,mission_id,decision,claim_ids_json,proof_ids_json,
               chain_head,caveats_json,payload_hash,created_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                receipt_id,
                request.matter_id,
                request.mission_id,
                decision.value,
                self.repo.dumps(request.claim_ids),
                self.repo.dumps(receipt_payload["proof_ids"]),
                post_chain.head_hash or "",
                self.repo.dumps(request.noncritical_unknowns),
                sha256_json(receipt_payload),
                self.repo.now(),
            ),
        )
        return ReleaseResult(
            decision=decision,
            release_receipt_id=receipt_id,
            verified_proof_ids=receipt_payload["proof_ids"],
            caveats=request.noncritical_unknowns,
            proof_chain_head=post_chain.head_hash,
        )

    def get_receipt(self, release_receipt_id: str) -> dict[str, Any] | None:
        row = self.repo.fetch_one(
            "SELECT * FROM release_receipts WHERE release_receipt_id=?", (release_receipt_id,)
        )
        return dict(row) if row else None
