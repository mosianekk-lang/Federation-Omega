import json

import pytest

from federation_omni_mesh_v1.provider_preflight import (
    CommandResult,
    build_identity_receipt,
    parse_wif_provider,
)


PROJECT_ID = "example-project"
PROJECT_NUMBER = "123456789012"
PROVIDER = (
    "projects/123456789012/locations/global/"
    "workloadIdentityPools/github-pool/providers/github"
)
DEPLOYER = "deployer@example-project.iam.gserviceaccount.com"


class FakeRunner:
    def __init__(self, *, project_number=PROJECT_NUMBER, fail_provider=False):
        self.project_number = project_number
        self.fail_provider = fail_provider
        self.commands = []

    def __call__(self, args):
        self.commands.append(tuple(args))
        command = " ".join(args)
        if "auth list" in command:
            return CommandResult(
                True,
                0,
                json.dumps([{"account": DEPLOYER}]),
                "",
            )
        if "projects describe" in command:
            return CommandResult(
                True,
                0,
                json.dumps(
                    {
                        "projectId": PROJECT_ID,
                        "projectNumber": self.project_number,
                        "lifecycleState": "ACTIVE",
                    }
                ),
                "",
            )
        if "workload-identity-pools providers describe" in command:
            if self.fail_provider:
                return CommandResult(False, 1, "", "not found")
            return CommandResult(
                True,
                0,
                json.dumps(
                    {
                        "name": PROVIDER,
                        "state": "ACTIVE",
                        "attributeMapping": {
                            "google.subject": "assertion.sub"
                        },
                        "attributeCondition": (
                            "assertion.repository_owner=='owner'"
                        ),
                    }
                ),
                "",
            )
        if "service-accounts describe" in command:
            return CommandResult(
                True,
                0,
                json.dumps(
                    {
                        "email": DEPLOYER,
                        "disabled": False,
                    }
                ),
                "",
            )
        if "service-accounts get-iam-policy" in command:
            return CommandResult(
                True,
                0,
                json.dumps(
                    {
                        "bindings": [
                            {
                                "role": (
                                    "roles/iam.workloadIdentityUser"
                                ),
                                "members": ["principalSet://example"],
                            }
                        ],
                    }
                ),
                "",
            )
        if "projects get-iam-policy" in command:
            return CommandResult(
                True,
                0,
                json.dumps(
                    {
                        "bindings": [
                            {
                                "role": "roles/viewer",
                                "members": [
                                    f"serviceAccount:{DEPLOYER}"
                                ],
                            }
                        ],
                    }
                ),
                "",
            )
        if "services list" in command:
            return CommandResult(
                True,
                0,
                json.dumps(
                    [
                        {
                            "config": {
                                "name": "run.googleapis.com"
                            },
                            "state": "ENABLED",
                        },
                        {
                            "config": {
                                "name": "pubsub.googleapis.com"
                            },
                            "state": "ENABLED",
                        },
                    ]
                ),
                "",
            )
        raise AssertionError(f"unexpected command: {command}")


def test_parse_wif_provider_requires_full_resource():
    parsed = parse_wif_provider(PROVIDER)
    assert parsed["project_number"] == PROJECT_NUMBER
    assert parsed["pool"] == "github-pool"
    assert parsed["provider"] == "github"
    with pytest.raises(ValueError, match="invalid"):
        parse_wif_provider("github")


def test_identity_preflight_verifies_read_only_provider_state():
    runner = FakeRunner()
    receipt = build_identity_receipt(
        project_id=PROJECT_ID,
        expected_project_number=PROJECT_NUMBER,
        wif_provider=PROVIDER,
        deployer_service_account=DEPLOYER,
        required_apis=[
            "run.googleapis.com",
            "pubsub.googleapis.com",
        ],
        runner=runner,
    )
    assert (
        receipt["classification"]
        == "PROVIDER_IDENTITY_PREFLIGHT_VERIFIED"
    )
    assert receipt["mutation_attempted"] is False
    assert receipt["secret_values_read"] is False
    assert receipt["source_repository_mutated"] is False
    assert len(receipt["receipt_sha256"]) == 64
    command_text = "\n".join(" ".join(c) for c in runner.commands)
    assert "secrets versions access" not in command_text
    assert "git push" not in command_text


def test_identity_preflight_holds_project_number_mismatch():
    runner = FakeRunner(project_number="999999999999")
    receipt = build_identity_receipt(
        project_id=PROJECT_ID,
        expected_project_number=PROJECT_NUMBER,
        wif_provider=PROVIDER,
        deployer_service_account=DEPLOYER,
        required_apis=["run.googleapis.com"],
        runner=runner,
    )
    assert (
        receipt["classification"]
        == "PROVIDER_IDENTITY_PREFLIGHT_PARTIAL"
    )
    assert receipt["checks"]["project_number_match"] is False


def test_identity_preflight_holds_missing_provider():
    runner = FakeRunner(fail_provider=True)
    receipt = build_identity_receipt(
        project_id=PROJECT_ID,
        expected_project_number=PROJECT_NUMBER,
        wif_provider=PROVIDER,
        deployer_service_account=DEPLOYER,
        required_apis=["run.googleapis.com"],
        runner=runner,
    )
    assert receipt["checks"]["wif_provider_readable"] is False
    assert (
        receipt["classification"]
        == "PROVIDER_IDENTITY_PREFLIGHT_PARTIAL"
    )


def test_identity_preflight_rejects_cross_project_provider():
    with pytest.raises(ValueError, match="does not match"):
        build_identity_receipt(
            project_id=PROJECT_ID,
            expected_project_number=PROJECT_NUMBER,
            wif_provider=(
                "projects/999999999999/locations/global/"
                "workloadIdentityPools/github-pool/providers/github"
            ),
            deployer_service_account=DEPLOYER,
            required_apis=[],
            runner=FakeRunner(),
        )
