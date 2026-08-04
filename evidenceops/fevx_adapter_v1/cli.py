from __future__ import annotations

import argparse
import json
from pathlib import Path

from .adapter import EvidenceOpsFEVXAdapter
from .core import atomic_write_json
from .store import DerivedStore


def main() -> int:
    parser = argparse.ArgumentParser(description="EvidenceOps FEVX read-only adapter")
    parser.add_argument("--database", required=True)
    parser.add_argument("--repo-root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)

    analyse = sub.add_parser("analyse")
    analyse.add_argument("--packet", required=True)
    analyse.add_argument("--output", required=True)

    verify = sub.add_parser("verify")
    verify.add_argument("--output", required=False)

    args = parser.parse_args()
    store = DerivedStore(args.database)
    try:
        if args.command == "analyse":
            packet = json.loads(Path(args.packet).read_text(encoding="utf-8"))
            result = EvidenceOpsFEVXAdapter(
                store=store,
                repo_root=args.repo_root,
            ).analyse(packet)
        else:
            result = store.verify_all()
        if getattr(args, "output", None):
            atomic_write_json(Path(args.output), result)
        else:
            print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("status", "PASSED") != "FAILED" else 1
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
