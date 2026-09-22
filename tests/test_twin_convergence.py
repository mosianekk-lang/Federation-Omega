from __future__ import annotations

import unittest

from evidenceops.caseforge.federation_capability_twin import (
    CapabilityTwin,
    ReadbackState,
    RuntimeState,
    SemanticState,
)
from evidenceops.caseforge.federation_evolution_program import AUTHORITY_CEILING, SYSTEM_PROFILES
from federation.living_state.twin_convergence import (
    EstateStatus,
    ProbeObservation,
    UsageObservation,
    classify_twin,
    converge_estate,
)

NOW = "2026-09-05T00:38:07+00:00"


def twin(
    system_id: str = "FEDERATION_OMEGA",
    *,
    runtime_state: RuntimeState = RuntimeState.RUNTIME_VERIFIED,
    semantic_state: SemanticState = SemanticState.RUNTIME_SEMANTIC_VERIFIED,
    readback_state: ReadbackState = ReadbackState.RUNTIME_READBACK,
    age_seconds: int = 60,
    ttl_seconds: int = 3600,
    provider_readback_ref: str = "",
) -> CapabilityTwin:
    return CapabilityTwin(
        system_id=system_id,
        source_ref="source:current-main",
        observed_at=NOW,
        source_exists=True,
        canonical_readback=True,
        authority_ceiling=AUTHORITY_CEILING,
        semantic_state=semantic_state,
        readback_state=readback_state,
        runtime_state=runtime_state,
        proof_ref="runtime:receipt",
        ttl_seconds=ttl_seconds,
        age_seconds=age_seconds,
        provider_readback_ref=provider_readback_ref,
    )


class TwinConvergenceTests(unittest.TestCase):
    def test_runtime_verified_is_green_without_usage_inference(self) -> None:
        status, reasons = classify_twin(twin())
        self.assertEqual(status, EstateStatus.GREEN)
        self.assertIn("INVOCATION_UNMEASURED", reasons)

    def test_explicit_zero_usage_is_dormant(self) -> None:
        status, _ = classify_twin(twin(), UsageObservation("FEDERATION_OMEGA", 0, "usage:zero"))
        self.assertEqual(status, EstateStatus.DORMANT)

    def test_source_only_deterministic_is_unbound(self) -> None:
        item = twin(
            runtime_state=RuntimeState.SOURCE_ONLY,
            semantic_state=SemanticState.DETERMINISTIC_TESTED,
            readback_state=ReadbackState.SOURCE_READBACK,
        )
        status, _ = classify_twin(item)
        self.assertEqual(status, EstateStatus.UNBOUND)

    def test_runtime_partial_is_unbound_not_green(self) -> None:
        item = twin(
            runtime_state=RuntimeState.RUNTIME_PARTIAL,
            semantic_state=SemanticState.DETERMINISTIC_TESTED,
            readback_state=ReadbackState.RUNTIME_READBACK,
        )
        status, _ = classify_twin(item)
        self.assertEqual(status, EstateStatus.UNBOUND)

    def test_stale_twin_is_stale(self) -> None:
        item = twin(age_seconds=3601, ttl_seconds=3600)
        status, _ = classify_twin(item)
        self.assertEqual(status, EstateStatus.STALE)

    def test_failed_probe_does_not_promote_missing_twin(self) -> None:
        _, report = converge_estate(
            (),
            probes=(ProbeObservation("EVIDENCEOPS", "OPERATOR_ROUTE_READ_ONLY_NOT_VERIFIED", "gha:33933359429", False),),
        )
        row = next(row for row in report.rows if row.system_id == "EVIDENCEOPS")
        self.assertEqual(row.status, EstateStatus.UNMEASURED)
        self.assertIn("DIAGNOSTIC_PROBE_DOES_NOT_PROMOTE_RUNTIME_STATE", row.reason_codes)

    def test_existing_living_state_adapter_is_reused(self) -> None:
        model, report = converge_estate((twin(),))
        node = model.current_nodes()["capability:FEDERATION_OMEGA"]
        self.assertEqual(node.state, "RUNTIME_VERIFIED")
        self.assertEqual(node.provenance.proof_maturity.value, "RUNTIME_READBACK")
        self.assertEqual(report.living_state_event_count, 1)

    def test_provider_verified_requires_real_provider_contract(self) -> None:
        item = twin(
            runtime_state=RuntimeState.PROVIDER_VERIFIED,
            semantic_state=SemanticState.PROVIDER_SEMANTIC_VERIFIED,
            readback_state=ReadbackState.PROVIDER_READBACK,
            provider_readback_ref="provider:receipt",
        )
        model, report = converge_estate((item,))
        row = next(row for row in report.rows if row.system_id == "FEDERATION_OMEGA")
        node = model.current_nodes()["capability:FEDERATION_OMEGA"]
        self.assertEqual(row.status, EstateStatus.GREEN)
        self.assertEqual(node.provenance.proof_maturity.value, "PROVIDER_READBACK")

    def test_every_registered_system_is_in_report(self) -> None:
        _, report = converge_estate((twin(),))
        self.assertEqual({row.system_id for row in report.rows}, set(SYSTEM_PROFILES))
        self.assertEqual(len(report.rows), len(SYSTEM_PROFILES))

    def test_no_twin_is_unmeasured_not_unbound(self) -> None:
        _, report = converge_estate(())
        self.assertEqual(report.counts["UNMEASURED"], len(SYSTEM_PROFILES))
        self.assertEqual(report.counts["UNBOUND"], 0)

    def test_convergence_has_zero_external_effects(self) -> None:
        model, report = converge_estate((twin(),))
        self.assertEqual(model.external_effects, 0)
        self.assertEqual(report.external_effects, 0)

    def test_usage_system_mismatch_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not match"):
            classify_twin(twin(), UsageObservation("MODISA", 1, "usage:wrong"))


if __name__ == "__main__":
    unittest.main()
