#!/usr/bin/env python3
"""Fail closed on unsafe Apps Script web-handler authorization patterns.

The scanner accepts source text only. It never reads or prints configured
credential values.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

_AUTH_SUBSTITUTION = re.compile(
    r"(?:approvalKey|gatewayToken|token|authorization)\s*\|\|\s*"
    r"(?:CONFIG\.)?(?:APPROVAL_KEY|GATEWAY_TOKEN|TOKEN|AUTHORIZATION)",
    re.IGNORECASE,
)
_HARDCODED_AUTH = re.compile(
    r"(?:APPROVAL_KEY|GATEWAY_TOKEN|AUTHORIZATION_TOKEN)\s*:\s*"
    r"['\"][^'\"]+['\"]",
    re.IGNORECASE,
)
_PUBLIC_WEBAPP = re.compile(
    r"(?:['\"]access['\"]\s*:\s*['\"]ANYONE['\"]|"
    r"access\s*:\s*['\"]ANYONE['\"])",
    re.IGNORECASE,
)
_DO_POST = re.compile(r"\bfunction\s+doPost\s*\(", re.IGNORECASE)


class AppsScriptSecurityError(ValueError):
    """Raised when Apps Script source violates the authorization contract."""


def validate_apps_script_source(source: str) -> str:
    if not isinstance(source, str) or not source.strip():
        raise AppsScriptSecurityError("Apps Script source is required")

    if _AUTH_SUBSTITUTION.search(source):
        raise AppsScriptSecurityError(
            "Caller authorization must not fall back to a configured "
            "approval value"
        )

    if _HARDCODED_AUTH.search(source):
        raise AppsScriptSecurityError(
            "Authorization material must not be hardcoded in Apps Script source"
        )

    if _PUBLIC_WEBAPP.search(source) and _DO_POST.search(source):
        raise AppsScriptSecurityError(
            "Privileged doPost handler must not use public ANYONE web-app access"
        )

    return source


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    args = parser.parse_args()

    path = Path(args.source)
    validate_apps_script_source(path.read_text(encoding="utf-8"))
    print("APPS_SCRIPT_AUTHORIZATION_SOURCE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
