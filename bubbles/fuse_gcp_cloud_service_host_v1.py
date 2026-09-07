"""Bubbles hosted no-effect adapter for FUSE-GCP Ω v1.

This adapter proves hosted consumption of the source-admitted FUSE-GCP Formation route
compiler and Alpha→Omega lifecycle. It does not call Google Cloud, create provider
workers, grant authority, mutate resources, or claim continuous service.
"""
from __future__ import annotations

from hashlib import sha256
import json

from federation.fuse_gcp_cloud_service_mesh_v1 import (
    CloudRoute,
    CloudServiceRequest,
    EffectClass,
    FUSEGCPCloudServiceMesh,
    Stage,
)

SCHEMA = "BUBBLES-FUSE-GCP-HOST-V1"
VERSION = "1.0.0"


def _digest(value: object) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + sha256(body.encode("utf-8")).hexdigest()


def run_host_canary(*, source_ref: str) -> dict[str, object]:
    """Run one deterministic read-only Cloud routing/lifecycle canary in Bubbles."""
    mesh = FUSEGCPCloudServiceMesh()
    request = CloudServiceRequest(
        request_id="FUSE-GCP-BUBBLES-HOST-CANARY-001",
        mission_id="MISSION-FUSE-GCP-HOST-CANARY",
        requesting_organ="BUBBLES",
        capability="cloud.service.discovery",
        effect_class=EffectClass.A1_INTERNAL,
    )
    routes = (
        CloudRoute(
            route_id="DIRECT_PROVIDER_READ",
            service="GOOGLE_CLOUD_READ_ONLY",
            executor="EXISTING_TRUSTED_PROVIDER_READER",
            directness=10,
            maturity=8,
            health=1.0,
            reliability=1.0,
            latency_ms=50,
            cost=0.0,
            risk=0.0,
            effect_ceiling=EffectClass.A1_INTERNAL,
            provider_native=True,
            build_required=False,
            evidence_refs=("host-canary:direct-provider-read",),
        ),
        CloudRoute(
            route_id="BUILD_NEW_EXECUTOR",
            service="NEW_CLOUD_EXECUTOR",
            executor="UNBUILT",
            directness=3,
            maturity=1,
            health=1.0,
            reliability=0.5,
            latency_ms=1000,
            cost=1.0,
            risk=0.4,
            effect_ceiling=EffectClass.A1_INTERNAL,
            provider_native=False,
            build_required=True,
            evidence_refs=("host-canary:build-last",),
        ),
    )
    plan = mesh.plan(request, routes, roles=("CLOUD_RUN_AGENT_RUNTIME_BOT", "VERTEX_AGENT_ENGINE_BOT"))
    stages = tuple(packet.stage.value for packet in plan.packets)
    expected_stages = tuple(stage.value for stage in Stage)
    host_binding_verified = bool(
        plan.selected_route_id == "DIRECT_PROVIDER_READ"
        and plan.provider_native_worker_count == 0
        and all(bot.logical_only and not bot.provider_native_worker for bot in plan.logical_bots)
        and stages == expected_stages
        and len(plan.packets) == 10
    )
    payload: dict[str, object] = {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "HOST_BOUND_VERIFIED" if host_binding_verified else "HOST_BINDING_HELD",
        "source_ref": source_ref,
        "host_surface": "BUBBLES_COMMAND_BUS_CONTRACT_JOB",
        "execution_route": "tests.test_cfbe_bubbles_work_graph_adapter_v1 -> run_fuse_gcp_host_canary",
        "host_binding_verified": host_binding_verified,
        "mission_id": plan.mission_id,
        "plan_sha256": plan.plan_sha256,
        "selected_route_id": plan.selected_route_id,
        "alpha_omega_stages": list(stages),
        "logical_bot_roles": sorted(bot.role for bot in plan.logical_bots),
        "logical_bot_count": len(plan.logical_bots),
        "provider_native_worker_count": plan.provider_native_worker_count,
        "provider_execution_attempted": False,
        "cloud_resource_mutation_attempted": False,
        "external_effect": False,
        "authority_delta": "NONE",
        "truth_boundary": (
            "This receipt proves the existing Bubbles GitHub-hosted contract surface imported and executed "
            "the source-admitted FUSE-GCP Formation route tournament and Alpha→Omega lifecycle compiler on a "
            "deterministic no-effect mission. It does not prove a Google Cloud provider call, provider-native "
            "workers, Cloud resource mutation, provider-running state, or continuous service."
        ),
    }
    payload["receipt_sha256"] = _digest(payload)
    return payload


__all__ = ["SCHEMA", "VERSION", "run_host_canary"]
