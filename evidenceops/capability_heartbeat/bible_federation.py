from __future__ import annotations

import fnmatch
from datetime import datetime, timedelta, timezone
from typing import Any

from .engine import HeartbeatError, SAFE_ID, sha256_value

NODE_STATES = {
    "NODE_ACTIVE_VERIFIED",
    "NODE_STALE",
    "NODE_SYNC_PENDING",
    "NODE_CONFLICT",
    "NODE_QUARANTINED",
    "NODE_ARCHIVED",
}
PRIVACY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}


def parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise HeartbeatError("invalid Bible node timestamp") from exc
    if parsed.tzinfo is None:
        raise HeartbeatError("Bible node timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


class BibleFederation:
    """Builds and verifies privacy-safe Master Bible node heartbeats."""

    def __init__(self, contract: dict[str, Any]):
        self.contract = contract
        self._validate_contract()

    def _validate_contract(self) -> None:
        if self.contract.get("schema") != "EVIDENCEOPS-BIBLE-NODE-1":
            raise HeartbeatError("unsupported Bible node contract")
        for key in ("node_id", "parent_node_id", "contract_version"):
            if not SAFE_ID.fullmatch(str(self.contract.get(key, ""))):
                raise HeartbeatError(f"invalid Bible node {key}")
        if self.contract.get("privacy_tier") not in PRIVACY_RANK:
            raise HeartbeatError("invalid Bible node privacy tier")
        if not isinstance(self.contract.get("branch_version"), int) or self.contract["branch_version"] < 1:
            raise HeartbeatError("Bible node branch_version must be positive")
        if not isinstance(self.contract.get("ttl_seconds"), int) or self.contract["ttl_seconds"] < 60:
            raise HeartbeatError("Bible node ttl_seconds must be at least 60")
        max_hops = self.contract.get("max_hops")
        if not isinstance(max_hops, int) or not 1 <= max_hops <= 32:
            raise HeartbeatError("Bible node max_hops must be between 1 and 32")
        patterns = self.contract.get("authorized_child_patterns")
        if not isinstance(patterns, list) or any(not isinstance(item, str) or not item for item in patterns):
            raise HeartbeatError("authorized child patterns must be a list")

    def _workflow_refs(self, workflow_ids: list[str]) -> list[str]:
        if any(not isinstance(value, str) or not value for value in workflow_ids):
            raise HeartbeatError("active workflow identifiers must be non-empty strings")
        if PRIVACY_RANK[self.contract["privacy_tier"]] <= PRIVACY_RANK["P1"]:
            return sorted(set(workflow_ids))
        return sorted({f"sha256:{sha256_value(value)}" for value in workflow_ids})

    def make_heartbeat(
        self,
        capability_report_sha: str,
        *,
        emitted_at: str,
        active_workflow_ids: list[str] | None = None,
        path: list[str] | None = None,
        last_merge_receipt_ref: str | None = None,
    ) -> dict[str, Any]:
        if not SAFE_ID.fullmatch(capability_report_sha):
            raise HeartbeatError("invalid capability report reference")
        emitted = parse_time(emitted_at)
        route = list(path or [self.contract["parent_node_id"], self.contract["node_id"]])
        if route[-1] != self.contract["node_id"] or len(route) != len(set(route)):
            raise HeartbeatError("Bible node propagation path is invalid or cyclic")
        if len(route) - 1 > self.contract["max_hops"]:
            raise HeartbeatError("Bible node propagation exceeds max_hops")
        body = {
            "schema": "EVIDENCEOPS-BIBLE-NODE-HEARTBEAT-1",
            "node_id": self.contract["node_id"],
            "parent_node_id": self.contract["parent_node_id"],
            "contract_version": self.contract["contract_version"],
            "branch_version": self.contract["branch_version"],
            "privacy_tier": self.contract["privacy_tier"],
            "status": "NODE_ACTIVE_VERIFIED",
            "active_workflow_refs": self._workflow_refs(active_workflow_ids or self.contract.get("active_workflow_ids", [])),
            "capability_report_sha": capability_report_sha,
            "last_merge_receipt_ref": last_merge_receipt_ref,
            "emitted_at": emitted.isoformat(),
            "expires_at": (emitted + timedelta(seconds=self.contract["ttl_seconds"])).isoformat(),
            "propagation_path": route,
            "hop_count": len(route) - 1,
            "max_hops": self.contract["max_hops"],
            "details_included": False,
            "credentials_included": False,
        }
        return {**body, "heartbeat_sha256": sha256_value(body)}

    @staticmethod
    def verify_heartbeat(envelope: dict[str, Any]) -> None:
        if envelope.get("schema") != "EVIDENCEOPS-BIBLE-NODE-HEARTBEAT-1":
            raise HeartbeatError("unsupported Bible node heartbeat")
        body = {key: value for key, value in envelope.items() if key != "heartbeat_sha256"}
        if envelope.get("heartbeat_sha256") != sha256_value(body):
            raise HeartbeatError("Bible node heartbeat hash mismatch")
        if envelope.get("status") not in NODE_STATES:
            raise HeartbeatError("invalid Bible node status")
        path = envelope.get("propagation_path")
        if not isinstance(path, list) or len(path) != len(set(path)):
            raise HeartbeatError("Bible node propagation loop detected")
        if envelope.get("hop_count") != len(path) - 1 or envelope["hop_count"] > envelope.get("max_hops", -1):
            raise HeartbeatError("invalid Bible node hop count")
        if envelope.get("credentials_included") or envelope.get("details_included"):
            raise HeartbeatError("Bible node heartbeat contains prohibited detail")
        parse_time(envelope.get("emitted_at"))
        parse_time(envelope.get("expires_at"))

    def make_child_genesis(self, child_id: str, parent_heartbeat: dict[str, Any]) -> dict[str, Any]:
        self.verify_heartbeat(parent_heartbeat)
        if not SAFE_ID.fullmatch(child_id):
            raise HeartbeatError("invalid child node id")
        if not any(fnmatch.fnmatchcase(child_id, pattern) for pattern in self.contract["authorized_child_patterns"]):
            raise HeartbeatError("child node is outside the delegated namespace")
        parent_path = list(parent_heartbeat["propagation_path"])
        if child_id in parent_path:
            raise HeartbeatError("child propagation would create a loop")
        if parent_heartbeat["hop_count"] + 1 > self.contract["max_hops"]:
            raise HeartbeatError("child propagation exceeds max_hops")
        body = {
            "schema": "EVIDENCEOPS-BIBLE-CHILD-GENESIS-1",
            "node_id": child_id,
            "parent_node_id": self.contract["node_id"],
            "contract_version": self.contract["contract_version"],
            "minimum_branch_version": self.contract["branch_version"],
            "privacy_tier_ceiling": self.contract["privacy_tier"],
            "propagation_path": [*parent_path, child_id],
            "hop_count": parent_heartbeat["hop_count"] + 1,
            "max_hops": self.contract["max_hops"],
            "parent_heartbeat_sha256": parent_heartbeat["heartbeat_sha256"],
            "required_startup_sequence": [
                "VERIFY_GENESIS_HASH",
                "REGISTER_NODE",
                "SCAN_CURRENT_CAPABILITIES",
                "EMIT_NODE_ACTIVE_HEARTBEAT",
                "READ_BACK_REGISTRY_RECEIPT",
            ],
            "effectful_execution_inherited": False,
        }
        return {**body, "genesis_sha256": sha256_value(body)}

    @staticmethod
    def reconcile(
        registered_node_ids: set[str],
        envelopes: list[dict[str, Any]],
        *,
        observed_at: str,
    ) -> dict[str, Any]:
        observed = parse_time(observed_at)
        latest: dict[str, dict[str, Any]] = {}
        conflicts: set[str] = set()
        quarantined: list[str] = []
        rejected_replays: list[str] = []
        for envelope in envelopes:
            BibleFederation.verify_heartbeat(envelope)
            node_id = envelope["node_id"]
            if node_id not in registered_node_ids:
                quarantined.append(node_id)
                continue
            prior = latest.get(node_id)
            if prior is None:
                latest[node_id] = envelope
                continue
            prior_time = parse_time(prior["emitted_at"])
            current_time = parse_time(envelope["emitted_at"])
            if current_time == prior_time and envelope["heartbeat_sha256"] != prior["heartbeat_sha256"]:
                conflicts.add(node_id)
            elif current_time > prior_time and envelope["branch_version"] >= prior["branch_version"]:
                latest[node_id] = envelope
            elif current_time < prior_time or envelope["branch_version"] < prior["branch_version"]:
                rejected_replays.append(envelope["heartbeat_sha256"])

        nodes: list[dict[str, Any]] = []
        for node_id in sorted(registered_node_ids):
            envelope = latest.get(node_id)
            if node_id in conflicts:
                state = "NODE_CONFLICT"
            elif envelope is None:
                state = "NODE_SYNC_PENDING"
            elif parse_time(envelope["expires_at"]) < observed:
                state = "NODE_STALE"
            else:
                state = "NODE_ACTIVE_VERIFIED"
            nodes.append({
                "node_id": node_id,
                "state": state,
                "last_heartbeat_sha256": envelope.get("heartbeat_sha256") if envelope else None,
            })
        return {
            "schema": "EVIDENCEOPS-BIBLE-NODE-RECONCILIATION-1",
            "observed_at": observed.isoformat(),
            "nodes": nodes,
            "quarantined_unregistered_nodes": sorted(set(quarantined)),
            "rejected_replay_heartbeats": sorted(set(rejected_replays)),
            "active_node_count": sum(item["state"] == "NODE_ACTIVE_VERIFIED" for item in nodes),
            "truth_boundary": "Only registered nodes with a current, hash-valid heartbeat are known active.",
        }
