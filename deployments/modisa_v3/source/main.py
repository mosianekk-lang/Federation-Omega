from __future__ import annotations

import argparse
import json
import os

import uvicorn

from modisa_v2.api import create_app
from modisa_v2.config import get_settings

app = create_app()


def cli() -> None:
    parser = argparse.ArgumentParser(description="MODISA Sovereign Legal OS v2")
    parser.add_argument("--health", action="store_true", help="Print safe configuration health")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8421")))
    args = parser.parse_args()
    if args.health:
        settings = get_settings()
        print(
            json.dumps(
                {
                    "api_key_present": settings.api_key_present,
                    "proof_ledger_key_present": settings.ledger_hmac_key is not None,
                    "evidence_key_present": settings.evidence_aes_key is not None,
                    "authentication_configured": settings.auth_disabled_dev or bool(settings.jwt_secret),
                    "external_actions_enabled": settings.external_actions_enabled,
                },
                indent=2,
            )
        )
        return
    uvicorn.run("main:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    cli()
