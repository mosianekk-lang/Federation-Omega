"""Private FastAPI transport for the metadata-only heartbeat runtime."""

from __future__ import annotations

import re

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from evidenceops.capability_heartbeat.foundation.errors import HeartbeatError

from .errors import (
    AuthenticationDenied,
    HeartbeatApiError,
    ImmutableConflict,
    ResourceNotFound,
    RuntimeUnavailable,
)
from .runtime import HeartbeatApiRuntime, build_runtime_from_env
from .schemas import HealthResponse, IngestRequest, SearchRequest

IDEMPOTENCY_HASH = re.compile(r"sha256:[0-9a-f]{64}")
MAX_REQUEST_BODY_BYTES = 64 * 1024


def create_app(runtime: HeartbeatApiRuntime | None = None) -> FastAPI:
    active = runtime or build_runtime_from_env()
    app = FastAPI(
        title="EvidenceOps Private Heartbeat API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.heartbeat_runtime = active

    @app.middleware("http")
    async def enforce_request_size(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH"}:
            declared = request.headers.get("content-length")
            if declared is None or not declared.isdigit() or int(declared) > MAX_REQUEST_BODY_BYTES:
                return JSONResponse(status_code=413, content={"error_code": "REQUEST_BODY_TOO_LARGE"})
        return await call_next(request)

    def authenticate(
        x_evidenceops_internal_auth: str | None = Header(default=None),
    ) -> None:
        try:
            active.authorizer.verify(x_evidenceops_internal_auth)
        except AuthenticationDenied as exc:
            raise HTTPException(
                status_code=401,
                detail={"error_code": "AUTHENTICATION_DENIED"},
                headers={"WWW-Authenticate": "Internal"},
            ) from exc

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"error_code": "METADATA_REQUEST_REJECTED"})

    @app.exception_handler(HeartbeatApiError)
    async def api_error(_request: Request, exc: HeartbeatApiError):
        if isinstance(exc, ResourceNotFound):
            status = 404
            code = "RESOURCE_NOT_FOUND"
        elif isinstance(exc, AuthenticationDenied):
            status = 401
            code = "AUTHENTICATION_DENIED"
        elif isinstance(exc, ImmutableConflict):
            status = 409
            code = "IMMUTABLE_CONFLICT"
        elif isinstance(exc, RuntimeUnavailable):
            status = 503
            code = "RUNTIME_UNAVAILABLE"
        else:
            status = 400
            code = "METADATA_REQUEST_REJECTED"
        return JSONResponse(status_code=status, content={"error_code": code})

    @app.exception_handler(HeartbeatError)
    async def foundation_error(_request: Request, _exc: HeartbeatError):
        return JSONResponse(status_code=400, content={"error_code": "HEARTBEAT_CONTRACT_REJECTED"})

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            ok=True,
            service_code="EVIDENCEOPS-HEARTBEAT-API",
            schema_version="HEARTBEAT-HTTP-0.1",
        )

    @app.get("/ready", dependencies=[Depends(authenticate)])
    def ready():
        state = active.readiness()
        if not state.ready:
            return JSONResponse(status_code=503, content=state.model_dump(mode="json"))
        return state

    @app.get("/v1/status", dependencies=[Depends(authenticate)])
    def status():
        return active.status()

    @app.post("/v1/search", dependencies=[Depends(authenticate)])
    def search(body: SearchRequest):
        return active.search(body)

    @app.get("/v1/resources/{resource_id:path}", dependencies=[Depends(authenticate)])
    def fetch(resource_id: str):
        return active.fetch(resource_id)

    @app.post("/v1/ingest", dependencies=[Depends(authenticate)])
    def ingest(body: IngestRequest):
        return active.ingest(body)

    @app.get("/v1/readback/{idempotency_hash:path}", dependencies=[Depends(authenticate)])
    def readback(idempotency_hash: str):
        if IDEMPOTENCY_HASH.fullmatch(idempotency_hash) is None:
            raise HTTPException(status_code=422, detail={"error_code": "METADATA_REQUEST_REJECTED"})
        return active.readback(idempotency_hash)

    return app


app = create_app()
