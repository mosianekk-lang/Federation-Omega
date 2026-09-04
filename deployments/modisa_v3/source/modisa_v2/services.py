from __future__ import annotations

import time
from dataclasses import dataclass
from typing import cast

from .actions import ActionService
from .adapters.cognitive_binding import CognitiveBindingAdapter
from .approvals import ApprovalService
from .audit import AuditLog
from .backup import BackupService
from .config import Settings
from .connectors import ConnectorRegistry
from .council import CouncilEngine
from .db import Repository
from .evidence_vault import EvidenceVault
from .knowledge import LegalKnowledgePlane
from .legal_graph import LegalGraph
from .nonce_stores import (
    BackendStatus,
    NonceStore,
    NonceStoreKind,
    ReplayScope,
    SQLiteNonceStore,
    build_redis_nonce_store,
)
from .proof_ledger import ProofLedger
from .proof_services import DeterministicProofServices
from .release_engine import ProofBoundReleaseEngine
from .research import PrimaryLawResearchService
from .secret_resolvers import GoogleSecretManagerResolver
from .webhook_auth import (
    EnvironmentSecretResolver,
    SecretReference,
    SecretResolver,
    WebhookAuthenticator,
    WebhookAuthPolicy,
)
from .workflow import DurableWorkflowStore


@dataclass
class Services:
    settings: Settings
    repo: Repository
    audit: AuditLog
    ledger: ProofLedger
    graph: LegalGraph
    knowledge: LegalKnowledgePlane
    vault: EvidenceVault
    proof_services: DeterministicProofServices
    research: PrimaryLawResearchService
    approvals: ApprovalService
    connectors: ConnectorRegistry
    actions: ActionService
    workflows: DurableWorkflowStore
    backup: BackupService
    council: CouncilEngine
    release_engine: ProofBoundReleaseEngine
    cognitive_binding: CognitiveBindingAdapter
    webhook_authenticator: WebhookAuthenticator | None
    webhook_secret_resolver_kind: str
    webhook_secret_provider_proven: bool
    webhook_nonce_store_kind: NonceStoreKind
    webhook_replay_scope: ReplayScope
    webhook_nonce_backend_configured: bool
    webhook_nonce_backend_proven: bool
    webhook_nonce_backend_status: BackendStatus


def build_services(
    settings: Settings,
    *,
    webhook_secret_resolver: SecretResolver | None = None,
    webhook_nonce_store: NonceStore | None = None,
) -> Services:
    settings.ensure_directories()
    repo = Repository(settings.database_path)
    audit = AuditLog(repo)
    ledger = ProofLedger(repo, settings.ledger_hmac_key)
    graph = LegalGraph(repo)
    knowledge = LegalKnowledgePlane(repo, graph, ledger)
    vault = EvidenceVault(settings, repo, ledger)
    proof_services = DeterministicProofServices(graph, ledger)
    research = PrimaryLawResearchService(graph, ledger)
    approvals = ApprovalService(repo, ledger, audit)
    connectors = ConnectorRegistry(repo, ledger)
    actions = ActionService(
        repo,
        ledger,
        approvals,
        audit,
        connectors,
        enabled=settings.external_actions_enabled,
    )
    workflows = DurableWorkflowStore(repo, audit)
    backup = BackupService(repo, ledger, audit)
    council = CouncilEngine(repo, ledger)
    release_engine = ProofBoundReleaseEngine(repo, ledger, graph)
    cognitive_binding = CognitiveBindingAdapter(ledger)
    webhook_authenticator: WebhookAuthenticator | None = None
    webhook_secret_resolver_kind = "none"  # noqa: S105 -- readiness label, not a secret
    webhook_secret_provider_proven = False
    webhook_nonce_store_kind: NonceStoreKind = settings.webhook_nonce_store
    webhook_replay_scope: ReplayScope = (
        "shared_redis" if settings.webhook_nonce_store == "redis" else "node_local_sqlite"
    )
    webhook_nonce_backend_configured = False
    webhook_nonce_backend_proven = False
    webhook_nonce_backend_status: BackendStatus = "unconfigured"
    if settings.webhook_auth_configured and settings.webhook_auth_secret_ref is not None:
        reference = SecretReference.parse(settings.webhook_auth_secret_ref)
        resolver = webhook_secret_resolver
        if resolver is None and reference.scheme == "env":
            resolver = EnvironmentSecretResolver()
        elif resolver is None and reference.scheme == "gcp-secret":
            resolver = GoogleSecretManagerResolver(
                allowed_resource=reference.identifier,
                timeout_seconds=settings.webhook_secret_timeout_seconds,
            )
            resolver.resolve(reference)
        elif resolver is None:
            raise ValueError("Configured webhook secret reference has no resolver")
        webhook_secret_resolver_kind = str(getattr(resolver, "kind", "injected"))
        webhook_secret_provider_proven = bool(getattr(resolver, "provider_proven", False))
        nonce_store = webhook_nonce_store
        if nonce_store is None and settings.webhook_nonce_store == "redis":
            nonce_store = build_redis_nonce_store(settings, now=int(time.time()))
        elif nonce_store is None:
            nonce_store = SQLiteNonceStore(settings.webhook_nonce_db)
        assert nonce_store is not None
        observed_kind = getattr(nonce_store, "kind", "injected")
        webhook_nonce_store_kind = (
            cast(NonceStoreKind, observed_kind)
            if observed_kind in ("sqlite", "redis", "injected")
            else "injected"
        )
        observed_scope = getattr(nonce_store, "replay_scope", "node_local_sqlite")
        webhook_replay_scope = (
            cast(ReplayScope, observed_scope)
            if observed_scope in ("node_local_sqlite", "shared_redis")
            else "node_local_sqlite"
        )
        webhook_nonce_backend_configured = bool(
            getattr(nonce_store, "backend_configured", True)
        )
        webhook_nonce_backend_proven = bool(getattr(nonce_store, "provider_proven", False))
        observed_status = getattr(nonce_store, "backend_status", "unproven")
        webhook_nonce_backend_status = (
            cast(BackendStatus, observed_status)
            if observed_status in ("unconfigured", "unproven", "ready", "unavailable")
            else "unavailable"
        )
        webhook_authenticator = WebhookAuthenticator(
            WebhookAuthPolicy(
                key_id=settings.webhook_auth_key_id,
                secret_ref=settings.webhook_auth_secret_ref,
                max_clock_skew_seconds=settings.webhook_max_clock_skew_seconds,
            ),
            resolver,
            nonce_store,
        )
    return Services(
        settings=settings,
        repo=repo,
        audit=audit,
        ledger=ledger,
        graph=graph,
        knowledge=knowledge,
        vault=vault,
        proof_services=proof_services,
        research=research,
        approvals=approvals,
        connectors=connectors,
        actions=actions,
        workflows=workflows,
        backup=backup,
        council=council,
        release_engine=release_engine,
        cognitive_binding=cognitive_binding,
        webhook_authenticator=webhook_authenticator,
        webhook_secret_resolver_kind=webhook_secret_resolver_kind,
        webhook_secret_provider_proven=webhook_secret_provider_proven,
        webhook_nonce_store_kind=webhook_nonce_store_kind,
        webhook_replay_scope=webhook_replay_scope,
        webhook_nonce_backend_configured=webhook_nonce_backend_configured,
        webhook_nonce_backend_proven=webhook_nonce_backend_proven,
        webhook_nonce_backend_status=webhook_nonce_backend_status,
    )
