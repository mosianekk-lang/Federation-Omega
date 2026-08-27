from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if any(marker in key.lower() for marker in ("token", "authorization", "credential"))
                else _redact(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def invoke(operator_url: str, action: str, payload: dict[str, Any]) -> dict[str, Any]:
    admin_token = os.environ.get("FO_ADMIN_TOKEN", "")
    identity_token = os.environ.get("FO_IDENTITY_TOKEN", "")
    if not admin_token and not identity_token:
        raise RuntimeError("FO_ADMIN_TOKEN or FO_IDENTITY_TOKEN is required")
    headers = {"accept": "application/json", "content-type": "application/json"}
    if admin_token:
        headers["x-fo-admin-token"] = admin_token
    else:
        headers["authorization"] = f"Bearer {identity_token}"
    request = urllib.request.Request(
        operator_url.rstrip("/") + "/execute",
        method="POST",
        headers=headers,
        data=json.dumps({"action": action, "payload": payload}, separators=(",", ":")).encode(),
    )
    try:
        with urllib.request.urlopen(request, timeout=1200) as response:
            result = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            error = json.loads(raw)
        except json.JSONDecodeError:
            error = {"text": raw[:2000]}
        raise RuntimeError(f"operator HTTP {exc.code}: {json.dumps(_redact(error))}") from exc
    if result.get("ok") is not True:
        raise RuntimeError(f"operator rejected {action}: {json.dumps(_redact(result))}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--operator", required=True)
    parser.add_argument("--action", required=True)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.payload.read_text(encoding="utf-8"))
    result = invoke(args.operator, args.action, payload)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(_redact(result), sort_keys=True))


if __name__ == "__main__":
    main()
