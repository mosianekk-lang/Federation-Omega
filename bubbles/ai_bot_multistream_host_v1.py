"""Bubbles host adapter for the FUSE AI-Bot Multi-Path / Multi-Stream Fabric v1.

The adapter is deliberately no-effect and provider-neutral. It binds the source-admitted
FUSE fabric to an existing Bubbles GitHub-hosted contract surface without creating a new
scheduler, daemon, provider identity, authority plane, memory root, or proof plane.

Hosted execution proves only that the Bubbles host imported and executed the planning /
reconciliation capability. Logical bot cells remain distinct from provider-native workers.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Iterable, Sequence

from federation.fuse_ai_bot_multistream_fabric_v1 import (
    FUSEAIBotMultiStreamFabric,
    MultiStreamPlan,
    OmegaWitness,
    PathOutcome,
    PathState,
    StreamPath,
)

SCHEMA = "BUBBLES-FUSE-AI-BOT-MULTISTREAM-HOST-V1"
VERSION = "1.0.0"


def _digest(value: object) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + sha256(body.encode("utf-8")).hexdigest()


class BubblesAIBotMultiStreamHost:
    """Existing-host adapter; planning/reconciliation only, never provider execution."""

    def __init__(self, *, max_parallel: int = 4, corroboration_required_per_stream: int = 1) -> None:
        self.fabric = FUSEAIBotMultiStreamFabric(
            max_parallel=max_parallel,
            corroboration_required_per_stream=corroboration_required_per_stream,
        )

    def plan(
        self,
        *,
        mission_id: str,
        objective: str,
        required_streams: Iterable[str],
        paths: Sequence[StreamPath],
    ) -> MultiStreamPlan:
        return self.fabric.plan(
            mission_id=mission_id,
            objective=objective,
            required_streams=required_streams,
            paths=paths,
        )

    def reconcile(self, plan: MultiStreamPlan, outcomes: Sequence[PathOutcome]) -> OmegaWitness:
        return self.fabric.reconcile(plan, outcomes)


def run_host_canary(*, source_ref: str) -> dict[str, object]:
    """Execute a deterministic synthetic no-effect mission through the Bubbles host adapter."""
    host = BubblesAIBotMultiStreamHost(max_parallel=3)
    paths = (
        StreamPath(
            path_id="SOURCE_PRIMARY",
            stream_id="SOURCE",
            objective="Attempt the primary source-admission route",
            independent_group="GITHUB_PRIMARY",
            closure_leverage=0.95,
            information_gain=0.80,
            success_probability=0.80,
            reversibility=1.0,
            cost=0.05,
            risk=0.05,
            latency=0.10,
            mutation_domain="github-source-write",
            evidence_refs=("host-canary:source-primary",),
        ),
        StreamPath(
            path_id="SOURCE_ALTERNATE",
            stream_id="SOURCE",
            objective="Use a materially different source-admission route after failure",
            independent_group="GITHUB_ALTERNATE",
            closure_leverage=0.85,
            information_gain=0.85,
            success_probability=0.90,
            reversibility=1.0,
            cost=0.05,
            risk=0.05,
            latency=0.10,
            mutation_domain="github-source-write",
            evidence_refs=("host-canary:source-alternate",),
        ),
        StreamPath(
            path_id="HOST_READBACK",
            stream_id="HOST",
            objective="Prove the independent hosted readback stream",
            independent_group="GITHUB_ACTIONS_HOST",
            closure_leverage=0.90,
            information_gain=0.90,
            success_probability=0.95,
            reversibility=1.0,
            cost=0.02,
            risk=0.02,
            latency=0.05,
            mutation_domain="github-host-read",
            evidence_refs=("host-canary:host-readback",),
        ),
    )
    plan = host.plan(
        mission_id="FUSE-AI-BOT-HOST-CANARY",
        objective="Prove Formation × Alpha→Omega multi-path multi-stream planning inside Bubbles",
        required_streams=("SOURCE", "HOST"),
        paths=paths,
    )
    witness = host.reconcile(
        plan,
        (
            PathOutcome(
                path_id="SOURCE_PRIMARY",
                stream_id="SOURCE",
                independent_group="GITHUB_PRIMARY",
                state=PathState.FAILED,
                failure_fingerprint="HOST_CANARY_PRIMARY_ROUTE_FAILURE",
                retry_after_predicate="PRIMARY_ROUTE_PREDICATE_CHANGED",
            ),
            PathOutcome(
                path_id="SOURCE_ALTERNATE",
                stream_id="SOURCE",
                independent_group="GITHUB_ALTERNATE",
                state=PathState.VERIFIED,
                evidence_refs=("host-canary:alternate-path-verified",),
            ),
            PathOutcome(
                path_id="HOST_READBACK",
                stream_id="HOST",
                independent_group="GITHUB_ACTIONS_HOST",
                state=PathState.VERIFIED,
                evidence_refs=("host-canary:host-stream-verified",),
            ),
        ),
    )
    roles = tuple(sorted(cell.role for cell in plan.logical_bot_cells))
    host_binding_verified = bool(
        witness.completion_allowed
        and witness.state == "OMEGA_MULTIPATH_MULTISTREAM_VERIFIED"
        and len(plan.logical_bot_cells) == 7
        and plan.provider_native_worker_count == 0
        and "SOURCE_PRIMARY:PRIMARY_ROUTE_PREDICATE_CHANGED" in witness.retryable_failures
    )
    payload: dict[str, object] = {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "HOST_BOUND_VERIFIED" if host_binding_verified else "HOST_BINDING_HELD",
        "source_ref": source_ref,
        "host_surface": "BUBBLES_COMMAND_BUS_CONTRACT_JOB",
        "execution_route": "tests.test_bubbles_control_plane -> BubblesWorkGraphAdapterTests -> BubblesAIBotMultiStreamHost",
        "host_binding_verified": host_binding_verified,
        "mission_id": plan.mission_id,
        "plan_sha256": plan.plan_sha256,
        "witness_sha256": witness.witness_sha256,
        "selected_wave": list(plan.selected_wave),
        "logical_bot_roles": list(roles),
        "logical_bot_count": len(plan.logical_bot_cells),
        "provider_native_worker_count": plan.provider_native_worker_count,
        "multipath_recovery_verified": witness.completion_allowed,
        "negative_knowledge": list(witness.negative_knowledge),
        "retryable_failures": list(witness.retryable_failures),
        "provider_execution_attempted": False,
        "external_effect": False,
        "authority_delta": "NONE",
        "truth_boundary": (
            "This receipt proves the existing Bubbles GitHub-hosted contract surface imported and executed the "
            "Formation × Alpha→Omega planning/reconciliation adapter on a deterministic synthetic no-effect mission. "
            "It does not prove provider-native bot workers, autonomous background execution, provider effects, or production mission behaviour."
        ),
    }
    payload["receipt_sha256"] = _digest(payload)
    return payload


__all__ = ["BubblesAIBotMultiStreamHost", "SCHEMA", "VERSION", "run_host_canary"]
