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


def test_identity_rejects_generic_health():
    try:
        validate_action_response("GET_RUNTIME_IDENTITY", _generic_health())
    except SemanticContractError as exc:
        assert "collapsed to generic runtime health" in str(exc)
    else:
        raise AssertionError("generic health must not satisfy identity proof")


def test_project_rejects_generic_health():
    try:
        validate_action_response("GET_PROJECT_INFO", _generic_health())
    except SemanticContractError:
        pass
    else:
        raise AssertionError("generic health must not satisfy project proof")


def test_service_rejects_generic_health():
    try:
        validate_action_response("GET_CLOUD_RUN_SERVICE", _generic_health())
    except SemanticContractError:
        pass
    else:
        raise AssertionError("generic health must not satisfy service proof")


def test_identity_accepts_action_specific_payload():
    body = {"runtimeIdentity": {"principal": "example@project.iam.gserviceaccount.com"}}
    assert validate_action_response("GET_RUNTIME_IDENTITY", {"body": body}) == body


def test_project_accepts_action_specific_payload():
    body = {"projectInfo": {"projectId": "sov-hybrid-suite"}}
    assert validate_action_response("GET_PROJECT_INFO", {"body": body}) == body


def test_service_accepts_action_specific_payload():
    body = {"service": {"name": "architron9", "region": "africa-south1"}}
    assert validate_action_response("GET_CLOUD_RUN_SERVICE", {"body": body}) == body
