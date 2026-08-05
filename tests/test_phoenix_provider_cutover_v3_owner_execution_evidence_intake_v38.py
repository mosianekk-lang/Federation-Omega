from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "phoenix" / "ops-template" / "owner_execution_evidence_intake.py"
)
HANDOFF_MODULE_PATH = ROOT / "phoenix" / "ops-template" / "owner_execution_handoff.py"

SPEC = importlib.util.spec_from_file_location(
    "owner_execution_evidence_intake_v38", MODULE_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

HANDOFF_SPEC = importlib.util.spec_from_file_location(
    "owner_execution_handoff_for_v38", HANDOFF_MODULE_PATH
)
assert HANDOFF_SPEC and HANDOFF_SPEC.loader
HANDOFF = importlib.util.module_from_spec(HANDOFF_SPEC)
sys.modules[HANDOFF_SPEC.name] = HANDOFF
HANDOFF_SPEC.loader.exec_module(HANDOFF)

RELEASE = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_owner_execution_handoff_release_receipt_v37.json"
)
V36_RELEASE = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_provider_attested_authorization_release_receipt_v36.json"
)
CONTRACT = (
    ROOT
    / "phoenix"
    / "ops-template"
    / "governance"
    / "OWNER_EXECUTION_EVIDENCE_INTAKE_CONTRACT.json"
)
CHECKPOINT = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_owner_execution_evidence_intake_checkpoint_v38.json"
)
PROJECTION = ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v38.json"
POLICY = ROOT / "phoenix" / "export_policy.json"
SOURCE_SHA = "36916cb0e26813e1bfb57a3c1a2993d82e7fd425"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def rehash(payload: dict, field: str) -> dict:
    body = dict(payload)
    body.pop(field, None)
    body[field] = MODULE.canonical_sha256(body)
    return body


class OwnerExecutionEvidenceIntakeV38Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.release = load(RELEASE)
        self.v36_release = load(V36_RELEASE)
        self.now = datetime(2026, 8, 5, 8, 2, 22, tzinfo=timezone.utc)
        self.handoff = HANDOFF.build_handoff(
            release_receipt=self.v36_release,
            current_source_sha=SOURCE_SHA,
            owner_login="mosianekk-lang",
            repository_full_name="mosianekk-lang/Federation-Omega",
            owner_packet_sha256=self.release["provider_proof"]["owner_packet_sha256"],
            generated_at=self.now,
        )

    def evidence(self, sequence: int) -> dict:
        step = self.handoff["ordered_steps"][sequence - 1]
        authority = step["authority"]
        mode = {
            "A1_INTERNAL": "INTERNAL_HASH_BOUND",
            "OWNER_RESERVED": "OWNER_ATTESTED_CANDIDATE",
            "GET_ONLY_PROVIDER_NATIVE": "PROVIDER_NATIVE_READBACK_CANDIDATE",
            "OWNER_RESERVED_EXTERNAL_COMMUNICATION": "OWNER_AND_PROVIDER_NATIVE_CANDIDATE",
            "OWNER_RESERVED_CONSEQUENTIAL_RELEASE": "OWNER_AND_PROVIDER_NATIVE_CANDIDATE",
        }[authority]
        body = {
            "schema": MODULE.EVIDENCE_SCHEMA,
            "status": "STEP_EVIDENCE_CANDIDATE_VERIFIED_NOT_PROVIDER_PROOF",
            "handoff_sha256": self.handoff["handoff_sha256"],
            "sequence": sequence,
            "step_id": step["id"],
            "stage": step["stage"],
            "authority": authority,
            "external_effect": step["external_effect"],
            "evidence_mode": mode,
            "artifact_sha256": hashlib.sha256(step["id"].encode()).hexdigest(),
            "recorded_at": self.now.isoformat().replace("+00:00", "Z"),
            "owner_attested": authority.startswith("OWNER_RESERVED"),
            "provider_native": authority in {
                "GET_ONLY_PROVIDER_NATIVE",
                "OWNER_RESERVED_EXTERNAL_COMMUNICATION",
                "OWNER_RESERVED_CONSEQUENTIAL_RELEASE",
            },
            "external_communication_performed": sequence == 4,
            "provider_apply_performed": sequence == 10,
            "mock_conformance": False,
            "credential_value_recorded": False,
            "external_commercial_gate_advanced": False,
        }
        body["evidence_sha256"] = MODULE.canonical_sha256(body)
        return body

    def build(self, evidence_chain):
        return MODULE.build_dossier(
            release_receipt=self.release,
            handoff=self.handoff,
            evidence_chain=evidence_chain,
            current_source_sha=SOURCE_SHA,
            generated_at=self.now,
        )

    def test_empty_dossier_is_hash_bound_and_names_first_step(self):
        result = self.build([])
        self.assertEqual(0, result["admitted_evidence_count"])
        self.assertEqual(1, result["next_eligible_step"]["sequence"])
        self.assertFalse(result["candidate_chain_complete"])
        self.assertFalse(result["owner_execution_proven"])
        self.assertFalse(result["provider_apply_proven"])
        claimed = result["dossier_sha256"]
        body = dict(result)
        body.pop("dossier_sha256")
        self.assertEqual(claimed, MODULE.canonical_sha256(body))

    def test_contiguous_candidate_chain_advances_only_next_step(self):
        result = self.build([self.evidence(1), self.evidence(2), self.evidence(3)])
        self.assertEqual(3, result["admitted_evidence_count"])
        self.assertEqual(4, result["next_eligible_step"]["sequence"])
        self.assertTrue(result["next_eligible_step"]["owner_reserved"])
        self.assertFalse(result["owner_execution_proven"])
        self.assertTrue(result["requires_independent_provider_native_verification"])

    def test_gap_fails_closed(self):
        with self.assertRaises(MODULE.OwnerExecutionEvidenceIntakeError):
            self.build([self.evidence(1), self.evidence(3)])

    def test_mock_conformance_fails_closed(self):
        evidence = self.evidence(1)
        evidence["mock_conformance"] = True
        evidence = rehash(evidence, "evidence_sha256")
        with self.assertRaises(MODULE.OwnerExecutionEvidenceIntakeError):
            self.build([evidence])

    def test_owner_reserved_evidence_requires_owner_attested_candidate(self):
        first = self.evidence(1)
        second = self.evidence(2)
        second["owner_attested"] = False
        second = rehash(second, "evidence_sha256")
        with self.assertRaises(MODULE.OwnerExecutionEvidenceIntakeError):
            self.build([first, second])

    def test_release_commercial_truth_inflation_fails_closed(self):
        self.release["commercial_truth"]["verified_live_revenue_events"] = 1
        self.release = rehash(self.release, "receipt_sha256")
        with self.assertRaises(MODULE.OwnerExecutionEvidenceIntakeError):
            self.build([])

    def test_contract_checkpoint_projection_and_export_truth(self):
        contract = load(CONTRACT)
        checkpoint = load(CHECKPOINT)
        projection = load(PROJECTION)
        policy = load(POLICY)

        MODULE._verify_hash(checkpoint, "checkpoint_sha256", "checkpoint")
        MODULE._verify_hash(projection, "projection_sha256", "projection")
        self.assertEqual(
            "CANDIDATE_INTAKE_NOT_OWNER_OR_PROVIDER_PROOF", contract["status"]
        )
        self.assertFalse(contract["controls"]["mock_conformance_admission_allowed"])
        self.assertFalse(contract["non_authoritative_effect"]["provider_apply_proven"])
        self.assertEqual(
            "OWNER_EXECUTION_EVIDENCE_INTAKE_IMPLEMENTED_PROVIDER_PROOF_REQUIRED_"
            "OWNER_ACTION_AND_FRESH_PROVIDER_AUTHORITY_REQUIRED",
            checkpoint["status"],
        )
        self.assertTrue(projection["dependency_order_preserved"])
        self.assertTrue(projection["service_enabled_platform_first"])
        self.assertTrue(projection["self_service_saas_held"])
        self.assertEqual(0, projection["verified_live_revenue_events"])
        self.assertFalse(projection["full_commercial_maturity"])
        required = set(policy["ops"]["required_files"])
        self.assertEqual("1.0.19", policy["version"])
        self.assertIn("owner_execution_evidence_intake.py", required)
        self.assertIn(
            "governance/OWNER_EXECUTION_EVIDENCE_INTAKE_CONTRACT.json", required
        )


if __name__ == "__main__":
    unittest.main()
