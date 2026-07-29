from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .audit import AuditLog
from .canonical import sha256_json
from .db import Repository
from .ids import new_id
from .proof_ledger import ProofLedger
from .schemas import (
    ApprovalCreateRequest,
    ApprovalDecisionRequest,
    ApprovalRecord,
    ApprovalStatus,
    ProofAppendRequest,
    ProofType,
)


class ApprovalService:
    def __init__(self, repo: Repository, ledger: ProofLedger, audit: AuditLog):
        self.repo = repo
        self.ledger = ledger
        self.audit = audit

    @staticmethod
    def action_digest(action_type: str, exact_parameters: dict[str, Any]) -> str:
        return sha256_json({"action_type": action_type, "exact_parameters": exact_parameters})

    def create(self, request: ApprovalCreateRequest) -> ApprovalRecord:
        self.repo.ensure_matter(request.matter_id)
        approval_id = new_id("APR")
        created_at = datetime.now(UTC)
        digest = self.action_digest(request.action_type.value, request.exact_parameters)
        self.repo.execute(
            """INSERT INTO approvals(
               approval_id,matter_id,mission_id,action_type,action_digest,parameters_json,
               status,requested_by,expires_at,created_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                approval_id,
                request.matter_id,
                request.mission_id,
                request.action_type.value,
                digest,
                self.repo.dumps(request.exact_parameters),
                ApprovalStatus.PENDING.value,
                request.requested_by,
                request.expires_at.isoformat() if request.expires_at else None,
                created_at.isoformat(),
            ),
        )
        self.audit.append(
            actor_id=request.requested_by,
            event_type="APPROVAL_REQUESTED",
            matter_id=request.matter_id,
            object_id=approval_id,
            payload={"action_type": request.action_type.value, "action_digest": digest},
        )
        return self.get(approval_id)  # type: ignore[return-value]

    @staticmethod
    def _from_row(row: Any) -> ApprovalRecord:
        from .schemas import ExternalActionType

        return ApprovalRecord(
            approval_id=row["approval_id"],
            matter_id=row["matter_id"],
            mission_id=row["mission_id"],
            action_type=ExternalActionType(row["action_type"]),
            action_digest=row["action_digest"],
            exact_parameters=json_load(row["parameters_json"]),
            status=ApprovalStatus(row["status"]),
            requested_by=row["requested_by"],
            decided_by=row["decided_by"],
            decision_reason=row["decision_reason"],
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            decided_at=datetime.fromisoformat(row["decided_at"]) if row["decided_at"] else None,
        )

    def get(self, approval_id: str) -> ApprovalRecord | None:
        row = self.repo.fetch_one("SELECT * FROM approvals WHERE approval_id=?", (approval_id,))
        return self._from_row(row) if row else None

    def decide(self, approval_id: str, decision: ApprovalDecisionRequest) -> tuple[ApprovalRecord, str]:
        approval = self.get(approval_id)
        if approval is None:
            raise ValueError("Unknown approval")
        if approval.status != ApprovalStatus.PENDING:
            raise ValueError(f"Approval is not pending: {approval.status.value}")
        now = datetime.now(UTC)
        if approval.expires_at and approval.expires_at <= now:
            self.repo.execute(
                "UPDATE approvals SET status=?, decided_at=? WHERE approval_id=?",
                (ApprovalStatus.EXPIRED.value, now.isoformat(), approval_id),
            )
            raise ValueError("Approval has expired")
        status = ApprovalStatus.APPROVED if decision.approve else ApprovalStatus.REJECTED
        self.repo.execute(
            """UPDATE approvals SET status=?,decided_by=?,decision_reason=?,decided_at=?
               WHERE approval_id=?""",
            (status.value, decision.decided_by, decision.reason, now.isoformat(), approval_id),
        )
        proof = self.ledger.append(
            ProofAppendRequest(
                matter_id=approval.matter_id,
                mission_id=approval.mission_id,
                proof_type=ProofType.APPROVAL,
                subject_id=approval_id,
                actor_id=decision.decided_by,
                source_ids=[],
                payload={
                    "approval_id": approval_id,
                    "action_type": approval.action_type.value,
                    "action_digest": approval.action_digest,
                    "decision": status.value,
                    "reason": decision.reason,
                    "exact_parameters": approval.exact_parameters,
                },
            )
        )
        self.audit.append(
            actor_id=decision.decided_by,
            event_type=f"APPROVAL_{status.value}",
            matter_id=approval.matter_id,
            object_id=approval_id,
            payload={"proof_id": proof.proof_id, "reason": decision.reason},
        )
        decided = self.get(approval_id)
        assert decided is not None
        return decided, proof.proof_id

    def begin_execution(self, approval_id: str, action_digest: str) -> ApprovalRecord:
        with self.repo.connect(immediate=True) as conn:
            row = conn.execute("SELECT * FROM approvals WHERE approval_id=?", (approval_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown approval")
            if row["status"] != ApprovalStatus.APPROVED.value:
                raise ValueError("Approval is not approved and available")
            if row["action_digest"] != action_digest:
                raise ValueError("Executed action does not match approved parameters")
            expires_at = datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None
            if expires_at and expires_at <= datetime.now(UTC):
                conn.execute(
                    "UPDATE approvals SET status=?, decided_at=? WHERE approval_id=?",
                    (ApprovalStatus.EXPIRED.value, datetime.now(UTC).isoformat(), approval_id),
                )
                raise ValueError("Approval has expired")
            conn.execute(
                "UPDATE approvals SET status=? WHERE approval_id=?",
                (ApprovalStatus.EXECUTING.value, approval_id),
            )
        record = self.get(approval_id)
        assert record is not None
        return record

    def complete_execution(self, approval_id: str) -> None:
        with self.repo.connect(immediate=True) as conn:
            row = conn.execute("SELECT status FROM approvals WHERE approval_id=?", (approval_id,)).fetchone()
            if row is None or row["status"] != ApprovalStatus.EXECUTING.value:
                raise ValueError("Approval is not in execution")
            conn.execute(
                "UPDATE approvals SET status=?, consumed_at=? WHERE approval_id=?",
                (ApprovalStatus.CONSUMED.value, datetime.now(UTC).isoformat(), approval_id),
            )

    def mark_execution_uncertain(self, approval_id: str, reason: str) -> None:
        with self.repo.connect(immediate=True) as conn:
            row = conn.execute("SELECT status FROM approvals WHERE approval_id=?", (approval_id,)).fetchone()
            if row is None:
                return
            if row["status"] == ApprovalStatus.EXECUTING.value:
                conn.execute(
                    "UPDATE approvals SET status=?, decision_reason=? WHERE approval_id=?",
                    (ApprovalStatus.EXECUTION_UNCERTAIN.value, reason[:4000], approval_id),
                )


def json_load(value: str) -> dict[str, Any]:
    import json

    loaded = json.loads(value)
    if not isinstance(loaded, dict):
        raise ValueError("Expected JSON object")
    return loaded
