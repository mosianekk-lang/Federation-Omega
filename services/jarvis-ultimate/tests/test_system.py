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
    CapabilityFabric,
    CapabilityState,
    CircuitBreaker,
    FormationKernel,
    LearningLedger,
    PermitVerifier,
)
from jarvis.math_engine import MathExpressionError, calculate
from jarvis.orchestrator import Jarvis
from jarvis.principles import ALLOWED_EPISTEMIC_CLASSES, catalogue, doctrine_summary
from jarvis.providers import (
    OfflineReasoner,
    ProviderConfigurationError,
    ProviderInvocationError,
    ProviderSettings,
    ReasoningResult,
)


class SuccessfulReasoner:
    name = "successful-test-route"
    provider_mode = "gemini_developer"

    def respond(self, message, context):
        return ReasoningResult(
            text="A semantically meaningful, evidence-bounded test response.",
            provider=self.provider_mode,
            model="test-model",
            api_version="test-v1",
        )


class FailingReasoner:
    name = "failing-test-route"
    provider_mode = "gemini_developer"

    def __init__(self):
        self.calls = 0

    def respond(self, message, context):
        self.calls += 1
        raise ProviderInvocationError("DEPENDENCY_UNAVAILABLE")


class ShortReasoner:
    name = "short-test-route"
    provider_mode = "gemini_developer"

    def respond(self, message, context):
        return ReasoningResult(text="short", provider=self.provider_mode, model="m", api_version="v1")


class JarvisTests(unittest.TestCase):
    def test_health_and_offline_chat_use_canonical_graph(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            app = Jarvis(directory)
            result = app.chat("map the objective")
            self.assertTrue(app.health()["ok"])
            self.assertEqual(result["route"], "offline-deterministic")
            self.assertTrue(result["semanticFruit"])
            self.assertEqual(len(result["workflowEvents"]), 5)
            self.assertTrue(all("nodeInfo" in event and "output" in event for event in result["workflowEvents"]))
            self.assertTrue(app.ledger.verify())

    def test_environment_key_never_auto_enables_provider_or_live_proof(self):
        settings = ProviderSettings.from_env({"GOOGLE_API_KEY": "secret-value"})
        self.assertEqual(settings.mode, "offline")
        fabric = CapabilityFabric(settings.mode)
        self.assertEqual(fabric.get("gemini").state, CapabilityState.ADAPTER_REQUIRED)

    def test_explicit_provider_requires_exact_configuration(self):
        with self.assertRaisesRegex(ProviderConfigurationError, "GEMINI_MODEL_REQUIRED"):
            ProviderSettings.from_env({"JARVIS_PROVIDER": "gemini_developer", "GOOGLE_API_KEY": "x"})
        with self.assertRaisesRegex(ProviderConfigurationError, "VERTEX_PROJECT_AND_LOCATION_REQUIRED"):
            ProviderSettings.from_env({"JARVIS_PROVIDER": "gemini_vertex", "JARVIS_GEMINI_MODEL": "m", "GOOGLE_CLOUD_PROJECT": "p"})
        settings = ProviderSettings.from_env(
            {"JARVIS_PROVIDER": "gemini_developer", "JARVIS_GEMINI_MODEL": "m", "GOOGLE_API_KEY": "x"}
        )
        self.assertEqual(settings.mode, "gemini_developer")
        self.assertEqual(CapabilityFabric(settings.mode).get("gemini").state, CapabilityState.ACTIVE_PARTIAL)

    def test_unknown_action_and_verb_bypasses_fail_closed(self):
        fabric, kernel = CapabilityFabric(), FormationKernel()
        for action in ("create resource", "update", "share", "move", "forward", "archive", "deploy candidate"):
            decision = kernel.decide("M1", action, fabric.get("github"))
            self.assertEqual(decision.status, "DENY")
            self.assertIn("ACTION_SCHEMA_UNKNOWN", decision.reasons)

    def test_unbound_capability_and_mismatched_action_are_denied(self):
        fabric, kernel = CapabilityFabric(), FormationKernel()
        self.assertEqual(kernel.decide("M1", "drive.read", None).status, "DENY")
        mismatch = kernel.decide("M1", "github.source", fabric.get("formation"))
        self.assertIn("ACTION_CAPABILITY_MISMATCH", mismatch.reasons)
        blocked = kernel.decide("M1", "drive.read", fabric.get("drive"))
        self.assertIn("CAPABILITY_NOT_LIVE", blocked.reasons)

    def test_bound_permit_is_single_use_and_replay_safe(self):
        secret = "test-secret-with-sufficient-entropy"
        now = int(time.time())
        token = PermitVerifier.issue(secret, "M1", "github.release", "github", "nonce-1234567890abcdef", now, now + 120)
        with tempfile.TemporaryDirectory() as directory:
            verifier = PermitVerifier(secret, Path(directory) / "nonces.txt")
            kernel = FormationKernel(verifier)
            capability = CapabilityFabric().get("github")
            preview = kernel.decide("M1", "github.release", capability, token, consume_permit=False)
            self.assertEqual(preview.status, "ALLOW_DRY_RUN")
            self.assertFalse(preview.permit_consumed)
            execution = kernel.decide("M1", "github.release", capability, token, consume_permit=True)
            self.assertEqual(execution.status, "AUTHORIZED_FOR_EXECUTION")
            self.assertTrue(execution.permit_consumed)
            replay = kernel.decide("M1", "github.release", capability, token, consume_permit=True)
            self.assertIn("PERMIT_REPLAYED", replay.reasons)

    def test_permit_binding_and_expiry_fail_closed(self):
        secret = "test-secret-with-sufficient-entropy"
        now = int(time.time())
        with tempfile.TemporaryDirectory() as directory:
            verifier = PermitVerifier(secret, Path(directory) / "nonces.txt", clock=lambda: now)
            capability = CapabilityFabric().get("github")
            bound = PermitVerifier.issue(secret, "M1", "github.release", "github", "nonce-abcdefghijklmnop", now, now + 60)
            mismatch = FormationKernel(verifier).decide("M2", "github.release", capability, bound, consume_permit=True)
            self.assertIn("PERMIT_BINDING_MISMATCH", mismatch.reasons)
            expired = PermitVerifier.issue(secret, "M1", "github.release", "github", "nonce-ponmlkjihgfedcba", now - 120, now - 1)
            expiry = FormationKernel(verifier).decide("M1", "github.release", capability, expired, consume_permit=True)
            self.assertIn("PERMIT_EXPIRED_OR_OUT_OF_BOUNDS", expiry.reasons)

    def test_circuit_breaker_is_enforced_before_third_call(self):
        with tempfile.TemporaryDirectory() as directory:
            reasoner = FailingReasoner()
            app = Jarvis(directory, reasoner=reasoner)
            self.assertFalse(app.chat("first")["semanticFruit"])
            self.assertTrue(app.chat("second")["quarantined"])
            third = app.chat("third")
            self.assertTrue(third["quarantined"])
            self.assertEqual(reasoner.calls, 2)

    def test_short_or_generic_semantic_fruit_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            result = Jarvis(directory, reasoner=ShortReasoner()).chat("objective")
            self.assertFalse(result["semanticFruit"])
            self.assertEqual(result["learningPromotion"], "NOT_PROMOTED")

    def test_success_records_session_proof_without_overclaiming_global_live(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Jarvis(directory, reasoner=SuccessfulReasoner())
            result = app.chat("objective")
            self.assertTrue(result["semanticFruit"])
            self.assertTrue(app.health()["providerSessionProof"].startswith("session-semantic:"))
            self.assertEqual(app.fabric.get("gemini").state, CapabilityState.ACTIVE_PARTIAL)

    def test_atomic_ledger_survives_concurrent_appends(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = LearningLedger(Path(directory) / "events.jsonl")
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda value: ledger.append("route", "SUCCESS", value, f"proof-{value}", True), range(32)))
            self.assertEqual(len(ledger.path.read_text(encoding="utf-8").splitlines()), 32)
            self.assertTrue(ledger.verify())

    def test_hash_chain_detects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = LearningLedger(Path(directory) / "events.jsonl")
            ledger.append("route", "SUCCESS", 1, "proof", True)
            event = json.loads(ledger.path.read_text(encoding="utf-8"))
            event["outcome"] = "FAILURE"
            ledger.path.write_text(json.dumps(event) + "\n", encoding="utf-8")
            self.assertFalse(ledger.verify())

    def test_math_engine_is_deterministic_and_rejects_code(self):
        self.assertAlmostEqual(calculate("sqrt(81) + sin(pi / 2)").value, 10.0)
        with self.assertRaises(MathExpressionError):
            calculate("__import__('os').system('id')")
        with self.assertRaises(MathExpressionError):
            calculate("2 ** 1000")

    def test_authority_is_an_intersection_not_a_role_inference(self):
        action = "gmail.send"
        scope = next(iter(WORKSPACE_MINIMUM_SCOPES[action]))
        complete = AuthorityEnvelope(True, frozenset({scope}), True, True, True, True)
        self.assertEqual(complete.evaluate(action), (True, ()))
        missing_scope = AuthorityEnvelope(True, frozenset(), True, True, True, True)
        allowed, reasons = missing_scope.evaluate(action)
        self.assertFalse(allowed)
        self.assertIn("OAUTH_SCOPE_MISSING", reasons)

    def test_science_doctrine_is_complete_and_truth_typed(self):
        rows = catalogue()
        summary = doctrine_summary()
        self.assertEqual(len(rows), 32)
        self.assertEqual(summary["categoryCount"], 9)
        self.assertTrue(all(row["epistemicClass"] in ALLOWED_EPISTEMIC_CLASSES for row in rows))
        self.assertTrue(all(row["limits"] and row["falsificationChecks"] for row in rows))

    def test_adk_entrypoint_uses_workflow_without_blanket_exception(self):
        source = (Path(__file__).parents[1] / "jarvis" / "agent.py").read_text(encoding="utf-8")
        self.assertIn("Workflow", source)
        self.assertIn("node_input", source)
        self.assertNotIn("except Exception", source)


if __name__ == "__main__":
    unittest.main()
