from __future__ import annotations

import unittest

from evidenceops.veritas.adapter import (
    AUTHORITY_CEILING,
    CANONICAL_SERVICE_ID,
    VeritasAdapter,
    VeritasRequest,
)


def synthetic_evaluator(request: VeritasRequest):
    return {
        "service_id": CANONICAL_SERVICE_ID,
        "operation": request.operation,
        "finding_count": 1,
        "findings": ("SYNTHETIC_NO_EFFECT_FINDING",),
        "external_effect": False,
    }


class VeritasSixContractAdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapter = VeritasAdapter(synthetic_evaluator)
        self.request = VeritasRequest(
            request_id="VER-SYNTH-001",
            matter_id="SYNTHETIC-MATTER",
            operation="FALSIFY",
            objective="Attempt to falsify one synthetic proposition",
            source_refs=("SYNTHETIC:SOURCE:001",),
            payload={"proposition": "synthetic proposition"},
        )

    def test_describe_exposes_exact_six_contracts_and_a0(self):
        description = self.adapter.describe()
        self.assertEqual(description["service_id"], CANONICAL_SERVICE_ID)
        self.assertEqual(description["authority_ceiling"], AUTHORITY_CEILING)
        self.assertFalse(description["external_effect"])
        self.assertEqual(
            description["contracts"],
            ("DESCRIBE", "ACCEPT", "AUTHORISE", "EXECUTE", "PROVE", "RECOVER"),
        )

    def test_full_a0_no_effect_contract_path(self):
        accepted = self.adapter.accept(self.request)
        self.assertEqual(accepted.request_id, self.request.request_id)
        decision = self.adapter.authorise(self.request.request_id)
        self.assertTrue(decision.allowed)
        output = self.adapter.execute(self.request.request_id)
        self.assertFalse(output["external_effect"])
        proof = self.adapter.prove(self.request.request_id)
        self.assertEqual(proof.service_id, CANONICAL_SERVICE_ID)
        self.assertEqual(proof.authority, "A0")
        self.assertFalse(proof.external_effect)
        self.assertEqual(proof.state, "EXECUTED_A0_NO_EFFECT_PROOF_BOUND")
        self.assertEqual(len(proof.request_sha256), 64)
        self.assertEqual(len(proof.output_sha256), 64)
        recovery = self.adapter.recover(self.request.request_id)
        self.assertEqual(recovery["restored_to"], "ACCEPTED")
        self.assertFalse(recovery["external_effect"])
        with self.assertRaises(ValueError):
            self.adapter.prove(self.request.request_id)

    def test_external_effect_is_rejected_before_acceptance(self):
        request = VeritasRequest(
            **{**self.request.__dict__, "request_id": "VER-SYNTH-002", "external_effect": True}
        )
        with self.assertRaises(PermissionError):
            self.adapter.accept(request)

    def test_authority_inheritance_is_rejected(self):
        request = VeritasRequest(
            **{**self.request.__dict__, "request_id": "VER-SYNTH-003", "authority": "A1_INTERNAL"}
        )
        with self.assertRaises(PermissionError):
            self.adapter.accept(request)

    def test_execute_requires_accept_and_authorise(self):
        with self.assertRaises(ValueError):
            self.adapter.execute("MISSING")
        self.adapter.accept(self.request)
        with self.assertRaises(PermissionError):
            self.adapter.execute(self.request.request_id)

    def test_request_id_collision_is_fail_closed(self):
        self.adapter.accept(self.request)
        changed = VeritasRequest(
            **{**self.request.__dict__, "objective": "different objective"}
        )
        with self.assertRaises(ValueError):
            self.adapter.accept(changed)

    def test_evaluator_cannot_report_external_effect(self):
        adapter = VeritasAdapter(lambda request: {"external_effect": True})
        adapter.accept(self.request)
        self.assertTrue(adapter.authorise(self.request.request_id).allowed)
        with self.assertRaises(PermissionError):
            adapter.execute(self.request.request_id)


if __name__ == "__main__":
    unittest.main()
