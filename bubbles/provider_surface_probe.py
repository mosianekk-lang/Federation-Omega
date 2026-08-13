from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Callable, Mapping
import urllib.error
import urllib.request


FO_OPERATOR_URL = "https://federation-omega-operator-257649435135.africa-south1.run.app"
ARCHON_ADMIN_URL = "https://archon-admin-plane-7ujkyfl36q-bq.a.run.app"
AFEME_URL = "https://afeme-sovereign-control-plane-v4-257649435135.africa-south1.run.app"
ARCHON_SCRIPT_DEPLOYMENT_ID = "AKfycbyaxovYOyaoMWFdsAZnbl2AIFU0PFY3hcGF-QRM1dmDqdtEHRFI7Ud7L_p7YCCVMG3J"
ARCHON_SCRIPT_URL = f"https://script.google.com/macros/s/{ARCHON_SCRIPT_DEPLOYMENT_ID}/exec"
PROJECT_ID = "sov-hybrid-suite"
REGION = "africa-south1"
TARGET_SERVICE = "architron9"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class ProbeHooks:
    http: Callable[..., Mapping[str, Any]]
    command: Callable[[list[str]], CommandResult]


def _json_or_text(raw: str) -> object:
    try:
        return json.loads(raw)
    except Exception:
        return {"text": raw[:5000]}


def _default_http(
    url: str,
    *,
    body: Mapping[str, object] | None = None,
    headers: Mapping[str, str] | None = None,
    follow_redirects: bool = False,
    timeout: int = 20,
) -> Mapping[str, Any]:
    request_headers = {"accept": "application/json,text/plain,*/*", **dict(headers or {})}
    data = None
    method = "GET"
    if body is not None:
        request_headers["content-type"] = "application/json"
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        method = "POST"
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    opener = urllib.request.build_opener() if follow_redirects else urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            return {
                "http_status": int(response.status),
                "body": _json_or_text(raw),
                "location": response.headers.get("Location"),
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        return {
            "http_status": int(exc.code),
            "body": _json_or_text(raw),
            "location": exc.headers.get("Location"),
        }
    except Exception as exc:  # pragma: no cover - exercised in provider runner
        return {"transport_error": type(exc).__name__, "message": str(exc)[:700]}


def _default_command(args: list[str]) -> CommandResult:
    try:
        proc = subprocess.run(args, text=True, capture_output=True, check=False, timeout=25)
        return CommandResult(proc.returncode, proc.stdout, proc.stderr)
    except Exception as exc:  # pragma: no cover - runner dependent
        return CommandResult(127, "", f"{type(exc).__name__}: {exc}")


def default_hooks() -> ProbeHooks:
    return ProbeHooks(http=_default_http, command=_default_command)


def _replace_secret(value: Any, secrets: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        return {key: _replace_secret(child, secrets) for key, child in value.items()}
    if isinstance(value, list):
        return [_replace_secret(child, secrets) for child in value]
    if isinstance(value, str):
        out = value
        for secret in secrets:
            if secret:
                out = out.replace(secret, "[REDACTED]")
        return out
    return value


def _active_account(hooks: ProbeHooks) -> tuple[str, str]:
    result = hooks.command(["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"])
    account = result.stdout.strip().splitlines()[0] if result.returncode == 0 and result.stdout.strip() else ""
    return account, result.stderr[-1200:]


def _read_secret(hooks: ProbeHooks, secret_id: str) -> tuple[str, str]:
    result = hooks.command(
        [
            "gcloud",
            "secrets",
            "versions",
            "access",
            "latest",
            f"--secret={secret_id}",
            f"--project={PROJECT_ID}",
        ]
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip(), ""
    return "", result.stderr[-1800:]


def _identity_token(hooks: ProbeHooks, audience: str) -> tuple[str, str]:
    result = hooks.command(["gcloud", "auth", "print-identity-token", f"--audiences={audience}"])
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip(), ""
    return "", result.stderr[-1800:]


def _response_ok(response: Mapping[str, Any]) -> bool:
    return response.get("http_status") == 200 and isinstance(response.get("body"), Mapping) and response["body"].get("ok") is True


def _public_reachable(response: Mapping[str, Any]) -> bool:
    return isinstance(response.get("http_status"), int) or "transport_error" not in response


def _apps_script_classification(response: Mapping[str, Any]) -> str:
    status = response.get("http_status")
    location = str(response.get("location") or "")
    if status in {301, 302, 303, 307, 308}:
        return "AUTH_OR_REDIRECT_REACHABLE" if location else "REDIRECT_REACHABLE"
    if status in {401, 403}:
        return "AUTH_REQUIRED_REACHABLE"
    if status == 200:
        return "HTTP_CALLABLE_SEMANTICS_UNVERIFIED"
    if "transport_error" in response:
        return "TRANSPORT_UNREACHABLE"
    return "REACHABLE_UNCLASSIFIED"


def run_probe(
    hooks: ProbeHooks | None = None,
    *,
    direct_fo_token: str = "",
    direct_archon_token: str = "",
) -> dict[str, Any]:
    hooks = hooks or default_hooks()

    public = {
        "fo_operator_health": hooks.http(f"{FO_OPERATOR_URL}/health"),
        "fo_operator_contract": hooks.http(f"{FO_OPERATOR_URL}/"),
        "archon_admin_root": hooks.http(f"{ARCHON_ADMIN_URL}/"),
        "archon_admin_openapi": hooks.http(f"{ARCHON_ADMIN_URL}/openapi.yaml"),
        "archon_apps_script": hooks.http(ARCHON_SCRIPT_URL),
        "afeme_root": hooks.http(f"{AFEME_URL}/"),
    }

    account, account_error = _active_account(hooks)
    fo_token = direct_fo_token.strip()
    fo_token_source = "github_actions_secret" if fo_token else ""
    fo_token_error = ""
    if not fo_token and account:
        fo_token, fo_token_error = _read_secret(hooks, "fo-operator-admin-token")
        if fo_token:
            fo_token_source = "google_secret_manager"

    operator_status: Mapping[str, Any] | None = None
    operator_cloud_read: Mapping[str, Any] | None = None
    allowed = set()
    contract_body = public["fo_operator_contract"].get("body")
    if isinstance(contract_body, Mapping):
        raw_allowed = contract_body.get("allowedActions", [])
        if isinstance(raw_allowed, list):
            allowed = {str(item) for item in raw_allowed}

    if fo_token and {"STATUS", "READ_CLOUD_RUN_SERVICE"}.issubset(allowed):
        auth_header = {"x-fo-admin-token": fo_token}
        operator_status = hooks.http(
            f"{FO_OPERATOR_URL}/execute",
            body={"action": "STATUS", "payload": {"purpose": "Bubbles provider readback probe", "mutation": "NONE"}},
            headers=auth_header,
        )
        operator_cloud_read = hooks.http(
            f"{FO_OPERATOR_URL}/execute",
            body={
                "action": "READ_CLOUD_RUN_SERVICE",
                "payload": {
                    "project": PROJECT_ID,
                    "region": REGION,
                    "service": TARGET_SERVICE,
                    "purpose": "Bubbles action-specific read-only cloud probe",
                },
            },
            headers=auth_header,
        )

    if not fo_token:
        operator_classification = "BLOCKED_TRUSTED_TOKEN_BINDING"
    elif not {"STATUS", "READ_CLOUD_RUN_SERVICE"}.issubset(allowed):
        operator_classification = "BLOCKED_LIVE_ALLOWLIST_MISMATCH"
    elif operator_status and operator_cloud_read and _response_ok(operator_status) and _response_ok(operator_cloud_read):
        operator_classification = "AUTHENTICATED_READBACK_VERIFIED"
    else:
        operator_classification = "AUTHENTICATED_READBACK_FAILED"

    archon_token = direct_archon_token.strip()
    archon_token_source = "github_actions_secret" if archon_token else ""
    archon_token_error = ""
    if not archon_token and account:
        archon_token, archon_token_error = _read_secret(hooks, "archon-admin-plane-token")
        if archon_token:
            archon_token_source = "google_secret_manager"

    archon_audit: Mapping[str, Any] | None = None
    if archon_token:
        archon_audit = hooks.http(
            f"{ARCHON_ADMIN_URL}/api/admin/command",
            body={"command": "capability_audit", "payload": {}, "source": "bubbles-provider-readback"},
            headers={"Authorization": f"Bearer {archon_token}"},
            timeout=45,
        )
    if archon_audit and archon_audit.get("http_status") == 200:
        archon_classification = "AUTHENTICATED_CAPABILITY_AUDIT_REACHABLE"
    elif archon_token:
        archon_classification = "AUTHENTICATED_CAPABILITY_AUDIT_FAILED"
    elif _public_reachable(public["archon_admin_openapi"]):
        archon_classification = "PUBLIC_SURFACE_REACHABLE_AUTH_PENDING"
    else:
        archon_classification = "CURRENT_REACHABILITY_UNVERIFIED"

    afeme_token = ""
    afeme_token_error = ""
    afeme_authenticated: Mapping[str, Any] | None = None
    if account:
        afeme_token, afeme_token_error = _identity_token(hooks, AFEME_URL)
        if afeme_token:
            afeme_authenticated = hooks.http(
                f"{AFEME_URL}/",
                headers={"Authorization": f"Bearer {afeme_token}"},
                follow_redirects=False,
            )
    if afeme_authenticated and afeme_authenticated.get("http_status") == 200:
        afeme_classification = "IDENTITY_TOKEN_READ_VERIFIED"
    elif afeme_token:
        afeme_classification = "IDENTITY_TOKEN_ACCEPTANCE_FAILED"
    elif public["afeme_root"].get("http_status") in {401, 403}:
        afeme_classification = "IAM_PROTECTED_REACHABLE_AUTH_PENDING"
    elif _public_reachable(public["afeme_root"]):
        afeme_classification = "PUBLIC_REACHABLE_SEMANTICS_UNVERIFIED"
    else:
        afeme_classification = "CURRENT_REACHABILITY_UNVERIFIED"

    secrets = tuple(secret for secret in (fo_token, archon_token, afeme_token) if secret)
    receipt: dict[str, Any] = {
        "schema": "BUBBLES-PROVIDER-SURFACE-PROBE-V1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "project": PROJECT_ID,
        "region": REGION,
        "active_gcloud_account": account,
        "active_account_probe_error": account_error,
        "mutation_attempted": False,
        "secret_values_recorded": False,
        "surfaces": {
            "federation_omega_operator": {
                "url": FO_OPERATOR_URL,
                "public_health": public["fo_operator_health"],
                "public_contract": public["fo_operator_contract"],
                "trusted_token_available": bool(fo_token),
                "token_source": fo_token_source,
                "token_access_error": fo_token_error,
                "authenticated_status": operator_status,
                "authenticated_cloud_read": operator_cloud_read,
                "classification": operator_classification,
            },
            "archon_admin_plane_v5": {
                "url": ARCHON_ADMIN_URL,
                "public_root": public["archon_admin_root"],
                "public_openapi": public["archon_admin_openapi"],
                "trusted_token_available": bool(archon_token),
                "token_source": archon_token_source,
                "token_access_error": archon_token_error,
                "authenticated_capability_audit": archon_audit,
                "classification": archon_classification,
            },
            "archon_apps_script_translator": {
                "script_id": "12CrTP0YUQbUpBvLklf_tInjN_k3L5qt3Tkp-M9pIO_O4Cs8dsYRH7kPO",
                "deployment_id": ARCHON_SCRIPT_DEPLOYMENT_ID,
                "web_app_url": ARCHON_SCRIPT_URL,
                "public_probe": public["archon_apps_script"],
                "classification": _apps_script_classification(public["archon_apps_script"]),
                "service_account_api_shortcut_allowed": False,
            },
            "afeme_v4": {
                "url": AFEME_URL,
                "public_probe": public["afeme_root"],
                "identity_token_obtained": bool(afeme_token),
                "identity_token_error": afeme_token_error,
                "authenticated_probe": afeme_authenticated,
                "classification": afeme_classification,
            },
        },
        "truth_boundary": (
            "This probe performs read-only reachability, identity and semantic checks. It never proves a mutation unless a separate "
            "effectful action and provider-native target readback exist. It records no credential values."
        ),
    }
    return _replace_secret(receipt, secrets)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Bubbles read-only Google/Federation provider surface probe.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    receipt = run_probe(
        direct_fo_token=os.environ.get("FO_ADMIN_TOKEN", ""),
        direct_archon_token=os.environ.get("ARCHON_ADMIN_TOKEN", ""),
    )
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
