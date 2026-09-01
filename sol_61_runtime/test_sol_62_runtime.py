from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

try:
    from .sol_62_frontier_primitives import (
        AuthorityError,
        AuthorityLease,
        ConstraintError,
        FenceError,
        GatewayPolicy,
        GuardrailPipeline,
        GuardrailResult,
        IdempotencyCollision,
        ProofEnvelope,
        ProofError,
        WorkloadIdentityPolicy,
    )
    from .sol_62_runtime import ExecutionIntent, MissionSpec, Sol62Runtime, TransitionSpec
except ImportError:
    from sol_62_frontier_primitives import (
        AuthorityError,
        AuthorityLease,
        ConstraintError,
        FenceError,
        GatewayPolicy,
        GuardrailPipeline,
        GuardrailResult,
        IdempotencyCollision,
        ProofEnvelope,
        ProofError,
        WorkloadIdentityPolicy,
    )
    from sol_62_runtime import ExecutionIntent, MissionSpec, Sol62Runtime, TransitionSpec


class Sol62RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.now = int(time.time())
        self.gateway = GatewayPolicy("sol-gateway", "sol-6.2")
        self.identity = WorkloadIdentityPolicy(
            allowed_issuers={"https://token.actions.githubusercontent.com"},
            audience="sol-runtime",
            subject_prefix="repo:mosianekk-lang/Federation-Omega:",
            max_ttl_seconds=600,
        )
        self.rt = Sol62Runtime(self.root, gateway_policy=self.gateway, identity_policy=self.identity)

    def tearDown(self):
        self.rt.close()
        self.tmp.cleanup()

    def claims(self, **changes):
        body = {
            "iss": "https://token.actions.githubusercontent.com",
            "aud": "sol-runtime",
            "sub": "repo:mosianekk-lang/Federation-Omega:ref:refs/heads/main",
            "iat": self.now - 10,
            "exp": self.now + 300,
            "credential_type": "oidc",
        }
        body.update(changes)
        return body

    def gateway_request(self, **changes):
        body = {
            "runtime_id": "sol-6.2",
            "via_gateway": "sol-gateway",
            "authenticated_principal": "spiffe://sol/worker",
            "policy_version": "6.2",
        }
        body.update(changes)
        return body

    def proof(self, proof_id, *, subject, target, operation, evidence, source_version="abc", evidence_class="PROVIDER_NATIVE"):
        return ProofEnvelope.from_evidence(
            proof_id=proof_id,
            subject=subject,
            target=target,
            operation=operation,
            issuer="github",
            source_version=source_version,
            evidence=evidence,
            max_age_seconds=600,
            provider_correlation_id="run-1",
            signature_ref="sig-1",
            evidence_class=evidence_class,
            scope="repo",
        )

    def register_mission_transition(self, *, consequential=True, simulation_required=True, required_proofs=(), success_proofs=()):
        self.rt.register_mission(
            MissionSpec(
                "m1",
                "Publish verified artifact",
                {"artifact": "MISSING", "approved": False},
                {"artifact": "PUBLISHED", "approved": True},
                tuple(success_proofs),
            )
        )
        self.rt.register_transition(
            TransitionSpec(
                transition_id="t1",
                mission_id="m1",
                operation="publish",
                target="repo/main",
                from_state={"artifact": "MISSING"},
                to_state={"artifact": "PUBLISHED", "approved": True},
                required_proofs=tuple(required_proofs),
                consequential=consequential,
                simulation_required=simulation_required,
                source_version="abc",
                risk_class="HIGH" if simulation_required else "LOW",
                conflict_domains=("repo",),
            )
        )

    def prepare(self, *, effect_id="e1", payload=None, idem="idem-1"):
        return self.rt.prepare_execution(
            ExecutionIntent(
                effect_id,
                "t1",
                "github",
                payload or {"artifact": "candidate"},
                "AT_MOST_ONCE",
                idem,
                "worker-1",
                "abc",
                {"status": "ok"},
                True,
            ),
            gateway_request=self.gateway_request(),
            identity_claims=self.claims(),
            now_epoch=self.now,
        )

    def simulation(self, proof_id="sim"):
        evidence = {"safe": True}
        proof = self.proof(
            proof_id,
            subject="transition:t1",
            target="repo/main",
            operation="simulate",
            evidence=evidence,
            evidence_class="DETERMINISTIC",
        )
        self.rt.register_verified_proof(
            proof,
            evidence,
            semantic_verifier=lambda p, e: e["safe"] is True,
            now_epoch=self.now,
        )
        return proof_id

    def authorize(self, simulation_proof_id="sim"):
        lease = AuthorityLease(
            "authority-e1", "publish", "repo/main", "worker-1", "abc",
            self.now - 10, self.now + 300, "nonce-e1", 1,
        )
        self.rt.create_authority_lease(lease)
        fence = self.rt.acquire_execution_fence("t1", "worker-1", ttl_seconds=120, now_epoch=self.now)
        return self.rt.authorize_dispatch(
            "e1",
            authority_lease_id=lease.lease_id,
            actor="worker-1",
            source_version="abc",
            now_epoch=self.now,
            worker="worker-1",
            lease_epoch=fence["epoch"],
            fencing_token=fence["fencing_token"],
            simulation_proof_id=simulation_proof_id,
        )

    def test_schema_versions_are_monotonic(self):
        body = {"fields": ["x"]}
        self.rt.control.register_schema("custom", 2, body)
        with self.assertRaises(ConstraintError):
            self.rt.control.register_schema("custom", 1, body)
        self.assertEqual(self.rt.control.register_schema("custom", 2, body)["version"], 2)

    def test_gateway_and_identity_fail_closed(self):
        self.register_mission_transition(consequential=False, simulation_required=False)
        intent = ExecutionIntent("e1", "t1", "github", {"x": 1}, "IDEMPOTENT", "idem", "worker-1", "abc", {"status": "ok"}, False)
        with self.assertRaises(ConstraintError):
            self.rt.prepare_execution(intent, gateway_request=self.gateway_request(via_gateway="wrong"), identity_claims=self.claims(), now_epoch=self.now)
        with self.assertRaises(ConstraintError):
            self.rt.prepare_execution(intent, gateway_request=self.gateway_request(), identity_claims=self.claims(credential_type="static_key"), now_epoch=self.now)

    def test_proof_requires_digest_semantics_and_attestation(self):
        evidence = {"ok": True}
        proof = self.proof("p1", subject="transition:t1", target="repo/main", operation="publish", evidence=evidence)
        with self.assertRaises(ProofError):
            self.rt.register_verified_proof(proof, {"ok": False}, semantic_verifier=lambda p, e: True, now_epoch=self.now)
        with self.assertRaises(ProofError):
            self.rt.register_verified_proof(proof, evidence, semantic_verifier=lambda p, e: False, now_epoch=self.now)
        with self.assertRaises(ProofError):
            self.rt.register_verified_proof(proof, evidence, semantic_verifier=lambda p, e: True, now_epoch=self.now, require_provider_attestation=True)
        stored = self.rt.register_verified_proof(
            proof,
            evidence,
            semantic_verifier=lambda p, e: e.get("ok") is True,
            now_epoch=self.now,
            require_provider_attestation=True,
            attestation_verifier=lambda p, e: p.signature_ref.startswith("sig-"),
        )
        self.assertEqual(stored["proof_id"], "p1")

    def test_end_to_end_verified_reality_closure(self):
        requirement = {
            "proof_id": "provider-proof",
            "subject": "transition:t1",
            "target": "repo/main",
            "operation": "publish",
            "source_version": "abc",
            "accepted_evidence_classes": ["PROVIDER_NATIVE"],
            "require_provider_correlation": True,
            "require_signature_ref": True,
        }
        self.register_mission_transition(required_proofs=(requirement,), success_proofs=(requirement,))
        self.simulation("sim")
        self.prepare()
        self.authorize("sim")
        self.rt.mark_dispatched("e1", provider_ref="provider-run-1")
        self.assertTrue(self.rt.observe_effect("e1", readback={"status": "ok", "extra": "readback"})["match"])
        evidence = {"status": "ok", "provider_ref": "provider-run-1"}
        proof = self.proof("provider-proof", subject="transition:t1", target="repo/main", operation="publish", evidence=evidence)
        self.rt.register_verified_proof(
            proof,
            evidence,
            semantic_verifier=lambda p, e: e["status"] == "ok",
            now_epoch=self.now,
            require_provider_attestation=True,
            attestation_verifier=lambda p, e: p.signature_ref.startswith("sig-"),
        )
        committed = self.rt.verify_effect_and_commit("e1", proof_ids=["provider-proof"], now_epoch=self.now, satisfied_constraints=set())
        self.assertEqual(committed["state"], "VERIFIED")
        closure = self.rt.evaluate_mission("m1", proof_ids=["provider-proof"], now_epoch=self.now, satisfied_constraints=set())
        self.assertEqual(closure["state"], "VERIFIED_REALITY")
        self.assertTrue(self.rt.verify_integrity()["event_chain_valid"])

    def test_mission_does_not_close_without_observed_target(self):
        requirement = {"proof_id": "p1", "subject": "transition:t1", "target": "repo/main", "operation": "publish", "source_version": "abc"}
        self.register_mission_transition(consequential=False, simulation_required=False, success_proofs=(requirement,))
        evidence = {"ok": True}
        proof = self.proof("p1", subject="transition:t1", target="repo/main", operation="publish", evidence=evidence)
        self.rt.register_verified_proof(proof, evidence, semantic_verifier=lambda p, e: True, now_epoch=self.now)
        closure = self.rt.evaluate_mission("m1", proof_ids=["p1"], now_epoch=self.now, satisfied_constraints=set())
        self.assertEqual(closure["state"], "OPEN")
        self.assertFalse(closure["target_satisfied"])

    def test_one_use_authority_cannot_be_replayed(self):
        self.register_mission_transition()
        self.simulation("sim")
        self.prepare()
        self.authorize("sim")
        with self.assertRaises(AuthorityError):
            self.rt.control.consume_authority_lease("authority-e1", action="publish", target="repo/main", actor="worker-1", source_version="abc", now_epoch=self.now)

    def test_idempotency_collision_and_interruption_semantics(self):
        self.register_mission_transition()
        self.simulation("sim")
        self.prepare(payload={"x": 1}, idem="same-key")
        with self.assertRaises(IdempotencyCollision):
            self.rt.prepare_execution(
                ExecutionIntent("e2", "t1", "github", {"x": 2}, "AT_MOST_ONCE", "same-key", "worker-1", "abc", {"status": "ok"}, True),
                gateway_request=self.gateway_request(), identity_claims=self.claims(), now_epoch=self.now,
            )
        self.authorize("sim")
        self.rt.mark_dispatched("e1", provider_ref="provider-run")
        self.assertEqual(self.rt.recover_inflight_effects()[0]["action"], "PROBE_PROVIDER_BEFORE_RETRY")

    def test_atomic_commit_fails_closed_on_state_race(self):
        requirement = {"proof_id": "p1", "subject": "transition:t1", "target": "repo/main", "operation": "publish", "source_version": "abc"}
        self.register_mission_transition(consequential=False, simulation_required=False, required_proofs=(requirement,))
        self.prepare()
        fence = self.rt.acquire_execution_fence("t1", "worker-1", ttl_seconds=120, now_epoch=self.now)
        self.rt.authorize_dispatch("e1", authority_lease_id=None, actor="worker-1", source_version="abc", now_epoch=self.now, worker="worker-1", lease_epoch=fence["epoch"], fencing_token=fence["fencing_token"])
        self.rt.mark_dispatched("e1", provider_ref="provider-run")
        self.rt.observe_effect("e1", readback={"status": "ok"})
        evidence = {"ok": True}
        proof = self.proof("p1", subject="transition:t1", target="repo/main", operation="publish", evidence=evidence)
        self.rt.register_verified_proof(proof, evidence, semantic_verifier=lambda p, e: True, now_epoch=self.now)
        original = self.rt.control.commit_verified_transition
        def racing_commit(**kwargs):
            state = self.rt.mission_state("m1")
            mutated = dict(state["value"])
            mutated["external_change"] = True
            self.rt.control.cas_put("sol62.mission_state", "m1", mutated, expected_version=state["version"])
            return original(**kwargs)
        self.rt.control.commit_verified_transition = racing_commit
        with self.assertRaises(FenceError):
            self.rt.verify_effect_and_commit("e1", proof_ids=["p1"], now_epoch=self.now, satisfied_constraints=set())
        self.assertEqual(self.rt.control.db.execute("SELECT state FROM effects WHERE effect_id='e1'").fetchone()["state"], "OBSERVED")

    def test_output_guardrail_rejects_before_commit(self):
        guards = GuardrailPipeline()
        guards.output_guards.append(lambda value: GuardrailResult("deny", "REJECT", "test"))
        other = Sol62Runtime(self.root / "guarded", gateway_policy=self.gateway, identity_policy=self.identity, guardrails=guards)
        try:
            other.register_mission(MissionSpec("m2", "guard", {"x": 0}, {"x": 1}))
            other.register_transition(TransitionSpec("t2", "m2", "publish", "repo/main", {"x": 0}, {"x": 1}, source_version="abc"))
            other.prepare_execution(ExecutionIntent("e2", "t2", "github", {"x": 1}, "IDEMPOTENT", "idem2", "worker-1", "abc", {"status": "ok"}, False), gateway_request=self.gateway_request(), identity_claims=self.claims(), now_epoch=self.now)
            fence = other.acquire_execution_fence("t2", "worker-1", ttl_seconds=120, now_epoch=self.now)
            other.authorize_dispatch("e2", authority_lease_id=None, actor="worker-1", source_version="abc", now_epoch=self.now, worker="worker-1", lease_epoch=fence["epoch"], fencing_token=fence["fencing_token"])
            other.mark_dispatched("e2", provider_ref="provider")
            other.observe_effect("e2", readback={"status": "ok"})
            with self.assertRaises(ConstraintError):
                other.verify_effect_and_commit("e2", proof_ids=[], now_epoch=self.now, satisfied_constraints=set())
            self.assertEqual(other.control.db.execute("SELECT state FROM effects WHERE effect_id='e2'").fetchone()["state"], "OBSERVED")
            self.assertEqual(other.mission_state("m2")["value"]["x"], 0)
        finally:
            other.close()

    def test_dependency_cycle_fails_closed(self):
        self.rt.register_mission(MissionSpec("cycle", "cycle", {"x": 0}, {"x": 1}))
        self.rt.register_transition(TransitionSpec("a", "cycle", "x", "local", {"x": 0}, {"x": 1}, dependencies=("b",)))
        self.rt.register_transition(TransitionSpec("b", "cycle", "x", "local", {"x": 0}, {"x": 1}, dependencies=("a",)))
        with self.assertRaises(ConstraintError):
            self.rt.ready_transitions("cycle", satisfied_constraints=set())


if __name__ == "__main__":
    unittest.main()
