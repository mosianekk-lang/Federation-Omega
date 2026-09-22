from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import proof_rank
from .store import FabricStore
from .util import digest_json, parse_utc, reject_sensitive, require_nonempty, utc_now
from .util import require_int


_ACTION_PRIORITY = {
    "REGISTER_NODE": 100,
    "REFRESH_HEARTBEAT": 90,
    "RUN_SEMANTIC_CANARY": 80,
    "VERIFY_RECOVERY": 70,
}


class Reconciler:
    def __init__(self, store: FabricStore):
        self.store = store

    def plan(self, desired: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
        if desired.get("schema") != "CFBE-ACF-DESIRED-STATE-V1":
            raise ValueError("unsupported desired-state schema")
        reject_sensitive(desired)
        desired_state_id = str(require_nonempty(desired.get("id"), "desired.id"))
        mission_id = str(require_nonempty(desired.get("mission_id"), "desired.mission_id"))
        mission_version = require_int(
            desired.get("mission_version"), "desired.mission_version", minimum=1
        )
        if not desired.get("nodes") and not desired.get("capabilities"):
            raise ValueError("desired state must declare nodes or capabilities")
        node_ids = [str(require_nonempty(node.get("id"), "desired.node.id")) for node in desired.get("nodes", [])]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("desired node identifiers must be unique")
        generation_hash = digest_json(desired)
        now = now or datetime.now(timezone.utc)
        actual = self.store.snapshot()
        assets = {row["id"]: row for row in actual["assets"]}
        heartbeats = {row["node_id"]: row for row in actual["heartbeats"]}
        providers = {row["id"]: row for row in actual["providers"]}
        actions, blockers = [], []
        for node in desired.get("nodes", []):
            node_id = node["id"]
            if node_id not in assets:
                actions.append(self._action("REGISTER_NODE", node_id, effectful=False))
                blockers.append(self._blocker(desired_state_id, node_id, "NODE_MISSING"))
                continue
            heartbeat = heartbeats.get(node_id)
            if not heartbeat:
                actions.append(self._action("REFRESH_HEARTBEAT", node_id, effectful=False))
                blockers.append(self._blocker(desired_state_id, node_id, "HEARTBEAT_MISSING"))
                continue
            age = (now - parse_utc(heartbeat["observed_at"])).total_seconds()
            if age < -300:
                actions.append(self._action("REFRESH_HEARTBEAT", node_id, effectful=False))
                blockers.append(
                    self._blocker(
                        desired_state_id, node_id, "HEARTBEAT_FROM_FUTURE", {"skew_seconds": -age}
                    )
                )
                continue
            age = max(0.0, age)
            if age > int(node.get("maximum_heartbeat_age_seconds", 3600)):
                actions.append(self._action("REFRESH_HEARTBEAT", node_id, effectful=False))
                blockers.append(self._blocker(desired_state_id, node_id, "HEARTBEAT_STALE", {"age_seconds": age}))
        for capability in desired.get("capabilities", []):
            proof_action_id = str(
                require_nonempty(capability.get("proof_action_id"), "capability.proof_action_id")
            )
            verified_stages = self.store.verified_provider_stages(
                mission_id=mission_id,
                mission_version=mission_version,
                action_id=proof_action_id,
            )
            provider = providers.get(capability["provider_id"])
            if not provider:
                blockers.append(self._blocker(desired_state_id, capability["provider_id"], "PROVIDER_MISSING"))
                continue
            current = verified_stages.get(capability["provider_id"], "UNKNOWN")
            required = capability.get("minimum_proof_stage", "SEMANTICALLY_VERIFIED")
            if proof_rank(current) < proof_rank(required):
                kind = "VERIFY_RECOVERY" if required == "RECOVERY_VERIFIED" else "RUN_SEMANTIC_CANARY"
                actions.append(self._action(kind, capability["provider_id"], effectful=False))
                blockers.append(
                    self._blocker(
                        desired_state_id,
                        capability["provider_id"],
                        "PROOF_GAP",
                        {"current": current, "required": required},
                    )
                )
        actions.sort(key=lambda row: (-_ACTION_PRIORITY[row["kind"]], row["subject_id"]))
        blockers.sort(key=lambda row: row["id"])
        active_blockers = self.store.reconcile_blockers(
            desired_state_id=desired_state_id,
            generation_hash=generation_hash,
            blockers=blockers,
        )
        completion_allowed = not actions and not active_blockers
        return {
            "schema": "CFBE-ACF-RECONCILIATION-PLAN-V1",
            "desired_state_id": desired_state_id,
            "generation_hash": generation_hash,
            "generated_at": utc_now(),
            "state": "IN_SYNC" if completion_allowed else "DRIFT_DETECTED",
            "immediate_actions": actions[:3],
            "all_actions": actions,
            "blockers": active_blockers,
            "effectful_paths_allowed": min(1, sum(1 for action in actions if action["effectful"])),
            "completion_claim_allowed": completion_allowed,
        }

    @staticmethod
    def _action(kind: str, subject_id: str, *, effectful: bool) -> dict[str, Any]:
        seed = {"kind": kind, "subject_id": subject_id}
        return {
            "id": "ACT-" + digest_json(seed)[:20],
            "kind": kind,
            "subject_id": subject_id,
            "effectful": effectful,
            "dry_run_required": True,
            "semantic_readback_required": True,
        }

    @staticmethod
    def _blocker(
        desired_state_id: str,
        subject_id: str,
        reason: str,
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        seed = {"desired_state_id": desired_state_id, "subject_id": subject_id, "reason": reason}
        return {
            "id": "BLK-" + digest_json(seed)[:20],
            "subject_id": subject_id,
            "reason": reason,
            "desired_state_id": desired_state_id,
            "detail": detail or {},
            "state": "OPEN",
            "observed_at": utc_now(),
        }
