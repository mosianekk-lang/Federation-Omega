from __future__ import annotations

import unittest

from evidenceops.caseforge.replication import (
    IndependentReplicationGate,
    ReplicationProofError,
    ReplicationRun,
)


H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64
H4 = "4" * 64


def run(
    *,
    run_id: str = "RUN-A",
    provider: str = "openai",
    model: str = "model-a",
    version: str = "version-a",
    route: str = "route-a",
    blind_hash: str = H1,
    output_hash: str = H2,
    config_hash: str = H3,
    verified: bool = True,
    external_effect: bool = False,
) -> ReplicationRun:
    return ReplicationRun(
        run_id=run_id,
        case_id="CF-UTILITY-ZA-001",
        blind_input_sha256=blind_hash,
        tested_output_sha256=output_hash,
        provider=provider,
        model=model,
        model_version_ref=version,
        configuration_sha256=config_hash,
        execution_route_id=route,
        provider_readback_ref=f"readback:{run_id}",
        provider_verified=verified,
        external_effect=external_effect,
    )


class IndependentReplicationGateTests(unittest.TestCase):
    def test_cross_provider_replication_is_materially_independent(self) -> None:
        decision = IndependentReplicationGate().evaluate(
            run(),
            run(run_id="RUN-B", provider="gemini", model="model-b", version="version-b"),
        )
        self.assertTrue(decision.independent)
        self.assertIn("PROVIDER", decision.independence_dimensions)
        self.assertEqual(64, len(decision.replication_pair_sha256))

    def test_same_provider_different_model_and_route_is_independent(self) -> None:
        decision = IndependentReplicationGate().evaluate(
            run(),
            run(run_id="RUN-B", model="model-b", version="version-b", route="route-b"),
        )
        self.assertTrue(decision.independent)
        self.assertEqual(
            ("MODEL_VERSION", "EXECUTION_ROUTE"),
            decision.independence_dimensions,
        )

    def test_same_provider_model_route_is_not_independent(self) -> None:
        decision = IndependentReplicationGate().evaluate(run(), run(run_id="RUN-B"))
        self.assertFalse(decision.independent)
        self.assertIn("MATERIAL_INDEPENDENCE_NOT_PROVEN", decision.reason_codes)

    def test_blind_input_mismatch_vetoes_replication(self) -> None:
        decision = IndependentReplicationGate().evaluate(
            run(),
            run(run_id="RUN-B", provider="gemini", blind_hash=H4),
        )
        self.assertFalse(decision.independent)
        self.assertIn("BLIND_INPUT_MISMATCH", decision.reason_codes)

    def test_provider_unverified_run_is_rejected(self) -> None:
        with self.assertRaisesRegex(ReplicationProofError, "provider-verified"):
            IndependentReplicationGate().evaluate(run(), run(run_id="RUN-B", verified=False))

    def test_external_effect_run_is_rejected(self) -> None:
        with self.assertRaisesRegex(ReplicationProofError, "no-external-effect"):
            IndependentReplicationGate().evaluate(
                run(),
                run(run_id="RUN-B", provider="gemini", external_effect=True),
            )

    def test_matching_output_hash_does_not_create_or_destroy_independence(self) -> None:
        decision = IndependentReplicationGate().evaluate(
            run(output_hash=H2),
            run(
                run_id="RUN-B",
                provider="gemini",
                model="model-b",
                version="version-b",
                output_hash=H2,
            ),
        )
        self.assertTrue(decision.independent)
        self.assertNotIn("OUTPUT_AGREEMENT", decision.independence_dimensions)


if __name__ == "__main__":
    unittest.main()
