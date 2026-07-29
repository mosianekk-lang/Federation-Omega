#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import os
import secrets
from pathlib import Path


def b64_key() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create local MODISA control secrets without revealing them.")
    parser.add_argument("--target", default=".env.local", help="Workspace-relative env-file path")
    parser.add_argument("--force", action="store_true", help="Replace an existing target")
    args = parser.parse_args()

    root = Path.cwd().resolve()
    target = (root / args.target).resolve()
    if target != root and root not in target.parents:
        raise SystemExit("Target must remain inside the current workspace")
    if target.is_symlink():
        raise SystemExit("Refusing to write secrets through a symlink")
    if target.exists() and not args.force:
        raise SystemExit(f"{target} already exists; use --force only after preserving it")

    lines = [
        "# OpenAI key is intentionally left blank. Add it through your secure local workflow.",
        "OPENAI_API_KEY=",
        "MODISA_PRIMARY_MODEL=gpt-5.6-sol",
        "MODISA_PREP_MODEL=gpt-5.6-terra",
        "MODISA_VOLUME_MODEL=gpt-5.6-luna",
        f"MODISA_LEDGER_HMAC_KEY_B64={b64_key()}",
        f"MODISA_EVIDENCE_AES_KEY_B64={b64_key()}",
        f"MODISA_JWT_SECRET={secrets.token_urlsafe(48)}",
        "MODISA_DATABASE_PATH=./state/modisa_v2.sqlite3",
        "MODISA_SESSION_DB=./state/agent_sessions.sqlite3",
        "MODISA_SESSION_BACKEND=sqlite",
        "MODISA_SESSION_DATABASE_URL=",
        "MODISA_EVIDENCE_ROOT=./evidence_vault",
        "MODISA_DATA_ROOT=./data",
        "MODISA_AUTH_DISABLED_DEV=false",
        "MODISA_ALLOW_UNENCRYPTED_DEV=false",
        "MODISA_EXTERNAL_ACTIONS_ENABLED=false",
        "MODISA_MAX_AGENT_TURNS=32",
        "MODISA_LOG_LEVEL=INFO",
        "",
    ]
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write("\n".join(lines))
    except Exception:
        target.unlink(missing_ok=True)
        raise
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    print(f"Created protected local configuration: {target}")
    print("OPENAI_API_KEY remains blank and was not printed or retrieved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
