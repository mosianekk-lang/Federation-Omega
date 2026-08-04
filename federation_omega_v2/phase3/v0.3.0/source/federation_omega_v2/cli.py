from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import EventStore, CanonicalQueryService, import_canonical_register
from .matter_adapter import load_snapshot, run_phase3_mission


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--db", required=True)

    register = sub.add_parser("import-register")
    register.add_argument("--db", required=True)
    register.add_argument("--register", required=True)

    matter = sub.add_parser("phase3-matter")
    matter.add_argument("--db", required=True)
    matter.add_argument("--snapshot", required=True)

    verify = sub.add_parser("verify")
    verify.add_argument("--db", required=True)

    query = sub.add_parser("query-system")
    query.add_argument("--db", required=True)
    query.add_argument("--system", required=True)

    args = parser.parse_args()
    store = EventStore(args.db)
    if args.command == "init":
        result = {"state": "INITIALIZED", "db": args.db}
    elif args.command == "import-register":
        register_data = json.loads(Path(args.register).read_text(encoding="utf-8"))
        result = import_canonical_register(store, register_data)
    elif args.command == "phase3-matter":
        result = run_phase3_mission(
            store,
            load_snapshot(args.snapshot),
            "2026-08-04T19:46:00+00:00",
        )
    elif args.command == "verify":
        result = store.verify()
    else:
        result = CanonicalQueryService(store).system(args.system)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
