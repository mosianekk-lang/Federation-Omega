from __future__ import annotations

import unittest

from bubbles.provider_authority_fabric import (
    AuthorityGrant,
    AuthorityState,
    CapabilityAuthorityContract,
    ProviderAuthorityFabric,
)
from federation.action_admission_gate_v1 import ActionRequest, AuthorityGrant as SpineGrant
from federation.autonomic_mission_spine_v1 import ActionExecutionBundle, AutonomicMissionSpine
from federation.capability_truth_v1 import CapabilityTruthRecord, ClaimKind, EvidenceRef, Maturity
from federation.cfbe_chat_hyperperformance_v1 import EffectClass, RouteProfile, WorkUnit
from federation.execution_topology_compiler_v1 import TopologyTask
from federation.live_worker_attestation_v1 import CapabilityEpoch, WorkerAttestation, WorkerState
from federation.mission_capability_admission_v1 import MissionCapabilityRequirement
from federation.mission_ir import MissionIR
from federation.mission_outcome_value_court_v1 import RequiredAction
from federation.spine_host_binding_v1 import SpineHostBindingCourt

NOW = "2026-09-06T23:12:00+02:00"
TARGET = "github:repo:target"


def mission() -> MissionIR:
    return MissionIR(
        mission_id="exact-target-m1",
        objective="prove exact provider target binding",
        domain="FEDERATION",
        outcome_contract="exact provider target admitted before dispatch",
        source_frontier="signed-main",
        privacy_class="P1_INTERNAL",
        rights_state="OWNER_AUTHORIZED",
        effect_class="BOUNDED_EFFECT",
        authority_requirements=("github.repository.write",),
        proof_requirements=("target_binding",),
        provider_allowlist=("github",),
    )


def spine_run(m: MissionIR):
    truth = CapabilityTruthRecord("CAP_A").add(
        EvidenceRef(
            "cap-e1", "CAP_A", ClaimKind.RUNTIME_RECEIPT,
            "provider:capability", Maturity.PROVIDER_RUNNING,
            fresh=True, independently_verified=True,
        )
    )
    epoch = CapabilityEpoch(
        "epoch-CAP_A", "CAP_A", "2026-09-06T22:30:00+02:00",
        "2026-09-07T00:30:00+02:00", "provider:epoch",
    )
    worker = WorkerAttestation(
        attestation_id="att-1", worker_id="w1", capability_id="CAP_A",
        epoch_id="epoch-CAP_A", state=WorkerState.HEARTBEAT_VERIFIED,
        observed_at="2026-09-06T23:00:00+02:00", expires_at="2026-09-07T00:00:00+02:00",
        source_ref="provider:worker", runtime_id="runtime-1", mission_id=m.mission_id,
        tool_refs=("tool:github",), heartbeat_ref="provider:heartbeat", independently_verified=True,
    )
    task = TopologyTask(
        WorkUnit(
            unit_id="u1", surface="github", operation="provider-dispatch",
            input_fingerprint="payload-v1", effect_class=EffectClass.INTERNAL_WRITE,
        ),
        capability_id="CAP_A", mutation_domain="github:target",
    )
    request = ActionRequest(
        action_id="provider-action", unit_id="u1", effect_class=EffectClass.INTERNAL_WRITE,
        target_scope=TARGET, mutation_domain="github:target", provider="github",
    )
    grant = SpineGrant(
        grant_id="sg1", mission_id=m.mission_id, action_id="provider-action",
        effect_class=EffectClass.INTERNAL_WRITE, target_scope=TARGET,
        source_ref="authority:spine", observed_at="2026-09-06T23:00:00+02:00",
        expires_at="2026-09-07T00:00:00+02:00",
        authority_refs=("github.repository.write",),
        current_state_ref="provider:pre", readback_contract_ref="provider:rb",
        rollback_plan_ref="provider:rollback", idempotency_key="idem-1",
    )
    return AutonomicMissionSpine().run(
        mission=m,
        capability_requirements=(MissionCapabilityRequirement("CAP_A", Maturity.PROVIDER_RUNNING),),
        truth_records={"CAP_A": truth},
        topology_tasks=(task,),
        routes=(RouteProfile(
            route_id="github-direct", surface="github", available=True,
            fresh=True, direct=True, proof_refs=("provider:route",),
        ),),
        worker_attestations=(worker,),
        capability_epochs={"CAP_A": epoch},
        action_bundles=(ActionExecutionBundle(
            request=request, grant=grant, provider_readiness={"github": True},
        ),),
        required_actions=(RequiredAction("provider-action"),),
        now=NOW,
    )


class ExactTargetProvenanceTests(unittest.TestCase):
    def test_authority_decision_preserves_contract_resource_ref(self) -> None:
        m = mission()
        contract = CapabilityAuthorityContract(
            capability_id="repo.write", provider="github", connector="github",
            action="write", minimum_authority="A1", effect_class="BOUNDED_EFFECT",
            credential_reference="secretmanager:github/token:v1", resource_ref=TARGET,
            proof_requirements=("provider_readback",), rollback_required=True,
            max_cost_microunits=0,
        )
        grant = AuthorityGrant(
            grant_id="g1", capability_id="repo.write", provider="github", connector="github",
            action="write", authority_class="A1",
            credential_reference="secretmanager:github/token:v1", mission_id=m.mission_id,
            expires_at_epoch=1_788_100_000.0, provider_native=True,
            semantic_readback_route="github:repo:readback",
            proof_refs=("provider:grant",), cost_ceiling_microunits=0,
        )
        decision = ProviderAuthorityFabric().resolve(
            m, contract, now_epoch=1_788_000_000.0, grants=(grant,)
        )
        self.assertEqual(AuthorityState.RESOLVED.value, decision.state)
        self.assertEqual(TARGET, decision.resource_ref)

    def test_host_binding_accepts_exact_provider_and_target(self) -> None:
        m = mission(); run = spine_run(m)
        result = SpineHostBindingCourt().admit_action(
            m, run, action_id="provider-action",
            expected_effect_class=EffectClass.INTERNAL_WRITE,
            expected_target_scope=TARGET, expected_provider="github",
        )
        self.assertTrue(result.admitted)

    def test_host_binding_rejects_target_mismatch(self) -> None:
        m = mission(); run = spine_run(m)
        result = SpineHostBindingCourt().admit_action(
            m, run, action_id="provider-action",
            expected_effect_class=EffectClass.INTERNAL_WRITE,
            expected_target_scope="github:repo:other", expected_provider="github",
        )
        self.assertFalse(result.admitted)
        self.assertIn("SPINE_ACTION_TARGET_MISMATCH", result.reasons)

    def test_host_binding_rejects_provider_mismatch(self) -> None:
        m = mission(); run = spine_run(m)
        result = SpineHostBindingCourt().admit_action(
            m, run, action_id="provider-action",
            expected_effect_class=EffectClass.INTERNAL_WRITE,
            expected_target_scope=TARGET, expected_provider="other-provider",
        )
        self.assertFalse(result.admitted)
        self.assertIn("SPINE_ACTION_PROVIDER_MISMATCH", result.reasons)


if __name__ == "__main__":
    unittest.main()
