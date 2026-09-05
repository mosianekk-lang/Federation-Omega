from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from bubbles.chat_governor_omega3.state import DurableState, EvidencePointer
from federation.fuse_serving_kernel_v1 import (
    ContextContract,
    EffectReceipt,
    FUSEServingKernelV1,
    PolicyDecisionReceipt,
    ServingLaneSpec,
)
from federation.mission_ir import MissionIR
from federation.sol62_effect_adapter_v1 import (
    ProviderEffectObservation,
    Sol62EffectExecutorV1,
    Sol62LaneBinding,
)
from federation.uas_runtime_v1 import EvaluationEvidence, UASRuntimeEvaluator
from sol_61_runtime.sol_62_frontier_primitives import GatewayPolicy, WorkloadIdentityPolicy
from sol_61_runtime.sol_62_runtime import MissionSpec, Sol62Runtime, TransitionSpec


def mission(
    mission_id: str,
    *,
    effect_class: str = "NO_EFFECT",
    proof_requirements: tuple[str, ...] = ("SOURCE",),
    max_cost_microunits: int | None = None,
    latency_target_ms: int | None = None,
) -> MissionIR:
    return MissionIR(
        mission_id=mission_id,
        objective="Execute a bounded FUSE serving-kernel regression mission",
        domain="FUSE",
        outcome_contract="All required lanes complete with UAS PASS",
        source_frontier="test-main",
        privacy_class="PRIVATE",
        rights_state="OWNER_CONTROLLED",
        effect_class=effect_class,
        owner_approval_required=effect_class == "CONSEQUENTIAL_EFFECT",
        rollback_required=True,
        authority_requirements=("A1_INTERNAL",) if effect_class not in {"NO_EFFECT", "READ_ONLY"} else (),
        proof_requirements=proof_requirements,
        max_cost_microunits=max_cost_microunits,
        latency_target_ms=latency_target_ms,
    )


class AllowPolicyGate:
    def authorize(self, *, mission: MissionIR, lane: ServingLaneSpec):
        return PolicyDecisionReceipt.create(
            decision="ALLOW",
            policy_ref="git://fkpf/federation.rego@test",
            input_sha256="a" * 64,
            result_sha256="b" * 64,
        )


class DenyPolicyGate:
    def authorize(self, *, mission: MissionIR, lane: ServingLaneSpec):
        return PolicyDecisionReceipt.create(
            decision="DENY",
            policy_ref="git://fkpf/federation.rego@test",
            input_sha256="c" * 64,
            result_sha256="d" * 64,
            reason="TEST_DENY",
        )


class FakeEffectExecutor:
    def execute(self, *, mission: MissionIR, lane: ServingLaneSpec, handler):
        handler()
        return EffectReceipt.verified(
            observed_state=dict(lane.expected_target_state),
            proof_axes=("PROVIDER_READBACK",),
            proof_refs=("receipt://provider/readback",),
            provider_ref="provider-run-1",
        )


class FUSEServingKernelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = DurableState(str(Path(self.tmp.name) / "fuse.sqlite3"))

    def tearDown(self):
        self.tmp.cleanup()

    def _verified_context(self, source_id: str = "aiu-master", version: str = "1") -> ContextContract:
        self.state.put_evidence(
            EvidencePointer(
                source_id=source_id,
                source_type="canonical",
                title="Canonical source",
                version=version,
                verified=True,
                verified_at="2026-09-05T05:10:00+02:00",
                sha256="abc",
            )
        )
        return ContextContract(
            required_source_ids=(source_id,),
            source_versions={source_id: version},
            minimum_verified_sources=1,
        )

    def test_missing_canonical_context_blocks_before_handler(self):
        called = []
        kernel = FUSEServingKernelV1(self.state)
        receipt = kernel.run(
            mission("context-block"),
            context=ContextContract(required_source_ids=("missing-master",), minimum_verified_sources=1),
            lanes=(ServingLaneSpec("research", "source_search", required_proof_axes=("SOURCE",)),),
            handlers={"research": lambda: called.append("ran")},
        )
        self.assertEqual(receipt.state, "HOLD_CONTEXT")
        self.assertEqual(called, [])
        self.assertFalse(self.state.latest_checkpoint("context-block")["proof_bearing"])

    def test_stale_canonical_context_holds(self):
        self._verified_context(version="1")
        kernel = FUSEServingKernelV1(self.state)
        receipt = kernel.run(
            mission("context-stale"),
            context=ContextContract(
                required_source_ids=("aiu-master",),
                source_versions={"aiu-master": "2"},
                minimum_verified_sources=1,
            ),
            lanes=(ServingLaneSpec("research", "source_search", required_proof_axes=("SOURCE",)),),
            handlers={"research": lambda: {"proof_axes": ("SOURCE",)}},
        )
        self.assertEqual(receipt.state, "HOLD_CONTEXT")

    def test_unearned_lane_proof_fails_closed(self):
        kernel = FUSEServingKernelV1(self.state)
        receipt = kernel.run(
            mission("proof-gap"),
            context=self._verified_context(),
            lanes=(ServingLaneSpec("research", "source_search", required_proof_axes=("SOURCE",)),),
            handlers={"research": lambda: {"result": "no proof"}},
        )
        self.assertEqual(receipt.state, "HOLD_UAS")
        self.assertEqual(receipt.lane_states["research"], "FAILED")
        self.assertNotIn("SOURCE", receipt.proof_axes)

    def test_optional_failed_lane_does_not_freeze_independent_required_lane(self):
        kernel = FUSEServingKernelV1(self.state, max_workers=2)

        def fail():
            raise RuntimeError("optional provider unavailable")

        receipt = kernel.run(
            mission("lane-isolation"),
            context=self._verified_context(),
            lanes=(
                ServingLaneSpec(
                    "canonical",
                    "canonical_read",
                    required_proof_axes=("SOURCE",),
                    required=True,
                ),
                ServingLaneSpec(
                    "optional",
                    "optional_challenger",
                    required=False,
                ),
            ),
            handlers={
                "canonical": lambda: {"proof_axes": ("SOURCE",), "proof_refs": ("source://canonical",)},
                "optional": fail,
            },
        )
        self.assertEqual(receipt.lane_states["canonical"], "COMPLETE")
        self.assertEqual(receipt.lane_states["optional"], "FAILED")
        self.assertEqual(receipt.state, "COMPLETE")

    def test_effectful_lane_requires_policy_gate(self):
        called = []
        kernel = FUSEServingKernelV1(self.state, effect_executor=FakeEffectExecutor())
        receipt = kernel.run(
            mission(
                "effect-no-policy",
                effect_class="BOUNDED_EFFECT",
                proof_requirements=("POLICY_ALLOW", "PROVIDER_READBACK"),
            ),
            context=self._verified_context(),
            lanes=(
                ServingLaneSpec(
                    "effect",
                    "provider_write",
                    effect_class="BOUNDED_EFFECT",
                    expected_target_state={"status": "PUBLISHED"},
                    required_proof_axes=("POLICY_ALLOW", "PROVIDER_READBACK"),
                ),
            ),
            handlers={"effect": lambda: called.append("ran")},
        )
        self.assertEqual(receipt.state, "HOLD_UAS")
        self.assertEqual(receipt.lane_states["effect"], "FAILED")
        self.assertEqual(called, [])

    def test_policy_denial_blocks_before_effect_executor(self):
        called = []
        kernel = FUSEServingKernelV1(
            self.state,
            policy_gate=DenyPolicyGate(),
            effect_executor=FakeEffectExecutor(),
        )
        receipt = kernel.run(
            mission(
                "effect-denied",
                effect_class="BOUNDED_EFFECT",
                proof_requirements=("POLICY_ALLOW", "PROVIDER_READBACK"),
            ),
            context=self._verified_context(),
            lanes=(
                ServingLaneSpec(
                    "effect",
                    "provider_write",
                    effect_class="BOUNDED_EFFECT",
                    expected_target_state={"status": "PUBLISHED"},
                    required_proof_axes=("POLICY_ALLOW", "PROVIDER_READBACK"),
                ),
            ),
            handlers={"effect": lambda: called.append("ran")},
        )
        self.assertEqual(receipt.state, "HOLD_UAS")
        self.assertEqual(called, [])

    def test_effectful_lane_requires_transactional_executor(self):
        kernel = FUSEServingKernelV1(self.state, policy_gate=AllowPolicyGate())
        receipt = kernel.run(
            mission(
                "effect-no-runtime",
                effect_class="BOUNDED_EFFECT",
                proof_requirements=("POLICY_ALLOW", "PROVIDER_READBACK"),
            ),
            context=self._verified_context(),
            lanes=(
                ServingLaneSpec(
                    "effect",
                    "provider_write",
                    effect_class="BOUNDED_EFFECT",
                    expected_target_state={"status": "PUBLISHED"},
                    required_proof_axes=("POLICY_ALLOW", "PROVIDER_READBACK"),
                ),
            ),
            handlers={"effect": lambda: {"dispatch": "would-run"}},
        )
        self.assertEqual(receipt.state, "HOLD_UAS")
        self.assertEqual(receipt.lane_states["effect"], "FAILED")

    def test_effectful_lane_completes_only_after_policy_and_verified_readback(self):
        kernel = FUSEServingKernelV1(
            self.state,
            policy_gate=AllowPolicyGate(),
            effect_executor=FakeEffectExecutor(),
        )
        receipt = kernel.run(
            mission(
                "effect-verified",
                effect_class="BOUNDED_EFFECT",
                proof_requirements=("POLICY_ALLOW", "PROVIDER_READBACK"),
            ),
            context=self._verified_context(),
            lanes=(
                ServingLaneSpec(
                    "effect",
                    "provider_write",
                    effect_class="BOUNDED_EFFECT",
                    expected_target_state={"status": "PUBLISHED"},
                    required_proof_axes=("POLICY_ALLOW", "PROVIDER_READBACK"),
                ),
            ),
            handlers={"effect": lambda: {"dispatch": "performed"}},
        )
        self.assertEqual(receipt.state, "COMPLETE")
        self.assertEqual(receipt.lane_states["effect"], "COMPLETE")
        self.assertIn("POLICY_ALLOW", receipt.proof_axes)
        self.assertIn("PROVIDER_READBACK", receipt.proof_axes)
        self.assertTrue(self.state.latest_checkpoint("effect-verified")["proof_bearing"])


class Sol62EffectAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.state = DurableState(str(root / "fuse.sqlite3"))
        self.runtime = Sol62Runtime(
            root / "sol62",
            gateway_policy=GatewayPolicy("sol-gateway", "sol-6.2"),
            identity_policy=WorkloadIdentityPolicy(
                allowed_issuers={"https://token.actions.githubusercontent.com"},
                audience="sol-runtime",
                subject_prefix="repo:mosianekk-lang/Federation-Omega:",
                max_ttl_seconds=600,
            ),
        )
        self.state.put_evidence(
            EvidencePointer(
                source_id="aiu-master",
                source_type="canonical",
                title="Canonical source",
                version="1",
                verified=True,
                verified_at="2026-09-05T05:10:00+02:00",
                sha256="abc",
            )
        )
        self.now = int(time.time())

    def tearDown(self):
        self.runtime.close()
        self.tmp.cleanup()

    def _claims(self):
        return {
            "iss": "https://token.actions.githubusercontent.com",
            "aud": "sol-runtime",
            "sub": "repo:mosianekk-lang/Federation-Omega:ref:refs/heads/main",
            "iat": self.now - 10,
            "exp": self.now + 300,
            "credential_type": "oidc",
        }

    def _gateway(self, *_):
        return {
            "runtime_id": "sol-6.2",
            "via_gateway": "sol-gateway",
            "authenticated_principal": "spiffe://fuse/proof-worker",
            "policy_version": "6.2",
        }

    def _prepare(self, mission_id: str = "sol-effect"):
        self.runtime.register_mission(
            MissionSpec(
                mission_id,
                "FUSE SOL62 effect regression",
                {"state": "CANDIDATE"},
                {"state": "PUBLISHED"},
            )
        )
        self.runtime.register_transition(
            TransitionSpec(
                "publish",
                mission_id,
                "publish",
                "repo/main",
                {"state": "CANDIDATE"},
                {"state": "PUBLISHED"},
                source_version="abc",
            )
        )
        binding = Sol62LaneBinding(
            transition_id="publish",
            effect_id="publish-effect",
            provider="github",
            payload={"artifact": "candidate"},
            semantics="IDEMPOTENT",
            idempotency_key="fuse-sol62-idem-1",
            actor="proof-worker",
            worker="proof-worker",
            source_version="abc",
        )
        return Sol62EffectExecutorV1(
            self.runtime,
            bindings={"effect": binding},
            gateway_request_factory=self._gateway,
            identity_claims_factory=lambda *_: self._claims(),
            now_epoch=lambda: self.now,
        )

    def test_real_sol62_adapter_executes_verified_transition(self):
        adapter = self._prepare()
        kernel = FUSEServingKernelV1(
            self.state,
            policy_gate=AllowPolicyGate(),
            effect_executor=adapter,
        )
        receipt = kernel.run(
            mission(
                "sol-effect",
                effect_class="BOUNDED_EFFECT",
                proof_requirements=("POLICY_ALLOW", "PROVIDER_READBACK"),
            ),
            context=ContextContract(
                required_source_ids=("aiu-master",),
                source_versions={"aiu-master": "1"},
                minimum_verified_sources=1,
            ),
            lanes=(
                ServingLaneSpec(
                    "effect",
                    "publish",
                    effect_class="BOUNDED_EFFECT",
                    expected_target_state={"status": "ok"},
                    required_proof_axes=("POLICY_ALLOW", "PROVIDER_READBACK"),
                ),
            ),
            handlers={
                "effect": lambda: ProviderEffectObservation(
                    provider_ref="github-run-1",
                    readback={"status": "ok"},
                    proof_refs=("provider://github-run-1",),
                )
            },
        )
        self.assertEqual(receipt.state, "COMPLETE")
        self.assertIn("POLICY_ALLOW", receipt.proof_axes)
        self.assertIn("PROVIDER_READBACK", receipt.proof_axes)
        self.assertEqual(self.runtime.mission_state("sol-effect")["value"]["state"], "PUBLISHED")
        self.assertEqual(self.runtime.transition_status("publish")["value"]["status"], "VERIFIED")

    def test_sol62_readback_mismatch_holds_and_preserves_uncertain_effect(self):
        adapter = self._prepare("sol-mismatch")
        kernel = FUSEServingKernelV1(
            self.state,
            policy_gate=AllowPolicyGate(),
            effect_executor=adapter,
        )
        receipt = kernel.run(
            mission(
                "sol-mismatch",
                effect_class="BOUNDED_EFFECT",
                proof_requirements=("POLICY_ALLOW", "PROVIDER_READBACK"),
            ),
            context=ContextContract(
                required_source_ids=("aiu-master",),
                source_versions={"aiu-master": "1"},
                minimum_verified_sources=1,
            ),
            lanes=(
                ServingLaneSpec(
                    "effect",
                    "publish",
                    effect_class="BOUNDED_EFFECT",
                    expected_target_state={"status": "ok"},
                    required_proof_axes=("POLICY_ALLOW", "PROVIDER_READBACK"),
                ),
            ),
            handlers={
                "effect": lambda: ProviderEffectObservation(
                    provider_ref="github-run-mismatch",
                    readback={"status": "wrong"},
                )
            },
        )
        self.assertEqual(receipt.state, "HOLD_UAS")
        effect = self.runtime.control.db.execute(
            "SELECT state FROM effects WHERE effect_id='publish-effect'"
        ).fetchone()
        self.assertEqual(effect["state"], "FAILED_UNCERTAIN")
        self.assertEqual(self.runtime.mission_state("sol-mismatch")["value"]["state"], "CANDIDATE")


class UASRuntimeTests(unittest.TestCase):
    def test_declared_cost_and_latency_targets_require_observation(self):
        evaluator = UASRuntimeEvaluator()
        result = evaluator.evaluate(
            mission("telemetry", max_cost_microunits=100, latency_target_ms=500),
            EvaluationEvidence(outcome_ok=True, proof_axes=("SOURCE",)),
        )
        self.assertEqual(result.state, "HOLD")
        self.assertIn("COST_EVIDENCE_MISSING", result.hard_blockers)
        self.assertIn("LATENCY_EVIDENCE_MISSING", result.hard_blockers)

    def test_statistical_promotion_uses_lower_confidence_bound(self):
        evaluator = UASRuntimeEvaluator()
        hold = evaluator.promotion_decision(
            successes=95,
            trials=100,
            minimum_lower_bound=0.90,
        )
        promote = evaluator.promotion_decision(
            successes=99,
            trials=100,
            minimum_lower_bound=0.90,
        )
        self.assertEqual(hold["state"], "HOLD")
        self.assertEqual(promote["state"], "PROMOTE")


if __name__ == "__main__":
    unittest.main()
