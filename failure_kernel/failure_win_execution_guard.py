#!/usr/bin/env python3
"""Fail-closed execution helpers selected by the Failure-to-Operational-Win Kernel."""

import json
import subprocess
import sys
import time
from pathlib import Path


FORMATION_GATE = Path(
    "/root/.codex/skills/remote-skills/govern-with-formation-engine/scripts/formation_gate.py"
)


class ExecutionBlocked(RuntimeError):
    """Raised before an executor runs when a governance or budget gate fails."""


def consume_then_execute(
    *,
    packet_path,
    permit_token,
    permit_db,
    executor,
    runner=subprocess.run,
    gate_path=FORMATION_GATE,
):
    """Consume one Formation permit, then invoke ``executor`` exactly once.

    The token is bound with ``--consume-permit=<token>`` so tokens beginning with
    a hyphen cannot be reinterpreted by argparse as new command-line options.
    """
    command = [
        sys.executable,
        str(gate_path),
        str(packet_path),
        f"--consume-permit={permit_token}",
        "--permit-db",
        str(permit_db),
    ]
    result = runner(command, capture_output=True, text=True, check=False)
    try:
        receipt = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise ExecutionBlocked("permit receipt was not valid JSON") from exc
    if (
        result.returncode != 0
        or receipt.get("decision") != "CONSUMED"
        or receipt.get("authorized") is not True
    ):
        reason = ",".join(receipt.get("reasons") or []) or "permit_consume_failed"
        raise ExecutionBlocked(reason)
    return executor()


def remaining_budget_seconds(*, started_at, deadline_seconds, now=None):
    current = time.time() if now is None else float(now)
    return float(deadline_seconds) - (current - float(started_at))


def require_stage_budget(
    *,
    started_at,
    deadline_seconds,
    proof_reserve_seconds,
    stage_estimates_seconds,
    now=None,
):
    """Admit a route only while all remaining stages and proof reserve still fit."""
    required = float(proof_reserve_seconds) + sum(
        float(seconds) for seconds in stage_estimates_seconds
    )
    remaining = remaining_budget_seconds(
        started_at=started_at,
        deadline_seconds=deadline_seconds,
        now=now,
    )
    if remaining < required:
        raise ExecutionBlocked(
            f"remaining_budget_insufficient:remaining={remaining:.3f},required={required:.3f}"
        )
    return {"remainingSeconds": remaining, "requiredSeconds": required}
