#!/usr/bin/env python3
"""Prevent checkpoints, reports, or 24-hour boundaries from closing open builds."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

TERMINAL_STATES = {"PROVEN", "INAPPLICABLE"}
REQUIRED_OPERATIONAL_LAYERS = (
    "design",
    "implementation",
    "testing",
    "configuration",
    "identityAuthentication",
    "authorization",
    "integration",
    "deployment",
    "liveReadback",
    "recoveryRollback",
    "monitoring",
)


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _state(value: Any) -> str:
    return str(value or "UNKNOWN").strip().upper()


def evaluate(packet: dict[str, Any]) -> dict[str, Any]:
    mission = packet.get("mission") or {}
    build = packet.get("systemBuild") or {}
    cycle = packet.get("cycle") or {}
    execution = packet.get("execution") or {}
    proof = packet.get("proof") or {}

    criteria = _items(mission.get("terminalCriteria"))
    critical = [item for item in criteria if isinstance(item, dict) and item.get("critical") is True]
    unresolved_criteria = sorted(
        str(item.get("id") or "UNNAMED")
        for item in critical
        if _state(item.get("state")) not in TERMINAL_STATES
    )

    layers = build.get("operationalLayers") or {}
    unresolved_layers: list[str] = []
    missing_layers: list[str] = []
    for name in REQUIRED_OPERATIONAL_LAYERS:
        layer = layers.get(name)
        if not isinstance(layer, dict):
            missing_layers.append(name)
            unresolved_layers.append(name)
        elif layer.get("applicable") is False:
            if not str(layer.get("inapplicableReason") or "").strip():
                unresolved_layers.append(name)
        elif layer.get("applicable") is not True or _state(layer.get("state")) not in TERMINAL_STATES:
            unresolved_layers.append(name)

    expected_fruit = {str(item) for item in _items(mission.get("terminalFruit")) if str(item)}
    observed_fruit = {str(item) for item in _items(proof.get("observedTerminalFruit")) if str(item)}
    missing_fruit = sorted(expected_fruit - observed_fruit)

    duration = cycle.get("durationHours")
    elapsed = cycle.get("elapsedHours")
    valid_timebox = (
        isinstance(duration, (int, float))
        and not isinstance(duration, bool)
        and duration == 24
        and isinstance(elapsed, (int, float))
        and not isinstance(elapsed, bool)
        and elapsed >= 0
    )
    cycle_expired = bool(valid_timebox and elapsed >= duration)
    manual_tasks = _items(execution.get("manualUserTasks"))
    zero_manual_required = execution.get("manualUserTasksAllowed") is False

    gates = {
        "OBJECTIVE_DEFINED": bool(str(mission.get("objective") or "").strip()),
        "CRITICAL_TERMINAL_CRITERIA_DEFINED": bool(critical),
        "ALL_CRITICAL_CRITERIA_TERMINAL": bool(critical) and not unresolved_criteria,
        "ALL_OPERATIONAL_LAYERS_CLASSIFIED": not missing_layers,
        "ALL_APPLICABLE_OPERATIONAL_LAYERS_TERMINAL": not unresolved_layers,
        "TERMINAL_FRUIT_DEFINED": bool(expected_fruit),
        "ALL_TERMINAL_FRUIT_OBSERVED": bool(expected_fruit) and not missing_fruit,
        "INDEPENDENT_LIVE_READBACK": proof.get("independentLiveReadback") is True,
        "VALID_24_HOUR_CYCLE": valid_timebox,
        "ZERO_PROHIBITED_MANUAL_TASKS": not (zero_manual_required and manual_tasks),
    }
    missing_gates = [name for name, passed in gates.items() if not passed]
    mission_complete = not missing_gates

    signals: list[str] = []
    if cycle.get("artifactComplete") is True and not mission_complete:
        signals.append("ARTIFACT_COMPLETION_SUBSTITUTED_FOR_MISSION_COMPLETION")
    if cycle.get("completionRequested") is True and not mission_complete:
        signals.append("COMPLETION_REQUESTED_WITH_OPEN_TERMINAL_GATES")
    if cycle.get("assistantStopping") is True and not mission_complete:
        signals.append("ASSISTANT_STOPPING_WITH_OUTCOME_ERROR")
    if cycle.get("reportingOpenWork") is True and not mission_complete:
        signals.append("OPEN_WORK_REPORTED_INSTEAD_OF_EXECUTED")
    if cycle.get("movingToUnrelatedWork") is True and not mission_complete:
        signals.append("UNRELATED_WORK_PROPOSED_BEFORE_TERMINAL_STATE")
    if cycle_expired and not mission_complete:
        signals.append("TIMEBOX_EXPIRY_TREATED_AS_POTENTIAL_MISSION_EXIT")
    if zero_manual_required and manual_tasks:
        signals.append("USER_BURDEN_TRANSFER_ATTEMPT")

    route_available = execution.get("authorizedRouteAvailable") is True
    next_action = str(execution.get("nextAutomatedAction") or "").strip()
    route_exhausted = execution.get("routeExhaustionProven") is True

    if mission_complete:
        decision, must_continue, cycle_action, canonical_status = (
            "MISSION_COMPLETE", False, "STOP", "PROVEN_COMPLETE"
        )
    elif signals:
        decision = "BLOCK_PREMATURE_COMPLETION"
        must_continue = route_available or not route_exhausted
        cycle_action = (
            "ROUTE_DISCOVERY"
            if not route_available and not route_exhausted
            else "OPEN_NEXT_24H_CYCLE" if cycle_expired else "CONTINUE_CURRENT_24H_CYCLE"
        )
        canonical_status = "PARTIAL_PROVEN"
    elif route_available:
        decision = "ROLLOVER_CONTINUE" if cycle_expired else "CONTINUE_AUTOMATICALLY"
        must_continue = True
        cycle_action = "OPEN_NEXT_24H_CYCLE" if cycle_expired else "CONTINUE_CURRENT_24H_CYCLE"
        canonical_status = "PARTIAL_PROVEN"
    elif not route_exhausted:
        decision, must_continue, cycle_action, canonical_status = (
            "DISCOVER_NEXT_ROUTE", True, "ROUTE_DISCOVERY", "BLOCKED_WITH_ROUTE_SEARCH_REQUIRED"
        )
    else:
        decision, must_continue, cycle_action, canonical_status = (
            "BLOCKED_ROUTE_EXHAUSTED", False, "PRESERVE_AND_WAIT_FOR_MACHINE_AUTHORITY",
            "BLOCKED_WITH_ROUTE_EXHAUSTION_PROOF",
        )

    if must_continue and not next_action:
        decision, cycle_action = "DISCOVER_NEXT_ROUTE", "ROUTE_DISCOVERY"

    return {
        "schema": "EVIDENCEOPS-OBJECTIVE-COMPLETION-GUARD-1",
        "decision": decision,
        "canonicalStatus": canonical_status,
        "completionClaimPermitted": mission_complete,
        "finalResponsePermitted": mission_complete or decision == "BLOCKED_ROUTE_EXHAUSTED",
        "missionComplete": mission_complete,
        "cycleComplete": cycle_expired or mission_complete,
        "mustContinue": must_continue,
        "cycleAction": cycle_action,
        "nextAutomatedAction": next_action or None,
        "unresolvedCriticalCriteria": unresolved_criteria,
        "unresolvedOperationalLayers": sorted(set(unresolved_layers)),
        "missingOperationalLayers": missing_layers,
        "missingTerminalFruit": missing_fruit,
        "missingGates": missing_gates,
        "prematureStoppingSignals": signals,
        "manualUserTasks": [],
        "ownerActionRequired": False,
        "internalRecoveryRequired": not mission_complete and decision != "BLOCKED_ROUTE_EXHAUSTED",
        "userVisibleFailureReportPermitted": decision == "BLOCKED_ROUTE_EXHAUSTED",
        "authorityGranted": False,
        "rule": "A 24-hour cycle may roll over; it may not redefine or terminate the owner's mission.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", nargs="?", help="Mission-state JSON; stdin when omitted")
    parser.add_argument("--output", help="Write the decision receipt to this path")
    parser.add_argument("--require-complete", action="store_true", help="Fail unless closure is proven")
    args = parser.parse_args(argv)
    if args.packet:
        with Path(args.packet).open(encoding="utf-8") as source:
            packet = json.load(source)
    else:
        packet = json.load(sys.stdin)
    result = evaluate(packet)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if args.require_complete and not result["missionComplete"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
