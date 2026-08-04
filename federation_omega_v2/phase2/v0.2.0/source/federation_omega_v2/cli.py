from __future__ import annotations
import argparse,json
from pathlib import Path
from .core import EventStore,CanonicalQueryService,import_canonical_register,run_evidenceops_reference_mission

def main():
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest="cmd",required=True)
    command=sub.add_parser("init"); command.add_argument("--db",required=True)
    command=sub.add_parser("import-register"); command.add_argument("--db",required=True); command.add_argument("--register",required=True)
    command=sub.add_parser("reference-mission"); command.add_argument("--db",required=True)
    command=sub.add_parser("verify"); command.add_argument("--db",required=True)
    command=sub.add_parser("query-system"); command.add_argument("--db",required=True); command.add_argument("--system",required=True)
    args=parser.parse_args(); store=EventStore(args.db)
    if args.cmd=="init": result={"state":"INITIALIZED"}
    elif args.cmd=="import-register": result=import_canonical_register(store,json.loads(Path(args.register).read_text()))
    elif args.cmd=="reference-mission": result=run_evidenceops_reference_mission(store)
    elif args.cmd=="verify": result=store.verify()
    else: result=CanonicalQueryService(store).system(args.system)
    print(json.dumps(result,indent=2,sort_keys=True)); return 0

if __name__=="__main__": raise SystemExit(main())
