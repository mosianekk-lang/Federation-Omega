#!/usr/bin/env python3
"""Deterministic exhaustive verifier for the additive BCO-Prime successor v3."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarking.cfbe_omega import bco_prime_capability_fabric_v1 as core
from benchmarking.cfbe_omega import bco_prime_chat_forensics_v1 as legacy
from benchmarking.cfbe_omega import bco_prime_chat_forensics_v2 as v2
from benchmarking.cfbe_omega import bco_prime_successor_v3 as successor


def _assert_receipt(receipt: Mapping[str, Any], operation: str) -> None:
    if receipt.get("operation") != operation or not receipt.get("receipt_sha256"):
        raise AssertionError(f"invalid receipt for {operation}")
    if receipt.get("manualUserTasks") != [] or receipt.get("ownerActionRequired") is not False:
        raise AssertionError(f"owner burden contract failed for {operation}")


def _legacy_payload() -> dict[str, Any]:
    return {
        "expected_id": "conversation-1",
        "observed_id": "conversation-1",
        "expected_title": "Synthetic release verification",
        "observed_title": "Synthetic release verification",
        "conversation_id": "conversation-1",
        "sources": [
            {
                "source_id": "source-1",
                "kind": "native_export",
                "accessible": True,
                "captured": True,
                "sha256": "a" * 64,
            }
        ],
        "probes": [{"capability": "native_export", "supported": True}],
        "evidence": [{"evidence_id": "evidence-1", "conversation_id": "conversation-1"}],
        "available_kinds": ["native_export"],
        "events": [{"event_id": "event-1", "content": "bounded"}],
        "message_count": 1,
        "native_timestamp_count": 1,
        "user_final_message_present": True,
        "assistant_terminal_content_present": True,
        "steps": [{"step_id": "step-1", "kind": "local", "status": "COMPLETED"}],
        "final_tool_action_present": True,
        "final_response_commit_observed": True,
        "required_checkpoints": ["checkpoint-1"],
        "present_checkpoints": ["checkpoint-1"],
        "work_durations_seconds": [1],
        "connector_sources": [],
        "connector_errors": [],
        "errors": [],
        "durable_artifact_matches": ["artifact-1"],
        "provider_ref": "local-only",
        "claimed_outputs": ["output-1"],
        "proven_outputs": ["output-1"],
        "engine_state": "COMPLETE_VERIFIED",
        "native_export": True,
        "native_message_ids": True,
        "native_timestamps": True,
        "captured_source_count": 1,
        "terminal_sequence_captured": True,
        "provider_durability_proven": True,
        "gaps": [],
        "findings": {"state": "verified"},
        "evidence_refs": ["evidence-1"],
    }


def _strategy_payload() -> dict[str, Any]:
    return {
        "candidates": [
            {
                "strategy_id": "local-route",
                "failure_domain": "local",
                "expected_quality": 0.9,
                "evidence_strength": 0.9,
                "reliability": 0.9,
                "reversibility": 1.0,
                "information_gain": 0.8,
                "failure_domain_diversity": 0.5,
                "latency_cost": 0.1,
                "monetary_cost": 0.0,
                "owner_burden": 0.0,
                "risk": 0.1,
            }
        ]
    }


def verify(workspace_root: Path) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)
    base = v2.UnifiedRegistry()
    health = base.health()
    if health["core_count"] != 100 or health["legacy_extension_count"] != 24:
        raise AssertionError("inherited registry counts changed")

    core_receipts = [base.execute(spec.capability_id, {}) for spec in core.CAPABILITY_SPECS]
    for receipt, spec in zip(core_receipts, core.CAPABILITY_SPECS):
        _assert_receipt(receipt, spec.capability_id)
        if receipt["namespace"] != "core":
            raise AssertionError("core namespace drift")

    legacy_payload = _legacy_payload()
    legacy_receipts = [base.execute(spec.capability_id, legacy_payload) for spec in legacy.CAPABILITY_SPECS]
    for receipt, spec in zip(legacy_receipts, legacy.CAPABILITY_SPECS):
        _assert_receipt(receipt, spec.capability_id)
        if receipt["namespace"] != "legacy_chat_forensics":
            raise AssertionError("legacy namespace drift")

    meta_receipts = [
        base.execute("BCO-PRIME-META-MANIFEST", {}),
        base.execute("BCO-PRIME-META-STRATEGY-TOURNAMENT", _strategy_payload()),
    ]
    for receipt in meta_receipts:
        _assert_receipt(receipt, receipt["operation"])
        if receipt["namespace"] != "meta":
            raise AssertionError("meta namespace drift")

    blocked_engines: list[str] = []
    for operation in v2.ENGINE_OPERATIONS:
        try:
            base.execute(operation, {})
        except v2.EngineUnavailable as exc:
            if str(exc) != "ENGINE_NOT_CONFIGURED":
                raise
            blocked_engines.append(operation)
        else:
            raise AssertionError(f"unconfigured engine route escaped: {operation}")

    with tempfile.TemporaryDirectory(prefix="bco-v3-proof-", dir=workspace_root) as directory:
        run_root = Path(directory)
        registry = successor.SuccessorRegistry(run_root, base)
        v3_receipts: list[dict[str, Any]] = []

        def execute(operation: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
            receipt = registry.execute(operation, payload or {})
            _assert_receipt(receipt, operation)
            v3_receipts.append(receipt)
            return receipt

        execute("BCO-PRIME-V3-MANIFEST")
        execute("BCO-PRIME-V3-FLIGHT-MANIFEST")
        event = {
            "event_id": "event-1",
            "mission_id": "release-proof",
            "correlation_id": "release-proof",
            "kind": "EXHAUSTIVE_ROUTE_PROOF",
            "status": "COMPLETED",
            "failure_type": "NONE",
            "started_ns": 1_000_000,
            "ended_ns": 2_000_000,
            "payload": {"scope": "local"},
        }
        execute("BCO-PRIME-V3-FLIGHT-APPEND", {"recorder_root": "flight", "event": event})
        if execute("BCO-PRIME-V3-FLIGHT-VERIFY", {"recorder_root": "flight"})["output"]["valid"] is not True:
            raise AssertionError("flight verification failed")
        if execute("BCO-PRIME-V3-FLIGHT-REPLAY", {"recorder_root": "flight"})["output"]["drift"]:
            raise AssertionError("unexpected flight drift")
        execute("BCO-PRIME-V3-FLIGHT-CHECKPOINT", {"recorder_root": "flight"})
        execute("BCO-PRIME-V3-HARVEST-MANIFEST")

        sources = run_root / "sources"
        sources.mkdir()
        (sources / "capability.py").write_text(
            "# SPDX-License-Identifier: MIT\nimport hashlib\ndef verify_payload(value):\n    return hashlib.sha256(repr(value).encode()).hexdigest()\n",
            encoding="utf-8",
        )
        radar = execute(
            "BCO-PRIME-V3-HARVEST-RADAR",
            {
                "scan_root": "sources",
                "authorized_source_ids": ["source-1"],
                "source_id": "source-1",
                "tenant_id": "tenant-1",
                "matter_id": "matter-1",
            },
        )["output"]
        graph = execute("BCO-PRIME-V3-OPPORTUNITY-GRAPH", {"records": radar["records"]})["output"]
        candidate = execute(
            "BCO-PRIME-V3-COMPILE-CANDIDATE", {"graph": graph, "selected_ids": [graph["ranked_candidates"][0]]}
        )["output"]
        paired_cases = [
            {"baseline_quality": 0.5, "candidate_quality": 0.6, "passed": True}
            for _ in range(30)
        ]
        qualified = execute(
            "BCO-PRIME-V3-QUALIFY-SHADOW",
            {
                "candidate": candidate,
                "paired_cases": paired_cases,
                "rollback_available": True,
                "independent_verifier_pass": True,
            },
        )["output"]
        if qualified["shadowProven"] is not True or qualified["stablePromotionAuthorized"] is not False:
            raise AssertionError("shadow qualification boundary failed")
        execute("BCO-PRIME-V3-ADAPTIVE-MANIFEST")
        adaptive = execute(
            "BCO-PRIME-V3-ADAPTIVE-EVALUATE",
            {
                "candidate": {
                    "candidate_id": "adaptive-release-proof",
                    "operation": "flight_append",
                    "policy": "retain_current_policy",
                    "evidence_ids": ["event-1"],
                    "reversible": True,
                    "effect_class": "LOCAL_SHADOW",
                },
                "cases": paired_cases,
                "rollback_available": True,
                "independent_verifier_pass": True,
            },
        )["output"]
        if adaptive["shadowProven"] is not True or adaptive["stablePromotionAuthorized"] is not False:
            raise AssertionError("adaptive boundary failed")
        closure = execute("BCO-PRIME-V3-META-DEPENDENCY-CLOSURE")["output"]
        if closure["state"] != "BLOCKED_WITH_ROUTE" or closure["safeSubsetReady"] is not True:
            raise AssertionError("meta dependency truth boundary failed")
        if len(v3_receipts) != len(successor.SUCCESSOR_OPERATIONS):
            raise AssertionError("successor operation coverage incomplete")

    report: dict[str, Any] = {
        "schema": "BCO_PRIME_SUCCESSOR_RELEASE_VERIFICATION_V3",
        "state": "PASS",
        "canonical_core_routes": len(core_receipts),
        "legacy_routes": len(legacy_receipts),
        "v2_meta_routes": len(meta_receipts),
        "expected_blocked_engine_routes": len(blocked_engines),
        "successor_routes": len(successor.SUCCESSOR_OPERATIONS),
        "canonical_core_invariant_preserved": len(core_receipts) == 100,
        "fullMetaRuntimeState": "BLOCKED_WITH_ROUTE",
        "safeSubsetReady": True,
        "runtimeState": "ON_DEMAND_GOVERNED",
        "providerEffectAuthorized": False,
        "stablePromotionAuthorized": False,
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }
    report["receipt_sha256"] = v2.digest(report)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BCO-Prime successor v3 release verifier")
    parser.add_argument("--workspace-root", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(verify(Path(args.workspace_root)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
