"""Reusable, secret-safe client for the permanent EvidenceOps cloud operator."""

from __future__ import annotations

import hmac
import json
import os
import urllib.error
import urllib.request
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

CONTRACT_PATH = Path(__file__).with_name("contract.json")


class CloudCapabilityError(RuntimeError):
    pass


class OperatorTransport(Protocol):
    def call(self, *, url: str, token: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


class JsonRpcTransport:
    def call(self, *, url: str, token: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps({
            "jsonrpc": "2.0", "id": "evidenceops-cloud-capability",
            "method": "tools/call", "params": {"name": tool, "arguments": arguments},
        }, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            url, data=body, method="POST",
            headers={"authorization": f"Bearer {token}", "content-type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                value = json.loads(response.read())
        except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
            raise CloudCapabilityError("cloud operator transport failed") from exc
        if not isinstance(value, dict) or value.get("error"):
            raise CloudCapabilityError("cloud operator rejected the request")
        result = value.get("result", {}).get("structuredContent")
        if not isinstance(result, dict):
            raise CloudCapabilityError("cloud operator returned no semantic result")
        return result


@dataclass(frozen=True)
class CloudCapability:
    contract: dict[str, Any]
    operator_url: str = ""
    operator_token: str = ""
    transport: OperatorTransport | None = None

    @classmethod
    def load(
        cls,
        path: str | Path = CONTRACT_PATH,
        *,
        env: dict[str, str] | None = None,
        transport: OperatorTransport | None = None,
    ) -> "CloudCapability":
        contract = json.loads(Path(path).read_text(encoding="utf-8"))
        cls.validate_contract(contract)
        values = os.environ if env is None else env
        return cls(
            contract=contract,
            operator_url=str(values.get("EVIDENCEOPS_CLOUD_OPERATOR_URL") or values.get("OMEGA_MCP_URL", "")),
            operator_token=str(values.get("OMEGA_MCP_SHARED_SECRET", "")),
            transport=transport,
        )

    @staticmethod
    def validate_contract(contract: dict[str, Any]) -> None:
        if contract.get("schema") != "EVIDENCEOPS-PERMANENT-CLOUD-CAPABILITY-1":
            raise CloudCapabilityError("unsupported cloud capability contract")
        scope = contract.get("scope") or {}
        if scope.get("control_breadth") != "FULL_PROJECT_CONTROL":
            raise CloudCapabilityError("full project control directive was diluted")
        participants = set(scope.get("participants") or [])
        required = {
            "evidenceops://systems/*", "evidenceops://subsystems/*",
            "evidenceops://ai-agents/*", "evidenceops://elements/*",
        }
        if not required.issubset(participants):
            raise CloudCapabilityError("mandatory EvidenceOps participants are missing")
        inheritance = contract.get("inheritance") or {}
        if inheritance.get("automatic") is not True or inheritance.get("explicit_opt_out_allowed") is not False:
            raise CloudCapabilityError("cloud capability inheritance must be automatic and non-optional")
        if not str(scope.get("target_project") or ""):
            raise CloudCapabilityError("target project is required")

    def inherited_context(self, element_id: str) -> dict[str, Any]:
        if not element_id.startswith("evidenceops://"):
            raise CloudCapabilityError("element is outside the EvidenceOps namespace")
        scope = self.contract["scope"]
        return {
            "element_id": element_id,
            "capability": self.contract["schema"],
            "target_project": scope["target_project"],
            "quota_project": scope["quota_project"],
            "control_breadth": scope["control_breadth"],
            "route": self.contract["inheritance"]["execution_route"],
            "raw_credentials": False,
            "inherited": True,
        }

    def readiness(self) -> dict[str, Any]:
        proof = self.contract["proof"]
        configured = bool(self.operator_url.startswith("https://") and self.operator_token)
        return {
            "state": "RUNTIME_CONFIGURED" if configured else "SOURCE_REGISTERED_RUNTIME_UNBOUND",
            "source_registered": True,
            "runtime_configured": configured,
            "target_project": self.contract["scope"]["target_project"],
            "control_breadth": "FULL_PROJECT_CONTROL",
            "provider_canary_state": proof["provider_canary_state"],
            "semantic_readback_state": proof["semantic_readback_state"],
            "permanence_state": proof["permanence_state"],
            "completion_claim": False,
        }

    def call(self, tool: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.operator_url.startswith("https://"):
            raise CloudCapabilityError("trusted runtime cloud operator binding is absent")
        if not isinstance(arguments or {}, dict):
            raise CloudCapabilityError("tool arguments must be an object")
        transport = self.transport or JsonRpcTransport()
        token = self.operator_token or self._metadata_identity_token()
        return transport.call(
            url=self.operator_url, token=token,
            tool=tool, arguments=arguments or {},
        )

    def _metadata_identity_token(self) -> str:
        audience = self.operator_url.removesuffix("/mcp")
        url = (
            "http://metadata.google.internal/computeMetadata/v1/instance/"
            "service-accounts/default/identity?audience=" + urllib.parse.quote(audience, safe="")
        )
        request = urllib.request.Request(url, headers={"Metadata-Flavor": "Google"})
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                token = response.read().decode("utf-8")
        except OSError as exc:
            raise CloudCapabilityError("Cloud Run service-identity token is unavailable") from exc
        if token.count(".") != 2:
            raise CloudCapabilityError("metadata server returned an invalid identity token")
        return token

    def token_matches(self, candidate: str) -> bool:
        """Test helper for constant-time binding checks; never returns the token."""
        return bool(candidate) and hmac.compare_digest(self.operator_token, candidate)
