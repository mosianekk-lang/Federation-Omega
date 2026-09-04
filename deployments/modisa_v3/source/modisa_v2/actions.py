from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from .approvals import ApprovalService
from .audit import AuditLog
from .connectors import ConnectorRegistry
from .db import Repository
from .ids import new_id
from .proof_ledger import ProofLedger
from .schemas import (
    ActionExecuteRequest,
    ActionReceipt,
    ExternalActionType,
    ProofAppendRequest,
    ProofType,
)


@dataclass(frozen=True)
class ProviderExecution:
    provider_action_id: str
    status: str
    response: dict[str, Any]


@dataclass(frozen=True)
class ProviderReadback:
    status: str
    confirmed: bool
    response: dict[str, Any]


class ActionAdapter(Protocol):
    connector_id: str
    action_type: ExternalActionType

    def execute(self, exact_parameters: dict[str, Any]) -> ProviderExecution: ...

    def readback(self, provider_action_id: str, exact_parameters: dict[str, Any]) -> ProviderReadback: ...


class NullActionAdapter:
    def __init__(self, action_type: ExternalActionType, connector_id: str = "NULL"):
        self.action_type = action_type
        self.connector_id = connector_id

    def execute(self, exact_parameters: dict[str, Any]) -> ProviderExecution:
        raise RuntimeError(f"No authorised {self.action_type.value} adapter is bound")

    def readback(self, provider_action_id: str, exact_parameters: dict[str, Any]) -> ProviderReadback:
        raise RuntimeError(f"No authorised {self.action_type.value} adapter is bound")


class ActionService:
    def __init__(
        self,
        repo: Repository,
        ledger: ProofLedger,
        approvals: ApprovalService,
        audit: AuditLog,
        connector_registry: ConnectorRegistry,
        adapters: dict[ExternalActionType, ActionAdapter] | None = None,
        *,
        enabled: bool = False,
    ):
        self.repo = repo
        self.ledger = ledger
        self.approvals = approvals
        self.audit = audit
        self.connector_registry = connector_registry
        self.adapters = adapters or {}
        self.enabled = enabled

    def bind(self, adapter: ActionAdapter) -> None:
        self.adapters[adapter.action_type] = adapter

    def execute(self, request: ActionExecuteRequest) -> ActionReceipt:
        if not self.enabled:
            raise RuntimeError("External actions are disabled")
        approval = self.approvals.get(request.approval_id)
        if approval is None:
            raise ValueError("Unknown approval")
        if approval.action_type != request.action_type:
            raise ValueError("Action type differs from approval")
        digest = self.approvals.action_digest(request.action_type.value, request.exact_parameters)
        if digest != approval.action_digest:
            raise ValueError("Action parameters differ from approval")
        adapter = self.adapters.get(request.action_type)
        if adapter is None:
            raise RuntimeError(f"No adapter bound for {request.action_type.value}")
        self.connector_registry.assert_action_ready(adapter.connector_id, request.action_type)

        self.approvals.begin_execution(request.approval_id, digest)
        try:
            execution = adapter.execute(request.exact_parameters)
        except Exception as exc:
            self.approvals.mark_execution_uncertain(request.approval_id, f"Execution error: {type(exc).__name__}: {exc}")
            self.audit.append(
                actor_id=request.executor_id,
                event_type="EXTERNAL_ACTION_EXECUTION_UNCERTAIN",
                matter_id=approval.matter_id,
                object_id=request.approval_id,
                payload={"error_type": type(exc).__name__},
            )
            raise
        execution_proof = self.ledger.append(
            ProofAppendRequest(
                matter_id=approval.matter_id,
                mission_id=approval.mission_id,
                proof_type=ProofType.ACTION_EXECUTION,
                subject_id=request.approval_id,
                actor_id=request.executor_id,
                source_ids=[],
                payload={
                    "approval_id": request.approval_id,
                    "action_type": request.action_type.value,
                    "action_digest": digest,
                    "provider_action_id": execution.provider_action_id,
                    "provider_status": execution.status,
                    "response": execution.response,
                },
            )
        )
        try:
            readback = adapter.readback(execution.provider_action_id, request.exact_parameters)
        except Exception as exc:
            self.approvals.mark_execution_uncertain(request.approval_id, f"Readback error: {type(exc).__name__}: {exc}")
            raise
        if not readback.confirmed:
            self.approvals.mark_execution_uncertain(request.approval_id, "Provider readback did not confirm the action")
            raise RuntimeError("Provider action could not be independently read back")
        readback_proof = self.ledger.append(
            ProofAppendRequest(
                matter_id=approval.matter_id,
                mission_id=approval.mission_id,
                proof_type=ProofType.ACTION_READBACK,
                subject_id=execution.provider_action_id,
                actor_id=request.executor_id,
                source_ids=[],
                payload={
                    "provider_action_id": execution.provider_action_id,
                    "readback_status": readback.status,
                    "confirmed": readback.confirmed,
                    "response": readback.response,
                    "action_digest": digest,
                },
            )
        )
        self.approvals.complete_execution(request.approval_id)
        receipt_id = new_id("ACTION")
        created_at = datetime.fromisoformat(self.repo.now())
        self.repo.execute(
            """INSERT INTO action_receipts(
               action_receipt_id,approval_id,matter_id,mission_id,action_type,action_digest,
               provider_action_id,provider_status,readback_status,execution_proof_id,
               readback_proof_id,created_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                receipt_id,
                approval.approval_id,
                approval.matter_id,
                approval.mission_id,
                request.action_type.value,
                digest,
                execution.provider_action_id,
                execution.status,
                readback.status,
                execution_proof.proof_id,
                readback_proof.proof_id,
                created_at.isoformat(),
            ),
        )
        self.audit.append(
            actor_id=request.executor_id,
            event_type="EXTERNAL_ACTION_VERIFIED",
            matter_id=approval.matter_id,
            object_id=receipt_id,
            payload={
                "approval_id": approval.approval_id,
                "provider_action_id": execution.provider_action_id,
                "execution_proof_id": execution_proof.proof_id,
                "readback_proof_id": readback_proof.proof_id,
            },
        )
        return ActionReceipt(
            action_receipt_id=receipt_id,
            approval_id=approval.approval_id,
            matter_id=approval.matter_id,
            mission_id=approval.mission_id,
            action_type=request.action_type,
            action_digest=digest,
            provider_action_id=execution.provider_action_id,
            provider_status=execution.status,
            readback_status=readback.status,
            execution_proof_id=execution_proof.proof_id,
            readback_proof_id=readback_proof.proof_id,
            created_at=created_at,
        )

    def get_receipt(self, action_receipt_id: str) -> ActionReceipt | None:
        row = self.repo.fetch_one(
            "SELECT * FROM action_receipts WHERE action_receipt_id=?", (action_receipt_id,)
        )
        if row is None:
            return None
        return ActionReceipt(
            action_receipt_id=row["action_receipt_id"],
            approval_id=row["approval_id"],
            matter_id=row["matter_id"],
            mission_id=row["mission_id"],
            action_type=ExternalActionType(row["action_type"]),
            action_digest=row["action_digest"],
            provider_action_id=row["provider_action_id"],
            provider_status=row["provider_status"],
            readback_status=row["readback_status"],
            execution_proof_id=row["execution_proof_id"],
            readback_proof_id=row["readback_proof_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
