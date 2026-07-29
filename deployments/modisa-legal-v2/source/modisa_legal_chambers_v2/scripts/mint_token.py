#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import time

import jwt
from dotenv import load_dotenv


def csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> int:
    load_dotenv(".env.local")
    load_dotenv(".env")
    parser = argparse.ArgumentParser(description="Mint a short-lived local MODISA JWT.")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--roles", required=True)
    parser.add_argument("--scopes", required=True)
    parser.add_argument("--matters", required=True)
    parser.add_argument("--minutes", type=int, default=30)
    args = parser.parse_args()
    secret = os.environ.get("MODISA_JWT_SECRET")
    if not secret:
        raise SystemExit("MODISA_JWT_SECRET is not configured")
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": args.subject,
            "roles": csv(args.roles),
            "scopes": csv(args.scopes),
            "matter_ids": csv(args.matters),
            "iat": now,
            "exp": now + max(1, args.minutes) * 60,
            "iss": "modisa-legal-v2-local",
        },
        secret,
        algorithm="HS256",
    )
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
