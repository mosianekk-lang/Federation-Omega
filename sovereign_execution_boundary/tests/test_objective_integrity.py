from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from seb.adapters import DurableWorkflowContract, WorkloadIdentity
from seb.completion import CompletionTheorem
from seb.engine import SovereignEngine
from seb.integrity import ObjectiveIntegrityKernel
from seb.ledger import JsonlLedger
from seb.models import Budget, CompletionEvidence, MissionIR, MissionState
from seb.objective import ObjectiveContract, ObjectiveRegistry, ObjectiveViolation
from seb.policy import PolicyEngine
from seb.providers import MockProvider
from seb.router import ProviderRouter


SECRET = b"test-only-owner-secret"


def contract(**changes):
    base = ObjectiveContract("owner", "deploy operational boundary",
        ("live external effects", "provider failover"), ("health readback", "rollback canary"),
        ("artifact-only completion",), ("objective immutable",))
    return replace(base, **changes)


def complete_evidence(c):
    return CompletionEvidence(c.fingerprint, c.mandatory_requirements, c.acceptance_tests,
                              ("provider-native:ok",), c.invariants, (), True, True)


class ObjectiveIntegrityTests(unittest.TestCase):
    def test_owner_signed_monotonic_supersession(self):
        registry = ObjectiveRegistry({"owner": SECRET})
        first = contract().sign(SECRET)
        registry.admit(first)
        second = replace(first, objective="deploy operational boundary v2", version=2,
                         supersedes=first.fingerprint, signature="").sign(SECRET)
        self.assertEqual(registry.admit(second), second)

    def test_invalid_signature_and_stale_version_fail_closed(self):
        registry = ObjectiveRegistry({"owner": SECRET})
        first = contract().sign(SECRET)
        registry.admit(first)
        with self.assertRaises(ObjectiveViolation):
            registry.admit(replace(first, version=2, supersedes=first.fingerprint, signature="bad"))
        with self.assertRaises(ObjectiveViolation):
            registry.admit(first)

    def test_mutation_and_requirement_dilution_detected(self):
        c = contract()
        candidate = replace(c, objective="write a report", mandatory_requirements=("provider failover",))
        decision = ObjectiveIntegrityKernel().compare(c, candidate)
        self.assertFalse(decision.preserved)
        self.assertIn("OBJECTIVE_MUTATED", decision.violations)
        self.assertTrue(any(x.startswith("MANDATORY_REQUIREMENT_DROPPED") for x in decision.violations))

    def test_weakened_tests_and_removed_substitution_ban_detected(self):
        c = contract()
        candidate = replace(c, acceptance_tests=("health readback",), prohibited_substitutions=())
        violations = ObjectiveIntegrityKernel().compare(c, candidate).violations
        self.assertTrue(any(x.startswith("ACCEPTANCE_TEST_WEAKENED") for x in violations))
        self.assertTrue(any(x.startswith("PROHIBITED_SUBSTITUTION_REMOVED") for x in violations))

    def test_artifact_cannot_masquerade_as_operational(self):
        c = contract()
        evidence = CompletionEvidence(c.fingerprint, ("provider failover",), ("health readback",),
                                      (), c.invariants, (), True, True)
        decision = CompletionTheorem().evaluate(c, evidence)
        self.assertFalse(decision.complete)
        self.assertIn("NATIVE_EFFECT_READBACK_MISSING", decision.defects)

    def test_full_completion_theorem(self):
        c = contract()
        self.assertTrue(CompletionTheorem().evaluate(c, complete_evidence(c)).complete)

    def test_engine_blocks_false_completion(self):
        c = contract()
        mission = MissionIR("bound", c.objective, c.mandatory_requirements, c.acceptance_tests,
                            budget=Budget(max_tokens=100))
        with tempfile.TemporaryDirectory() as td:
            engine = SovereignEngine(JsonlLedger(Path(td) / "e.jsonl"), PolicyEngine(),
                                     ProviderRouter([MockProvider("p")]))
            result = engine.execute(mission, "run", {}, lambda x: x["accepted"], contract=c,
                                    evidence_builder=lambda _: CompletionEvidence(c.fingerprint))
        self.assertEqual(result.state, MissionState.BLOCKED_INCOMPLETE)

    def test_replay_and_workload_identity_guards(self):
        DurableWorkflowContract("wf", "abc").validate_replay("abc")
        with self.assertRaises(RuntimeError):
            DurableWorkflowContract("wf", "abc").validate_replay("changed")
        WorkloadIdentity("spiffe://federation.local/seb/api").validate("federation.local")
        with self.assertRaises(ValueError):
            WorkloadIdentity("spiffe://foreign/seb/api").validate("federation.local")


if __name__ == "__main__":
    unittest.main()
