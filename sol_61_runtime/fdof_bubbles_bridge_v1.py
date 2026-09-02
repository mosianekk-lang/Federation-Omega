from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

try:
    from .fdof_v1 import ExecutorSpec, FederationDistributedOperatingFabric, HealthObservation
    from .sol_62_frontier_primitives import ConstraintError, digest
except ImportError:
    from fdof_v1 import ExecutorSpec, FederationDistributedOperatingFabric, HealthObservation
    from sol_62_frontier_primitives import ConstraintError, digest

from bubbles.command_bus import build_receipt
from bubbles.control_plane import ActionRequest, BubblesControlPlane, EffectClass


BRIDGE_VERSION = "1.0.0"
HOST_EXECUTOR_ID = "EXEC-GITHUB-BUBBLES-READ-001"
HOST_TARGET = "github-actions:bubbles-command-bus"
HOST_TARGET_ALIAS = "GITHUB_ACTIONS_A0_A1"
HOST_CAPABILITY = "HOSTED_READ_ONLY_COMMAND_INGRESS"
QUALIFICATION_MESSAGE = "FDOF_GITHUB_HOST_QUALIFICATION"


@dataclass(frozen=True)
class HostedQualification:
    executor_id: str
    command: Mapping[str, Any]
    command_sha256: str
    proof_scope: str


class FDOFBubblesBridge:
    """Bind FDOF to the existing Bubbles control/command plane without duplicating it.

    V1 qualifies only the existing no-effect hosted command-ingress capability.
    It does not infer repository write authority, cloud authority, Apps Script
    authority, provider effects, or unattended Federation autonomy.
    """

    def __init__(
        self,
        fdof: FederationDistributedOperatingFabric,
        bubbles: BubblesControlPlane | None = None,
    ) -> None:
        self.fdof = fdof
        self.bubbles = bubbles or BubblesControlPlane()

    @staticmethod
    def hosted_executor_spec(executor_id: str = HOST_EXECUTOR_ID) -> ExecutorSpec:
        return ExecutorSpec(
            executor_id=executor_id,
            provider="GitHub Actions / Bubbles Command Bus",
            capabilities=(HOST_CAPABILITY, "IMMUTABLE_RECEIPT_READBACK"),
            target_prefixes=(HOST_TARGET,),
            authority_ceiling="A1_INTERNAL",
            cost_class="C0_INCLUDED_FREE",
            readback_modes=("IMMUTABLE_GITHUB_ACTIONS_ARTIFACT",),
            rollback_modes=(),
            max_parallel=1,
            version=1,
            metadata={
                "host_workflow": ".github/workflows/bubbles-command-bus.yml",
                "adapter_id": "bubbles_command_bus",
                "effect_scope": "READ_ONLY_NO_PROVIDER_EFFECT",
                "authority_inheritance": False,
            },
        )

    def register_hosted_executor(self, executor_id: str = HOST_EXECUTOR_ID) -> dict[str, Any]:
        return self.fdof.register_executor(self.hosted_executor_spec(executor_id))

    def qualification_command(self, executor_id: str = HOST_EXECUTOR_ID) -> HostedQualification:
        state = self.fdof.control.get_state("fdof.executor", executor_id)
        if state is None:
            raise ConstraintError("FDOF_HOST_EXECUTOR_NOT_REGISTERED")
        spec = state["value"]
        if HOST_CAPABILITY not in set(spec.get("capabilities", ())):
            raise ConstraintError("FDOF_HOST_CAPABILITY_NOT_REGISTERED")
        if HOST_TARGET not in set(spec.get("target_prefixes", ())):
            raise ConstraintError("FDOF_HOST_TARGET_NOT_REGISTERED")

        request = ActionRequest(
            adapter_id="bubbles_command_bus",
            action="canary",
            effect=EffectClass.READ,
            target_alias=HOST_TARGET_ALIAS,
            payload={
                "message": QUALIFICATION_MESSAGE,
                "executor_id": executor_id,
                "proof_scope": HOST_CAPABILITY,
                "external_effect": False,
            },
        )
        decision = self.bubbles.decide(request)
        if decision.state != "READY":
            raise ConstraintError(f"BUBBLES_HOST_QUALIFICATION_NOT_READY:{decision.reason}")
        envelope = self.bubbles.command_envelope(request)
        return HostedQualification(
            executor_id=executor_id,
            command=envelope,
            command_sha256=str(envelope["command_sha256"]),
            proof_scope=HOST_CAPABILITY,
        )

    @staticmethod
    def health_from_receipt(
        receipt: Mapping[str, Any],
        *,
        executor_id: str = HOST_EXECUTOR_ID,
        observed_at_epoch: int,
        ttl_seconds: int = 900,
    ) -> HealthObservation:
        request = receipt.get("request")
        execution = receipt.get("execution")
        if not isinstance(request, Mapping) or not isinstance(execution, Mapping):
            raise ConstraintError("BUBBLES_RECEIPT_STRUCTURE_INVALID")

        expected = {
            "receipt_state": receipt.get("state") == "SUCCESS",
            "adapter": request.get("adapter_id") == "bubbles_command_bus",
            "action": request.get("action") == "canary",
            "effect": request.get("effect") == "READ",
            "target": request.get("target_alias") == HOST_TARGET_ALIAS,
            "message": execution.get("echo") == QUALIFICATION_MESSAGE,
            "kind": execution.get("kind") == "LOCAL_COMMAND_BUS_CANARY",
        }
        failed = tuple(name for name, passed in expected.items() if not passed)
        if failed:
            raise ConstraintError("BUBBLES_HOST_RECEIPT_SEMANTIC_MISMATCH:" + ",".join(failed))

        proof_id = str(receipt.get("receipt_sha256") or "")
        if not proof_id:
            proof_id = "sha256:" + digest(receipt)
        elif not proof_id.startswith("sha256:"):
            proof_id = "sha256:" + proof_id

        return HealthObservation(
            observation_id=f"health:{executor_id}:{observed_at_epoch}",
            executor_id=executor_id,
            observed_at_epoch=int(observed_at_epoch),
            ttl_seconds=int(ttl_seconds),
            process="HEALTHY",
            authentication="HEALTHY",
            target_access="HEALTHY",
            semantic_capability="HEALTHY",
            readback="HEALTHY",
            capacity_available=1,
            provider_state="AVAILABLE",
            proof_id=proof_id,
            evidence_class="HOSTED_RUNTIME_IMMUTABLE_READBACK",
            metadata={
                "bridge_version": BRIDGE_VERSION,
                "qualified_capability": HOST_CAPABILITY,
                "qualified_target": HOST_TARGET,
                "provider_effect_proven": False,
                "repository_write_authority_proven": False,
                "cloud_authority_proven": False,
                "apps_script_authority_proven": False,
            },
        )

    def admit_hosted_receipt(
        self,
        receipt: Mapping[str, Any],
        *,
        executor_id: str = HOST_EXECUTOR_ID,
        observed_at_epoch: int,
        ttl_seconds: int = 900,
    ) -> dict[str, Any]:
        observation = self.health_from_receipt(
            receipt,
            executor_id=executor_id,
            observed_at_epoch=observed_at_epoch,
            ttl_seconds=ttl_seconds,
        )
        return self.fdof.record_health(observation)


def deterministic_local_qualification_receipt(command: Mapping[str, Any]) -> dict[str, Any]:
    """Test helper only: deterministic local semantics, never hosted-runtime proof."""
    return build_receipt(
        json.dumps(dict(command), sort_keys=True),
        actor="mosianekk-lang",
        event_name="pull_request",
        source_ref="FDOF-LOCAL-QUALIFICATION-TEST",
    )
