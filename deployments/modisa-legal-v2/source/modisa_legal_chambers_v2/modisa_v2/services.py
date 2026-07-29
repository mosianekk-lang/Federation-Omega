from __future__ import annotations

from dataclasses import dataclass

from .actions import ActionService
from .approvals import ApprovalService
from .audit import AuditLog
from .backup import BackupService
from .config import Settings
from .connectors import ConnectorRegistry
from .council import CouncilEngine
from .db import Repository
from .evidence_vault import EvidenceVault
from .legal_graph import LegalGraph
from .knowledge import LegalKnowledgePlane
from .proof_ledger import ProofLedger
from .proof_services import DeterministicProofServices
from .release_engine import ProofBoundReleaseEngine
from .research import PrimaryLawResearchService
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


def build_services(settings: Settings) -> Services:
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
    )
