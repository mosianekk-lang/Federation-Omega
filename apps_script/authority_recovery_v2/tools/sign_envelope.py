#!/usr/bin/env python3
"""Create canonical HMAC-SHA256 Apps Script request envelopes.

The secret is read from ``SOVARA_HMAC_SECRET`` or ``--secret-file`` and is
never included in output. ``gateway`` mode builds a v2 read-only gateway
request. ``admin`` mode signs an already prepared request JSON whose provider
receipt and effect permit have been independently issued.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import hmac
import json
import os
import secrets
import sys
from pathlib import Path
from typing import Any


def canonical(value: Any) -> str:
    if value is None or isinstance(value, (bool, int, float, str)):
        return json.dumps(value, separators=(",", ":"), ensure_ascii=True)
    if isinstance(value, list):
        return "[" + ",".join(canonical(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(
            json.dumps(key, ensure_ascii=True) + ":" + canonical(value[key])
            for key in sorted(value)
        ) + "}"
    raise TypeError(f"Unsupported value: {type(value)!r}")


def read_secret(path: Path | None) -> str:
    secret = (
        path.read_text(encoding="utf-8").strip()
        if path
        else os.environ.get("SOVARA_HMAC_SECRET", "")
    )
    if len(secret) < 32:
        raise SystemExit(
            "SOVARA_HMAC_SECRET or --secret-file must contain 32+ characters"
        )
    return secret


def sign(payload: dict[str, Any], secret: str) -> dict[str, Any]:
    unsigned = dict(payload)
    unsigned.pop("signature", None)
    signature = hmac.new(
        secret.encode("utf-8"),
        canonical(unsigned).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {**unsigned, "signature": signature}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("gateway", "admin"))
    parser.add_argument("--action")
    parser.add_argument("--target-project-number", default="257649435135")
    parser.add_argument("--payload", type=Path)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--secret-file", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    secret = read_secret(args.secret_file)
    if args.mode == "gateway":
        if not args.action:
            raise SystemExit("--action is required for gateway mode")
        payload: Any = {}
        if args.payload:
            payload = json.loads(args.payload.read_text(encoding="utf-8"))
        envelope = {
            "version": "2",
            "requestId": f"REQ-{secrets.token_hex(12)}",
            "action": args.action.strip().upper(),
            "targetProjectNumber": args.target_project_number,
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "nonce": secrets.token_urlsafe(24),
            "payload": payload,
        }
    else:
        if not args.request:
            raise SystemExit("--request is required for admin mode")
        envelope = json.loads(args.request.read_text(encoding="utf-8"))
        if not isinstance(envelope, dict):
            raise SystemExit("admin request must be a JSON object")
        envelope.setdefault(
            "timestamp", dt.datetime.now(dt.timezone.utc).isoformat()
        )
        envelope.setdefault("nonce", secrets.token_urlsafe(24))

    rendered = json.dumps(sign(envelope, secret), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
