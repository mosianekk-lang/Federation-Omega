from __future__ import annotations

import argparse
import json

from .canary import run_civitas_canary
from .service import serve
from .suite import FederationCivitasSuite


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m federation.civitas")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("canary")
    sub.add_parser("manifest")
    sub.add_parser("catalog")
    query = sub.add_parser("query")
    query.add_argument("question")
    server = sub.add_parser("serve")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    suite = FederationCivitasSuite()
    if args.command == "canary":
        payload = run_civitas_canary()
    elif args.command == "manifest":
        payload = suite.manifest()
    elif args.command == "catalog":
        payload = suite.catalog.as_mapping()
    elif args.command == "query":
        payload = suite.query(args.question)
    else:
        serve(host=args.host, port=args.port)
        return 0
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, default=str))
    return 0 if payload.get("status", "PASS") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
