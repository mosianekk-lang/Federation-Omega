from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .sandbox_fleet import ReceiptLedger


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True)
class Revision:
    revision_id: str
    manifest_digest: str
    manifest: dict[str, Any]


class FileRevisionProvider:
    """Artifact-backed GitHub Actions reference provider.

    It proves immutable revisions, allocation changes, readback, persistence and
    rollback. It is not represented as a Cloud Run or public traffic endpoint.
    """

    def __init__(self, workspace: str | Path):
        self.workspace = Path(workspace)
        self.revisions = self.workspace / "revisions"
        self.state_path = self.workspace / "delivery_state.json"
        self.revisions.mkdir(parents=True, exist_ok=True)
        self.ledger = ReceiptLedger(self.workspace / "delivery_ledger.jsonl")
        if not self.state_path.exists():
            self._write_state({"active_revision": None, "traffic": {}, "generation": 0})

    def _write_state(self, state: Mapping[str, Any]) -> None:
        temp = self.state_path.with_suffix(".tmp")
        temp.write_text(json.dumps(dict(state), sort_keys=True, indent=2), encoding="utf-8")
        os.replace(temp, self.state_path)

    def state(self) -> dict[str, Any]:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def snapshot(self) -> dict[str, Any]:
        return self.state()

    def deploy(self, manifest: Mapping[str, Any]) -> Revision:
        payload = dict(manifest)
        digest = _digest(payload)
        revision_id = f"rev-{digest[:16]}"
        path = self.revisions / revision_id / "manifest.json"
        if path.exists():
            readback = json.loads(path.read_text(encoding="utf-8"))
            if _canonical(readback) != _canonical(payload):
                raise ValueError("immutable revision conflict")
        else:
            path.parent.mkdir(parents=True, exist_ok=False)
            path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
        revision = Revision(revision_id, digest, payload)
        if self.readback(revision_id).manifest_digest != digest:
            raise IOError("revision readback mismatch")
        return revision

    def readback(self, revision_id: str) -> Revision:
        path = self.revisions / revision_id / "manifest.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        return Revision(revision_id, _digest(payload), payload)

    def set_traffic(self, allocation: Mapping[str, int]) -> dict[str, Any]:
        normalized = {key: int(value) for key, value in allocation.items() if int(value) > 0}
        if sum(normalized.values()) != 100:
            raise ValueError("traffic allocation must total 100")
        for revision_id in normalized:
            if not (self.revisions / revision_id / "manifest.json").is_file():
                raise KeyError(revision_id)
        current = self.state()
        active = next((key for key, value in normalized.items() if value == 100), current["active_revision"])
        updated = {
            "active_revision": active,
            "traffic": dict(sorted(normalized.items())),
            "generation": int(current["generation"]) + 1,
        }
        self._write_state(updated)
        if self.state() != updated:
            raise IOError("traffic state readback mismatch")
        return updated

    def restore(self, snapshot: Mapping[str, Any]) -> bool:
        self._write_state(dict(snapshot))
        return self.state() == dict(snapshot)

    def persistence_probe(self) -> bool:
        reopened = FileRevisionProvider(self.workspace)
        return reopened.state() == self.state() and reopened.ledger.verify()["valid"]


class ProgressiveDeliveryController:
    def __init__(self, provider: FileRevisionProvider):
        self.provider = provider

    def release(
        self,
        manifest: Mapping[str, Any],
        health_probe: Callable[[Revision, int], bool],
        steps: Sequence[int] = (10, 25, 50, 100),
    ) -> dict[str, Any]:
        if not steps or tuple(sorted(set(steps))) != tuple(steps) or steps[-1] != 100:
            raise ValueError("steps must be unique ascending percentages ending at 100")
        if any(step <= 0 or step > 100 for step in steps):
            raise ValueError("invalid rollout percentage")

        before = self.provider.snapshot()
        previous = before.get("active_revision")
        candidate = self.provider.deploy(manifest)
        transitions: list[dict[str, Any]] = []
        healthy = True

        for percentage in steps:
            allocation = {candidate.revision_id: percentage}
            if previous and previous != candidate.revision_id and percentage < 100:
                allocation[previous] = 100 - percentage
            elif percentage < 100 and not previous:
                # No live predecessor exists; exercise staged validation without
                # pretending that unassigned traffic is real provider traffic.
                allocation = {candidate.revision_id: 100}
            state = self.provider.set_traffic(allocation)
            passed = bool(health_probe(candidate, percentage))
            transitions.append({"percentage": percentage, "state": state, "health": passed})
            if not passed:
                healthy = False
                break

        if not healthy:
            rollback_verified = self.provider.restore(before)
            receipt = {
                "status": "ROLLED_BACK",
                "candidate": candidate.revision_id,
                "transitions": transitions,
                "health_verified": False,
                "rollback_verified": rollback_verified,
                "final_state": self.provider.state(),
            }
            receipt["receipt_hash"] = _digest(receipt)
            receipt["ledger_entry"] = self.provider.ledger.append(receipt)["entry_hash"]
            receipt["persistence_verified"] = self.provider.persistence_probe()
            return receipt

        promoted = self.provider.snapshot()
        rollback_verified = self.provider.restore(before)
        restoration_verified = self.provider.restore(promoted)
        final_state = self.provider.state()
        readback = self.provider.readback(candidate.revision_id)
        receipt = {
            "status": "PROMOTED",
            "candidate": candidate.revision_id,
            "manifest_digest": candidate.manifest_digest,
            "transitions": transitions,
            "execution_verified": True,
            "readback_verified": readback.manifest_digest == candidate.manifest_digest,
            "health_verified": all(item["health"] for item in transitions),
            "rollback_verified": rollback_verified,
            "restoration_verified": restoration_verified,
            "final_state": final_state,
        }
        receipt["receipt_hash"] = _digest(receipt)
        receipt["ledger_entry"] = self.provider.ledger.append(receipt)["entry_hash"]
        receipt["persistence_verified"] = self.provider.persistence_probe()
        return receipt
