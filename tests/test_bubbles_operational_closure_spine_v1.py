from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from alpha_omega_v30.capability_market import CapabilityRegistry, CapabilitySpec
from federation.idea_system_build_runtime import (
    BuildCandidate,
    CapabilityQualification,
    CapabilityRegistryDiscovery,
    PersistentWorkspace,
)
from federation.sentinel_omega.owner_value_ingress import OwnerValueMissionRecord
from omega_one.interop import EffectClass, UniversalCapabilityContract

from bubbles.operational_closure_spine_v1 import compile_operational_closure


SOURCE = "a" * 40


def _ucc() -> UniversalCapabilityContract:
    return UniversalCapabilityContract(
        capability_id="BUBBLES-CFBE-TRACE",
        name="Bubbles Operational Closure",
        description="Read-only operational closure projection",
        effect_class=EffectClass.READ,
        proof_required=("source", "readback"),
    )


def _measured(*, pair_id: str, variant: str, owner_seconds: float, proof_ref: str) -> OwnerValueMissionRecord:
    return OwnerValueMissionRecord.from_mapping(
        {
            "observation_id": f"{pair_id}-{variant}",
            "pair_id": pair_id,
            "variant": variant,
            "mission_class": "TEST",
            "mission_id": "mission-1",
            "task_signature": "same-task",
            "oracle_id": "oracle-1",
            "source_head_sha": SOURCE,
            "observed_at": "2026-09-03T00:00:00Z",
            "accepted": True,
            "verified_output_ratio": 1.0,
            "owner_intervention_seconds": owner_seconds,
            "owner_intervention_count": 1 if owner_seconds else 0,
            "clarification_count": 0,
            "correction_count": 0,
            "elapsed_seconds": 10.0,
            "independent_readback": True,
            "proof_refs": [proof_ref],
            "evidence_class": "OBSERVED_OWNER_VALUE",
            "measurement_state": "MEASURED",
        }
    )


class BubblesOperationalClosureSpineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.registry = CapabilityRegistry(root / "capabilities.jsonl")
        spec = CapabilitySpec(
            capability_id="existing-capability",
            version="1.0.0",
            purpose="Existing verified capability",
            interfaces=("read",),
            providers=("local",),
            fitness={"correctness": 1.0, "reliability": 1.0, "cost_efficiency": 1.0},
            proof_refs=("proof://existing",),
        )
        record = self.registry.register(spec)
        self.fingerprint = record["fingerprint"]
        self.workspace = PersistentWorkspace(root / "workspace.jsonl")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _compile(self, **kwargs):
        discovery = kwargs.pop(
            "discovery",
            CapabilityRegistryDiscovery(
                self.registry,
                qualifications=(
                    CapabilityQualification(
                        self.fingerprint,
                        "VERIFIED",
                        ("proof://existing",),
                    ),
                ),
            ),
        )
        return compile_operational_closure(
            mission_id="mission-1",
            trace_id="trace-1",
            source_head_sha=SOURCE,
            capability_contract=_ucc(),
            discovery=discovery,
            workspace=self.workspace,
            **kwargs,
        )

    def test_composes_existing_controls_without_granting_provider_authority(self) -> None:
        receipt = self._compile()
        self.assertEqual(receipt["state"], "SOURCE_CONTROL_CONVERGED_PROVIDER_VALUE_GATED")
        self.assertTrue(receipt["interop"]["zero_dilution_verified"])
        self.assertEqual(receipt["capability_discovery"]["qualified_reusable_count"], 1)
        self.assertTrue(receipt["workspace"]["valid"])
        self.assertFalse(receipt["provider_effect_authorized"])
        self.assertFalse(receipt["stable_promotion_allowed"])
        self.assertFalse(receipt["interop"]["otel_provider_export_verified"])

    def test_registry_presence_without_qualification_is_not_reusable(self) -> None:
        receipt = self._compile(
            discovery=CapabilityRegistryDiscovery(self.registry),
        )
        self.assertEqual(receipt["capability_discovery"]["record_count"], 1)
        self.assertEqual(receipt["capability_discovery"]["qualified_reusable_count"], 0)
        self.assertTrue(receipt["local_gates"]["capability_registry_integrity"])

    def test_owner_value_pair_is_existing_court_input_not_value_proof(self) -> None:
        baseline = _measured(
            pair_id="PAIR-1",
            variant="BASELINE",
            owner_seconds=120.0,
            proof_ref="proof://baseline",
        )
        bubbles = _measured(
            pair_id="PAIR-1",
            variant="BUBBLES",
            owner_seconds=30.0,
            proof_ref="proof://bubbles",
        )
        receipt = self._compile(owner_value_records=(baseline, bubbles))
        self.assertEqual(receipt["owner_value"]["eligible_pair_count"], 1)
        self.assertFalse(receipt["owner_value"]["owner_value_proven"])
        self.assertFalse(receipt["owner_value"]["stable_promotion_allowed"])

    def test_provider_readback_must_be_native_semantic_and_proof_bound(self) -> None:
        receipt = self._compile(
            provider_readbacks={
                "weak": {
                    "provider": "example",
                    "state": "VERIFIED",
                    "provider_native": True,
                    "semantic_readback": False,
                    "proof_ref": "proof://weak",
                },
                "strong": {
                    "provider": "example-2",
                    "state": "VERIFIED",
                    "provider_native": True,
                    "semantic_readback": True,
                    "proof_ref": "proof://strong",
                },
            }
        )
        self.assertEqual(receipt["provider_readbacks"]["verified_route_count"], 1)
        self.assertEqual(receipt["provider_readbacks"]["unverified_route_count"], 1)
        self.assertFalse(receipt["provider_effect_authorized"])

    def test_browser_receipt_remains_bounded(self) -> None:
        receipt = self._compile(
            browser_receipt={
                "schema": "BUBBLES-BROWSER-RUNTIME-CANARY-1",
                "state": "HOSTED_BROWSER_RUNTIME_VERIFIED",
                "browser_runtime_verified": True,
                "javascript_execution_verified": True,
                "dom_readback_verified": True,
                "loopback_only": True,
                "external_network_target_requested": False,
                "provider_mutation_attempted": False,
                "secret_values_recorded": False,
                "receipt_sha256": "b" * 64,
            }
        )
        self.assertTrue(receipt["browser_runtime"]["hosted_browser_bounded_verified"])
        self.assertFalse(receipt["browser_runtime"]["arbitrary_computer_use_verified"])
        self.assertFalse(receipt["browser_runtime"]["external_site_authority_verified"])

    def test_workspace_integrity_failure_holds_local_core(self) -> None:
        self.workspace.path.write_text(
            '{"previous_hash":"BAD","payload":{"kind":"STAGE"},"event_hash":"BAD"}\n',
            encoding="utf-8",
        )
        receipt = self._compile()
        self.assertEqual(receipt["state"], "SOURCE_CONTROL_INCOMPLETE")
        self.assertFalse(receipt["local_gates"]["logical_workspace_integrity"])

    def test_promoted_logical_workspace_is_not_provider_sandbox(self) -> None:
        candidate = BuildCandidate(
            candidate_id="C-1",
            files={"result.txt": "ok"},
            validation_command=("python", "-c", "print('ok')"),
        )
        revision = self.workspace.stage(
            plan_digest="plan-1",
            candidate=candidate,
            parent_revision=None,
        )
        self.workspace.promote(
            revision_id=revision,
            sandbox_receipt={
                "status": "PASS",
                "result_hash": "result-hash",
                "ledger_entry_hash": "ledger-hash",
                "artifacts": {},
            },
        )
        receipt = self._compile()
        self.assertEqual(receipt["workspace"]["current_revision"], revision)
        self.assertFalse(receipt["workspace"]["provider_workspace_or_sandbox_verified"])


if __name__ == "__main__":
    unittest.main()
