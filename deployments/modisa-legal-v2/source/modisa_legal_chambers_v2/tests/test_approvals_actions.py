from dataclasses import dataclass

import pytest

from modisa_v2.actions import ActionAdapter, ProviderExecution, ProviderReadback
from modisa_v2.connectors import ConnectorCapability, ConnectorContract
from modisa_v2.schemas import (
    ActionExecuteRequest,
    ApprovalCreateRequest,
    ApprovalDecisionRequest,
    ExternalActionType,
)


@dataclass
class FakeEmailAdapter(ActionAdapter):
    connector_id = "CONN-EMAIL"
    action_type = ExternalActionType.EMAIL_SEND

    def health_canary(self):
        return {"ok": True, "readback": "verified"}

    def execute(self, exact_parameters):
        return ProviderExecution("provider-123", "SUCCESS", {"accepted": True})

    def readback(self, provider_action_id, exact_parameters):
        return ProviderReadback("CONFIRMED", True, {"id": provider_action_id})


def bind_verified_email_connector(services, adapter):
    services.repo.ensure_matter("MAT-CONNECTOR")
    services.connectors.register(
        ConnectorContract(
            connector_id="CONN-EMAIL",
            provider="fake-email",
            capabilities=[ConnectorCapability.SEND_EMAIL],
            credential_ref="secret-manager://test/email",
            least_privilege_scopes=["send:email"],
        )
    )
    services.connectors.run_canary(
        connector_id="CONN-EMAIL",
        matter_id="MAT-CONNECTOR",
        mission_id="MIS-CONNECTOR",
        actor_id="tester",
        adapter=adapter,
    )
    services.actions.bind(adapter)


def test_exact_approval_execution_and_readback(services):
    services.actions.enabled = True
    bind_verified_email_connector(services, FakeEmailAdapter())
    approval = services.approvals.create(
        ApprovalCreateRequest(
            matter_id="MAT-A",
            mission_id="MIS-A",
            action_type=ExternalActionType.EMAIL_SEND,
            exact_parameters={"recipient": "person@example.com", "subject": "Notice", "body": "Text"},
            requested_by="counsel",
        )
    )
    services.approvals.decide(
        approval.approval_id,
        ApprovalDecisionRequest(approve=True, decided_by="owner", reason="Approved exactly"),
    )
    receipt = services.actions.execute(
        ActionExecuteRequest(
            approval_id=approval.approval_id,
            action_type=ExternalActionType.EMAIL_SEND,
            exact_parameters={"recipient": "person@example.com", "subject": "Notice", "body": "Text"},
            executor_id="connector",
        )
    )
    assert receipt.provider_action_id == "provider-123"
    assert receipt.readback_status == "CONFIRMED"


def test_parameter_drift_is_rejected(services):
    services.actions.enabled = True
    bind_verified_email_connector(services, FakeEmailAdapter())
    approval = services.approvals.create(
        ApprovalCreateRequest(
            matter_id="MAT-A2",
            mission_id="MIS-A2",
            action_type=ExternalActionType.EMAIL_SEND,
            exact_parameters={"recipient": "a@example.com", "subject": "A", "body": "A"},
            requested_by="counsel",
        )
    )
    services.approvals.decide(
        approval.approval_id,
        ApprovalDecisionRequest(approve=True, decided_by="owner", reason="Approved"),
    )
    with pytest.raises(ValueError):
        services.actions.execute(
            ActionExecuteRequest(
                approval_id=approval.approval_id,
                action_type=ExternalActionType.EMAIL_SEND,
                exact_parameters={"recipient": "b@example.com", "subject": "A", "body": "A"},
                executor_id="connector",
            )
        )


@dataclass
class FailingEmailAdapter(ActionAdapter):
    connector_id = "CONN-EMAIL"
    action_type = ExternalActionType.EMAIL_SEND

    def health_canary(self):
        return {"ok": True, "readback": "verified"}

    def execute(self, exact_parameters):
        raise RuntimeError("provider timeout")

    def readback(self, provider_action_id, exact_parameters):
        raise AssertionError("readback should not be called")


def test_uncertain_execution_cannot_be_silently_retried(services):
    services.actions.enabled = True
    bind_verified_email_connector(services, FailingEmailAdapter())
    approval = services.approvals.create(
        ApprovalCreateRequest(
            matter_id="MAT-U",
            mission_id="MIS-U",
            action_type=ExternalActionType.EMAIL_SEND,
            exact_parameters={"recipient": "a@example.com", "subject": "A", "body": "A"},
            requested_by="counsel",
        )
    )
    services.approvals.decide(
        approval.approval_id,
        ApprovalDecisionRequest(approve=True, decided_by="owner", reason="Approved"),
    )
    with pytest.raises(RuntimeError):
        services.actions.execute(
            ActionExecuteRequest(
                approval_id=approval.approval_id,
                action_type=ExternalActionType.EMAIL_SEND,
                exact_parameters={"recipient": "a@example.com", "subject": "A", "body": "A"},
                executor_id="connector",
            )
        )
    assert services.approvals.get(approval.approval_id).status.value == "EXECUTION_UNCERTAIN"
    with pytest.raises(ValueError):
        services.actions.execute(
            ActionExecuteRequest(
                approval_id=approval.approval_id,
                action_type=ExternalActionType.EMAIL_SEND,
                exact_parameters={"recipient": "a@example.com", "subject": "A", "body": "A"},
                executor_id="connector",
            )
        )
