import json
import unittest
from copy import deepcopy
from pathlib import Path

from ao_harmonic_v3.failure_win_v2 import (
    FailureEventType,
    FailureObservation,
    FailureToOperationalWinKernelV2,
    FailureWinRequest,
    FailureWinState,
    RecoveryRoute,
)
from ao_harmonic_v3.models import PerformanceVector
from kaio_fluid.shadow import RegisteredSourceShadowValidator


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "tests" / "fixtures" / "federation_n_evidenceops_fevx_cse_v110.json"


class KaioRegisteredSourceShadowTests(unittest.TestCase):
    def load_packet(self):
        return json.loads(PACKET.read_text(encoding="utf-8"))

    def test_real_registered_source_packet_shadow_validates_without_provider_claim(self):
        result = RegisteredSourceShadowValidator().validate(self.load_packet())
        self.assertEqual("SHADOW_VALIDATED_REGISTERED_SOURCE_PACKET", result.status)
        self.assertEqual("evidenceops", result.domain)
        self.assertEqual(4, result.source_count)
        self.assertEqual(10, result.open_provider_proofs)
        self.assertEqual("A1_INTERNAL", result.authority_ceiling)
        self.assertFalse(result.external_effect)
        self.assertFalse(result.provider_mutation_permitted)
        self.assertFalse(result.provider_runtime_verified)
        self.assertIn("remain unverified", result.release_claim)

    def test_shadow_rejects_external_effect_or_provider_mutation(self):
        for field in ("external_effect", "provider_mutation_permitted"):
            packet = self.load_packet()
            packet[field] = True
            with self.assertRaises(ValueError):
                RegisteredSourceShadowValidator().validate(packet)

    def test_shadow_rejects_missing_sources(self):
        packet = self.load_packet()
        packet["sources"] = []
        with self.assertRaises(ValueError):
            RegisteredSourceShadowValidator().validate(packet)

    def test_shadow_rejects_authority_prefix_and_suffix_bypass(self):
        for authority in (
            "A1_INTERNAL",
            "A1_INTERNAL_WRITE",
            "A1_INTERNAL_READ_ONLY_EXTRA",
            "A2_EXTERNAL",
        ):
            packet = self.load_packet()
            packet["authority_ceiling"] = authority
            with self.assertRaises(ValueError):
                RegisteredSourceShadowValidator().validate(packet)

    def test_shadow_rejects_blank_or_duplicate_source_identity(self):
        blank_packet = self.load_packet()
        blank_packet["sources"][0]["source_id"] = "  "
        with self.assertRaises(ValueError):
            RegisteredSourceShadowValidator().validate(blank_packet)

        duplicate_packet = self.load_packet()
        duplicate_packet["sources"][1]["source_id"] = duplicate_packet["sources"][0]["source_id"]
        with self.assertRaises(ValueError):
            RegisteredSourceShadowValidator().validate(duplicate_packet)

    def test_shadow_rejects_promoted_or_missing_provider_proof_state(self):
        for promoted_state in ("PROVIDER_VERIFIED", "VERIFIED", ""):
            packet = self.load_packet()
            packet["required_provider_proof"] = deepcopy(packet["required_provider_proof"])
            packet["required_provider_proof"][0]["initial_state"] = promoted_state
            with self.assertRaises(ValueError):
                RegisteredSourceShadowValidator().validate(packet)

    def test_shadow_is_deterministic(self):
        validator = RegisteredSourceShadowValidator()
        first = validator.validate(self.load_packet())
        second = validator.validate(self.load_packet())
        self.assertEqual(first, second)

    def test_failure_win_v2_kaio_receiver_canary_preserves_provider_boundary(self):
        native = RegisteredSourceShadowValidator().validate(self.load_packet())
        self.assertEqual("SHADOW_VALIDATED_REGISTERED_SOURCE_PACKET", native.status)
        self.assertFalse(native.external_effect)
        self.assertFalse(native.provider_runtime_verified)

        incumbent = PerformanceVector(quality=8, reliability=8, proof=8, speed=2, owner_burden=1)
        candidate = PerformanceVector(
            quality=8, reliability=8, proof=8, speed=5,
            owner_time_recovered=2, recovery_gain=2, owner_burden=0,
        )
        result = FailureToOperationalWinKernelV2().evaluate(
            FailureWinRequest(
                observation=FailureObservation(
                    event_id="FWV2-KAIO-PRECURSOR-CANARY",
                    event_type=FailureEventType.PRECURSOR_RISK,
                    system_id="KAIO Ω",
                    objective="preempt a synthetic registered-source assurance drift",
                    claim="a registered-source packet may drift from its proof boundary",
                    observed_fruit="synthetic shadow validation only; no provider effect",
                    desired_outcome="prewarm a current registered-source validation route",
                    failure_code="SYNTHETIC_KAIO_SOURCE_DRIFT",
                    material=False,
                    precursor_signals=("source-drift-fixture", "provider-proof-fixture"),
                ),
                incumbent=incumbent,
                routes=(RecoveryRoute(
                    route_id="kaio-current-shadow-validation-fixture",
                    route_type="REROUTE",
                    performance=candidate,
                    proof_strength=1.0,
                    reversibility=1.0,
                    strategic_value=1.0,
                    expected_value=2.0,
                ),),
            )
        )
        self.assertEqual(FailureWinState.PREEMPTION_READY, result.state)
        self.assertTrue(result.vector_gate_passed)
        self.assertFalse(result.proof_graph.complete)
        self.assertNotEqual(FailureWinState.OPERATIONAL_WIN_VERIFIED, result.state)


if __name__ == "__main__":
    unittest.main()
