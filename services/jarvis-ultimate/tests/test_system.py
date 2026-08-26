import base64
import hashlib
import hmac
import json
import os
import sys
import tempfile
import threading
import time
import types as pytypes
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from jarvis.authority import AuthorityEnvelope, WORKSPACE_MINIMUM_SCOPES
from jarvis.core import (
    ACTION_SPECS,
    CapabilityFabric,
    CapabilityState,
    CircuitBreaker,
    FormationKernel,
    LearningLedger,
    LedgerIntegrityError,
    PermitVerifier,
    RecoveryProof,
    semantic_fingerprint,
    stable_json,
)
from jarvis.math_engine import MathExpressionError, calculate
from jarvis.orchestrator import Jarvis
from jarvis.principles import ALLOWED_EPISTEMIC_CLASSES, catalogue, doctrine_summary
from jarvis.providers import GeminiReasoner, ProviderConfigurationError, ProviderInvocationError, ProviderSettings, ReasoningResult


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def public_key(private_key):
    raw = private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return b64(raw)


def mint_permit(private_key, mission_id, mission_version, action_id, capability, subject_id, resource, arguments, nonce, issued_at, expires_at):
    payload = {
        "version": 3,
        "audience": "jarvis-ultimate",
        "missionId": mission_id,
        "missionVersion": mission_version,
        "actionId": action_id,
        "capability": capability,
        "subjectId": subject_id,
        "resource": resource,
        "argumentsHash": semantic_fingerprint(arguments),
        "idempotencyKey": arguments.get("idempotency_key", ""),
        "nonce": nonce,
        "issuedAt": issued_at,
        "expiresAt": expires_at,
    }
    body = stable_json(payload).encode()
    signature = private_key.sign(body)
    return f"{b64(body)}.{b64(signature)}"


def signed_recovery_proof(route, proof_id, verifier_id, evidence_hash, checked_at, generation, private_key):
    unsigned = RecoveryProof(route, proof_id, verifier_id, evidence_hash, True, checked_at, generation)
    signature = b64(private_key.sign(unsigned.signed_body()))
    return RecoveryProof(route, proof_id, verifier_id, evidence_hash, True, checked_at, generation, signature)


def authority(action, resource, subject="owner"):
    scopes = WORKSPACE_MINIMUM_SCOPES.get(action, frozenset())
    return AuthorityEnvelope(
        subject_id=subject,
        user_grants=frozenset({action}),
        oauth_scopes=scopes,
        iam_actions=frozenset({action}),
        mission_actions=frozenset({action}),
        tool_allowlist=frozenset({action}),
        resource_allowlist=frozenset({resource}),
    )


class SuccessfulReasoner:
    name = "successful-test-route"
    provider_mode = "gemini_developer"

    def respond(self, message, context):
        return ReasoningResult(
            "A semantically meaningful, evidence-bounded test response.",
            self.provider_mode,
            "test-model",
            "test-v1",
            "ADVISORY",
            "NO_EFFECTS_EXECUTED",
            (),
            True,
        )


class FailingReasoner:
    name = "failing-test-route"
    provider_mode = "gemini_developer"

    def __init__(self):
        self.calls = 0

    def respond(self, message, context):
        self.calls += 1
        raise ProviderInvocationError("DEPENDENCY_UNAVAILABLE")


class UnexpectedReasoner(FailingReasoner):
    name = "unexpected-test-route"

    def respond(self, message, context):
        self.calls += 1
        raise RuntimeError("raw internal detail")


class GenericClaimReasoner:
    name = "generic-claim-route"
    provider_mode = "gemini_developer"

    def __init__(self, claim="Deployment successfully completed for every requested resource."):
        self.claim = claim

    def respond(self, message, context):
        return ReasoningResult(self.claim, self.provider_mode, "m", "v1")


class JarvisTests(unittest.TestCase):
    def test_health_and_offline_chat_use_canonical_graph_and_doctrine(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            app = Jarvis(directory)
            result = app.chat("map the objective")
            self.assertTrue(app.health()["ok"])
            self.assertEqual(result["route"], "offline-deterministic")
            self.assertTrue(result["semanticFruit"])
            self.assertEqual(len(result["workflowEvents"]), 5)
            self.assertIn("truth-typed doctrine principles=32", result["answer"])
            self.assertTrue(app.ledger.verify())

    def test_environment_key_never_auto_enables_provider_or_live_proof(self):
        settings = ProviderSettings.from_env({"GOOGLE_API_KEY": "secret-value"})
        self.assertEqual(settings.mode, "offline")
        self.assertEqual(CapabilityFabric(settings.mode).get("gemini").state, CapabilityState.ADAPTER_REQUIRED)

    def test_explicit_provider_requires_exact_configuration(self):
        with self.assertRaisesRegex(ProviderConfigurationError, "GEMINI_MODEL_REQUIRED"):
            ProviderSettings.from_env({"JARVIS_PROVIDER": "gemini_developer", "GOOGLE_API_KEY": "x"})
        with self.assertRaisesRegex(ProviderConfigurationError, "VERTEX_PROJECT_AND_LOCATION_REQUIRED"):
            ProviderSettings.from_env({"JARVIS_PROVIDER": "gemini_vertex", "JARVIS_GEMINI_MODEL": "m", "GOOGLE_CLOUD_PROJECT": "p"})

    def test_gemini_reasoner_retains_sdk_types_for_the_call_contract(self):
        class FakeHttpOptions:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class FakeGenerateContentConfig:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class FakeModels:
            def generate_content(self, **kwargs):
                self.kwargs = kwargs
                return pytypes.SimpleNamespace(
                    text=json.dumps(
                        {
                            "responseClass": "ADVISORY",
                            "effectState": "NO_EFFECTS_EXECUTED",
                            "answer": "Evidence-bounded advisory response.",
                            "claims": [],
                        }
                    )
                )

        class FakeClient:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                self.models = FakeModels()

        fake_genai = pytypes.ModuleType("google.genai")
        fake_genai.Client = FakeClient
        fake_genai.types = pytypes.SimpleNamespace(
            HttpOptions=FakeHttpOptions,
            GenerateContentConfig=FakeGenerateContentConfig,
        )
        fake_google = pytypes.ModuleType("google")
        fake_google.genai = fake_genai
        settings = ProviderSettings("gemini_developer", "model", "v1beta", api_key="test-only")
        with patch.dict(sys.modules, {"google": fake_google, "google.genai": fake_genai}):
            result = GeminiReasoner(settings).respond(
                "objective",
                {"capabilities": [], "principles": [], "doctrine": {}},
            )
        self.assertEqual(result.response_class, "ADVISORY")
        self.assertEqual(result.effect_state, "NO_EFFECTS_EXECUTED")
        self.assertTrue(result.structured)

    def test_unknown_action_and_natural_language_bypasses_fail_closed(self):
        fabric, kernel = CapabilityFabric(), FormationKernel()
        for action_id in ("create resource", "update", "share", "move", "forward", "archive", "deploy candidate"):
            decision = kernel.decide("M1", 1, action_id, fabric.get("github"))
            self.assertEqual(decision.status, "DENY")
            self.assertIn("ACTION_SCHEMA_UNKNOWN", decision.reasons)

    def test_action_argument_and_resource_schema_is_exact(self):
        spec = ACTION_SPECS["github.release"]
        self.assertTrue(spec.resource_required)
        self.assertEqual({field.name for field in spec.arguments}, {"idempotency_key", "branch", "commit_sha"})
        fabric, kernel = CapabilityFabric(), FormationKernel()
        result = kernel.decide(
            "M1", 1, "github.release", fabric.get("github"), resource="*",
            arguments={"idempotency_key": "k", "branch": "b", "commit_sha": "c", "owner": True},
        )
        self.assertIn("ACTION_RESOURCE_EXACT_REQUIRED", result.reasons)
        self.assertIn("ACTION_ARGUMENT_UNKNOWN:owner", result.reasons)

    def test_external_action_requires_full_authority_intersection(self):
        fabric, kernel = CapabilityFabric(), FormationKernel()
        result = kernel.decide("M1", 1, "github.source", fabric.get("github"), resource="repo:path", arguments={})
        self.assertIn("EFFECTIVE_AUTHORITY_REQUIRED", result.reasons)

    def test_workspace_scope_map_covers_every_workspace_action(self):
        workspace = {"drive", "gmail", "sheets", "calendar"}
        missing = [spec.id for spec in ACTION_SPECS.values() if spec.capability in workspace and spec.id not in WORKSPACE_MINIMUM_SCOPES]
        self.assertEqual(missing, [])

    def test_bound_permit_is_single_use_and_binds_resource_arguments_subject_and_version(self):
        private_key = Ed25519PrivateKey.generate()
        now = int(time.time())
        action_id, resource = "github.release", "repo:agent/v1"
        arguments = {"idempotency_key": "release-1", "branch": "agent/v1", "commit_sha": "a" * 40}
        token = mint_permit(private_key, "M1", 7, action_id, "github", "owner", resource, arguments, "nonce-1234567890abcdef", now, now + 120)
        with tempfile.TemporaryDirectory() as directory:
            kernel = FormationKernel(PermitVerifier(public_key(private_key), Path(directory) / "nonces.txt"))
            capability = CapabilityFabric().get("github")
            envelope = authority(action_id, resource)
            preview = kernel.decide("M1", 7, action_id, capability, resource=resource, arguments=arguments, authority_envelope=envelope, permit=token)
            self.assertEqual(preview.status, "ALLOW_DRY_RUN")
            execution = kernel.decide("M1", 7, action_id, capability, resource=resource, arguments=arguments, authority_envelope=envelope, permit=token, consume_permit=True)
            self.assertEqual(execution.status, "AUTHORIZED_FOR_EXECUTION")
            self.assertTrue(execution.permit_consumed)
            replay = kernel.decide("M1", 7, action_id, capability, resource=resource, arguments=arguments, authority_envelope=envelope, permit=token, consume_permit=True)
            self.assertIn("PERMIT_REPLAYED", replay.reasons)
            changed = kernel.decide("M1", 8, action_id, capability, resource=resource, arguments=arguments, authority_envelope=envelope, permit=token)
            self.assertIn("PERMIT_BINDING_MISMATCH", changed.reasons)

    def test_malformed_formation_public_key_is_rejected(self):
        verifier = PermitVerifier("x", "/tmp/unused-nonce-test")
        valid, reason, consumed = verifier.verify_and_optionally_consume(
            "x.y", mission_id="M", mission_version=1, action_id="a", capability="c", subject_id="s",
            resource="r", arguments_hash="h", idempotency_key="i", consume=False,
        )
        self.assertFalse(valid)
        self.assertEqual(reason, "FORMATION_PUBLIC_KEY_INVALID")
        self.assertFalse(consumed)

    def test_periodic_shared_secret_cannot_be_used_as_formation_authority(self):
        verifier = PermitVerifier("01234567" * 4, "/tmp/unused-repeated-key-test")
        valid, reason, consumed = verifier.verify_and_optionally_consume(
            "x.y", mission_id="M", mission_version=1, action_id="a", capability="c", subject_id="s",
            resource="r", arguments_hash="h", idempotency_key="i", consume=False,
        )
        self.assertFalse(valid)
        self.assertEqual(reason, "FORMATION_PUBLIC_KEY_INVALID")
        self.assertFalse(consumed)

    def test_input_validation_never_quarantines_healthy_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Jarvis(directory)
            app.chat("")
            app.chat("  ")
            self.assertNotIn("offline-deterministic", app.breaker.quarantined)
            self.assertTrue(app.chat("valid objective")["semanticFruit"])

    def test_expected_and_unexpected_provider_failures_open_breaker(self):
        for reasoner in (FailingReasoner(), UnexpectedReasoner()):
            with tempfile.TemporaryDirectory() as directory:
                app = Jarvis(directory, reasoner=reasoner)
                self.assertFalse(app.chat("first")["semanticFruit"])
                self.assertTrue(app.chat("second")["quarantined"])
                app.chat("third")
                self.assertEqual(reasoner.calls, 2)

    def test_generic_effect_completion_claim_is_rejected(self):
        claims = (
            "Deployment successfully completed for every requested resource.",
            "All requested work is done.",
            "The production service is now live.",
            "Permissions have been granted.",
            "The resource has been provisioned.",
            "The email reached the recipient.",
            "Access is enabled.",
            "The operation succeeded.",
            "The rollout achieved its objective.",
            "The file now exists in Drive.",
            "The release went through.",
            "The account can now administer the project.",
        )
        for claim in claims:
            with self.subTest(claim=claim), tempfile.TemporaryDirectory() as directory:
                result = Jarvis(directory, reasoner=GenericClaimReasoner(claim)).chat("status")
                self.assertFalse(result["semanticFruit"])
                self.assertEqual(result["error"], "SEMANTIC_FRUIT_INVALID")

    def test_breaker_recovery_requires_two_independent_fresh_proofs(self):
        now = int(time.time())
        first_private, second_private = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
        keys = {
            "verifier-one": public_key(first_private),
            "verifier-two": public_key(second_private),
        }
        breaker = CircuitBreaker(1, clock=lambda: now, recovery_verifier_keys=keys)
        breaker.record("route", False)
        same = signed_recovery_proof("route", "proof-one", "verifier-one", "a" * 64, now, 1, first_private)
        self.assertFalse(breaker.restore_after_independent_proof("route", (same, same)))
        other = signed_recovery_proof("route", "proof-two", "verifier-two", "b" * 64, now, 1, second_private)
        self.assertTrue(breaker.restore_after_independent_proof("route", (same, other)))

    def test_breaker_recovery_rejects_fabricated_distinct_receipts(self):
        now = int(time.time())
        first_private, second_private = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
        breaker = CircuitBreaker(
            1,
            clock=lambda: now,
            recovery_verifier_keys={
                "verifier-one": public_key(first_private),
                "verifier-two": public_key(second_private),
            },
        )
        breaker.record("route", False)
        fabricated = (
            RecoveryProof("route", "proof-one", "verifier-one", "a" * 64, True, now, 1, "0" * 64),
            RecoveryProof("route", "proof-two", "verifier-two", "b" * 64, True, now, 1, "1" * 64),
        )
        self.assertFalse(breaker.restore_after_independent_proof("route", fabricated))

    def test_recovery_receipts_cannot_be_replayed_after_later_quarantine(self):
        now = int(time.time())
        first_private, second_private = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
        breaker = CircuitBreaker(1, clock=lambda: now, recovery_verifier_keys={"verifier-one": public_key(first_private), "verifier-two": public_key(second_private)})
        breaker.record("route", False)
        proofs = (
            signed_recovery_proof("route", "proof-one", "verifier-one", "a" * 64, now, 1, first_private),
            signed_recovery_proof("route", "proof-two", "verifier-two", "b" * 64, now, 1, second_private),
        )
        self.assertTrue(breaker.restore_after_independent_proof("route", proofs))
        breaker.record("route", False)
        self.assertEqual(breaker.generations["route"], 2)
        self.assertFalse(breaker.restore_after_independent_proof("route", proofs))

    def test_recovery_receipt_consumption_is_atomic_within_one_runtime(self):
        now = int(time.time())
        first_private, second_private = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
        breaker = CircuitBreaker(1, clock=lambda: now, recovery_verifier_keys={"verifier-one": public_key(first_private), "verifier-two": public_key(second_private)})
        breaker.record("route", False)
        proofs = (
            signed_recovery_proof("route", "proof-one", "verifier-one", "a" * 64, now, 1, first_private),
            signed_recovery_proof("route", "proof-two", "verifier-two", "b" * 64, now, 1, second_private),
        )
        barrier = threading.Barrier(3)

        def restore():
            barrier.wait()
            return breaker.restore_after_independent_proof("route", proofs)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(restore) for _ in range(2)]
            barrier.wait()
            results = [future.result() for future in futures]
        self.assertEqual(sorted(results), [False, True])

    def test_atomic_ledger_survives_concurrent_appends(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = LearningLedger(Path(directory) / "events.jsonl")
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda value: ledger.append("route", "SUCCESS", value, f"proof-{value}", True), range(32)))
            self.assertEqual(len(ledger.path.read_text(encoding="utf-8").splitlines()), 32)
            self.assertTrue(ledger.verify())

    def test_tampered_ledger_blocks_new_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = LearningLedger(Path(directory) / "events.jsonl")
            ledger.append("route", "SUCCESS", 1, "proof", True)
            event = json.loads(ledger.path.read_text(encoding="utf-8"))
            event["outcome"] = "FAILURE"
            ledger.path.write_text(json.dumps(event) + "\n", encoding="utf-8")
            self.assertFalse(ledger.verify())
            with self.assertRaises(LedgerIntegrityError):
                ledger.append("route", "SUCCESS", 2, "proof-2", True)

    def test_authenticated_ledger_checkpoint_detects_recomputation(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = LearningLedger(Path(directory) / "state" / "events.jsonl", "0123456789abcdef0123456789abcdef", Path(directory) / "anchor" / "highwater.json")
            ledger.append("route", "SUCCESS", 1, "proof", True)
            self.assertTrue(ledger.verify())
            checkpoint = json.loads(ledger.checkpoint_path.read_text(encoding="utf-8"))
            checkpoint["count"] = 99
            ledger.checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
            self.assertFalse(ledger.verify())

    def test_authenticated_ledger_detects_deletion_and_blocks_recreation(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = LearningLedger(Path(directory) / "state" / "events.jsonl", "0123456789abcdef0123456789abcdef", Path(directory) / "anchor" / "highwater.json")
            ledger.append("route", "SUCCESS", 1, "proof", True)
            ledger.path.unlink()
            ledger.checkpoint_path.unlink()
            self.assertFalse(ledger.verify())
            with self.assertRaisesRegex(LedgerIntegrityError, "LEDGER_ROLLBACK_OR_DELETION_DETECTED"):
                ledger.append("route", "SUCCESS", 2, "proof-2", True)

    def test_authenticated_ledger_rejects_older_valid_chain_and_checkpoint_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = LearningLedger(Path(directory) / "state" / "events.jsonl", "0123456789abcdef0123456789abcdef", Path(directory) / "anchor" / "highwater.json")
            ledger.append("route", "SUCCESS", 1, "proof-1", True)
            old_ledger = ledger.path.read_text(encoding="utf-8")
            old_checkpoint = ledger.checkpoint_path.read_text(encoding="utf-8")
            ledger.append("route", "SUCCESS", 2, "proof-2", True)
            ledger.path.write_text(old_ledger, encoding="utf-8")
            ledger.checkpoint_path.write_text(old_checkpoint, encoding="utf-8")
            self.assertFalse(ledger.verify())
            with self.assertRaises(LedgerIntegrityError):
                ledger.append("route", "SUCCESS", 3, "proof-3", True)

    def test_authenticated_ledger_refuses_unanchored_initialization(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = LearningLedger(Path(directory) / "events.jsonl", "0123456789abcdef0123456789abcdef")
            self.assertFalse(ledger.verify())
            with self.assertRaisesRegex(LedgerIntegrityError, "LEDGER_EXTERNAL_ANCHOR_REQUIRED"):
                ledger.append("route", "SUCCESS", 1, "proof", True)

    def test_math_engine_is_integrated_and_rejects_code_arity_and_exponents(self):
        self.assertAlmostEqual(calculate("sqrt(81) + sin(pi / 2)").value, 10.0)
        for expression in ("__import__('os').system('id')", "2 ** 1000", "sqrt(4, 9)"):
            with self.assertRaises(MathExpressionError):
                calculate(expression)
        with tempfile.TemporaryDirectory() as directory:
            result = Jarvis(directory).chat("/math sqrt(81) + sin(pi/2)")
            self.assertEqual(result["route"], "deterministic-math")
            self.assertIn("= 10.0", result["answer"])

    def test_authority_is_an_exact_intersection(self):
        action, resource = "gmail.send", "gmail:message-1"
        complete = authority(action, resource)
        self.assertEqual(complete.evaluate(action, resource, True), (True, ()))
        missing = AuthorityEnvelope("owner", frozenset({action}), frozenset(), frozenset({action}), frozenset({action}), frozenset({action}), frozenset({resource}))
        allowed, reasons = missing.evaluate(action, resource, True)
        self.assertFalse(allowed)
        self.assertIn("OAUTH_SCOPE_MISSING", reasons)

    def test_science_doctrine_is_complete_and_truth_typed(self):
        rows, summary = catalogue(), doctrine_summary()
        self.assertEqual(len(rows), 32)
        self.assertEqual(summary["categoryCount"], 9)
        self.assertTrue(all(row["epistemicClass"] in ALLOWED_EPISTEMIC_CLASSES for row in rows))
        self.assertTrue(all(row["limits"] and row["falsificationChecks"] for row in rows))

    def test_adk_entrypoint_uses_typed_workflow_without_blanket_exception(self):
        source = (Path(__file__).parents[1] / "jarvis" / "agent.py").read_text(encoding="utf-8")
        self.assertIn("Workflow", source)
        self.assertIn("node_input: str", source)
        self.assertNotIn("except Exception", source)

    def test_protected_browser_bootstrap_is_public_before_api_auth(self):
        source = (Path(__file__).parents[1] / "jarvis" / "main.py").read_text(encoding="utf-8")
        self.assertLess(source.index('if self.path == "/":'), source.index("if not self._authorized()"))

    def test_external_advisory_never_mints_semantic_or_effect_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Jarvis(directory, reasoner=SuccessfulReasoner())
            result = app.chat("objective")
            self.assertFalse(result["semanticFruit"])
            self.assertTrue(result["advisoryFruit"])
            self.assertFalse(result["effectFruit"])
            self.assertIsNone(app.health()["providerSessionProof"])
            self.assertTrue(app.health()["providerSessionReceipt"].startswith("session-advisory-contract:"))
            self.assertEqual(app.fabric.get("gemini").state, CapabilityState.ACTIVE_PARTIAL)

    def test_contradictory_structured_advisory_is_qualified_and_not_semantic_proof(self):
        class ContradictoryStructuredReasoner:
            name = "contradictory-structured-route"
            provider_mode = "gemini_developer"

            def respond(self, message, context):
                return ReasoningResult(
                    "The production deployment completed successfully.",
                    "gemini_developer",
                    "model",
                    "v1",
                    "ADVISORY",
                    "NO_EFFECTS_EXECUTED",
                    (),
                    True,
                )

        with tempfile.TemporaryDirectory() as directory:
            app = Jarvis(directory, reasoner=ContradictoryStructuredReasoner())
            result = app.chat("status")
            self.assertFalse(result["semanticFruit"])
            self.assertTrue(result["advisoryFruit"])
            self.assertFalse(result["effectFruit"])
            self.assertTrue(result["answer"].startswith("Untrusted external advisory;"))
            self.assertIsNone(app.health()["providerSessionProof"])

    def test_external_reasoner_cannot_spoof_trusted_local_provenance(self):
        class SpoofingReasoner:
            name = "external-spoof-route"
            provider_mode = "gemini_developer"

            def __init__(self, provider):
                self.provider = provider

            def respond(self, message, context):
                return ReasoningResult(
                    "Evidence-bounded external advisory response.",
                    self.provider,
                    "model",
                    "v1",
                    "ADVISORY",
                    "NO_EFFECTS_EXECUTED",
                    (),
                    True,
                )

        for spoofed_provider in ("offline-deterministic", "deterministic-math"):
            with self.subTest(provider=spoofed_provider), tempfile.TemporaryDirectory() as directory:
                app = Jarvis(directory, reasoner=SpoofingReasoner(spoofed_provider))
                result = app.chat("ordinary advisory objective")
                self.assertEqual(result["route"], "external-spoof-route")
                self.assertFalse(result["semanticFruit"])
                self.assertTrue(result["advisoryFruit"])
                self.assertFalse(result["effectFruit"])
                self.assertTrue(result["answer"].startswith("Untrusted external advisory;"))
                self.assertIsNone(app.health()["providerSessionProof"])


if __name__ == "__main__":
    unittest.main()
