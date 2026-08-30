#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJECT = "sov-hybrid-suite"
PROJECT_NUMBER = "257649435135"
DEPLOYER_SA = f"superior-logic-deployer@{PROJECT}.iam.gserviceaccount.com"
SERVICES = (
    {"name": "federation-omega-operator", "region": "africa-south1", "expected_sa": f"fo-operator-sa@{PROJECT}.iam.gserviceaccount.com"},
    {"name": "afeme-sovereign-control-plane-v4", "region": "africa-south1", "expected_sa": f"afeme-sovereign-runtime-v4@{PROJECT}.iam.gserviceaccount.com"},
)
READ_PATHS = ("/", "/health", "/openapi.json", "/openapi.yaml")


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def get_json(url: str, token: str = "") -> dict[str, object]:
    headers = {"Accept": "application/json, text/yaml, text/plain;q=0.9"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read().decode("utf-8", errors="replace")
            ctype = str(response.headers.get("Content-Type") or "")
            parsed: object = None
            if "json" in ctype or raw.lstrip().startswith(("{", "[")):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = None
            safe_summary: dict[str, object] = {
                "http_status": int(response.status),
                "content_type": ctype[:200],
                "body_sha256": digest(raw),
                "body_length": len(raw),
            }
            if isinstance(parsed, dict):
                safe_summary["json_keys"] = sorted(str(k) for k in parsed.keys())[:100]
                for key in ("service", "version", "status", "mode", "runtime", "project", "projectId", "region", "serviceName"):
                    value = parsed.get(key)
                    if isinstance(value, (str, int, float, bool)):
                        safe_summary[key] = value
                actions = parsed.get("allowedActions") or parsed.get("capabilities") or parsed.get("actions")
                if isinstance(actions, list):
                    safe_summary["advertised_actions"] = [str(x) for x in actions[:100]]
            return safe_summary
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return {
            "http_status": int(exc.code),
            "body_sha256": digest(raw),
            "body_length": len(raw),
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"http_status": None, "transport_error": type(exc).__name__}


def describe_service(name: str, region: str) -> dict[str, object]:
    proc = run(
        "gcloud", "run", "services", "describe", name,
        "--project", PROJECT,
        "--region", region,
        "--platform", "managed",
        "--format=json",
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return {"exists": False, "name": name, "region": region}
    data = json.loads(proc.stdout)
    spec = data.get("spec") or {}
    template = spec.get("template") or {}
    template_spec = template.get("spec") or {}
    status = data.get("status") or {}
    metadata = data.get("metadata") or {}
    annotations = metadata.get("annotations") or {}
    traffic = status.get("traffic") or []
    sa = str(template_spec.get("serviceAccountName") or template.get("serviceAccount") or "")
    url = str(status.get("url") or "")
    return {
        "exists": True,
        "name": name,
        "region": region,
        "service_account": sa,
        "url": url,
        "latest_ready_revision": str(status.get("latestReadyRevisionName") or ""),
        "latest_created_revision": str(status.get("latestCreatedRevisionName") or ""),
        "ingress": str(annotations.get("run.googleapis.com/ingress") or ""),
        "traffic": traffic,
    }


def id_token(audience: str) -> str:
    proc = run("gcloud", "auth", "print-identity-token", f"--audiences={audience}")
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def main() -> int:
    active = run("gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)")
    active_account = active.stdout.strip().splitlines()[0] if active.returncode == 0 and active.stdout.strip() else ""
    if active_account != DEPLOYER_SA:
        raise SystemExit("canonical WIF deployer identity required")

    service_receipts: list[dict[str, object]] = []
    privileged_matches: list[dict[str, object]] = []
    callable_privileged: list[dict[str, object]] = []
    for target in SERVICES:
        info = describe_service(target["name"], target["region"])
        info["expected_service_account"] = target["expected_sa"]
        info["runtime_identity_matches_expected"] = bool(
            info.get("exists") and info.get("service_account") == target["expected_sa"]
        )
        probes: dict[str, object] = {}
        url = str(info.get("url") or "")
        if url:
            token = id_token(url)
            info["identity_token_minted"] = bool(token)
            for path in READ_PATHS:
                probes[path] = {
                    "unauthenticated": get_json(url.rstrip("/") + path),
                    "wif_authenticated": get_json(url.rstrip("/") + path, token) if token else {"http_status": None, "token_unavailable": True},
                }
        else:
            info["identity_token_minted"] = False
        info["read_probes"] = probes
        service_receipts.append(info)
        if info["runtime_identity_matches_expected"]:
            privileged_matches.append({
                "service": target["name"],
                "region": target["region"],
                "service_account": target["expected_sa"],
            })
            authenticated_success = any(
                isinstance(value, dict)
                and isinstance(value.get("wif_authenticated"), dict)
                and value["wif_authenticated"].get("http_status") == 200
                for value in probes.values()
            )
            if authenticated_success:
                callable_privileged.append({
                    "service": target["name"],
                    "region": target["region"],
                    "service_account": target["expected_sa"],
                    "url": url,
                })

    receipt = {
        "schema": "SOVARA_PRIVILEGED_CONTROL_RUNTIME_CENSUS_V1",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_id": PROJECT,
        "project_number": PROJECT_NUMBER,
        "active_account": active_account,
        "services": service_receipts,
        "privileged_runtime_identity_matches": privileged_matches,
        "wif_callable_privileged_runtimes": callable_privileged,
        "provider_mutation_performed": False,
        "secret_payload_accessed": False,
        "credential_values_recorded": False,
    }
    receipt["receipt_sha256"] = digest(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    out = Path(os.environ.get("SOVARA_RECEIPT_DIR", ".")) / "PRIVILEGED_CONTROL_RUNTIME_CENSUS.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "privileged_runtime_identity_matches": privileged_matches,
        "wif_callable_privileged_runtimes": callable_privileged,
        "receipt_sha256": receipt["receipt_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
