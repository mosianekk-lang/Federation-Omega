"""Offline operator CLI for the MODISA v3 sovereign execution fabric."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from . import __version__
from .sovereign_runtime import (
    DurableJournal,
    LaneContext,
    LaneResult,
    LaneSpec,
    MissionIR,
    ProofArtifact,
    SovereignOrchestrator,
)


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def _handler(context: LaneContext) -> LaneResult:
    payload = {"lane": context.lane.lane_id, "attempt": context.attempt, "state": "PROVEN"}
    proof = ProofArtifact(
        proof_id=f"proof-{context.lane.lane_id}",
        kind="READBACK",
        source_id="offline-demo",
        digest=_digest(json.dumps(payload, sort_keys=True)),
    )
    return LaneResult(payload, (proof,))


def demo(path: Path) -> dict[str, object]:
    lanes = (
        LaneSpec("inspect", "Inspect current state", 1, proof_requirements=("READBACK",)),
        LaneSpec("test", "Run deterministic tests", 2, proof_requirements=("READBACK",)),
        LaneSpec(
            "seal",
            "Seal proven result",
            3,
            dependencies=("inspect", "test"),
            proof_requirements=("READBACK",),
        ),
    )
    mission = MissionIR("MODISA-V3-OFFLINE-DEMO", 1, "prove the complete local runtime", lanes)
    journal = DurableJournal(path)
    try:
        receipt = SovereignOrchestrator(journal).run(
            mission, {lane.lane_id: _handler for lane in lanes}
        )
    finally:
        journal.close()
    return {
        "version": __version__,
        "mission_id": receipt.mission_id,
        "complete": receipt.complete,
        "claim_allowed": receipt.claim_allowed,
        "event_chain_valid": receipt.event_chain_valid,
        "lane_states": {key: value.value for key, value in receipt.lane_states.items()},
        "manual_user_tasks": list(receipt.manual_user_tasks),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="MODISA v3 sovereign runtime")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    demo_parser = subparsers.add_parser("demo", help="run a deterministic offline mission")
    demo_parser.add_argument("--state", type=Path, required=True)
    verify_parser = subparsers.add_parser("verify-journal", help="verify one mission event chain")
    verify_parser.add_argument("--state", type=Path, required=True)
    verify_parser.add_argument("--mission", required=True)
    args = parser.parse_args()
    if args.command == "demo":
        result = demo(args.state)
    else:
        journal = DurableJournal(args.state)
        try:
            result = {
                "mission_id": args.mission,
                "event_count": len(journal.events(args.mission)),
                "event_chain_valid": journal.verify_chain(args.mission),
            }
        finally:
            journal.close()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["event_chain_valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
