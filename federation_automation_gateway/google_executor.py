from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import google.auth
from google.auth import impersonated_credentials
from google.auth.transport.requests import AuthorizedSession, Request

from .contracts import Command

CLOUD_PLATFORM = "https://www.googleapis.com/auth/cloud-platform"
APPS_SCRIPT = "https://www.googleapis.com/auth/script.projects"
DEPLOYMENTS = "https://www.googleapis.com/auth/script.deployments"


@dataclass
class ExecutionResult:
    provider_status: str
    semantic_readback: str
    proof: dict[str, Any]
    production_effect: bool = False


class GoogleExecutor:
    """Bounded Google executor. No arbitrary URL passthrough is allowed."""

    def __init__(self, *, project_id: str, elevated_sa: str = "") -> None:
        self.project_id = project_id
        self.elevated_sa = elevated_sa

    def _credentials(self, elevated: bool):
        base, _ = google.auth.default(scopes=[CLOUD_PLATFORM, APPS_SCRIPT, DEPLOYMENTS])
        if not elevated:
            return base
        if not self.elevated_sa:
            raise RuntimeError("FED_BOOTSTRAP_SA is not configured for elevated execution")
        return impersonated_credentials.Credentials(
            source_credentials=base,
            target_principal=self.elevated_sa,
            target_scopes=[CLOUD_PLATFORM, APPS_SCRIPT, DEPLOYMENTS],
            lifetime=900,
        )

    def _session(self, elevated: bool) -> AuthorizedSession:
        credentials = self._credentials(elevated)
        credentials.refresh(Request())
        return AuthorizedSession(credentials)

    @staticmethod
    def _json_response(response) -> dict[str, Any]:
        try:
            body = response.json()
        except Exception:
            body = {"text": response.text[:4000]}
        return {"http_status": response.status_code, "body": body}

    def execute(self, command: Command, *, elevated: bool) -> ExecutionResult:
        handlers: dict[str, Callable[[Command, AuthorizedSession], ExecutionResult]] = {
            "GCP_GET_PROJECT": self._get_project,
            "GCP_LIST_ENABLED_SERVICES": self._list_enabled_services,
            "GCP_ENABLE_SERVICE": self._enable_service,
            "CLOUD_RUN_GET_SERVICE": self._get_cloud_run_service,
            "APPS_SCRIPT_GET_CONTENT": self._apps_script_get_content,
            "APPS_SCRIPT_GET_DEPLOYMENTS": self._apps_script_get_deployments,
            "APPS_SCRIPT_RUN": self._apps_script_run,
        }
        try:
            handler = handlers[command.action]
        except KeyError as exc:
            raise ValueError(f"Unsupported bounded Google action: {command.action}") from exc
        return handler(command, self._session(elevated))

    def _get_project(self, command: Command, session: AuthorizedSession) -> ExecutionResult:
        response = session.get(
            f"https://cloudresourcemanager.googleapis.com/v3/projects/{self.project_id}",
            timeout=30,
        )
        proof = self._json_response(response)
        ok = response.status_code == 200 and proof["body"].get("projectId") == self.project_id
        return ExecutionResult(
            "DONE" if ok else "FAILED",
            "PROJECT_ID_EXACT" if ok else "PROJECT_READBACK_FAILED",
            proof,
        )

    def _list_enabled_services(self, command: Command, session: AuthorizedSession) -> ExecutionResult:
        response = session.get(
            f"https://serviceusage.googleapis.com/v1/projects/{self.project_id}/services",
            params={"filter": "state:ENABLED", "pageSize": 200},
            timeout=30,
        )
        proof = self._json_response(response)
        ok = response.status_code == 200 and isinstance(proof["body"].get("services", []), list)
        proof["enabled_count"] = len(proof["body"].get("services", [])) if ok else None
        return ExecutionResult(
            "DONE" if ok else "FAILED",
            "ENABLED_SERVICES_READBACK" if ok else "SERVICE_READBACK_FAILED",
            proof,
        )

    def _enable_service(self, command: Command, session: AuthorizedSession) -> ExecutionResult:
        service = str(command.payload.get("service", "")).strip()
        if not service or "/" in service:
            raise ValueError("payload.service must be a Google service name")
        enable_url = (
            f"https://serviceusage.googleapis.com/v1/projects/{self.project_id}/services/"
            f"{service}:enable"
        )
        enable = session.post(enable_url, json={}, timeout=45)
        first = self._json_response(enable)
        readback = session.get(
            f"https://serviceusage.googleapis.com/v1/projects/{self.project_id}/services/{service}",
            timeout=30,
        )
        second = self._json_response(readback)
        state = second["body"].get("state")
        ok = readback.status_code == 200 and state == "ENABLED"
        return ExecutionResult(
            "DONE" if ok else "PARTIAL" if enable.status_code in (200, 201) else "FAILED",
            "SERVICE_ENABLED_READBACK" if ok else "ENABLE_ACCEPTED_READBACK_PENDING",
            {"service": service, "enable": first, "readback": second},
            production_effect=True,
        )

    def _get_cloud_run_service(self, command: Command, session: AuthorizedSession) -> ExecutionResult:
        region = str(command.payload.get("region", "africa-south1"))
        service = str(command.payload.get("service", ""))
        if not service:
            raise ValueError("payload.service is required")
        url = (
            f"https://run.googleapis.com/v2/projects/{self.project_id}/locations/{region}/services/{service}"
        )
        response = session.get(url, timeout=30)
        proof = self._json_response(response)
        expected = f"projects/{self.project_id}/locations/{region}/services/{service}"
        ok = response.status_code == 200 and proof["body"].get("name") == expected
        return ExecutionResult(
            "DONE" if ok else "FAILED",
            "CLOUD_RUN_TARGET_EXACT" if ok else "CLOUD_RUN_READBACK_FAILED",
            proof,
        )

    def _apps_script_get_content(self, command: Command, session: AuthorizedSession) -> ExecutionResult:
        script_id = str(command.payload.get("script_id", ""))
        if not script_id:
            raise ValueError("payload.script_id is required")
        response = session.get(
            f"https://script.googleapis.com/v1/projects/{script_id}/content",
            timeout=30,
        )
        proof = self._json_response(response)
        files = proof["body"].get("files", []) if response.status_code == 200 else []
        ok = response.status_code == 200 and bool(files)
        proof["file_count"] = len(files)
        return ExecutionResult(
            "DONE" if ok else "FAILED",
            "APPS_SCRIPT_SOURCE_READBACK" if ok else "APPS_SCRIPT_CONTENT_FAILED",
            proof,
        )

    def _apps_script_get_deployments(self, command: Command, session: AuthorizedSession) -> ExecutionResult:
        script_id = str(command.payload.get("script_id", ""))
        if not script_id:
            raise ValueError("payload.script_id is required")
        response = session.get(
            f"https://script.googleapis.com/v1/projects/{script_id}/deployments",
            timeout=30,
        )
        proof = self._json_response(response)
        ok = response.status_code == 200
        proof["deployment_count"] = len(proof["body"].get("deployments", [])) if ok else None
        return ExecutionResult(
            "DONE" if ok else "FAILED",
            "APPS_SCRIPT_DEPLOYMENT_READBACK" if ok else "APPS_SCRIPT_DEPLOYMENTS_FAILED",
            proof,
        )

    def _apps_script_run(self, command: Command, session: AuthorizedSession) -> ExecutionResult:
        script_id = str(command.payload.get("script_id", ""))
        function = str(command.payload.get("function", ""))
        parameters = command.payload.get("parameters", [])
        if not script_id or not function:
            raise ValueError("payload.script_id and payload.function are required")
        if not isinstance(parameters, list):
            raise ValueError("payload.parameters must be a list")
        response = session.post(
            f"https://script.googleapis.com/v1/scripts/{script_id}:run",
            json={
                "function": function,
                "parameters": parameters,
                "devMode": bool(command.payload.get("dev_mode", False)),
            },
            timeout=90,
        )
        proof = self._json_response(response)
        body = proof["body"]
        ok = response.status_code == 200 and "error" not in body and "response" in body
        return ExecutionResult(
            "DONE" if ok else "FAILED",
            "APPS_SCRIPT_FUNCTION_RETURNED" if ok else "APPS_SCRIPT_RUN_FAILED",
            proof,
            production_effect=True,
        )
