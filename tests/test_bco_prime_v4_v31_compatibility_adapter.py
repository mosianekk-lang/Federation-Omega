import copy
import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from benchmarking.cfbe_omega.bco_prime_v4_v31_compatibility_adapter import (
    BcoPrimeV4CompatibilityAdapter,
    SOURCE_MAIN_SHA,
    V31_REGISTRY_SHA256,
    V4CompatibilityContractError,
    V4CompatibilityDependencyError,
)
from benchmarking.cfbe_omega.bco_prime_successor_v3_1 import SuccessorRegistryV31


def canonical_digest(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def decision_payload():
    return {
        "source_head_sha": SOURCE_MAIN_SHA,
        "observation": {
            "mission_id": "MISSION-V4-COMPAT-001",
            "objective_sha256": "1" * 64,
            "graph": {
                "node_count": 12,
                "edge_count": 10,
                "ready_parallel_count": 5,
                "shared_state_key_count": 1,
                "deterministic_fraction": 0.75,
                "uncertainty": 0.45,
                "evidence_conflict": 0.15,
                "consequential_fraction": 0.0,
            },
            "meta_state": {
                "confidence": 0.8,
                "evidence_coverage": 0.85,
                "contradiction_pressure": 0.1,
                "novelty": 0.45,
                "progress": 0.7,
                "plan_stability": 0.75,
                "context_freshness": 0.9,
                "resource_pressure": 0.3,
                "repeated_failure_count": 0,
            },
            "effect_class": "NO_EFFECT",
            "reversible": True,
            "exact_authority": True,
            "provider_runtime_available": True,
            "active_streams": 2,
            "owner_burden": 0.2,
            "architecture_overlap": 0.2,
            "frontier_gap": 0.3,
        },
        "strategies": [
            {
                "strategy_id": "S1",
                "failure_domain": "git",
                "expected_quality": 0.9,
                "evidence_strength": 0.9,
                "reliability": 0.9,
                "reversibility": 1.0,
                "information_gain": 0.8,
                "failure_domain_diversity": 0.8,
                "latency_cost": 0.2,
                "monetary_cost": 0.0,
                "owner_burden": 0.1,
                "risk": 0.1,
            }
        ],
        "capabilities": [
            {
                "capability_id": "GITHUB",
                "interfaces": ["source.read"],
                "providers": ["github"],
                "failure_domain": "github",
                "state": "LIVE_VERIFIED",
                "proof_age_hours": 2.0,
                "eligible_missions": 10,
                "used_missions": 8,
                "successful_uses": 8,
                "reliability": 0.92,
                "owner_burden_reduction": 0.85,
                "cost_efficiency": 0.9,
                "failure_domain_uniqueness": 0.8,
                "strategic_option_value": 0.85,
                "maintenance_burden": 0.15,
                "context_burden": 0.15,
                "authority_ready": True,
                "evidence_refs": ["proof:github"],
            },
            {
                "capability_id": "DRIVE",
                "interfaces": ["memory.read"],
                "providers": ["google"],
                "failure_domain": "google",
                "state": "LIVE_VERIFIED",
                "proof_age_hours": 1.0,
                "eligible_missions": 8,
                "used_missions": 7,
                "successful_uses": 7,
                "reliability": 0.95,
                "owner_burden_reduction": 0.9,
                "cost_efficiency": 0.9,
                "failure_domain_uniqueness": 0.9,
                "strategic_option_value": 0.8,
                "maintenance_burden": 0.1,
                "context_burden": 0.1,
                "authority_ready": True,
            },
        ],
        "utilization": [
            {
                "capability_id": "GITHUB",
                "relevance": 1.0,
                "used": True,
                "current_readback_available": True,
                "current_readback_used": True,
            },
            {"capability_id": "DRIVE", "relevance": 0.8, "used": True},
        ],
        "future_demand": [
            {
                "demand_id": "OP",
                "horizon": "OPERATIONAL",
                "required_interfaces": ["source.read"],
                "probability": 0.9,
                "value": 0.9,
                "urgency": 0.8,
                "option_value": 0.8,
                "dependency_centrality": 0.7,
                "evidence_strength": 0.9,
                "uncertainty": 0.3,
                "evidence_refs": ["demand:op"],
            },
            {
                "demand_id": "STRAT",
                "horizon": "STRATEGIC",
                "required_interfaces": ["memory.read"],
                "probability": 0.8,
                "value": 0.8,
                "urgency": 0.6,
                "option_value": 0.9,
                "dependency_centrality": 0.7,
                "evidence_strength": 0.8,
                "uncertainty": 0.8,
            },
        ],
    }


def genome_payload():
    return {
        "records": [
            {
                "features": ["source-drift", "manual"],
                "mission_sequence": ["ASK_OWNER"],
                "realized_value": 0.2,
                "reliability": 0.4,
                "evidence_refs": ["proof:weak"],
            },
            {
                "features": ["source-drift", "proof-repair", "github"],
                "mission_sequence": ["REFRESH_SOURCE", "MINIMAL_PATCH", "AIRLOCK", "READBACK"],
                "realized_value": 0.95,
                "reliability": 0.95,
                "evidence_refs": ["proof:strong"],
            },
        ],
        "features": ["source-drift", "proof-repair", "github"],
    }


class AdapterTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.adapter = BcoPrimeV4CompatibilityAdapter(Path(self.temp.name))


class UnitContractTests(AdapterTestCase):
    def test_health_is_additive_and_authority_closed(self):
        health = self.adapter.health()
        self.assertEqual(health["canonical_core_count"], 100)
        self.assertTrue(health["canonical_core_invariant_preserved"])
        self.assertEqual(health["v4_operation_count"], 3)
        self.assertFalse(health["dispatchAuthorized"])
        self.assertFalse(health["providerEffectAuthorized"])
        self.assertFalse(health["stablePromotionAuthorized"])
        self.assertEqual(health["source_main_sha"], SOURCE_MAIN_SHA)

    def test_manifest_binds_exact_sources_and_zero_new_sovereign_planes(self):
        manifest = self.adapter.manifest()
        component = manifest["components"]["anticipatory_institution_v4"]
        self.assertEqual(component["sha256"], "3cada8deb311b9fcefe04990c0063086b0e623884591d23fe3359d258c04d0c8")
        self.assertEqual(component["manifest"]["new_schedulers"], 0)
        self.assertEqual(component["manifest"]["new_memory_roots"], 0)
        self.assertTrue(manifest["authorityBoundary"]["decisionSupportOnly"])
        self.assertFalse(manifest["authorityBoundary"]["inheritedAuthorityExpanded"])

    def test_manifest_hash_is_self_consistent(self):
        manifest = self.adapter.manifest()
        expected = manifest.pop("manifest_sha256")
        self.assertEqual(canonical_digest(manifest), expected)


class IntegrationTests(AdapterTestCase):
    def test_v31_operation_is_delegated_without_receipt_wrapping(self):
        through_adapter = self.adapter.execute("BCO-PRIME-V3-1-MANIFEST", {})
        direct = self.adapter.base.execute("BCO-PRIME-V3-1-MANIFEST", {})
        self.assertEqual(through_adapter, direct)
        self.assertEqual(through_adapter["schema"], "BCO_PRIME_SUCCESSOR_EXECUTION_RECEIPT_V3_1")
        self.assertEqual(through_adapter["namespace"], "successor_v3_1")

    def test_v4_decision_compiles_through_v31_surface(self):
        receipt = self.adapter.execute("BCO-PRIME-V4-COMPILE-DECISION", decision_payload())
        output = receipt["output"]
        self.assertEqual(output["schema"], "BCO_PRIME_ANTICIPATORY_INSTITUTION_V4")
        self.assertEqual(output["mode"], "SHADOW_ONLY")
        self.assertFalse(output["dispatch_authorized"])
        self.assertFalse(output["external_effect_authorized"])
        self.assertFalse(output["stable_self_promotion_allowed"])
        self.assertFalse(receipt["providerEffectAuthorized"])

    def test_genome_bridge_returns_preparation_not_execution(self):
        receipt = self.adapter.execute("BCO-PRIME-V4-STRATEGIC-GENOME-RECOMMEND", genome_payload())
        output = receipt["output"]
        self.assertIsNotNone(output["selected_pattern_id"])
        self.assertEqual(
            output["preparatory_mission_sequence"],
            ["REFRESH_SOURCE", "MINIMAL_PATCH", "AIRLOCK", "READBACK"],
        )
        self.assertFalse(output["execution_authorized"])
        self.assertFalse(output["provider_effect_authorized"])


class InjectedRegistryIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = SuccessorRegistryV31(self.root / "base")

    def test_injected_registry_requires_exact_source_attestation(self):
        with self.assertRaisesRegex(V4CompatibilityDependencyError, "V31_REGISTRY_ATTESTATION_REQUIRED"):
            BcoPrimeV4CompatibilityAdapter(self.root / "adapter", base_registry=self.base)

    def test_exact_attested_injected_registry_is_accepted(self):
        adapter = BcoPrimeV4CompatibilityAdapter(
            self.root / "adapter",
            base_registry=self.base,
            base_registry_sha256=V31_REGISTRY_SHA256,
        )
        self.assertEqual(adapter.health()["base_registry_source_sha256"], V31_REGISTRY_SHA256)

    def test_tampered_injected_surface_is_rejected(self):
        base = self.base

        class TamperedRegistry:
            def health(self):
                value = base.health()
                value["canonical_core_count"] = 99
                return value

            def manifest(self):
                return base.manifest()

            def execute(self, operation, payload=None):
                return base.execute(operation, payload)

        with self.assertRaisesRegex(V4CompatibilityDependencyError, "V31_REGISTRY_SURFACE_MISMATCH"):
            BcoPrimeV4CompatibilityAdapter(
                self.root / "adapter",
                base_registry=TamperedRegistry(),
                base_registry_sha256=V31_REGISTRY_SHA256,
            )

class DeterminismTests(AdapterTestCase):
    def test_decision_receipt_is_deterministic(self):
        left = self.adapter.execute("BCO-PRIME-V4-COMPILE-DECISION", decision_payload())
        right_payload = decision_payload()
        right_payload["capabilities"] = list(reversed(right_payload["capabilities"]))
        right_payload["utilization"] = list(reversed(right_payload["utilization"]))
        right = self.adapter.execute("BCO-PRIME-V4-COMPILE-DECISION", right_payload)
        self.assertEqual(left["output"]["receipt_sha256"], right["output"]["receipt_sha256"])
        self.assertNotEqual(left["input_sha256"], right["input_sha256"])

    def test_identical_genome_request_has_identical_receipt(self):
        self.assertEqual(
            self.adapter.execute("BCO-PRIME-V4-STRATEGIC-GENOME-RECOMMEND", genome_payload()),
            self.adapter.execute("BCO-PRIME-V4-STRATEGIC-GENOME-RECOMMEND", genome_payload()),
        )

    def test_v4_receipt_hash_is_self_consistent(self):
        receipt = self.adapter.execute("BCO-PRIME-V4-MANIFEST", {})
        expected = receipt.pop("receipt_sha256")
        self.assertEqual(canonical_digest(receipt), expected)


class FailureFirstTests(AdapterTestCase):
    def test_unknown_operation_fails_closed_in_inherited_registry(self):
        with self.assertRaisesRegex(Exception, "unknown operation"):
            self.adapter.execute("BCO-PRIME-NOT-REGISTERED", {})

    def test_non_mapping_payload_is_rejected(self):
        with self.assertRaisesRegex(V4CompatibilityContractError, "payload must be an object"):
            self.adapter.execute("BCO-PRIME-V4-MANIFEST", [])

    def test_missing_compile_field_is_rejected(self):
        payload = decision_payload()
        del payload["observation"]
        with self.assertRaisesRegex(V4CompatibilityContractError, "missing fields: observation"):
            self.adapter.execute("BCO-PRIME-V4-COMPILE-DECISION", payload)

    def test_unknown_nested_field_is_rejected(self):
        payload = decision_payload()
        payload["observation"]["surprise"] = "not admitted"
        with self.assertRaisesRegex(V4CompatibilityContractError, "unknown fields: surprise"):
            self.adapter.execute("BCO-PRIME-V4-COMPILE-DECISION", payload)

    def test_underuse_forces_hold(self):
        payload = decision_payload()
        payload["utilization"][0]["used"] = False
        receipt = self.adapter.execute("BCO-PRIME-V4-COMPILE-DECISION", payload)
        self.assertEqual(receipt["output"]["mode"], "HOLD_CAPABILITY_UNDERUSE")
        self.assertIn(
            "REPAIR_CAPABILITY_UNDERUSE_BEFORE_TERMINALITY",
            receipt["output"]["preparatory_actions"],
        )

    def test_quadratic_capability_input_is_bounded(self):
        payload = decision_payload()
        payload["capabilities"] = [copy.deepcopy(payload["capabilities"][0]) for _ in range(513)]
        with self.assertRaisesRegex(V4CompatibilityContractError, "item count must be in range"):
            self.adapter.execute("BCO-PRIME-V4-COMPILE-DECISION", payload)


class SecurityBoundaryTests(AdapterTestCase):
    def test_authority_request_is_rejected_at_any_depth(self):
        payload = decision_payload()
        payload["observation"]["providerEffectAuthorized"] = True
        with self.assertRaisesRegex(V4CompatibilityContractError, "authority or executable effect rejected"):
            self.adapter.execute("BCO-PRIME-V4-COMPILE-DECISION", payload)

    def test_non_finite_number_is_rejected(self):
        payload = decision_payload()
        payload["capabilities"][0]["reliability"] = float("nan")
        with self.assertRaisesRegex(V4CompatibilityContractError, "non-finite number"):
            self.adapter.execute("BCO-PRIME-V4-COMPILE-DECISION", payload)

    def test_bool_is_not_accepted_as_integer(self):
        payload = decision_payload()
        payload["observation"]["active_streams"] = True
        with self.assertRaisesRegex(V4CompatibilityContractError, "must be an integer"):
            self.adapter.execute("BCO-PRIME-V4-COMPILE-DECISION", payload)

    def test_path_traversal_is_still_rejected_by_v31(self):
        payload = {
            "scan_root": "../escape",
            "source_id": "source",
            "tenant_id": "tenant",
            "matter_id": "matter",
            "baseline_sha256": "a" * 64,
            "dependency_licenses": {},
            "cancelled": False,
        }
        with self.assertRaisesRegex(Exception, "path traversal rejected"):
            self.adapter.execute("BCO-PRIME-V3-1-INCREMENTAL-SCAN", payload)

    def test_external_signal_is_observed_but_never_authorizes_effect(self):
        payload = decision_payload()
        payload["capabilities"][0]["external_effect"] = True
        payload["capabilities"][0]["authority_ready"] = False
        payload["future_demand"][0]["external_effect"] = True
        receipt = self.adapter.execute("BCO-PRIME-V4-COMPILE-DECISION", payload)
        github = next(
            item for item in receipt["output"]["capability_opportunities"]
            if item["capability_id"] == "GITHUB"
        )
        self.assertEqual(github["recommended_action"], "HOLD_PROVIDER")
        self.assertFalse(receipt["output"]["external_effect_authorized"])
        self.assertFalse(receipt["providerEffectAuthorized"])


if __name__ == "__main__":
    unittest.main()
