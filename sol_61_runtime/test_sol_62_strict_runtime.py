from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

try:
    from .sol_62 import (
        AuthorityError,
        AuthorityLease,
        ConstraintError,
        ExecutionIntent,
        GatewayPolicy,
        MissionSpec,
        ProofEnvelope,
        ProofError,
        Sol62Runtime,
        TransitionSpec,
        WorkloadIdentityPolicy,
        digest,
    )
except ImportError:
    from sol_62 import (
        AuthorityError,
        AuthorityLease,
        ConstraintError,
        ExecutionIntent,
        GatewayPolicy,
        MissionSpec,
        ProofEnvelope,
        ProofError,
        Sol62Runtime,
        TransitionSpec,
        WorkloadIdentityPolicy,
        digest,
    )


class Sol62StrictRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.now = int(time.time())
        self.rt = Sol62Runtime(
            Path(self.tmp.name),
            gateway_policy=GatewayPolicy("sol-gateway", "sol-6.2"),
            identity_policy=WorkloadIdentityPolicy(
                allowed_issuers={"https://token.actions.githubusercontent.com"},
                audience="sol-runtime",
                subject_prefix="repo:mosianekk-lang/Federation-Omega:",
                max_ttl_seconds=600,
            ),
        )

    def tearDown(self) -> None:
        self.rt.close()
        self.tmp.cleanup()

    def claims(self) -> dict:
        return {
            "iss": "https://token.actions.githubusercontent.com",
            "aud": "sol-runtime",
            "sub": "repo:mosianekk-lang/Federation-Omega:ref:refs/heads/main",
            "iat": self.now - 10,
            "exp": self.now + 300,
            "credential_type": "oidc",
        }

    def gateway(self) -> dict:
        return {
            "runtime_id": "sol-6.2",
            "via_gateway": "sol-gateway",
            "authenticated_principal": "spiffe://sol/worker-1",
            "policy_version": "6.2",
        }

    def mission(self, *, consequential: bool = False, success_proofs=(), required_proofs=()) -> None:
        self.rt.register_mission(
            MissionSpec(
                "m1",
                "Reach independently verified provider state",
                {"state": "CANDIDATE"},
                {"state": "PUBLISHED"},
                tuple(success_proofs),
            )
        )
        self.rt.register_transition(
            TransitionSpec(
                "t1",
                "m1",
                "publish",
                "repo/main",
                {"state": "CANDIDATE"},
                {"state": "PUBLISHED"},
                required_proofs=tuple(required_proofs),
                consequential=consequential,
                source_version="abc",
            )
        )

    def intent(self, *, effect_id="e1", expected=None, consequential=False) -> ExecutionIntent:
        return ExecutionIntent(
            effect_id,
            "t1",
            "github",
            {"artifact": "candidate"},
            "AT_MOST_ONCE" if consequential else "IDEMPOTENT",
            f"idem-{effect_id}",
            "worker-1",
            "abc",
            {"status": "ok"} if expected is None else expected,
            consequential,
        )

    def prepare(self, *, consequential=False) -> None:
        self.rt.prepare_execution(
            self.intent(consequential=consequential),
            gateway_request=self.gateway(),
            identity_claims=self.claims(),
            now_epoch=self.now,
        )

    def fence(self):
        return self.rt.acquire_execution_fence("t1", "worker-1", ttl_seconds=120, now_epoch=self.now)

    def test_explicit_readback_contract_is_mandatory(self) -> None:
        self.mission()
        with self.assertRaises(ConstraintError):
            self.rt.prepare_execution(
                self.intent(expected={}),
                gateway_request=self.gateway(),
                identity_claims=self.claims(),
                now_epoch=self.now,
            )

    def test_dispatch_actor_must_equal_durable_intent_actor(self) -> None:
        self.mission()
        self.prepare()
        fence = self.fence()
        with self.assertRaises(AuthorityError):
            self.rt.authorize_dispatch(
                "e1",
                authority_lease_id=None,
                actor="different-worker",
                source_version="abc",
                now_epoch=self.now,
                worker="worker-1",
                lease_epoch=fence["epoch"],
                fencing_token=fence["fencing_token"],
            )

    def test_provider_native_proof_automatically_requires_attestation_verifier(self) -> None:
        evidence = {"status": "ok"}
        proof = ProofEnvelope.from_evidence(
            proof_id="provider-proof",
            subject="transition:t1",
            target="repo/main",
            operation="publish",
            issuer="github",
            source_version="abc",
            evidence=evidence,
            provider_correlation_id="run-1",
            signature_ref="sig-1",
            evidence_class="PROVIDER_NATIVE",
        )
        with self.assertRaises(ProofError):
            self.rt.register_verified_proof(
                proof,
                evidence,
                semantic_verifier=lambda p, e: True,
                now_epoch=self.now,
            )
        stored = self.rt.register_verified_proof(
            proof,
            evidence,
            semantic_verifier=lambda p, e: True,
            now_epoch=self.now,
            attestation_verifier=lambda p, e: p.signature_ref == "sig-1",
        )
        self.assertEqual(stored["proof_id"], "provider-proof")

    def test_consequential_proof_must_bind_to_actual_effect_and_readback(self) -> None:
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
        self.mission(consequential=True, required_proofs=(requirement,))
        self.prepare(consequential=True)
        lease = AuthorityLease(
            "lease-1",
            "publish",
            "repo/main",
            "worker-1",
            "abc",
            self.now - 10,
            self.now + 300,
            "nonce-1",
            1,
        )
        self.rt.create_authority_lease(lease)
        fence = self.fence()
        self.rt.authorize_dispatch(
            "e1",
            authority_lease_id="lease-1",
            actor="worker-1",
            source_version="abc",
            now_epoch=self.now,
            worker="worker-1",
            lease_epoch=fence["epoch"],
            fencing_token=fence["fencing_token"],
        )
        self.rt.mark_dispatched("e1", provider_ref="provider-run-1")
        readback = {"status": "ok", "provider_state": "published"}
        self.rt.observe_effect("e1", readback=readback)
        evidence = {"status": "ok", "provider_state": "published"}
        wrong = ProofEnvelope.from_evidence(
            proof_id="provider-proof",
            subject="transition:t1",
            target="repo/main",
            operation="publish",
            issuer="github",
            source_version="abc",
            evidence=evidence,
            provider_correlation_id="different-provider-run",
            signature_ref="sig-1",
            evidence_class="PROVIDER_NATIVE",
            attributes={"effect_id": "e1", "readback_sha256": digest(readback)},
        )
        self.rt.register_verified_proof(
            wrong,
            evidence,
            semantic_verifier=lambda p, e: True,
            now_epoch=self.now,
            attestation_verifier=lambda p, e: True,
        )
        with self.assertRaises(ProofError):
            self.rt.verify_effect_and_commit(
                "e1",
                proof_ids=["provider-proof"],
                now_epoch=self.now,
                satisfied_constraints=set(),
            )

    def test_verified_reality_freezes_execution_and_closure_is_idempotent(self) -> None:
        requirement = {
            "proof_id": "p1",
            "subject": "transition:t1",
            "target": "repo/main",
            "operation": "publish",
            "source_version": "abc",
            "accepted_evidence_classes": ["DETERMINISTIC"],
        }
        self.mission(required_proofs=(requirement,), success_proofs=(requirement,))
        self.rt.register_transition(
            TransitionSpec(
                "t2",
                "m1",
                "mutate-again",
                "repo/main",
                {"state": "PUBLISHED"},
                {"state": "MUTATED_AGAIN"},
                source_version="abc",
            )
        )
        self.prepare()
        fence = self.fence()
        self.rt.authorize_dispatch(
            "e1",
            authority_lease_id=None,
            actor="worker-1",
            source_version="abc",
            now_epoch=self.now,
            worker="worker-1",
            lease_epoch=fence["epoch"],
            fencing_token=fence["fencing_token"],
        )
        self.rt.mark_dispatched("e1", provider_ref="provider-run-1")
        self.rt.observe_effect("e1", readback={"status": "ok"})
        evidence = {"ok": True}
        proof = ProofEnvelope.from_evidence(
            proof_id="p1",
            subject="transition:t1",
            target="repo/main",
            operation="publish",
            issuer="deterministic-court",
            source_version="abc",
            evidence=evidence,
        )
        self.rt.register_verified_proof(
            proof,
            evidence,
            semantic_verifier=lambda p, e: True,
            now_epoch=self.now,
        )
        result = self.rt.verify_effect_and_commit(
            "e1",
            proof_ids=["p1"],
            now_epoch=self.now,
            satisfied_constraints=set(),
        )
        self.assertEqual(result["mission_closure"]["state"], "VERIFIED_REALITY")
        self.assertEqual(self.rt.ready_transitions("m1", satisfied_constraints=set()), [])
        before = self.rt.control.db.execute(
            "SELECT COUNT(*) AS n FROM events WHERE kind='SOL62_MISSION_REALITY_VERIFIED'"
        ).fetchone()["n"]
        repeated = self.rt.evaluate_mission(
            "m1", proof_ids=["p1"], now_epoch=self.now, satisfied_constraints=set()
        )
        after = self.rt.control.db.execute(
            "SELECT COUNT(*) AS n FROM events WHERE kind='SOL62_MISSION_REALITY_VERIFIED'"
        ).fetchone()["n"]
        self.assertEqual(repeated["closure_sha256"], result["mission_closure"]["closure_sha256"])
        self.assertEqual(before, after)
        with self.assertRaises(ConstraintError):
            self.rt.prepare_execution(
                ExecutionIntent(
                    "e2", "t2", "github", {"x": 2}, "IDEMPOTENT", "idem-e2",
                    "worker-1", "abc", {"status": "ok"}, False,
                ),
                gateway_request=self.gateway(),
                identity_claims=self.claims(),
                now_epoch=self.now,
            )


if __name__ == "__main__":
    unittest.main()
