from __future__ import annotations

import tempfile
import unittest

from bubbles.autonomic_federation_runtime import (
    BubblesAutonomicFederationRuntime,
    WORK_AUTHORITY, WORK_EXECUTION, WORK_PROOF, WORK_READBACK, WORK_VALUE,
)
from bubbles.provider_authority_fabric import (
    AuthorityLeaseDecision, AuthorityState, CapabilityAuthorityContract,
)
from bubbles.provider_cell_mesh import ProviderCellHealth, ProviderCellSpec
from federation.action_admission_gate_v1 import ActionRequest, AuthorityGrant as SpineAuthorityGrant
from federation.autonomic_mission_spine_v1 import ActionExecutionBundle, AutonomicMissionSpine
from federation.capability_truth_v1 import CapabilityTruthRecord, ClaimKind, EvidenceRef, Maturity
from federation.cfbe_chat_hyperperformance_v1 import EffectClass, RouteProfile, WorkUnit
from federation.execution_readback_closure_v1 import ExecutionAttempt, SemanticReadback
from federation.execution_topology_compiler_v1 import TopologyTask
from federation.live_worker_attestation_v1 import CapabilityEpoch, WorkerAttestation, WorkerState
from federation.mission_capability_admission_v1 import MissionCapabilityRequirement
from federation.mission_ir import MissionIR
from federation.mission_outcome_value_court_v1 import OutcomeEvidence, RequiredAction, ValueObservation

SOURCE = "b" * 40
FRONTIER = f"main@{SOURCE}"
NOW = "2026-09-06T23:15:00+02:00"
TARGET = "github:repo:target"


def mission(effect_class: str = "READ_ONLY", *, approval: bool = False) -> MissionIR:
    authority = () if effect_class in {"NO_EFFECT", "READ_ONLY"} else ("github.repository.write",)
    return MissionIR(
        mission_id=f"BUB-AFR-{effect_class}",
        objective="Execute one bounded autonomic provider lifecycle with proof before claim.",
        domain="SYSTEMS",
        outcome_contract="Provider semantic result is independently read back or held.",
        source_frontier=FRONTIER,
        privacy_class="P1_INTERNAL",
        rights_state="AUTHORIZED_INTERNAL",
        effect_class=effect_class,
        owner_approval_required=approval,
        rollback_required=True,
        authority_requirements=authority,
        proof_requirements=("source", "semantic_readback", "independent_readback"),
        provider_allowlist=("github",),
        value_metrics=("owner_intervention_seconds", "elapsed_seconds"),
        max_cost_microunits=1000,
        latency_target_ms=5000,
        metadata={"authority_ceiling": "A2"},
    )


def cells() -> tuple[ProviderCellSpec, ...]:
    return (
        ProviderCellSpec(cell_id="github-read", provider="github", connector="github", capabilities=("repo.read",), supports_effect_classes=("READ_ONLY",), priority=80),
        ProviderCellSpec(cell_id="github-write", provider="github", connector="github", capabilities=("repo.write",), supports_effect_classes=("BOUNDED_EFFECT", "CONSEQUENTIAL_EFFECT"), priority=80),
    )


def health(cell_id: str, *, credential: bool) -> ProviderCellHealth:
    return ProviderCellHealth(
        cell_id=cell_id, provider_native=True, provider_live=True,
        semantic_readback_ready=True, credential_bound=credential,
        latency_ms=25, estimated_cost_microunits=0,
        proof_refs=(f"provider:{cell_id}:fresh",), observed_at=NOW,
    )


def effect_for(m: MissionIR) -> EffectClass:
    return {
        "NO_EFFECT": EffectClass.READ_ONLY,
        "READ_ONLY": EffectClass.READ_ONLY,
        "BOUNDED_EFFECT": EffectClass.INTERNAL_WRITE,
        "CONSEQUENTIAL_EFFECT": EffectClass.EXTERNAL_EFFECT,
    }[m.effect_class]


def spine_truth() -> dict[str, CapabilityTruthRecord]:
    ev = EvidenceRef("cap-e1", "CAP_A", ClaimKind.RUNTIME_RECEIPT, "provider:capability", Maturity.PROVIDER_RUNNING, fresh=True, independently_verified=True)
    return {"CAP_A": CapabilityTruthRecord("CAP_A").add(ev)}


def spine_epoch() -> CapabilityEpoch:
    return CapabilityEpoch("epoch-CAP_A", "CAP_A", "2026-09-06T22:30:00+02:00", "2026-09-07T00:30:00+02:00", "provider:epoch")


def spine_worker(m: MissionIR) -> WorkerAttestation:
    return WorkerAttestation(
        attestation_id="worker-att", worker_id="worker-1", capability_id="CAP_A",
        epoch_id="epoch-CAP_A", state=WorkerState.HEARTBEAT_VERIFIED,
        observed_at="2026-09-06T23:00:00+02:00", expires_at="2026-09-07T00:00:00+02:00",
        source_ref="provider:worker", runtime_id="runtime-1", mission_id=m.mission_id,
        tool_refs=("tool:github",), heartbeat_ref="provider:heartbeat", independently_verified=True,
    )


def spine_route() -> tuple[RouteProfile, ...]:
    return (RouteProfile(route_id="github-direct", surface="github", available=True, fresh=True, direct=True, proof_refs=("provider:route",)),)


def spine_task(m: MissionIR) -> TopologyTask:
    effect = effect_for(m)
    return TopologyTask(
        WorkUnit(unit_id="u1", surface="github", operation="provider-dispatch", input_fingerprint="payload:v1", effect_class=effect, cacheable=effect is not EffectClass.EXTERNAL_EFFECT),
        capability_id="CAP_A",
        mutation_domain="github:target" if effect is not EffectClass.READ_ONLY else "",
    )


def spine_request(m: MissionIR) -> ActionRequest:
    effect = effect_for(m)
    return ActionRequest(
        action_id="provider-action", unit_id="u1", effect_class=effect,
        target_scope=TARGET,
        mutation_domain="github:target" if effect is not EffectClass.READ_ONLY else "",
        provider="github",
    )


def spine_grant(m: MissionIR) -> SpineAuthorityGrant | None:
    effect = effect_for(m)
    if effect is EffectClass.READ_ONLY:
        return None
    return SpineAuthorityGrant(
        grant_id="spine-grant", mission_id=m.mission_id, action_id="provider-action",
        effect_class=effect, target_scope=TARGET, source_ref="authority:spine",
        observed_at="2026-09-06T23:00:00+02:00", expires_at="2026-09-07T00:00:00+02:00",
        authority_refs=("github.repository.write",), provider_identity_ref="provider:github-identity",
        owner_approval_ref="owner:approval" if m.owner_approval_required else "",
        current_state_ref="provider:prestate", readback_contract_ref="provider:readback-contract",
        rollback_plan_ref="provider:rollback", idempotency_key="spine-idem-1",
    )


def run_spine(m: MissionIR, *, close: bool = False, include_outcome: bool = False):
    spine = AutonomicMissionSpine()
    request = spine_request(m)
    grant = spine_grant(m)
    readiness = {"github": True}
    base = dict(
        mission=m,
        capability_requirements=(MissionCapabilityRequirement("CAP_A", Maturity.PROVIDER_RUNNING),),
        truth_records=spine_truth(), topology_tasks=(spine_task(m),), routes=spine_route(),
        worker_attestations=(spine_worker(m),), capability_epochs={"CAP_A": spine_epoch()},
        action_bundles=(ActionExecutionBundle(request=request, grant=grant, provider_readiness=readiness),),
        required_actions=(RequiredAction("provider-action", require_behaviour=True),), now=NOW,
        outcome_evidence=None, proof_evidence={}, value_observations=(),
    )
    if not close:
        return spine.run(**base)
    first = spine.run(**base)
    action = first.action_admissions[0]
    effect = effect_for(m)
    attempt = ExecutionAttempt(
        attempt_id="attempt-1", action_admission_digest=action.receipt_digest,
        mission_id=m.mission_id, action_id="provider-action", unit_id="u1",
        effect_class=effect, target_scope=TARGET, idempotency_key="spine-idem-1",
        request_fingerprint="request-v1", pre_state_fingerprint="pre-v1",
        transport_ref="provider:transport", write_ack_ref="provider:ack" if effect is not EffectClass.READ_ONLY else "",
    )
    rb = SemanticReadback(
        readback_id="rb1", attempt_id="attempt-1", provider_ref="provider:readback",
        target_scope=TARGET, observed_state_fingerprint="post-v1", expected_state_fingerprint="post-v1",
        semantic_match=True, fresh=True, provider_native=True, behaviour_ref="provider:behaviour",
    )
    base["action_bundles"] = (ActionExecutionBundle(request=request, grant=grant, attempt=attempt, readback=rb, provider_readiness=readiness),)
    if include_outcome:
        base["outcome_evidence"] = OutcomeEvidence("out1", m.mission_id, m.outcome_contract, "provider:outcome", True, True)
        base["proof_evidence"] = {name: f"proof:{name}" for name in m.proof_requirements}
        base["value_observations"] = tuple(ValueObservation(name, f"metric:{name}", "0", True, True) for name in m.value_metrics)
    return spine.run(**base)


class BubblesAutonomicFederationRuntimeTests(unittest.TestCase):
    def runtime(self, root: str) -> BubblesAutonomicFederationRuntime:
        return BubblesAutonomicFederationRuntime(root, source_frontier=FRONTIER, policy_sha256="policy-afr-v1", environment_sha256="environment-afr-v1", cells=cells(), minimum_owner_value_pairs=2)

    def test_compile_reuses_durable_runtime_and_exposes_spine_truth_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            runtime = self.runtime(root); item = mission()
            status = runtime.compile(item, trace_id="trace-afr-001")
            self.assertEqual({WORK_AUTHORITY, WORK_EXECUTION, WORK_READBACK, WORK_PROOF, WORK_VALUE}, set(status["work_items"]))
            self.assertEqual("VERIFIED", runtime.durable.ledger.verify()["state"])
            self.assertTrue(status["truth_boundary"]["provider_dispatch_requires_autonomic_spine_action_admission"])
            self.assertFalse(status["truth_boundary"]["legacy_spine_bypass_flag_exists"])

    def test_provider_dispatch_without_spine_action_stage_is_fail_closed_and_never_calls_executor(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            runtime = self.runtime(root); item = mission(); runtime.compile(item, trace_id="t")
            authority = AuthorityLeaseDecision(schema="x", mission_id=item.mission_id, capability_id="repo.read", contract_sha256="x", state=AuthorityState.NOT_REQUIRED.value, provider="github", resource_ref=TARGET)
            selection = runtime.select_provider(item, "repo.read", health=(health("github-read", credential=False),))
            bad = AutonomicMissionSpine().run(
                mission=item, capability_requirements=(MissionCapabilityRequirement("CAP_A", Maturity.PROVIDER_RUNNING),),
                truth_records={"CAP_A": CapabilityTruthRecord("CAP_A")}, topology_tasks=(spine_task(item),), routes=spine_route(),
                worker_attestations=(spine_worker(item),), capability_epochs={"CAP_A": spine_epoch()},
                action_bundles=(), required_actions=(), now=NOW,
            )
            calls = []
            receipt = runtime.execute_provider(item, selection, authority=authority, payload={}, execute=lambda *a, **k: calls.append(1) or {}, readback=lambda *a, **k: {}, spine_receipt=bad, action_id="provider-action")
            self.assertEqual("SPINE_GATED", receipt.state); self.assertEqual([], calls)

    def test_read_only_live_route_with_spine_action_stage_executes_and_semantic_readback_survives(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            runtime = self.runtime(root); item = mission(); runtime.compile(item, trace_id="read")
            contract = CapabilityAuthorityContract("repo.read", "github", "github", "read", "A0", "READ_ONLY", resource_ref=TARGET, proof_requirements=("semantic_readback",), rollback_required=True, max_cost_microunits=0)
            authority = runtime.resolve_authority(item, contract, now_epoch=1_788_000_000.0)
            selection = runtime.select_provider(item, "repo.read", health=(health("github-read", credential=False),))
            pre = run_spine(item)
            receipt = runtime.execute_provider(
                item, selection, authority=authority, payload={"query": "main"}, spine_receipt=pre, action_id="provider-action",
                execute=lambda cell, payload, key: {"transport_ok": True, "provider_native": True, "effect_attempted": False, "result_ref": "github:read:result", "result_sha256": "c" * 64, "proof_refs": ("github:transport",), "cost_microunits": 0, "latency_ms": 25},
                readback=lambda cell, execution, key: {"provider_native": True, "semantic_readback_verified": True, "readback_ref": "github:semantic:readback", "proof_refs": ("github:readback",)},
            )
            self.assertEqual("PROVIDER_SEMANTIC_READBACK_VERIFIED", receipt.state)
            gated = runtime.finalize_proof(item, spine_receipt=pre)
            self.assertFalse(gated.get("proof_complete", False))
            closed = run_spine(item, close=True)
            self.assertTrue(runtime.finalize_proof(item, spine_receipt=closed)["proof_complete"])

    def test_bounded_effect_without_exact_bubbles_grant_never_calls_executor_even_with_spine(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            runtime = self.runtime(root); item = mission("BOUNDED_EFFECT"); runtime.compile(item, trace_id="gated")
            contract = CapabilityAuthorityContract("repo.write", "github", "github", "write", "A1", "BOUNDED_EFFECT", credential_reference="secretmanager:github/token:v1", resource_ref=TARGET, proof_requirements=("provider_readback",), rollback_required=True, max_cost_microunits=0)
            authority = runtime.resolve_authority(item, contract, now_epoch=1_788_000_000.0)
            selection = runtime.select_provider(item, "repo.write", health=(health("github-write", credential=True),)); calls = []
            receipt = runtime.execute_provider(item, selection, authority=authority, payload={}, execute=lambda *a, **k: calls.append(1) or {}, readback=lambda *a, **k: {}, spine_receipt=run_spine(item), action_id="provider-action")
            self.assertEqual("AUTHORITY_GATED", receipt.state); self.assertEqual([], calls)

    def test_consequential_effect_remains_approval_gated_after_spine_binding(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            runtime = self.runtime(root); item = mission("CONSEQUENTIAL_EFFECT", approval=True); runtime.compile(item, trace_id="cons")
            selection = runtime.select_provider(item, "repo.write", health=(health("github-write", credential=True),))
            fabricated = AuthorityLeaseDecision(schema="x", mission_id=item.mission_id, capability_id="repo.write", contract_sha256="e" * 64, state=AuthorityState.RESOLVED.value, grant_id="FAB", provider="github", connector="github", action="write", credential_reference="secret", semantic_readback_route="github:readback", proof_refs=("test",), expires_at_epoch=1_788_100_000.0, provider_effect_authorized=True, resource_ref=TARGET)
            calls = []
            receipt = runtime.execute_provider(item, selection, authority=fabricated, payload={}, execute=lambda *a, **k: calls.append(1) or {}, readback=lambda *a, **k: {}, spine_receipt=run_spine(item), action_id="provider-action")
            self.assertEqual("APPROVAL_REQUIRED", receipt.state); self.assertEqual([], calls)

    def test_owner_value_evaluation_requires_outcome_spine_and_finalization_requires_value_observed(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            runtime = self.runtime(root); item = mission(); runtime.compile(item, trace_id="value")
            pre = run_spine(item, close=True, include_outcome=False)
            self.assertEqual("SPINE_GATED", runtime.evaluate_owner_value(item, (), spine_receipt=pre)["state"])
            final_run = run_spine(item, close=True, include_outcome=True)
            measured = runtime.evaluate_owner_value(item, (), spine_receipt=final_run)
            self.assertFalse(measured["mission_value_finalized"])
            self.assertTrue(runtime.finalize_owner_value(item, spine_receipt=final_run)["mission_value_finalized"])


if __name__ == "__main__":
    unittest.main()
