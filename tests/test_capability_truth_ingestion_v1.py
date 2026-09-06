from __future__ import annotations

import unittest

from federation.capability_truth_ingestion_v1 import (
    ClaimEnvelope,
    OperationalTruthCompiler,
    SourceClass,
)
from federation.capability_truth_v1 import Maturity


class CapabilityTruthIngestionV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.compiler = OperationalTruthCompiler()

    def env(
        self,
        evidence_id: str,
        source_class: SourceClass,
        maturity: Maturity,
        *,
        parent: str = "",
        fresh: bool = True,
        independent: bool = False,
    ) -> ClaimEnvelope:
        return ClaimEnvelope(
            evidence_id=evidence_id,
            capability_id="AGENT_FOUNDRY",
            source_class=source_class,
            source_ref=f"ref:{evidence_id}",
            asserted_maturity=maturity,
            derived_from_evidence_id=parent,
            fresh=fresh,
            independently_verified=independent,
        )

    def test_bible_requirement_claimed_runtime_stays_specified(self) -> None:
        item = self.compiler.compile(
            self.env("bible-req", SourceClass.BIBLE_REQUIREMENT, Maturity.PROVIDER_RUNNING)
        )
        self.assertEqual(item.admitted_maturity, Maturity.SPECIFIED)

    def test_bible_design_claimed_runtime_stays_designed(self) -> None:
        item = self.compiler.compile(
            self.env("bible-design", SourceClass.BIBLE_DESIGN, Maturity.PROVIDER_RUNNING)
        )
        self.assertEqual(item.admitted_maturity, Maturity.DESIGNED)

    def test_registry_active_label_cannot_prove_running(self) -> None:
        item = self.compiler.compile(
            self.env("registry-active", SourceClass.REGISTRY_ENTRY, Maturity.PROVIDER_RUNNING)
        )
        self.assertEqual(item.admitted_maturity, Maturity.SPECIFIED)

    def test_model_memory_cannot_prove_running(self) -> None:
        item = self.compiler.compile(
            self.env("memory", SourceClass.MODEL_MEMORY, Maturity.VALUE_PROVEN)
        )
        self.assertEqual(item.admitted_maturity, Maturity.SPECIFIED)

    def test_chatbridge_requires_provenance(self) -> None:
        with self.assertRaisesRegex(ValueError, "DERIVED_OPERATIONAL_CLAIM_REQUIRES_PROVENANCE"):
            self.compiler.compile(
                self.env("chatbridge", SourceClass.CHATBRIDGE_SUMMARY, Maturity.PROVIDER_RUNNING)
            )

    def test_fkpf_requires_provenance(self) -> None:
        with self.assertRaisesRegex(ValueError, "DERIVED_OPERATIONAL_CLAIM_REQUIRES_PROVENANCE"):
            self.compiler.compile(
                self.env("fkpf", SourceClass.FKPF_PROPAGATION, Maturity.BEHAVIOUR_VERIFIED)
            )

    def test_chatbridge_summary_of_design_stays_specified(self) -> None:
        record = self.compiler.compile_record(
            "AGENT_FOUNDRY",
            (
                self.env("design", SourceClass.BIBLE_DESIGN, Maturity.DESIGNED),
                self.env(
                    "chatbridge",
                    SourceClass.CHATBRIDGE_SUMMARY,
                    Maturity.PROVIDER_RUNNING,
                    parent="design",
                ),
            ),
        )
        by_id = {item.evidence_id: item for item in record.evidence}
        self.assertEqual(by_id["design"].admitted_maturity, Maturity.DESIGNED)
        self.assertEqual(by_id["chatbridge"].admitted_maturity, Maturity.SPECIFIED)

    def test_fkpf_cannot_upgrade_source_admission_to_runtime(self) -> None:
        record = self.compiler.compile_record(
            "AGENT_FOUNDRY",
            (
                self.env(
                    "source-admit",
                    SourceClass.SOURCE_ADMISSION_RECEIPT,
                    Maturity.SOURCE_ADMITTED,
                ),
                self.env(
                    "fkpf-copy",
                    SourceClass.FKPF_PROPAGATION,
                    Maturity.PROVIDER_RUNNING,
                    parent="source-admit",
                ),
            ),
        )
        by_id = {item.evidence_id: item for item in record.evidence}
        self.assertEqual(by_id["source-admit"].admitted_maturity, Maturity.SOURCE_ADMITTED)
        self.assertEqual(by_id["fkpf-copy"].admitted_maturity, Maturity.SPECIFIED)

    def test_runtime_receipt_can_reach_running(self) -> None:
        item = self.compiler.compile(
            self.env("runtime", SourceClass.RUNTIME_RECEIPT, Maturity.PROVIDER_RUNNING)
        )
        self.assertEqual(item.admitted_maturity, Maturity.PROVIDER_RUNNING)

    def test_provider_readback_can_reach_provider_readback(self) -> None:
        item = self.compiler.compile(
            self.env("readback", SourceClass.PROVIDER_READBACK, Maturity.PROVIDER_READBACK)
        )
        self.assertEqual(item.admitted_maturity, Maturity.PROVIDER_READBACK)

    def test_value_receipt_can_reach_value_proven(self) -> None:
        item = self.compiler.compile(
            self.env("value", SourceClass.VALUE_RECEIPT, Maturity.VALUE_PROVEN)
        )
        self.assertEqual(item.admitted_maturity, Maturity.VALUE_PROVEN)

    def test_missing_parent_fails_closed(self) -> None:
        envelope = self.env(
            "chatbridge",
            SourceClass.CHATBRIDGE_SUMMARY,
            Maturity.PROVIDER_RUNNING,
            parent="missing",
        )
        with self.assertRaisesRegex(ValueError, "OPERATIONAL_CLAIM_PROVENANCE_NOT_FOUND"):
            self.compiler.compile(envelope, evidence_index={})

    def test_wrong_parent_capability_fails_closed(self) -> None:
        other = self.compiler.compile(
            ClaimEnvelope(
                evidence_id="other",
                capability_id="OTHER",
                source_class=SourceClass.BIBLE_DESIGN,
                source_ref="ref:other",
                asserted_maturity=Maturity.DESIGNED,
            )
        )
        envelope = self.env(
            "chatbridge",
            SourceClass.CHATBRIDGE_SUMMARY,
            Maturity.PROVIDER_RUNNING,
            parent="other",
        )
        with self.assertRaisesRegex(ValueError, "OPERATIONAL_CLAIM_PROVENANCE_SUBJECT_MISMATCH"):
            self.compiler.compile(envelope, evidence_index={"other": other})

    def test_compile_record_resolves_child_after_parent_even_when_out_of_order(self) -> None:
        record = self.compiler.compile_record(
            "AGENT_FOUNDRY",
            (
                self.env(
                    "chatbridge",
                    SourceClass.CHATBRIDGE_SUMMARY,
                    Maturity.PROVIDER_RUNNING,
                    parent="design",
                ),
                self.env("design", SourceClass.BIBLE_DESIGN, Maturity.DESIGNED),
            ),
        )
        self.assertEqual(len(record.evidence), 2)

    def test_unresolvable_provenance_graph_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "OPERATIONAL_CLAIM_PROVENANCE_CYCLE_OR_MISSING_PARENT"
        ):
            self.compiler.compile_record(
                "AGENT_FOUNDRY",
                (
                    self.env(
                        "a",
                        SourceClass.CHATBRIDGE_SUMMARY,
                        Maturity.PROVIDER_RUNNING,
                        parent="b",
                    ),
                    self.env(
                        "b",
                        SourceClass.FKPF_PROPAGATION,
                        Maturity.PROVIDER_RUNNING,
                        parent="a",
                    ),
                ),
            )

    def test_stale_parent_makes_derived_claim_stale(self) -> None:
        record = self.compiler.compile_record(
            "AGENT_FOUNDRY",
            (
                self.env("design", SourceClass.BIBLE_DESIGN, Maturity.DESIGNED, fresh=False),
                self.env(
                    "chatbridge",
                    SourceClass.CHATBRIDGE_SUMMARY,
                    Maturity.PROVIDER_RUNNING,
                    parent="design",
                    fresh=True,
                ),
            ),
        )
        by_id = {item.evidence_id: item for item in record.evidence}
        self.assertFalse(by_id["chatbridge"].fresh)

    def test_derived_summary_never_inherits_independent_verification(self) -> None:
        record = self.compiler.compile_record(
            "AGENT_FOUNDRY",
            (
                self.env(
                    "runtime",
                    SourceClass.RUNTIME_RECEIPT,
                    Maturity.PROVIDER_RUNNING,
                    independent=True,
                ),
                self.env(
                    "chatbridge",
                    SourceClass.CHATBRIDGE_SUMMARY,
                    Maturity.PROVIDER_RUNNING,
                    parent="runtime",
                ),
            ),
        )
        by_id = {item.evidence_id: item for item in record.evidence}
        self.assertTrue(by_id["runtime"].independently_verified)
        self.assertFalse(by_id["chatbridge"].independently_verified)


if __name__ == "__main__":
    unittest.main()
