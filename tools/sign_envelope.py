#!/usr/bin/env python3
"""Create an exact v1.1 signed public-gateway envelope.

The HMAC key is read from an environment variable and is never printed. The
output contract matches candidate/public_gateway/Gateway_Security.gs exactly.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import hmac
import json
import os
import re
import secrets
from typing import Any

CANONICAL_TARGET_PROJECT_NUMBER = "257649435135"
ALLOWED_ACTIONS = frozenset({"STATUS", "CHALLENGE"})
_NONCE_RE = re.compile(r"^[A-Za-z0-9_.:-]{16,160}$")
_CREDENTIAL_LIKE = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/\-]+=*", re.IGNORECASE),
    re.compile(r"\b(?:sk-(?:proj-)?|gh[pousr]_)[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_unsigned_envelope(
    *,
    action: str,
    timestamp: str | None = None,
    nonce: str | None = None,
    challenge: str | None = None,
    target_project_number: str = CANONICAL_TARGET_PROJECT_NUMBER,
) -> dict[str, Any]:
    normalized_action = str(action).strip().upper()
    if normalized_action not in ALLOWED_ACTIONS:
        raise ValueError(f"Unsupported gateway action: {normalized_action or '<empty>'}")
    if target_project_number != CANONICAL_TARGET_PROJECT_NUMBER:
        raise ValueError("The source candidate signs only the canonical target project")

    issued_at = timestamp or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    try:
        parsed = datetime.fromisoformat(issued_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")

    nonce_value = nonce or f"nonce-{secrets.token_hex(16)}"
    if not _NONCE_RE.fullmatch(nonce_value):
        raise ValueError("nonce must be 16-160 public-safe characters")

    if normalized_action == "STATUS":
        if challenge is not None:
            raise ValueError("STATUS does not accept a challenge payload")
        payload: dict[str, Any] = {}
    else:
        value = str(challenge or "")
        if not value or len(value) > 4096:
            raise ValueError("CHALLENGE requires 1-4096 characters")
        if any(pattern.search(value) for pattern in _CREDENTIAL_LIKE):
            raise ValueError("Credential-like challenge material is prohibited")
        payload = {"challenge": value}

    return {
        "timestamp": parsed.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "nonce": nonce_value,
        "action": normalized_action,
        "targetProjectNumber": target_project_number,
        "payload": payload,
    }


def sign_envelope(unsigned: dict[str, Any], secret: str) -> dict[str, Any]:
    if len(secret) < 32:
        raise ValueError("The gateway HMAC secret must contain at least 32 characters")
    canonical = canonical_json(unsigned)
    signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return {**unsigned, "signature": signature}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--secret-env", default="SOVARA_GATEWAY_HMAC_SECRET")
    parser.add_argument("--action", required=True, choices=["STATUS", "CHALLENGE", "status", "challenge"])
    parser.add_argument("--challenge")
    parser.add_argument("--timestamp")
    parser.add_argument("--nonce")
    parser.add_argument("--target-project-number", default=CANONICAL_TARGET_PROJECT_NUMBER)
    parser.add_argument("--output")
    args = parser.parse_args()

    secret = os.environ.get(args.secret_env, "")
    if len(secret) < 32:
        raise SystemExit(f"{args.secret_env} must be configured with at least 32 characters")

    envelope = sign_envelope(
        build_unsigned_envelope(
            action=args.action,
            timestamp=args.timestamp,
            nonce=args.nonce,
            challenge=args.challenge,
            target_project_number=args.target_project_number,
        ),
        secret,
    )
    rendered = json.dumps(envelope, indent=2, sort_keys=True) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
