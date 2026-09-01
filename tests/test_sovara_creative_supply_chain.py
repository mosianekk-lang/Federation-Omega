import unittest
from dataclasses import replace

from sovara.creative.creative_graph import CreativeGraph, CreativeNodeKind
from sovara.creative.genome import CreativeMissionGenome, RightsState
from sovara.creative.policy import ContentClass, PrivacyClass
from sovara.creative.producer import ProducerCompiler
from sovara.creative.supply_chain import (
    ConsentState,
    CreativeDiscoveryGraph,
    DuplicateState,
    PerformanceObservation,
    PreReleaseState,
    ReleaseSignal,
    ReleaseSignalState,
    RightsConsentGraph,
    RightsGrant,
    build_asset_fingerprint,
    compile_async_media_work_packet,
    detect_duplicate,
    evaluate_pre_release,
)
from sovara.creative.taste import TasteMemory, TasteObservation


class SovaraCreativeSupplyChainTests(unittest.TestCase):
    def asset(self, asset_id="asset-1", content=b"alpha", perceptual=""):
        return build_asset_fingerprint(
            asset_id=asset_id,
            mission_id="mission-supply",
            graph_node_id="asset-node",
            version_id="v1",
            content=content,
            source_ref="main@source-sha",
            provider_id="synthetic-fixture",
            perceptual_fingerprint=perceptual,
        )

    def full_release_signals(self):
        return tuple(
            ReleaseSignal(detector, ReleaseSignalState.PASS, f"proof:{detector.lower()}")
            for detector in ("IDENTITY", "RIGHTS", "CONSENT", "QA", "PROVENANCE", "POLICY")
        )

    def producer_plan(self):
        mission = CreativeMissionGenome.build(
            mission_id="mission-supply",
            content_class=ContentClass.BRAND_COMMERCIAL,
            objective="Create a campaign master",
            privacy_class=PrivacyClass.PUBLIC,
            required_modalities=("image", "video", "audio"),
            target_channels=("review",),
            rights_state=RightsState.VERIFIED,
            owner_approval_required=True,
        )
        graph = CreativeGraph("mission-supply")
        graph.add_node(
            expected_version=graph.head_version,
            node_id="concept",
            kind=CreativeNodeKind.CONCEPT,
            attributes={"tone": "premium"},
        )
        taste = TasteMemory("owner-supply")
        taste.observe(TasteObservation("obs-1", "lighting", "low-key", 1.0, 1))
        return ProducerCompiler().compile(mission=mission, graph=graph, taste=taste)

    def test_exact_and_perceptual_duplicate_detection_are_distinct(self):
        original = self.asset("asset-a", b"same", "faceprint-001")
        exact = self.asset("asset-b", b"same", "faceprint-002")
        perceptual = self.asset("asset-c", b"different", "faceprint-001")

        exact_decision = detect_duplicate(exact, (original,))
        self.assertEqual(exact_decision.state, DuplicateState.EXACT_MATCH)
        self.assertEqual(exact_decision.matched_asset_ids, ("asset-a",))
        self.assertTrue(exact_decision.exact_content_match)

        perceptual_decision = detect_duplicate(perceptual, (original,))
        self.assertEqual(perceptual_decision.state, DuplicateState.PERCEPTUAL_MATCH)
        self.assertFalse(perceptual_decision.exact_content_match)
        self.assertTrue(perceptual_decision.perceptual_match)

    def test_fingerprint_does_not_fake_perceptual_hash(self):
        fingerprint = self.asset()
        self.assertEqual(fingerprint.perceptual_fingerprint, "")
        self.assertEqual(len(fingerprint.content_sha256), 64)
        self.assertEqual(len(fingerprint.fingerprint_sha256), 64)
        self.assertFalse(fingerprint.external_effect_performed)

    def test_rights_consent_gate_and_revocation_impact_use_creative_graph(self):
        graph = CreativeGraph("mission-supply")
        graph.add_node(
            expected_version=graph.head_version,
            node_id="asset-node",
            kind=CreativeNodeKind.ASSET,
            attributes={"modality": "image"},
        )
        graph.add_node(
            expected_version=graph.head_version,
            node_id="package-node",
            kind=CreativeNodeKind.PACKAGE,
            attributes={},
            locked=True,
        )
        graph.add_dependency(
            expected_version=graph.head_version,
            source_id="asset-node",
            target_id="package-node",
        )

        rights = RightsConsentGraph()
        rights.bind(
            RightsGrant(
                grant_id="grant-1",
                subject_id="subject-1",
                graph_node_id="asset-node",
                rights_state=RightsState.VERIFIED,
                consent_state=ConsentState.VERIFIED,
                identity_verified=True,
                allowed_channels=("instagram",),
                allowed_uses=("campaign",),
                evidence_ref="proof:consent-1",
            )
        )
        allowed = rights.evaluate("asset-node", channel="instagram", use="campaign")
        self.assertTrue(allowed.eligible)

        rights.update_consent(
            "grant-1",
            consent_state=ConsentState.REVOKED,
            evidence_ref="proof:revocation-1",
        )
        denied = rights.evaluate("asset-node", channel="instagram", use="campaign")
        self.assertFalse(denied.eligible)
        self.assertIn("grant-1", denied.blocking_grant_ids)
        impact = rights.impact_for_subject(graph, "subject-1")
        self.assertEqual(impact.direct_node_ids, ("asset-node",))
        self.assertEqual(impact.invalidated_node_ids, ())
        self.assertEqual(impact.blocked_locked_node_ids, ("package-node",))
        self.assertFalse(impact.external_effect_performed)

    def test_rights_gate_rejects_channel_or_use_outside_scope(self):
        rights = RightsConsentGraph()
        rights.bind(
            RightsGrant(
                grant_id="grant-1",
                subject_id="subject-1",
                graph_node_id="asset-node",
                rights_state=RightsState.VERIFIED,
                consent_state=ConsentState.VERIFIED,
                identity_verified=True,
                allowed_channels=("instagram",),
                allowed_uses=("campaign",),
                evidence_ref="proof:consent-1",
            )
        )
        denied = rights.evaluate("asset-node", channel="youtube", use="campaign")
        self.assertFalse(denied.eligible)
        self.assertTrue(any(item.startswith("CHANNEL_NOT_ALLOWED") for item in denied.reasons))

    def test_pre_release_requires_all_detectors_and_owner_release(self):
        asset = self.asset()
        incomplete = evaluate_pre_release(
            asset=asset,
            signals=self.full_release_signals()[:-1],
            owner_release_observed=True,
        )
        self.assertEqual(incomplete.state, PreReleaseState.HOLD_MISSING_DETECTOR)
        self.assertIn("RIGHTS", tuple(signal.detector for signal in self.full_release_signals()))

        waiting_owner = evaluate_pre_release(
            asset=asset,
            signals=self.full_release_signals(),
            owner_release_observed=False,
        )
        self.assertEqual(waiting_owner.state, PreReleaseState.HOLD_OWNER_RELEASE)
        self.assertFalse(waiting_owner.package_eligible)

        ready = evaluate_pre_release(
            asset=asset,
            signals=self.full_release_signals(),
            owner_release_observed=True,
        )
        self.assertEqual(ready.state, PreReleaseState.PACKAGE_ELIGIBLE)
        self.assertTrue(ready.package_eligible)
        self.assertFalse(ready.publication_authorized)
        self.assertFalse(ready.provider_effect_authorized)

    def test_trusted_critical_failure_quarantines_even_with_owner_release(self):
        signals = list(self.full_release_signals())
        signals[-1] = ReleaseSignal(
            "POLICY",
            ReleaseSignalState.FAIL,
            "proof:trusted-policy-alert",
            trusted=True,
            critical=True,
        )
        decision = evaluate_pre_release(
            asset=self.asset(),
            signals=tuple(signals),
            owner_release_observed=True,
        )
        self.assertEqual(decision.state, PreReleaseState.QUARANTINED_TRUSTED_SIGNAL)
        self.assertFalse(decision.package_eligible)
        self.assertFalse(decision.publication_authorized)

    def test_async_media_packet_is_deterministic_and_provider_disabled(self):
        plan = self.producer_plan()
        first = compile_async_media_work_packet(plan)
        second = compile_async_media_work_packet(plan)
        self.assertEqual(first, second)
        self.assertEqual(first.heavy_modalities, ("audio", "video"))
        selected_actions = {
            step.action for step in plan.steps if step.step_id in first.selected_step_ids
        }
        self.assertEqual(
            selected_actions,
            {"PREPARE_AUDIO_WORK_PACKET", "PREPARE_VIDEO_WORK_PACKET"},
        )
        self.assertFalse(first.provider_execution_authorized)
        self.assertFalse(first.external_effect_performed)

    def test_async_media_packet_rejects_effectful_plan(self):
        plan = replace(self.producer_plan(), external_effect_performed=True)
        with self.assertRaises(ValueError):
            compile_async_media_work_packet(plan)

    def test_discovery_graph_excludes_synthetic_and_requires_repeated_signal(self):
        graph = CreativeDiscoveryGraph(min_observations=2)
        graph.observe(
            PerformanceObservation("perf-1", "asset-1", ("luxury", "silk"), 0.8, 1)
        )
        graph.observe(
            PerformanceObservation("perf-2", "asset-2", ("luxury",), 0.6, 2)
        )
        graph.observe(
            PerformanceObservation(
                "synthetic-1", "asset-x", ("neon",), 1.0, 3, synthetic=True
            )
        )
        receipt = graph.receipt()
        self.assertTrue(receipt.learning_ready)
        self.assertEqual(receipt.eligible_observation_count, 2)
        self.assertEqual(tuple(item.tag for item in receipt.recommendations), ("luxury",))
        self.assertEqual(receipt.recommendations[0].score, 0.7)
        self.assertFalse(receipt.external_effect_performed)

    def test_discovery_graph_does_not_promote_one_off_signal(self):
        graph = CreativeDiscoveryGraph(min_observations=2)
        graph.observe(PerformanceObservation("perf-1", "asset-1", ("luxury",), 1.0, 1))
        receipt = graph.receipt()
        self.assertFalse(receipt.learning_ready)
        self.assertEqual(receipt.recommendations, ())


if __name__ == "__main__":
    unittest.main()
