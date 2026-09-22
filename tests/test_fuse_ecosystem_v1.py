from __future__ import annotations

import unittest

from federation.capability_truth_v1 import (
    AdapterObservation,
    AdapterAvailability,
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


NOW = "2026-09-22T08:00:00+00:00"


def obs(capability, adapter, domain, *, provider="provider", effects=("NO_EFFECT",), authority=("A1_INTERNAL",)):
    return AdapterObservation(
        adapter_id=adapter,
        capability_id=capability,
        provider=provider,
        source_ref=f"proof:{adapter}",
        claim_kind=ClaimKind.PROVIDER_READBACK,
        declared_maturity=Maturity.PROVIDER_READBACK,
        observed_at="2026-09-22T07:00:00+00:00",
        expires_at="2026-09-22T09:00:00+00:00",
        availability=AdapterAvailability.CALLABLE,
        authority_classes=authority,
        effect_classes=effects,
        privacy_ceiling=PrivacyClass.PRIVATE,
        failure_domain=domain,
        independently_verified=True,
    )


class FuseEcosystemV1Tests(unittest.TestCase):
    def test_service_catalog_has_full_ecosystem_planes(self):
        self.assertGreaterEqual(len(FUSE_ECOSYSTEM_SERVICES), 16)
        ids=set(FUSE_ECOSYSTEM_SERVICES)
        for required in {
            "research.deep","agent.action","agent.multi","model.council",
            "code.agentic","creative.studio","enterprise.workflow",
            "memory.continuum","device.computer","security.agent",
            "observability.agent","marketplace.capability","artifact.workspace",
        }:
            self.assertIn(required, ids)

    def test_model_council_requires_failure_domain_diversity(self):
        fabric=CapabilityCurrentnessFabric((
            obs("model.route","openai-route","openai"),
            obs("model.route","gemini-route","google"),
            obs("model.evaluate","eval-a","local"),
            obs("model.evaluate","eval-b","google"),
            obs("model.disagreement","judge-a","local"),
            obs("model.disagreement","judge-b","google"),
        ))
        plan=FuseEcosystemKernel(fabric).compile(
            EcosystemMissionSpec(
                "m1",("model.council",),
                independent_backup_required=False,
            ),
            now=NOW,
        )
        self.assertTrue(plan.executable)
        self.assertEqual(set(),set(plan.missing_capabilities))
        self.assertTrue(all(len(x.failure_domains)>=2 for x in plan.selections))

    def test_missing_live_capability_is_nonexecutable_not_fabricated(self):
        plan=FuseEcosystemKernel(CapabilityCurrentnessFabric()).compile(
            EcosystemMissionSpec("m2",("creative.studio",)),
            now=NOW,
        )
        self.assertFalse(plan.executable)
        self.assertIn("creative.design",plan.missing_capabilities)

    def test_source_only_cannot_satisfy_live_service(self):
        source=AdapterObservation(
            adapter_id="source",
            capability_id="device.screen.read",
            provider="local",
            source_ref="source:file",
            claim_kind=ClaimKind.IMPLEMENTATION,
            declared_maturity=Maturity.BUILT,
            observed_at="2026-09-22T07:00:00+00:00",
            expires_at="2026-09-22T09:00:00+00:00",
            availability=AdapterAvailability.SOURCE_ONLY,
            authority_classes=("A1_INTERNAL",),
            effect_classes=("NO_EFFECT",),
            privacy_ceiling=PrivacyClass.PRIVATE,
        )
        input_obs=obs("device.input","input","local")
        plan=FuseEcosystemKernel(CapabilityCurrentnessFabric((source,input_obs))).compile(
            EcosystemMissionSpec("m3",("device.computer",)),
            now=NOW,
        )
        self.assertFalse(plan.executable)
        self.assertIn("device.screen.read",plan.missing_capabilities)

    def test_effect_and_authority_are_requirements_not_grants(self):
        fabric=CapabilityCurrentnessFabric((
            obs("identity.resolve","g","google",effects=("READ_ONLY",),authority=("READ",)),
            obs("identity.resolve","m","microsoft",effects=("READ_ONLY",),authority=("READ",)),
            obs("mail.telemetry","gm","google",effects=("READ_ONLY",),authority=("READ",)),
            obs("mail.telemetry","om","microsoft",effects=("READ_ONLY",),authority=("READ",)),
            obs("calendar.read","gc","google",effects=("READ_ONLY",),authority=("READ",)),
            obs("calendar.read","oc","microsoft",effects=("READ_ONLY",),authority=("READ",)),
        ))
        plan=FuseEcosystemKernel(fabric).compile(
            EcosystemMissionSpec(
                "m4",("communications.enterprise",),
                authority_class="SEND",
                effect_class="EXTERNAL_SEND",
                independent_backup_required=True,
            ),
            now=NOW,
        )
        self.assertFalse(plan.executable)
        self.assertTrue(plan.missing_capabilities)

    def test_provider_names_are_not_service_ids(self):
        ids=set(FUSE_ECOSYSTEM_SERVICES)
        for vendor in {"openai","google","microsoft","anthropic","perplexity","canva","adobe"}:
            self.assertNotIn(vendor,ids)

    def test_unknown_service_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"ECOSYSTEM_SERVICE_UNKNOWN"):
            FuseEcosystemKernel(CapabilityCurrentnessFabric()).compile(
                EcosystemMissionSpec("m5",("unknown.service",)),
                now=NOW,
            )


if __name__ == "__main__":
    unittest.main()
