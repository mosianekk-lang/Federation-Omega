#!/usr/bin/env python3
"""GET-only GitHub authority acquisition probe for Phoenix cutover.

The probe never creates repositories, changes settings, writes provider state,
or records a credential value. It classifies whether the private process has a
user-scoped authority or an all-repositories GitHub App installation authority
suitable for the separately owner-authorised cutover path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API = "https://api.github.com"
API_VERSION = "2026-03-10"
SCHEMA = "FEDOMEGA-PHOENIX-PROVIDER-AUTHORITY-PROBE-1"
HEX40 = re.compile(r"^[0-9a-fA-F]{40}$")


class AuthorityProbeError(RuntimeError):
    """Fail-closed probe or provider readback error."""


def canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class GitHubReadClient:
    def __init__(self, token: str):
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "federation-omega-phoenix-authority-probe",
        }

    def get(self, path: str, *, allow: tuple[int, ...] = (200,)) -> tuple[int, Any]:
        request = urllib.request.Request(API + path, headers=self.headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
                payload = json.loads(raw) if raw else None
                if response.status not in allow:
                    raise AuthorityProbeError(
                        f"unexpected GitHub status {response.status} for GET {path}"
                    )
                return response.status, payload
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code in allow:
                return exc.code, json.loads(detail) if detail else None
            raise AuthorityProbeError(
                f"GitHub GET {path} failed with {exc.code}: {detail[:800]}"
            ) from exc
        except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
            raise AuthorityProbeError(f"GitHub GET {path} failed") from exc

    def optional(self, path: str) -> Any | None:
        try:
            return self.get(path)[1]
        except AuthorityProbeError as exc:
            if " failed with 404:" in str(exc):
                return None
            raise


def _permission_at_least_read(value: Any) -> bool:
    return value in {"read", "write"}


def _permission_write(value: Any) -> bool:
    return value == "write"


def _repo_admin(repo: dict[str, Any]) -> bool:
    return bool(repo.get("permissions", {}).get("admin"))


def _head_sha(payload: dict[str, Any]) -> str:
    value = payload.get("object", {}).get("sha")
    if not isinstance(value, str) or not HEX40.fullmatch(value):
        raise AuthorityProbeError("legacy main readback returned an invalid SHA")
    return value.lower()


def probe_authority(
    client: Any,
    *,
    owner: str = "mosianekk-lang",
    legacy: str = "Federation-Omega",
    core: str = "Federation-Omega-Core",
    ops: str = "Federation-Omega-Ops",
    now: datetime | None = None,
) -> dict[str, Any]:
    observed_at = (now or datetime.now(timezone.utc)).isoformat()
    legacy_path = f"/repos/{owner}/{legacy}"
    core_path = f"/repos/{owner}/{core}"
    ops_path = f"/repos/{owner}/{ops}"

    identity_mode: str
    identity: dict[str, Any]
    try:
        _, user = client.get("/user")
        if not isinstance(user, dict):
            raise AuthorityProbeError("GitHub user identity response is invalid")
        identity_mode = "USER_SCOPED"
        identity = {
            "authenticated_login": user.get("login"),
            "identity_verified": str(user.get("login", "")).lower() == owner.lower(),
        }
    except AuthorityProbeError:
        _, installation = client.get("/installation")
        if not isinstance(installation, dict):
            raise AuthorityProbeError("GitHub installation identity response is invalid")
        identity_mode = "INSTALLATION_TEMPLATE"
        identity = {
            "installation_id": installation.get("id"),
            "account_login": installation.get("account", {}).get("login"),
            "identity_verified": (
                str(installation.get("account", {}).get("login", "")).lower()
                == owner.lower()
            ),
            "repository_selection": installation.get("repository_selection"),
            "installation_permissions": installation.get("permissions", {}),
        }

    _, legacy_repo = client.get(legacy_path)
    if not isinstance(legacy_repo, dict):
        raise AuthorityProbeError("legacy repository response is invalid")
    _, actions = client.get(f"{legacy_path}/actions/permissions")
    _, rulesets = client.get(f"{legacy_path}/rulesets?includes_parents=false")
    _, head = client.get(f"{legacy_path}/git/ref/heads/main")
    core_repo = client.optional(core_path)
    ops_repo = client.optional(ops_path)

    checks: dict[str, bool] = {
        "owner_identity": bool(identity["identity_verified"]),
        "legacy_admin": _repo_admin(legacy_repo),
        "legacy_actions_readable": isinstance(actions, dict),
        "legacy_rulesets_readable": isinstance(rulesets, list),
        "legacy_main_readable": True,
        "core_target_absent_or_owned": (
            core_repo is None
            or str(core_repo.get("owner", {}).get("login", "")).lower() == owner.lower()
        ),
        "ops_target_absent_or_owned": (
            ops_repo is None
            or str(ops_repo.get("owner", {}).get("login", "")).lower() == owner.lower()
        ),
    }

    blockers: list[str] = []
    if not checks["owner_identity"]:
        blockers.append("AUTHENTICATED_ACCOUNT_MISMATCH")
    if not checks["legacy_admin"]:
        blockers.append("LEGACY_ADMINISTRATION_UNAVAILABLE")
    if not checks["core_target_absent_or_owned"]:
        blockers.append("CORE_TARGET_OWNER_CONFLICT")
    if not checks["ops_target_absent_or_owned"]:
        blockers.append("OPS_TARGET_OWNER_CONFLICT")

    route_ready = False
    route_detail: dict[str, Any]
    if identity_mode == "USER_SCOPED":
        route_ready = all(
            checks[name]
            for name in (
                "owner_identity",
                "legacy_admin",
                "legacy_actions_readable",
                "legacy_rulesets_readable",
                "core_target_absent_or_owned",
                "ops_target_absent_or_owned",
            )
        )
        route_detail = {
            "authority_mode": identity_mode,
            "repository_creation_endpoint": "/user/repos",
            "repository_creation_mutation_performed": False,
            "settings_mutation_performed": False,
            **identity,
        }
    else:
        permissions = identity.get("installation_permissions", {})
        permission_checks = {
            "all_repositories_selection": identity.get("repository_selection") == "all",
            "administration_write": _permission_write(permissions.get("administration")),
            "contents_write": _permission_write(permissions.get("contents")),
            "metadata_read": _permission_at_least_read(permissions.get("metadata")),
        }
        checks.update(permission_checks)
        if not permission_checks["all_repositories_selection"]:
            blockers.append("INSTALLATION_SELECTED_REPOSITORIES_ONLY")
        if not permission_checks["administration_write"]:
            blockers.append("INSTALLATION_ADMINISTRATION_WRITE_MISSING")
        if not permission_checks["contents_write"]:
            blockers.append("INSTALLATION_CONTENTS_WRITE_MISSING")
        if not permission_checks["metadata_read"]:
            blockers.append("INSTALLATION_METADATA_READ_MISSING")
        route_ready = all(checks.values())
        route_detail = {
            "authority_mode": identity_mode,
            "repository_creation_endpoint": f"{legacy_path}/generate",
            "repository_creation_mutation_performed": False,
            "settings_mutation_performed": False,
            **identity,
        }

    status = "AUTHORITY_READY_FOR_FRESH_OWNER_AUTHORISED_APPLY"
    if blockers or not route_ready:
        status = "AUTHORITY_BLOCKED_EXACT_REMEDIATION_REQUIRED"

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        "observed_at": observed_at,
        "owner": owner,
        "legacy": legacy,
        "core": core,
        "ops": ops,
        "legacy_main_sha": _head_sha(head),
        "core_target_exists": core_repo is not None,
        "ops_target_exists": ops_repo is not None,
        "route": route_detail,
        "checks": checks,
        "blockers": sorted(set(blockers)),
        "owner_authorization_still_required": True,
        "provider_apply_performed": False,
        "provider_mutation_performed": False,
        "credential_value_recorded": False,
    }
    payload["receipt_sha256"] = canonical_sha256(payload)
    return payload


def missing_authority_receipt(*, now: datetime | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "AUTHORITY_UNAVAILABLE_NO_PRIVATE_CREDENTIAL",
        "observed_at": (now or datetime.now(timezone.utc)).isoformat(),
        "route": None,
        "checks": {"private_credential_present": False},
        "blockers": ["GH_ADMIN_TOKEN_NOT_PRESENT_IN_PRIVATE_PROCESS"],
        "owner_authorization_still_required": True,
        "provider_apply_performed": False,
        "provider_mutation_performed": False,
        "credential_value_recorded": False,
    }
    payload["receipt_sha256"] = canonical_sha256(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--owner", default="mosianekk-lang")
    parser.add_argument("--legacy", default="Federation-Omega")
    parser.add_argument("--core", default="Federation-Omega-Core")
    parser.add_argument("--ops", default="Federation-Omega-Ops")
    args = parser.parse_args()
    token = os.getenv("GH_ADMIN_TOKEN", "")
    if token:
        receipt = probe_authority(
            GitHubReadClient(token),
            owner=args.owner,
            legacy=args.legacy,
            core=args.core,
            ops=args.ops,
        )
    else:
        receipt = missing_authority_receipt()
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "AUTHORITY_READY_FOR_FRESH_OWNER_AUTHORISED_APPLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
