from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

try:
    from .sol_62_frontier_primitives import (
        AuthorityError,
        AuthorityLease,
        ConstraintError,
        EffectContract,
        FenceError,
        GatewayPolicy,
        GuardrailPipeline,
        IdempotencyCollision,
        ProofBundleVerifier,
        ProofEnvelope,
        ProofError,
        SQLiteControlPlane,
        TraceEnvelope,
        WorkloadIdentityPolicy,
        digest,
        stable_json,
        utc_now,
    )
except ImportError:
    from sol_62_frontier_primitives import (
        AuthorityError,
        AuthorityLease,
        ConstraintError,
        EffectContract,
        FenceError,
        GatewayPolicy,
        GuardrailPipeline,
        IdempotencyCollision,
        ProofBundleVerifier,
        ProofEnvelope,
        ProofError,
        SQLiteControlPlane,
        TraceEnvelope,
        WorkloadIdentityPolicy,
        digest,
        stable_json,
        utc_now,
    )


SOL62_VERSION = "6.2"
TERMINAL_EFFECT_STATES = {"VERIFIED", "COMPENSATED", "CANCELLED", "DEAD_LETTER"}


@dataclass(frozen=True)
class MissionSpec:
    mission_id: str
    objective: str
    initial_state: Mapping[str, Any]
    target_state: Mapping[str, Any]
    success_proofs: tuple[Mapping[str, Any], ...] = ()
    constraints: tuple[str, ...] = ()
    version: int = 1


@dataclass(frozen=True)
class TransitionSpec:
    transition_id: str
    mission_id: str
    operation: str
    target: str
    from_state: Mapping[str, Any]
    to_state: Mapping[str, Any]
    dependencies: tuple[str, ...] = ()
    required_proofs: tuple[Mapping[str, Any], ...] = ()
    constraints: tuple[str, ...] = ()
    conflict_domains: tuple[str, ...] = ()
    priority: int = 50
    risk_class: str = "LOW"
    consequential: bool = False
    simulation_required: bool = False
    source_version: str = "UNPINNED"


@dataclass(frozen=True)
class ExecutionIntent:
    effect_id: str
    transition_id: str
    provider: str
    payload: Mapping[str, Any]
    semantics: str
    idempotency_key: str
    actor: str
    source_version: str
    expected_readback: Mapping[str, Any] = field(default_factory=dict)
    rollback_required: bool = False


class Sol62ControlPlane(SQLiteControlPlane):
    """SOL 6.2 control-plane compatibility wrapper.

    Tightens schema monotonicity without changing the SOL 6.1 hardening
    primitive: same-version/same-content is idempotent; any downgrade fails.
    """

    def register_schema(self, schema_id: str, version: int, body: Mapping[str, Any]) -> dict[str, Any]:
        body_sha = digest(body)
        prior = self.db.execute(
            "SELECT version,schema_sha256 FROM schemas WHERE schema_id=?", (schema_id,)
        ).fetchone()
        if prior:
            prior_version = int(prior["version"])
            if int(version) < prior_version:
                raise ConstraintError("SCHEMA_VERSION_ROLLBACK_FORBIDDEN")
            if int(version) == prior_version:
                if body_sha != prior["schema_sha256"]:
                    raise ConstraintError("SCHEMA_REPLACEMENT_REQUIRES_HIGHER_VERSION")
                return {"schema_id": schema_id, "version": prior_version, "sha256": prior["schema_sha256"]}
        return super().register_schema(schema_id, int(version), body)

    def prepare_effect_with_intent(
        self,
        *,
        contract: EffectContract,
        payload: Mapping[str, Any],
        intent_body: Mapping[str, Any],
        mission_id: str,
        transition_id: str,
    ) -> dict[str, Any]:
        """Atomically reserve idempotency, persist intent, prepare effect and audit."""
        request = {
            "provider": contract.provider,
            "operation": contract.operation,
            "target": contract.target,
            "payload": dict(payload),
            "expected_readback": dict(contract.expected_readback),
        }
        request_hash = digest(request)
        with self.tx() as db:
            idem = db.execute(
                "SELECT * FROM idempotency WHERE idem_key=?", (contract.idempotency_key,)
            ).fetchone()
            if idem:
                if idem["request_sha256"] != request_hash:
                    raise IdempotencyCollision(
                        "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_REQUEST"
                    )
            else:
                now = utc_now()
                db.execute(
                    "INSERT INTO idempotency(idem_key,request_sha256,semantics,state,result_json,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (
                        contract.idempotency_key,
                        request_hash,
                        contract.semantics,
                        "RESERVED",
                        None,
                        now,
                        now,
                    ),
                )

            existing_effect = db.execute(
                "SELECT * FROM effects WHERE idem_key=?", (contract.idempotency_key,)
            ).fetchone()
            effect_created = existing_effect is None
            if existing_effect:
                if existing_effect["request_sha256"] != request_hash:
                    raise IdempotencyCollision("EFFECT_REQUEST_COLLISION")
                if existing_effect["effect_id"] != contract.effect_id:
                    raise IdempotencyCollision("IDEMPOTENCY_KEY_BOUND_TO_DIFFERENT_EFFECT")
                effect_row = dict(existing_effect)
            else:
                now = utc_now()
                db.execute(
                    "INSERT INTO effects(effect_id,idem_key,request_sha256,provider,operation,target,semantics,"
                    "consequential,rollback_required,state,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        contract.effect_id,
                        contract.idempotency_key,
                        request_hash,
                        contract.provider,
                        contract.operation,
                        contract.target,
                        contract.semantics,
                        int(contract.consequential),
                        int(contract.rollback_required),
                        "PREPARED",
                        now,
                        now,
                    ),
                )
                effect_row = dict(
                    db.execute(
                        "SELECT * FROM effects WHERE effect_id=?", (contract.effect_id,)
                    ).fetchone()
                )

            intent_existing = db.execute(
                "SELECT value_json FROM state "
                "WHERE namespace='sol62.effect_intent' AND item_key=?",
                (contract.effect_id,),
            ).fetchone()
            intent_json = stable_json(dict(intent_body))
            if intent_existing:
                if digest(json.loads(intent_existing["value_json"])) != digest(
                    dict(intent_body)
                ):
                    raise ConstraintError("EFFECT_INTENT_COLLISION")
            else:
                db.execute(
                    "INSERT INTO state(namespace,item_key,value_json,version,updated_at) "
                    "VALUES('sol62.effect_intent',?,?,1,?)",
                    (contract.effect_id, intent_json, utc_now()),
                )

            if effect_created:
                previous = db.execute(
                    "SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1"
                ).fetchone()
                previous_hash = previous["event_hash"] if previous else "GENESIS"
                next_seq = int(
                    db.execute(
                        "SELECT COALESCE(MAX(seq),0)+1 AS n FROM events"
                    ).fetchone()["n"]
                )
                created_at = utc_now()
                event_body = {
                    "event_id": f"evt-{next_seq:012d}",
                    "aggregate": mission_id,
                    "kind": "SOL62_EFFECT_PREPARED",
                    "payload": {
                        "effect_id": contract.effect_id,
                        "transition_id": transition_id,
                        "request_sha256": request_hash,
                    },
                    "previous_hash": previous_hash,
                    "created_at": created_at,
                }
                event_hash = digest(event_body)
                db.execute(
                    "INSERT INTO events(event_id,aggregate,kind,payload_json,previous_hash,event_hash,created_at) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (
                        event_body["event_id"],
                        mission_id,
                        event_body["kind"],
                        stable_json(event_body["payload"]),
                        previous_hash,
                        event_hash,
                        created_at,
                    ),
                )
            return {
                "effect_id": contract.effect_id,
                "state": effect_row["state"],
                "request_sha256": request_hash,
                "semantics": contract.semantics,
            }

    def authorize_effect_dispatch(
        self,
        *,
        effect_id: str,
        transition_id: str,
        mission_id: str,
        authority_lease_id: str | None,
        action: str,
        target: str,
        actor: str,
        source_version: str,
        now_epoch: int,
        worker: str,
        lease_epoch: int,
        fencing_token: int,
    ) -> dict[str, Any]:
        """Atomically consume action authority, fence and authorize dispatch."""
        with self.tx() as db:
            resource_id = f"transition:{transition_id}"
            fence = db.execute(
                "SELECT * FROM leases WHERE resource_id=?", (resource_id,)
            ).fetchone()
            if (
                not fence
                or fence["owner"] != worker
                or int(fence["epoch"]) != int(lease_epoch)
                or int(fence["fencing_token"]) != int(fencing_token)
                or int(fence["expires_at_epoch"]) <= int(now_epoch)
            ):
                raise FenceError("STALE_FENCE")

            effect = db.execute(
                "SELECT * FROM effects WHERE effect_id=?", (effect_id,)
            ).fetchone()
            if not effect:
                raise KeyError(effect_id)
            if effect["state"] != "PREPARED":
                raise FenceError("EFFECT_STATE_RACE")

            transition_status = db.execute(
                "SELECT version,value_json FROM state "
                "WHERE namespace='sol62.transition_status' AND item_key=?",
                (transition_id,),
            ).fetchone()
            if not transition_status:
                raise ConstraintError("TRANSITION_STATUS_MISSING")
            status_body = json.loads(transition_status["value_json"])
            if status_body.get("status") != "QUEUED":
                raise FenceError("TRANSITION_NOT_QUEUED")

            authority_result = None
            if authority_lease_id is not None:
                row = db.execute(
                    "SELECT * FROM authority_leases WHERE lease_id=?",
                    (authority_lease_id,),
                ).fetchone()
                if not row:
                    raise AuthorityError("AUTHORITY_LEASE_MISSING")
                lease = AuthorityLease(**json.loads(row["lease_json"]))
                reasons = lease.validate(
                    action=action,
                    target=target,
                    actor=actor,
                    source_version=source_version,
                    now_epoch=now_epoch,
                )
                if reasons:
                    raise AuthorityError(",".join(reasons))
                uses = int(row["uses"])
                if uses >= lease.max_uses:
                    raise AuthorityError("AUTHORITY_LEASE_ALREADY_CONSUMED")
                uses += 1
                db.execute(
                    "UPDATE authority_leases SET uses=?,consumed_at=? WHERE lease_id=?",
                    (uses, utc_now(), authority_lease_id),
                )
                authority_result = {
                    "lease_id": authority_lease_id,
                    "uses": uses,
                    "remaining": lease.max_uses - uses,
                }

            created_at = utc_now()
            db.execute(
                "UPDATE effects SET state='DISPATCHING',attempt_count=attempt_count+1,updated_at=? "
                "WHERE effect_id=?",
                (created_at, effect_id),
            )
            db.execute(
                "UPDATE state SET value_json=?,version=?,updated_at=? "
                "WHERE namespace='sol62.transition_status' AND item_key=?",
                (
                    stable_json({"status": "RUNNING", "superseded_by": None}),
                    int(transition_status["version"]) + 1,
                    created_at,
                    transition_id,
                ),
            )

            previous = db.execute(
                "SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            previous_hash = previous["event_hash"] if previous else "GENESIS"
            next_seq = int(
                db.execute("SELECT COALESCE(MAX(seq),0)+1 AS n FROM events").fetchone()["n"]
            )
            event_body = {
                "event_id": f"evt-{next_seq:012d}",
                "aggregate": mission_id,
                "kind": "SOL62_DISPATCH_AUTHORIZED",
                "payload": {
                    "effect_id": effect_id,
                    "transition_id": transition_id,
                    "fencing_token": int(fencing_token),
                    "authority_lease_id": authority_lease_id,
                },
                "previous_hash": previous_hash,
                "created_at": created_at,
            }
            event_hash = digest(event_body)
            db.execute(
                "INSERT INTO events(event_id,aggregate,kind,payload_json,previous_hash,event_hash,created_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    event_body["event_id"],
                    mission_id,
                    event_body["kind"],
                    stable_json(event_body["payload"]),
                    previous_hash,
                    event_hash,
                    created_at,
                ),
            )
            return {
                "effect_id": effect_id,
                "state": "DISPATCHING",
                "authority": authority_result,
                "event_hash": event_hash,
            }

    def commit_verified_transition(
        self,
        *,
        effect_id: str,
        mission_id: str,
        transition_id: str,
        expected_mission_version: int,
        next_state: Mapping[str, Any],
        proof_ids: Sequence[str],
    ) -> dict[str, Any]:
        """Atomically bind VERIFIED effect, mission projection and audit event."""
        with self.tx() as db:
            effect = db.execute(
                "SELECT state FROM effects WHERE effect_id=?", (effect_id,)
            ).fetchone()
            if not effect or effect["state"] != "OBSERVED":
                raise ConstraintError("EFFECT_NOT_OBSERVED")
            mission = db.execute(
                "SELECT version FROM state WHERE namespace='sol62.mission_state' AND item_key=?",
                (mission_id,),
            ).fetchone()
            if not mission or int(mission["version"]) != int(expected_mission_version):
                raise FenceError("MISSION_STATE_CHANGED_BEFORE_COMMIT")
            transition_status = db.execute(
                "SELECT version,value_json FROM state "
                "WHERE namespace='sol62.transition_status' AND item_key=?",
                (transition_id,),
            ).fetchone()
            if not transition_status:
                raise ConstraintError("TRANSITION_STATUS_MISSING")
            status_value = json.loads(transition_status["value_json"])
            if status_value.get("status") != "RUNNING":
                raise FenceError("TRANSITION_NOT_RUNNING")

            previous = db.execute(
                "SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            previous_hash = previous["event_hash"] if previous else "GENESIS"
            next_seq = int(
                db.execute("SELECT COALESCE(MAX(seq),0)+1 AS n FROM events").fetchone()["n"]
            )
            created_at = utc_now()
            event_body = {
                "event_id": f"evt-{next_seq:012d}",
                "aggregate": mission_id,
                "kind": "SOL62_STATE_TRANSITION_COMMITTED",
                "payload": {
                    "transition_id": transition_id,
                    "effect_id": effect_id,
                    "state_sha256": digest(next_state),
                    "proof_ids": list(proof_ids),
                },
                "previous_hash": previous_hash,
                "created_at": created_at,
            }
            event_hash = digest(event_body)

            db.execute(
                "UPDATE effects SET state='VERIFIED',updated_at=? WHERE effect_id=?",
                (created_at, effect_id),
            )
            db.execute(
                "UPDATE state SET value_json=?,version=?,updated_at=? "
                "WHERE namespace='sol62.mission_state' AND item_key=?",
                (
                    stable_json(dict(next_state)),
                    int(expected_mission_version) + 1,
                    created_at,
                    mission_id,
                ),
            )
            db.execute(
                "UPDATE state SET value_json=?,version=?,updated_at=? "
                "WHERE namespace='sol62.transition_status' AND item_key=?",
                (
                    stable_json({"status": "VERIFIED", "superseded_by": None}),
                    int(transition_status["version"]) + 1,
                    created_at,
                    transition_id,
                ),
            )
            db.execute(
                "INSERT INTO events(event_id,aggregate,kind,payload_json,previous_hash,event_hash,created_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    event_body["event_id"],
                    mission_id,
                    event_body["kind"],
                    stable_json(event_body["payload"]),
                    previous_hash,
                    event_hash,
                    created_at,
                ),
            )
            return {
                "event_id": event_body["event_id"],
                "event_hash": event_hash,
                "mission_version": int(expected_mission_version) + 1,
                "transition_status": "VERIFIED",
                "effect_state": "VERIFIED",
            }


class Sol62Runtime:
    """Transactional, self-verifying evolution of the SOL 6.1 runtime.

    The unit of completion is an independently observed target-state transition,
    not task status. Provider effects are prepared durably before dispatch,
    authority is action-bound and one-use, and state advances only after
    provider readback plus semantically verified proof.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        gateway_policy: GatewayPolicy | None = None,
        identity_policy: WorkloadIdentityPolicy | None = None,
        guardrails: GuardrailPipeline | None = None,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.control = Sol62ControlPlane(self.root / "sol62.sqlite3")
        self.gateway_policy = gateway_policy
        self.identity_policy = identity_policy
        self.guardrails = guardrails or GuardrailPipeline()
        self._register_schemas()

    def close(self) -> None:
        self.control.close()

    def _register_schemas(self) -> None:
        self.control.register_schema(
            "sol62.mission",
            1,
            {
                "required": ["mission_id", "objective", "initial_state", "target_state", "version"],
                "completion": "OBSERVED_TARGET_STATE_PLUS_PROOF",
            },
        )
        self.control.register_schema(
            "sol62.transition",
            1,
            {
                "required": ["transition_id", "mission_id", "from_state", "to_state", "operation", "target"],
                "execution": "PREPARE_AUTHORIZE_DISPATCH_READBACK_VERIFY_COMMIT",
            },
        )
        self.control.register_schema(
            "sol62.proof",
            1,
            {
                "required": [
                    "proof_id", "subject", "target", "operation", "issuer", "observed_at",
                    "source_version", "evidence_sha256", "semantic_state",
                ],
                "semantic_state": "VERIFIED",
            },
        )

    @staticmethod
    def _matches(observed: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
        return all(observed.get(key) == value for key, value in expected.items())

    def _put_once(self, namespace: str, key: str, value: Mapping[str, Any]) -> dict[str, Any]:
        current = self.control.get_state(namespace, key)
        body = dict(value)
        if current:
            if digest(current["value"]) != digest(body):
                raise ConstraintError(f"{namespace.upper()}_ID_COLLISION")
            return current
        version = self.control.cas_put(namespace, key, body, expected_version=0)
        return {"value": body, "version": version}

    def _update(self, namespace: str, key: str, value: Mapping[str, Any]) -> dict[str, Any]:
        current = self.control.get_state(namespace, key)
        if not current:
            raise KeyError(f"{namespace}:{key}")
        version = self.control.cas_put(namespace, key, dict(value), expected_version=int(current["version"]))
        return {"value": dict(value), "version": version}

    def _rows(self, namespace: str) -> list[dict[str, Any]]:
        rows = self.control.db.execute(
            "SELECT item_key,value_json,version,updated_at FROM state WHERE namespace=? ORDER BY item_key",
            (namespace,),
        ).fetchall()
        return [
            {
                "key": row["item_key"],
                "value": json.loads(row["value_json"]),
                "version": int(row["version"]),
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def register_mission(self, spec: MissionSpec) -> dict[str, Any]:
        if not spec.mission_id or not spec.objective:
            raise ConstraintError("MISSION_ID_AND_OBJECTIVE_REQUIRED")
        if int(spec.version) < 1:
            raise ConstraintError("MISSION_VERSION_INVALID")
        body = dataclasses.asdict(spec)
        current = self.control.get_state("sol62.mission", spec.mission_id)
        if current:
            if digest(current["value"]) == digest(body):
                return current
            current_version = int(current["value"].get("version", 1))
            if int(spec.version) <= current_version:
                raise ConstraintError("MISSION_REPLACEMENT_REQUIRES_HIGHER_VERSION")
            version = self.control.cas_put(
                "sol62.mission",
                spec.mission_id,
                body,
                expected_version=int(current["version"]),
            )
            self.control.append_event(spec.mission_id, "SOL62_MISSION_REVISED", body)
            return {"value": body, "version": version}

        version = self.control.cas_put(
            "sol62.mission", spec.mission_id, body, expected_version=0
        )
        self.control.cas_put(
            "sol62.mission_state", spec.mission_id, dict(spec.initial_state), expected_version=0
        )
        self.control.append_event(spec.mission_id, "SOL62_MISSION_REGISTERED", body)
        return {"value": body, "version": version}

    def register_transition(self, spec: TransitionSpec) -> dict[str, Any]:
        if not self.control.get_state("sol62.mission", spec.mission_id):
            raise ConstraintError("MISSION_NOT_REGISTERED")
        if spec.risk_class not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            raise ConstraintError("INVALID_RISK_CLASS")
        body = dataclasses.asdict(spec)
        current = self.control.get_state("sol62.transition", spec.transition_id)
        if current:
            if digest(current["value"]) != digest(body):
                raise ConstraintError("TRANSITION_ID_COLLISION")
            return current
        stored = self._put_once("sol62.transition", spec.transition_id, body)
        self._put_once(
            "sol62.transition_status",
            spec.transition_id,
            {"status": "QUEUED", "superseded_by": None},
        )
        self.control.append_event(spec.mission_id, "SOL62_TRANSITION_REGISTERED", body)
        return stored

    def mission_state(self, mission_id: str) -> dict[str, Any]:
        state = self.control.get_state("sol62.mission_state", mission_id)
        if not state:
            raise KeyError(mission_id)
        return state

    def transition_status(self, transition_id: str) -> dict[str, Any]:
        state = self.control.get_state("sol62.transition_status", transition_id)
        if not state:
            raise KeyError(transition_id)
        return state

    def validate_mission_graph(self, mission_id: str) -> dict[str, Any]:
        transitions = {
            row["key"]: row["value"]
            for row in self._rows("sol62.transition")
            if row["value"]["mission_id"] == mission_id
        }
        unknown = sorted(
            {
                dependency
                for spec in transitions.values()
                for dependency in spec.get("dependencies", ())
                if dependency not in transitions
            }
        )
        if unknown:
            raise ConstraintError("UNKNOWN_DEPENDENCIES:" + ",".join(unknown))
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(transition_id: str) -> None:
            if transition_id in visiting:
                raise ConstraintError("DEPENDENCY_CYCLE")
            if transition_id in visited:
                return
            visiting.add(transition_id)
            for dependency in transitions[transition_id].get("dependencies", ()):
                visit(dependency)
            visiting.remove(transition_id)
            visited.add(transition_id)

        for transition_id in transitions:
            visit(transition_id)
        return {"valid": True, "transition_count": len(transitions)}

    def supersede_transition(
        self,
        failed_transition_id: str,
        replacement: TransitionSpec,
    ) -> dict[str, Any]:
        failed_status = self.transition_status(failed_transition_id)
        if failed_status["value"]["status"] not in {"FAILED", "BLOCKED"}:
            raise ConstraintError("ONLY_FAILED_OR_BLOCKED_TRANSITION_CAN_BE_SUPERSEDED")
        failed_spec = self.control.get_state("sol62.transition", failed_transition_id)["value"]
        if replacement.mission_id != failed_spec["mission_id"]:
            raise ConstraintError("REPLACEMENT_MISSION_MISMATCH")
        inherited = dataclasses.replace(
            replacement,
            required_proofs=tuple(
                list(replacement.required_proofs) + list(failed_spec.get("required_proofs", ()))
            ),
            constraints=tuple(
                sorted(set(replacement.constraints) | set(failed_spec.get("constraints", ())))
            ),
        )
        self.register_transition(inherited)
        self._update(
            "sol62.transition_status",
            failed_transition_id,
            {"status": "SUPERSEDED", "superseded_by": replacement.transition_id},
        )
        self.control.append_event(
            failed_spec["mission_id"],
            "SOL62_TRANSITION_SUPERSEDED",
            {
                "failed_transition_id": failed_transition_id,
                "replacement_transition_id": replacement.transition_id,
            },
        )
        return {"state": "SUPERSEDED", "replacement": replacement.transition_id}

    def ready_transitions(
        self,
        mission_id: str,
        *,
        satisfied_constraints: set[str],
        capacity: int | None = None,
    ) -> list[str]:
        self.validate_mission_graph(mission_id)
        current = self.mission_state(mission_id)["value"]
        status_rows = {
            row["key"]: row["value"] for row in self._rows("sol62.transition_status")
        }
        satisfied_transitions: set[str] = set()
        for transition_id, status_row in status_rows.items():
            status = status_row.get("status")
            if status in {"VERIFIED", "COMPENSATED"}:
                satisfied_transitions.add(transition_id)
            elif status == "SUPERSEDED":
                replacement = status_row.get("superseded_by")
                if replacement and status_rows.get(replacement, {}).get("status") == "VERIFIED":
                    satisfied_transitions.add(transition_id)
        candidates: list[dict[str, Any]] = []
        for row in self._rows("sol62.transition"):
            spec = row["value"]
            if spec["mission_id"] != mission_id:
                continue
            if status_rows.get(spec["transition_id"], {}).get("status") != "QUEUED":
                continue
            if not set(spec.get("dependencies", ())) <= satisfied_transitions:
                continue
            if not self._matches(current, spec.get("from_state", {})):
                continue
            if not set(spec.get("constraints", ())) <= set(satisfied_constraints):
                continue
            candidates.append(spec)
        candidates.sort(
            key=lambda item: (-int(item.get("priority", 50)), str(item["transition_id"]))
        )
        selected: list[str] = []
        used_domains: set[str] = set()
        for spec in candidates:
            if capacity is not None and len(selected) >= capacity:
                break
            domains = set(spec.get("conflict_domains", ()))
            if domains & used_domains:
                continue
            selected.append(spec["transition_id"])
            used_domains |= domains
        return selected

    def create_authority_lease(self, lease: AuthorityLease) -> dict[str, Any]:
        return self.control.create_authority_lease(lease)

    def acquire_execution_fence(
        self, transition_id: str, worker: str, *, ttl_seconds: int, now_epoch: int
    ) -> dict[str, Any]:
        return self.control.acquire_lease(
            f"transition:{transition_id}", worker, ttl_seconds=ttl_seconds, now_epoch=now_epoch
        )

    def prepare_execution(
        self,
        intent: ExecutionIntent,
        *,
        gateway_request: Mapping[str, Any],
        identity_claims: Mapping[str, Any],
        now_epoch: int,
    ) -> dict[str, Any]:
        if self.gateway_policy is None or self.identity_policy is None:
            raise ConstraintError("EXECUTION_POLICY_NOT_CONFIGURED")
        gateway = self.gateway_policy.admit(gateway_request)
        if not gateway["admitted"]:
            raise ConstraintError("GATEWAY_ADMISSION_FAILED:" + ",".join(gateway["reasons"]))
        identity = self.identity_policy.validate(identity_claims, now_epoch=now_epoch)
        if not identity["valid"]:
            raise ConstraintError("WORKLOAD_IDENTITY_FAILED:" + ",".join(identity["reasons"]))

        transition = self.control.get_state("sol62.transition", intent.transition_id)
        if not transition:
            raise ConstraintError("TRANSITION_NOT_REGISTERED")
        spec = transition["value"]
        if intent.source_version != spec["source_version"]:
            raise ConstraintError("SOURCE_VERSION_MISMATCH")
        if not self._matches(self.mission_state(spec["mission_id"])["value"], spec["from_state"]):
            raise ConstraintError("SOURCE_STATE_MISMATCH")

        input_guard = self.guardrails.check_input(
            {"transition_id": intent.transition_id, "payload": dict(intent.payload)}
        )
        if input_guard["decision"] != "ALLOW":
            raise ConstraintError("INPUT_GUARDRAIL_" + input_guard["decision"])
        pre_tool = self.guardrails.check_pre_tool(
            {
                "provider": intent.provider,
                "operation": spec["operation"],
                "target": spec["target"],
                "payload": dict(intent.payload),
            }
        )
        if pre_tool["decision"] != "ALLOW":
            raise ConstraintError("PRE_TOOL_GUARDRAIL_" + pre_tool["decision"])

        if bool(spec["consequential"]) and not bool(intent.rollback_required):
            raise ConstraintError("CONSEQUENTIAL_EFFECT_REQUIRES_ROLLBACK_CONTRACT")

        contract = EffectContract(
            effect_id=intent.effect_id,
            provider=intent.provider,
            operation=spec["operation"],
            target=spec["target"],
            semantics=intent.semantics,
            consequential=bool(spec["consequential"]),
            rollback_required=bool(intent.rollback_required),
            idempotency_key=intent.idempotency_key,
            expected_readback=dict(intent.expected_readback),
        )
        return self.control.prepare_effect_with_intent(
            contract=contract,
            payload=dict(intent.payload),
            intent_body=dataclasses.asdict(intent),
            mission_id=spec["mission_id"],
            transition_id=intent.transition_id,
        )

    def register_verified_proof(
        self,
        envelope: ProofEnvelope,
        evidence: Any,
        *,
        semantic_verifier: Callable[[ProofEnvelope, Any], bool],
        now_epoch: int,
        require_provider_attestation: bool = False,
        attestation_verifier: Callable[[ProofEnvelope, Any], bool] | None = None,
    ) -> dict[str, Any]:
        if digest(evidence) != envelope.evidence_sha256:
            raise ProofError("EVIDENCE_DIGEST_MISMATCH")
        check = envelope.validate(
            now_epoch=now_epoch,
            require_provider_correlation=require_provider_attestation,
            require_signature_ref=require_provider_attestation,
        )
        if not check["valid"]:
            raise ProofError(",".join(check["reasons"]))
        if not bool(semantic_verifier(envelope, evidence)):
            raise ProofError("SEMANTIC_VERIFIER_REJECTED")
        if require_provider_attestation:
            if attestation_verifier is None:
                raise ProofError("PROVIDER_ATTESTATION_VERIFIER_REQUIRED")
            if not bool(attestation_verifier(envelope, evidence)):
                raise ProofError("PROVIDER_ATTESTATION_VERIFIER_REJECTED")
        stored = self.control.register_proof(envelope)
        self.control.append_event(
            envelope.subject,
            "SOL62_PROOF_VERIFIED",
            {
                "proof_id": envelope.proof_id,
                "evidence_sha256": envelope.evidence_sha256,
                "evidence_class": envelope.evidence_class,
                "scope": envelope.scope,
            },
        )
        return stored

    def _proof_bundle(self, proof_ids: Sequence[str]) -> ProofBundleVerifier:
        return ProofBundleVerifier([self.control.fetch_proof(proof_id) for proof_id in proof_ids])

    def authorize_dispatch(
        self,
        effect_id: str,
        *,
        authority_lease_id: str | None,
        actor: str,
        source_version: str,
        now_epoch: int,
        worker: str,
        lease_epoch: int,
        fencing_token: int,
        simulation_proof_id: str | None = None,
    ) -> dict[str, Any]:
        intent_state = self.control.get_state("sol62.effect_intent", effect_id)
        if not intent_state:
            raise ConstraintError("EFFECT_INTENT_MISSING")
        intent = intent_state["value"]
        transition = self.control.get_state("sol62.transition", intent["transition_id"])["value"]
        self.control.assert_fence(
            f"transition:{intent['transition_id']}",
            worker,
            epoch=lease_epoch,
            fencing_token=fencing_token,
            now_epoch=now_epoch,
        )
        if source_version != transition["source_version"] or source_version != intent["source_version"]:
            raise ConstraintError("SOURCE_VERSION_MISMATCH")

        if bool(transition["simulation_required"]) or transition["risk_class"] in {"HIGH", "CRITICAL"}:
            if not simulation_proof_id:
                raise ProofError("SIMULATION_PROOF_REQUIRED")
            simulation = self.control.fetch_proof(simulation_proof_id)
            sim_check = simulation.validate(
                now_epoch=now_epoch,
                expected_subject=f"transition:{intent['transition_id']}",
                expected_target=transition["target"],
                expected_operation="simulate",
                expected_source_version=source_version,
            )
            if not sim_check["valid"]:
                raise ProofError("SIMULATION_PROOF_INVALID:" + ",".join(sim_check["reasons"]))

        if bool(transition["consequential"]) and not authority_lease_id:
            raise AuthorityError("ACTION_BOUND_AUTHORITY_REQUIRED")

        return self.control.authorize_effect_dispatch(
            effect_id=effect_id,
            transition_id=intent["transition_id"],
            mission_id=transition["mission_id"],
            authority_lease_id=authority_lease_id,
            action=transition["operation"],
            target=transition["target"],
            actor=actor,
            source_version=source_version,
            now_epoch=now_epoch,
            worker=worker,
            lease_epoch=lease_epoch,
            fencing_token=fencing_token,
        )

    def mark_dispatched(self, effect_id: str, *, provider_ref: str) -> dict[str, Any]:
        if not provider_ref:
            raise ConstraintError("PROVIDER_REFERENCE_REQUIRED")
        return self.control.transition_effect(
            effect_id,
            expected_state="DISPATCHING",
            next_state="DISPATCHED",
            provider_ref=provider_ref,
        )

    def observe_effect(self, effect_id: str, *, readback: Mapping[str, Any]) -> dict[str, Any]:
        intent = self.control.get_state("sol62.effect_intent", effect_id)["value"]
        expected = intent.get("expected_readback", {})
        match = self._matches(readback, expected)
        row = self.control.db.execute(
            "SELECT state FROM effects WHERE effect_id=?", (effect_id,)
        ).fetchone()
        if not row:
            raise KeyError(effect_id)
        current_state = row["state"]
        post_guard = self.guardrails.check_post_tool(
            {"effect_id": effect_id, "readback": dict(readback), "matches_expected": match}
        )
        if post_guard["decision"] != "ALLOW":
            raise ConstraintError("POST_TOOL_GUARDRAIL_" + post_guard["decision"])
        if not match:
            if current_state in {"DISPATCHING", "DISPATCHED"}:
                result = self.control.transition_effect(
                    effect_id,
                    expected_state=current_state,
                    next_state="FAILED_UNCERTAIN",
                    result=dict(readback),
                )
            else:
                result = dict(row)
            self.control.append_event(
                effect_id,
                "SOL62_READBACK_MISMATCH",
                {"effect_id": effect_id, "readback_sha256": digest(readback)},
            )
            return {"match": False, "effect": result}
        if current_state not in {"DISPATCHED", "FAILED_UNCERTAIN"}:
            raise ConstraintError("READBACK_NOT_ALLOWED_FROM_STATE:" + current_state)
        result = self.control.transition_effect(
            effect_id,
            expected_state=current_state,
            next_state="OBSERVED",
            result=dict(readback),
        )
        self.control.append_event(
            effect_id,
            "SOL62_PROVIDER_READBACK_OBSERVED",
            {"effect_id": effect_id, "readback_sha256": digest(readback)},
        )
        return {"match": True, "effect": result}

    def verify_effect_and_commit(
        self,
        effect_id: str,
        *,
        proof_ids: Sequence[str],
        now_epoch: int,
        satisfied_constraints: set[str],
    ) -> dict[str, Any]:
        intent = self.control.get_state("sol62.effect_intent", effect_id)["value"]
        transition_row = self.control.get_state("sol62.transition", intent["transition_id"])
        transition = transition_row["value"]
        missing_constraints = sorted(
            set(transition.get("constraints", ())) - set(satisfied_constraints)
        )
        proof_result = self._proof_bundle(proof_ids).verify_requirements(
            transition.get("required_proofs", ()), now_epoch=now_epoch
        )
        if missing_constraints or not proof_result["valid"]:
            raise ProofError(
                "TRANSITION_NOT_PROVEN:"
                + stable_json(
                    {"missing_constraints": missing_constraints, "proof": proof_result}
                )
            )
        effect_row = self.control.db.execute(
            "SELECT state FROM effects WHERE effect_id=?", (effect_id,)
        ).fetchone()
        if not effect_row or effect_row["state"] != "OBSERVED":
            raise ConstraintError("EFFECT_NOT_OBSERVED")

        mission_state = self.mission_state(transition["mission_id"])
        if not self._matches(mission_state["value"], transition["from_state"]):
            raise FenceError("MISSION_STATE_CHANGED_BEFORE_COMMIT")
        next_state = dict(mission_state["value"])
        next_state.update(transition["to_state"])
        output_guard = self.guardrails.check_output(
            {
                "mission_id": transition["mission_id"],
                "transition_id": intent["transition_id"],
                "prospective_state": next_state,
            }
        )
        if output_guard["decision"] != "ALLOW":
            raise ConstraintError("OUTPUT_GUARDRAIL_" + output_guard["decision"])

        committed = self.control.commit_verified_transition(
            effect_id=effect_id,
            mission_id=transition["mission_id"],
            transition_id=intent["transition_id"],
            expected_mission_version=int(mission_state["version"]),
            next_state=next_state,
            proof_ids=proof_ids,
        )
        return {
            "state": "VERIFIED",
            "mission_state": next_state,
            "event_hash": committed["event_hash"],
            "proof": proof_result,
        }

    def evaluate_mission(
        self,
        mission_id: str,
        *,
        proof_ids: Sequence[str],
        now_epoch: int,
        satisfied_constraints: set[str],
    ) -> dict[str, Any]:
        mission = self.control.get_state("sol62.mission", mission_id)
        if not mission:
            raise KeyError(mission_id)
        spec = mission["value"]
        observed = self.mission_state(mission_id)["value"]
        target_satisfied = self._matches(observed, spec["target_state"])
        missing_constraints = sorted(
            set(spec.get("constraints", ())) - set(satisfied_constraints)
        )
        proof_result = self._proof_bundle(proof_ids).verify_requirements(
            spec.get("success_proofs", ()), now_epoch=now_epoch
        )
        state = (
            "VERIFIED_REALITY"
            if target_satisfied and not missing_constraints and proof_result["valid"]
            else "OPEN"
        )
        result = {
            "mission_id": mission_id,
            "state": state,
            "target_satisfied": target_satisfied,
            "missing_constraints": missing_constraints,
            "proof": proof_result,
            "observed_state_sha256": digest(observed),
            "target_state_sha256": digest(spec["target_state"]),
        }
        result["closure_sha256"] = digest(result)
        if state == "VERIFIED_REALITY":
            self.control.append_event(
                mission_id,
                "SOL62_MISSION_REALITY_VERIFIED",
                {
                    "closure_sha256": result["closure_sha256"],
                    "proof_ids": list(proof_ids),
                },
            )
        return result

    def recover_inflight_effects(self) -> list[dict[str, Any]]:
        rows = self.control.db.execute(
            "SELECT effect_id,state FROM effects ORDER BY effect_id"
        ).fetchall()
        recovery = []
        for row in rows:
            if row["state"] in TERMINAL_EFFECT_STATES:
                continue
            decision = self.control.interrupted_effect_decision(row["effect_id"])
            recovery.append({"effect_id": row["effect_id"], **decision})
        return recovery

    def trace(
        self,
        *,
        trace_id: str,
        span_id: str,
        parent_span_id: str | None,
        kind: str,
        name: str,
        started_at_epoch_ms: int,
        duration_ms: float,
        status: str,
        attributes: Mapping[str, Any],
    ) -> dict[str, Any]:
        envelope = TraceEnvelope(
            trace_id,
            span_id,
            parent_span_id,
            kind,
            name,
            started_at_epoch_ms,
            duration_ms,
            status,
            attributes,
        )
        safe = envelope.otel_attributes()
        self.control.append_event(trace_id, "SOL62_TRACE_EMITTED", {"attributes": safe})
        return safe

    def record_value(
        self,
        *,
        event_id: str,
        mission_id: str,
        accepted_outcome: bool,
        owner_interventions: int,
        minutes_saved: float,
        cost: float,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.control.record_value(
            event_id=event_id,
            mission_id=mission_id,
            accepted_outcome=accepted_outcome,
            owner_interventions=owner_interventions,
            minutes_saved=minutes_saved,
            cost=cost,
            metadata=metadata,
        )
        return self.control.value_summary(mission_id)

    def verify_integrity(self) -> dict[str, Any]:
        return {
            "version": SOL62_VERSION,
            "event_chain_valid": self.control.verify_event_chain(),
            "inflight_effects": self.recover_inflight_effects(),
        }
