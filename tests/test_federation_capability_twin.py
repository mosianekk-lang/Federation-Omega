from __future__ import annotations

import unittest

from evidenceops.caseforge.federation_capability_twin import (
    CapabilityTwin,
    FederationTwinRollup,
    ReadbackState,
    RuntimeState,
    SemanticState,
    TwinState,
)
from evidenceops.caseforge.federation_evolution_program import SYSTEM_PROFILES


class FederationCapabilityTwinTests(unittest.TestCase):
    def twin(self, **overrides):
        payload = dict(
            system_id="TRUTHGRID",
            source_ref="KDV:TRUTHGRID",
            observed_at="2026-08-11T23:50:00+02:00",
            source_exists=True,
            canonical_readback=True,
            authority_ceiling="A1_INTERNAL",
            semantic_state=SemanticState.DECLARED_CONTRACT,
            readback_state=ReadbackState.SOURCE_READBACK,
            runtime_state=RuntimeState.SOURCE_ONLY,
            proof_ref="RCP-TWIN-1",
            ttl_seconds=3600,
            age_seconds=1,
        )
        payload.update(overrides)
        return CapabilityTwin(**payload)

    def test_source_only_is_not_promoted_to_runtime_live(self) -> None:
        twin = self.twin()
        self.assertEqual(TwinState.SOURCE_VERIFIED_RUNTIME_UNVERIFIED, twin.twin_state)
        self.assertTrue(twin.resolution_complete)
        self.assertLess(twin.confidence, 0.5)
        self.assertFalse(twin.to_stage_evidence().provider_readback)

    def test_deterministic_tests_are_not_provider_runtime(self) -> None:
        twin = self.twin(semantic_state=SemanticState.DETERMINISTIC_TESTED)
        self.assertEqual(TwinState.SOURCE_AND_TESTS_VERIFIED_RUNTIME_UNBOUND, twin.twin_state)
        self.assertTrue(twin.resolution_complete)

    def test_adapter_required_is_truthfully_resolved_not_live(self) -> None:
        twin = self.twin(runtime_state=RuntimeState.ADAPTER_REQUIRED)
        self.assertEqual(TwinState.CANONICAL_VERIFIED_ADAPTER_REQUIRED, twin.twin_state)
        self.assertTrue(twin.resolution_complete)

    def test_runtime_verified_requires_semantic_and_readback_proof(self) -> None:
        with self.assertRaisesRegex(ValueError, "semantic runtime proof"):
            self.twin(runtime_state=RuntimeState.RUNTIME_VERIFIED).validate()
        twin = self.twin(
            runtime_state=RuntimeState.RUNTIME_VERIFIED,
            semantic_state=SemanticState.RUNTIME_SEMANTIC_VERIFIED,
            readback_state=ReadbackState.RUNTIME_READBACK,
        )
        self.assertEqual(TwinState.RUNTIME_VERIFIED, twin.twin_state)

    def test_provider_verified_requires_provider_native_reference(self) -> None:
        with self.assertRaisesRegex(ValueError, "provider readback"):
            self.twin(
                runtime_state=RuntimeState.PROVIDER_VERIFIED,
                semantic_state=SemanticState.PROVIDER_SEMANTIC_VERIFIED,
                readback_state=ReadbackState.PROVIDER_READBACK,
            ).validate()
        twin = self.twin(
            runtime_state=RuntimeState.PROVIDER_VERIFIED,
            semantic_state=SemanticState.PROVIDER_SEMANTIC_VERIFIED,
            readback_state=ReadbackState.PROVIDER_READBACK,
            provider_readback_ref="PROVIDER-RCP-1",
        )
        self.assertEqual(TwinState.PROVIDER_VERIFIED, twin.twin_state)
        self.assertEqual(1.0, twin.confidence)
        self.assertTrue(twin.to_stage_evidence().provider_readback)

    def test_stale_twin_cannot_pass_stage_two(self) -> None:
        twin = self.twin(ttl_seconds=60, age_seconds=61)
        self.assertEqual(TwinState.STALE, twin.twin_state)
        self.assertFalse(twin.resolution_complete)
        self.assertEqual(0.0, twin.confidence)

    def test_unknown_semantics_cannot_pass_stage_two(self) -> None:
        self.assertFalse(self.twin(semantic_state=SemanticState.UNKNOWN).resolution_complete)

    def test_lower_authority_ceiling_is_allowed_without_inheritance(self) -> None:
        twin = self.twin(system_id="VERITAS", authority_ceiling="A0")
        self.assertEqual(TwinState.SOURCE_VERIFIED_RUNTIME_UNVERIFIED, twin.twin_state)
        self.assertTrue(twin.resolution_complete)

    def test_authority_expansion_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "expand authority"):
            self.twin(authority_ceiling="A5").validate()

    def test_rollup_requires_all_registered_profiles_when_requested(self) -> None:
        with self.assertRaisesRegex(ValueError, "coverage mismatch"):
            FederationTwinRollup((self.twin(),)).validate()

    def test_rollup_can_cover_every_profile_conservatively(self) -> None:
        twins = []
        for system_id in SYSTEM_PROFILES:
            twins.append(
                CapabilityTwin(
                    system_id=system_id,
                    source_ref=f"REGISTRY:{system_id}",
                    observed_at="2026-08-11T23:50:00+02:00",
                    source_exists=True,
                    canonical_readback=True,
                    authority_ceiling="A1_INTERNAL",
                    semantic_state=SemanticState.DECLARED_CONTRACT,
                    readback_state=ReadbackState.SOURCE_READBACK,
                    runtime_state=RuntimeState.SOURCE_ONLY,
                    proof_ref=f"RCP:{system_id}",
                    ttl_seconds=3600,
                    age_seconds=0,
                )
            )
        rollup = FederationTwinRollup(tuple(twins)).validate()
        self.assertEqual(len(SYSTEM_PROFILES), len(rollup.resolved_systems))
        self.assertEqual((), rollup.unresolved_systems)
        self.assertEqual(
            len(SYSTEM_PROFILES),
            rollup.state_counts()[TwinState.SOURCE_VERIFIED_RUNTIME_UNVERIFIED.value],
        )


if __name__ == "__main__":
    unittest.main()
