from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field

from .db import Repository
from .proof_ledger import ProofLedger
from .schemas import ExternalActionType, ProofAppendRequest, ProofType


class ConnectorCapability(StrEnum):
    READ_EMAIL = "READ_EMAIL"
    READ_DRIVE = "READ_DRIVE"
    SEARCH_PRIMARY_LAW = "SEARCH_PRIMARY_LAW"
    SEND_EMAIL = "SEND_EMAIL"
    SHARE_FILE = "SHARE_FILE"
    WRITE_CALENDAR = "WRITE_CALENDAR"
    LEGAL_FILING = "LEGAL_FILING"
    PRODUCTION_DEPLOYMENT = "PRODUCTION_DEPLOYMENT"


ACTION_CAPABILITY = {
    ExternalActionType.EMAIL_SEND: ConnectorCapability.SEND_EMAIL,
    ExternalActionType.FILE_SHARE: ConnectorCapability.SHARE_FILE,
    ExternalActionType.LEGAL_FILING: ConnectorCapability.LEGAL_FILING,
    ExternalActionType.PRODUCTION_DEPLOYMENT: ConnectorCapability.PRODUCTION_DEPLOYMENT,
}


class ConnectorContract(BaseModel):
    connector_id: str
    provider: str
    capabilities: list[ConnectorCapability]
    credential_ref: str = Field(description="Secret-manager reference only; never a credential value")
    least_privilege_scopes: list[str]
    status: str = "REGISTERED_UNVERIFIED"
    last_canary_at: datetime | None = None
    last_canary_proof_id: str | None = None


class HealthCapableAdapter(Protocol):
    connector_id: str

    def health_canary(self) -> dict[str, object]: ...


class ConnectorRegistry:
    def __init__(self, repo: Repository, ledger: ProofLedger):
        self.repo = repo
        self.ledger = ledger

    def register(self, contract: ConnectorContract) -> ConnectorContract:
        if not contract.credential_ref or any(token in contract.credential_ref.lower() for token in ("sk-", "password=", "token=")):
            raise ValueError("credential_ref must be an opaque secret-manager reference, not a secret")
        now = self.repo.now()
        self.repo.execute(
            """INSERT INTO connector_contracts(
               connector_id,provider,capabilities_json,credential_ref,least_privilege_scopes_json,
               status,last_canary_at,last_canary_proof_id,created_at,updated_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(connector_id) DO UPDATE SET
                 provider=excluded.provider,
                 capabilities_json=excluded.capabilities_json,
                 credential_ref=excluded.credential_ref,
                 least_privilege_scopes_json=excluded.least_privilege_scopes_json,
                 status='REGISTERED_UNVERIFIED',
                 last_canary_at=NULL,
                 last_canary_proof_id=NULL,
                 updated_at=excluded.updated_at""",
            (
                contract.connector_id,
                contract.provider,
                self.repo.dumps([item.value for item in contract.capabilities]),
                contract.credential_ref,
                self.repo.dumps(contract.least_privilege_scopes),
                "REGISTERED_UNVERIFIED",
                None,
                None,
                now,
                now,
            ),
        )
        result = self.get(contract.connector_id)
        assert result is not None
        return result

    def get(self, connector_id: str) -> ConnectorContract | None:
        row = self.repo.fetch_one("SELECT * FROM connector_contracts WHERE connector_id=?", (connector_id,))
        if row is None:
            return None
        return ConnectorContract(
            connector_id=row["connector_id"],
            provider=row["provider"],
            capabilities=[ConnectorCapability(value) for value in self.repo.loads(row["capabilities_json"], [])],
            credential_ref=row["credential_ref"],
            least_privilege_scopes=self.repo.loads(row["least_privilege_scopes_json"], []),
            status=row["status"],
            last_canary_at=datetime.fromisoformat(row["last_canary_at"]) if row["last_canary_at"] else None,
            last_canary_proof_id=row["last_canary_proof_id"],
        )

    def run_canary(
        self,
        *,
        connector_id: str,
        matter_id: str,
        mission_id: str,
        actor_id: str,
        adapter: HealthCapableAdapter,
    ) -> ConnectorContract:
        contract = self.get(connector_id)
        if contract is None:
            raise ValueError("Unknown connector contract")
        if adapter.connector_id != connector_id:
            raise ValueError("Adapter and connector contract IDs differ")
        result = adapter.health_canary()
        if result.get("ok") is not True:
            raise RuntimeError("Connector health canary failed")
        proof = self.ledger.append(
            ProofAppendRequest(
                matter_id=matter_id,
                mission_id=mission_id,
                proof_type=ProofType.WRITE_READBACK,
                subject_id=connector_id,
                actor_id=actor_id,
                payload={
                    "connector_id": connector_id,
                    "provider": contract.provider,
                    "health_canary": result,
                    "readback_verified": True,
                },
            )
        )
        now = datetime.now(UTC)
        self.repo.execute(
            """UPDATE connector_contracts SET status=?,last_canary_at=?,last_canary_proof_id=?,updated_at=?
               WHERE connector_id=?""",
            ("VERIFIED_ACTIVE", now.isoformat(), proof.proof_id, now.isoformat(), connector_id),
        )
        updated = self.get(connector_id)
        assert updated is not None
        return updated

    def assert_action_ready(self, connector_id: str, action_type: ExternalActionType) -> ConnectorContract:
        contract = self.get(connector_id)
        if contract is None:
            raise RuntimeError("Action connector is not registered")
        required = ACTION_CAPABILITY.get(action_type)
        if required is None:
            raise RuntimeError(f"No connector capability mapping for {action_type.value}")
        if required not in contract.capabilities:
            raise RuntimeError(f"Connector lacks capability {required.value}")
        if contract.status != "VERIFIED_ACTIVE" or not contract.last_canary_proof_id:
            raise RuntimeError("Connector has no current verified canary")
        proof = self.ledger.get(contract.last_canary_proof_id)
        if proof is None or not self.ledger.verify_record(proof)[0]:
            raise RuntimeError("Connector canary proof is invalid")
        return contract
