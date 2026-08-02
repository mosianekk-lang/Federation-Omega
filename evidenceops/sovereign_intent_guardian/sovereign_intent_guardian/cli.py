"""Local-only CLI for the guardian foundation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import secrets
from typing import Sequence

from .contracts import AuditRequest, parse_json_strict
from .store import GuardianStore
from .worker import GuardianWorker


def _json_file(path: str) -> dict:
    return parse_json_strict(Path(path).read_text(encoding="utf-8"))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Read-only Sovereign Intent Guardian")
    root.add_argument("--database", required=True, help="Explicit local SQLite database path")
    root.add_argument(
        "--trusted-attestation-registry",
        help="JSON object mapping trusted verifier IDs to exact continuity-binding hashes",
    )
    root.add_argument(
        "--trusted-resume-registry",
        help="JSON object mapping record hashes to exact stop-resume authority records",
    )
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    enqueue = sub.add_parser("enqueue")
    enqueue.add_argument("request")
    enqueue.add_argument("--idempotency-key")
    work = sub.add_parser("work-once")
    work.add_argument("--worker-id", required=True)
    work.add_argument("--boot-id")
    sub.add_parser("status")
    readback = sub.add_parser("readback")
    readback.add_argument("task_id")
    stop = sub.add_parser("stop")
    stop.add_argument("--scope", required=True, choices=["GLOBAL", "MISSION", "REQUIREMENT"])
    stop.add_argument("--subject", required=True)
    stop.add_argument("--mission-version", required=True, type=int)
    stop.add_argument("--reason-code", required=True)
    resume = sub.add_parser("resume")
    resume.add_argument("--scope", required=True, choices=["GLOBAL", "MISSION", "REQUIREMENT"])
    resume.add_argument("--subject", required=True)
    resume.add_argument("--new-mission-version", required=True, type=int)
    resume.add_argument("--expected-generation", required=True, type=int)
    resume.add_argument("--authority-record-hash", required=True)
    delivered = sub.add_parser("record-delivered-output")
    delivered.add_argument("--occurrence-id", required=True)
    delivered.add_argument("--mission-id", required=True)
    delivered.add_argument("--mission-version", required=True, type=int)
    delivered.add_argument("--payload-file", required=True)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    trusted = _json_file(args.trusted_attestation_registry) if args.trusted_attestation_registry else {}
    resume_records = _json_file(args.trusted_resume_registry) if args.trusted_resume_registry else {}
    store = GuardianStore(
        args.database,
        trusted_attestations=trusted,
        trusted_resume_records=resume_records,
    )
    store.initialize()
    if args.command == "init-db":
        result = store.health()
    elif args.command == "enqueue":
        request = AuditRequest.from_dict(_json_file(args.request))
        result = {"task_id": store.enqueue(request, idempotency_key=args.idempotency_key)}
    elif args.command == "work-once":
        boot_id = args.boot_id or f"boot-{secrets.token_hex(8)}"
        worker = GuardianWorker(store, worker_id=args.worker_id, boot_id=boot_id)
        worker.start()
        result = dict(worker.run_once())
    elif args.command == "status":
        result = store.health()
    elif args.command == "readback":
        result = store.semantic_readback(args.task_id)
    elif args.command == "stop":
        result = {"control_generation": store.set_stop(
            scope=args.scope,
            subject=args.subject,
            mission_version=args.mission_version,
            reason_code=args.reason_code,
        )}
    elif args.command == "resume":
        result = {"control_generation": store.clear_stop(
            scope=args.scope,
            subject=args.subject,
            new_mission_version=args.new_mission_version,
            expected_generation=args.expected_generation,
            authority_record_hash=args.authority_record_hash,
        )}
    else:
        payload_hash = hashlib.sha256(Path(args.payload_file).read_bytes()).hexdigest()
        count, ledger_hash = store.record_delivered_output(
            occurrence_id=args.occurrence_id,
            mission_id=args.mission_id,
            mission_version=args.mission_version,
            payload_hash=payload_hash,
        )
        result = {"delivered_output_count": count, "output_ledger_hash": ledger_hash}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0
