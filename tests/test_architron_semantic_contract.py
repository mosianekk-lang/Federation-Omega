import pytest

from ops.architron_semantic_contract import SemanticContractError, validate_action_response


def _generic_health():
    return {
        "body": {
            "runtime": "architron-unified-core",
            "version": "v11.0-UNIFIED-SOVEREIGNTY",
            "cloudRunService": "architron9",
            "project": "sov-hybrid-suite",
            "healthOk": True,
        }
    }


@pytest.mark.parametrize(
    "action",
    [
        "GET_RUNTIME_IDENTITY",
        "GET_PROJECT_INFO",
        "GET_CLOUD_RUN_SERVICE",
        "LIST_CLOUD_RUN_SERVICES",
        "LIST_CLOUD_BUILD_BUILDS",
        "LIST_CLOUD_SCHEDULER_JOBS",
        "LIST_CLOUD_SCHEDULER_JOBS_ALL_REGIONS",
        "LIST_PUBSUB_TOPICS",
        "LIST_SERVICE_ACCOUNTS",
        "LIST_SECRET_NAMES",
    ],
)
def test_provider_actions_reject_generic_health(action):
    with pytest.raises(SemanticContractError, match="collapsed to generic runtime health"):
        validate_action_response(action, _generic_health())


def test_identity_accepts_action_specific_payload():
    body = {
        "runtimeIdentity": {
            "principal": "example@project.iam.gserviceaccount.com",
            "identitySource": "provider",
        }
    }
    assert validate_action_response("GET_RUNTIME_IDENTITY", {"body": body}) == body


def test_project_requires_id_and_number():
    with pytest.raises(SemanticContractError, match="projectNumber"):
        validate_action_response(
            "GET_PROJECT_INFO", {"body": {"projectInfo": {"projectId": "example"}}}
        )

    body = {"projectInfo": {"projectId": "example", "projectNumber": "123"}}
    assert validate_action_response("GET_PROJECT_INFO", {"body": body}) == body


def test_service_requires_identity_and_provider_locator():
    with pytest.raises(SemanticContractError, match="at least one provider field"):
        validate_action_response(
            "GET_CLOUD_RUN_SERVICE",
            {"body": {"service": {"name": "architron9", "region": "africa-south1"}}},
        )

    body = {
        "service": {
            "name": "architron9",
            "region": "africa-south1",
            "latestReadyRevision": "architron9-00001-test",
        }
    }
    assert validate_action_response("GET_CLOUD_RUN_SERVICE", {"body": body}) == body


@pytest.mark.parametrize(
    ("action", "key"),
    [
        ("LIST_CLOUD_RUN_SERVICES", "services"),
        ("LIST_CLOUD_BUILD_BUILDS", "builds"),
        ("LIST_CLOUD_SCHEDULER_JOBS", "jobs"),
        ("LIST_CLOUD_SCHEDULER_JOBS_ALL_REGIONS", "jobs"),
        ("LIST_PUBSUB_TOPICS", "topics"),
        ("LIST_SERVICE_ACCOUNTS", "serviceAccounts"),
        ("LIST_SECRET_NAMES", "secretNames"),
    ],
)
def test_inventory_actions_require_typed_lists(action, key):
    with pytest.raises(SemanticContractError, match="not a list"):
        validate_action_response(action, {"body": {key: {"wrong": "shape"}}})

    body = {key: []}
    assert validate_action_response(action, {"body": body}) == body
