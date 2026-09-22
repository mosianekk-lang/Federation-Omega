from __future__ import annotations

import unittest

from federation.capability_truth_v1 import (
    AdapterAvailability,
    AdapterObservation,
    CapabilityCurrentnessFabric,
    CapabilityRouteRequirement,
    ClaimKind,
    Maturity,
    PrivacyClass,
)
from federation.fcoa.admin_v1.fcoa_admin import (
    AdminAction,
    CapabilityRecord,
    FCOAAdminRegistry,
    FCOASuperAdmin,
    MissionAuthority,
    Scope,
)


NOW = "2026-09-22T06:30:00+00:00"


def observation(
    *,
    adapter_id: str,
    capability_id: str = "provider.read",
    provider: str = "provider",
    claim_kind: ClaimKind = ClaimKind.PROVIDER_READBACK,
    maturity: Maturity = Maturity.PROVIDER_READBACK,
    availability: AdapterAvailability = AdapterAvailability.CALLABLE,
    observed_at: str = "2026-09-22T06:00:00+00:00",
    expires_at: str = "2026-09-22T07:00:00+00:00",
    authority_classes: tuple[str, ...] = ("provider-exec",),
    effect_classes: tuple[str, ...] = ("READ_ONLY",),
    privacy: PrivacyClass = PrivacyClass.PRIVATE,
    failure_domain: str = "",
):
    return AdapterObservation(
        adapter_id=adapter_id,
        capability_id=capability_id,
        provider=provider,
        source_ref=f"proof:{adapter_id}",
        claim_kind=claim_kind,
        declared_maturity=maturity,
        observed_at=observed_at,
        expires_at=expires_at,
        availability=availability,
        authority_classes=authority_classes,
        effect_classes=effect_classes,
        privacy_ceiling=privacy,
        failure_domain=failure_domain,
        independently_verified=True,
    )


class FCOACurrentnessGateV1Tests(unittest.TestCase):
    def make_admin(self) -> FCOASuperAdmin:
        registry = FCOAAdminRegistry([
            CapabilityRecord(
                "provider.read",
                "provider-exec",
                Scope.PROVIDER,
                frozenset({"READ_ONLY"}),
                requires_credentials=True,
            ),
            CapabilityRecord(
                "internal.route",
                "alpha-omega",
                Scope.FUSE_OWNED,
                frozenset({"FUSE_INTERNAL_ADMIN"}),
            ),
        ])
        return FCOASuperAdmin(registry)

    def mission(self) -> MissionAuthority:
        return MissionAuthority(
            mission_id="m1",
            allowed_effects=frozenset({"READ_ONLY"}),
            provider_credentials_bound=frozenset({"provider-exec"}),
            provider_authorities=frozenset({"provider-exec"}),
        )

    def requirement(self, **kwargs) -> CapabilityRouteRequirement:
        values = dict(
            capability_id="provider.read",
            required_maturity=Maturity.PROVIDER_READBACK,
            authority_class="provider-exec",
            effect_class="READ_ONLY",
            privacy_class=PrivacyClass.INTERNAL,
            require_callable=True,
            require_independent_verification=True,
        )
        values.update(kwargs)
        return CapabilityRouteRequirement(**values)

    def test_live_provider_route_passes_currentness_then_authority(self):
        admin = self.make_admin()
        fabric = CapabilityCurrentnessFabric((
            observation(adapter_id="provider-exec"),
        ))
        auth, gate = admin.authorize_with_currentness(
            "provider.read",
            AdminAction.READ,
            self.mission(),
            fabric=fabric,
            requirement=self.requirement(),
            now=NOW,
            requested_effect="READ_ONLY",
        )
        self.assertTrue(gate.qualified)
        self.assertEqual(gate.selected_adapter, "provider-exec")
        self.assertEqual(auth.state, "AUTHORIZED")

    def test_stale_provider_route_cannot_authorize(self):
        admin = self.make_admin()
        fabric = CapabilityCurrentnessFabric((
            observation(
                adapter_id="provider-exec",
                observed_at="2026-09-22T04:00:00+00:00",
                expires_at="2026-09-22T05:00:00+00:00",
            ),
        ))
        auth, gate = admin.authorize_with_currentness(
            "provider.read",
            AdminAction.READ,
            self.mission(),
            fabric=fabric,
            requirement=self.requirement(),
            now=NOW,
            requested_effect="READ_ONLY",
        )
        self.assertFalse(gate.qualified)
        self.assertEqual(auth.state, "REBIND_OR_REQUALIFY")

    def test_source_only_provider_route_cannot_authorize(self):
        admin = self.make_admin()
        fabric = CapabilityCurrentnessFabric((
            observation(
                adapter_id="provider-exec",
                claim_kind=ClaimKind.IMPLEMENTATION,
                maturity=Maturity.BUILT,
                availability=AdapterAvailability.SOURCE_ONLY,
            ),
        ))
        auth, gate = admin.authorize_with_currentness(
            "provider.read",
            AdminAction.READ,
            self.mission(),
            fabric=fabric,
            requirement=self.requirement(),
            now=NOW,
            requested_effect="READ_ONLY",
        )
        self.assertFalse(gate.qualified)
        self.assertEqual(auth.state, "REBIND_OR_REQUALIFY")

    def test_currentness_does_not_replace_credentials(self):
        admin = self.make_admin()
        fabric = CapabilityCurrentnessFabric((observation(adapter_id="provider-exec"),))
        no_creds = MissionAuthority(
            mission_id="m2",
            allowed_effects=frozenset({"READ_ONLY"}),
            provider_authorities=frozenset({"provider-exec"}),
        )
        auth, gate = admin.authorize_with_currentness(
            "provider.read",
            AdminAction.READ,
            no_creds,
            fabric=fabric,
            requirement=self.requirement(),
            now=NOW,
            requested_effect="READ_ONLY",
        )
        self.assertTrue(gate.qualified)
        self.assertEqual(auth.state, "REBIND_REQUIRED")

    def test_currentness_does_not_replace_provider_authority(self):
        admin = self.make_admin()
        fabric = CapabilityCurrentnessFabric((observation(adapter_id="provider-exec"),))
        no_authority = MissionAuthority(
            mission_id="m3",
            allowed_effects=frozenset({"READ_ONLY"}),
            provider_credentials_bound=frozenset({"provider-exec"}),
        )
        auth, gate = admin.authorize_with_currentness(
            "provider.read",
            AdminAction.READ,
            no_authority,
            fabric=fabric,
            requirement=self.requirement(),
            now=NOW,
            requested_effect="READ_ONLY",
        )
        self.assertTrue(gate.qualified)
        self.assertEqual(auth.state, "AUTHORITY_REQUIRED")

    def test_failure_domain_exclusion_selects_alternate_provider(self):
        admin = self.make_admin()
        fabric = CapabilityCurrentnessFabric((
            observation(adapter_id="provider-exec", provider="google", failure_domain="google"),
            observation(adapter_id="microsoft-read", provider="microsoft", failure_domain="microsoft"),
        ))
        gate = admin.currentness_gate(
            fabric,
            self.requirement(excluded_failure_domains=("google",)),
            now=NOW,
        )
        self.assertTrue(gate.qualified)
        self.assertEqual(gate.selected_adapter, "microsoft-read")
        self.assertEqual(gate.provider, "microsoft")

    def test_missing_observation_is_not_absent_before_census(self):
        admin = self.make_admin()
        gate = admin.currentness_gate(
            CapabilityCurrentnessFabric(),
            self.requirement(),
            now=NOW,
            census_complete=False,
        )
        self.assertFalse(gate.qualified)
        self.assertEqual(gate.state, "CENSUS_REQUIRED")

    def test_missing_observation_is_harvest_after_complete_census(self):
        admin = self.make_admin()
        gate = admin.currentness_gate(
            CapabilityCurrentnessFabric(),
            self.requirement(),
            now=NOW,
            census_complete=True,
        )
        self.assertFalse(gate.qualified)
        self.assertEqual(gate.state, "HARVEST_OR_BUILD")

    def test_internal_fuse_authority_remains_separate(self):
        admin = self.make_admin()
        fabric = CapabilityCurrentnessFabric((
            observation(
                adapter_id="alpha-omega",
                capability_id="internal.route",
                claim_kind=ClaimKind.BINDING,
                maturity=Maturity.BOUND,
                authority_classes=("FUSE_INTERNAL_ADMIN",),
                effect_classes=("FUSE_INTERNAL_ADMIN",),
            ),
        ))
        auth, gate = admin.authorize_with_currentness(
            "internal.route",
            AdminAction.ROUTE,
            MissionAuthority(
                mission_id="m4",
                allowed_effects=frozenset({"FUSE_INTERNAL_ADMIN"}),
            ),
            fabric=fabric,
            requirement=CapabilityRouteRequirement(
                "internal.route",
                required_maturity=Maturity.BOUND,
                authority_class="FUSE_INTERNAL_ADMIN",
                effect_class="FUSE_INTERNAL_ADMIN",
                privacy_class=PrivacyClass.INTERNAL,
            ),
            now=NOW,
            requested_effect="FUSE_INTERNAL_ADMIN",
        )
        self.assertEqual(auth.state, "AUTHORIZED")
        self.assertTrue(gate.qualified)


if __name__ == "__main__":
    unittest.main()
