from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from federation.capability_truth_v1 import (
    AdapterAvailability,
    AdapterObservation,
    CapabilityCurrentnessFabric,
    ClaimKind,
    Maturity,
    PrivacyClass,
)
from federation.fuse_ecosystem_v1 import (
    EcosystemMissionSpec,
    FUSE_ECOSYSTEM_SERVICES,
    FuseEcosystemKernel,
)
from federation.fuse_unified_service_catalog_v1 import (
    build_unified_kernel,
    build_unified_service_catalog,
    resolve_unified_service,
)


NOW = "2026-10-01T10:00:00+00:00"


def workflow_observations() -> tuple[AdapterObservation, ...]:
    return tuple(
        AdapterObservation(
            adapter_id=f"workflow-test-{index}",
            capability_id=capability,
            provider="test-provider",
            source_ref=f"test-receipt:{index}",
            claim_kind=ClaimKind.PROVIDER_READBACK,
            declared_maturity=Maturity.PROVIDER_READBACK,
            observed_at="2026-10-01T09:00:00+00:00",
            expires_at="2026-10-01T11:00:00+00:00",
            availability=AdapterAvailability.CALLABLE,
            authority_classes=("A1_INTERNAL",),
            effect_classes=("NO_EFFECT",),
            privacy_ceiling=PrivacyClass.INTERNAL,
            failure_domain="test-workflow",
            independently_verified=True,
        )
        for index, capability in enumerate(("workflow.compose", "workflow.trigger", "workflow.connector"))
    )


class UnifiedServiceCatalogTests(unittest.TestCase):
    def test_catalog_reconciles_actual_source_against_all_contract_ids(self):
        contract = json.loads(
            (Path(__file__).resolve().parents[1] / "config" / "fuse-unified-capability-fabric-v1.json")
            .read_text(encoding="utf-8")
        )
        catalog = build_unified_service_catalog()
        self.assertEqual([row["service_id"] for row in catalog["services"]], contract["registered_services"])
        self.assertEqual(catalog["counts"], {
            "registered_services": 35,
            "source_supported": 16,
            "source_missing": 19,
            "legacy_aliases": 1,
            "runtime_assessed": 0,
        })
        family_by_id = {service: family for family, services in contract["capability_families"].items() for service in services}
        self.assertTrue(all(row["family"] == family_by_id[row["service_id"]] for row in catalog["services"]))

    def test_source_projection_never_promotes_runtime_or_fabricates_dependencies(self):
        catalog = build_unified_service_catalog()
        self.assertTrue(catalog["projection_only"])
        self.assertFalse(catalog["sovereign_controller_created"])
        for row in catalog["services"]:
            self.assertEqual(row["runtime_readiness"], "NOT_ASSESSED")
            self.assertIsNone(row["callable_now"])
            if not row["source_supported"]:
                self.assertEqual(row["source_state"], "UNRESOLVED_DEFINITION")
                self.assertIsNone(row["required_capabilities"])
                self.assertIsNone(row["required_maturity"])
                self.assertIsNone(row["implementation_service_id"])
        encoded = json.dumps(catalog)
        for private_marker in ("/workspace/", "C:\\\\", "source_ref", "observed_at", "expires_at", "access_token"):
            self.assertNotIn(private_marker, encoded)

    def test_alias_preserves_exact_definition_and_does_not_mutate_legacy_catalog(self):
        original = FUSE_ECOSYSTEM_SERVICES["enterprise.workflow"]
        before = dict(FUSE_ECOSYSTEM_SERVICES)
        resolved = resolve_unified_service("workflow.enterprise")
        self.assertEqual(resolved, replace(original, service_id="workflow.enterprise"))
        alias = next(row for row in build_unified_service_catalog()["services"] if row["service_id"] == "workflow.enterprise")
        self.assertEqual(alias["alias_of"], "enterprise.workflow")
        self.assertEqual(alias["source_state"], "LEGACY_ALIAS")
        self.assertEqual(before, FUSE_ECOSYSTEM_SERVICES)

    def test_canonical_alias_compiles_through_existing_kernel_with_same_selections(self):
        fabric = CapabilityCurrentnessFabric(workflow_observations())
        legacy = FuseEcosystemKernel(fabric).compile(EcosystemMissionSpec("workflow", ("enterprise.workflow",)), now=NOW)
        unified = build_unified_kernel(fabric)
        self.assertIs(type(unified), FuseEcosystemKernel)
        canonical = unified.compile(EcosystemMissionSpec("workflow", ("workflow.enterprise",)), now=NOW)
        self.assertTrue(canonical.executable)
        self.assertEqual(canonical.selections, legacy.selections)
        self.assertEqual(canonical, replace(legacy, service_ids=("workflow.enterprise",)))
        self.assertEqual(unified.compile(EcosystemMissionSpec("workflow", ("enterprise.workflow",)), now=NOW), legacy)

    def test_alias_retains_currentness_authority_privacy_and_maturity_gates(self):
        for changes in (
            {"expires_at": "2026-10-01T09:30:00+00:00"},
            {"authority_classes": ("OTHER_AUTHORITY",)},
            {"effect_classes": ("READ_ONLY",)},
            {"privacy_ceiling": PrivacyClass.PUBLIC},
            {"claim_kind": ClaimKind.IMPLEMENTATION, "declared_maturity": Maturity.BUILT},
            {"availability": AdapterAvailability.SOURCE_ONLY},
        ):
            with self.subTest(changes=changes):
                observations = tuple(replace(row, **changes) for row in workflow_observations())
                plan = build_unified_kernel(CapabilityCurrentnessFabric(observations)).compile(
                    EcosystemMissionSpec("workflow", ("workflow.enterprise",)), now=NOW
                )
                self.assertFalse(plan.executable)
                self.assertEqual(len(plan.missing_capabilities), 3)
        empty = build_unified_kernel(CapabilityCurrentnessFabric()).compile(
            EcosystemMissionSpec("workflow", ("workflow.enterprise",)), now=NOW
        )
        self.assertFalse(empty.executable)

    def test_undefined_and_unknown_services_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "UNIFIED_SERVICE_DEFINITION_MISSING:runtime.application"):
            resolve_unified_service("runtime.application")
        with self.assertRaisesRegex(ValueError, "UNIFIED_SERVICE_UNKNOWN:invented.service"):
            resolve_unified_service("invented.service")
        kernel = build_unified_kernel(CapabilityCurrentnessFabric())
        for service_id in ("runtime.application", "invented.service"):
            with self.subTest(service_id=service_id), self.assertRaisesRegex(ValueError, "ECOSYSTEM_SERVICE_UNKNOWN"):
                kernel.compile(EcosystemMissionSpec("unknown", (service_id,)), now=NOW)

    def test_ambiguous_families_cannot_be_presented_as_a_valid_catalog(self):
        broken = {
            "schema": "FUSE_UNIFIED_CAPABILITY_FABRIC_V1",
            "registered_services": ["research.deep"],
            "service_count": 1,
            "capability_families": {"FIRST": ["research.deep"], "SECOND": ["research.deep"]},
        }
        with patch("federation.fuse_unified_service_catalog_v1.Path.read_text", return_value=json.dumps(broken)):
            with self.assertRaisesRegex(ValueError, "UNIFIED_SERVICE_FAMILY_AMBIGUOUS"):
                build_unified_service_catalog()


if __name__ == "__main__":
    unittest.main()
