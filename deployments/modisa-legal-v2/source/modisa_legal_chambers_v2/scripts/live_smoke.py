#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Running a script by path places only scripts/ on sys.path. Bind the project root
# explicitly so the documented `python scripts/live_smoke.py` command is valid.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modisa_v2.agents_runtime import SovereignLegalRuntime
from modisa_v2.config import get_settings
from modisa_v2.schemas import MissionRequest, RiskLevel
from modisa_v2.services import build_services


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    services = build_services(settings)
    runtime = SovereignLegalRuntime(services)
    try:
        result = await runtime.run(
            MissionRequest(
                matter_id=args.matter,
                mission=args.mission,
                jurisdiction=args.jurisdiction,
                forum=args.forum,
                risk_level=RiskLevel(args.risk),
                requested_work_product="live smoke result",
                source_paths=args.source,
                session_id=args.session,
            )
        )
    except RuntimeError as exc:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "matter_id": args.matter,
                    "mission": args.mission,
                    "model_execution_started": False,
                    "blocker": str(exc),
                    "api_key_present": settings.api_key_present,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 3
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0 if result.status == "completed" else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one live, proof-bound Agents SDK mission.")
    parser.add_argument("--matter", required=True)
    parser.add_argument("--mission", required=True)
    parser.add_argument("--jurisdiction", default="South Africa")
    parser.add_argument("--forum", default="UNSPECIFIED")
    parser.add_argument("--risk", choices=[r.value for r in RiskLevel], default="HIGH")
    parser.add_argument("--session", default="live-smoke")
    parser.add_argument("--source", action="append", default=[])
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
