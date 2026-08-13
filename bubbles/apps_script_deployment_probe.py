from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping
import urllib.error
import urllib.parse
import urllib.request


ARCHON_SCRIPT_DEPLOYMENT_ID = "AKfycbyaxovYOyaoMWFdsAZnbl2AIFU0PFY3hcGF-QRM1dmDqdtEHRFI7Ud7L_p7YCCVMG3J"
ARCHON_SCRIPT_URL = f"https://script.google.com/macros/s/{ARCHON_SCRIPT_DEPLOYMENT_ID}/exec"
EVIDENCE_BASIS = "USER_SUPPLIED_DEPLOYMENT_SCREENSHOT_PLUS_EXISTING_ARCHON_CONTROL_RECORDS"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _json_or_text(raw: str) -> object:
    try:
        return json.loads(raw)
    except Exception:
        return {"text": raw[:5000]}


def _http(url: str, *, follow_redirects: bool, timeout: int = 25) -> Mapping[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"accept": "application/json,text/plain,*/*"},
        method="GET",
    )
    opener = urllib.request.build_opener() if follow_redirects else urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            return {
                "http_status": int(response.status),
                "body": _json_or_text(raw),
                "location": response.headers.get("Location"),
                "final_url": response.geturl(),
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        return {
            "http_status": int(exc.code),
            "body": _json_or_text(raw),
            "location": exc.headers.get("Location"),
            "final_url": exc.geturl(),
        }
    except Exception as exc:  # pragma: no cover - provider runner dependent
        return {"transport_error": type(exc).__name__, "message": str(exc)[:700]}


def _url(action: str | None = None) -> str:
    if not action:
        return ARCHON_SCRIPT_URL
    return f"{ARCHON_SCRIPT_URL}?{urllib.parse.urlencode({'action': action})}"


def _semantic_classification(probe: Mapping[str, Any], *, expected_action: str | None = None) -> str:
    status = probe.get("http_status")
    body = probe.get("body")
    if status == 200 and isinstance(body, Mapping):
        if body.get("ok") is True:
            action = body.get("action") or body.get("status") or body.get("service")
            if expected_action and action and str(action).lower() not in {
                expected_action.lower(),
                "ok",
                "ready",
                "healthy",
                "done",
            }:
                return "HTTP_200_SEMANTIC_MISMATCH"
            return "SEMANTIC_JSON_OK"
        if "text" in body:
            return "HTTP_200_TEXT_SEMANTICS_UNVERIFIED"
        return "HTTP_200_JSON_SEMANTICS_UNVERIFIED"
    if status in {301, 302, 303, 307, 308}:
        return "REDIRECT_REACHABLE"
    if status in {401, 403}:
        return "AUTH_REQUIRED_REACHABLE"
    if status == 404:
        return "HTTP_404_REACHABLE"
    if "transport_error" in probe:
        return "TRANSPORT_UNREACHABLE"
    return "REACHABLE_UNCLASSIFIED"


def run_probe() -> dict[str, Any]:
    targets = {
        "root_no_redirect": (_url(), False, None),
        "health_no_redirect": (_url("health_check"), False, "health_check"),
        "health_follow_redirects": (_url("health_check"), True, "health_check"),
        "openapi_no_redirect": (_url("openapi"), False, "openapi"),
        "openapi_follow_redirects": (_url("openapi"), True, "openapi"),
    }
    probes: dict[str, Any] = {}
    for name, (url, follow, expected) in targets.items():
        response = _http(url, follow_redirects=follow)
        probes[name] = {
            "url": url,
            "follow_redirects": follow,
            "response": response,
            "classification": _semantic_classification(response, expected_action=expected),
        }

    health = probes["health_follow_redirects"]["classification"]
    openapi = probes["openapi_follow_redirects"]["classification"]
    if health == "SEMANTIC_JSON_OK":
        overall = "DEPLOYMENT_HEALTH_SEMANTICS_VERIFIED"
    elif health.startswith("HTTP_200") or openapi.startswith("HTTP_200"):
        overall = "DEPLOYMENT_HTTP_REACHABLE_SEMANTICS_UNVERIFIED"
    elif any(item["classification"] in {"REDIRECT_REACHABLE", "AUTH_REQUIRED_REACHABLE", "HTTP_404_REACHABLE"} for item in probes.values()):
        overall = "DEPLOYMENT_PROVIDER_REACHABLE_ACTION_SEMANTICS_UNVERIFIED"
    else:
        overall = "DEPLOYMENT_CURRENT_REACHABILITY_UNVERIFIED"

    return {
        "schema": "BUBBLES-ARCHON-APPS-SCRIPT-DEPLOYMENT-PROBE-V1",
        "evidence_basis": EVIDENCE_BASIS,
        "script_id": "12CrTP0YUQbUpBvLklf_tInjN_k3L5qt3Tkp-M9pIO_O4Cs8dsYRH7kPO",
        "deployment_id": ARCHON_SCRIPT_DEPLOYMENT_ID,
        "web_app_url": ARCHON_SCRIPT_URL,
        "overall_classification": overall,
        "mutation_attempted": False,
        "credential_values_recorded": False,
        "probes": probes,
        "truth_boundary": (
            "This is a public, read-only deployment-route probe. HTTP/redirect reachability is not mutation proof. "
            "Only action-specific semantic output may verify a claimed Apps Script capability."
        ),
    }


def augment_receipt(path: Path) -> dict[str, Any]:
    receipt = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    receipt.setdefault("surface_corrections", {})["archon_apps_script_exact_deployment"] = run_probe()
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe the exact ARCHON Apps Script web-app deployment without mutation.")
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args()
    receipt = augment_receipt(Path(args.receipt))
    print(json.dumps(receipt["surface_corrections"]["archon_apps_script_exact_deployment"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
