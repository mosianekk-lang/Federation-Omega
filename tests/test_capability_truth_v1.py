from __future__ import annotations

import unittest

from federation.capability_truth_v1 import (
    CapabilityEligibilityCourt,
    CapabilityRequirement,
    CapabilityTruthRecord,
    AdapterAvailability,
    AdapterObservation,
    CapabilityCurrentnessFabric,
    CapabilityRouteRequirement,
    CapabilitySurfaceState,
    PrivacyClass,
    ClaimKind,
    EvidenceRef,
    Maturity,
    capability_truth_index,
    propagate_evidence,
)


class CapabilityTruthV1Tests(unittest.TestCase):
    def evidence(
        self,
        evidence_id: str,
        kind: ClaimKind,
        maturity: Maturity,
        *,
        fresh: bool = True,
        independent: bool = False,
        source_maturity: Maturity | None = None,
    ) -> EvidenceRef:
        return EvidenceRef(
            evidence_id=evidence_id,
            capability_id="AGENT_FOUNDRY",
            claim_kind=kind,
            source_ref=f"ref:{evidence_id}",
            declared_maturity=maturity,
            source_maturity=source_maturity,
            fresh=fresh,
            independently_verified=independent,
        )

    def test_requirement_cannot_self_promote_to_runtime(self) -> None:
        item = self.evidence("bible", ClaimKind.REQUIREMENT, Maturity.PROVIDER_RUNNING)
        self.assertEqual(item.admitted_maturity, Maturity.SPECIFIED)

    def test_design_cannot_self_promote_to_runtime(self) -> None:
        item = self.evidence("design", ClaimKind.DESIGN, Maturity.BEHAVIOUR_VERIFIED)
        self.assertEqual(item.admitted_maturity, Maturity.DESIGNED)

    def test_agent_role_registration_is_not_running_worker(self) -> None:
        item = self.evidence("fcx-builder", ClaimKind.ROLE_REGISTRATION, Maturity.PROVIDER_RUNNING)
        self.assertEqual(item.admitted_maturity, Maturity.DESIGNED)
        record = CapabilityTruthRecord("AGENT_FOUNDRY", (item,))
        decision = CapabilityEligibilityCourt().decide(
            CapabilityRequirement("AGENT_FOUNDRY", Maturity.PROVIDER_RUNNING),
            record,
        )
        self.assertFalse(decision.eligible)
        self.assertEqual(decision.proven_maturity, Maturity.DESIGNED)

    def test_source_implementation_only_proves_built(self) -> None:
        item = self.evidence("source", ClaimKind.IMPLEMENTATION, Maturity.VALUE_PROVEN)
        self.assertEqual(item.admitted_maturity, Maturity.BUILT)

    def test_test_result_only_proves_tested_local(self) -> None:
        item = self.evidence("tests", ClaimKind.TEST_RESULT, Maturity.PROVIDER_RUNNING)
        self.assertEqual(item.admitted_maturity, Maturity.TESTED_LOCAL)

    def test_source_admission_does_not_prove_hosted_runtime(self) -> None:
        item = self.evidence("merge", ClaimKind.SOURCE_ADMISSION, Maturity.PROVIDER_RUNNING)
        record = CapabilityTruthRecord("AGENT_FOUNDRY", (item,))
        self.assertEqual(record.max_proven_maturity, Maturity.SOURCE_ADMITTED)
        decision = CapabilityEligibilityCourt().decide(
            CapabilityRequirement("AGENT_FOUNDRY", Maturity.HOSTED), record
        )
        self.assertFalse(decision.eligible)

    def test_runtime_receipt_can_prove_running_but_not_provider_readback(self) -> None:
        item = self.evidence("runtime", ClaimKind.RUNTIME_RECEIPT, Maturity.VALUE_PROVEN)
        self.assertEqual(item.admitted_maturity, Maturity.PROVIDER_RUNNING)

    def test_provider_readback_advances_only_to_provider_readback(self) -> None:
        item = self.evidence("readback", ClaimKind.PROVIDER_READBACK, Maturity.VALUE_PROVEN)
        self.assertEqual(item.admitted_maturity, Maturity.PROVIDER_READBACK)

    def test_narrative_summary_never_upgrades_source_maturity(self) -> None:
        source = self.evidence("source-design", ClaimKind.DESIGN, Maturity.DESIGNED)
        derived = propagate_evidence(
            source,
            evidence_id="chatbridge-summary",
            source_ref="chatbridge:g3",
            declared_maturity=Maturity.PROVIDER_RUNNING,
        )
        self.assertEqual(derived.admitted_maturity, Maturity.SPECIFIED)
        self.assertEqual(derived.source_maturity, Maturity.DESIGNED)

    def test_explicit_propagation_above_source_is_rejected(self) -> None:
        item = self.evidence(
            "bad-copy",
            ClaimKind.SOURCE_ADMISSION,
            Maturity.SOURCE_ADMITTED,
            source_maturity=Maturity.DESIGNED,
        )
        with self.assertRaisesRegex(ValueError, "PROPAGATED_MATURITY_EXCEEDS_SOURCE"):
            item.validate()

    def test_stale_evidence_does_not_satisfy_fresh_requirement(self) -> None:
        runtime = self.evidence(
            "old-runtime", ClaimKind.RUNTIME_RECEIPT, Maturity.PROVIDER_RUNNING, fresh=False
        )
        record = CapabilityTruthRecord("AGENT_FOUNDRY", (runtime,))
        decision = CapabilityEligibilityCourt().decide(
            CapabilityRequirement("AGENT_FOUNDRY", Maturity.PROVIDER_RUNNING, require_fresh=True),
            record,
        )
        self.assertFalse(decision.eligible)

    def test_independent_requirement_filters_self_report_only(self) -> None:
        runtime = self.evidence(
            "self-runtime", ClaimKind.RUNTIME_RECEIPT, Maturity.PROVIDER_RUNNING, independent=False
        )
        record = CapabilityTruthRecord("AGENT_FOUNDRY", (runtime,))
        decision = CapabilityEligibilityCourt().decide(
            CapabilityRequirement(
                "AGENT_FOUNDRY",
                Maturity.PROVIDER_RUNNING,
                require_independent_verification=True,
            ),
            record,
        )
        self.assertFalse(decision.eligible)

    def test_independently_verified_runtime_can_satisfy_running_requirement(self) -> None:
        runtime = self.evidence(
            "verified-runtime",
            ClaimKind.RUNTIME_RECEIPT,
            Maturity.PROVIDER_RUNNING,
            independent=True,
        )
        record = CapabilityTruthRecord("AGENT_FOUNDRY", (runtime,))
        decision = CapabilityEligibilityCourt().decide(
            CapabilityRequirement(
                "AGENT_FOUNDRY",
                Maturity.PROVIDER_RUNNING,
                require_independent_verification=True,
            ),
            record,
        )
        self.assertTrue(decision.eligible)

    def test_revoked_capability_fails_closed(self) -> None:
        runtime = self.evidence("runtime", ClaimKind.RUNTIME_RECEIPT, Maturity.PROVIDER_RUNNING)
        record = CapabilityTruthRecord("AGENT_FOUNDRY", (runtime,)).revoke("WORKER_RUNTIME_LOST")
        decision = CapabilityEligibilityCourt().decide(
            CapabilityRequirement("AGENT_FOUNDRY", Maturity.BUILT), record
        )
        self.assertFalse(decision.eligible)
        self.assertIn("CAPABILITY_REVOKED", decision.reasons)

    def test_missing_record_fails_closed(self) -> None:
        decision = CapabilityEligibilityCourt().decide(
            CapabilityRequirement("AGENT_FOUNDRY", Maturity.BUILT), None
        )
        self.assertFalse(decision.eligible)
        self.assertEqual(decision.proven_maturity, Maturity.SPECIFIED)

    def test_duplicate_evidence_id_rejected(self) -> None:
        item = self.evidence("same", ClaimKind.DESIGN, Maturity.DESIGNED)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_CAPABILITY_EVIDENCE_ID"):
            CapabilityTruthRecord("AGENT_FOUNDRY", (item, item)).validate()

    def test_evidence_subject_mismatch_rejected(self) -> None:
        item = EvidenceRef(
            evidence_id="wrong",
            capability_id="OTHER",
            claim_kind=ClaimKind.DESIGN,
            source_ref="ref:wrong",
            declared_maturity=Maturity.DESIGNED,
        )
        with self.assertRaisesRegex(ValueError, "CAPABILITY_EVIDENCE_SUBJECT_MISMATCH"):
            CapabilityTruthRecord("AGENT_FOUNDRY", (item,)).validate()

    def test_truth_index_uses_proven_maturity_not_declared_maturity(self) -> None:
        item = self.evidence("bible", ClaimKind.REQUIREMENT, Maturity.VALUE_PROVEN)
        index = capability_truth_index((CapabilityTruthRecord("AGENT_FOUNDRY", (item,)),))
        self.assertEqual(index["AGENT_FOUNDRY"], Maturity.SPECIFIED)

    def test_duplicate_truth_record_rejected(self) -> None:
        record = CapabilityTruthRecord("AGENT_FOUNDRY")
        with self.assertRaisesRegex(ValueError, "DUPLICATE_CAPABILITY_TRUTH_RECORD"):
            capability_truth_index((record, record))

    def adapter(
        self,
        adapter_id: str,
        kind: ClaimKind,
        maturity: Maturity,
        *,
        availability: AdapterAvailability = AdapterAvailability.CALLABLE,
        observed_at: str = "2026-09-22T05:00:00+00:00",
        expires_at: str = "2026-09-22T06:00:00+00:00",
        authority: tuple[str, ...] = ("A1_INTERNAL",),
        effects: tuple[str, ...] = ("NO_EFFECT", "READ_ONLY"),
        privacy: PrivacyClass = PrivacyClass.PRIVATE,
        failure_domain: str = "",
        reliability: float = 1.0,
        proof_strength: float = 1.0,
        independent: bool = False,
        provider: str = "provider",
    ) -> AdapterObservation:
        return AdapterObservation(
            adapter_id=adapter_id,
            capability_id="AGENT_FOUNDRY",
            provider=provider,
            source_ref=f"ref:{adapter_id}",
            claim_kind=kind,
            declared_maturity=maturity,
            observed_at=observed_at,
            expires_at=expires_at,
            availability=availability,
            authority_classes=authority,
            effect_classes=effects,
            privacy_ceiling=privacy,
            failure_domain=failure_domain,
            reliability=reliability,
            proof_strength=proof_strength,
            independently_verified=independent,
        )

    def test_provider_readback_callable_adapter_is_live(self) -> None:
        fabric = CapabilityCurrentnessFabric((
            self.adapter("live", ClaimKind.PROVIDER_READBACK, Maturity.PROVIDER_READBACK, independent=True),
        ))
        snapshot = fabric.snapshot("AGENT_FOUNDRY", now="2026-09-22T05:30:00+00:00")
        self.assertEqual(snapshot.state, CapabilitySurfaceState.LIVE)
        self.assertEqual(snapshot.callable_adapters, ("live",))

    def test_bound_callable_adapter_is_live_partial_not_live(self) -> None:
        fabric = CapabilityCurrentnessFabric((
            self.adapter("bound", ClaimKind.BINDING, Maturity.BOUND),
        ))
        snapshot = fabric.snapshot("AGENT_FOUNDRY", now="2026-09-22T05:30:00+00:00")
        self.assertEqual(snapshot.state, CapabilitySurfaceState.LIVE_PARTIAL)

    def test_source_only_adapter_never_becomes_live(self) -> None:
        fabric = CapabilityCurrentnessFabric((
            self.adapter("source", ClaimKind.IMPLEMENTATION, Maturity.BUILT, availability=AdapterAvailability.SOURCE_ONLY),
        ))
        snapshot = fabric.snapshot("AGENT_FOUNDRY", now="2026-09-22T05:30:00+00:00")
        self.assertEqual(snapshot.state, CapabilitySurfaceState.SOURCE_ONLY)

    def test_stale_readback_requires_requalification(self) -> None:
        fabric = CapabilityCurrentnessFabric((
            self.adapter(
                "stale",
                ClaimKind.PROVIDER_READBACK,
                Maturity.PROVIDER_READBACK,
                observed_at="2026-09-22T03:00:00+00:00",
                expires_at="2026-09-22T04:00:00+00:00",
            ),
        ))
        snapshot = fabric.snapshot("AGENT_FOUNDRY", now="2026-09-22T05:30:00+00:00")
        self.assertEqual(snapshot.state, CapabilitySurfaceState.STALE_REQUALIFICATION_REQUIRED)

    def test_missing_observation_is_unknown_until_census_complete(self) -> None:
        fabric = CapabilityCurrentnessFabric()
        self.assertEqual(
            fabric.snapshot("AGENT_FOUNDRY", now="2026-09-22T05:30:00+00:00").state,
            CapabilitySurfaceState.UNKNOWN_NOT_ABSENT,
        )
        self.assertEqual(
            fabric.snapshot("AGENT_FOUNDRY", now="2026-09-22T05:30:00+00:00", census_complete=True).state,
            CapabilitySurfaceState.ABSENT_AFTER_ESTATE_CENSUS,
        )

    def test_connector_unavailable_does_not_hide_live_alternate_adapter(self) -> None:
        fabric = CapabilityCurrentnessFabric((
            self.adapter("missing-direct", ClaimKind.BINDING, Maturity.BOUND, availability=AdapterAvailability.CONNECTOR_UNAVAILABLE, provider="direct"),
            self.adapter("alternate", ClaimKind.PROVIDER_READBACK, Maturity.PROVIDER_READBACK, provider="alternate"),
        ))
        snapshot = fabric.snapshot("AGENT_FOUNDRY", now="2026-09-22T05:30:00+00:00")
        self.assertEqual(snapshot.state, CapabilitySurfaceState.LIVE)
        self.assertEqual(snapshot.callable_adapters, ("alternate",))

    def test_rank_enforces_authority_effect_and_privacy(self) -> None:
        fabric = CapabilityCurrentnessFabric((
            self.adapter("good", ClaimKind.PROVIDER_READBACK, Maturity.PROVIDER_READBACK, authority=("A1_INTERNAL","SEND"), effects=("NO_EFFECT","EXTERNAL_SEND"), privacy=PrivacyClass.RESTRICTED),
            self.adapter("bad", ClaimKind.PROVIDER_READBACK, Maturity.PROVIDER_READBACK, authority=("A1_INTERNAL",), effects=("NO_EFFECT",), privacy=PrivacyClass.INTERNAL),
        ))
        ranked = fabric.rank(
            CapabilityRouteRequirement(
                "AGENT_FOUNDRY",
                Maturity.PROVIDER_READBACK,
                authority_class="SEND",
                effect_class="EXTERNAL_SEND",
                privacy_class=PrivacyClass.CONFIDENTIAL,
            ),
            now="2026-09-22T05:30:00+00:00",
        )
        self.assertEqual(ranked[0].adapter_id, "good")
        self.assertTrue(ranked[0].selected)
        self.assertIn("ADAPTER_AUTHORITY_MISMATCH", ranked[1].reasons)

    def test_second_failure_domain_can_be_excluded(self) -> None:
        fabric = CapabilityCurrentnessFabric((
            self.adapter("same", ClaimKind.PROVIDER_READBACK, Maturity.PROVIDER_READBACK, failure_domain="google"),
            self.adapter("other", ClaimKind.PROVIDER_READBACK, Maturity.PROVIDER_READBACK, failure_domain="microsoft"),
        ))
        ranked = fabric.rank(
            CapabilityRouteRequirement(
                "AGENT_FOUNDRY",
                Maturity.PROVIDER_READBACK,
                excluded_failure_domains=("google",),
            ),
            now="2026-09-22T05:30:00+00:00",
        )
        self.assertEqual(ranked[0].adapter_id, "other")

    def test_rank_prefers_stronger_proof_then_reliability_then_lower_burden(self) -> None:
        fabric = CapabilityCurrentnessFabric((
            self.adapter("weak", ClaimKind.PROVIDER_READBACK, Maturity.PROVIDER_READBACK, proof_strength=0.7, reliability=1.0),
            self.adapter("strong", ClaimKind.PROVIDER_READBACK, Maturity.PROVIDER_READBACK, proof_strength=1.0, reliability=0.9),
        ))
        ranked = fabric.rank(
            CapabilityRouteRequirement("AGENT_FOUNDRY", Maturity.PROVIDER_READBACK),
            now="2026-09-22T05:30:00+00:00",
        )
        self.assertEqual(ranked[0].adapter_id, "strong")

    def test_currentness_snapshot_can_publish_selected_adapter(self) -> None:
        fabric = CapabilityCurrentnessFabric((
            self.adapter("google", ClaimKind.PROVIDER_READBACK, Maturity.PROVIDER_READBACK, provider="google"),
            self.adapter("microsoft", ClaimKind.PROVIDER_READBACK, Maturity.PROVIDER_READBACK, provider="microsoft", proof_strength=0.8),
        ))
        req = CapabilityRouteRequirement("AGENT_FOUNDRY", Maturity.PROVIDER_READBACK)
        snapshot = fabric.snapshot("AGENT_FOUNDRY", now="2026-09-22T05:30:00+00:00", requirement=req)
        self.assertEqual(snapshot.selected_adapter, "google")

    def test_observation_cannot_exceed_claim_maturity_ceiling(self) -> None:
        observation = self.adapter("design", ClaimKind.DESIGN, Maturity.PROVIDER_READBACK)
        evidence = observation.to_evidence(now="2026-09-22T05:30:00+00:00")
        self.assertEqual(evidence.admitted_maturity, Maturity.DESIGNED)


if __name__ == "__main__":
    unittest.main()
