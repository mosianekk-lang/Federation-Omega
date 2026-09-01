from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "SOL_6_2_GOOGLE_SURFACE_MESH_V1"
DEFAULT_MESH_PATH = Path(__file__).with_name("SOL_6_2_GOOGLE_SURFACE_MESH.json")


class GoogleSurfaceMeshError(RuntimeError):
    pass


class NoVerifiedRoute(GoogleSurfaceMeshError):
    pass


class Operation(str, Enum):
    APPS_SCRIPT_SAFE_COMMAND = "APPS_SCRIPT_SAFE_COMMAND"
    APPS_SCRIPT_SOURCE_MUTATION = "APPS_SCRIPT_SOURCE_MUTATION"
    GOOGLE_CLOUD_READ = "GOOGLE_CLOUD_READ"
    GOOGLE_CLOUD_MUTATION = "GOOGLE_CLOUD_MUTATION"
    GEMINI_INFERENCE = "GEMINI_INFERENCE"


@dataclass(frozen=True)
class RouteDecision:
    operation: Operation
    surface: str
    state: str
    automation_level: str
    executable: bool
    reason: str


class GoogleSurfaceMesh:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        if payload.get("schema") != SCHEMA:
            raise GoogleSurfaceMeshError(f"unsupported mesh schema: {payload.get('schema')!r}")
        surfaces = payload.get("surfaces")
        if not isinstance(surfaces, dict) or not surfaces:
            raise GoogleSurfaceMeshError("Google surface mesh requires surfaces")
        rules = payload.get("global_rules")
        if not isinstance(rules, list) or "NO_CROSS_SURFACE_MATURITY_INHERITANCE" not in rules:
            raise GoogleSurfaceMeshError("cross-surface maturity inheritance must be forbidden")
        self.payload = dict(payload)
        self.surfaces: dict[str, dict[str, Any]] = {
            str(name): dict(value) for name, value in surfaces.items() if isinstance(value, dict)
        }
        self._validate()

    def _surface(self, name: str) -> dict[str, Any]:
        try:
            return self.surfaces[name]
        except KeyError as exc:
            raise GoogleSurfaceMeshError(f"missing Google surface: {name}") from exc

    def _validate(self) -> None:
        queue = self._surface("GOOGLE_APPS_SCRIPT_QUEUE_RUNTIME")
        if queue.get("state") != "OPERATIONAL_VERIFIED_SCOPED":
            raise GoogleSurfaceMeshError("Apps Script queue runtime may only be primary when operationally verified")
        canary = queue.get("provider_canary") or {}
        if canary.get("status") != "EXECUTED" or canary.get("provider_state") != "verified_live":
            raise GoogleSurfaceMeshError("Apps Script queue runtime lacks provider execution proof")
        if not str(canary.get("executed_at_utc", "")).endswith("Z"):
            raise GoogleSurfaceMeshError("Apps Script provider canary requires UTC execution timestamp")

        web = self._surface("GOOGLE_APPS_SCRIPT_WEB_APP")
        if int(web.get("last_probe_http_status", 0)) != 404:
            raise GoogleSurfaceMeshError("web-app truth state drifted; re-probe required")
        if web.get("automation_level") != "DO_NOT_ROUTE":
            raise GoogleSurfaceMeshError("stale Apps Script web app must never be routed")

        source = self._surface("GOOGLE_APPS_SCRIPT_SOURCE_CONTROL")
        if source.get("service_accounts_sufficient") is not False:
            raise GoogleSurfaceMeshError("Apps Script source authority may not be inherited from service accounts")

        cloud = self._surface("GOOGLE_CLOUD_WIF_CONTROL_PLANE")
        if cloud.get("oidc_exchange_verified") is not True or cloud.get("adc_runtime_identity_verified") is not True:
            raise GoogleSurfaceMeshError("Google Cloud control plane requires provider-authenticated WIF and ADC")
        if cloud.get("wif_hardened_contract_verified") is not False:
            raise GoogleSurfaceMeshError("current mesh must preserve unresolved WIF hardening gap")
        if cloud.get("blocking_provider_permission") != "iam.workloadIdentityPoolProviders.update":
            raise GoogleSurfaceMeshError("current WIF permission blocker changed; refresh provider proof")
        if int(cloud.get("alternate_github_admin_credential_aliases_verified", -1)) != 0:
            raise GoogleSurfaceMeshError("alternate Google admin credential truth state drifted")

        vertex = self._surface("GEMINI_VERTEX")
        if vertex.get("provider_native_inference_verified") is not False:
            raise GoogleSurfaceMeshError("Vertex inference cannot be promoted without provider-native proof")

        ai_studio = self._surface("GEMINI_AI_STUDIO_DEVELOPER_API")
        if ai_studio.get("credential_value_recorded") is not False:
            raise GoogleSurfaceMeshError("AI Studio credential values must never be recorded")
        if ai_studio.get("last_semantic_verified") is not False:
            raise GoogleSurfaceMeshError("AI Studio semantic maturity must match the live probe")

    def route(self, operation: Operation | str, *, command: str | None = None) -> RouteDecision:
        op = operation if isinstance(operation, Operation) else Operation(str(operation))

        if op is Operation.APPS_SCRIPT_SAFE_COMMAND:
            surface = self._surface("GOOGLE_APPS_SCRIPT_QUEUE_RUNTIME")
            allowed = {str(item) for item in surface.get("allowed_commands", [])}
            if not command or command not in allowed:
                raise NoVerifiedRoute(f"Apps Script command is not in the verified SAFE_AUTO set: {command!r}")
            return RouteDecision(
                operation=op,
                surface="GOOGLE_APPS_SCRIPT_QUEUE_RUNTIME",
                state=str(surface["state"]),
                automation_level=str(surface["automation_level"]),
                executable=True,
                reason="provider-executed queue runtime with verified live command semantics",
            )

        if op is Operation.GOOGLE_CLOUD_READ:
            surface = self._surface("GOOGLE_CLOUD_WIF_CONTROL_PLANE")
            return RouteDecision(
                operation=op,
                surface="GOOGLE_CLOUD_WIF_CONTROL_PLANE",
                state=str(surface["state"]),
                automation_level=str(surface["automation_level"]),
                executable=True,
                reason="WIF exchange and ADC runtime identity are provider verified for read/control-plane inspection",
            )

        if op is Operation.APPS_SCRIPT_SOURCE_MUTATION:
            surface = self._surface("GOOGLE_APPS_SCRIPT_SOURCE_CONTROL")
            raise NoVerifiedRoute(
                f"Apps Script source mutation held: {surface['state']} with human OAuth and deployment scopes required"
            )

        if op is Operation.GOOGLE_CLOUD_MUTATION:
            cloud = self._surface("GOOGLE_CLOUD_WIF_CONTROL_PLANE")
            raise NoVerifiedRoute(
                "Google Cloud mutation held until hardened WIF provider readback is verified; "
                f"current blocker={cloud.get('blocking_provider_permission')}"
            )

        if op is Operation.GEMINI_INFERENCE:
            vertex = self._surface("GEMINI_VERTEX")
            if vertex.get("provider_native_inference_verified") is True:
                return RouteDecision(
                    operation=op,
                    surface="GEMINI_VERTEX",
                    state=str(vertex["state"]),
                    automation_level=str(vertex["automation_level"]),
                    executable=True,
                    reason="provider-native Vertex inference and semantic readback verified",
                )
            ai_studio = self._surface("GEMINI_AI_STUDIO_DEVELOPER_API")
            if ai_studio.get("last_semantic_verified") is True:
                return RouteDecision(
                    operation=op,
                    surface="GEMINI_AI_STUDIO_DEVELOPER_API",
                    state=str(ai_studio["state"]),
                    automation_level=str(ai_studio["automation_level"]),
                    executable=True,
                    reason="Gemini Developer API semantic nonce canary verified",
                )
            raise NoVerifiedRoute(
                "Gemini inference held: Vertex lacks hardened-WIF/provider-native inference proof and "
                "AI Studio Developer API credential/semantic proof is absent"
            )

        raise NoVerifiedRoute(f"no Google route for operation: {op.value}")

    def automation_plan(self) -> dict[str, Any]:
        executable: list[dict[str, str]] = []
        blocked: list[dict[str, str]] = []

        for op, kwargs in (
            (Operation.APPS_SCRIPT_SAFE_COMMAND, {"command": "verify_state"}),
            (Operation.GOOGLE_CLOUD_READ, {}),
            (Operation.APPS_SCRIPT_SOURCE_MUTATION, {}),
            (Operation.GOOGLE_CLOUD_MUTATION, {}),
            (Operation.GEMINI_INFERENCE, {}),
        ):
            try:
                decision = self.route(op, **kwargs)
                executable.append(
                    {
                        "operation": op.value,
                        "surface": decision.surface,
                        "state": decision.state,
                        "automation_level": decision.automation_level,
                    }
                )
            except NoVerifiedRoute as exc:
                blocked.append({"operation": op.value, "reason": str(exc)})

        return {
            "mesh_id": self.payload["mesh_id"],
            "executable": executable,
            "blocked": blocked,
            "no_cross_surface_maturity_inheritance": True,
        }


def load_google_surface_mesh(path: str | Path | None = None) -> GoogleSurfaceMesh:
    mesh_path = Path(path) if path is not None else DEFAULT_MESH_PATH
    try:
        payload = json.loads(mesh_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GoogleSurfaceMeshError(f"cannot load Google surface mesh: {mesh_path}") from exc
    return GoogleSurfaceMesh(payload)


__all__ = [
    "GoogleSurfaceMesh",
    "GoogleSurfaceMeshError",
    "NoVerifiedRoute",
    "Operation",
    "RouteDecision",
    "load_google_surface_mesh",
]
