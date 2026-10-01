from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from frontier_convergence.core import PrivacyEnvelope
from frontier_convergence.gemini_adapter import GeminiAdapter
from frontier_convergence.intelligence_formation_v2 import (
    FormationMode,
    IntelligenceCandidate,
    IntelligenceFormationCompiler,
)

ROOT = Path(__file__).resolve().parents[1]


def candidate(
    cell_id: str,
    provider: str,
    model: str,
    domains: tuple[str, ...],
    quality: float,
) -> IntelligenceCandidate:
    return IntelligenceCandidate(
        cell_id=cell_id,
        provider=provider,
        model_ref=model,
        capabilities=("reasoning",),
        correlation_domains=domains,
        authority_pass=True,
        privacy_pass=True,
        currentness_pass=True,
        capability_pass=True,
        budget_pass=True,
        proof_floor_pass=True,
        recovery_pass=True,
        quality=quality,
        reliability=0.99,
        latency_ms=100,
        cost=0.01,
        owner_burden=0.0,
    )


class FuseGoogleIntelligenceRuntimeV2Tests(unittest.TestCase):
    def test_contract_prompt_and_predecessor_are_hash_bound(self) -> None:
        contract = json.loads(
            (ROOT / "config" / "fuse-google-intelligence-runtime-v2.json").read_text(encoding="utf-8")
        )
        prompt = (ROOT / contract["prompt_path"]).read_bytes()
        self.assertEqual(contract["schema"], "FUSE_GOOGLE_INTELLIGENCE_RUNTIME_V2")
        self.assertEqual(contract["version"], "2.0.0")
        self.assertEqual(hashlib.sha256(prompt).hexdigest(), contract["prompt_sha256"])
        self.assertEqual(contract["primary_google_protocol"], "VERTEX_AI_INTERACTIONS_REST")
        self.assertEqual(contract["primary_google_model_candidate"], "gemini-3.8-flash")
        self.assertEqual(contract["incumbent_google_model"], "gemini-2.5-flash")
        self.assertEqual(contract["champion_state"], "CANDIDATE_REQUIRES_MATCHED_COURT")
        self.assertIs(contract["sensitive_default_store"], False)
        self.assertIs(contract["matched_champion_promotion_required"], True)
        self.assertIs(contract["predecessor"]["rollback_preserved"], True)

    def test_interactions_plan_defaults_stateless_and_keyless(self) -> None:
        plan = GeminiAdapter.compile_interaction(
            mission_id="M",
            input_data="hello",
        )
        self.assertEqual(plan.protocol, "VERTEX_AI_INTERACTIONS_REST")
        self.assertEqual(plan.model_ref, "gemini-3.8-flash")
        self.assertEqual(plan.credential_reference, "GITHUB_WIF_ADC")
        self.assertIs(plan.request_body["store"], False)
        self.assertIn("interaction_id", plan.required_readback_fields)
        self.assertIn("response_digest", plan.required_readback_fields)

    def test_interactions_privacy_envelope_filters_mapping_input(self) -> None:
        env = PrivacyEnvelope.create(
            data_classification="owner_private",
            permitted_fields=["prompt"],
        )
        plan = GeminiAdapter.compile_interaction(
            mission_id="M",
            input_data={"prompt": "safe", "private": "drop"},
            privacy_envelope=env,
        )
        self.assertEqual(plan.request_body["input"], {"prompt": "safe"})
        self.assertIs(plan.request_body["store"], False)

    def test_stateless_interaction_rejects_provider_continuation(self) -> None:
        with self.assertRaisesRegex(ValueError, "STATELESS_INTERACTION_CANNOT_REFERENCE_PREVIOUS"):
            GeminiAdapter.compile_interaction(
                mission_id="M",
                input_data="x",
                store=False,
                previous_interaction_id="int_123",
            )
        with self.assertRaisesRegex(ValueError, "STATELESS_INTERACTION_CANNOT_RUN_BACKGROUND"):
            GeminiAdapter.compile_interaction(
                mission_id="M",
                input_data="x",
                store=False,
                background=True,
            )

    def test_interactions_readback_requires_interaction_identity(self) -> None:
        plan = GeminiAdapter.compile_interaction(mission_id="M", input_data="x")
        readback = {field: "x" for field in plan.required_readback_fields}
        readback.pop("interaction_id")
        ok, missing = GeminiAdapter.validate_readback(plan, readback)
        self.assertFalse(ok)
        self.assertIn("interaction_id", missing)
        readback["interaction_id"] = "int_1"
        ok2, missing2 = GeminiAdapter.validate_readback(plan, readback)
        self.assertTrue(ok2)
        self.assertEqual(missing2, ())

    def test_fast_formation_selects_best_eligible_candidate(self) -> None:
        plan = IntelligenceFormationCompiler.compile(
            mission_id="M",
            mode=FormationMode.FAST,
            required_capabilities=["reasoning"],
            candidates=[
                candidate("google", "GOOGLE", "gemini-3.8-flash", ("google", "vertex"), 0.95),
                candidate("openai", "OPENAI", "gpt", ("openai", "chatgpt"), 0.90),
            ],
        )
        self.assertEqual(plan.selected_cell_ids, ("google",))

    def test_fusion_requires_independent_domains(self) -> None:
        same_a = candidate("g1", "GOOGLE", "m1", ("google", "vertex"), 0.95)
        same_b = candidate("g2", "GOOGLE", "m2", ("google", "vertex"), 0.94)
        with self.assertRaisesRegex(ValueError, "FORMATION_INDEPENDENCE_NOT_PROVEN"):
            IntelligenceFormationCompiler.compile(
                mission_id="M",
                mode=FormationMode.FUSION,
                required_capabilities=["reasoning"],
                candidates=[same_a, same_b],
            )

        plan = IntelligenceFormationCompiler.compile(
            mission_id="M",
            mode=FormationMode.FUSION,
            required_capabilities=["reasoning"],
            candidates=[
                same_a,
                candidate("o1", "OPENAI", "gpt", ("openai", "chatgpt"), 0.93),
            ],
        )
        self.assertTrue(plan.independence_pass)
        self.assertEqual(len(plan.selected_cell_ids), 2)

    def test_hard_gate_failure_excludes_candidate(self) -> None:
        bad = IntelligenceCandidate(
            cell_id="bad",
            provider="GOOGLE",
            model_ref="gemini",
            capabilities=("reasoning",),
            correlation_domains=("google",),
            authority_pass=True,
            privacy_pass=False,
            currentness_pass=True,
            capability_pass=True,
            budget_pass=True,
            proof_floor_pass=True,
            recovery_pass=True,
            quality=1.0,
        )
        good = candidate("good", "OPENAI", "gpt", ("openai",), 0.5)
        plan = IntelligenceFormationCompiler.compile(
            mission_id="M",
            mode=FormationMode.FAST,
            required_capabilities=["reasoning"],
            candidates=[bad, good],
        )
        self.assertEqual(plan.selected_cell_ids, ("good",))


if __name__ == "__main__":
    unittest.main()
