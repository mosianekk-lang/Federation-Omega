from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping

from evidenceops.caseforge.openai_provider_adapter import (
    ALLOWED_PROVIDER_OPTIONS,
    FORBIDDEN_PROVIDER_OPTIONS,
    OpenAIProviderAdapterError,
    ProviderReadbackEvidence,
    ProviderReadbackVerifier,
    ProviderResponseEvidence,
)
from federation.idea_system_build_runtime import BuildCandidate
from federation.idea_to_system_compiler import IdeaSystemPlan

_SCHEMA = "FEDERATION-OPENAI-BUILD-GENERATOR-V1"
_FAILURE_FIELDS = frozenset(
    {
        "status",
        "returncode",
        "result_hash",
        "ledger_entry_hash",
        "execution_verified",
        "readback_verified",
        "persistence_verified",
        "rollback_verified",
    }
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _failure_summary(receipt: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if receipt is None:
        return None
    return {
        key: receipt[key]
        for key in sorted(_FAILURE_FIELDS)
        if key in receipt
    }


@dataclass(frozen=True, slots=True)
class BuildGeneratorProviderReceipt:
    provider_state: str
    response_id: str
    requested_model: str
    response_model: str
    response_status: str
    request_id: str
    output_sha256: str
    configuration_sha256: str
    provider_readback_ref: str = ""
    verified_model_version: str = ""
    provider_execution_authorized: bool = True
    provider_payload_authorized: bool = True
    provider_storage: bool = False
    external_mutation: bool = False

    def canonical_mapping(self) -> dict[str, Any]:
        return {
            "schema": _SCHEMA,
            "provider_state": self.provider_state,
            "response_id": self.response_id,
            "requested_model": self.requested_model,
            "response_model": self.response_model,
            "response_status": self.response_status,
            "request_id": self.request_id,
            "output_sha256": self.output_sha256,
            "configuration_sha256": self.configuration_sha256,
            "provider_readback_ref": self.provider_readback_ref,
            "verified_model_version": self.verified_model_version,
            "provider_execution_authorized": self.provider_execution_authorized,
            "provider_payload_authorized": self.provider_payload_authorized,
            "provider_storage": self.provider_storage,
            "external_mutation": self.external_mutation,
            "truth_boundary": {
                "provider_execution_is_provider_readback": self.provider_state == "PROVIDER_VERIFIED",
                "provider_call_authority_is_payload_share_authority": False,
                "generated_candidate_is_deployed": False,
                "provider_execution_grants_mutation_authority": False,
                "provider_execution_proves_user_value": False,
            },
        }


class OpenAIResponsesBuildGenerator:
    """Generic Idea->System BuildGenerator using an already-authorised Responses client.

    This adapter deliberately does not reuse CaseForge's legal benchmark prompt.
    It does reuse CaseForge's provider execution/readback evidence contracts.
    A provider call and transfer of the Idea/System workspace payload are separate
    gates. Responses are never provider-stored by this adapter.
    """

    def __init__(
        self,
        *,
        client: Any,
        model: str,
        provider_execution_authorized: bool = False,
        provider_payload_authorized: bool = False,
        request_options: Mapping[str, Any] | None = None,
        readback_verifier: ProviderReadbackVerifier | None = None,
        require_provider_readback: bool = False,
    ) -> None:
        if not str(model).strip():
            raise ValueError("model is required")
        self.client = client
        self.model = str(model).strip()
        self.provider_execution_authorized = bool(provider_execution_authorized)
        self.provider_payload_authorized = bool(provider_payload_authorized)
        self.request_options = dict(request_options or {})
        forbidden = sorted(FORBIDDEN_PROVIDER_OPTIONS & set(self.request_options))
        if forbidden:
            raise OpenAIProviderAdapterError(
                "provider options would weaken build isolation: " + ",".join(forbidden)
            )
        unsupported = sorted(set(self.request_options) - ALLOWED_PROVIDER_OPTIONS)
        if unsupported:
            raise OpenAIProviderAdapterError(
                "provider options are not admitted by the existing Responses contract: "
                + ",".join(unsupported)
            )
        if require_provider_readback and readback_verifier is None:
            raise ValueError("require_provider_readback needs an independent readback verifier")
        self.readback_verifier = readback_verifier
        self.require_provider_readback = bool(require_provider_readback)
        self._last_receipt: BuildGeneratorProviderReceipt | None = None

    @staticmethod
    def _instructions() -> str:
        return (
            "You are a bounded software build-candidate generator. Return exactly one JSON object "
            "with keys candidate_id, files, validation_command, export_paths, rationale. files must "
            "map safe relative paths to UTF-8 source text. validation_command and export_paths must "
            "be arrays of strings. Produce the smallest implementation that satisfies the supplied "
            "Idea-to-System plan and current workspace. Do not deploy, publish, send, purchase, use "
            "tools, access external systems, invent credentials, weaken tests, or claim provider or "
            "production verification. When a prior sandbox failure summary is supplied, make a "
            "material repair rather than repeating the identical candidate."
        )

    @staticmethod
    def _candidate_from_output(payload: Any) -> BuildCandidate:
        if not isinstance(payload, Mapping):
            raise ValueError("build generator output must be one JSON object")
        required = {"candidate_id", "files", "validation_command", "export_paths", "rationale"}
        missing = sorted(required - set(payload))
        if missing:
            raise ValueError("build generator output missing: " + ",".join(missing))
        if not isinstance(payload["files"], Mapping):
            raise ValueError("files must be an object")
        if not isinstance(payload["validation_command"], (list, tuple)):
            raise ValueError("validation_command must be an array")
        if not isinstance(payload["export_paths"], (list, tuple)):
            raise ValueError("export_paths must be an array")
        candidate = BuildCandidate(
            candidate_id=str(payload["candidate_id"]),
            files={str(key): str(value) for key, value in dict(payload["files"]).items()},
            validation_command=tuple(str(item) for item in payload["validation_command"]),
            export_paths=tuple(str(item) for item in payload["export_paths"]),
            rationale=str(payload["rationale"]),
        )
        candidate.normalized_files()
        return candidate

    def _provider_execution(self, output_text: str, response: Any) -> ProviderResponseEvidence:
        request_configuration = {"store": False, **self.request_options}
        return ProviderResponseEvidence(
            provider="openai",
            response_id=str(getattr(response, "id", "") or "").strip(),
            requested_model=self.model,
            response_model=str(getattr(response, "model", "") or "").strip(),
            status=str(getattr(response, "status", "") or "").strip(),
            created_at=getattr(response, "created_at", None),
            request_id=str(getattr(response, "_request_id", "") or "").strip(),
            output_text_sha256=_digest_text(output_text),
            store=False,
            request_configuration=request_configuration,
            configuration_sha256=_digest_text(_canonical(request_configuration)),
        ).validate()

    def propose(
        self,
        plan: IdeaSystemPlan,
        current_files: Mapping[str, str],
        failure_receipt: Mapping[str, Any] | None,
    ) -> BuildCandidate:
        self._last_receipt = None
        if not self.provider_execution_authorized:
            raise PermissionError("OpenAI build generation requires explicit provider execution authorization")
        if not self.provider_payload_authorized:
            raise PermissionError("OpenAI build generation requires explicit provider payload authorization")

        payload = {
            "plan": plan.canonical_mapping(),
            "current_files": dict(sorted((str(key), str(value)) for key, value in current_files.items())),
            "failure_summary": _failure_summary(failure_receipt),
        }
        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=self._instructions(),
                input=[{"role": "user", "content": _canonical(payload)}],
                store=False,
                **self.request_options,
            )
        except Exception as exc:
            raise OpenAIProviderAdapterError(
                f"OpenAI build generation failed: {type(exc).__name__}"
            ) from exc

        output_text = str(getattr(response, "output_text", "") or "").strip()
        if not output_text:
            raise OpenAIProviderAdapterError("OpenAI build generation returned empty output text")
        execution = self._provider_execution(output_text, response)

        readback: ProviderReadbackEvidence | None = None
        provider_state = "PROVIDER_EXECUTED_UNREADBACK"
        if self.readback_verifier is not None:
            readback = self.readback_verifier.verify(execution).validate_against(execution)
            provider_state = "PROVIDER_VERIFIED"
        elif self.require_provider_readback:
            raise OpenAIProviderAdapterError("provider readback was required but unavailable")

        try:
            parsed = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise ValueError("OpenAI build generator returned non-JSON output") from exc
        candidate = self._candidate_from_output(parsed)

        self._last_receipt = BuildGeneratorProviderReceipt(
            provider_state=provider_state,
            response_id=execution.response_id,
            requested_model=execution.requested_model,
            response_model=execution.response_model,
            response_status=execution.status,
            request_id=execution.request_id,
            output_sha256=execution.output_text_sha256,
            configuration_sha256=execution.configuration_sha256,
            provider_readback_ref=("" if readback is None else readback.provider_readback_ref),
            verified_model_version=("" if readback is None else readback.model_version),
            provider_execution_authorized=True,
            provider_payload_authorized=True,
            provider_storage=False,
            external_mutation=False,
        )
        return candidate

    def provider_receipt(self) -> Mapping[str, Any] | None:
        if self._last_receipt is None:
            return None
        return self._last_receipt.canonical_mapping()


__all__ = [
    "BuildGeneratorProviderReceipt",
    "OpenAIResponsesBuildGenerator",
]
