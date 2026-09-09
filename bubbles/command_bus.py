from __future__ import annotations

"""Existing Bubbles Command Bus with one bounded READ-only F130 action."""

import argparse
import json
from pathlib import Path
from typing import Mapping

from . import command_bus_base as _base
from .f130_mission_runtime_adapter_v1 import F130CommandError, execute_f130_mission_runtime

COMMAND_SCHEMA = _base.COMMAND_SCHEMA
RECEIPT_SCHEMA = _base.RECEIPT_SCHEMA
ALLOWED_ACTORS = _base.ALLOWED_ACTORS
CommandBusError = _base.CommandBusError

# Preserve incumbent test/patch hooks while delegating all incumbent actions.
_edpf_now = _base._edpf_now
run_apps_script_deployment_probe = _base.run_apps_script_deployment_probe


def _sync_incumbent_hooks() -> None:
    _base._edpf_now = _edpf_now
    _base.run_apps_script_deployment_probe = run_apps_script_deployment_probe


def execute_command(command: Mapping[str, object], *, actor: str, event_name: str, source_ref: str) -> dict[str, object]:
    _sync_incumbent_hooks()
    try:
        request = _base._request_from_command(command)
    except Exception:
        return _base.execute_command(command, actor=actor, event_name=event_name, source_ref=source_ref)

    if request.adapter_id != "bubbles_command_bus" or request.action != "f130_mission_runtime":
        return _base.execute_command(command, actor=actor, event_name=event_name, source_ref=source_ref)

    # Let the incumbent command bus perform actor, canonical-hash, secret-field,
    # route-kind and READ-only authority validation first.  The incumbent ends
    # at its generic unbound-executor constraint for a newly introduced action.
    incumbent = _base.execute_command(command, actor=actor, event_name=event_name, source_ref=source_ref)
    route = incumbent.get("route_decision", {}) if isinstance(incumbent, dict) else {}
    if not (
        incumbent.get("state") == "CONSTRAINT"
        and route.get("state") == "READY"
        and incumbent.get("reason") == "Provider executor is not bound in command-bus v1."
    ):
        return incumbent

    execution = execute_f130_mission_runtime(request.payload)
    receipt = dict(incumbent)
    receipt.pop("reason", None)
    receipt["state"] = "SUCCESS"
    receipt["execution"] = execution
    receipt["truth_boundary"] = (
        "SUCCESS proves the existing Bubbles GitHub Actions command host executed the F130 mission-runtime court "
        "against a caller-supplied WHOLE_OWNER_MISSION snapshot with zero external effects. It does not prove "
        "the SINGLE PRIMARY Federation Autopilot consumed the receipt, native ChatGPT interception, or any provider effect."
    )
    return receipt


def build_receipt(raw: str, *, actor: str, event_name: str, source_ref: str) -> dict[str, object]:
    try:
        command = _base._load_command(raw)
        return execute_command(command, actor=actor, event_name=event_name, source_ref=source_ref)
    except (CommandBusError, F130CommandError, KeyError, TypeError, ValueError) as exc:
        return {
            "schema": RECEIPT_SCHEMA,
            "state": "FAILURE",
            "actor": actor,
            "event_name": event_name,
            "source_ref": source_ref,
            "reason": str(exc),
            "truth_boundary": "Command validation failed; no provider action executed.",
        }


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
