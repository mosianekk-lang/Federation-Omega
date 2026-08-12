from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .ledger import LedgerError
from .service import ServiceState


@dataclass(frozen=True)
class ResilienceReceipt:
    schema: str
    state: str
    workspace_sha256: str
    index_sha256: str | None
    accounting_state: str | None
    custody_state: str | None
    restart_stable: bool
    failures: tuple[str, ...]
    truth_boundary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def probe_workspace(workspace: str | Path, *, token_sha256: str) -> ResilienceReceipt:
    root = Path(workspace).resolve()
    failures: list[str] = []
    index_sha = None
    accounting_state = None
    custody_state = None
    restart_stable = False
    workspace_identity: dict[str, Any] = {"workspace": str(root)}
    try:
        first = ServiceState.load(root, token_sha256=token_sha256)
        health = first.health()
        ready = first.readiness()
        audit = first.audit()
        index_sha = health.get("index_sha256")
        accounting_state = ready.get("accounting_state")
        custody = first.ledger.verify_custody_chain()
        custody_state = custody.get("state")
        manifest = first.ledger.read_workspace_manifest()
        workspace_identity = {
            "workspace_id": manifest.get("workspace_id"),
            "matter": manifest.get("matter"),
            "case_wall": manifest.get("case_wall"),
            "index_sha256": index_sha,
            "counts": audit.get("counts"),
        }
        if not ready.get("ready"):
            failures.append("READINESS_FAILED")
        if accounting_state != "PASS":
            failures.append("UNIT_ACCOUNTING_FAILED")
        if custody_state != "PASS":
            failures.append("CUSTODY_CHAIN_FAILED")
        second = ServiceState.load(root, token_sha256=token_sha256)
        second_health = second.health()
        second_ready = second.readiness()
        restart_stable = (
            second_health.get("index_sha256") == index_sha
            and second_ready.get("accounting_state") == accounting_state
            and second.ledger.verify_custody_chain().get("state") == custody_state
        )
        if not restart_stable:
            failures.append("RESTART_STATE_DRIFT")
    except (LedgerError, OSError, ValueError, json.JSONDecodeError) as exc:
        failures.append(f"LOAD_OR_STATE_FAILURE:{type(exc).__name__}")
    return ResilienceReceipt(
        schema="EVIDENCEOPS-IPEP-PATCH-RESILIENCE-RECEIPT-V1",
        state="PASS" if not failures else "FAIL",
        workspace_sha256=_digest(workspace_identity),
        index_sha256=index_sha,
        accounting_state=accounting_state,
        custody_state=custody_state,
        restart_stable=restart_stable,
        failures=tuple(sorted(set(failures))),
        truth_boundary=(
            "This receipt proves deterministic workspace/readiness/custody/restart checks only. "
            "It does not prove provider deployment, uptime, transcript certification or disaster recovery outside the tested workspace."
        ),
    )
