from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_institutional_twin_v1 import (
    CapabilityHealth,
    CapabilityObservation,
    build_institutional_twin,
    capability_reuse_candidates,
    proof_state_counts,
)
from benchmarking.cfbe_omega.kim_dataverse_level7_plus_v1 import MaturityState, OwnerBoundary


class KimDataverseInstitutionalTwinTests(unittest.TestCase):
    def test_provider_verified_requires_proof(self) -> None:
        with self.assertRaises(ValueError):
            build_institutional_twin(
                (
                    CapabilityObservation(
                        "provider",
                        "a" * 40,
                        MaturityState.PROVIDER_VERIFIED,
                        CapabilityHealth.HEALTHY,
                        (),
                    ),
                )
            )

    def test_twin_preserves_proof_state_separation(self) -> None:
        twin = build_institutional_twin(
            (
                CapabilityObservation(
                    "sol",
                    "a" * 40,
                    MaturityState.TESTED,
                    CapabilityHealth.HEALTHY,
                    ("proof:sol",),
                    reliability=0.99,
                ),
                CapabilityObservation(
                    "sovara-google",
                    "b" * 40,
                    MaturityState.PROVIDER_VERIFIED,
                    CapabilityHealth.HEALTHY,
                    ("proof:provider",),
                    authority_boundary=OwnerBoundary.AUTHORITY,
                    reliability=0.95,
                ),
                CapabilityObservation(
                    "owner-value",
                    "c" * 40,
                    MaturityState.VALUE_PROVEN,
                    CapabilityHealth.HEALTHY,
                    ("proof:value",),
                    owner_burden_minutes=2.0,
                ),
            )
        )
        self.assertEqual(1, twin.provider_verified_count)
        self.assertEqual(0, twin.operationally_observed_count)
        self.assertEqual(1, twin.value_proven_count)
        self.assertEqual(1, twin.authority_bound_count)
        counts = proof_state_counts(twin)
        self.assertEqual(1, counts["PROVIDER_VERIFIED"])
        self.assertEqual(1, counts["VALUE_PROVEN"])

    def test_unresolved_dependency_is_visible_not_inferred(self) -> None:
        twin = build_institutional_twin(
            (
                CapabilityObservation(
                    "prime",
                    "a" * 40,
                    MaturityState.TESTED,
                    CapabilityHealth.HEALTHY,
                    ("proof:prime",),
                    dependencies=("missing-cap",),
                ),
            )
        )
        self.assertEqual((("prime", "missing-cap"),), twin.unresolved_dependencies)

    def test_stale_or_degraded_capability_is_not_reuse_candidate(self) -> None:
        twin = build_institutional_twin(
            (
                CapabilityObservation(
                    "healthy",
                    "a" * 40,
                    MaturityState.TESTED,
                    CapabilityHealth.HEALTHY,
                    ("proof:h",),
                    reliability=0.9,
                ),
                CapabilityObservation(
                    "stale",
                    "b" * 40,
                    MaturityState.TESTED,
                    CapabilityHealth.STALE,
                    ("proof:s",),
                    reliability=0.99,
                ),
            )
        )
        self.assertEqual(("healthy",), capability_reuse_candidates(twin, (), minimum_reliability=0.8))

    def test_duplicate_capability_fails_closed(self) -> None:
        observation = CapabilityObservation(
            "dup",
            "a" * 40,
            MaturityState.TESTED,
            CapabilityHealth.HEALTHY,
            ("proof",),
        )
        with self.assertRaises(ValueError):
            build_institutional_twin((observation, observation))

    def test_digest_is_deterministic_and_no_effect(self) -> None:
        observations = (
            CapabilityObservation(
                "cap",
                "a" * 40,
                MaturityState.TESTED,
                CapabilityHealth.HEALTHY,
                ("proof",),
            ),
        )
        first = build_institutional_twin(observations)
        second = build_institutional_twin(observations)
        self.assertEqual(first.digest(), second.digest())


if __name__ == "__main__":
    unittest.main()
