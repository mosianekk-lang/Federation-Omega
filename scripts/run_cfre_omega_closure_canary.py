#!/usr/bin/env python3
"""Run the provider-disabled CFRE Omega closure canary."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidenceops.build_system.runtime_controls import (  # noqa: E402
    ACKNOWLEDGED,
    ORPHANED_UNACKNOWLEDGED,
    SYSTEM_IDENTITY,
    CancellationToken,
    CooperativeCancellation,
    DeliveryJournal,
    DistinctRouteCircuit,
    HeartbeatScheduler,
    HandoffStore,
    NoSafeRoute,
    PolicyDenied,
    Route,
    RuntimePolicy,
)


BASE_COMMIT = "d54e81a7044b964fcdadbe30bbbd4c26546257e2"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(value):
    raw = value if isinstance(value, bytes) else canonical(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def run_canary() -> dict:
    mandatory = {}
    negative = {}
    observations = {}

    with tempfile.TemporaryDirectory(prefix="cfre-omega-canary-") as temp:
        root = Path(temp)

        heartbeats = []
        heartbeat_ready = threading.Event()

        def capture(heartbeat):
            heartbeats.append(asdict(heartbeat))
            if len(heartbeats) >= 2:
                heartbeat_ready.set()

        scheduler = HeartbeatScheduler(0.01, capture)
        scheduler.start()
        heartbeat_passed = heartbeat_ready.wait(1.0)
        stopped = scheduler.stop()
        mandatory["BACKGROUND_HEARTBEAT_SCHEDULER"] = heartbeat_passed and stopped
        observations["heartbeat_count"] = len(heartbeats)

        token_a = CancellationToken(root / "control.sqlite3", "canary-mission")
        token_b = CancellationToken(root / "control.sqlite3", "canary-mission")
        token_a.cancel("canary stop")
        try:
            token_b.checkpoint()
            cancellation_passed = False
        except CooperativeCancellation:
            cancellation_passed = True
        mandatory["SHARED_COOPERATIVE_CANCELLATION"] = cancellation_passed

        circuit = DistinctRouteCircuit(
            root / "routes.sqlite3",
            [Route("primary", 100), Route("local-fallback", 90), Route("provider", 80, provider_effect=True)],
        )
        circuit.open("primary", "sha256:canary-failure")
        selected = circuit.select_distinct("primary", providers_enabled=False)
        mandatory["DISTINCT_ROUTE_CIRCUIT_BREAKER"] = selected.route_id == "local-fallback"
        observations["selected_route"] = selected.route_id

        handoff_payload = {
            "identity": SYSTEM_IDENTITY,
            "directive": "continue existing repair",
            "next_action": "terminal delivery",
        }
        handoff = HandoffStore(root / "handoff.json")
        handoff.write("tx-handoff", handoff_payload)
        mandatory["HASH_VERIFIED_HANDOFF_PERSISTENCE"] = (
            handoff.read("tx-handoff") == handoff_payload
        )

        journal = DeliveryJournal(root / "delivery.sqlite3")
        artifact_hash = sha256({"result": "canary"})
        acknowledged = journal.deliver(
            "tx-ack", "canary-artifact", artifact_hash, acknowledgement="local-readback"
        )
        orphan = journal.deliver(
            "tx-orphan", "unacknowledged-artifact", artifact_hash, acknowledgement=None
        )
        mandatory["JOURNALED_TERMINAL_DELIVERY"] = (
            acknowledged["state"] == ACKNOWLEDGED
            and orphan["state"] == ORPHANED_UNACKNOWLEDGED
        )

        policy = RuntimePolicy()
        try:
            policy.admit("PROVIDER_WRITE")
            provider_blocked = False
        except PolicyDenied:
            provider_blocked = True
        negative["PROVIDER_ACTION_BLOCKED"] = provider_blocked

        try:
            policy.admit("LOCAL_TEST", target_identity="CFRE-OMEGA-REPLACEMENT")
            new_system_blocked = False
        except PolicyDenied:
            new_system_blocked = True
        negative["NEW_SYSTEM_CREATION_REJECTED"] = new_system_blocked
        negative["EVENT_CHAIN_VERIFIED"] = journal.verify_event_chain()

    receipt = {
        "schema": "CFRE-OMEGA-PROVIDER-DISABLED-CANARY-1",
        "identity": SYSTEM_IDENTITY,
        "base_commit": BASE_COMMIT,
        "providers_enabled": False,
        "provider_effects": 0,
        "mandatory_controls": mandatory,
        "negative_controls": negative,
        "mandatory_passed": sum(mandatory.values()),
        "mandatory_total": len(mandatory),
        "negative_passed": sum(negative.values()),
        "negative_total": len(negative),
        "passed": all(mandatory.values()) and all(negative.values()),
        "observations": observations,
        "truth_boundary": [
            "Local standard-library runtime only.",
            "No provider, GitHub, Library, Drive, email, or deployment mutation occurred.",
            "This receipt does not prove ChatGPT-native or private-plane binding."
        ],
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    receipt["receipt_sha256"] = sha256(receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run_canary()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=args.output.parent, delete=False
    ) as handle:
        json.dump(receipt, handle, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, args.output)
    readback = json.loads(args.output.read_text(encoding="utf-8"))
    observed_hash = readback.pop("receipt_sha256")
    if observed_hash != sha256(readback):
        raise SystemExit("receipt self-hash mismatch")
    print(json.dumps({"passed": receipt["passed"], "receipt_sha256": receipt["receipt_sha256"]}))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
