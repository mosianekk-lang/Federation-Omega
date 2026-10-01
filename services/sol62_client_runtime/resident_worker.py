from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Mapping

from federation.mobile_gateway.fuse_mobile_v1 import EffectClass, MobileRequest, Mode
from fuse_genesis.currentness import resolve_source_epoch
from fuse_genesis.resident_host import ResidentHost
from services.fuse_mobile_gateway.bindings import runtime_from_environment as gateway_from_environment
from services.fuse_mobile_gateway.runtime import GatewayRuntime, RuntimeBindingError, VerifiedIdentity
from services.sol62_client_runtime.autonomous_harvester import FuseAutonomousHarvester
from services.sol62_client_runtime.gateway_adapter import GatewayChatAdapter
from sol_61_runtime.sol_62 import GatewayPolicy, Sol62Runtime, WorkloadIdentityPolicy
from sol_61_runtime.sol_62_complete_client_runtime import RouteCandidate, Sol62CompleteClientRuntime
from sol_61_runtime.sol_62_genesis_client_bridge import Sol62GenesisWakeBridge


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _sol_runtime() -> Sol62Runtime:
    root = Path(os.getenv("SOL62_CLIENT_ROOT", "./sol62-client-state"))
    runtime_id = os.getenv("SOL62_RUNTIME_ID", "sol-6.2")
    gateway_id = os.getenv("SOL62_GATEWAY_ID", "sol-gateway")
    issuer = os.getenv("SOL62_WORKER_ISSUER", "https://token.actions.githubusercontent.com")
    audience = os.getenv("SOL62_WORKER_AUDIENCE", "sol-runtime")
    subject_prefix = os.getenv(
        "SOL62_WORKER_SUBJECT_PREFIX",
        "repo:mosianekk-lang/Federation-Omega:",
    )
    return Sol62Runtime(
        root,
        gateway_policy=GatewayPolicy(gateway_id, runtime_id),
        identity_policy=WorkloadIdentityPolicy(
            allowed_issuers={issuer},
            audience=audience,
            subject_prefix=subject_prefix,
            max_ttl_seconds=600,
        ),
    )


class ResidentWorkerIdentity:
    def __init__(self) -> None:
        self.issuer = os.getenv("SOL62_WORKER_ISSUER", "").strip()
        self.audience = os.getenv("SOL62_WORKER_AUDIENCE", "").strip()
        self.subject = os.getenv("SOL62_WORKER_SUBJECT", "").strip()
        self.credential_type = os.getenv("SOL62_WORKER_CREDENTIAL_TYPE", "oidc").strip()

    @property
    def ready(self) -> bool:
        return bool(
            self.issuer
            and self.audience
            and self.subject
            and self.credential_type == "oidc"
        )

    def claims(self, now_epoch: int) -> dict[str, Any]:
        if not self.ready:
            raise RuntimeError("SOL62_WORKER_IDENTITY_UNBOUND")
        return {
            "iss": self.issuer,
            "aud": self.audience,
            "sub": self.subject,
            "iat": now_epoch - 5,
            "exp": now_epoch + 300,
            "credential_type": self.credential_type,
        }


class Sol62ResidentProcessor:
    """Genesis task receiver for SOL client wake/build packets.

    Browser session credentials are never persisted or required. The durable SOL
    mission owns the owner subject; server workload identity owns execution.
    Consequential effects still require the normal SOL action-bound authority path.
    """

    def __init__(
        self,
        *,
        gateway: GatewayRuntime | None = None,
        sol: Sol62Runtime | None = None,
        genesis_root: str | Path | None = None,
    ) -> None:
        self.gateway = gateway or gateway_from_environment()
        self.sol = sol or _sol_runtime()
        self.client = Sol62CompleteClientRuntime(self.sol)
        self.worker_identity = ResidentWorkerIdentity()
        self.genesis = Sol62GenesisWakeBridge(
            genesis_root or os.getenv("FUSE_GENESIS_HOST_ROOT", "./fuse-host-state")
        )
        self.source_frontier = (
            os.getenv("SOL62_SOURCE_FRONTIER")
            or os.getenv("FUSE_SOURCE_MAIN")
            or "CURRENT_MAIN_REQUIRED"
        )
        self.client.register_route(
            RouteCandidate(
                "FUSE-AUTO",
                "FUSE_GATEWAY",
                operations=("*",),
                current=True,
                callable=self.gateway.execution_ready,
                authorized=True,
                privacy_ok=True,
                priority=100,
                failure_domain="FUSE_GATEWAY",
            )
        )

    def close(self) -> None:
        self.sol.close()

    def _mission_owner(self, mission_id: str) -> VerifiedIdentity:
        row = self.client._get("sol62.client.mission", mission_id)
        if not row:
            raise KeyError(mission_id)
        subject = str(row["value"].get("owner_subject") or "")
        if not subject:
            raise RuntimeError("SOL62_MISSION_OWNER_MISSING")
        return VerifiedIdentity(
            subject,
            {
                "identity_source": "SOL62_DURABLE_MISSION",
                "background_continuation": "true",
            },
        )

    def _gateway_request(self) -> dict[str, Any]:
        return {
            "runtime_id": os.getenv("SOL62_RUNTIME_ID", "sol-6.2"),
            "via_gateway": os.getenv("SOL62_GATEWAY_ID", "sol-gateway"),
            "authenticated_principal": "spiffe://sol62-client-runtime/resident-worker",
            "policy_version": "6.2",
        }

    async def _wake(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        mission_id = str(payload.get("mission_id") or "")
        if not mission_id:
            raise ValueError("MISSION_ID_REQUIRED")
        if not self.worker_identity.ready:
            raise RuntimeError("SOL62_WORKER_IDENTITY_UNBOUND")

        now = int(time.time())
        owner = self._mission_owner(mission_id)
        result = await self.client.wake_until_terminal(
            mission_id,
            adapter=GatewayChatAdapter(self.gateway, owner),
            gateway_request=self._gateway_request(),
            identity_claims=self.worker_identity.claims(now),
            worker="sol62-genesis-resident",
            now_epoch=now,
            harvester=FuseAutonomousHarvester(source_frontier=self.source_frontier),
        )
        if result.get("build_required") and result.get("build_packet"):
            build_packet = dict(result["build_packet"])
            build_packet["resume_packet"] = result.get("resume_packet")
            result["build_handoff"] = self.genesis.enqueue_build(
                build_packet, now_epoch=time.time()
            )
        elif result.get("state") != "VERIFIED_REALITY" and result.get("resume_packet"):
            result["durable_handoff"] = self.genesis.enqueue(
                result["resume_packet"], now_epoch=time.time()
            )
        return result

    async def _build(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        mission_id = str(payload.get("mission_id") or "")
        if not mission_id:
            raise ValueError("MISSION_ID_REQUIRED")
        owner = self._mission_owner(mission_id)
        build_key = "build-" + _sha(payload)[:24]

        self.client._put(
            "sol62.client.build_work",
            build_key,
            {
                "mission_id": mission_id,
                "state": "BUILD_REQUESTED",
                "packet_sha256": _sha(payload),
                "source_frontier": payload.get("source_frontier"),
                "authority_boundary": payload.get("authority_boundary", {}),
            },
        )
        self.sol.control.append_event(
            mission_id,
            "SOL62_CLIENT_BUILD_REQUESTED",
            {"build_key": build_key, "packet_sha256": _sha(payload)},
        )

        if not self.gateway.execution_ready:
            self.client._put(
                "sol62.client.build_work",
                build_key,
                {
                    "mission_id": mission_id,
                    "state": "WAITING_BUILD_EXECUTOR",
                    "packet_sha256": _sha(payload),
                    "source_frontier": payload.get("source_frontier"),
                },
            )
            return {
                "state": "WAITING_BUILD_EXECUTOR",
                "mission_id": mission_id,
                "build_key": build_key,
                "truth_boundary": "BUILD_PACKET_PERSISTED__NO_BUILD_EXECUTOR_CURRENTLY_CALLABLE",
            }

        intent = (
            "Build the smallest source-independent residual capability described by this "
            "governed SOL 6.2 build packet. Preserve its authority boundary. Do not deploy, "
            "publish, spend, widen permissions, or mutate canonical source. Return the "
            "implementation artifact plus tests and activation requirements.\n\n"
            + json.dumps(dict(payload), sort_keys=True, default=str)
        )
        try:
            result = await self.gateway.execute(
                owner,
                MobileRequest(
                    intent=intent,
                    mode=Mode.BUILD,
                    effect_class=EffectClass.READ_ONLY,
                    verification="HIGH",
                ),
            )
        except RuntimeBindingError as error:
            self.client._put(
                "sol62.client.build_work",
                build_key,
                {
                    "mission_id": mission_id,
                    "state": "WAITING_BUILD_EXECUTOR",
                    "packet_sha256": _sha(payload),
                    "failure_code": error.code,
                },
            )
            return {
                "state": "WAITING_BUILD_EXECUTOR",
                "mission_id": mission_id,
                "build_key": build_key,
                "reason": error.code,
            }

        artifact = {
            "mission_id": mission_id,
            "build_key": build_key,
            "status": result.status,
            "trace_id": result.trace_id,
            "provider": result.provider,
            "model": result.model,
            "source_refs": list(result.source_refs),
            "artifact_text": result.text,
            "artifact_sha256": hashlib.sha256(result.text.encode("utf-8")).hexdigest(),
            "activation_state": "SOURCE_INDEPENDENT_CANDIDATE",
            "canonical_source_mutated": False,
            "provider_effect_performed": False,
        }
        self.client._put("sol62.client.build_artifact", build_key, artifact)
        self.client._put(
            "sol62.client.build_work",
            build_key,
            {
                "mission_id": mission_id,
                "state": "SOURCE_INDEPENDENT_CANDIDATE",
                "packet_sha256": _sha(payload),
                "artifact_sha256": artifact["artifact_sha256"],
                "trace_id": result.trace_id,
            },
        )
        self.sol.control.append_event(
            mission_id,
            "SOL62_CLIENT_BUILD_CANDIDATE_PRODUCED",
            {
                "build_key": build_key,
                "artifact_sha256": artifact["artifact_sha256"],
                "trace_id": result.trace_id,
            },
        )
        resume = payload.get("resume_packet")
        handoff = None
        if isinstance(resume, Mapping):
            handoff = self.genesis.enqueue(dict(resume), now_epoch=time.time())
        return {
            "state": "SOURCE_INDEPENDENT_BUILD_CANDIDATE",
            "mission_id": mission_id,
            "build_key": build_key,
            "artifact_sha256": artifact["artifact_sha256"],
            "durable_handoff": handoff,
            "truth_boundary": "BUILD_CANDIDATE_NE_SOURCE_ADMITTED_NE_ACTIVATED",
        }

    def process(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        task_type = payload.get("task_type")
        if task_type == "SOL62_CLIENT_WAKE":
            return asyncio.run(self._wake(payload))
        if task_type == "SOL62_CLIENT_BUILD":
            return asyncio.run(self._build(payload))
        raise ValueError("UNSUPPORTED_SOL62_RESIDENT_TASK")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        default=os.getenv("FUSE_GENESIS_HOST_ROOT", "./fuse-host-state"),
    )
    parser.add_argument("--max-ticks", type=int, default=None)
    parser.add_argument(
        "--interval",
        type=float,
        default=float(os.getenv("FUSE_GENESIS_HOST_INTERVAL", "1")),
    )
    args = parser.parse_args()
    epoch = resolve_source_epoch()
    processor = Sol62ResidentProcessor(genesis_root=args.root)
    host = ResidentHost(args.root, epoch, interval=args.interval)
    try:
        receipt = host.run(
            handler=processor.process,
            max_ticks=args.max_ticks,
        )
        print(
            json.dumps(
                {
                    "state": "SOL62_RESIDENT_STOPPED",
                    **receipt,
                    "runtime": "SOL_6_2_COMPLETE_FUSE_CLIENT_RUNTIME_V1",
                },
                sort_keys=True,
            )
        )
    finally:
        host.close()
        processor.close()


if __name__ == "__main__":
    main()
