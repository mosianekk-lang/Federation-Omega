import base64
import hashlib
import hmac
import json
import os
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

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
from jarvis.providers import ProviderConfigurationError, ProviderInvocationError, ProviderSettings, ReasoningResult


def mint_permit(secret, mission_id, mission_version, action_id, capability, subject_id, resource, arguments, nonce, issued_at, expires_at):
    payload = {
        "version": 2,
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
    signature = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    encode = lambda value: base64.urlsafe_b64encode(value).rstrip(b"=").decode()
    return f"{encode(body)}.{encode(signature)}"


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
        return ReasoningResult("A semantically meaningful, evidence-bounded test response.", self.provider_mode, "test-model", "test-v1")


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

    def respond(self, message, context):
        return ReasoningResult("Deployment successfully completed for every requested resource.", self.provider_mode, "m", "v1")


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
        secret = "0123456789abcdef0123456789abcdef"
        now = int(time.time())
        action_id, resource = "github.release", "repo:agent/v1"
        arguments = {"idempotency_key": "release-1", "branch": "agent/v1", "commit_sha": "a" * 40}
        token = mint_permit(secret, "M1", 7, action_id, "github", "owner", resource, arguments, "nonce-1234567890abcdef", now, now + 120)
        with tempfile.TemporaryDirectory() as directory:
            kernel = FormationKernel(PermitVerifier(secret, Path(directory) / "nonces.txt"))
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

    def test_short_formation_key_is_rejected(self):
        verifier = PermitVerifier("x", "/tmp/unused-nonce-test")
        valid, reason, consumed = verifier.verify_and_optionally_consume(
            "x.y", mission_id="M", mission_version=1, action_id="a", capability="c", subject_id="s",
            resource="r", arguments_hash="h", idempotency_key="i", consume=False,
        )
        self.assertFalse(valid)
        self.assertEqual(reason, "FORMATION_KEY_TOO_WEAK")
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
        with tempfile.TemporaryDirectory() as directory:
            result = Jarvis(directory, reasoner=GenericClaimReasoner()).chat("status")
            self.assertFalse(result["semanticFruit"])
            self.assertEqual(result["error"], "SEMANTIC_FRUIT_INVALID")

    def test_breaker_recovery_requires_two_independent_fresh_proofs(self):
        now = int(time.time())
        breaker = CircuitBreaker(1, clock=lambda: now)
        breaker.record("route", False)
        same = RecoveryProof("route", "proof-one", "verifier-one", "a" * 64, True, now)
        self.assertFalse(breaker.restore_after_independent_proof("route", (same, same)))
        other = RecoveryProof("route", "proof-two", "verifier-two", "b" * 64, True, now)
        self.assertTrue(breaker.restore_after_independent_proof("route", (same, other)))

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
            ledger = LearningLedger(Path(directory) / "events.jsonl", "a" * 32)
            ledger.append("route", "SUCCESS", 1, "proof", True)
            self.assertTrue(ledger.verify())
            checkpoint = json.loads(ledger.checkpoint_path.read_text(encoding="utf-8"))
            checkpoint["count"] = 99
            ledger.checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
            self.assertFalse(ledger.verify())

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

    def test_success_creates_only_session_partial_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Jarvis(directory, reasoner=SuccessfulReasoner())
            self.assertTrue(app.chat("objective")["semanticFruit"])
            self.assertTrue(app.health()["providerSessionProof"].startswith("session-semantic:"))
            self.assertEqual(app.fabric.get("gemini").state, CapabilityState.ACTIVE_PARTIAL)


if __name__ == "__main__":
    unittest.main()
