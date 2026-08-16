from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Mapping

from bubbles.control_plane import (
    ActionRequest,
    BubblesControlPlane,
    EffectClass,
    RouteKind,
)
from bubbles.forest_background import run_background_event
from evidenceops.build_system.chat_failure_resilience import evaluate_failure


COMMAND_SCHEMA = "BUBBLES-CONTROL-COMMAND-V1"
RECEIPT_SCHEMA = "BUBBLES-COMMAND-RECEIPT-V1"
ALLOWED_ACTORS = frozenset({"mosianekk-lang"})


class CommandBusError(ValueError):
    pass


def _load_command(raw: str) -> Mapping[str, object]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CommandBusError(f"Command is not valid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise CommandBusError("Command must be a JSON object")
    if data.get("schema") != COMMAND_SCHEMA:
        raise CommandBusError(f"Unsupported command schema: {data.get('schema')!r}")
    required = {"adapter_id", "action", "effect", "target_alias"}
    missing = sorted(required.difference(data))
    if missing:
        raise CommandBusError(f"Missing command fields: {', '.join(missing)}")
    payload = data.get("payload", {})
    if not isinstance(payload, dict):
        raise CommandBusError("payload must be a JSON object")
    return data


def _request_from_command(command: Mapping[str, object]) -> ActionRequest:
    try:
        effect = EffectClass(str(command["effect"]))
    except ValueError as exc:
        raise CommandBusError(f"Unsupported effect: {command.get('effect')!r}") from exc
    return ActionRequest(
        adapter_id=str(command["adapter_id"]),
        action=str(command["action"]),
        effect=effect,
        target_alias=str(command["target_alias"]),
        payload=dict(command.get("payload", {})),
    )


def _chat_failure_recovery(request: ActionRequest) -> dict[str, object]:
    event = request.payload.get("event")
    if not isinstance(event, dict):
        raise CommandBusError("recover_chat_failure requires payload.event as a JSON object")
    mission = request.payload.get("mission_packet")
    if mission is not None and not isinstance(mission, dict):
        raise CommandBusError("payload.mission_packet must be a JSON object when supplied")
    previous = request.payload.get("previous_checkpoint")
    if previous is not None and not isinstance(previous, dict):
        raise CommandBusError("payload.previous_checkpoint must be a JSON object when supplied")
    recovery = evaluate_failure(event, previous_checkpoint=previous, mission_packet=mission)
    return {"kind": "LOCAL_CHAT_FAILURE_RECOVERY", "recovery": asdict(recovery), "provider_effects": False}


def _forest_background_event(request: ActionRequest) -> dict[str, object]:
    event = request.payload.get("event")
    if not isinstance(event, dict):
        raise CommandBusError("forest_first_omega_event requires payload.event as a sanitized JSON object")
    return {
        "kind": "LOCAL_FOREST_FIRST_OMEGA_BACKGROUND_EVENT",
        "background_receipt": run_background_event(event),
        "provider_effects": False,
    }


def execute_command(command: Mapping[str, object], *, actor: str, event_name: str, source_ref: str) -> dict[str, object]:
    if actor not in ALLOWED_ACTORS:
        return {"schema": RECEIPT_SCHEMA, "state": "CONSTRAINT", "actor": actor, "event_name": event_name,
                "source_ref": source_ref, "reason": "Actor is not allowed by the Bubbles command-bus contract.",
                "truth_boundary": "No provider action executed."}

    request = _request_from_command(command)
    control = BubblesControlPlane()
    envelope = control.command_envelope(request)
    supplied_hash = command.get("command_sha256")
    if supplied_hash is not None and supplied_hash != envelope["command_sha256"]:
        return {"schema": RECEIPT_SCHEMA, "state": "CONSTRAINT", "actor": actor, "event_name": event_name,
                "source_ref": source_ref, "command_sha256": envelope["command_sha256"],
                "reason": "Supplied command hash does not match canonical command payload.",
                "truth_boundary": "No provider action executed."}

    spec = control.adapter(request.adapter_id)
    if spec.route_kind is not RouteKind.GITHUB_COMMAND_BUS:
        return {
            "schema": RECEIPT_SCHEMA, "state": "CONSTRAINT", "actor": actor, "event_name": event_name,
            "source_ref": source_ref, "command_sha256": envelope["command_sha256"],
            "request": {"adapter_id": request.adapter_id, "action": request.action, "effect": request.effect.value,
                        "target_alias": request.target_alias},
            "route_decision": {"state": "CONSTRAINT", "route_kind": spec.route_kind.value,
                               "adapter_id": request.adapter_id, "action": request.action, "missing_proofs": [],
                               "reason": "Route family rejected before proof evaluation."},
            "reason": "Command bus only executes routes classified GITHUB_COMMAND_BUS.",
            "truth_boundary": "No provider action executed.",
        }

    decision = control.decide(request)
    decision_record = {**asdict(decision), "route_kind": decision.route_kind.value if decision.route_kind else None}
    base_receipt: dict[str, object] = {
        "schema": RECEIPT_SCHEMA, "actor": actor, "event_name": event_name, "source_ref": source_ref,
        "command_sha256": envelope["command_sha256"],
        "request": {"adapter_id": request.adapter_id, "action": request.action, "effect": request.effect.value,
                    "target_alias": request.target_alias},
        "route_decision": decision_record,
    }
    if decision.state != "READY":
        return {**base_receipt, "state": "CONSTRAINT", "reason": decision.reason,
                "missing_proofs": list(decision.missing_proofs),
                "truth_boundary": "Route validation failed closed; no provider action executed."}

    if request.adapter_id == "bubbles_command_bus" and request.action == "canary":
        return {**base_receipt, "state": "SUCCESS",
                "execution": {"kind": "LOCAL_COMMAND_BUS_CANARY", "target_alias": request.target_alias,
                              "echo": request.payload.get("message", "BUBBLES_COMMAND_BUS_CANARY")},
                "truth_boundary": "SUCCESS proves ChatGPT/GitHub command ingress, route validation and runner execution only. It does not prove Google Cloud, Apps Script, AI Studio or any external provider mutation."}

    if request.adapter_id == "bubbles_command_bus" and request.action == "recover_chat_failure":
        return {**base_receipt, "state": "SUCCESS", "execution": _chat_failure_recovery(request),
                "truth_boundary": "SUCCESS proves that the Bubbles command bus invoked CFRE and generated a recovery receipt. It does not prove repair of the ChatGPT client, browser, network or OpenAI service, and it performs no external provider mutation."}

    if request.adapter_id == "bubbles_command_bus" and request.action == "forest_first_omega_event":
        return {**base_receipt, "state": "SUCCESS", "execution": _forest_background_event(request),
                "truth_boundary": "SUCCESS proves the admitted Bubbles runner processed a sanitized Forest-First Omega event and emitted a cost-governed wake decision. It does not expose private provider content, establish legal facts, or perform any external provider mutation."}

    return {**base_receipt, "state": "CONSTRAINT", "reason": "Provider executor is not bound in command-bus v1.",
            "truth_boundary": "Route readiness alone is not provider authority. External execution remains blocked until a provider-specific executor supplies fresh identity, target, scope, execution and readback proof."}


def build_receipt(raw: str, *, actor: str, event_name: str, source_ref: str) -> dict[str, object]:
    try:
        command = _load_command(raw)
        return execute_command(command, actor=actor, event_name=event_name, source_ref=source_ref)
    except (CommandBusError, KeyError, ValueError) as exc:
        return {"schema": RECEIPT_SCHEMA, "state": "FAILURE", "actor": actor, "event_name": event_name,
                "source_ref": source_ref, "reason": str(exc),
                "truth_boundary": "Command validation failed; no provider action executed."}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one Bubbles command-bus envelope and emit a proof receipt.")
    parser.add_argument("--command-file", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    raw = Path(args.command_file).read_text(encoding="utf-8")
    receipt = build_receipt(raw, actor=args.actor, event_name=args.event_name, source_ref=args.source_ref)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["state"] == "SUCCESS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
