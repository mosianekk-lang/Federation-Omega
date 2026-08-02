"""Secret-safe, read-only provider and GitHub configuration discovery.

This module is deliberately transport-injected and has no deployment side
effects. A production adapter must supply a runtime-identity token supplier;
caller payloads can never carry tokens, credentials, URLs, or secret values.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import urllib.error
import urllib.request
from collections.abc import Callable, Collection, Mapping
from typing import Any
from urllib.parse import quote, urlparse

READ_WIF_PROVIDER_METADATA = "READ_WIF_PROVIDER_METADATA"
READ_GITHUB_ACTIONS_CONFIG_PRESENCE = "READ_GITHUB_ACTIONS_CONFIG_PRESENCE"

DEFAULT_GITHUB_CONFIGURATION_ALLOWLIST = frozenset(
    {
        "DEPLOYER_SA",
        "GCP_PROJECT_ID",
        "GCP_REGION",
        "GCP_SERVICE_ACCOUNT",
        "GCP_WIF_PROVIDER",
        "GCP_WORKLOAD_IDENTITY_PROVIDER",
        "WIF_PROVIDER",
    }
)

_PROVIDER_RESOURCE = re.compile(
    r"\Aprojects/(?P<project>[1-9][0-9]{0,19})/locations/global/"
    r"workloadIdentityPools/(?P<pool>(?!gcp-)[a-z](?:[a-z0-9-]{2,30}[a-z0-9]))/"
    r"providers/(?P<provider>(?!gcp-)[a-z](?:[a-z0-9-]{2,30}[a-z0-9]))\Z",
    re.ASCII,
)
_CONFIG_NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
_CONTROL_CHAR = re.compile(r"[\x00-\x1f\x7f]")
_SECRET_NAME_FRAGMENT = re.compile(
    r"(?:^|_)(?:API_KEY|AUTHORIZATION|CREDENTIALS?|PASSWORD|PRIVATE_KEY|SECRETS?|TOKENS?)(?:_|$)"
)
_HTTP_CLASSIFICATIONS = {
    400: "INVALID_PROVIDER_REQUEST",
    401: "CALLER_UNAUTHENTICATED",
    403: "CALLER_UNAUTHORIZED",
    404: "PROVIDER_NOT_FOUND_OR_NOT_VISIBLE",
    409: "UPSTREAM_STATE_CONFLICT",
    429: "UPSTREAM_RATE_LIMITED",
}
_MAX_RESPONSE_BYTES = 65_536
_MAX_JSON_DEPTH = 16
_MAX_MAPPING_KEYS = 32


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_DEFAULT_OPENER = urllib.request.build_opener(_RejectRedirects()).open


class RequestRejected(ValueError):
    """A stable, non-sensitive validation failure."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _validate_purpose(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise RequestRejected("PURPOSE_REQUIRED")
    if _CONTROL_CHAR.search(value):
        raise RequestRejected("PURPOSE_INVALID")
    return value.strip()


def _validate_exact_keys(
    payload: object, *, required: set[str], optional: set[str] | None = None
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RequestRejected("PAYLOAD_OBJECT_REQUIRED")
    optional = optional or set()
    keys = set(payload)
    if required - keys:
        raise RequestRejected("PAYLOAD_REQUIRED_FIELD_MISSING")
    if keys - required - optional:
        raise RequestRejected("PAYLOAD_FIELD_NOT_ALLOWED")
    return payload


def _provider_type(value: Mapping[str, Any]) -> str:
    for key, label in (
        ("oidc", "OIDC"),
        ("aws", "AWS"),
        ("saml", "SAML"),
        ("x509", "X509"),
    ):
        if isinstance(value.get(key), dict):
            return label
    return "UNKNOWN"


def _issuer_class(value: Mapping[str, Any]) -> str:
    oidc = value.get("oidc")
    if not isinstance(oidc, dict):
        return "NOT_APPLICABLE"
    raw = oidc.get("issuerUri")
    if not isinstance(raw, str):
        return "UNKNOWN"
    parsed = urlparse(raw)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return "INVALID"
    return "GITHUB_ACTIONS" if parsed.hostname.lower() == "token.actions.githubusercontent.com" else "OTHER_HTTPS"


def _json_depth(value: object, depth: int = 0) -> int:
    if depth > _MAX_JSON_DEPTH:
        return depth
    if isinstance(value, dict):
        return max((_json_depth(item, depth + 1) for item in value.values()), default=depth)
    if isinstance(value, list):
        return max((_json_depth(item, depth + 1) for item in value), default=depth)
    return depth


def _minimal_provider_metadata(value: Mapping[str, Any]) -> dict[str, Any]:
    mapping = value.get("attributeMapping")
    mapping_keys = sorted(str(key) for key in mapping) if isinstance(mapping, dict) else []
    if len(mapping_keys) > _MAX_MAPPING_KEYS or any(
        len(key) > 128 or re.fullmatch(r"[A-Za-z][A-Za-z0-9._-]{0,127}", key, re.ASCII) is None
        for key in mapping_keys
    ):
        raise RequestRejected("UPSTREAM_RESPONSE_INVALID")
    raw_state = value.get("state") if isinstance(value.get("state"), str) else "UNKNOWN"
    state = raw_state if raw_state in {"ACTIVE", "DELETED", "STATE_UNSPECIFIED"} else "UNKNOWN"
    disabled = value.get("disabled") is True
    return {
        "nameMatchesRequest": True,
        "state": state,
        "disabled": disabled,
        "expiryPresent": isinstance(value.get("expireTime"), str) and bool(value.get("expireTime")),
        "providerKind": _provider_type(value),
        "issuerClass": _issuer_class(value),
        "attributeMappingKeys": mapping_keys,
        "attributeConditionPresent": bool(value.get("attributeCondition")),
    }


def _operational_classification(metadata: Mapping[str, Any]) -> str:
    if metadata.get("state") == "DELETED":
        return "BLOCKED_PROVIDER_DELETED"
    if metadata.get("disabled") is True:
        return "BLOCKED_PROVIDER_DISABLED"
    if metadata.get("state") == "ACTIVE":
        return "METADATA_ACTIVE_TOKEN_EXCHANGE_UNVERIFIED"
    return "PROVIDER_OPERATIONAL_STATE_UNKNOWN"


def _safe_failure(action: str, classification: str) -> dict[str, Any]:
    return {
        "ok": False,
        "action": action,
        "classification": classification,
        "mutationPerformed": False,
        "callerSecretValuesAccepted": False,
        "credentialMaterialReturned": False,
    }


class GoogleIamProviderClient:
    """Fixed-host Google IAM provider reader with exact-resource allowlisting."""

    def __init__(
        self,
        *,
        allowed_provider_resources: Collection[str],
        access_token_supplier: Callable[[], str],
        opener: Callable[..., Any] = _DEFAULT_OPENER,
        timeout_seconds: int = 10,
    ) -> None:
        allowed = frozenset(str(item) for item in allowed_provider_resources)
        if not allowed or any(_PROVIDER_RESOURCE.fullmatch(item) is None for item in allowed):
            raise ValueError("allowed_provider_resources must contain valid exact resources")
        if not callable(access_token_supplier):
            raise TypeError("access_token_supplier must be callable")
        if not 1 <= timeout_seconds <= 30:
            raise ValueError("timeout_seconds must be between 1 and 30")
        self._allowed = allowed
        self._token_supplier = access_token_supplier
        self._opener = opener
        self._timeout = timeout_seconds

    def read(self, payload: object) -> dict[str, Any]:
        try:
            body = _validate_exact_keys(
                payload,
                required={"providerResource", "purpose", "mutation"},
            )
            resource = body["providerResource"]
            if not isinstance(resource, str) or _PROVIDER_RESOURCE.fullmatch(resource) is None:
                raise RequestRejected("PROVIDER_RESOURCE_INVALID")
            if resource not in self._allowed:
                raise RequestRejected("PROVIDER_RESOURCE_NOT_ALLOWLISTED")
            _validate_purpose(body["purpose"])
            if body["mutation"] != "NONE":
                raise RequestRejected("READ_ACTION_REQUIRES_MUTATION_NONE")
        except RequestRejected as exc:
            return _safe_failure(READ_WIF_PROVIDER_METADATA, exc.code)

        try:
            token = self._token_supplier()
        except Exception:
            return _safe_failure(READ_WIF_PROVIDER_METADATA, "MACHINE_AUTHORITY_UNAVAILABLE")
        if not isinstance(token, str) or not token or any(char.isspace() for char in token):
            return _safe_failure(READ_WIF_PROVIDER_METADATA, "MACHINE_AUTHORITY_UNAVAILABLE")

        url = "https://iam.googleapis.com/v1/" + quote(resource, safe="/")
        request = urllib.request.Request(
            url,
            headers={
                "accept": "application/json",
                "authorization": "Bearer " + token,
            },
            method="GET",
        )
        try:
            with self._opener(request, timeout=self._timeout) as response:
                status = getattr(response, "status", 200)
                if not isinstance(status, int) or status != 200:
                    classification = (
                        "UPSTREAM_REDIRECT_REJECTED"
                        if isinstance(status, int) and 300 <= status < 400
                        else "UPSTREAM_UNEXPECTED_STATUS"
                    )
                    return _safe_failure(READ_WIF_PROVIDER_METADATA, classification)
                response_url_reader = getattr(response, "geturl", None)
                response_url = response_url_reader() if callable(response_url_reader) else None
                if response_url != url:
                    return _safe_failure(
                        READ_WIF_PROVIDER_METADATA,
                        "UPSTREAM_REDIRECT_REJECTED",
                    )
                headers = getattr(response, "headers", None)
                if headers is not None:
                    content_type = headers.get_content_type()
                    if content_type not in {"application/json", "application/ld+json"}:
                        return _safe_failure(READ_WIF_PROVIDER_METADATA, "UPSTREAM_RESPONSE_INVALID")
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
                if len(raw) > _MAX_RESPONSE_BYTES:
                    return _safe_failure(READ_WIF_PROVIDER_METADATA, "UPSTREAM_RESPONSE_INVALID")
        except urllib.error.HTTPError as exc:
            classification = _HTTP_CLASSIFICATIONS.get(exc.code)
            if classification is None:
                if 300 <= exc.code < 400:
                    classification = "UPSTREAM_REDIRECT_REJECTED"
                else:
                    classification = "UPSTREAM_UNAVAILABLE" if exc.code >= 500 else "UPSTREAM_UNEXPECTED_STATUS"
            return _safe_failure(READ_WIF_PROVIDER_METADATA, classification)
        except ssl.SSLError:
            return _safe_failure(READ_WIF_PROVIDER_METADATA, "TLS_VALIDATION_FAILED")
        except (TimeoutError, urllib.error.URLError, OSError):
            return _safe_failure(READ_WIF_PROVIDER_METADATA, "NETWORK_UNAVAILABLE")
        except Exception:
            return _safe_failure(READ_WIF_PROVIDER_METADATA, "NETWORK_UNAVAILABLE")

        try:
            decoded = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
            upstream = json.loads(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            return _safe_failure(READ_WIF_PROVIDER_METADATA, "UPSTREAM_RESPONSE_INVALID")
        if not isinstance(upstream, dict):
            return _safe_failure(READ_WIF_PROVIDER_METADATA, "UPSTREAM_RESPONSE_INVALID")
        if _json_depth(upstream) > _MAX_JSON_DEPTH:
            return _safe_failure(READ_WIF_PROVIDER_METADATA, "UPSTREAM_RESPONSE_INVALID")
        if upstream.get("name") != resource:
            return _safe_failure(READ_WIF_PROVIDER_METADATA, "UPSTREAM_RESOURCE_IDENTITY_MISMATCH")

        provider_kinds = sum(isinstance(upstream.get(key), dict) for key in ("oidc", "aws", "saml", "x509"))
        if provider_kinds != 1:
            return _safe_failure(READ_WIF_PROVIDER_METADATA, "UPSTREAM_RESPONSE_INVALID")
        try:
            metadata = _minimal_provider_metadata(upstream)
        except RequestRejected as exc:
            return _safe_failure(READ_WIF_PROVIDER_METADATA, exc.code)
        return {
            "contract": "FO_WIF_PROVIDER_METADATA_V1",
            "ok": True,
            "action": READ_WIF_PROVIDER_METADATA,
            "classification": "FOUND",
            "evidenceClass": "GOOGLE_IAM_PROVIDER_METADATA",
            "independentReadback": True,
            "tokenExchangeAttempted": False,
            "tokenExchangeVerified": False,
            "operationalClassification": _operational_classification(metadata),
            "provider": metadata,
            "mutationPerformed": False,
            "callerSecretValuesAccepted": False,
            "credentialMaterialReturned": False,
        }


class GitHubActionsEnvironmentPresenceReader:
    """Read only allowlisted non-secret configuration from the process environment."""

    def __init__(
        self,
        *,
        allowed_configuration_names: Collection[str] = DEFAULT_GITHUB_CONFIGURATION_ALLOWLIST,
        environment_supplier: Callable[[], Mapping[str, str]] | None = None,
    ) -> None:
        names = frozenset(str(name) for name in allowed_configuration_names)
        if names != DEFAULT_GITHUB_CONFIGURATION_ALLOWLIST or any(
            _CONFIG_NAME.fullmatch(name) is None or _SECRET_NAME_FRAGMENT.search(name)
            for name in names
        ):
            raise ValueError("allowed_configuration_names must equal the exact safe set")
        if environment_supplier is not None and not callable(environment_supplier):
            raise TypeError("environment_supplier must be callable")
        self._allowed_configuration_names = names
        self._environment_supplier = environment_supplier or (lambda: os.environ)

    def read(self, payload: object) -> dict[str, Any]:
        try:
            body = _validate_exact_keys(
                payload,
                required={"purpose", "mutation"},
            )
            _validate_purpose(body["purpose"])
            if body["mutation"] != "NONE":
                raise RequestRejected("READ_ACTION_REQUIRES_MUTATION_NONE")
        except RequestRejected as exc:
            return _safe_failure(READ_GITHUB_ACTIONS_CONFIG_PRESENCE, exc.code)

        try:
            environment = self._environment_supplier()
            if not isinstance(environment, Mapping):
                raise RequestRejected("CONFIGURATION_ENVIRONMENT_UNAVAILABLE")
            presence: dict[str, bool] = {}
            for name in self._allowed_configuration_names:
                value = environment.get(name)
                if value is None:
                    presence[name] = False
                elif not isinstance(value, str):
                    raise RequestRejected("CONFIGURATION_ENVIRONMENT_INVALID")
                else:
                    presence[name] = value != ""
        except RequestRejected as exc:
            return _safe_failure(READ_GITHUB_ACTIONS_CONFIG_PRESENCE, exc.code)
        except Exception:
            return _safe_failure(
                READ_GITHUB_ACTIONS_CONFIG_PRESENCE,
                "CONFIGURATION_ENVIRONMENT_UNAVAILABLE",
            )

        configured = sorted(name for name, value in presence.items() if value)
        missing = sorted(name for name, value in presence.items() if not value)
        common_context = presence["GCP_PROJECT_ID"] and presence["GCP_REGION"]
        lane_presence = {
            "CANONICAL_WIF": presence["GCP_WIF_PROVIDER"] and presence["GCP_SERVICE_ACCOUNT"],
            "GCP_WORKLOAD_IDENTITY_WIF": (
                presence["GCP_WORKLOAD_IDENTITY_PROVIDER"]
                and presence["GCP_SERVICE_ACCOUNT"]
            ),
            "GENERIC_WIF": presence["WIF_PROVIDER"] and presence["DEPLOYER_SA"],
        }
        minimum_context = common_context and any(lane_presence.values())
        return {
            "contract": "FO_GITHUB_VARS_PRESENCE_V1",
            "ok": True,
            "action": READ_GITHUB_ACTIONS_CONFIG_PRESENCE,
            "classification": (
                "AT_LEAST_ONE_WIF_LANE_PRESENT"
                if minimum_context
                else "NO_COMPLETE_WIF_LANE_PRESENT"
            ),
            "scope": "ALLOWLISTED_PROCESS_ENVIRONMENT_SNAPSHOT",
            "evidenceClass": "DIRECT_ALLOWLISTED_ENVIRONMENT_PRESENCE",
            "independentReadback": False,
            "runtimeOriginVerified": False,
            "configuredNames": configured,
            "missingNames": missing,
            "lanePresence": lane_presence,
            "commonContextPresent": common_context,
            "minimumWifContextPresent": minimum_context,
            "valuesReturned": False,
            "mutationPerformed": False,
            "callerSecretValuesAccepted": False,
            "credentialMaterialReturned": False,
        }


class FederationReadDiscovery:
    """Strict action dispatcher for the draft read-only upgrade."""

    def __init__(
        self,
        *,
        provider_client: GoogleIamProviderClient,
        configuration_reader: GitHubActionsEnvironmentPresenceReader | None = None,
    ) -> None:
        self._provider_client = provider_client
        self._configuration_reader = configuration_reader or GitHubActionsEnvironmentPresenceReader()

    @property
    def allowed_actions(self) -> tuple[str, ...]:
        return tuple(sorted((READ_GITHUB_ACTIONS_CONFIG_PRESENCE, READ_WIF_PROVIDER_METADATA)))

    def execute(self, action: object, payload: object) -> dict[str, Any]:
        if action == READ_WIF_PROVIDER_METADATA:
            return self._provider_client.read(payload)
        if action == READ_GITHUB_ACTIONS_CONFIG_PRESENCE:
            return self._configuration_reader.read(payload)
        return _safe_failure("UNRECOGNIZED", "ACTION_NOT_ALLOWLISTED")
