from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


@dataclass(frozen=True)
class Mission:
    mission_id: str
    objective: str
    success_definition: tuple[str, ...]
    constraints: tuple[str, ...] = ()
    version: int = 1


@dataclass(frozen=True)
class Workstream:
    workstream_id: str
    mission_id: str
    objective: str
    dependencies: tuple[str, ...] = ()
    priority: int = 50
    reversible: bool = True


@dataclass(frozen=True)
class ProviderCapability:
    provider: str
    operation: str
    read: bool
    write: bool
    execute: bool
    readback: bool
    rollback: bool
    authority_state: str
    verified_at: str


@dataclass(frozen=True)
class CompletionContract:
    required_receipts: tuple[str, ...]
    max_receipt_age_seconds: int = 86400


@dataclass
class RuntimeState:
    missions: dict[str, dict[str, Any]] = field(default_factory=dict)
    workstreams: dict[str, dict[str, Any]] = field(default_factory=dict)
    providers: dict[str, dict[str, Any]] = field(default_factory=dict)
    receipts: dict[str, dict[str, Any]] = field(default_factory=dict)
    checkpoints: dict[str, dict[str, Any]] = field(default_factory=dict)
    lessons: list[dict[str, Any]] = field(default_factory=list)
    policies: list[dict[str, Any]] = field(default_factory=list)
    reliability: dict[str, dict[str, Any]] = field(default_factory=dict)


class SolRuntime:
    """Durable reference runtime for SOL 6.1, Omega-Max and EvidenceOps.

    State is derived from append-only events. Provider actions are admitted only
    through explicit capability and completion contracts. This module is a
    provider-neutral kernel; external workers must return provider-native receipts.
    """

    FAILURE_REPAIRS = {
        "TRANSIENT": "RETRY_WITH_EXPONENTIAL_BACKOFF_AND_JITTER",
        "AUTHORITY": "TRY_AUTHORISED_ALTERNATE_OR_MARK_OWNER_CONSENT_REQUIRED",
        "CONTRACT": "RECOMPILE_REQUEST_AND_VALIDATE_SCHEMA",
        "LOGIC": "PATCH_RUN_TESTS_AND_REPLAY_FROM_CHECKPOINT",
        "STATE": "RECONCILE_CANONICAL_STATE_AND_RESTORE_CHECKPOINT",
        "PROVIDER": "SELECT_ALTERNATE_VERIFIED_ADAPTER_OR_MARK_PROVIDER_BLOCKED",
        "MARKET": "PRESERVE_READINESS_AND_AWAIT_EXTERNAL_EVIDENCE",
        "OWNER_RESERVED": "HOLD_ONLY_CONSEQUENTIAL_ACTION_AND_CONTINUE_INDEPENDENT_STREAMS",
    }

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.events = self.root / "events.jsonl"
        self.snapshot = self.root / "state.json"
        self.state = RuntimeState()
        self._replay()

    def append_event(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._events()
        event = {
            "event_id": f"evt-{len(rows)+1:08d}",
            "event_type": event_type,
            "payload": payload,
            "recorded_at": utc_now(),
            "previous_hash": rows[-1]["event_hash"] if rows else "GENESIS",
        }
        event["event_hash"] = digest(event)
        with self.events.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._apply(event)
        self._persist()
        return event

    def register_mission(self, mission: Mission) -> dict[str, Any]:
        existing = self.state.missions.get(mission.mission_id)
        body = asdict(mission)
        if existing and existing != body:
            if mission.version <= int(existing["version"]):
                raise ValueError("mission replacement requires a higher version")
        self.append_event("MISSION_REGISTERED", body)
        return body

    def register_workstream(self, workstream: Workstream) -> dict[str, Any]:
        if workstream.mission_id not in self.state.missions:
            raise KeyError("mission not registered")
        body = asdict(workstream) | {"status": "QUEUED", "attempts": 0}
        self.append_event("WORKSTREAM_REGISTERED", body)
        return body

    def register_provider(self, capability: ProviderCapability) -> dict[str, Any]:
        body = asdict(capability)
        self.append_event("PROVIDER_CAPABILITY_VERIFIED", body)
        return body

    def compile_context(self, workstream_id: str, facts: list[dict[str, Any]], max_items: int = 12) -> dict[str, Any]:
        ws = self.state.workstreams[workstream_id]
        mission = self.state.missions[ws["mission_id"]]
        relevant = [f for f in facts if workstream_id in f.get("workstreams", []) or ws["mission_id"] in f.get("missions", [])]
        relevant.sort(key=lambda f: (f.get("verified", False), f.get("priority", 0), f.get("observed_at", "")), reverse=True)
        return {
            "mission": mission,
            "workstream": ws,
            "verified_facts": [f for f in relevant[:max_items] if f.get("verified")],
            "unknowns": [f for f in relevant[:max_items] if not f.get("verified")],
            "proof_requirements": ws.get("proof_requirements", []),
        }

    @staticmethod
    def reasoning_budget(*, complexity: float, consequence: float, uncertainty: float, dependency_depth: float, contradiction_risk: float) -> dict[str, Any]:
        score = complexity * consequence * uncertainty * max(1.0, dependency_depth) * contradiction_risk
        lane = "FAST" if score < 2 else "DEEP" if score < 8 else "MULTI_PASS" if score < 20 else "ESCALATED"
        return {"score": round(score, 4), "lane": lane}

    def ready_workstreams(self) -> list[dict[str, Any]]:
        done = {key for key, value in self.state.workstreams.items() if value.get("status") == "VERIFIED"}
        ready = []
        for ws in self.state.workstreams.values():
            if ws.get("status") in {"QUEUED", "RETRY_READY"} and set(ws.get("dependencies", ())) <= done:
                ready.append(ws)
        return sorted(ready, key=lambda w: (-int(w.get("priority", 50)), w["workstream_id"]))

    def admit_action(self, provider: str, operation: str, consequential: bool = False) -> dict[str, Any]:
        key = f"{provider}:{operation}"
        cap = self.state.providers.get(key)
        if not cap:
            return {"admitted": False, "state": "PROVIDER_BLOCKED", "reason": "capability not verified"}
        if cap["authority_state"] != "VERIFIED":
            return {"admitted": False, "state": cap["authority_state"], "reason": "authority not verified"}
        if consequential and not cap["rollback"]:
            return {"admitted": False, "state": "OWNER_APPROVAL_REQUIRED", "reason": "consequential action lacks rollback"}
        return {"admitted": True, "state": "ADMITTED", "capability": cap}

    def record_receipt(self, workstream_id: str, receipt_type: str, provider: str, body: dict[str, Any]) -> dict[str, Any]:
        receipt = {
            "receipt_id": f"rcpt-{len(self.state.receipts)+1:08d}",
            "workstream_id": workstream_id,
            "receipt_type": receipt_type,
            "provider": provider,
            "body": body,
            "observed_at": utc_now(),
        }
        receipt["sha256"] = digest(receipt)
        self.append_event("RECEIPT_RECORDED", receipt)
        return receipt

    def evaluate_completion(self, workstream_id: str, contract: CompletionContract) -> dict[str, Any]:
        present = {
            row["receipt_type"]
            for row in self.state.receipts.values()
            if row["workstream_id"] == workstream_id
        }
        missing = sorted(set(contract.required_receipts) - present)
        state = "VERIFIED" if not missing else "PARTIALLY_VERIFIED"
        self.append_event("COMPLETION_EVALUATED", {"workstream_id": workstream_id, "state": state, "missing": missing})
        return {"workstream_id": workstream_id, "state": state, "missing": missing}

    def checkpoint(self, mission_id: str) -> dict[str, Any]:
        payload = {
            "mission_id": mission_id,
            "state_hash": digest(asdict(self.state)),
            "ready_workstreams": [w["workstream_id"] for w in self.ready_workstreams()],
            "created_at": utc_now(),
        }
        payload["checkpoint_id"] = f"cp-{len(self.state.checkpoints)+1:08d}"
        self.append_event("CHECKPOINT_CREATED", payload)
        return payload

    def classify_failure(self, failure: dict[str, Any]) -> dict[str, str]:
        kind = str(failure.get("class", "LOGIC")).upper()
        if kind not in self.FAILURE_REPAIRS:
            kind = "LOGIC"
        return {"class": kind, "repair": self.FAILURE_REPAIRS[kind]}

    def record_lesson(self, trigger: str, lesson: str, evidence_ref: str) -> dict[str, Any]:
        record = {"trigger": trigger, "lesson": lesson, "evidence_ref": evidence_ref, "recorded_at": utc_now()}
        self.append_event("LESSON_RECORDED", record)
        return record

    def compile_lesson_to_policy(self, lesson_index: int, policy_type: str) -> dict[str, Any]:
        lesson = self.state.lessons[lesson_index]
        policy = {
            "policy_id": f"policy-{len(self.state.policies)+1:06d}",
            "policy_type": policy_type,
            "source_lesson": lesson,
            "status": "ACTIVE",
            "compiled_at": utc_now(),
        }
        self.append_event("POLICY_COMPILED", policy)
        return policy

    def update_reliability(self, action_class: str, success: bool) -> dict[str, Any]:
        current = self.state.reliability.get(action_class, {"attempts": 0, "verified_successes": 0})
        current["attempts"] += 1
        current["verified_successes"] += int(success)
        current["success_rate"] = current["verified_successes"] / current["attempts"]
        current["autonomy"] = "AUTOMATIC" if current["success_rate"] >= 0.98 else "EXTRA_VERIFICATION" if current["success_rate"] >= 0.90 else "SHADOW_FIRST" if current["success_rate"] >= 0.75 else "CONTROLLED"
        self.append_event("RELIABILITY_UPDATED", {"action_class": action_class, **current})
        return current

    def cybernetic_decision(self, *, error_rate: float, queue_age_seconds: int, proof_age_seconds: int, retries: int) -> dict[str, Any]:
        if proof_age_seconds > 86400:
            action = "REFRESH_PROOF"
        elif error_rate > 0.20 or retries >= 4:
            action = "ULTRASTABLE_RECONFIGURE"
        elif queue_age_seconds > 3600:
            action = "REPRIORITISE_OR_FAILOVER"
        elif error_rate > 0.05:
            action = "DAMPEN_AND_RETRY"
        else:
            action = "CONTINUE"
        return {"action": action, "error_rate": error_rate, "queue_age_seconds": queue_age_seconds, "proof_age_seconds": proof_age_seconds, "retries": retries}

    def verify_event_chain(self) -> bool:
        previous = "GENESIS"
        for event in self._events():
            if event["previous_hash"] != previous:
                return False
            payload = {k: v for k, v in event.items() if k != "event_hash"}
            if digest(payload) != event["event_hash"]:
                return False
            previous = event["event_hash"]
        return True

    def _events(self) -> list[dict[str, Any]]:
        if not self.events.exists():
            return []
        return [json.loads(line) for line in self.events.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _replay(self) -> None:
        self.state = RuntimeState()
        for event in self._events():
            self._apply(event)
        self._persist()

    def _apply(self, event: dict[str, Any]) -> None:
        kind, payload = event["event_type"], event["payload"]
        if kind == "MISSION_REGISTERED":
            self.state.missions[payload["mission_id"]] = payload
        elif kind == "WORKSTREAM_REGISTERED":
            self.state.workstreams[payload["workstream_id"]] = payload
        elif kind == "PROVIDER_CAPABILITY_VERIFIED":
            self.state.providers[f"{payload['provider']}:{payload['operation']}"] = payload
        elif kind == "RECEIPT_RECORDED":
            self.state.receipts[payload["receipt_id"]] = payload
        elif kind == "COMPLETION_EVALUATED":
            self.state.workstreams[payload["workstream_id"]]["status"] = payload["state"]
        elif kind == "CHECKPOINT_CREATED":
            self.state.checkpoints[payload["checkpoint_id"]] = payload
        elif kind == "LESSON_RECORDED":
            self.state.lessons.append(payload)
        elif kind == "POLICY_COMPILED":
            self.state.policies.append(payload)
        elif kind == "RELIABILITY_UPDATED":
            action_class = payload.pop("action_class")
            self.state.reliability[action_class] = payload

    def _persist(self) -> None:
        atomic_json(self.snapshot, asdict(self.state))
