from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import threading
from typing import Any, Callable, Mapping

from bubbles.chat_governor_omega3 import (
    ConnectorGateway,
    DurableState,
    FrontierControlPlane,
    MissionPlan,
)
from federation.fio_surface_access import (
    SurfaceAction,
    SurfaceAttestation,
    SurfaceClass,
    SurfaceManifest,
    SurfaceRegistry,
    SovaraDerivedSurfaceRouter,
    default_kdv_surface_manifests,
)

HOST_RECEIPT_SCHEMA = "BUBBLES-CHATGOV-FRONTIER-HOST-RECEIPT-V1"
HOST_SURFACE_ID = "BUBBLES_PROVIDER_SURFACE_READBACK_HOST"
HOST_ADAPTER_ID = "BUBBLES_PROVIDER_SURFACE_PROBE"


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _semantic_readback_ok(payload: Mapping[str, Any]) -> bool:
    if payload.get("schema") != "BUBBLES-PROVIDER-SURFACE-PROBE-V1":
        return False
    if payload.get("mutation_attempted") is not False:
        return False
    if payload.get("secret_values_recorded") is not False:
        return False
    if not isinstance(payload.get("surfaces"), Mapping):
        return False
    corrections = payload.get("surface_corrections", {})
    if not isinstance(corrections, Mapping):
        return False
    correction = corrections.get("archon_apps_script_exact_deployment")
    if not isinstance(correction, Mapping):
        return False
    if correction.get("schema") != "BUBBLES-ARCHON-APPS-SCRIPT-DEPLOYMENT-PROBE-V1":
        return False
    if correction.get("mutation_attempted") is not False:
        return False
    if correction.get("credential_values_recorded") is not False:
        return False
    return True


def _fio_route(*, source_version: str, observed_at: str, proof_ref: str):
    host_manifest = SurfaceManifest(
        surface_id=HOST_SURFACE_ID,
        name="Bubbles provider surface readback host",
        surface_class=SurfaceClass.HOST_INTERFACE,
        capabilities=("READ",),
        authority_ceiling="A0_READ_ONLY",
        privacy_ceiling="P3_RESTRICTED",
        direct_adapter=HOST_ADAPTER_ID,
        fallback_adapter="",
        external_effect_default=False,
        explicit_communication_send_only=False,
        auto_enroll_unknown=False,
        freshness_ttl_minutes=30,
    )
    registry = SurfaceRegistry(default_kdv_surface_manifests() + (host_manifest,))
    router = SovaraDerivedSurfaceRouter(registry)
    attestation = SurfaceAttestation(
        surface_id=HOST_SURFACE_ID,
        present=True,
        direct_route_live=True,
        fallback_route_live=False,
        read_capable=True,
        write_capable=False,
        semantic_readback_ready=True,
        fresh=True,
        proof_refs=(proof_ref, f"source:{source_version}"),
        observed_at=observed_at,
        current_authority="A0_READ_ONLY",
        failure_domain="GITHUB_ACTIONS_BUBBLES_PROVIDER_SURFACE",
    )
    action = SurfaceAction(
        action_id="bubbles-provider-surface-readback",
        surface_id=HOST_SURFACE_ID,
        capability="READ",
        requested_authority="A0_READ_ONLY",
        external_effect=False,
        effect_class="NONE",
        readback_required=True,
        rollback_required=False,
    )
    decision = router.route(action, (attestation,))
    if (
        decision.state != "AUTO_ROUTE_SAFE_INTERNAL"
        or decision.auto_execute_internal is not True
        or decision.selected_adapter != HOST_ADAPTER_ID
        or decision.delegate_to_sovara
        or decision.human_required
    ):
        raise RuntimeError(f"FIO_HOST_ROUTE_NOT_SAFE:{decision.state}")
    return decision


class HostedProviderReadbackAdapter:
    """Bind the existing Bubbles provider probe to FIO + ChatGov safe-read execution.

    This class does not own provider authority and exposes no effectful operation.
    It exists only to route the pre-existing read-only provider probe through the
    admitted ChatGov ConnectorGateway / FrontierControlPlane path.
    """

    def __init__(
        self,
        *,
        state_path: str,
        source_version: str,
        mission_currentness_ref: str,
        mission_id: str = "MISSION-FUSE-BUBBLES-HOST-ADOPTER-20260905-001",
        observed_at: str | None = None,
        singleflight_ttl_seconds: float = 60.0,
    ) -> None:
        self.state_path = str(state_path)
        self.source_version = str(source_version).strip() or "UNKNOWN_SOURCE"
        self.mission_currentness_ref = (
            str(mission_currentness_ref).strip()
            or f"GITHUB_SHA:{self.source_version}"
        )
        self.mission_id = str(mission_id).strip()
        if not self.mission_id:
            raise ValueError("HOST_ADAPTER_MISSION_ID_REQUIRED")
        self.observed_at = observed_at or datetime.now(timezone.utc).isoformat()
        self.frontier = FrontierControlPlane(
            singleflight_ttl_seconds=singleflight_ttl_seconds
        )
        self.route = _fio_route(
            source_version=self.source_version,
            observed_at=self.observed_at,
            proof_ref=".github/workflows/bubbles-command-bus.yml#provider-surface-readback",
        )
        self.plan = MissionPlan(
            mission_id=self.mission_id,
            objective=(
                "Execute the existing Bubbles provider surface readback through "
                "FIO and ChatGov without provider mutation."
            ),
            mission_type="cloud_deployment",
            active_specialists=["Bubbles", "FIO", "ChatGov"],
            active_connectors=[self.route.selected_adapter],
            excluded_connectors=[],
            retrieval_budget=4,
            tool_result_token_budget=4096,
            max_parallel_lanes=2,
            created_at=self.observed_at,
        )

    def _gateway(self, suffix: str = "") -> ConnectorGateway:
        path = Path(self.state_path)
        if suffix:
            path = path.with_name(path.name + suffix)
        path.parent.mkdir(parents=True, exist_ok=True)
        return ConnectorGateway(DurableState(str(path)), frontier=self.frontier)

    def _execute_one(
        self,
        gateway: ConnectorGateway,
        reader: Callable[[], Mapping[str, Any]],
    ) -> dict[str, Any]:
        return gateway.execute(
            plan=self.plan,
            connector=self.route.selected_adapter,
            action="provider_surface_readback",
            target=HOST_SURFACE_ID,
            fn=lambda: dict(reader()),
            semantic_check=_semantic_readback_ok,
            source_version=self.source_version,
            force_revalidation=False,
            retry_attempts=1,
            effect_class="READ_ONLY",
            use_frontier=True,
        )

    def execute(
        self,
        reader: Callable[[], Mapping[str, Any]],
        *,
        prove_singleflight: bool = False,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        provider_executions = 0
        provider_lock = threading.Lock()

        def counted_reader() -> Mapping[str, Any]:
            nonlocal provider_executions
            with provider_lock:
                provider_executions += 1
            return reader()

        if prove_singleflight:
            barrier = threading.Barrier(2)
            results: list[dict[str, Any]] = []
            errors: list[BaseException] = []
            result_lock = threading.Lock()
            gateways = (self._gateway(".a"), self._gateway(".b"))

            def runner(gateway: ConnectorGateway) -> None:
                try:
                    barrier.wait(timeout=5.0)
                    result = self._execute_one(gateway, counted_reader)
                    with result_lock:
                        results.append(result)
                except BaseException as exc:
                    with result_lock:
                        errors.append(exc)

            threads = [
                threading.Thread(target=runner, args=(gateway,), daemon=True)
                for gateway in gateways
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=120.0)
            if any(thread.is_alive() for thread in threads):
                raise TimeoutError("HOSTED_SINGLEFLIGHT_THREADS_NOT_TERMINAL")
            if errors:
                raise RuntimeError(
                    "HOSTED_SINGLEFLIGHT_CALLER_FAILED:"
                    + ",".join(type(exc).__name__ for exc in errors)
                )
            if len(results) != 2:
                raise RuntimeError("HOSTED_SINGLEFLIGHT_RESULT_COUNT_INVALID")
        else:
            results = [self._execute_one(self._gateway(), counted_reader)]

        payload_hashes = {
            _digest(result.get("payload"))
            for result in results
            if isinstance(result.get("payload"), Mapping)
        }
        if len(payload_hashes) != 1:
            raise RuntimeError("HOSTED_SINGLEFLIGHT_PAYLOAD_DIVERGENCE")
        payload = dict(results[0]["payload"])

        caller_frontier_flags = [
            result.get("frontier_singleflight") is True for result in results
        ]
        singleflight_verified = (
            prove_singleflight
            and provider_executions == 1
            and self.frontier.singleflight.executions == 1
            and self.frontier.singleflight.coalesced_waiters >= 1
            and all(caller_frontier_flags)
        )
        if prove_singleflight and not singleflight_verified:
            raise RuntimeError("HOSTED_FRONTIER_SINGLEFLIGHT_NOT_PROVEN")

        route_material = asdict(self.route)
        route_material["mode"] = self.route.mode.value
        frontier_receipt = asdict(self.frontier.receipt())
        result_summaries = [
            {
                "reused": bool(result.get("reused")),
                "reuse_source": result.get("reuse_source"),
                "idempotency_key": result.get("idempotency_key"),
                "attempts": result.get("attempts"),
                "frontier_singleflight": result.get("frontier_singleflight"),
            }
            for result in results
        ]
        base = {
            "schema": HOST_RECEIPT_SCHEMA,
            "mission_id": self.mission_id,
            "host": "GITHUB_ACTIONS_BUBBLES_COMMAND_BUS",
            "host_job": "provider-surface-readback",
            "source_version": self.source_version,
            "mission_currentness_ref": self.mission_currentness_ref,
            "effect_class": "READ_ONLY",
            "fio_route": route_material,
            "chatgov_gateway": {
                "connector": self.route.selected_adapter,
                "action": "provider_surface_readback",
                "target": HOST_SURFACE_ID,
                "results": result_summaries,
            },
            "frontier_binding": frontier_receipt,
            "singleflight_proof": {
                "requested_callers": len(results),
                "provider_execution_count": provider_executions,
                "frontier_executions": self.frontier.singleflight.executions,
                "coalesced_waiters": self.frontier.singleflight.coalesced_waiters,
                "reuse_hits": self.frontier.singleflight.reuse_hits,
                "verified": singleflight_verified,
            },
            "provider_receipt_schema": payload.get("schema"),
            "provider_receipt_sha256": next(iter(payload_hashes)),
            "semantic_readback_verified": _semantic_readback_ok(payload),
            "host_binding_verified": bool(
                self.route.auto_execute_internal
                and all(caller_frontier_flags)
                and _semantic_readback_ok(payload)
            ),
            "provider_effect_authorized": False,
            "provider_effect_performed": False,
            "source_promotion_authorized": False,
            "native_chatgpt_dispatch_proven": False,
            "secret_values_recorded": False,
            "truth_boundary": (
                "This receipt proves the existing Bubbles GitHub Actions provider-readback "
                "host invoked the read-only provider probe through FIO routing and ChatGov "
                "ConnectorGateway/FrontierControlPlane. It does not prove native ChatGPT "
                "tool-dispatch adoption, provider mutation authority, deployment, traffic "
                "control, skill promotion, or FUSE source/runtime promotion."
            ),
        }
        receipt = dict(base)
        receipt["receipt_sha256"] = _digest(base)
        return payload, receipt


def execute_hosted_provider_readback(
    reader: Callable[[], Mapping[str, Any]],
    *,
    state_path: str,
    source_version: str,
    mission_currentness_ref: str,
    prove_singleflight: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    return HostedProviderReadbackAdapter(
        state_path=state_path,
        source_version=source_version,
        mission_currentness_ref=mission_currentness_ref,
    ).execute(reader, prove_singleflight=prove_singleflight)


__all__ = [
    "HOST_ADAPTER_ID",
    "HOST_RECEIPT_SCHEMA",
    "HOST_SURFACE_ID",
    "HostedProviderReadbackAdapter",
    "execute_hosted_provider_readback",
]
