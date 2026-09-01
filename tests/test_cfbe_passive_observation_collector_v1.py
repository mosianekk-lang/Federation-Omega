from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmarking.cfbe_omega.passive_observation_collector_v1 import (
    COLLECTOR_SCHEMA,
    CollectorState,
    bind_eligible_directive,
    canonical_state_hash,
    ingest_owner_value_observation,
    initialize_collector,
    main,
    validate_collector_state,
)
from benchmarking.cfbe_omega.value_foundry_v1 import (
    EVIDENCE_SCHEMA,
    canonical_hash,
    record_hash,
)


HEAD = "7cb7c960ef0ef220d12f858b7a1d7960cb9f9525"
VERIFIER = "realityguard:independent-readback-v1"


def cohort_manifest() -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    return json.loads(
        (root / "benchmarking/cfbe_omega/cohorts/CFBE_VALUE_FOUNDRY_COHORT_001.json")
        .read_text(encoding="utf-8")
    )


def evidence_receipt(reference: str, subject: str, raw: dict[str, object]) -> dict[str, object]:
    unsigned = {
        "schema": EVIDENCE_SCHEMA,
        "evidence_id": reference,
        "subject": subject,
        "evidence_class": "INDEPENDENT_SEMANTIC_READBACK",
        "source_head_sha": HEAD,
        "record_sha256": record_hash(raw),
        "payload_sha256": canonical_hash({"semantic": "verified", "reference": reference}),
        "verifier_id": VERIFIER,
        "verified_at": "2026-09-01T05:00:00Z",
        "independent_readback": True,
        "status": "VERIFIED",
    }
    return {**unsigned, "receipt_sha256": canonical_hash(unsigned)}


def directive(*, task_class: str = "DIRECTIVE_COMPLETION") -> dict[str, object]:
    return {
        "directive_id": "directive-real-001",
        "task_class": task_class,
        "source_head_sha": HEAD,
        "observed_at": "2026-09-01T07:00:00+02:00",
        "real_directive": True,
        "synthetic": False,
        "shadow": False,
        "replayed": False,
        "proof_refs": ["directive-proof-001"],
    }


def observation(variant: str) -> dict[str, object]:
    baseline = variant == "BASELINE"
    return {
        "observation_id": f"CFBE-VF-COHORT-001-PAIR-01-{'BASELINE' if baseline else 'BUBBLES'}",
        "pair_id": "CFBE-VF-COHORT-001-PAIR-01",
        "variant": variant,
        "mission_class": "DIRECTIVE_COMPLETION",
        "mission_id": "directive-real-001",
        "task_signature": "directive-completion-v1",
        "oracle_id": "CFBE-REAL-TASK-ORACLE-01",
        "source_head_sha": HEAD,
        "observed_at": "2026-09-01T07:10:00+02:00",
        "accepted": True,
        "verified_output_ratio": 0.95 if baseline else 1.0,
        "owner_intervention_seconds": 600 if baseline else 240,
        "owner_intervention_count": 3 if baseline else 1,
        "clarification_count": 2 if baseline else 1,
        "correction_count": 1 if baseline else 0,
        "elapsed_seconds": 900 if baseline else 480,
        "independent_readback": True,
        "real_observation": True,
        "synthetic": False,
        "shadow": False,
        "replayed": False,
        "proof_refs": [f"observation-proof-{variant.lower()}"],
        "evidence_class": "OBSERVED_OWNER_VALUE",
        "measurement_state": "MEASURED",
    }


def bound_state() -> tuple[CollectorState, dict[str, dict[str, object]]]:
    state = initialize_collector(cohort_manifest(), source_base_sha=HEAD)
    item = directive()
    registry = {
        "directive-proof-001": evidence_receipt(
            "directive-proof-001", "directive:directive-real-001", item
        )
    }
    state, _ = bind_eligible_directive(
        state,
        cohort_manifest(),
        item,
        evidence_registry=registry,
        trusted_verifiers=(VERIFIER,),
    )
    return state, registry


class PassiveObservationCollectorV1Tests(unittest.TestCase):
    def test_initial_state_is_empty_and_cannot_promote(self) -> None:
        state = initialize_collector(cohort_manifest(), source_base_sha=HEAD)
        self.assertEqual(state.schema, COLLECTOR_SCHEMA)
        self.assertEqual(state.bound_directive_count, 0)
        self.assertEqual(state.collected_observation_count, 0)
        self.assertEqual(state.pair_ready_count, 0)
        self.assertFalse(state.owner_value_proven)
        self.assertFalse(state.stable_promotion_allowed)
        self.assertFalse(state.provider_effect_authorized)
        self.assertFalse(state.external_effect)

    def test_unresolved_directive_receipt_fails_closed(self) -> None:
        state = initialize_collector(cohort_manifest(), source_base_sha=HEAD)
        with self.assertRaisesRegex(ValueError, "EVIDENCE_REFERENCE_UNRESOLVED"):
            bind_eligible_directive(
                state, cohort_manifest(), directive(),
                evidence_registry={}, trusted_verifiers=(VERIFIER,),
            )

    def test_synthetic_shadow_and_replayed_directives_are_rejected(self) -> None:
        for field in ("synthetic", "shadow", "replayed"):
            item = directive()
            item[field] = True
            registry = {"directive-proof-001": evidence_receipt(
                "directive-proof-001", "directive:directive-real-001", item
            )}
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field.upper()):
                bind_eligible_directive(
                    initialize_collector(cohort_manifest(), source_base_sha=HEAD),
                    cohort_manifest(), item,
                    evidence_registry=registry, trusted_verifiers=(VERIFIER,),
                )

    def test_next_compatible_empty_slot_is_selected_deterministically(self) -> None:
        state, _ = bound_state()
        binding = state.bindings[0]
        self.assertEqual(binding.slot_id, "CFBE-VF-COHORT-001-SLOT-01")
        self.assertEqual(binding.pair_id, "CFBE-VF-COHORT-001-PAIR-01")
        self.assertEqual(binding.task_oracle_id, "CFBE-REAL-TASK-ORACLE-01")

    def test_unregistered_task_class_is_rejected(self) -> None:
        item = directive(task_class="NOT_REGISTERED")
        registry = {"directive-proof-001": evidence_receipt(
            "directive-proof-001", "directive:directive-real-001", item
        )}
        with self.assertRaisesRegex(ValueError, "NO_COMPATIBLE_EMPTY_SLOT"):
            bind_eligible_directive(
                initialize_collector(cohort_manifest(), source_base_sha=HEAD),
                cohort_manifest(), item,
                evidence_registry=registry, trusted_verifiers=(VERIFIER,),
            )

    def test_exact_directive_replay_is_idempotent(self) -> None:
        state, registry = bound_state()
        replay, receipt = bind_eligible_directive(
            state, cohort_manifest(), directive(),
            evidence_registry=registry, trusted_verifiers=(VERIFIER,),
        )
        self.assertEqual(replay.receipt_sha256, state.receipt_sha256)
        self.assertTrue(receipt.idempotent_replay)

    def test_conflicting_directive_replay_is_rejected(self) -> None:
        state, registry = bound_state()
        changed = directive()
        changed["observed_at"] = "2026-09-01T08:00:00+02:00"
        registry["directive-proof-001"] = evidence_receipt(
            "directive-proof-001", "directive:directive-real-001", changed
        )
        with self.assertRaisesRegex(ValueError, "DIRECTIVE_REPLAY_CONFLICT"):
            bind_eligible_directive(
                state, cohort_manifest(), changed,
                evidence_registry=registry, trusted_verifiers=(VERIFIER,),
            )

    def test_observation_without_trusted_receipt_fails_closed(self) -> None:
        state, registry = bound_state()
        with self.assertRaisesRegex(ValueError, "EVIDENCE_REFERENCE_UNRESOLVED"):
            ingest_owner_value_observation(
                state, observation("BASELINE"),
                evidence_registry=registry, trusted_verifiers=(VERIFIER,),
            )

    def test_synthetic_shadow_and_replayed_observations_are_rejected(self) -> None:
        state, registry = bound_state()
        for field in ("synthetic", "shadow", "replayed"):
            item = observation("BASELINE")
            item[field] = True
            ref = str(item["proof_refs"][0])
            registry[ref] = evidence_receipt(ref, f"owner-value:{item['observation_id']}", item)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field.upper()):
                ingest_owner_value_observation(
                    state, item, evidence_registry=registry, trusted_verifiers=(VERIFIER,)
                )

    def test_observation_must_explicitly_be_real(self) -> None:
        state, registry = bound_state()
        item = observation("BASELINE")
        item["real_observation"] = False
        ref = str(item["proof_refs"][0])
        registry[ref] = evidence_receipt(ref, f"owner-value:{item['observation_id']}", item)
        with self.assertRaisesRegex(ValueError, "REAL_OBSERVATION_REQUIRED"):
            ingest_owner_value_observation(
                state, item, evidence_registry=registry, trusted_verifiers=(VERIFIER,)
            )

    def test_observation_identity_mismatch_is_rejected(self) -> None:
        state, registry = bound_state()
        item = observation("BASELINE")
        item["oracle_id"] = "wrong-oracle"
        registry["observation-proof-baseline"] = evidence_receipt(
            "observation-proof-baseline", f"owner-value:{item['observation_id']}", item
        )
        with self.assertRaisesRegex(ValueError, "ORACLE_MISMATCH"):
            ingest_owner_value_observation(
                state, item, evidence_registry=registry, trusted_verifiers=(VERIFIER,)
            )

    def test_one_real_observation_does_not_make_pair_ready(self) -> None:
        state, registry = bound_state()
        item = observation("BASELINE")
        registry["observation-proof-baseline"] = evidence_receipt(
            "observation-proof-baseline", f"owner-value:{item['observation_id']}", item
        )
        state, receipt = ingest_owner_value_observation(
            state, item, evidence_registry=registry, trusted_verifiers=(VERIFIER,)
        )
        self.assertFalse(receipt.pair_ready)
        self.assertEqual(state.collected_observation_count, 1)
        self.assertEqual(state.pair_ready_count, 0)
        self.assertFalse(state.owner_value_proven)

    def test_pair_is_ready_only_after_two_trusted_real_observations(self) -> None:
        state, registry = bound_state()
        for variant in ("BASELINE", "BUBBLES"):
            item = observation(variant)
            ref = str(item["proof_refs"][0])
            registry[ref] = evidence_receipt(ref, f"owner-value:{item['observation_id']}", item)
            state, receipt = ingest_owner_value_observation(
                state, item, evidence_registry=registry, trusted_verifiers=(VERIFIER,)
            )
        self.assertTrue(receipt.pair_ready)
        self.assertEqual(state.pair_ready_count, 1)
        self.assertEqual(state.bindings[0].status, "PAIR_READY_FOR_SEPARATE_FOUNDRY_EVALUATION")
        self.assertFalse(state.owner_value_proven)
        self.assertFalse(state.stable_promotion_allowed)

    def test_exact_observation_replay_is_idempotent_and_conflict_is_rejected(self) -> None:
        state, registry = bound_state()
        item = observation("BASELINE")
        registry["observation-proof-baseline"] = evidence_receipt(
            "observation-proof-baseline", f"owner-value:{item['observation_id']}", item
        )
        state, _ = ingest_owner_value_observation(
            state, item, evidence_registry=registry, trusted_verifiers=(VERIFIER,)
        )
        replay, receipt = ingest_owner_value_observation(
            state, item, evidence_registry=registry, trusted_verifiers=(VERIFIER,)
        )
        self.assertEqual(replay.receipt_sha256, state.receipt_sha256)
        self.assertTrue(receipt.idempotent_replay)
        changed = deepcopy(item)
        changed["elapsed_seconds"] = 901
        registry["observation-proof-baseline"] = evidence_receipt(
            "observation-proof-baseline", f"owner-value:{changed['observation_id']}", changed
        )
        with self.assertRaisesRegex(ValueError, "OBSERVATION_REPLAY_CONFLICT"):
            ingest_owner_value_observation(
                state, changed, evidence_registry=registry, trusted_verifiers=(VERIFIER,)
            )

    def test_state_receipt_is_deterministic_and_tamper_evident(self) -> None:
        first = initialize_collector(cohort_manifest(), source_base_sha=HEAD)
        second = initialize_collector(cohort_manifest(), source_base_sha=HEAD)
        self.assertEqual(first.receipt_sha256, second.receipt_sha256)
        payload = first.to_dict()
        payload["pair_ready_count"] = 1
        with self.assertRaisesRegex(ValueError, "STATE_RECEIPT_HASH_MISMATCH"):
            validate_collector_state(payload)
        self.assertEqual(canonical_state_hash(first.to_dict()), first.receipt_sha256)

    def test_inputs_are_not_mutated(self) -> None:
        manifest = cohort_manifest()
        item = directive()
        manifest_before, item_before = deepcopy(manifest), deepcopy(item)
        registry = {"directive-proof-001": evidence_receipt(
            "directive-proof-001", "directive:directive-real-001", item
        )}
        bind_eligible_directive(
            initialize_collector(manifest, source_base_sha=HEAD), manifest, item,
            evidence_registry=registry, trusted_verifiers=(VERIFIER,),
        )
        self.assertEqual(manifest, manifest_before)
        self.assertEqual(item, item_before)

    def test_cli_initializes_source_level_state_without_runtime_effect(self) -> None:
        request = {
            "action": "initialize",
            "source_base_sha": HEAD,
            "cohort_manifest": cohort_manifest(),
        }
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.json"
            output_path = Path(directory) / "output.json"
            input_path.write_text(json.dumps(request), encoding="utf-8")
            with patch("sys.argv", ["collector", "--input", str(input_path), "--output", str(output_path)]):
                self.assertEqual(main(), 0)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            validate_collector_state(payload["state"])
            self.assertFalse(payload["state"]["provider_runtime_deployed"])

    def test_repository_collector_registration_is_valid_and_empty(self) -> None:
        root = Path(__file__).resolve().parents[1]
        payload = json.loads(
            (root / "benchmarking/cfbe_omega/cohorts/CFBE_VALUE_FOUNDRY_COLLECTOR_001.json")
            .read_text(encoding="utf-8")
        )
        validate_collector_state(payload)
        self.assertEqual(payload["bound_directive_count"], 0)
        self.assertEqual(payload["collected_observation_count"], 0)
        self.assertEqual(payload["pair_ready_count"], 0)


if __name__ == "__main__":
    unittest.main()
