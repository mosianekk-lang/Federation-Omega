from __future__ import annotations

from copy import deepcopy
import unittest

from benchmarking.cfbe_omega.value_foundry_v1 import (
    EVIDENCE_SCHEMA,
    canonical_hash,
    evaluate_value_foundry,
    record_hash,
)

HEAD = "b7cec901481f7fc66970c6cb8da279cb89675fd4"
VERIFIER = "realityguard:independent-readback-v1"


def observation(index: int, variant: str) -> dict[str, object]:
    baseline = variant == "BASELINE"
    return {
        "observation_id": f"obs-{index}-{variant.lower()}",
        "pair_id": f"pair-{index}",
        "variant": variant,
        "mission_class": "SOFTWARE_ENGINEERING",
        "mission_id": f"mission-{index}",
        "task_signature": f"task-{index}",
        "oracle_id": "oracle-v1",
        "source_head_sha": HEAD,
        "observed_at": "2026-09-01T04:00:00+02:00",
        "accepted": True,
        "verified_output_ratio": 0.95 if baseline else 1.0,
        "owner_intervention_seconds": 600 if baseline else 240,
        "owner_intervention_count": 3 if baseline else 1,
        "clarification_count": 2 if baseline else 1,
        "correction_count": 1 if baseline else 0,
        "elapsed_seconds": 900 if baseline else 480,
        "independent_readback": True,
        "proof_refs": [f"ev-{index}-{variant.lower()}"],
        "evidence_class": "OBSERVED_OWNER_VALUE",
        "measurement_state": "MEASURED",
    }


def evidence_receipt(reference: str, subject: str, raw: dict[str, object], *, verifier: str = VERIFIER) -> dict[str, object]:
    unsigned = {
        "schema": EVIDENCE_SCHEMA,
        "evidence_id": reference,
        "subject": subject,
        "evidence_class": "INDEPENDENT_SEMANTIC_READBACK",
        "source_head_sha": HEAD,
        "record_sha256": record_hash(raw),
        "payload_sha256": canonical_hash({"semantic": "verified", "reference": reference}),
        "verifier_id": verifier,
        "verified_at": "2026-09-01T02:00:00Z",
        "independent_readback": True,
        "status": "VERIFIED",
    }
    return {**unsigned, "receipt_sha256": canonical_hash(unsigned)}


def cohort(count: int) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    records: list[dict[str, object]] = []
    registry: dict[str, dict[str, object]] = {}
    for index in range(count):
        for variant in ("BASELINE", "BUBBLES"):
            item = observation(index, variant)
            reference = str(item["proof_refs"][0])
            registry[reference] = evidence_receipt(reference, f"owner-value:{item['observation_id']}", item)
            records.append(item)
    return records, registry


def runtime(mode: str, suffix: str) -> dict[str, object]:
    live = mode == "LIVE_PROVIDER_DEPLOYMENT"
    return {
        "evidence_id": f"runtime-{suffix}",
        "source_head_sha": HEAD,
        "evidence_mode": mode,
        "environment": "bounded-canary",
        "image_digest": "sha256:" + suffix * 64,
        "revision_id": "revision-1" if live else "",
        "provider_registration_verified": live,
        "workload_identity_verified": live,
        "health_readback_verified": True,
        "rollback_verified": True,
        "deployment_observed": live,
        "independent_readback": True,
        "provider_effect_authorized": live,
        "proof_refs": [f"runtime-ref-{suffix}-{i}" for i in range(3 if live else 2)],
    }


def add_runtime_receipts(registry: dict[str, dict[str, object]], item: dict[str, object]) -> None:
    for reference in item["proof_refs"]:
        registry[str(reference)] = evidence_receipt(str(reference), f"runtime:{item['evidence_id']}", item)


class CFBEValueFoundryV1Tests(unittest.TestCase):
    def evaluate(self, records, registry, runtime_items=()):
        return evaluate_value_foundry(
            champion_id="bubbles-current",
            candidate_id="bubbles-value-foundry-v1",
            source_head_sha=HEAD,
            owner_value_records=records,
            runtime_or_deployment_evidence=runtime_items,
            evidence_registry=registry,
            trusted_verifiers=(VERIFIER,),
        )

    def test_colon_shaped_or_missing_reference_never_resolves(self):
        records, registry = cohort(1)
        records[0]["proof_refs"] = ["source:module"]
        receipt = self.evaluate(records, registry)
        self.assertEqual("HOLD_UNTRUSTED_OR_INCOMPLETE_EVIDENCE", receipt.decision)
        self.assertIn("EVIDENCE_REFERENCE_UNRESOLVED", receipt.blockers[0])

    def test_tampered_receipt_hash_fails_closed(self):
        records, registry = cohort(1)
        first = next(iter(registry))
        registry[first]["status"] = "REJECTED"
        receipt = self.evaluate(records, registry)
        self.assertEqual("HOLD_UNTRUSTED_OR_INCOMPLETE_EVIDENCE", receipt.decision)
        self.assertIn("EVIDENCE_RECEIPT_HASH_MISMATCH", receipt.blockers[0])

    def test_untrusted_verifier_fails_closed(self):
        records, registry = cohort(1)
        first = records[0]
        ref = str(first["proof_refs"][0])
        registry[ref] = evidence_receipt(ref, f"owner-value:{first['observation_id']}", first, verifier="unknown")
        receipt = self.evaluate(records, registry)
        self.assertIn("EVIDENCE_VERIFIER_UNTRUSTED", receipt.blockers[0])

    def test_record_mutation_after_verification_fails_closed(self):
        records, registry = cohort(1)
        records[0]["owner_intervention_seconds"] = 1
        receipt = self.evaluate(records, registry)
        self.assertIn("EVIDENCE_RECORD_HASH_MISMATCH", receipt.blockers[0])

    def test_nine_pairs_hold_owner_value(self):
        records, registry = cohort(9)
        receipt = self.evaluate(records, registry)
        self.assertEqual("HOLD_NO_PROMOTION", receipt.decision)
        self.assertFalse(receipt.owner_value_proven)

    def test_ten_resolved_pairs_prove_value_but_not_deployment(self):
        records, registry = cohort(10)
        receipt = self.evaluate(records, registry)
        self.assertEqual("OWNER_VALUE_PROVEN_DEPLOYMENT_GATES_OPEN", receipt.decision)
        self.assertTrue(receipt.owner_value_proven)
        self.assertFalse(receipt.provider_deployment_proven)
        self.assertFalse(receipt.stable_promotion_allowed)

    def test_complete_evidence_only_reaches_separate_owner_review(self):
        records, registry = cohort(10)
        internal = runtime("INTERNAL_RUNTIME_QUALIFICATION", "a")
        live = runtime("LIVE_PROVIDER_DEPLOYMENT", "b")
        add_runtime_receipts(registry, internal)
        add_runtime_receipts(registry, live)
        receipt = self.evaluate(records, registry, (internal, live))
        self.assertEqual("READY_FOR_SEPARATE_OWNER_PROMOTION_REVIEW", receipt.decision)
        self.assertTrue(receipt.provider_deployment_proven)
        self.assertFalse(receipt.stable_promotion_allowed)
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertFalse(receipt.external_effect)

    def test_runtime_reference_must_resolve_too(self):
        records, registry = cohort(10)
        internal = runtime("INTERNAL_RUNTIME_QUALIFICATION", "a")
        receipt = self.evaluate(records, registry, (internal,))
        self.assertEqual("HOLD_UNTRUSTED_OR_INCOMPLETE_EVIDENCE", receipt.decision)

    def test_receipt_is_deterministic(self):
        records, registry = cohort(10)
        first = self.evaluate(deepcopy(records), deepcopy(registry))
        second = self.evaluate(deepcopy(records), deepcopy(registry))
        self.assertEqual(first.receipt_sha256, second.receipt_sha256)

    def test_input_records_are_not_mutated(self):
        records, registry = cohort(10)
        before = deepcopy(records)
        self.evaluate(records, registry)
        self.assertEqual(before, records)

    def test_distinct_champion_and_candidate_required(self):
        with self.assertRaisesRegex(ValueError, "DISTINCT_CHAMPION"):
            evaluate_value_foundry(
                champion_id="same", candidate_id="same", source_head_sha=HEAD,
                evidence_registry={}, trusted_verifiers=(VERIFIER,),
            )

    def test_no_trusted_verifier_set_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "TRUSTED_VERIFIER_SET_REQUIRED"):
            evaluate_value_foundry(
                champion_id="a", candidate_id="b", source_head_sha=HEAD,
                evidence_registry={}, trusted_verifiers=(),
            )


if __name__ == "__main__":
    unittest.main()
