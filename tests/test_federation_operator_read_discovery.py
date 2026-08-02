from __future__ import annotations

import io
import json
import unittest
import urllib.error
from email.message import Message
from typing import Any

from federation_operator import (
    DEFAULT_GITHUB_CONFIGURATION_ALLOWLIST,
    READ_GITHUB_ACTIONS_CONFIG_PRESENCE,
    READ_WIF_PROVIDER_METADATA,
    FederationReadDiscovery,
    GitHubActionsEnvironmentPresenceReader,
    GoogleIamProviderClient,
    execute_kdv_l017_sequence,
)

RESOURCE = (
    "projects/257649435135/locations/global/workloadIdentityPools/"
    "github-federation-omega/providers/github"
)


class DummyResponse:
    def __init__(
        self,
        body: object,
        *,
        content_type: str = "application/json",
        status: int = 200,
        final_url: str | None = None,
    ):
        if isinstance(body, bytes):
            self.body = body
        elif isinstance(body, str):
            self.body = body.encode()
        else:
            self.body = json.dumps(body).encode()
        self.status = status
        self.final_url = final_url
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, size: int = -1) -> bytes:
        return self.body if size < 0 else self.body[:size]

    def geturl(self) -> str | None:
        return self.final_url


class SpyOpener:
    def __init__(self, response: object):
        self.response = response
        self.calls: list[tuple[Any, int]] = []

    def __call__(self, request, *, timeout: int):
        self.calls.append((request, timeout))
        if isinstance(self.response, BaseException):
            raise self.response
        return DummyResponse(self.response, final_url=request.full_url)


class ReadDiscoveryTests(unittest.TestCase):
    def build(self, upstream: object, *, token_supplier=None, configuration_environment=None):
        opener = SpyOpener(upstream)
        supplier_calls: list[bool] = []

        def supplier():
            supplier_calls.append(True)
            return "unit-test-runtime-token"

        client = GoogleIamProviderClient(
            allowed_provider_resources={RESOURCE},
            access_token_supplier=token_supplier or supplier,
            opener=opener,
        )
        environment = {} if configuration_environment is None else configuration_environment
        configuration_reader = GitHubActionsEnvironmentPresenceReader(
            environment_supplier=lambda: environment,
        )
        return (
            FederationReadDiscovery(
                provider_client=client,
                configuration_reader=configuration_reader,
            ),
            opener,
            supplier_calls,
        )

    def payload(self, **changes):
        value = {
            "providerResource": RESOURCE,
            "purpose": "read-only WIF state diagnostic",
            "mutation": "NONE",
        }
        value.update(changes)
        return value

    def test_success_returns_only_minimal_allowlisted_metadata(self):
        upstream = {
            "name": RESOURCE,
            "state": "ACTIVE",
            "disabled": False,
            "expireTime": "2027-01-01T00:00:00Z",
            "attributeMapping": {
                "google.subject": "assertion.sub",
                "attribute.repository": "assertion.repository",
            },
            "attributeCondition": "assertion.repository == 'private/repository'",
            "oidc": {
                "issuerUri": "https://token.actions.githubusercontent.com",
                "allowedAudiences": ["sensitive-audience"],
                "jwksJson": "sensitive-jwks",
            },
            "accessToken": "upstream-token-that-must-not-escape",
        }
        service, opener, _ = self.build(upstream)
        result = service.execute(READ_WIF_PROVIDER_METADATA, self.payload())
        self.assertTrue(result["ok"])
        self.assertEqual("FOUND", result["classification"])
        self.assertEqual("GOOGLE_IAM_PROVIDER_METADATA", result["evidenceClass"])
        self.assertTrue(result["independentReadback"])
        self.assertFalse(result["tokenExchangeAttempted"])
        self.assertFalse(result["tokenExchangeVerified"])
        self.assertEqual(
            "METADATA_ACTIVE_TOKEN_EXCHANGE_UNVERIFIED",
            result["operationalClassification"],
        )
        self.assertEqual("FO_WIF_PROVIDER_METADATA_V1", result["contract"])
        self.assertEqual(
            {
                "nameMatchesRequest",
                "state",
                "disabled",
                "expiryPresent",
                "providerKind",
                "issuerClass",
                "attributeMappingKeys",
                "attributeConditionPresent",
            },
            set(result["provider"]),
        )
        serialized = json.dumps(result, sort_keys=True)
        for forbidden in (
            "unit-test-runtime-token",
            "upstream-token-that-must-not-escape",
            "sensitive-audience",
            "sensitive-jwks",
            "private/repository",
            "assertion.repository",
        ):
            self.assertNotIn(forbidden, serialized)
        request, timeout = opener.calls[0]
        self.assertEqual(
            "https://iam.googleapis.com/v1/" + RESOURCE,
            request.full_url,
        )
        self.assertEqual("GET", request.method)
        self.assertLessEqual(timeout, 30)

    def test_invalid_resource_is_rejected_before_credential_use(self):
        service, opener, supplier_calls = self.build({"name": RESOURCE})
        result = service.execute(
            READ_WIF_PROVIDER_METADATA,
            self.payload(providerResource="https://attacker.invalid/provider"),
        )
        self.assertEqual("PROVIDER_RESOURCE_INVALID", result["classification"])
        self.assertFalse(opener.calls)
        self.assertFalse(supplier_calls)

    def test_valid_but_unallowlisted_resource_is_rejected_before_credential_use(self):
        service, opener, supplier_calls = self.build({"name": RESOURCE})
        other = RESOURCE.replace("/providers/github", "/providers/other")
        result = service.execute(
            READ_WIF_PROVIDER_METADATA,
            self.payload(providerResource=other),
        )
        self.assertEqual("PROVIDER_RESOURCE_NOT_ALLOWLISTED", result["classification"])
        self.assertFalse(opener.calls)
        self.assertFalse(supplier_calls)

    def test_extra_payload_field_and_mutation_are_rejected(self):
        service, opener, _ = self.build({"name": RESOURCE})
        extra = service.execute(
            READ_WIF_PROVIDER_METADATA,
            {**self.payload(), "accessToken": "forbidden"},
        )
        mutation = service.execute(
            READ_WIF_PROVIDER_METADATA,
            self.payload(mutation="UPDATE"),
        )
        self.assertEqual("PAYLOAD_FIELD_NOT_ALLOWED", extra["classification"])
        self.assertEqual("READ_ACTION_REQUIRES_MUTATION_NONE", mutation["classification"])
        self.assertFalse(opener.calls)

    def test_http_failure_is_classified_without_returning_body(self):
        response = urllib.error.HTTPError(
            "https://iam.googleapis.com/v1/redacted",
            403,
            "body contains a credential",
            {},
            io.BytesIO(b'{"token":"must-not-escape"}'),
        )
        service, _, _ = self.build(response)
        result = service.execute(READ_WIF_PROVIDER_METADATA, self.payload())
        self.assertEqual("CALLER_UNAUTHORIZED", result["classification"])
        self.assertNotIn("must-not-escape", json.dumps(result))

    def test_invalid_upstream_and_resource_mismatch_fail_closed(self):
        invalid, _, _ = self.build(b"not-json")
        mismatch, _, _ = self.build({"name": RESOURCE.replace("github", "other")})
        self.assertEqual(
            "UPSTREAM_RESPONSE_INVALID",
            invalid.execute(READ_WIF_PROVIDER_METADATA, self.payload())["classification"],
        )
        self.assertEqual(
            "UPSTREAM_RESOURCE_IDENTITY_MISMATCH",
            mismatch.execute(READ_WIF_PROVIDER_METADATA, self.payload())["classification"],
        )

    def test_oversized_deep_or_multi_kind_upstream_response_is_rejected(self):
        oversized, _, _ = self.build(b"{" + b" " * 65_536 + b"}")
        deep: object = "leaf"
        for _ in range(18):
            deep = {"nested": deep}
        deeply_nested, _, _ = self.build({"name": RESOURCE, "oidc": {}, "extra": deep})
        multi_kind, _, _ = self.build({"name": RESOURCE, "oidc": {}, "aws": {}})
        for service in (oversized, deeply_nested, multi_kind):
            with self.subTest(service=service):
                result = service.execute(READ_WIF_PROVIDER_METADATA, self.payload())
                self.assertEqual("UPSTREAM_RESPONSE_INVALID", result["classification"])

    def test_redirect_is_rejected_and_never_retried(self):
        redirect = urllib.error.HTTPError(
            "https://iam.googleapis.com/v1/redacted",
            302,
            "redirect",
            {"Location": "https://attacker.invalid/steal"},
            io.BytesIO(b""),
        )
        service, opener, _ = self.build(redirect)
        result = service.execute(READ_WIF_PROVIDER_METADATA, self.payload())
        self.assertEqual("UPSTREAM_REDIRECT_REJECTED", result["classification"])
        self.assertEqual(1, len(opener.calls))

    def test_success_response_from_changed_final_url_is_rejected(self):
        class ChangedUrlOpener:
            def __init__(self):
                self.calls = 0

            def __call__(self, request, *, timeout: int):
                self.calls += 1
                return DummyResponse(
                    {"name": RESOURCE, "oidc": {}},
                    final_url="https://attacker.invalid/provider",
                )

        opener = ChangedUrlOpener()
        client = GoogleIamProviderClient(
            allowed_provider_resources={RESOURCE},
            access_token_supplier=lambda: "unit-test-runtime-token",
            opener=opener,
        )
        service = FederationReadDiscovery(provider_client=client)
        result = service.execute(READ_WIF_PROVIDER_METADATA, self.payload())
        self.assertEqual("UPSTREAM_REDIRECT_REJECTED", result["classification"])
        self.assertEqual(1, opener.calls)

    def test_deleted_and_disabled_provider_metadata_is_explicitly_blocked(self):
        cases = (
            ({"name": RESOURCE, "state": "DELETED", "disabled": False, "oidc": {}}, "BLOCKED_PROVIDER_DELETED"),
            ({"name": RESOURCE, "state": "ACTIVE", "disabled": True, "oidc": {}}, "BLOCKED_PROVIDER_DISABLED"),
        )
        for upstream, expected in cases:
            with self.subTest(expected=expected):
                service, _, _ = self.build(upstream)
                result = service.execute(READ_WIF_PROVIDER_METADATA, self.payload())
                self.assertEqual("FOUND", result["classification"])
                self.assertEqual(expected, result["operationalClassification"])
                self.assertFalse(result["tokenExchangeVerified"])

    def test_machine_authority_failure_suppresses_exception_text(self):
        def broken_supplier():
            raise RuntimeError("credential-value-that-must-not-escape")

        service, opener, _ = self.build({"name": RESOURCE}, token_supplier=broken_supplier)
        result = service.execute(READ_WIF_PROVIDER_METADATA, self.payload())
        self.assertEqual("MACHINE_AUTHORITY_UNAVAILABLE", result["classification"])
        self.assertNotIn("credential-value", json.dumps(result))
        self.assertFalse(opener.calls)

    def test_configuration_presence_returns_names_and_booleans_only(self):
        environment = {
            "DEPLOYER_SA": "",
            "GCP_PROJECT_ID": "project-id-not-returned",
            "GCP_REGION": "region-not-returned",
            "GCP_WIF_PROVIDER": "provider-name-not-returned",
            "GCP_SERVICE_ACCOUNT": "",
            "GCP_WORKLOAD_IDENTITY_PROVIDER": "",
            "WIF_PROVIDER": "",
            "UNAPPROVED_NAME": "ignored-not-enumerated",
        }
        service, _, _ = self.build(
            {"name": RESOURCE},
            configuration_environment=environment,
        )
        result = service.execute(
            READ_GITHUB_ACTIONS_CONFIG_PRESENCE,
            {
                "purpose": "repository configuration diagnostic",
                "mutation": "NONE",
            },
        )
        self.assertTrue(result["ok"])
        self.assertEqual("NO_COMPLETE_WIF_LANE_PRESENT", result["classification"])
        self.assertEqual("DIRECT_ALLOWLISTED_ENVIRONMENT_PRESENCE", result["evidenceClass"])
        self.assertEqual("ALLOWLISTED_PROCESS_ENVIRONMENT_SNAPSHOT", result["scope"])
        self.assertFalse(result["independentReadback"])
        self.assertFalse(result["runtimeOriginVerified"])
        self.assertEqual(
            ["GCP_PROJECT_ID", "GCP_REGION", "GCP_WIF_PROVIDER"],
            result["configuredNames"],
        )
        self.assertEqual(
            ["DEPLOYER_SA", "GCP_SERVICE_ACCOUNT", "GCP_WORKLOAD_IDENTITY_PROVIDER", "WIF_PROVIDER"],
            result["missingNames"],
        )
        self.assertFalse(result["minimumWifContextPresent"])
        self.assertFalse(result["valuesReturned"])
        serialized = json.dumps(result, sort_keys=True)
        for forbidden in (
            "project-id-not-returned",
            "region-not-returned",
            "provider-name-not-returned",
            "ignored-not-enumerated",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_configuration_request_cannot_supply_names_values_or_assertions(self):
        service, _, _ = self.build({"name": RESOURCE})
        result = service.execute(
            READ_GITHUB_ACTIONS_CONFIG_PRESENCE,
            {
                "purpose": "configuration diagnostic",
                "mutation": "NONE",
                "configurationPresence": {"GCP_WIF_PROVIDER": True},
            },
        )
        self.assertEqual("PAYLOAD_FIELD_NOT_ALLOWED", result["classification"])

    def test_configuration_environment_fails_closed_and_allowlist_is_exact(self):
        service, _, _ = self.build(
            {"name": RESOURCE},
            configuration_environment={"GCP_PROJECT_ID": True},
        )
        result = service.execute(
            READ_GITHUB_ACTIONS_CONFIG_PRESENCE,
            {
                "purpose": "configuration diagnostic",
                "mutation": "NONE",
            },
        )
        self.assertEqual("CONFIGURATION_ENVIRONMENT_INVALID", result["classification"])
        self.assertFalse(result["ok"])
        cases = (
            DEFAULT_GITHUB_CONFIGURATION_ALLOWLIST - {"GCP_REGION"},
            DEFAULT_GITHUB_CONFIGURATION_ALLOWLIST | {"CUSTOM_CONFIG"},
            {"FO_ADMIN_TOKEN"},
        )
        for names in cases:
            with self.subTest(names=names):
                with self.assertRaisesRegex(ValueError, "exact safe set"):
                    GitHubActionsEnvironmentPresenceReader(
                        allowed_configuration_names=names,
                    )

    def test_each_known_wif_lane_is_evaluated_without_values(self):
        base = {name: "" for name in DEFAULT_GITHUB_CONFIGURATION_ALLOWLIST}
        base.update({"GCP_PROJECT_ID": "configured", "GCP_REGION": "configured"})
        cases = (
            ({"GCP_WIF_PROVIDER": "configured", "GCP_SERVICE_ACCOUNT": "configured"}, "CANONICAL_WIF"),
            (
                {
                    "GCP_WORKLOAD_IDENTITY_PROVIDER": "configured",
                    "GCP_SERVICE_ACCOUNT": "configured",
                },
                "GCP_WORKLOAD_IDENTITY_WIF",
            ),
            ({"WIF_PROVIDER": "configured", "DEPLOYER_SA": "configured"}, "GENERIC_WIF"),
        )
        for changes, lane in cases:
            with self.subTest(lane=lane):
                environment = {**base, **changes}
                service, _, _ = self.build(
                    {"name": RESOURCE},
                    configuration_environment=environment,
                )
                result = service.execute(
                    READ_GITHUB_ACTIONS_CONFIG_PRESENCE,
                    {
                        "purpose": "configuration diagnostic",
                        "mutation": "NONE",
                    },
                )
                self.assertEqual("AT_LEAST_ONE_WIF_LANE_PRESENT", result["classification"])
                self.assertTrue(result["minimumWifContextPresent"])
                self.assertTrue(result["lanePresence"][lane])
                self.assertFalse(result["valuesReturned"])

    def test_unknown_action_is_rejected(self):
        service, opener, _ = self.build({"name": RESOURCE})
        result = service.execute("READ_ARBITRARY_URL_WITH_sensitive-value", {})
        self.assertEqual("ACTION_NOT_ALLOWLISTED", result["classification"])
        self.assertEqual("UNRECOGNIZED", result["action"])
        self.assertNotIn("sensitive-value", json.dumps(result))
        self.assertFalse(opener.calls)


class KdvL017ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.update_calls: list[str] = []

    def create(self):
        return {"objectId": "object-123", "response": "id-only"}

    def context(self, created):
        return {"route": {"effectSequence": "object-create-then-reference-update"}}

    def current_reference(self):
        return "old-object-456"

    def update(self, object_id: str, *, force: bool):
        self.update_calls.append(f"{object_id}:{force}")
        return {"ref": "refs/heads/draft", "objectId": object_id}

    def test_block_decision_never_calls_dependent_reference_update(self):
        result = execute_kdv_l017_sequence(
            create_object=self.create,
            build_gate_context=self.context,
            evaluate_gate=lambda _: {
                "decision": "BLOCK",
                "issues": ["INCOMPLETE_WRITE_RESPONSE_REQUIRES_READBACK"],
                "lessonsApplied": ["KDV-L017"],
            },
            read_current_reference=self.current_reference,
            expected_reference_object_id="old-object-456",
            update_reference=self.update,
        )
        self.assertEqual("REFERENCE_UPDATE_BLOCKED_BY_KDV_L017", result["classification"])
        self.assertFalse(result["referenceUpdateCalled"])
        self.assertEqual([], self.update_calls)

    def test_allow_without_kdv_l017_attestation_still_blocks(self):
        result = execute_kdv_l017_sequence(
            create_object=self.create,
            build_gate_context=self.context,
            evaluate_gate=lambda _: {"decision": "ALLOW", "issues": [], "lessonsApplied": []},
            read_current_reference=self.current_reference,
            expected_reference_object_id="old-object-456",
            update_reference=self.update,
        )
        self.assertEqual("KDV_L017_ATTESTATION_REQUIRED", result["classification"])
        self.assertEqual([], self.update_calls)

    def test_gate_exception_fails_closed_before_reference_update(self):
        def broken_gate(_):
            raise RuntimeError("untrusted failure detail")

        result = execute_kdv_l017_sequence(
            create_object=self.create,
            build_gate_context=self.context,
            evaluate_gate=broken_gate,
            read_current_reference=self.current_reference,
            expected_reference_object_id="old-object-456",
            update_reference=self.update,
        )
        self.assertEqual("KDV_L017_GATE_FAILED", result["classification"])
        self.assertEqual([], self.update_calls)

    def test_kdv_l017_allow_calls_reference_update_once(self):
        result = execute_kdv_l017_sequence(
            create_object=self.create,
            build_gate_context=self.context,
            evaluate_gate=lambda _: {
                "decision": "ALLOW",
                "issues": [],
                "lessonsApplied": ["KDV-L017"],
            },
            read_current_reference=self.current_reference,
            expected_reference_object_id="old-object-456",
            update_reference=self.update,
        )
        self.assertEqual("COMPLETE", result["decision"])
        self.assertEqual(["object-123:False"], self.update_calls)

    def test_reference_movement_after_allow_blocks_non_force_update(self):
        result = execute_kdv_l017_sequence(
            create_object=self.create,
            build_gate_context=self.context,
            evaluate_gate=lambda _: {
                "decision": "ALLOW",
                "issues": [],
                "lessonsApplied": ["KDV-L017"],
            },
            read_current_reference=lambda: "concurrent-object-999",
            expected_reference_object_id="old-object-456",
            update_reference=self.update,
        )
        self.assertEqual("REFERENCE_MOVED_AFTER_STRUCTURAL_VERIFICATION", result["classification"])
        self.assertEqual([], self.update_calls)


if __name__ == "__main__":
    unittest.main()
