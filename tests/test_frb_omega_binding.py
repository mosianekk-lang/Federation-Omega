from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from alpha_omega_v30.capability_market import CapabilityRegistry, CapabilitySpec
from alpha_omega_v30.sandbox_fleet import OperationalSandbox, ReceiptLedger, SandboxPolicy
from federation.frb_omega_binding import (
    FRBBoundIdeaSystemRuntime,
    FRBOmegaBinding,
    FRBResourceObservation,
)
from federation.idea_system_build_runtime import (
    CapabilityQualification,
    CapabilityRegistryDiscovery,
    IdeaSystemBuildRuntime,
    PersistentWorkspace,
)


def observation(
    resource_id: str,
    capabilities: tuple[str, ...],
    *,
    heartbeat_state: str = "SESSION_CONNECTOR_AVAILABLE",
    age_seconds: int = 1,
    ttl_seconds: int = 60,
    semantic_ok: bool = True,
    readback_ok: bool = True,
    authority_verified: bool = True,
    fit: float = 0.95,
    evidence_factor: float = 0.95,
    reliability: float = 0.95,
    provider_live: bool = False,
    mutation_authority: bool = False,
    independent_verifier_available: bool = True,
    incremental_cost: float | None = 0.0,
    latency_ms: float | None = 10.0,
    owner_burden: float | None = 0.1,
    outcome_value: float | None = 0.9,
) -> FRBResourceObservation:
    return FRBResourceObservation(
        resource_id=resource_id,
        capabilities=capabilities,
        heartbeat_state=heartbeat_state,
        ttl_seconds=ttl_seconds,
        age_seconds=age_seconds,
        semantic_ok=semantic_ok,
        readback_ok=readback_ok,
        authority_verified=authority_verified,
        reliability=reliability,
        fit=fit,
        evidence_factor=evidence_factor,
        provider_live=provider_live,
        mutation_authority=mutation_authority,
        independent_verifier_available=independent_verifier_available,
        incremental_cost=incremental_cost,
        latency_ms=latency_ms,
        owner_burden=owner_burden,
        outcome_value=outcome_value,
        proof_refs=(f"PROOF:{resource_id}",),
    )


def make_runtime(root: Path, interfaces: tuple[str, ...]):
    registry = CapabilityRegistry(root / "capability_registry.jsonl")
    registered = registry.register(
        CapabilitySpec(
            capability_id="operational-sandbox-fleet",
            version="1.1.0",
            purpose="Disposable operational sandbox",
            interfaces=interfaces,
            providers=("github-actions",),
            fitness={"correctness": 1.0},
            proof_refs=("PROOF-P06",),
        )
    )
    discovery = CapabilityRegistryDiscovery(
        registry,
        qualifications=(
            CapabilityQualification(
                registered["fingerprint"],
                "OPERATIONAL_VERIFIED",
                ("PROOF-P06",),
            ),
        ),
    )
    sandbox = OperationalSandbox(
        SandboxPolicy(
            timeout_seconds=1.0,
            max_output_bytes=2048,
            max_artifact_bytes=100_000,
            allowed_executables=(sys.executable,),
        ),
        ReceiptLedger(root / "sandbox_ledger.jsonl"),
    )
    return IdeaSystemBuildRuntime(
        discovery,
        PersistentWorkspace(root / "workspace.jsonl"),
        sandbox,
    )


class FRBOmegaBindingTests(unittest.TestCase):
    def test_stale_high_fit_resource_never_becomes_reusable(self) -> None:
        broker = FRBOmegaBinding(
            (
                observation(
                    "stale",
                    ("CODE_SANDBOX",),
                    fit=1.0,
                    age_seconds=600,
                    ttl_seconds=60,
                ),
            )
        )
        receipt = broker.select(("CODE_SANDBOX",))
        self.assertEqual((), receipt.selected_resource_ids)
        self.assertEqual(("CODE_SANDBOX",), receipt.unresolved_capabilities)
        self.assertEqual("QUALIFICATION_GATE", receipt.requirement_routes[0].state)

    def test_unknown_cost_fails_closed_before_value_ranking(self) -> None:
        broker = FRBOmegaBinding(
            (observation("unknown-cost", ("CODE_SANDBOX",), incremental_cost=None),)
        )
        receipt = broker.select(("CODE_SANDBOX",))
        self.assertEqual("COST_GATE", receipt.requirement_routes[0].state)
        self.assertEqual((), receipt.selected_resource_ids)

    def test_provider_live_requirement_stays_provider_gate(self) -> None:
        broker = FRBOmegaBinding(
            (observation("source-only", ("MODEL_CODE_GENERATION",), provider_live=False),)
        )
        receipt = broker.select(
            ("MODEL_CODE_GENERATION",),
            provider_live_required=("MODEL_CODE_GENERATION",),
        )
        self.assertEqual("PROVIDER_GATE", receipt.requirement_routes[0].state)
        self.assertEqual((), receipt.selected_resource_ids)

    def test_missing_value_metrics_are_not_inferred(self) -> None:
        broker = FRBOmegaBinding(
            (
                observation(
                    "no-value",
                    ("CODE_SANDBOX",),
                    latency_ms=None,
                    owner_burden=None,
                    outcome_value=None,
                ),
            )
        )
        receipt = broker.select(("CODE_SANDBOX",))
        self.assertEqual("VALUE_METRICS_GATE", receipt.requirement_routes[0].state)
        self.assertEqual(("no-value",), receipt.unranked_resource_ids)

    def test_global_minimum_set_can_keep_cross_capability_resource(self) -> None:
        broker = FRBOmegaBinding(
            (
                observation(
                    "A",
                    ("READ", "LEGAL"),
                    fit=0.99,
                    reliability=0.99,
                    latency_ms=5,
                    owner_burden=0.05,
                    outcome_value=0.95,
                ),
                observation(
                    "B",
                    ("VISUAL",),
                    fit=0.99,
                    reliability=0.99,
                    latency_ms=5,
                    owner_burden=0.05,
                    outcome_value=0.95,
                ),
                observation(
                    "C",
                    ("READ", "LEGAL", "VISUAL"),
                    fit=0.90,
                    reliability=0.90,
                    latency_ms=20,
                    owner_burden=0.2,
                    outcome_value=0.85,
                ),
            )
        )
        receipt = broker.select(("READ", "LEGAL", "VISUAL"))
        self.assertEqual(("C",), receipt.selected_resource_ids)
        self.assertEqual((), receipt.unresolved_capabilities)
        fronts = dict(receipt.pareto_fronts)
        self.assertIn("A", fronts["READ"])
        self.assertNotIn("C", fronts["READ"])
        self.assertFalse(receipt.canonical_mapping()["truth_boundary"]["pareto_dominance_overrides_capability_coverage"])

    def test_broker_selection_never_inherits_effect_authority(self) -> None:
        broker = FRBOmegaBinding(
            (observation("safe", ("CODE_SANDBOX",), mutation_authority=True),)
        )
        receipt = broker.select(("CODE_SANDBOX",))
        self.assertEqual(("safe",), receipt.selected_resource_ids)
        self.assertFalse(receipt.canonical_mapping()["truth_boundary"]["broker_selection_grants_authority"])


class FRBBoundIdeaSystemRuntimeTests(unittest.TestCase):
    def test_broker_selected_registry_slice_drives_compiler_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = make_runtime(root, ("CODE_SANDBOX", "TEST_EVALUATION"))
            broker = FRBOmegaBinding(
                (
                    observation(
                        "operational-sandbox-fleet",
                        ("CODE_SANDBOX", "TEST_EVALUATION"),
                    ),
                )
            )
            bound = FRBBoundIdeaSystemRuntime(runtime, broker)
            plan = bound.plan("Build a small API and test it.", source_frontier="main@test")
            decisions = {item.requirement: item for item in plan.capability_decisions}
            self.assertEqual("REUSE", decisions["CODE_SANDBOX"].strategy)
            self.assertEqual("REUSE", decisions["TEST_EVALUATION"].strategy)
            selection = bound.selection_for(plan)
            self.assertEqual(("operational-sandbox-fleet",), selection.selected_resource_ids)
            self.assertIn("SCAFFOLD_BUILD", selection.unresolved_capabilities)

    def test_broker_observation_cannot_invent_unregistered_capability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = make_runtime(root, ("CODE_SANDBOX",))
            broker = FRBOmegaBinding(
                (
                    observation(
                        "operational-sandbox-fleet",
                        ("CODE_SANDBOX", "TEST_EVALUATION"),
                    ),
                )
            )
            bound = FRBBoundIdeaSystemRuntime(runtime, broker)
            with self.assertRaisesRegex(ValueError, "cannot extend registered capability surface"):
                bound.plan("Build a small API and test it.", source_frontier="main@test")


if __name__ == "__main__":
    unittest.main()
