from __future__ import annotations

import tempfile
import unittest

from bubbles.autonomic_federation_runtime import (
    BubblesAutonomicFederationRuntime,
    WORK_AUTHORITY,
    WORK_EXECUTION,
    WORK_PROOF,
    WORK_READBACK,
    WORK_VALUE,
)
from bubbles.provider_authority_fabric import (
    AuthorityGrant,
    AuthorityLeaseDecision,
    AuthorityState,
    CapabilityAuthorityContract,
)
from bubbles.provider_cell_mesh import ProviderCellHealth, ProviderCellSpec
from federation.mission_ir import MissionIR


SOURCE = "b" * 40
FRONTIER = f"main@{SOURCE}"


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
        ProviderCellSpec(
            cell_id="github-read",
            provider="github",
            connector="github",
            capabilities=("repo.read",),
            supports_effect_classes=("READ_ONLY",),
            priority=80,
        ),
        ProviderCellSpec(
            cell_id="github-write",
            provider="github",
            connector="github",
            capabilities=("repo.write",),
            supports_effect_classes=("BOUNDED_EFFECT", "CONSEQUENTIAL_EFFECT"),
            priority=80,
        ),
    )


def health(cell_id: str, *, credential: bool) -> ProviderCellHealth:
    return ProviderCellHealth(
        cell_id=cell_id,
        provider_native=True,
        provider_live=True,
        semantic_readback_ready=True,
        credential_bound=credential,
        latency_ms=25,
        estimated_cost_microunits=0,
        proof_refs=(f"provider:{cell_id}:fresh",),
        observed_at="2026-09-03T03:00:00+02:00",
    )


class BubblesAutonomicFederationRuntimeTests(unittest.TestCase):
    def runtime(self, root: str) -> BubblesAutonomicFederationRuntime:
        return BubblesAutonomicFederationRuntime(
            root,
            source_frontier=FRONTIER,
            policy_sha256="policy-afr-v1",
            environment_sha256="environment-afr-v1",
            cells=cells(),
            minimum_owner_value_pairs=2,
        )

    def test_compile_reuses_durable_runtime_and_creates_five_lane_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            runtime = self.runtime(root)
            item = mission()
            status = runtime.compile(item, trace_id="trace-afr-001")
            self.assertEqual(
                {WORK_AUTHORITY, WORK_EXECUTION, WORK_READBACK, WORK_PROOF, WORK_VALUE},
                set(status["work_items"]),
            )
            self.assertEqual("VERIFIED", runtime.durable.ledger.verify()["state"])
            self.assertFalse(status["truth_boundary"]["durable_runtime_is_hidden_background_chatgpt"])
            self.assertFalse(status["truth_boundary"]["second_scheduler_created"])

    def test_read_only_live_route_semantic_readback_can_finalize_proof(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            runtime = self.runtime(root)
            item = mission()
            runtime.compile(item, trace_id="trace-afr-read")
            contract = CapabilityAuthorityContract(
                capability_id="repo.read",
                provider="github",
                connector="github",
                action="read",
                minimum_authority="A0",
                effect_class="READ_ONLY",
                resource_ref="github:repo:readback",
                proof_requirements=("semantic_readback",),
                rollback_required=True,
                max_cost_microunits=0,
            )
            authority = runtime.resolve_authority(item, contract, now_epoch=1_788_000_000.0)
            self.assertEqual(AuthorityState.NOT_REQUIRED.value, authority.state)
            selection = runtime.select_provider(item, "repo.read", health=(health("github-read", credential=False),))
            self.assertEqual("SELECTED", selection.state)

            def execute(cell, payload, idempotency_key):
                return {
                    "transport_ok": True,
                    "provider_native": True,
                    "effect_attempted": False,
                    "result_ref": "github:read:result",
                    "result_sha256": "c" * 64,
                    "proof_refs": ("github:transport",),
                    "cost_microunits": 0,
                    "latency_ms": 25,
                }

            def readback(cell, execution, idempotency_key):
                return {
                    "provider_native": True,
                    "semantic_readback_verified": True,
                    "readback_ref": "github:semantic:readback",
                    "proof_refs": ("github:readback",),
                }

            receipt = runtime.execute_provider(
                item,
                selection,
                authority=authority,
                payload={"query": "main"},
                execute=execute,
                readback=readback,
            )
            self.assertEqual("PROVIDER_SEMANTIC_READBACK_VERIFIED", receipt.state)
            final = runtime.finalize_proof(item.mission_id)
            self.assertTrue(final["proof_complete"])
            self.assertFalse(final["owner_value_proven"])

    def test_bounded_effect_without_exact_grant_never_calls_executor(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            runtime = self.runtime(root)
            item = mission("BOUNDED_EFFECT")
            runtime.compile(item, trace_id="trace-afr-gated")
            contract = CapabilityAuthorityContract(
                capability_id="repo.write",
                provider="github",
                connector="github",
                action="write",
                minimum_authority="A1",
                effect_class="BOUNDED_EFFECT",
                credential_reference="secretmanager:github/token:v1",
                resource_ref="github:repo:target",
                proof_requirements=("provider_readback",),
                rollback_required=True,
                max_cost_microunits=0,
            )
            authority = runtime.resolve_authority(item, contract, now_epoch=1_788_000_000.0)
            self.assertEqual(AuthorityState.PROVIDER_GATED.value, authority.state)
            selection = runtime.select_provider(item, "repo.write", health=(health("github-write", credential=True),))
            calls = []

            def execute(*args, **kwargs):
                calls.append("execute")
                return {}

            receipt = runtime.execute_provider(
                item,
                selection,
                authority=authority,
                payload={"operation": "bounded-write"},
                execute=execute,
                readback=lambda *args, **kwargs: {},
            )
            self.assertEqual("AUTHORITY_GATED", receipt.state)
            self.assertEqual([], calls)

    def test_exact_grant_dispatch_without_semantic_readback_holds_effect(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            runtime = self.runtime(root)
            item = mission("BOUNDED_EFFECT")
            runtime.compile(item, trace_id="trace-afr-hold")
            contract = CapabilityAuthorityContract(
                capability_id="repo.write",
                provider="github",
                connector="github",
                action="write",
                minimum_authority="A1",
                effect_class="BOUNDED_EFFECT",
                credential_reference="secretmanager:github/token:v1",
                resource_ref="github:repo:target",
                proof_requirements=("provider_readback",),
                rollback_required=True,
                max_cost_microunits=0,
            )
            grant = AuthorityGrant(
                grant_id="GRANT-GITHUB-WRITE-001",
                capability_id="repo.write",
                provider="github",
                connector="github",
                action="write",
                authority_class="A1",
                credential_reference="secretmanager:github/token:v1",
                mission_id=item.mission_id,
                expires_at_epoch=1_788_100_000.0,
                provider_native=True,
                semantic_readback_route="github:repo:readback",
                proof_refs=("provider:grant:001",),
                cost_ceiling_microunits=0,
            )
            authority = runtime.resolve_authority(item, contract, now_epoch=1_788_000_000.0, grants=(grant,))
            self.assertEqual(AuthorityState.RESOLVED.value, authority.state)
            selection = runtime.select_provider(item, "repo.write", health=(health("github-write", credential=True),))

            receipt = runtime.execute_provider(
                item,
                selection,
                authority=authority,
                payload={"operation": "bounded-write"},
                execute=lambda cell, payload, key: {
                    "transport_ok": True,
                    "provider_native": True,
                    "effect_attempted": True,
                    "result_ref": "github:write:receipt",
                    "result_sha256": "d" * 64,
                    "proof_refs": ("github:write:transport",),
                    "cost_microunits": 0,
                    "latency_ms": 30,
                },
                readback=lambda cell, execution, key: {
                    "provider_native": True,
                    "semantic_readback_verified": False,
                    "readback_ref": "",
                    "proof_refs": (),
                },
            )
            self.assertEqual("HOLD_READBACK", receipt.state)
            snapshot = runtime.passport.snapshot(item.mission_id)
            self.assertTrue(snapshot.hold_readback)
            self.assertFalse(snapshot.proof_complete)

    def test_consequential_effect_is_never_automatically_dispatched(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            runtime = self.runtime(root)
            item = mission("CONSEQUENTIAL_EFFECT", approval=True)
            runtime.compile(item, trace_id="trace-afr-consequential")
            selection = runtime.select_provider(item, "repo.write", health=(health("github-write", credential=True),))
            fabricated_authority = AuthorityLeaseDecision(
                schema="BUBBLES-OMEGA-PROVIDER-AUTHORITY-FABRIC-V1",
                mission_id=item.mission_id,
                capability_id="repo.write",
                contract_sha256="e" * 64,
                state=AuthorityState.RESOLVED.value,
                grant_id="FABRICATED-TEST-GRANT",
                provider="github",
                connector="github",
                action="write",
                credential_reference="secretmanager:github/token:v1",
                semantic_readback_route="github:repo:readback",
                proof_refs=("test:grant",),
                expires_at_epoch=1_788_100_000.0,
                provider_effect_authorized=True,
            )
            calls = []
            receipt = runtime.execute_provider(
                item,
                selection,
                authority=fabricated_authority,
                payload={"operation": "consequential"},
                execute=lambda *args, **kwargs: calls.append("execute") or {},
                readback=lambda *args, **kwargs: {},
            )
            self.assertEqual("APPROVAL_REQUIRED", receipt.state)
            self.assertEqual([], calls)


if __name__ == "__main__":
    unittest.main()
