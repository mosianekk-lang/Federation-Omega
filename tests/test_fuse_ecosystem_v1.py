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
    DYNAMIC_REROUTE_TRIGGERS,
    DynamicRerouteTrigger,
    DynamicRouteContext,
    DynamicRouteElectionState,
    EcosystemMissionSpec,
    EcosystemPlane,
    EcosystemServiceSpec,
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


    def test_dynamic_trigger_set_covers_material_route_changes(self):
        required = {
            DynamicRerouteTrigger.CHECKPOINT,
            DynamicRerouteTrigger.CURRENTNESS_CHANGED,
            DynamicRerouteTrigger.PROVIDER_HEALTH_CHANGED,
            DynamicRerouteTrigger.CAPABILITY_QUALIFIED,
            DynamicRerouteTrigger.CONSTRAINT,
            DynamicRerouteTrigger.FAILURE,
            DynamicRerouteTrigger.LEASE_FENCE_CHANGED,
            DynamicRerouteTrigger.OWNER_PRIORITY_CHANGED,
        }
        self.assertEqual(required, set(DYNAMIC_REROUTE_TRIGGERS))

    def test_checkpoint_keeps_current_when_route_remains_strongest(self):
        fabric=CapabilityCurrentnessFabric((
            obs("identity.resolve","google","google",effects=("READ_ONLY",),authority=("READ",)),
            obs("identity.resolve","microsoft","microsoft",effects=("READ_ONLY",),authority=("READ",)),
            obs("mail.telemetry","gmail","google",effects=("READ_ONLY",),authority=("READ",)),
            obs("mail.telemetry","outlook","microsoft",effects=("READ_ONLY",),authority=("READ",)),
            obs("calendar.read","gcal","google",effects=("READ_ONLY",),authority=("READ",)),
            obs("calendar.read","ocal","microsoft",effects=("READ_ONLY",),authority=("READ",)),
        ))
        kernel=FuseEcosystemKernel(fabric)
        mission=EcosystemMissionSpec(
            "dyn-1",("communications.enterprise",),
            authority_class="READ",effect_class="READ_ONLY",
            independent_backup_required=True,
        )
        prior=kernel.compile(mission,now=NOW)
        election=kernel.re_elect(
            mission,
            now=NOW,
            context=DynamicRouteContext(DynamicRerouteTrigger.CHECKPOINT,route_epoch=7),
            prior_plan=prior,
        )
        self.assertEqual(DynamicRouteElectionState.KEEP_CURRENT,election.state)
        self.assertEqual(8,election.route_epoch)
        self.assertEqual((),election.changed_capabilities)
        self.assertTrue(election.preserve_mission_identity)
        self.assertTrue(election.preserve_checkpoint)
        self.assertTrue(election.preserve_fence)

    def test_failure_domain_exclusion_reselects_alternate_route(self):
        fabric=CapabilityCurrentnessFabric((
            obs("identity.resolve","google","google",effects=("READ_ONLY",),authority=("READ",)),
            obs("identity.resolve","microsoft","microsoft",effects=("READ_ONLY",),authority=("READ",)),
        ))
        services={
            "test.identity": EcosystemServiceSpec(
                "test.identity",
                EcosystemPlane.COMMUNICATION,
                ("identity.resolve",),
                required_maturity=Maturity.PROVIDER_READBACK,
                min_failure_domains=1,
            )
        }
        kernel=FuseEcosystemKernel(fabric,services=services)
        mission=EcosystemMissionSpec(
            "dyn-2",("test.identity",),
            authority_class="READ",effect_class="READ_ONLY",
        )
        prior=kernel.compile(mission,now=NOW)
        prior_primary=prior.selections[0].primary_adapter
        failed_domain="microsoft" if prior_primary=="microsoft" else "google"
        election=kernel.re_elect(
            mission,
            now=NOW,
            context=DynamicRouteContext(
                DynamicRerouteTrigger.FAILURE,
                route_epoch=2,
                excluded_failure_domains={
                    "identity.resolve":(failed_domain,),
                },
            ),
            prior_plan=prior,
        )
        self.assertTrue(election.plan.executable)
        self.assertEqual(DynamicRouteElectionState.RESELECTED,election.state)
        self.assertEqual(("identity.resolve",),election.changed_capabilities)
        self.assertNotEqual(
            prior_primary,
            election.plan.selections[0].primary_adapter,
        )

    def test_no_qualified_route_enters_durable_hold_without_losing_identity(self):
        kernel=FuseEcosystemKernel(CapabilityCurrentnessFabric())
        mission=EcosystemMissionSpec("dyn-3",("creative.studio",))
        election=kernel.re_elect(
            mission,
            now=NOW,
            context=DynamicRouteContext(DynamicRerouteTrigger.CURRENTNESS_CHANGED,route_epoch=1),
        )
        self.assertEqual(DynamicRouteElectionState.DURABLE_HOLD,election.state)
        self.assertEqual("dyn-3",election.mission_id)
        self.assertFalse(election.plan.executable)
        self.assertTrue(election.preserve_mission_identity)

    def test_terminal_mission_is_never_rerouted(self):
        kernel=FuseEcosystemKernel(CapabilityCurrentnessFabric())
        mission=EcosystemMissionSpec("dyn-4",("creative.studio",))
        prior=kernel.compile(mission,now=NOW)
        election=kernel.re_elect(
            mission,
            now=NOW,
            context=DynamicRouteContext(
                DynamicRerouteTrigger.PROVIDER_HEALTH_CHANGED,
                route_epoch=12,
                nonterminal=False,
            ),
            prior_plan=prior,
        )
        self.assertEqual(DynamicRouteElectionState.TERMINAL_NOOP,election.state)
        self.assertEqual(12,election.route_epoch)

    def test_dynamic_reroute_does_not_grant_missing_effect_authority(self):
        fabric=CapabilityCurrentnessFabric((
            obs("identity.resolve","g","google",effects=("READ_ONLY",),authority=("READ",)),
            obs("identity.resolve","m","microsoft",effects=("READ_ONLY",),authority=("READ",)),
            obs("mail.telemetry","gm","google",effects=("READ_ONLY",),authority=("READ",)),
            obs("mail.telemetry","om","microsoft",effects=("READ_ONLY",),authority=("READ",)),
            obs("calendar.read","gc","google",effects=("READ_ONLY",),authority=("READ",)),
            obs("calendar.read","oc","microsoft",effects=("READ_ONLY",),authority=("READ",)),
        ))
        kernel=FuseEcosystemKernel(fabric)
        mission=EcosystemMissionSpec(
            "dyn-5",("communications.enterprise",),
            authority_class="SEND",effect_class="EXTERNAL_SEND",
            independent_backup_required=True,
        )
        election=kernel.re_elect(
            mission,
            now=NOW,
            context=DynamicRouteContext(DynamicRerouteTrigger.CONSTRAINT),
        )
        self.assertEqual(DynamicRouteElectionState.DURABLE_HOLD,election.state)
        self.assertFalse(election.plan.executable)


if __name__ == "__main__":
    unittest.main()
