from __future__ import annotations

import dataclasses
import json
from typing import Any, Callable, Mapping, Sequence

try:
    from .sol_62_frontier_primitives import (
        AuthorityError,
        ConstraintError,
        ProofEnvelope,
        ProofError,
        digest,
        stable_json,
        utc_now,
    )
    from .sol_62_runtime import ExecutionIntent, MissionSpec, Sol62Runtime as _BaseSol62Runtime, TransitionSpec
except ImportError:
    from sol_62_frontier_primitives import (
        AuthorityError,
        ConstraintError,
        ProofEnvelope,
        ProofError,
        digest,
        stable_json,
        utc_now,
    )
    from sol_62_runtime import ExecutionIntent, MissionSpec, Sol62Runtime as _BaseSol62Runtime, TransitionSpec


PROVIDER_EVIDENCE_CLASSES = frozenset(
    {"PROVIDER_NATIVE", "PROVIDER_LIVE", "PROVIDER_READBACK", "PROVIDER_ATTESTED"}
)


class Sol62StrictRuntime(_BaseSol62Runtime):
    """Canonical SOL 6.2 facade with cross-object proof and closure binding.

    The base runtime supplies transactional primitives. This facade closes the
    remaining semantic gaps: provider proof must bind to the effect actually
    observed, execution identity must bind to durable intent, readback must be
    explicit, and a verified mission becomes immutable for execution purposes.
    """

    def _mission_status(self, mission_id: str) -> dict[str, Any] | None:
        return self.control.get_state("sol62.mission_status", mission_id)

    def _assert_mission_open(self, mission_id: str) -> None:
        status = self._mission_status(mission_id)
        if status and status["value"].get("status") == "VERIFIED_REALITY":
            raise ConstraintError("MISSION_ALREADY_VERIFIED_REALITY")

    def register_mission(self, spec: MissionSpec) -> dict[str, Any]:
        existing = self.control.get_state("sol62.mission", spec.mission_id)
        status = self._mission_status(spec.mission_id)
        if status and status["value"].get("status") == "VERIFIED_REALITY" and existing:
            if digest(existing["value"]) != digest(dataclasses.asdict(spec)):
                raise ConstraintError("VERIFIED_MISSION_IS_IMMUTABLE")
            return existing
        result = super().register_mission(spec)
        if self._mission_status(spec.mission_id) is None:
            self._put_once(
                "sol62.mission_status",
                spec.mission_id,
                {"status": "OPEN", "closure_sha256": None},
            )
        return result

    def register_transition(self, spec: TransitionSpec) -> dict[str, Any]:
        self._assert_mission_open(spec.mission_id)
        return super().register_transition(spec)

    def supersede_transition(self, failed_transition_id: str, replacement: TransitionSpec) -> dict[str, Any]:
        self._assert_mission_open(replacement.mission_id)
        return super().supersede_transition(failed_transition_id, replacement)

    def ready_transitions(
        self,
        mission_id: str,
        *,
        satisfied_constraints: set[str],
        capacity: int | None = None,
    ) -> list[str]:
        status = self._mission_status(mission_id)
        if status and status["value"].get("status") == "VERIFIED_REALITY":
            return []
        return super().ready_transitions(
            mission_id,
            satisfied_constraints=satisfied_constraints,
            capacity=capacity,
        )

    def prepare_execution(
        self,
        intent: ExecutionIntent,
        *,
        gateway_request: Mapping[str, Any],
        identity_claims: Mapping[str, Any],
        now_epoch: int,
    ) -> dict[str, Any]:
        transition = self.control.get_state("sol62.transition", intent.transition_id)
        if not transition:
            raise ConstraintError("TRANSITION_NOT_REGISTERED")
        self._assert_mission_open(transition["value"]["mission_id"])
        if not intent.expected_readback:
            raise ConstraintError("EXPLICIT_EXPECTED_READBACK_REQUIRED")
        return super().prepare_execution(
            intent,
            gateway_request=gateway_request,
            identity_claims=identity_claims,
            now_epoch=now_epoch,
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
        provider_native = envelope.evidence_class in PROVIDER_EVIDENCE_CLASSES
        return super().register_verified_proof(
            envelope,
            evidence,
            semantic_verifier=semantic_verifier,
            now_epoch=now_epoch,
            require_provider_attestation=require_provider_attestation or provider_native,
            attestation_verifier=attestation_verifier,
        )

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
        if actor != intent.get("actor"):
            raise AuthorityError("EXECUTION_ACTOR_DIFFERS_FROM_DURABLE_INTENT")
        transition = self.control.get_state("sol62.transition", intent["transition_id"])["value"]
        self._assert_mission_open(transition["mission_id"])
        return super().authorize_dispatch(
            effect_id,
            authority_lease_id=authority_lease_id,
            actor=actor,
            source_version=source_version,
            now_epoch=now_epoch,
            worker=worker,
            lease_epoch=lease_epoch,
            fencing_token=fencing_token,
            simulation_proof_id=simulation_proof_id,
        )

    def _validate_effect_bound_provider_proofs(
        self,
        effect_id: str,
        *,
        proof_ids: Sequence[str],
    ) -> None:
        intent = self.control.get_state("sol62.effect_intent", effect_id)["value"]
        transition = self.control.get_state("sol62.transition", intent["transition_id"])["value"]
        effect = self.control.db.execute(
            "SELECT provider_ref,result_json FROM effects WHERE effect_id=?", (effect_id,)
        ).fetchone()
        if not effect:
            raise KeyError(effect_id)
        provider_ref = str(effect["provider_ref"] or "")
        observed = json.loads(effect["result_json"]) if effect["result_json"] else {}
        readback_sha256 = digest(observed)
        bound_provider_proofs = 0
        for proof_id in proof_ids:
            envelope = self.control.fetch_proof(proof_id)
            if envelope.evidence_class not in PROVIDER_EVIDENCE_CLASSES:
                continue
            bound_provider_proofs += 1
            reasons: list[str] = []
            if not provider_ref:
                reasons.append("EFFECT_PROVIDER_REFERENCE_MISSING")
            if envelope.provider_correlation_id != provider_ref:
                reasons.append("PROVIDER_CORRELATION_NOT_BOUND_TO_EFFECT")
            if envelope.attributes.get("effect_id") != effect_id:
                reasons.append("PROOF_EFFECT_ID_MISMATCH")
            if envelope.attributes.get("readback_sha256") != readback_sha256:
                reasons.append("PROOF_READBACK_DIGEST_MISMATCH")
            if reasons:
                raise ProofError("EFFECT_BOUND_PROVIDER_PROOF_INVALID:" + ",".join(reasons))
        if bool(transition.get("consequential")) and bound_provider_proofs == 0:
            raise ProofError("CONSEQUENTIAL_EFFECT_REQUIRES_EFFECT_BOUND_PROVIDER_PROOF")

    def verify_effect_and_commit(
        self,
        effect_id: str,
        *,
        proof_ids: Sequence[str],
        now_epoch: int,
        satisfied_constraints: set[str],
    ) -> dict[str, Any]:
        intent = self.control.get_state("sol62.effect_intent", effect_id)["value"]
        transition = self.control.get_state("sol62.transition", intent["transition_id"])["value"]
        self._assert_mission_open(transition["mission_id"])
        self._validate_effect_bound_provider_proofs(effect_id, proof_ids=proof_ids)
        result = super().verify_effect_and_commit(
            effect_id,
            proof_ids=proof_ids,
            now_epoch=now_epoch,
            satisfied_constraints=satisfied_constraints,
        )
        result["mission_closure"] = self.evaluate_mission(
            transition["mission_id"],
            proof_ids=proof_ids,
            now_epoch=now_epoch,
            satisfied_constraints=satisfied_constraints,
        )
        return result

    def evaluate_mission(
        self,
        mission_id: str,
        *,
        proof_ids: Sequence[str],
        now_epoch: int,
        satisfied_constraints: set[str],
    ) -> dict[str, Any]:
        stored_closure = self.control.get_state("sol62.mission_closure", mission_id)
        if stored_closure:
            return dict(stored_closure["value"])

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
        if state != "VERIFIED_REALITY":
            return result

        with self.control.tx() as db:
            status = db.execute(
                "SELECT version,value_json FROM state WHERE namespace='sol62.mission_status' AND item_key=?",
                (mission_id,),
            ).fetchone()
            if status:
                status_value = json.loads(status["value_json"])
                if status_value.get("status") == "VERIFIED_REALITY":
                    existing = db.execute(
                        "SELECT value_json FROM state WHERE namespace='sol62.mission_closure' AND item_key=?",
                        (mission_id,),
                    ).fetchone()
                    return json.loads(existing["value_json"]) if existing else result
                status_version = int(status["version"])
            else:
                status_version = 0

            created_at = utc_now()
            if status_version == 0:
                db.execute(
                    "INSERT INTO state(namespace,item_key,value_json,version,updated_at) VALUES('sol62.mission_status',?,?,1,?)",
                    (mission_id, stable_json({"status": "VERIFIED_REALITY", "closure_sha256": result["closure_sha256"]}), created_at),
                )
            else:
                db.execute(
                    "UPDATE state SET value_json=?,version=?,updated_at=? WHERE namespace='sol62.mission_status' AND item_key=?",
                    (
                        stable_json({"status": "VERIFIED_REALITY", "closure_sha256": result["closure_sha256"]}),
                        status_version + 1,
                        created_at,
                        mission_id,
                    ),
                )
            db.execute(
                "INSERT INTO state(namespace,item_key,value_json,version,updated_at) VALUES('sol62.mission_closure',?,?,1,?)",
                (mission_id, stable_json(result), created_at),
            )

            previous = db.execute("SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
            previous_hash = previous["event_hash"] if previous else "GENESIS"
            next_seq = int(db.execute("SELECT COALESCE(MAX(seq),0)+1 AS n FROM events").fetchone()["n"])
            event_body = {
                "event_id": f"evt-{next_seq:012d}",
                "aggregate": mission_id,
                "kind": "SOL62_MISSION_REALITY_VERIFIED",
                "payload": {"closure_sha256": result["closure_sha256"], "proof_ids": list(proof_ids)},
                "previous_hash": previous_hash,
                "created_at": created_at,
            }
            event_hash = digest(event_body)
            db.execute(
                "INSERT INTO events(event_id,aggregate,kind,payload_json,previous_hash,event_hash,created_at) VALUES(?,?,?,?,?,?,?)",
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
        return result
