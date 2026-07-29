import importlib.util
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from .agents_runtime import SovereignLegalRuntime
from .config import Settings, get_settings
from .inventory import InventoryLimits, append_inventory_proof, inventory_path
from .schemas import (
    ActionExecuteRequest,
    BackupCreateRequest,
    ApprovalCreateRequest,
    ApprovalDecisionRequest,
    AuthorityRegisterRequest,
    ClaimCreateRequest,
    ClaimLinkRequest,
    CouncilDecision,
    CouncilDecisionRequest,
    EvidenceIngestRequest,
    HealthResponse,
    AuthPrincipal,
    InventoryRequest,
    KnowledgeIngestRequest,
    KnowledgeSearchRequest,
    MissionRequest,
    MissionResponse,
    ReleaseRequest,
    ReleaseResult,
    RestoreCanaryRequest,
    WorkflowCreateRequest,
    WorkflowFailureRequest,
    WorkflowLeaseRequest,
    WorkflowRecord,
    WorkflowStateRequest,
)
from .security import AccessRequirement, AuthService, SlidingWindowRateLimiter
from .services import Services, build_services


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    services: Services = build_services(settings)
    runtime = SovereignLegalRuntime(services)
    auth = AuthService(settings)
    limiter = SlidingWindowRateLimiter(limit=180, window_seconds=60)

    app = FastAPI(
        title="MODISA–EvidenceOps Sovereign Legal Intelligence OS",
        version="2.0.0",
        description="Proof-bound, human-governed legal intelligence and evidence-control API.",
    )

    async def principal(authorization: str | None = Header(default=None)):
        return auth.principal_from_header(authorization)

    Principal = Annotated[AuthPrincipal, Depends(principal)]

    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        key = request.client.host if request.client else "unknown"
        limiter.check(key)
        try:
            response = await call_next(request)
        except HTTPException:
            raise
        except Exception as exc:
            services.audit.append(
                actor_id="api",
                event_type="UNHANDLED_API_ERROR",
                payload={"path": request.url.path, "error_type": type(exc).__name__},
            )
            return JSONResponse(status_code=500, content={"detail": "Internal error"})
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    def enforce(principal_obj, requirement: AccessRequirement, matter_id: str | None = None) -> None:
        auth.enforce(principal_obj, requirement, matter_id)

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        database_ready = False
        audit_ready = False
        try:
            services.repo.counts()
            database_ready = True
            audit_ready = services.audit.verify()[0]
        except Exception:
            pass
        limitations: list[str] = []
        if importlib.util.find_spec("agents") is None:
            limitations.append("OpenAI Agents SDK not installed")
        if not settings.api_key_present:
            limitations.append("OPENAI_API_KEY not injected into this runtime")
        limitations.extend(settings.runtime_security_errors())
        if not settings.external_actions_enabled:
            limitations.append("External action execution disabled")
        if not audit_ready:
            limitations.append("Audit-chain verification failed")
        ready = (
            importlib.util.find_spec("agents") is not None
            and settings.api_key_present
            and database_ready
            and services.ledger.ready
            and services.vault.encryption_ready
            and (settings.auth_disabled_dev or bool(settings.jwt_secret))
            and audit_ready
        )
        return HealthResponse(
            status="ok" if ready else "degraded",
            version="2.0.0",
            sdk_installed=importlib.util.find_spec("agents") is not None,
            api_key_present=settings.api_key_present,
            database_ready=database_ready,
            proof_ledger_ready=services.ledger.ready,
            evidence_encryption_ready=services.vault.encryption_ready,
            authentication_ready=settings.auth_disabled_dev or bool(settings.jwt_secret),
            external_actions_enabled=settings.external_actions_enabled,
            durable_workflow_ready=database_ready,
            primary_model=settings.primary_model,
            limitations=limitations,
        )

    @app.post("/v2/evidence/ingest")
    async def ingest_evidence(request: EvidenceIngestRequest, p: Principal):
        enforce(p, AccessRequirement(roles=frozenset({"OWNER", "COUNSEL", "ANALYST"}), scopes=frozenset({"evidence:write"})), request.matter_id)
        evidence, hash_proof, injection_proof = services.vault.ingest(request, p.subject)
        return {
            "evidence": evidence.model_dump(mode="json"),
            "hash_proof_id": hash_proof,
            "prompt_injection_proof_id": injection_proof,
        }

    @app.get("/v2/evidence/{evidence_id}")
    async def get_evidence(evidence_id: str, p: Principal):
        evidence = services.vault.get(evidence_id)
        if evidence is None:
            raise HTTPException(status_code=404, detail="Evidence not found")
        enforce(p, AccessRequirement(roles=frozenset({"OWNER", "COUNSEL", "ANALYST", "AUDITOR", "READ_ONLY"}), scopes=frozenset({"evidence:read"})), evidence.matter_id)
        return evidence.model_dump(mode="json")

    @app.post("/v2/inventory")
    async def inventory(request: InventoryRequest, p: Principal):
        enforce(p, AccessRequirement(roles=frozenset({"OWNER", "COUNSEL", "ANALYST", "AUDITOR"}), scopes=frozenset({"evidence:read"})), request.matter_id)
        path = Path(request.path).expanduser().resolve()
        if not any(path == root or root in path.parents for root in settings.authorised_read_roots):
            raise HTTPException(status_code=400, detail="Path outside authorised roots")
        limits = InventoryLimits(
            max_file_bytes=settings.max_file_bytes,
            max_parts=settings.max_mime_parts,
            max_depth=settings.max_mime_depth,
            max_decoded_bytes=settings.max_decoded_bytes,
            max_zip_entries=settings.max_zip_entries,
            max_zip_expanded_bytes=settings.max_zip_expanded_bytes,
            max_zip_ratio=settings.max_zip_ratio,
        )
        result = inventory_path(
            path,
            application_visible_count=request.application_visible_count,
            application_attachment_count=request.application_attachment_count,
            application_inline_count=request.application_inline_count,
            limits=limits,
        )
        proof_id = append_inventory_proof(
            services.ledger,
            matter_id=request.matter_id,
            mission_id=request.mission_id,
            subject_id=request.subject_id,
            actor_id=p.subject,
            source_ids=request.source_ids,
            result=result,
        )
        return {"inventory": result.model_dump(mode="json"), "proof_id": proof_id}

    @app.get("/v2/proofs/verify/{matter_id}")
    async def verify_proofs(matter_id: str, p: Principal):
        enforce(p, AccessRequirement(roles=frozenset({"OWNER", "COUNSEL", "AUDITOR"}), scopes=frozenset({"proof:verify"})), matter_id)
        return services.ledger.verify_chain(matter_id).model_dump(mode="json")

    @app.post("/v2/claims")
    async def create_claim(request: ClaimCreateRequest, p: Principal):
        enforce(p, AccessRequirement(roles=frozenset({"OWNER", "COUNSEL", "ANALYST"}), scopes=frozenset({"claim:write"})), request.matter_id)
        return services.graph.create_claim(request).model_dump(mode="json")

    @app.post("/v2/claims/link")
    async def link_claim(request: ClaimLinkRequest, p: Principal):
        claim = services.graph.get_claim(request.claim_id)
        if claim is None:
            raise HTTPException(status_code=404, detail="Claim not found")
        enforce(p, AccessRequirement(roles=frozenset({"OWNER", "COUNSEL", "ANALYST"}), scopes=frozenset({"claim:write"})), claim.matter_id)
        return {"link_id": services.graph.link_claim(request)}

    @app.post("/v2/authorities")
    async def register_authority(request: AuthorityRegisterRequest, p: Principal):
        enforce(p, AccessRequirement(roles=frozenset({"OWNER", "COUNSEL", "ANALYST"}), scopes=frozenset({"authority:write"})), request.matter_id)
        authority, source_proof, law_proof = services.research.retrieve_and_register(request, p.subject)
        return {
            "authority": authority.model_dump(mode="json"),
            "source_read_proof_id": source_proof,
            "law_check_proof_id": law_proof,
        }

    @app.post("/v2/knowledge/ingest")
    async def ingest_knowledge(request: KnowledgeIngestRequest, p: Principal):
        enforce(p, AccessRequirement(roles=frozenset({"OWNER", "COUNSEL", "ANALYST"}), scopes=frozenset({"knowledge:write"})), request.matter_id)
        document_id, chunk_ids, proof_id = services.knowledge.ingest(
            authority_id=request.authority_id,
            matter_id=request.matter_id,
            mission_id=request.mission_id,
            actor_id=p.subject,
            text=request.text,
            metadata=request.metadata,
        )
        return {"document_id": document_id, "chunk_ids": chunk_ids, "proof_id": proof_id}

    @app.post("/v2/knowledge/search")
    async def search_knowledge(request: KnowledgeSearchRequest, p: Principal):
        enforce(p, AccessRequirement(roles=frozenset({"OWNER", "COUNSEL", "ANALYST", "AUDITOR", "READ_ONLY"}), scopes=frozenset({"knowledge:read"})), request.matter_id)
        return [hit.__dict__ for hit in services.knowledge.search(matter_id=request.matter_id, query=request.query, top_k=request.top_k)]

    @app.post("/v2/approvals")
    async def create_approval(request: ApprovalCreateRequest, p: Principal):
        enforce(p, AccessRequirement(roles=frozenset({"OWNER", "COUNSEL"}), scopes=frozenset({"approval:request"})), request.matter_id)
        return services.approvals.create(request).model_dump(mode="json")

    @app.post("/v2/approvals/{approval_id}/decision")
    async def decide_approval(approval_id: str, request: ApprovalDecisionRequest, p: Principal):
        approval = services.approvals.get(approval_id)
        if approval is None:
            raise HTTPException(status_code=404, detail="Approval not found")
        enforce(p, AccessRequirement(roles=frozenset({"OWNER"}), scopes=frozenset({"approval:decide"})), approval.matter_id)
        if request.decided_by != p.subject:
            raise HTTPException(status_code=400, detail="decided_by must match authenticated principal")
        record, proof_id = services.approvals.decide(approval_id, request)
        return {"approval": record.model_dump(mode="json"), "proof_id": proof_id}

    @app.post("/v2/actions/execute")
    async def execute_action(request: ActionExecuteRequest, p: Principal):
        approval = services.approvals.get(request.approval_id)
        if approval is None:
            raise HTTPException(status_code=404, detail="Approval not found")
        enforce(p, AccessRequirement(roles=frozenset({"OWNER", "CONNECTOR"}), scopes=frozenset({"action:execute"})), approval.matter_id)
        if request.executor_id != p.subject:
            raise HTTPException(status_code=400, detail="executor_id must match authenticated principal")
        try:
            return services.actions.execute(request).model_dump(mode="json")
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/v2/release", response_model=ReleaseResult)
    async def release(request: ReleaseRequest, p: Principal) -> ReleaseResult:
        enforce(p, AccessRequirement(roles=frozenset({"OWNER", "COUNSEL", "AUDITOR"}), scopes=frozenset({"release:evaluate"})), request.matter_id)
        return services.release_engine.evaluate(request, p.subject)

    @app.get("/v2/release/{release_receipt_id}")
    async def get_release(release_receipt_id: str, p: Principal):
        receipt = services.release_engine.get_receipt(release_receipt_id)
        if receipt is None:
            raise HTTPException(status_code=404, detail="Release receipt not found")
        enforce(p, AccessRequirement(roles=frozenset({"OWNER", "COUNSEL", "AUDITOR", "READ_ONLY"}), scopes=frozenset({"release:read"})), receipt["matter_id"])
        return receipt

    @app.post("/v2/workflows", response_model=WorkflowRecord)
    async def create_workflow(request: WorkflowCreateRequest, p: Principal) -> WorkflowRecord:
        enforce(p, AccessRequirement(roles=frozenset({"OWNER", "COUNSEL", "ANALYST"}), scopes=frozenset({"workflow:write"})), request.matter_id)
        return services.workflows.create(request, p.subject)

    @app.post("/v2/workflows/{workflow_id}/lease", response_model=WorkflowRecord)
    async def lease_workflow(workflow_id: str, request: WorkflowLeaseRequest, p: Principal) -> WorkflowRecord:
        record = services.workflows.get(workflow_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Workflow not found")
        enforce(p, AccessRequirement(roles=frozenset({"OWNER", "COUNSEL", "ANALYST", "CONNECTOR"}), scopes=frozenset({"workflow:execute"})), record.matter_id)
        return services.workflows.lease(workflow_id, request.worker_id, request.lease_seconds)

    @app.post("/v2/workflows/{workflow_id}/state", response_model=WorkflowRecord)
    async def update_workflow(workflow_id: str, request: WorkflowStateRequest, p: Principal) -> WorkflowRecord:
        record = services.workflows.get(workflow_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Workflow not found")
        enforce(p, AccessRequirement(roles=frozenset({"OWNER", "COUNSEL", "ANALYST", "CONNECTOR"}), scopes=frozenset({"workflow:execute"})), record.matter_id)
        return services.workflows.update_state(workflow_id, request.worker_id, request.state)

    @app.post("/v2/workflows/{workflow_id}/fail", response_model=WorkflowRecord)
    async def fail_workflow(workflow_id: str, request: WorkflowFailureRequest, p: Principal) -> WorkflowRecord:
        record = services.workflows.get(workflow_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Workflow not found")
        enforce(p, AccessRequirement(roles=frozenset({"OWNER", "COUNSEL", "ANALYST", "CONNECTOR"}), scopes=frozenset({"workflow:execute"})), record.matter_id)
        return services.workflows.fail(workflow_id, request.worker_id, request.error, request.retry_delay_seconds)

    @app.post("/v2/backups")
    async def create_backup(request: BackupCreateRequest, p: Principal):
        enforce(p, AccessRequirement(roles=frozenset({"OWNER", "AUDITOR"}), scopes=frozenset({"backup:create"})), request.matter_id)
        return services.backup.create_snapshot(
            matter_id=request.matter_id,
            mission_id=request.mission_id,
            actor_id=p.subject,
            destination=Path(request.destination),
        )

    @app.post("/v2/backups/restore-canary")
    async def restore_canary(request: RestoreCanaryRequest, p: Principal):
        enforce(p, AccessRequirement(roles=frozenset({"OWNER", "AUDITOR"}), scopes=frozenset({"backup:restore-test"})), request.matter_id)
        proof_id = services.backup.restore_canary(
            matter_id=request.matter_id,
            mission_id=request.mission_id,
            actor_id=p.subject,
            snapshot_dir=Path(request.snapshot_dir),
        )
        return {"proof_id": proof_id, "status": "RESTORE_CANARY_PASSED"}

    @app.post("/v2/council/decide", response_model=CouncilDecision)
    async def council_decide(request: CouncilDecisionRequest, p: Principal) -> CouncilDecision:
        enforce(p, AccessRequirement(roles=frozenset({"OWNER", "COUNSEL", "AUDITOR"}), scopes=frozenset({"council:evaluate"})), request.matter_id)
        return services.council.decide(request, p.subject)

    @app.post("/v2/missions", response_model=MissionResponse)
    async def mission(request: MissionRequest, p: Principal) -> MissionResponse:
        enforce(p, AccessRequirement(roles=frozenset({"OWNER", "COUNSEL", "ANALYST"}), scopes=frozenset({"mission:run"})), request.matter_id)
        return await runtime.run(request)

    return app
