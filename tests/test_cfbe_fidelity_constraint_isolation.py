from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from benchmarking.cfbe_omega.fidelity_constraint_isolation import (
    AdapterRoute,
    CanonicalSource,
    CapabilityAttestation,
    CapabilityRequirement,
    FidelityError,
    FidelityMode,
    InvariantKind,
    IsolationPolicy,
    MaturityEvidence,
    MaturityState,
    PlatformProfile,
    ProtectedInvariant,
    evaluate_fidelity,
    isolate_constraints,
    isolate_payload,
)


def tested_evidence(prefix: str = "proof") -> MaturityEvidence:
    return MaturityEvidence(
        source_ref=f"{prefix}:source",
        test_ref=f"{prefix}:test",
        rollback_ref=f"{prefix}:rollback",
    )


def proven_evidence(prefix: str = "proof") -> MaturityEvidence:
    return MaturityEvidence(
        source_ref=f"{prefix}:source",
        test_ref=f"{prefix}:test",
        registration_ref=f"{prefix}:registry",
        authorization_ref=f"{prefix}:authority",
        readiness_ref=f"{prefix}:ready",
        deployment_ref=f"{prefix}:deployment",
        readback_ref=f"{prefix}:readback",
        rollback_ref=f"{prefix}:rollback",
    )


def platform(
    capabilities: tuple[CapabilityAttestation, ...] = (),
) -> PlatformProfile:
    return PlatformProfile(
        platform_id="chat-surface",
        exact_scope="current connected chat surface",
        discovery_ref="discovery:2026-08-30",
        capabilities=capabilities,
    )


def requirement(capability_id: str = "durable-write") -> CapabilityRequirement:
    return CapabilityRequirement(capability_id, f"Provide {capability_id}")


class FidelityEvaluationTests(unittest.TestCase):
    def test_exact_accepts_identity_and_rejects_modification(self) -> None:
        source = CanonicalSource(
            "source-1", "1", "text/plain", "alpha\nbeta\n", FidelityMode.EXACT
        )
        self.assertEqual(evaluate_fidelity(source, source.content).verdict, "ACCEPT_ZERO_DILUTION")
        rejected = evaluate_fidelity(source, "alpha\nBETA\n")
        self.assertEqual(rejected.verdict, "REJECT_DILUTION")
        self.assertEqual(rejected.violations[0].code, "EXACT_MISMATCH")

    def test_expected_hash_is_fail_closed(self) -> None:
        source = CanonicalSource(
            "source-1",
            "1",
            "text/plain",
            "alpha",
            FidelityMode.EXACT,
            expected_sha256="0" * 64,
        )
        with self.assertRaises(FidelityError):
            evaluate_fidelity(source, "alpha")

    def test_text_additions_preserve_order_but_deletion_fails(self) -> None:
        source = CanonicalSource(
            "source-1", "1", "text/plain", "alpha\nbeta\n", FidelityMode.EXACT_OR_ADDITIVE
        )
        accepted = evaluate_fidelity(source, "preface\nalpha\ninsert\nbeta\nappendix\n")
        self.assertTrue(accepted.accepted)
        rejected = evaluate_fidelity(source, "alpha\nappendix\n")
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.violations[0].code, "NON_ADDITIVE_TEXT_CHANGE")

    def test_json_additions_pass_and_canonical_change_fails(self) -> None:
        source = CanonicalSource(
            "source-1",
            "1",
            "application/json",
            '{"controls":["fidelity","proof"],"enabled":true}',
            FidelityMode.EXACT_OR_ADDITIVE,
        )
        self.assertTrue(
            evaluate_fidelity(
                source,
                '{"controls":["fidelity","new","proof"],"enabled":true,"extra":1}',
            ).accepted
        )
        self.assertFalse(
            evaluate_fidelity(
                source, '{"controls":["fidelity"],"enabled":false}'
            ).accepted
        )

    def test_literal_and_json_pointer_invariants(self) -> None:
        literal_source = CanonicalSource(
            "source-1",
            "1",
            "text/plain",
            "NEVER_DILUTE\nbody\nNEVER_DILUTE\n",
            FidelityMode.PROTECTED_INVARIANTS,
            (ProtectedInvariant("literal", InvariantKind.LITERAL, "NEVER_DILUTE", 2),),
        )
        self.assertFalse(
            evaluate_fidelity(literal_source, "NEVER_DILUTE\nbody\n").accepted
        )
        json_source = CanonicalSource(
            "source-2",
            "1",
            "application/json",
            '{"policy":{"allowDilution":false},"version":1}',
            FidelityMode.PROTECTED_INVARIANTS,
            (
                ProtectedInvariant(
                    "policy", InvariantKind.JSON_POINTER, "/policy/allowDilution"
                ),
            ),
        )
        self.assertTrue(
            evaluate_fidelity(
                json_source,
                '{"policy":{"allowDilution":false},"version":2,"extra":true}',
            ).accepted
        )
        self.assertFalse(
            evaluate_fidelity(
                json_source, '{"policy":{"allowDilution":true},"version":1}'
            ).accepted
        )

    def test_python_symbol_is_ast_exact(self) -> None:
        source = CanonicalSource(
            "source-1",
            "1",
            "text/x-python",
            "def preserve(value):\n    return value\n",
            FidelityMode.PROTECTED_INVARIANTS,
            (
                ProtectedInvariant(
                    "function", InvariantKind.PYTHON_SYMBOL, "preserve"
                ),
            ),
        )
        self.assertTrue(
            evaluate_fidelity(
                source,
                "def preserve(value):\n    return value\n\ndef additive():\n    return True\n",
            ).accepted
        )
        self.assertFalse(
            evaluate_fidelity(
                source, "def preserve(value):\n    return str(value)\n"
            ).accepted
        )


class ConstraintIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = CanonicalSource(
            "directive", "2", "text/plain", "preserve me\n", FidelityMode.EXACT
        )

    def test_native_readback_route_is_proven_without_execution_claim(self) -> None:
        result = isolate_constraints(
            self.source,
            self.source.content,
            platform(
                (
                    CapabilityAttestation(
                        "durable-write", MaturityState.READBACK_PROVEN, proven_evidence()
                    ),
                )
            ),
            (requirement(),),
        )
        self.assertEqual(result["resultState"], "ROUTE_READY_PROVEN")
        self.assertEqual(result["executionState"], "NOT_EXECUTED")
        self.assertFalse(result["truthBoundary"]["providerMutationPerformed"])

    def test_adapter_route_obeys_evidence_and_policy(self) -> None:
        adapter = AdapterRoute(
            "local-adapter",
            ("durable-write",),
            MaturityState.DETERMINISTIC_TESTED,
            tested_evidence(),
            fidelity_evidence_ref="test:fidelity",
        )
        result = isolate_constraints(
            self.source,
            self.source.content,
            platform(),
            (requirement(),),
            (adapter,),
        )
        self.assertEqual(result["resultState"], "ROUTE_READY_LOCAL")
        self.assertEqual(result["selectedAdapters"], ["local-adapter"])
        self.assertEqual(result["adapterLedger"][0]["status"], "SELECTED")

    def test_authority_cost_and_external_effects_remain_boundaries(self) -> None:
        adapters = (
            AdapterRoute(
                "authority-route",
                ("durable-write",),
                MaturityState.DETERMINISTIC_TESTED,
                tested_evidence("authority"),
                authority_ceiling="A3",
                fidelity_evidence_ref="test:fidelity",
            ),
            AdapterRoute(
                "cost-route",
                ("durable-write",),
                MaturityState.DETERMINISTIC_TESTED,
                tested_evidence("cost"),
                recurring_cost=1,
                fidelity_evidence_ref="test:fidelity",
            ),
            AdapterRoute(
                "effect-route",
                ("durable-write",),
                MaturityState.DETERMINISTIC_TESTED,
                tested_evidence("effect"),
                external_effect_required=True,
                fidelity_evidence_ref="test:fidelity",
            ),
        )
        result = isolate_constraints(
            self.source,
            self.source.content,
            platform(),
            (requirement(),),
            adapters,
            IsolationPolicy(available_authority="A1"),
        )
        self.assertEqual(result["resultState"], "PLATFORM_BOUNDARY")
        reasons = {
            item["adapterId"]: set(item["reasonCodes"]) for item in result["adapterLedger"]
        }
        self.assertIn("AUTHORITY_EXCEEDS_POLICY", reasons["authority-route"])
        self.assertIn("RECURRING_COST_EXCEEDS_POLICY", reasons["cost-route"])
        self.assertIn("EXTERNAL_EFFECT_NOT_AUTHORIZED", reasons["effect-route"])
        boundary = result["requirementDecisions"][0]["boundary"]
        self.assertEqual(boundary["classification"], "UNRESOLVED_CAPABILITY")
        self.assertIn("CANNOT_REQUIRES_TYPED_TERMINAL_BLOCKER", boundary["reasonCodes"])
        build = result["buildTriggers"][0]
        self.assertEqual(build["state"], "UNRESOLVED_ENGINEERING_BUILD")
        for field in (
            "gap",
            "desiredCapability",
            "owningEngine",
            "dependencies",
            "workaround",
            "implementationTasks",
            "securityPrivacyLimits",
            "tests",
            "acceptanceCriteria",
            "nextExecutableAction",
            "capabilityChangeTrigger",
            "closureProof",
        ):
            self.assertIn(field, build)

    def test_adapter_selection_recomputes_coverage_and_is_input_order_stable(self) -> None:
        routes = (
            AdapterRoute(
                "route-z",
                ("cap-a", "cap-b"),
                MaturityState.DETERMINISTIC_TESTED,
                tested_evidence("z"),
                fidelity_evidence_ref="test:z",
            ),
            AdapterRoute(
                "route-a",
                ("cap-a", "cap-c"),
                MaturityState.DETERMINISTIC_TESTED,
                tested_evidence("a"),
                fidelity_evidence_ref="test:a",
            ),
            AdapterRoute(
                "route-b",
                ("cap-b",),
                MaturityState.DETERMINISTIC_TESTED,
                tested_evidence("b"),
                fidelity_evidence_ref="test:b",
            ),
        )
        requirements = tuple(requirement(name) for name in ("cap-a", "cap-b", "cap-c"))
        forward = isolate_constraints(
            self.source, self.source.content, platform(), requirements, routes
        )
        reverse = isolate_constraints(
            self.source, self.source.content, platform(), requirements, tuple(reversed(routes))
        )
        self.assertEqual(forward["selectedAdapters"], ["route-a", "route-b"])
        self.assertEqual(forward["receiptSha256"], reverse["receiptSha256"])

    def test_fidelity_rejection_prevents_route_selection(self) -> None:
        adapter = AdapterRoute(
            "adapter",
            ("durable-write",),
            MaturityState.READBACK_PROVEN,
            proven_evidence(),
            fidelity_evidence_ref="readback:fidelity",
        )
        result = isolate_constraints(
            self.source, "changed\n", platform(), (requirement(),), (adapter,)
        )
        self.assertEqual(result["resultState"], "REJECT_DILUTION")
        self.assertEqual(result["selectedAdapters"], [])
        self.assertEqual(result["requirementDecisions"], [])

    def test_platform_hard_limit_requires_and_uses_exact_evidence(self) -> None:
        hard_limit = CapabilityRequirement(
            "durable-write",
            "Write durably",
            platform_hard_limit=True,
            boundary_evidence_ref="provider-contract:hard-limit",
        )
        result = isolate_constraints(
            self.source, self.source.content, platform(), (hard_limit,)
        )
        boundary = result["requirementDecisions"][0]["boundary"]
        self.assertEqual(boundary["classification"], "PROVEN_PLATFORM_HARD_LIMIT")
        self.assertIn("EXACT_SCOPE_PLATFORM_HARD_LIMIT", boundary["reasonCodes"])
        with self.assertRaises(FidelityError):
            CapabilityRequirement(
                "durable-write", "Write durably", platform_hard_limit=True
            ).validate()

    def test_maturity_overclaim_is_rejected(self) -> None:
        claimed = CapabilityAttestation(
            "durable-write", MaturityState.READBACK_PROVEN, tested_evidence()
        )
        with self.assertRaises(FidelityError):
            isolate_constraints(
                self.source,
                self.source.content,
                platform((claimed,)),
                (requirement(),),
            )

    def test_payload_rejects_string_boolean_and_non_finite_cost(self) -> None:
        base = {
            "canonicalSource": {
                "sourceId": "directive",
                "version": "1",
                "mediaType": "text/plain",
                "content": "preserve me\n",
                "fidelityMode": "EXACT",
            },
            "candidateContent": "preserve me\n",
            "platformProfile": {
                "platformId": "test",
                "exactScope": "test process",
                "discoveryRef": "test:discovery",
                "capabilities": [],
            },
            "requirements": [
                {"capabilityId": "durable-write", "description": "Write durably"}
            ],
            "adapterRoutes": [],
            "policy": {"allowExternalEffects": "false"},
        }
        with self.assertRaises(FidelityError):
            isolate_payload(base)
        base["policy"] = {"maxRecurringCost": float("nan")}
        with self.assertRaises(FidelityError):
            isolate_payload(base)
        base["policy"] = {}
        base["canonicalSource"]["sourceId"] = None
        with self.assertRaises(FidelityError):
            isolate_payload(base)

    def test_receipt_and_build_trigger_are_deterministic_and_content_free(self) -> None:
        first = isolate_constraints(
            self.source, self.source.content, platform(), (requirement(),)
        )
        second = isolate_constraints(
            self.source, self.source.content, platform(), (requirement(),)
        )
        self.assertEqual(first["receiptSha256"], second["receiptSha256"])
        self.assertEqual(first["buildTriggers"], second["buildTriggers"])
        serialized = json.dumps(first, sort_keys=True)
        self.assertNotIn(self.source.content.strip(), serialized)
        receipt = first.pop("receiptSha256")
        expected = hashlib.sha256(
            json.dumps(first, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self.assertEqual(receipt, expected)

    def test_cli_writes_atomic_public_safe_report(self) -> None:
        payload = {
            "canonicalSource": {
                "sourceId": "directive",
                "version": "1",
                "mediaType": "text/plain",
                "content": "CANONICAL_PRIVATE_BODY\n",
                "fidelityMode": "EXACT",
            },
            "candidateContent": "CANONICAL_PRIVATE_BODY\n",
            "platformProfile": {
                "platformId": "test",
                "exactScope": "test process",
                "discoveryRef": "test:discovery",
                "capabilities": [],
            },
            "requirements": [
                {"capabilityId": "durable-write", "description": "Write durably"}
            ],
            "adapterRoutes": [],
            "policy": {},
        }
        with tempfile.TemporaryDirectory() as directory:
            request_path = Path(directory) / "request.json"
            output_path = Path(directory) / "result.json"
            request_path.write_text(json.dumps(payload), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "benchmarking.cfbe_omega.fidelity_constraint_isolation",
                    "--input",
                    str(request_path),
                    "--output",
                    str(output_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(report["executionState"], "NOT_EXECUTED")
            self.assertNotIn("CANONICAL_PRIVATE_BODY", json.dumps(report))
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
