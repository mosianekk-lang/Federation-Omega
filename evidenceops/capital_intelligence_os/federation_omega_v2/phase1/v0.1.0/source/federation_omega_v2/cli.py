from __future__ import annotations

import argparse
import json
from pathlib import Path

from .canonical_query import CanonicalQueryService
from .event_store import EventStore
from .intent_compiler import compile_mission
from .models import Event


def read_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--db", required=True)

    append = sub.add_parser("append")
    append.add_argument("--db", required=True)
    append.add_argument("--event", required=True)

    compile_cmd = sub.add_parser("compile")
    compile_cmd.add_argument("--objective", required=True)
    compile_cmd.add_argument("--db")
    compile_cmd.add_argument("--deadline")
    compile_cmd.add_argument("--authority", default="A1")

    query = sub.add_parser("query")
    query.add_argument("--db", required=True)
    query.add_argument("--entity", required=True)

    verify = sub.add_parser("verify")
    verify.add_argument("--db", required=True)

    args = parser.parse_args()
    if args.command == "init":
        EventStore(args.db)
        result = {"state": "INITIALIZED", "db": args.db}
    elif args.command == "append":
        result = EventStore(args.db).append(Event(**read_json(args.event)))
    elif args.command == "compile":
        mission = compile_mission(
            args.objective,
            deadline=args.deadline,
            authority_ceiling=args.authority,
        )
        result = mission.to_dict()
        if args.db:
            EventStore(args.db).save_mission(result)
    elif args.command == "query":
        result = CanonicalQueryService(EventStore(args.db)).entity(args.entity)
    else:
        result = EventStore(args.db).verify()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
