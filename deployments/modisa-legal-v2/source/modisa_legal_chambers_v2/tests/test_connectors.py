import pytest

from modisa_v2.connectors import ConnectorCapability, ConnectorContract
from modisa_v2.schemas import ExternalActionType


def test_connector_requires_verified_canary(services):
    services.connectors.register(
        ConnectorContract(
            connector_id="CONN-X",
            provider="test",
            capabilities=[ConnectorCapability.SEND_EMAIL],
            credential_ref="secret-manager://test/x",
            least_privilege_scopes=["send:email"],
        )
    )
    with pytest.raises(RuntimeError):
        services.connectors.assert_action_ready("CONN-X", ExternalActionType.EMAIL_SEND)


def test_plaintext_secret_is_rejected_as_credential_reference(services):
    with pytest.raises(ValueError):
        services.connectors.register(
            ConnectorContract(
                connector_id="CONN-BAD",
                provider="test",
                capabilities=[ConnectorCapability.SEND_EMAIL],
                credential_ref="token=plaintext-secret",
                least_privilege_scopes=["send:email"],
            )
        )
