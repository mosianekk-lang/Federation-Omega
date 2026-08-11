from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable


class LearningFabricError(RuntimeError):
    """Base error for the Federation learning fabric."""


class PolicyError(LearningFabricError):
    """Raised when the policy is missing or unsafe."""


class EventType(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    CONSTRAINT = "CONSTRAINT"
    RECOVERY = "RECOVERY"
    CORRECTION = "CORRECTION"


@dataclass(frozen=True)
class TriggerActivation:
    trigger_id: str
    action: str
    reason: str
    state: str
    authority_ceiling: str
    source_event_hash: str
    activation_count: int
    activated_at: str


SECRET_KEY_PATTERN = re.compile(
    r"(authorization|credential|secret|password|private[_-]?key|access[_-]?token|refresh[_-]?token|api[_-]?key)",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b"),
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def digest(value: Any) -> str:
    if isinstance(value, bytes):
        payload = value
    elif isinstance(value, str):
        payload = value.encode("utf-8")
    else:
        payload = canonical_bytes(value)
    return hashlib.sha256(payload).hexdigest()


def redact(value: Any, key: str = "") -> Any:
    """Redact secret-bearing keys and common secret-looking values recursively."""
    if SECRET_KEY_PATTERN.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(item, key) for item in value]
    if isinstance(value, tuple):
        return [redact(item, key) for item in value]
    if isinstance(value, str):
        rendered = value
        for pattern in SECRET_VALUE_PATTERNS:
            rendered = pattern.sub("[REDACTED]", rendered)
        return rendered
    return value


def load_policy(path: str | Path | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if payload is None:
        if path is None:
            raise PolicyError("policy path or payload is required")
        policy_path = Path(path)
        if not policy_path.is_file():
            raise PolicyError(f"learning policy is missing: {policy_path}")
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    policy = copy.deepcopy(payload)
    if policy.get("policy_id") != "FEDOMEGA-CONTINUOUS-LEARNING-TRIGGERS-V1":
        raise PolicyError("unexpected learning policy identifier")
    if policy.get("authority_ceiling") != "A1_INTERNAL":
        raise PolicyError("learning fabric authority ceiling must remain A1_INTERNAL")
    if policy.get("external_effect") is not False:
        raise PolicyError("learning fabric must not have an external effect")
    if policy.get("source_repository_runtime_output") != "FORBIDDEN":
        raise PolicyError("runtime learning output must remain outside canonical source")
    return policy


class LearningFabric:
    """Append-only event learning plus deterministic algorithm-trigger state.

    The append-only ledger is evidence. Trigger state is a derived artifact and may
    be regenerated from the ledger. The fabric does not execute consequential
    actions and cannot expand authority.
    """

    def __init__(
        self,
        workspace: str | Path,
        *,
        policy_path: str | Path | None = None,
        policy: dict[str, Any] | None = None,
    ) -> None:
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.policy = load_policy(policy_path, policy)
        self.ledger_path = self.workspace / "learning_ledger.jsonl"
        self.trigger_state_path = self.workspace / "algorithm_trigger_state.json"
        self.summary_path = self.workspace / "learning_summary.json"

    def _events(self) -> list[dict[str, Any]]:
        if not self.ledger_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line_number, line in enumerate(
            self.ledger_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LearningFabricError(
                    f"invalid ledger JSON at line {line_number}"
                ) from exc
            rows.append(row)
        return rows

    def _load_trigger_state(self) -> dict[str, Any]:
        if not self.trigger_state_path.exists():
            return {
                "schema": "FEDOMEGA_ALGORITHM_TRIGGER_STATE_V1",
                "policy_id": self.policy["policy_id"],
                "policy_version": self.policy["version"],
                "updated_at": None,
                "event_count": 0,
                "event_type_counts": {},
                "category_counts": {},
                "fingerprints": {},
                "workflow_success_counts": {},
                "workflow_failure_counts": {},
                "activations": {},
                "unresolved_failure_fingerprints": [],
                "authority_ceiling": "A1_INTERNAL",
                "external_effect": False,
            }
        state = json.loads(self.trigger_state_path.read_text(encoding="utf-8"))
        if state.get("authority_ceiling") != "A1_INTERNAL":
            raise LearningFabricError("trigger state attempted authority expansion")
        if state.get("external_effect") is not False:
            raise LearningFabricError("trigger state attempted an external effect")
        return state

    def _write_json(self, path: Path, value: Any) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def _normalise_text(value: Any) -> str:
        return " ".join(str(value).lower().split())

    def classify_category(
        self,
        event_type: EventType,
        summary: str,
        details: dict[str, Any],
        explicit: str | None = None,
    ) -> str:
        if explicit:
            category = explicit.upper()
            if category not in self.policy["failure_categories"]:
                return "UNKNOWN"
            return category
        if event_type == EventType.SUCCESS:
            return "NONE"
        text = self._normalise_text({"summary": summary, "details": details})
        for category, tokens in self.policy["failure_categories"].items():
            if category == "UNKNOWN":
                continue
            if any(token.lower() in text for token in tokens):
                return category
        return "UNKNOWN"

    def _existing_by_event_key(self, event_key: str) -> dict[str, Any] | None:
        for event in self._events():
            if event.get("event_key") == event_key:
                existing = copy.deepcopy(event)
                existing["idempotent"] = True
                return existing
        return None

    def record(
        self,
        *,
        event_type: EventType | str,
        system_id: str,
        workflow_id: str,
        mission_id: str,
        summary: str,
        details: dict[str, Any] | None = None,
        evidence_refs: Iterable[str] = (),
        category: str | None = None,
        source_run_id: str = "",
        event_key: str | None = None,
        authority: str = "A1_INTERNAL",
        external_effect: bool = False,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        event_type = event_type if isinstance(event_type, EventType) else EventType(str(event_type).upper())
        if authority not in {"A0_READ", "A1_INTERNAL"}:
            raise LearningFabricError("learning capture cannot exceed A1_INTERNAL")
        if external_effect:
            raise LearningFabricError("learning capture cannot perform an external effect")
        for field_name, field_value in (
            ("system_id", system_id),
            ("workflow_id", workflow_id),
            ("mission_id", mission_id),
            ("summary", summary),
        ):
            if not isinstance(field_value, str) or not field_value.strip():
                raise LearningFabricError(f"{field_name} must be a non-empty string")

        safe_details = redact(details or {})
        safe_refs = [str(item) for item in evidence_refs]
        timestamp = occurred_at or utc_now()
        resolved_category = self.classify_category(
            event_type, summary, safe_details, category
        )
        key = event_key or digest(
            {
                "source_run_id": source_run_id,
                "event_type": event_type.value,
                "system_id": system_id,
                "workflow_id": workflow_id,
                "mission_id": mission_id,
                "summary": summary,
                "details": safe_details,
                "evidence_refs": safe_refs,
            }
        )
        existing = self._existing_by_event_key(key)
        if existing is not None:
            return existing

        events = self._events()
        previous_hash = events[-1]["event_hash"] if events else "GENESIS"
        fingerprint = digest(
            {
                "event_type": event_type.value,
                "category": resolved_category,
                "system_id": system_id,
                "workflow_id": workflow_id,
                "normalised_summary": self._normalise_text(summary),
            }
        )
        body = {
            "schema": "FEDOMEGA_LEARNING_EVENT_V1",
            "policy_id": self.policy["policy_id"],
            "policy_version": self.policy["version"],
            "event_id": f"LRN-{digest([key, timestamp, previous_hash])[:20]}",
            "event_key": key,
            "occurred_at": timestamp,
            "captured_at": utc_now(),
            "event_type": event_type.value,
            "category": resolved_category,
            "system_id": system_id,
            "workflow_id": workflow_id,
            "mission_id": mission_id,
            "source_run_id": source_run_id,
            "summary": redact(summary),
            "details": safe_details,
            "evidence_refs": safe_refs,
            "fingerprint": fingerprint,
            "authority_ceiling": "A1_INTERNAL",
            "external_effect": False,
            "previous_hash": previous_hash,
        }
        event_hash = digest(body)
        event = {**body, "event_hash": event_hash, "idempotent": False}
        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")
        activations = self._update_trigger_state(event)
        event["trigger_activations"] = [asdict(item) for item in activations]
        self._write_summary()
        return event

    def _activate(
        self,
        state: dict[str, Any],
        event: dict[str, Any],
        action: str,
        reason: str,
        activation_state: str = "ACTIVE",
    ) -> TriggerActivation:
        trigger_id = f"TRG-{digest([action, event['workflow_id'], event['category']])[:16]}"
        current = state["activations"].get(trigger_id, {})
        count = int(current.get("activation_count", 0)) + 1
        activation = TriggerActivation(
            trigger_id=trigger_id,
            action=action,
            reason=reason,
            state=activation_state,
            authority_ceiling="A1_INTERNAL",
            source_event_hash=event["event_hash"],
            activation_count=count,
            activated_at=utc_now(),
        )
        state["activations"][trigger_id] = asdict(activation)
        return activation

    def _update_trigger_state(
        self, event: dict[str, Any]
    ) -> list[TriggerActivation]:
        state = self._load_trigger_state()
        state["event_count"] = int(state.get("event_count", 0)) + 1
        event_type = event["event_type"]
        category = event["category"]
        state["event_type_counts"][event_type] = (
            int(state["event_type_counts"].get(event_type, 0)) + 1
        )
        state["category_counts"][category] = (
            int(state["category_counts"].get(category, 0)) + 1
        )

        fingerprint_state = state["fingerprints"].setdefault(
            event["fingerprint"],
            {
                "event_type": event_type,
                "category": category,
                "system_id": event["system_id"],
                "workflow_id": event["workflow_id"],
                "count": 0,
                "last_event_hash": "",
            },
        )
        fingerprint_state["count"] += 1
        fingerprint_state["last_event_hash"] = event["event_hash"]
        key = f"{event['system_id']}::{event['workflow_id']}"

        activations: list[TriggerActivation] = []
        global_triggers = self.policy["global_triggers"]

        if event_type == EventType.FAILURE.value:
            state["workflow_failure_counts"][key] = (
                int(state["workflow_failure_counts"].get(key, 0)) + 1
            )
            unresolved = set(state.get("unresolved_failure_fingerprints", []))
            unresolved.add(event["fingerprint"])
            state["unresolved_failure_fingerprints"] = sorted(unresolved)
            for action in global_triggers["every_failure"]:
                activations.append(
                    self._activate(state, event, action, "every failure must be learned")
                )
            for action in self.policy["trigger_actions"].get(category, []):
                activations.append(
                    self._activate(
                        state,
                        event,
                        action,
                        f"failure category {category}",
                    )
                )
            if fingerprint_state["count"] >= int(
                self.policy["thresholds"]["repeated_failure_open_circuit"]
            ):
                for action in global_triggers["repeated_failure"]:
                    activations.append(
                        self._activate(
                            state,
                            event,
                            action,
                            "repeated failure threshold reached",
                        )
                    )

        elif event_type == EventType.CONSTRAINT.value:
            for action in global_triggers["every_constraint"]:
                activations.append(
                    self._activate(state, event, action, "constraint encountered")
                )
            for action in self.policy["trigger_actions"].get(category, []):
                activations.append(
                    self._activate(
                        state, event, action, f"constraint category {category}"
                    )
                )

        elif event_type == EventType.SUCCESS.value:
            prior_failures = int(state["workflow_failure_counts"].get(key, 0))
            success_count = int(state["workflow_success_counts"].get(key, 0)) + 1
            state["workflow_success_counts"][key] = success_count
            for action in global_triggers["every_success"]:
                activations.append(
                    self._activate(state, event, action, "successful outcome recorded")
                )
            if prior_failures:
                for action in global_triggers["success_after_failure"]:
                    activations.append(
                        self._activate(
                            state,
                            event,
                            action,
                            "success followed a recorded failure",
                        )
                    )
            if success_count >= int(
                self.policy["thresholds"]["repeated_success_confidence_candidate"]
            ):
                for action in global_triggers["repeated_success"]:
                    activations.append(
                        self._activate(
                            state,
                            event,
                            action,
                            "repeated success threshold reached",
                            "CANDIDATE",
                        )
                    )

        elif event_type == EventType.CORRECTION.value:
            for action in global_triggers["every_correction"]:
                activations.append(
                    self._activate(state, event, action, "correction recorded")
                )

        elif event_type == EventType.RECOVERY.value:
            unresolved = set(state.get("unresolved_failure_fingerprints", []))
            resolved = event["details"].get("resolved_failure_fingerprint")
            if resolved:
                unresolved.discard(str(resolved))
                state["unresolved_failure_fingerprints"] = sorted(unresolved)
            for action in global_triggers["every_recovery"]:
                activations.append(
                    self._activate(state, event, action, "recovery recorded")
                )

        state["updated_at"] = utc_now()
        state["ledger_head_hash"] = event["event_hash"]
        state["authority_ceiling"] = "A1_INTERNAL"
        state["external_effect"] = False
        self._write_json(self.trigger_state_path, state)
        return activations

    def verify_chain(self) -> dict[str, Any]:
        previous = "GENESIS"
        errors: list[str] = []
        events = self._events()
        for index, event in enumerate(events, start=1):
            if event.get("previous_hash") != previous:
                errors.append(f"line {index}: previous hash mismatch")
            body = {
                key: value
                for key, value in event.items()
                if key not in {"event_hash", "idempotent", "trigger_activations"}
            }
            expected = digest(body)
            if event.get("event_hash") != expected:
                errors.append(f"line {index}: event hash mismatch")
            previous = str(event.get("event_hash", ""))
        return {
            "schema": "FEDOMEGA_LEARNING_CHAIN_VERIFICATION_V1",
            "status": "PASSED" if not errors else "FAILED",
            "event_count": len(events),
            "ledger_head_hash": previous,
            "errors": errors,
        }

    def _write_summary(self) -> dict[str, Any]:
        verification = self.verify_chain()
        state = self._load_trigger_state()
        summary = {
            "schema": "FEDOMEGA_LEARNING_SUMMARY_V1",
            "policy_id": self.policy["policy_id"],
            "policy_version": self.policy["version"],
            "recorded_at": utc_now(),
            "chain": verification,
            "event_type_counts": state.get("event_type_counts", {}),
            "category_counts": state.get("category_counts", {}),
            "active_trigger_count": sum(
                1
                for activation in state.get("activations", {}).values()
                if activation.get("state") == "ACTIVE"
            ),
            "candidate_trigger_count": sum(
                1
                for activation in state.get("activations", {}).values()
                if activation.get("state") == "CANDIDATE"
            ),
            "unresolved_failure_fingerprints": state.get(
                "unresolved_failure_fingerprints", []
            ),
            "authority_ceiling": "A1_INTERNAL",
            "external_effect": False,
            "proof_destination": self.policy["proof_destination"],
        }
        self._write_json(self.summary_path, summary)
        return summary

    def summary(self) -> dict[str, Any]:
        return self._write_summary()

    def capture_result(
        self,
        result: dict[str, Any],
        *,
        system_id: str,
        workflow_id: str,
        mission_id: str,
        source_run_id: str = "",
        evidence_refs: Iterable[str] = (),
    ) -> list[dict[str, Any]]:
        """Capture success/failure plus explicit constraints from a result object."""
        safe_result = redact(result)
        status = str(
            result.get("status")
            or result.get("state")
            or result.get("result")
            or "UNKNOWN"
        ).upper()
        success_states = {
            "SUCCESS",
            "PASSED",
            "PASS",
            "VERIFIED",
            "COMPLETE_VERIFIED",
            "OPERATIONAL",
        }
        captured: list[dict[str, Any]] = []
        event_type = EventType.SUCCESS if status in success_states else EventType.FAILURE
        captured.append(
            self.record(
                event_type=event_type,
                system_id=system_id,
                workflow_id=workflow_id,
                mission_id=mission_id,
                summary=f"terminal result: {status}",
                details={"result": safe_result},
                evidence_refs=evidence_refs,
                source_run_id=source_run_id,
            )
        )

        checks = result.get("checks")
        if isinstance(checks, dict):
            for name, passed in checks.items():
                if passed is False:
                    captured.append(
                        self.record(
                            event_type=EventType.FAILURE,
                            system_id=system_id,
                            workflow_id=workflow_id,
                            mission_id=mission_id,
                            summary=f"proof gate failed: {name}",
                            details={"check": name, "observed": passed},
                            evidence_refs=evidence_refs,
                            category="CONTRACT",
                            source_run_id=source_run_id,
                            event_key=digest(
                                [source_run_id, "FAILED_CHECK", workflow_id, name]
                            ),
                        )
                    )

        constraint_keys = (
            "constraints",
            "blockers",
            "missing",
            "held_functions",
            "residual_risks",
        )
        for key in constraint_keys:
            value = result.get(key)
            if value in (None, "", [], {}):
                continue
            items = value if isinstance(value, list) else [value]
            for index, item in enumerate(items):
                captured.append(
                    self.record(
                        event_type=EventType.CONSTRAINT,
                        system_id=system_id,
                        workflow_id=workflow_id,
                        mission_id=mission_id,
                        summary=f"{key}: {item}",
                        details={"field": key, "value": item},
                        evidence_refs=evidence_refs,
                        source_run_id=source_run_id,
                        event_key=digest(
                            [source_run_id, "CONSTRAINT", workflow_id, key, index, item]
                        ),
                    )
                )
        return captured
