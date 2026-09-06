from __future__ import annotations

import unittest

from federation.capability_truth_v1 import (
    CapabilityEligibilityCourt,
    CapabilityRequirement,
    CapabilityTruthRecord,
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


if __name__ == "__main__":
    unittest.main()
