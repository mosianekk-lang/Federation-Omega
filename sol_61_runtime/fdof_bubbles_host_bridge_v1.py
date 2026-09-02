from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping

from bubbles.command_bus import RECEIPT_SCHEMA, execute_command

try:
    from .fdof_hosted_state_v1 import export_capsule, read_capsule, restore_capsule, write_capsule
    from .fdof_provider_bridge_v1 import (
        DispatchReceipt,
        FederationProviderBridge,
        ProviderAdapter,
        ProviderExecutionRequest,
        ReadbackReceipt,
    )
    from .fdof_v1 import (
        ExecutorSpec,
        FederationDistributedOperatingFabric,
        HealthObservation,
        RouteRequest,
    )
    from .sol_62_frontier_primitives import ConstraintError, digest
    from .sol_62_runtime import Sol62Runtime
except ImportError:
    from fdof_hosted_state_v1 import export_capsule, read_capsule, restore_capsule, write_capsule
    from fdof_provider_bridge_v1 import (
        DispatchReceipt,
        FederationProviderBridge,
        ProviderAdapter,
        ProviderExecutionRequest,
        ReadbackReceipt,
    )
    from fdof_v1 import ExecutorSpec, FederationDistributedOperatingFabric, HealthObservation, RouteRequest
    from sol_62_frontier_primitives import ConstraintError, digest
    from sol_62_runtime import Sol62Runtime


BRIDGE_VERSION = "1.0.0"
PROVIDER = "BUBBLES_GITHUB_HOST"
EXECUTOR_ID = "EXEC-FDOF-BUBBLES-HOST-V1"
TARGET = "bubbles://command-bus/canary"
MISSION_ID = "MISSION-FDOF-BUBBLES-HOST-BRIDGE-V1"
TRANSITION_ID = "TRANS-FDOF-BUBBLES-HOST-BRIDGE-V1"
ROUTE_ID = "ROUTE-FDOF-BUBBLES-HOST-BRIDGE-V1"
EXECUTION_ID = "EXECUTION-FDOF-BUBBLES-HOST-BRIDGE-V1"
IDEMPOTENCY_KEY = "FDOF:BUBBLES:HOSTED_CANARY:V1"
ECHO = "FDOF_BUBBLES_HOST_BRIDGE_V1"


def _command(message: str) -> dict[str, Any]:
    return {
        "schema": "BUBBLES-CONTROL-COMMAND-V1",
        "adapter_id": "bubbles_command_bus",
        "action": "canary",
        "effect": "READ",
        "target_alias": "GITHUB_ACTIONS_A0_A1",
        "payload": {"message": message},
    }


def _semantic_readback(receipt: Mapping[str, Any], *, expected_echo: str) -> dict[str, Any]:
    request = receipt.get("request") if isinstance(receipt.get("request"), Mapping) else {}
    execution = receipt.get("execution") if isinstance(receipt.get("execution"), Mapping) else {}
    route = receipt.get("route_decision") if isinstance(receipt.get("route_decision"), Mapping) else {}
    checks = {
        "schema": receipt.get("schema") == RECEIPT_SCHEMA,
        "state": receipt.get("state") == "SUCCESS",
        "request_action": request.get("action") == "canary",
        "request_effect": request.get("effect") == "READ",
        "execution_kind": execution.get("kind") == "LOCAL_COMMAND_BUS_CANARY",
        "execution_echo": execution.get("echo") == expected_echo,
        "route_kind": route.get("route_kind") == "GITHUB_COMMAND_BUS",
    }
    return {
        "verified": all(checks.values()),
        "checks": checks,
        "semantic_state": "BUBBLES_LOCAL_COMMAND_BUS_CANARY_VERIFIED" if all(checks.values()) else "BUBBLES_RECEIPT_MISMATCH",
        "receipt_sha256": digest(receipt),
    }


def run_hosted_bridge(
    *,
    capsule_path: str | Path,
    restore_receipt_path: str | Path,
    runtime_root: str | Path,
    output_dir: str | Path,
    source_sha: str,
    actor: str = "mosianekk-lang",
    now_epoch: int | None = None,
) -> dict[str, Any]:
    now_epoch = int(time.time()) if now_epoch is None else int(now_epoch)
    source_sha = str(source_sha).strip().lower()
    if not source_sha:
        raise ConstraintError("HOST_BRIDGE_SOURCE_SHA_REQUIRED")

    capsule = read_capsule(str(capsule_path))
    restore_receipt = json.loads(Path(restore_receipt_path).read_text(encoding="utf-8"))
    if restore_receipt.get("state") != "HOSTED_SEPARATE_RUN_STATE_CONTINUITY_VERIFIED":
        raise ConstraintError("HOST_BRIDGE_RESTORE_RECEIPT_NOT_VERIFIED")
    if restore_receipt.get("trigger_head_sha") != source_sha:
        raise ConstraintError("HOST_BRIDGE_RESTORE_SOURCE_MISMATCH")
    if restore_receipt.get("capsule_sha256") != capsule.get("capsule_sha256"):
        raise ConstraintError("HOST_BRIDGE_CAPSULE_BINDING_MISMATCH")
    if capsule.get("source_version") != source_sha:
        raise ConstraintError("HOST_BRIDGE_CAPSULE_SOURCE_MISMATCH")

    runtime = Sol62Runtime(Path(runtime_root))
    try:
        restore_capsule(runtime, capsule)
        authority_count = int(
            runtime.control.db.execute("SELECT COUNT(*) AS n FROM authority_leases").fetchone()["n"]
        )
        if authority_count:
            raise ConstraintError("HOST_BRIDGE_AUTHORITY_TRANSFER_FORBIDDEN")

        fdof = FederationDistributedOperatingFabric(runtime)
        fdof.register_executor(
            ExecutorSpec(
                executor_id=EXECUTOR_ID,
                provider=PROVIDER,
                capabilities=("LOCAL_COMMAND_BUS_CANARY",),
                target_prefixes=("bubbles://command-bus/",),
                authority_ceiling="A0_READ_ONLY",
                cost_class="C0_INCLUDED_FREE",
                readback_modes=("BUBBLES_RECEIPT_SEMANTIC",),
                max_parallel=1,
                metadata={
                    "host": "github-actions",
                    "bridge_version": BRIDGE_VERSION,
                    "provider_effect": False,
                    "authority_inherited": False,
                },
            )
        )
        fdof.record_health(
            HealthObservation(
                observation_id=f"HEALTH-FDOF-BUBBLES-{now_epoch}",
                executor_id=EXECUTOR_ID,
                observed_at_epoch=now_epoch,
                ttl_seconds=600,
                process="HEALTHY",
                authentication="HEALTHY",
                target_access="HEALTHY",
                semantic_capability="HEALTHY",
                readback="HEALTHY",
                capacity_available=1,
                provider_state="AVAILABLE",
                proof_id=f"HOSTED-RUNTIME:{source_sha}",
                evidence_class="HOSTED_RUNTIME_PRECHECK",
                metadata={
                    "authentication_basis": "local read-only command bus requires no provider credential",
                    "semantic_check_occurs_after_fenced_dispatch": True,
                },
            )
        )
        route = fdof.route(
            RouteRequest(
                route_id=ROUTE_ID,
                mission_id=MISSION_ID,
                transition_id=TRANSITION_ID,
                operation="CANARY_READ",
                target=TARGET,
                required_capabilities=("LOCAL_COMMAND_BUS_CANARY",),
                authority_ceiling="A0_READ_ONLY",
                allowed_cost_classes=("C0_INCLUDED_FREE",),
                require_readback=True,
                require_rollback=False,
                consequential=False,
                metadata={"no_external_effect": True, "source_sha": source_sha},
            ),
            now_epoch=now_epoch,
        )
        lease = fdof.acquire_transition_lease(
            TRANSITION_ID,
            EXECUTOR_ID,
            ttl_seconds=300,
            now_epoch=now_epoch,
        )

        request = ProviderExecutionRequest(
            execution_id=EXECUTION_ID,
            mission_id=MISSION_ID,
            transition_id=TRANSITION_ID,
            route_id=ROUTE_ID,
            executor_id=EXECUTOR_ID,
            provider=PROVIDER,
            operation="CANARY_READ",
            target=TARGET,
            payload={"message": ECHO},
            idempotency_key=IDEMPOTENCY_KEY,
            semantics="AT_MOST_ONCE",
            consequential=False,
            expected_readback={
                "state": "SUCCESS",
                "execution_kind": "LOCAL_COMMAND_BUS_CANARY",
                "echo": ECHO,
            },
            metadata={"source_sha": source_sha, "no_external_effect": True},
        )
        idem = runtime.control.reserve_idempotency(
            IDEMPOTENCY_KEY,
            {
                "execution_id": EXECUTION_ID,
                "operation": request.operation,
                "target": request.target,
                "payload": dict(request.payload),
                "source_sha": source_sha,
            },
            "AT_MOST_ONCE",
        )

        holder: dict[str, Any] = {}

        def dispatch(req: ProviderExecutionRequest) -> DispatchReceipt:
            bubbles_receipt = execute_command(
                _command(str(req.payload["message"])),
                actor=actor,
                event_name="fdof_hosted_bridge",
                source_ref=f"FDOF-HOST-BRIDGE:{source_sha}",
            )
            receipt = DispatchReceipt(
                execution_id=req.execution_id,
                provider=req.provider,
                provider_request_id=f"bubbles:{digest(bubbles_receipt)[:24]}",
                accepted=bubbles_receipt.get("state") == "SUCCESS",
                effect_uncertain=False,
                summary={"bubbles_receipt": bubbles_receipt},
            )
            holder["dispatch"] = receipt
            return receipt

        def readback(req: ProviderExecutionRequest, dispatch_receipt: DispatchReceipt) -> ReadbackReceipt:
            raw = dispatch_receipt.summary.get("bubbles_receipt")
            if not isinstance(raw, Mapping):
                semantic = {"verified": False, "semantic_state": "BUBBLES_RECEIPT_MISSING", "checks": {}}
            else:
                semantic = _semantic_readback(raw, expected_echo=str(req.payload["message"]))
            return ReadbackReceipt(
                execution_id=req.execution_id,
                provider=req.provider,
                semantic_state=str(semantic["semantic_state"]),
                verified=bool(semantic["verified"]),
                provider_correlation_id=dispatch_receipt.provider_request_id,
                evidence=semantic,
            )

        bridge = FederationProviderBridge(fdof)
        bridge.register_adapter(
            ProviderAdapter(
                adapter_id="FDOF-BUBBLES-HOST-ADAPTER-V1",
                provider=PROVIDER,
                dispatch=dispatch,
                readback=readback,
                rollback=None,
            )
        )
        dispatched = bridge.execute(
            request,
            lease_epoch=int(lease["epoch"]),
            fencing_token=int(lease["fencing_token"]),
            now_epoch=now_epoch,
        )
        dispatch_receipt = holder.get("dispatch")
        if not isinstance(dispatch_receipt, DispatchReceipt):
            raise ConstraintError("HOST_BRIDGE_DISPATCH_RECEIPT_MISSING")
        verified = bridge.verify(
            request,
            dispatch_receipt=dispatch_receipt,
            now_epoch=now_epoch,
        )
        if verified.get("state") != "VERIFIED":
            raise ConstraintError("HOST_BRIDGE_SEMANTIC_READBACK_NOT_VERIFIED")

        bubbles_receipt = dispatch_receipt.summary["bubbles_receipt"]
        semantic = _semantic_readback(bubbles_receipt, expected_echo=ECHO)
        if not semantic["verified"]:
            raise ConstraintError("HOST_BRIDGE_BUBBLES_RECEIPT_MISMATCH")
        if not runtime.control.verify_event_chain():
            raise ConstraintError("HOST_BRIDGE_EVENT_CHAIN_INVALID")

        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        next_capsule = export_capsule(
            runtime,
            source_version=source_sha,
            parent_artifact_ref=f"capsule:{capsule['capsule_sha256']}",
        )
        write_capsule(str(output / "next-capsule.json"), next_capsule)
        result = {
            "schema": "FDOF-BUBBLES-HOST-BRIDGE-RECEIPT-V1",
            "version": BRIDGE_VERSION,
            "state": "HOSTED_FDOF_BUBBLES_BRIDGE_VERIFIED",
            "source_sha": source_sha,
            "generation_anchor": next_capsule["generation_anchor"],
            "inbound_capsule_sha256": capsule["capsule_sha256"],
            "outbound_capsule_sha256": next_capsule["capsule_sha256"],
            "restore_receipt_state": restore_receipt["state"],
            "route_id": route["route_id"],
            "executor_id": route["executor_id"],
            "health_state": route["health_state"],
            "lease_epoch": int(lease["epoch"]),
            "fencing_token": int(lease["fencing_token"]),
            "idempotency_key": IDEMPOTENCY_KEY,
            "idempotency_request_sha256": idem["request_sha256"],
            "provider_execution_state": verified["state"],
            "bubbles_receipt_sha256": semantic["receipt_sha256"],
            "bubbles_semantic_state": semantic["semantic_state"],
            "bubbles_semantic_checks": semantic["checks"],
            "authority_leases_absent": authority_count == 0,
            "provider_effect": False,
            "external_effect": False,
            "provider_authority": False,
            "persistent_24x7_host": False,
        }
        (output / "bridge-receipt.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return result
    finally:
        runtime.close()
