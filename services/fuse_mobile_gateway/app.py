from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from federation.mobile_gateway.fuse_mobile_v1 import MobileRequest, Mode
from services.fuse_mobile_gateway import VERSION
from services.fuse_mobile_gateway.bindings import runtime_from_environment
from services.fuse_mobile_gateway.aegis_edge_adapter import build_aegis_edge_router, sink_from_environment
from services.fuse_mobile_gateway.runtime import (
    GatewayRuntime,
    RuntimeBindingError,
    bearer_token,
    effect_from_string,
)
from services.fuse_mobile_gateway.observation import ObservationCache, classify_ui_signal


class ChatRequestBody(BaseModel):
    intent: str = Field(min_length=1, max_length=100_000)
    mode: Mode = Mode.AUTO
    requested_sources: list[str] = Field(default_factory=list, max_length=32)
    requested_models: list[str] = Field(default_factory=list, max_length=16)
    requested_agents: list[str] = Field(default_factory=list, max_length=16)
    effect_class: str = "READ_ONLY"
    verification: str = Field(default="HIGH", pattern="^(NORMAL|HIGH)$")


class DeviceRevokeBody(BaseModel):
    device_token: str = Field(min_length=32, max_length=512)


class UISignalBody(BaseModel):
    text: str = Field(min_length=1, max_length=4_000)
    source: str = Field(default="fuse-workspace", min_length=1, max_length=128)
    mission_id: str | None = Field(default=None, max_length=256)


def _status_for(error: RuntimeBindingError) -> int:
    if error.code in {
        "AUTHORIZATION_REQUIRED",
        "BEARER_TOKEN_REQUIRED",
        "SESSION_MALFORMED",
        "SESSION_SIGNATURE_INVALID",
        "SESSION_SCOPE_INVALID",
        "SESSION_SUBJECT_MISSING",
        "SESSION_EXPIRED",
        "SESSION_DEVICE_BINDING_REQUIRED",
        "SESSION_DEVICE_REVOKED",
        "SESSION_SUBJECT_MISMATCH",
        "SESSION_INVALID",
        "OWNER_ENROLLMENT_INVALID",
        "OWNER_IDENTITY_MISMATCH",
        "IAP_ASSERTION_REQUIRED",
        "IAP_ASSERTION_INVALID",
        "IAP_ISSUER_INVALID",
        "IAP_AUDIENCE_INVALID",
        "IAP_OWNER_EMAIL_INVALID",
        "IAP_SUBJECT_MISSING",
        "DEVICE_CREDENTIAL_INVALID",
        "DEVICE_SUBJECT_MISMATCH",
    }:
        return 401
    if error.code in {
        "OWNER_EFFECT_APPROVAL_REQUIRED",
        "OWNER_ENROLLMENT_ALREADY_CONSUMED",
    }:
        return 409
    if error.code in {
        "IDENTITY_VERIFIER_UNBOUND",
        "SESSION_SIGNER_UNBOUND",
        "FEDERATION_EXECUTOR_UNBOUND",
        "OWNER_ENROLLMENT_UNBOUND",
        "OWNER_IAP_VERIFIER_UNBOUND",
        "OWNER_IAP_ENROLLMENT_UNBOUND",
        "DEVICE_REVOCATION_UNBOUND",
        "RUNTIME_CONFIGURATION_INCOMPLETE",
        "CANONICAL_PROJECT_MISMATCH",
    }:
        return 503
    return 400


def create_app(runtime: GatewayRuntime | None = None) -> FastAPI:
    active = runtime or GatewayRuntime()
    app = FastAPI(
        title="FUSE Mobile Gateway",
        version=VERSION,
        docs_url=None,
        redoc_url=None,
    )
    app.include_router(build_aegis_edge_router(active, sink_from_environment()))
    observations = ObservationCache.from_environment()

    def fail(error: RuntimeBindingError) -> None:
        raise HTTPException(
            status_code=_status_for(error),
            detail={"status": "HELD", "reason": error.code},
        ) from error

    def fuse_token(x_fuse_authorization: str | None, authorization: str | None) -> str:
        """Keep provider transport identity separate from FUSE application auth.

        X-Fuse-Authorization is authoritative for real private ingress. Authorization
        remains a local/provider-canary compatibility fallback until IAP is enabled.
        """
        try:
            return bearer_token(x_fuse_authorization or authorization)
        except RuntimeBindingError as error:
            fail(error)

    async def session_identity(x_fuse_authorization: str | None, authorization: str | None):
        try:
            return await active.verify_session(fuse_token(x_fuse_authorization, authorization))
        except RuntimeBindingError as error:
            fail(error)

    @app.get("/health")
    async def health() -> dict:
        runtime_ready = active.session_ready and active.execution_ready
        return {
            "ok": True,
            "service": "fuse-mobile-gateway",
            "version": VERSION,
            "status": "RUNTIME_READY" if runtime_ready else "SOURCE_READY_RUNTIME_BINDING_REQUIRED",
            "enrollment_ready": active.enrollment_ready,
            "iap_enrollment_ready": active.iap_enrollment_ready,
            "session_ready": active.session_ready,
            "execution_ready": active.execution_ready,
            "provider_credentials_in_client": False,
        }

    @app.post("/v1/enroll")
    async def enroll(
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
        x_goog_iap_jwt_assertion: Annotated[str | None, Header(alias="X-Goog-IAP-JWT-Assertion")] = None,
    ) -> dict:
        try:
            if x_goog_iap_jwt_assertion:
                return await active.enroll_iap_owner(x_goog_iap_jwt_assertion)
            credential = fuse_token(x_fuse_authorization, authorization)
            return await active.enroll_device(credential)
        except RuntimeBindingError as error:
            fail(error)

    @app.post("/v1/session")
    async def create_session(
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict:
        try:
            credential = fuse_token(x_fuse_authorization, authorization)
            return await active.issue_session(credential)
        except RuntimeBindingError as error:
            fail(error)

    @app.post("/v1/device/revoke")
    async def revoke_device(
        body: DeviceRevokeBody,
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict:
        identity = await session_identity(x_fuse_authorization, authorization)
        try:
            await active.revoke_device(identity, body.device_token)
            return {"status": "REVOKED", "subject": identity.subject}
        except RuntimeBindingError as error:
            fail(error)

    @app.get("/v1/federation/health")
    async def federation_health(
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict:
        identity = await session_identity(x_fuse_authorization, authorization)
        manifest = await active.manifest(identity)
        capabilities = manifest.public_view()["capabilities"]
        return {
            "status": "RUNTIME_READY" if active.execution_ready else "DEGRADED_EXECUTOR_UNBOUND",
            "version": VERSION,
            "subject": identity.subject,
            "enrollment_ready": active.enrollment_ready,
            "iap_enrollment_ready": active.iap_enrollment_ready,
            "session_ready": active.session_ready,
            "execution_ready": active.execution_ready,
            "capability_count": len(capabilities),
            "runtime_verified_capability_count": sum(
                1
                for capability in capabilities
                if capability["health"] in {
                    "RUNTIME_VERIFIED",
                    "BEHAVIOR_VERIFIED",
                    "HOSTED_VERIFIED",
                    "VERIFIED_SCOPED",
                    "HEALTHY",
                }
            ),
        }

    @app.get("/v1/capabilities")
    async def capabilities(
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict:
        identity = await session_identity(x_fuse_authorization, authorization)
        return (await active.manifest(identity)).public_view()

    @app.post("/v1/chat")
    async def chat(
        body: ChatRequestBody,
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict:
        identity = await session_identity(x_fuse_authorization, authorization)
        try:
            request = MobileRequest(
                intent=body.intent,
                mode=body.mode,
                requested_sources=tuple(body.requested_sources),
                requested_models=tuple(body.requested_models),
                requested_agents=tuple(body.requested_agents),
                effect_class=effect_from_string(body.effect_class),
                verification=body.verification,
            )
            result = await active.execute(identity, request)
            return {
                "text": result.text,
                "trace_id": result.trace_id,
                "status": result.status,
                "provider": result.provider,
                "model": result.model,
                "source_refs": list(result.source_refs),
            }
        except RuntimeBindingError as error:
            fail(error)

    @app.get("/v1/workspace/status")
    async def workspace_status(
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict:
        identity = await session_identity(x_fuse_authorization, authorization)
        return {
            "schema": "FUSE-WORKSPACE-STATUS-V1",
            "version": VERSION,
            "subject": identity.subject,
            "mission_state_root": "MISSION_BUS_WORK_PLANE",
            "chat_is_detachable_client": True,
            "observation_cache": observations.status(),
            "truth_boundary": "OBSERVATION_CACHE_IS_EPHEMERAL_AND_NEVER_A_MISSION_STATE_OR_AUTHORITY_ROOT",
        }

    @app.post("/v1/observation/ui-signal")
    async def observation_ui_signal(
        body: UISignalBody,
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict:
        identity = await session_identity(x_fuse_authorization, authorization)
        signal = classify_ui_signal(body.text)
        return {
            "schema": "FUSE-UI-SIGNAL-CLASSIFICATION-V1",
            "subject": identity.subject,
            "source": body.source,
            "mission_id": body.mission_id,
            "category": signal.category,
            "severity": signal.severity,
            "recommended_action": signal.recommended_action,
            "normalized_message": signal.normalized_message,
            "mission_state_changed": False,
            "truth_boundary": "CLASSIFICATION_ONLY__DURABLE_MISSION_UPDATES_REMAIN_IN_FUSE_PLANE",
        }

    @app.post("/v1/vision/frame")
    async def vision_frame(
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
        x_fuse_vision_source: Annotated[str | None, Header(alias="X-Fuse-Vision-Source")] = None,
        x_fuse_mission_id: Annotated[str | None, Header(alias="X-Fuse-Mission-Id")] = None,
    ) -> dict:
        identity = await session_identity(x_fuse_authorization, authorization)
        data = await request.body()
        try:
            status = observations.ingest_frame(
                data,
                content_type=request.headers.get("content-type", ""),
                source=x_fuse_vision_source or "fuse-owner-client",
                mission_id=x_fuse_mission_id,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail={"status": "HELD", "reason": str(error)}) from error
        return {"subject": identity.subject, **status}

    @app.get("/v1/vision/context")
    async def vision_context(
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict:
        identity = await session_identity(x_fuse_authorization, authorization)
        return {"subject": identity.subject, **observations.status()}

    @app.get("/v1/vision/latest/image")
    async def vision_latest_image(
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ):
        await session_identity(x_fuse_authorization, authorization)
        path = observations.image_path()
        if not path:
            raise HTTPException(status_code=404, detail={"status": "HELD", "reason": "VISION_FRAME_NOT_AVAILABLE"})
        meta = observations.status()
        return FileResponse(
            path,
            media_type=str(meta.get("content_type") or "application/octet-stream"),
            headers={"Cache-Control": "no-store, max-age=0", "X-FUSE-Frame-SHA256": str(meta.get("sha256") or "")},
        )

    @app.delete("/v1/vision/latest")
    async def vision_clear(
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict:
        identity = await session_identity(x_fuse_authorization, authorization)
        return {"subject": identity.subject, **observations.clear()}

    return app


app = create_app(runtime_from_environment())
