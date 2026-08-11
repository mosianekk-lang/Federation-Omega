"""Private authenticated HTTP API for the EvidenceOps Secure Capability Box."""

from __future__ import annotations

import hmac
import os

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .errors import AuthorizationDenied, InvalidRequest, SecureBoxError
from .runtime import SecureBoxRuntime, build_runtime


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IssueBody(StrictModel):
    mission_id: str
    mission_version: int = Field(ge=1)
    operation_id: str
    action: str
    ttl_seconds: int = Field(default=300, ge=1, le=900)


class ExecuteBody(StrictModel):
    handle: str
    payload: dict = Field(default_factory=dict)


class RevokeBody(StrictModel):
    handle: str
    reason: str = Field(min_length=1, max_length=256)


def create_app(runtime: SecureBoxRuntime | None = None) -> FastAPI:
    runtime = runtime or build_runtime()
    app = FastAPI(title="EvidenceOps Secure Capability Box", version="1.0.0", docs_url=None, redoc_url=None)

    def authenticate(
        authorization: str | None = Header(default=None),
        x_scb_api_token: str | None = Header(default=None),
    ) -> None:
        supplied = ""
        if authorization and authorization.startswith("Bearer "):
            supplied = authorization[7:]
        if x_scb_api_token:
            supplied = x_scb_api_token
        if not supplied or not hmac.compare_digest(supplied, runtime.config.api_token):
            raise HTTPException(status_code=401, detail="authentication failed")

    @app.exception_handler(SecureBoxError)
    async def safe_box_error(_request, exc: SecureBoxError):
        from fastapi.responses import JSONResponse
        status = 403 if isinstance(exc, AuthorizationDenied) else 400 if isinstance(exc, InvalidRequest) else 409
        return JSONResponse(status_code=status, content={"error": type(exc).__name__, "detail": "request was rejected"})

    @app.get("/health")
    def health():
        return {"ok": True, "service": "evidenceops-secure-capability-box"}

    @app.get("/ready", dependencies=[Depends(authenticate)])
    def ready():
        return runtime.broker.readiness()

    @app.post("/v1/capabilities/issue", dependencies=[Depends(authenticate)])
    def issue(body: IssueBody):
        request = runtime.request(**body.model_dump())
        return {"handle": runtime.broker.issue(request), "operation_id": request.operation_id, "expires_in": request.ttl_seconds}

    @app.post("/v1/capabilities/execute", dependencies=[Depends(authenticate)])
    def execute(body: ExecuteBody):
        return runtime.broker.execute(
            body.handle,
            subject=runtime.config.subject,
            audience=runtime.config.audience,
            payload=body.payload,
        ).as_dict()

    @app.post("/v1/capabilities/revoke", dependencies=[Depends(authenticate)])
    def revoke(body: RevokeBody):
        sequence = runtime.broker.revoke(
            body.handle, subject=runtime.config.subject,
            audience=runtime.config.audience, reason=body.reason,
        )
        return {"state": "REVOKED", "audit_sequence": sequence}

    @app.get("/v1/audit/status", dependencies=[Depends(authenticate)])
    def audit_status():
        return {"valid": runtime.broker.store.verify_audit(), "health": runtime.broker.store.health()}

    @app.get("/v1/reconcile", dependencies=[Depends(authenticate)])
    def reconcile():
        return {"incomplete_operations": runtime.broker.store.incomplete_operations()}

    return app


app = create_app() if os.environ.get("SCB_LAZY_APP") != "1" else None
