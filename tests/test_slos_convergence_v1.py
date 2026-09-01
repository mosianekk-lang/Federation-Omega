from __future__ import annotations

import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from superior_logic.change_impact import ChangeImpactCompiler, ImpactDecision, MissionSnapshot
from superior_logic.convergence import (
    AuthorityDomain,
    AuthorityOwner,
    ConstitutionalConflict,
    ConstitutionalConvergence,
    DEFAULT_AUTHORITY_GRAPH,
)
from superior_logic.evidence_distillation import EvidenceDistiller
from superior_logic.provider_attestations import (
    AttestationError,
    DynamicProviderRouter,
    NoFreshProviderRoute,
    ProviderAttestation,
    ProviderAttestationStore,
    ProviderRoutePolicy,
)
from superior_logic.runtime import SuperiorLogicRuntime
from superior_logic.secure_service import create_secure_app
from superior_logic.security import AuthMode, SlosAuthPolicy, sign_hmac_assertion
from superior_logic.trace import SpanKind, TraceBuffer, TraceSpan


class SlosConvergenceTests(unittest.TestCase):
    def test_single_authority_graph_binds_sol_as_kernel(self):
        convergence = ConstitutionalConvergence()
        receipt = convergence.architecture_receipt()
        self.assertEqual("SLOS", receipt["mission_semantic_owner"])
        self.assertEqual("SOL_6_2_KERNEL", receipt["transaction_kernel_owner"])
        self.assertEqual("SOVARA", receipt["provider_effect_owner"])
        self.assertFalse(receipt["duplicate_sovereign_mission_plane"])

    def test_duplicate_constitutional_owner_is_rejected(self):
        conflicting = DEFAULT_AUTHORITY_GRAPH + (
            AuthorityOwner(AuthorityDomain.MISSION_SEMANTICS, "SOL_6_2_KERNEL", "invalid duplicate"),
        )
        with self.assertRaises(ConstitutionalConflict):
            ConstitutionalConvergence(conflicting)

    def test_slos_mission_projects_into_sol_without_changing_identity(self):
        convergence = ConstitutionalConvergence()
        mission = convergence.compile_mission(
            mission_id="mission-1",
            objective="reach verified state",
            source_version="abc123",
            initial_state={"state": "OPEN"},
            target_state={"state": "VERIFIED"},
            constraints=("NO_SECRET_VALUES",),
        )
        projected = convergence.project_mission_to_kernel(mission)
        self.assertEqual(mission.mission_id, projected.mission_id)
        self.assertEqual(mission.objective, projected.objective)
        self.assertEqual({"state": "VERIFIED"}, dict(projected.target_state))


class SlosSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.runtime = SuperiorLogicRuntime(Path(self.tmp.name) / "secure.db")

    def tearDown(self):
        self.runtime.close()
        self.tmp.cleanup()

    def test_default_network_front_door_denies_mutation(self):
        client = TestClient(create_secure_app(self.runtime, auth_policy=SlosAuthPolicy()))
        try:
            self.assertEqual(200, client.get("/health").status_code)
            denied = client.post("/missions", json={"instruction": "must not execute anonymously"})
            self.assertEqual(401, denied.status_code)
            state = client.get("/security-state").json()
            self.assertTrue(state["mutation_auth_enforced"])
            self.assertEqual("deny_mutations", state["auth_mode"])
        finally:
            client.close()

    def test_short_lived_hmac_operator_can_mutate(self):
        secret = "x" * 48
        policy = SlosAuthPolicy(mode=AuthMode.HMAC, hmac_secret=secret, audience="slos-test")
        client = TestClient(create_secure_app(self.runtime, auth_policy=policy))
        try:
            expires = int(time.time()) + 120
            nonce = "nonce-12345678"
            signature = sign_hmac_assertion(
                secret=secret,
                method="POST",
                path="/missions",
                subject="tester@example.invalid",
                roles=("operator",),
                expires_at=expires,
                audience="slos-test",
                nonce=nonce,
            )
            response = client.post(
                "/missions",
                json={"instruction": "authenticated mission"},
                headers={
                    "X-SLOS-Principal": "tester@example.invalid",
                    "X-SLOS-Roles": "operator",
                    "X-SLOS-Expires": str(expires),
                    "X-SLOS-Audience": "slos-test",
                    "X-SLOS-Nonce": nonce,
                    "X-SLOS-Signature": signature,
                },
            )
            self.assertEqual(200, response.status_code)
        finally:
            client.close()

    def test_bad_hmac_is_rejected(self):
        policy = SlosAuthPolicy(mode=AuthMode.HMAC, hmac_secret="y" * 48, audience="slos-test")
        client = TestClient(create_secure_app(self.runtime, auth_policy=policy))
        try:
            response = client.post(
                "/missions",
                json={"instruction": "forged mission"},
                headers={
                    "X-SLOS-Principal": "attacker",
                    "X-SLOS-Roles": "owner",
                    "X-SLOS-Expires": str(int(time.time()) + 120),
                    "X-SLOS-Audience": "slos-test",
                    "X-SLOS-Nonce": "forged-nonce",
                    "X-SLOS-Signature": "0" * 64,
                },
            )
            self.assertEqual(401, response.status_code)
        finally:
            client.close()


class ProviderAttestationTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.store = ProviderAttestationStore(self.db)

    def tearDown(self):
        self.db.close()

    def _attestation(self, *, state="INFERENCE_VERIFIED_SCOPED"):
        return ProviderAttestation.build(
            attestation_id="att-1",
            provider="GOOGLE",
            surface="GEMINI_VERTEX",
            subject="superior-logic-runtime@example.invalid",
            state=state,
            capabilities=("GEMINI_INFERENCE", "READ_PROJECT_METADATA"),
            observed_at_epoch=1000,
            expires_at_epoch=1100,
            evidence_refs=("provider-run:123", "receipt:abc"),
            source_revision="sha-1",
            details={"credential_reference": "WIF_RUNTIME"},
        )

    def test_fresh_attestation_routes_and_expiry_holds(self):
        self.store.put(self._attestation())
        router = DynamicProviderRouter(
            self.store,
            (
                ProviderRoutePolicy(
                    operation="GEMINI_INFERENCE",
                    provider="GOOGLE",
                    surface="GEMINI_VERTEX",
                    capability="GEMINI_INFERENCE",
                    priority=1,
                ),
            ),
        )
        decision = router.route("GEMINI_INFERENCE", now_epoch=1050)
        self.assertEqual("att-1", decision.attestation_id)
        with self.assertRaises(NoFreshProviderRoute):
            router.route("GEMINI_INFERENCE", now_epoch=1200)

    def test_attestation_id_collision_rejected(self):
        self.store.put(self._attestation())
        changed = ProviderAttestation.build(
            attestation_id="att-1",
            provider="GOOGLE",
            surface="GEMINI_VERTEX",
            subject="superior-logic-runtime@example.invalid",
            state="VERIFIED",
            capabilities=("READ_PROJECT_METADATA",),
            observed_at_epoch=1000,
            expires_at_epoch=1100,
            evidence_refs=("provider-run:999",),
            source_revision="sha-2",
        )
        with self.assertRaises(AttestationError):
            self.store.put(changed)

    def test_raw_secret_fields_are_rejected(self):
        with self.assertRaises(AttestationError):
            ProviderAttestation.build(
                attestation_id="secret",
                provider="GOOGLE",
                surface="AI_STUDIO",
                subject="runtime",
                state="VERIFIED",
                capabilities=("GEMINI_INFERENCE",),
                observed_at_epoch=1,
                expires_at_epoch=2,
                evidence_refs=("receipt:1",),
                source_revision="sha",
                details={"api_key_value": "must-not-enter-state"},
            )


class ChangeImpactTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = MissionSnapshot.build(
            mission_id="m1",
            base_revision="base-sha",
            protected_paths=("superior_logic/**", "sol_61_runtime/**"),
            retest_paths=("tests/test_slos_*", "tests/test_sol_62_*"),
            contract_paths=("governance/proofos_omega_policy_extension_slos_*", "Dockerfile"),
            source_epoch=1,
        )
        self.compiler = ChangeImpactCompiler()

    def test_unrelated_main_movement_does_not_force_rebase(self):
        result = self.compiler.evaluate(self.snapshot, ["sovara/creative/new_feature.py"])
        self.assertEqual(ImpactDecision.IGNORE_UNRELATED, result.decision)

    def test_relevant_test_change_requires_retest_only(self):
        result = self.compiler.evaluate(self.snapshot, ["tests/test_slos_other.py"])
        self.assertEqual(ImpactDecision.RETEST_ONLY, result.decision)

    def test_source_change_requires_rebase(self):
        result = self.compiler.evaluate(self.snapshot, ["superior_logic/runtime.py"])
        self.assertEqual(ImpactDecision.REBASE_REQUIRED, result.decision)


class EvidenceAndTraceTests(unittest.TestCase):
    def test_sensitive_evidence_never_enters_excerpt(self):
        distiller = EvidenceDistiller(max_excerpt_chars=40)
        evidence = distiller.distill(
            evidence_id="ev1",
            source_ref="workflow:1",
            evidence_kind="LOG",
            raw="very secret provider log",
            sensitive=True,
        )
        self.assertIsNone(evidence.excerpt)
        self.assertEqual(64, len(evidence.content_sha256))
        bundle = distiller.bundle([evidence])
        self.assertFalse(bundle["raw_content_embedded"])

    def test_trace_requires_parent_lineage_and_rejects_secret_fields(self):
        trace = TraceBuffer("trace-1")
        root = TraceSpan.build(trace_id="trace-1", kind=SpanKind.MISSION, name="mission", status="OK")
        trace.append(root)
        child = TraceSpan.build(
            trace_id="trace-1",
            parent_span_id=root.span_id,
            kind=SpanKind.PROVIDER,
            name="google",
            status="OK",
            attributes={"provider_run_id": "123"},
        )
        trace.append(child)
        self.assertEqual(2, trace.receipt()["span_count"])
        with self.assertRaises(ValueError):
            TraceSpan.build(
                trace_id="trace-1",
                kind=SpanKind.TOOL,
                name="bad",
                status="ERROR",
                attributes={"access_token": "do-not-store"},
            )


class SourceShapeTests(unittest.TestCase):
    def _read_repository_surface(self, path: str) -> str:
        target = Path(path)
        if not target.is_file():
            self.skipTest(
                "repository packaging surface unavailable in extracted-core court; "
                "full-checkout Airlock/source-shape court remains authoritative"
            )
        return target.read_text(encoding="utf-8")

    def test_docker_uses_secure_service_and_includes_sol_kernel(self):
        text = self._read_repository_surface("Dockerfile")
        self.assertIn("APP_MODULE=superior_logic.secure_service:app", text)
        self.assertIn("COPY sol_61_runtime ./sol_61_runtime", text)
        self.assertNotIn("APP_MODULE=superior_logic.service:app", text)

    def test_wif_lease_has_consumption_gate_and_shell_portability(self):
        text = self._read_repository_surface(".github/workflows/sol62-wif-hardening-lease.yml")
        self.assertIn("actions: read", text)
        self.assertIn("Consume lease only after first successful transaction", text)
        self.assertIn("steps.lease.outputs.consumed != 'true'", text)
        self.assertIn("bash ./ops/harden_sovara_provider_wif_v1.sh --apply", text)
        self.assertIn("ALREADY_CONSUMED", text)


if __name__ == "__main__":
    unittest.main()
