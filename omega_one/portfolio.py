"""Omega-One v0.8.4 100-capability blueprint maturity baseline.

This module is an index/compilation layer, not a substitute for the full Master Blueprint.
It preserves all 100 capability identities and their target modules while compiling only
proof that is individually supported. Portfolio/package evidence is retained separately
and may not promote every capability by inheritance.

Zero-dilution invariant: every capability remains PRESERVED_FULL_CAPABILITY even when
its execution or maturity is held. A hold governs use/claim state, never deletion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .maturity import CapabilityRecord, MaturityStage, ProofClaim

BLUEPRINT_SOURCE_REF = "uploaded:Omega-One — 100 System Capability Upgrades & Master Implementation Blueprint.docx"
STARTUP_REGISTER_SOURCE_REF = "uploaded:Federation Omega Startup Register v1.xlsx"

BLUEPRINT_CAPABILITIES = (
    ('CAP-001', 1, 'Distributed FMEC Lease Fencing', 'kernel.fmec', 1, 'Core Kernel & Sovereign Invariants'),
    ('CAP-002', 2, 'Zero-Case-Data Leakage Boundary', 'security.airlock', 1, 'Core Kernel & Sovereign Invariants'),
    ('CAP-003', 3, '20-Invariant Runtime Court', 'kernel.invariants', 1, 'Core Kernel & Sovereign Invariants'),
    ('CAP-004', 4, 'Monotonic Version Lineage Guard', 'kernel.lineage', 1, 'Core Kernel & Sovereign Invariants'),
    ('CAP-005', 5, 'Consequence Gatekeeper', 'governance.consequence', 1, 'Core Kernel & Sovereign Invariants'),
    ('CAP-006', 6, 'Dual-State Namespace Isolator', 'runtime.isolation', 1, 'Core Kernel & Sovereign Invariants'),
    ('CAP-007', 7, 'Reversible State Transaction Engine', 'recovery.transaction', 1, 'Core Kernel & Sovereign Invariants'),
    ('CAP-008', 8, 'Keyless Ephemeral Identity Authenticator', 'auth.ephemeral', 1, 'Core Kernel & Sovereign Invariants'),
    ('CAP-009', 9, 'Failsafe Crash Recovery Horizon', 'recovery.horizon', 1, 'Core Kernel & Sovereign Invariants'),
    ('CAP-010', 10, 'Single Point of Failure (SPOF) Eliminator', 'resilience.spof', 1, 'Core Kernel & Sovereign Invariants'),
    ('CAP-011', 11, '24-Registry Automated Delta Poller', 'discovery.poller', 2, 'Global Capability Discovery & Sourcing'),
    ('CAP-012', 12, 'Semantic Signal-to-Noise Filter', 'discovery.filter', 2, 'Global Capability Discovery & Sourcing'),
    ('CAP-013', 13, 'Automated Supply Chain Vulnerability Scanner', 'security.supplychain', 2, 'Global Capability Discovery & Sourcing'),
    ('CAP-014', 14, 'Open-Source License Provenance Classifier', 'compliance.license', 2, 'Global Capability Discovery & Sourcing'),
    ('CAP-015', 15, 'GitHub Commit Velocity & Health Tracker', 'metrics.velocity', 2, 'Global Capability Discovery & Sourcing'),
    ('CAP-016', 16, 'Multi-Registry Deduplication Matrix', 'discovery.dedupe', 2, 'Global Capability Discovery & Sourcing'),
    ('CAP-017', 17, 'Changelog & Breaking Change Extractor', 'discovery.changelog', 2, 'Global Capability Discovery & Sourcing'),
    ('CAP-018', 18, 'Synthetic Documentation Harvester', 'discovery.harvester', 2, 'Global Capability Discovery & Sourcing'),
    ('CAP-019', 19, 'Frontier Emergence Trend Predictor', 'discovery.predictor', 2, 'Global Capability Discovery & Sourcing'),
    ('CAP-020', 20, 'Airgapped Ingestion Buffer', 'security.airgap', 2, 'Global Capability Discovery & Sourcing'),
    ('CAP-021', 21, '14-Stage Structural Archaeology Court', 'archaeology.court', 3, 'Deep Archaeology & Mechanism Assimilation'),
    ('CAP-022', 22, 'AST-Based Logic Gene Extractor', 'archaeology.ast', 3, 'Deep Archaeology & Mechanism Assimilation'),
    ('CAP-023', 23, 'Clean-Room Native Gene Re-implementer', 'archaeology.reimplement', 3, 'Deep Archaeology & Mechanism Assimilation'),
    ('CAP-024', 24, 'Universal Capability Contract (UCC) Auto-Generator', 'contract.ucc', 3, 'Deep Archaeology & Mechanism Assimilation'),
    ('CAP-025', 25, 'Interface Drift & Compatibility Detector', 'contract.drift', 3, 'Deep Archaeology & Mechanism Assimilation'),
    ('CAP-026', 26, 'Microbenchmark Sandbox Generator', 'benchmark.sandbox', 3, 'Deep Archaeology & Mechanism Assimilation'),
    ('CAP-027', 27, 'Memory & Resource Leak Profiler', 'benchmark.profiler', 3, 'Deep Archaeology & Mechanism Assimilation'),
    ('CAP-028', 28, 'Static Malice & Obfuscation Scanner', 'security.staticscan', 3, 'Deep Archaeology & Mechanism Assimilation'),
    ('CAP-029', 29, 'Selective Corpus Document Slicer', 'corpus.slicer', 3, 'Deep Archaeology & Mechanism Assimilation'),
    ('CAP-030', 30, 'Reusable Engineering Gene Catalog', 'genome.catalog', 3, 'Deep Archaeology & Mechanism Assimilation'),
    ('CAP-031', 31, 'OpenAPI 3.1 to Contract Compiler', 'adapter.openapi', 4, 'Schema-First Adapter & Integration Mesh'),
    ('CAP-032', 32, 'GraphQL & gRPC Schema Normalizer', 'adapter.graphql', 4, 'Schema-First Adapter & Integration Mesh'),
    ('CAP-033', 33, 'Secret Field Sanitizer & Credential Stripper', 'security.sanitizer', 4, 'Schema-First Adapter & Integration Mesh'),
    ('CAP-034', 34, 'Multi-Step Complex Auth Handler', 'auth.multistep', 4, 'Schema-First Adapter & Integration Mesh'),
    ('CAP-035', 35, 'Dynamic Payload & Type Validator', 'contract.validator', 4, 'Schema-First Adapter & Integration Mesh'),
    ('CAP-036', 36, 'Adaptive Rate-Limit & Backoff Controller', 'mesh.ratelimit', 4, 'Schema-First Adapter & Integration Mesh'),
    ('CAP-037', 37, 'Synthetic API Mock Response Generator', 'mesh.mocker', 4, 'Schema-First Adapter & Integration Mesh'),
    ('CAP-038', 38, 'Asynchronous Webhook Ingestion Listener', 'mesh.webhook', 4, 'Schema-First Adapter & Integration Mesh'),
    ('CAP-039', 39, 'Streaming to Batch Chunk Transformer', 'mesh.streamer', 4, 'Schema-First Adapter & Integration Mesh'),
    ('CAP-040', 40, 'API Version Evolution Tracker', 'mesh.versioning', 4, 'Schema-First Adapter & Integration Mesh'),
    ('CAP-041', 41, 'Ω-Scientist Autonomous Hypothesis Generator', 'scientist.hypothesis', 5, 'Scientific Evolution & Epistemic Governance'),
    ('CAP-042', 42, 'Causal Knowledge Graph & Edge Weighting Kernel', 'scientist.causal', 5, 'Scientific Evolution & Epistemic Governance'),
    ('CAP-043', 43, 'Epistemic Debt & Knowledge Gap Calculator', 'scientist.epistemic', 5, 'Scientific Evolution & Epistemic Governance'),
    ('CAP-044', 44, 'Negative Result & Falsification Ledger', 'scientist.negative', 5, 'Scientific Evolution & Epistemic Governance'),
    ('CAP-045', 45, 'Champion-Challenger Tournament Evaluator', 'scientist.tournament', 5, 'Scientific Evolution & Epistemic Governance'),
    ('CAP-046', 46, 'Multi-Variable Parameter Perturbation Engine', 'scientist.perturbation', 5, 'Scientific Evolution & Epistemic Governance'),
    ('CAP-047', 47, 'Empirical Convergence & Hallucination Suppressor', 'scientist.convergence', 5, 'Scientific Evolution & Epistemic Governance'),
    ('CAP-048', 48, 'Automated Premortem & Postmortem Classifier', 'scientist.postmortem', 5, 'Scientific Evolution & Epistemic Governance'),
    ('CAP-049', 49, 'Curiosity Graph & Information Gain Maximizer', 'scientist.curiosity', 5, 'Scientific Evolution & Epistemic Governance'),
    ('CAP-050', 50, 'Scientific Confidence Envelope & Certainty Scorer', 'scientist.confidence', 5, 'Scientific Evolution & Epistemic Governance'),
    ('CAP-051', 51, 'Forest-First Cognitive Demand Classifier', 'mesh.classifier', 6, 'Multi-Model Orchestration & Forest-First Mesh'),
    ('CAP-052', 52, 'Dynamic Multi-Model Router', 'mesh.router', 6, 'Multi-Model Orchestration & Forest-First Mesh'),
    ('CAP-053', 53, 'OpenRouter Pinned-Proof Shadow Client', 'mesh.openrouter', 6, 'Multi-Model Orchestration & Forest-First Mesh'),
    ('CAP-054', 54, 'Multi-Provider Fallback Circuit Breaker', 'mesh.circuitbreaker', 6, 'Multi-Model Orchestration & Forest-First Mesh'),
    ('CAP-055', 55, 'FOCUS 1.4 Cost & Token Normalizer', 'finops.focus', 6, 'Multi-Model Orchestration & Forest-First Mesh'),
    ('CAP-056', 56, 'Model Output Divergence Cross-Examiner', 'mesh.discrepancy', 6, 'Multi-Model Orchestration & Forest-First Mesh'),
    ('CAP-057', 57, 'Speculative Parallel Stream Evaluator', 'mesh.speculative', 6, 'Multi-Model Orchestration & Forest-First Mesh'),
    ('CAP-058', 58, 'Privacy-Preserving PII & Token Stripper', 'privacy.redaction', 6, 'Multi-Model Orchestration & Forest-First Mesh'),
    ('CAP-059', 59, 'Semantic Context Compactor', 'mesh.compactor', 6, 'Multi-Model Orchestration & Forest-First Mesh'),
    ('CAP-060', 60, 'Multi-Agent Consensus Arbiter', 'mesh.consensus', 6, 'Multi-Model Orchestration & Forest-First Mesh'),
    ('CAP-061', 61, 'Content-Addressed Store (CAS) with SHA-256 Deduplication', 'storage.cas', 7, 'Sovereign Recovery Fabric & Backup (R0–R6)'),
    ('CAP-062', 62, 'R0–R6 Recovery Readiness State Machine', 'recovery.r6', 7, 'Sovereign Recovery Fabric & Backup (R0–R6)'),
    ('CAP-063', 63, 'Cross-Provider Backup Replicator', 'storage.crosscloud', 7, 'Sovereign Recovery Fabric & Backup (R0–R6)'),
    ('CAP-064', 64, 'Atomic Release Promotion Gate', 'release.atomicgate', 7, 'Sovereign Recovery Fabric & Backup (R0–R6)'),
    ('CAP-065', 65, 'Automated Disaster Recovery Simulation Court', 'recovery.drill', 7, 'Sovereign Recovery Fabric & Backup (R0–R6)'),
    ('CAP-066', 66, 'Append-Only Heritage Provenance Vault', 'storage.heritage', 7, 'Sovereign Recovery Fabric & Backup (R0–R6)'),
    ('CAP-067', 67, 'Self-Extracting Offline Snapshot Bundler', 'storage.snapshot', 7, 'Sovereign Recovery Fabric & Backup (R0–R6)'),
    ('CAP-068', 68, 'Continuous State Micro-Checkpointer', 'recovery.microcheckpoint', 7, 'Sovereign Recovery Fabric & Backup (R0–R6)'),
    ('CAP-069', 69, 'Stale-Writer Document Collision Sentinel', 'concurrency.sentinel', 7, 'Sovereign Recovery Fabric & Backup (R0–R6)'),
    ('CAP-070', 70, 'Cloud-Agnostic Container Builder', 'deploy.container', 7, 'Sovereign Recovery Fabric & Backup (R0–R6)'),
    ('CAP-071', 71, '59-Section Traceability & Evidence Verifier', 'ao5.traceability', 8, 'JARVIS ΑΩ5 Forensic Decision & Evidence DAG'),
    ('CAP-072', 72, 'Bidirectional Decision Directed Acyclic Graph (DAG)', 'ao5.dag', 8, 'JARVIS ΑΩ5 Forensic Decision & Evidence DAG'),
    ('CAP-073', 73, 'Multidimensional Evidence Quality Vector (EQV)', 'ao5.eqv', 8, 'JARVIS ΑΩ5 Forensic Decision & Evidence DAG'),
    ('CAP-074', 74, 'Contradiction Gravity & Conflict Resolver', 'ao5.gravity', 8, 'JARVIS ΑΩ5 Forensic Decision & Evidence DAG'),
    ('CAP-075', 75, 'Five-Angle Adversarial Council', 'ao5.council', 8, 'JARVIS ΑΩ5 Forensic Decision & Evidence DAG'),
    ('CAP-076', 76, 'Replayable Decision Lineage Audit Trail', 'ao5.replay', 8, 'JARVIS ΑΩ5 Forensic Decision & Evidence DAG'),
    ('CAP-077', 77, 'Temporal State & Timeline Discrepancy Engine', 'ao5.timeline', 8, 'JARVIS ΑΩ5 Forensic Decision & Evidence DAG'),
    ('CAP-078', 78, 'Institutional Accountability & SPOF Mapper', 'ao5.accountability', 8, 'JARVIS ΑΩ5 Forensic Decision & Evidence DAG'),
    ('CAP-079', 79, 'Neutral Arbiter Bias Filter', 'ao5.biasfilter', 8, 'JARVIS ΑΩ5 Forensic Decision & Evidence DAG'),
    ('CAP-080', 80, 'RealityGuard Execution Receipt Verifier', 'ao5.realityguard', 8, 'JARVIS ΑΩ5 Forensic Decision & Evidence DAG'),
    ('CAP-081', 81, 'Apps Script (GAS) Authority Gateway & Queue', 'workspace.gas', 9, 'Workspace Automation & Operating Surface'),
    ('CAP-082', 82, 'Multi-Tab Command & Control Spreadsheet Sync', 'workspace.sheets', 9, 'Workspace Automation & Operating Surface'),
    ('CAP-083', 83, 'Automated Evidence Dossier Filer', 'workspace.drive', 9, 'Workspace Automation & Operating Surface'),
    ('CAP-084', 84, 'Smart Gmail Thread Classifier & Action Extractor', 'workspace.gmail', 9, 'Workspace Automation & Operating Surface'),
    ('CAP-085', 85, 'Calendar Meeting & Preparation Orchestrator', 'workspace.calendar', 9, 'Workspace Automation & Operating Surface'),
    ('CAP-086', 86, 'Real-Time Chat Notification & Alert Filter', 'workspace.chat', 9, 'Workspace Automation & Operating Surface'),
    ('CAP-087', 87, 'Power Automate Multi-Cloud Bridge', 'workspace.powerautomate', 9, 'Workspace Automation & Operating Surface'),
    ('CAP-088', 88, 'Live System Telemetry & Health Dashboard', 'workspace.telemetry', 9, 'Workspace Automation & Operating Surface'),
    ('CAP-089', 89, 'Audio Hearing & Interview Diarization Parser', 'workspace.transcription', 9, 'Workspace Automation & Operating Surface'),
    ('CAP-090', 90, 'Low-Bandwidth Mobile Status Surface', 'workspace.mobile', 9, 'Workspace Automation & Operating Surface'),
    ('CAP-091', 91, 'Labor Law & Disciplinary Compliance Auditor', 'legal.lra', 10, 'Enterprise Strategy, Case Law & Growth'),
    ('CAP-092', 92, 'Forensic Case Transcript Cross-Correlator', 'legal.transcript', 10, 'Enterprise Strategy, Case Law & Growth'),
    ('CAP-093', 93, 'Institutional Policy Conflict Detector', 'legal.policy', 10, 'Enterprise Strategy, Case Law & Growth'),
    ('CAP-094', 94, 'Protected Disclosure & Grievance Milestone Tracker', 'legal.grievance', 10, 'Enterprise Strategy, Case Law & Growth'),
    ('CAP-095', 95, 'Job Evaluation & Workload Structure Modeler', 'legal.jobgrade', 10, 'Enterprise Strategy, Case Law & Growth'),
    ('CAP-096', 96, 'Cryptocurrency Strategy Backtester & Risk Guard (Luno)', 'fintech.luno', 10, 'Enterprise Strategy, Case Law & Growth'),
    ('CAP-097', 97, 'Drone Flight Telemetry & Mapping Pipeline', 'iot.drone', 10, 'Enterprise Strategy, Case Law & Growth'),
    ('CAP-098', 98, 'Intellectual Property & Platform Gene Catalog', 'ip.catalog', 10, 'Enterprise Strategy, Case Law & Growth'),
    ('CAP-099', 99, 'Zero-Loss Autonomous Session Handoff Manager', 'continuity.handoff', 10, 'Enterprise Strategy, Case Law & Growth'),
    ('CAP-100', 100, 'Founder Plain-Language Strategic Synthesizer', 'strategy.briefing', 10, 'Enterprise Strategy, Case Law & Growth'),
)

PORTFOLIO_EVIDENCE = (
    {
        "ref": BLUEPRINT_SOURCE_REF,
        "supports": ("100 capability identities", "10 domains", "target modules", "architecture design"),
        "does_not_support": ("provider execution of all 100", "value verification of all 100"),
    },
    {
        "ref": STARTUP_REGISTER_SOURCE_REF + ":Startup_Index!A18:J18",
        "supports": ("historical 100-candidate registry", "100 unique candidates"),
        "does_not_support": ("100 capabilities deployed",),
        "recorded_status": "STATIC_CANDIDATE_REGISTRY_TESTED / NO_100_CAPABILITIES_DEPLOYED",
        "proof_state": "5_REGISTRY_TESTS / 100_UNIQUE_CANDIDATES",
    },
    {
        "ref": STARTUP_REGISTER_SOURCE_REF + ":Startup_Index!A31:J31",
        "supports": ("100-improvement staged master package", "16/16 hermetic package unit tests"),
        "does_not_support": ("individual provider maturity for every capability", "automatic live activation of every capability"),
        "recorded_status": "MASTER_PACKAGE_DEPLOYED_STAGED",
        "proof_state": "16_OF_16_UNIT_TESTS_PASS",
    },
)

INDIVIDUAL_PROOF = {
    "CAP-031": (
        ProofClaim(MaturityStage.SOURCE_IMPLEMENTED, True, (
            "Omega-One v0.8.3 clean-room schema compiler candidate",
            "sha256:0761bb4fe09787f0d501f62dc67ffd6f4e3ac61c2a04149bd7983b0c994c16b4",
        )),
        ProofClaim(MaturityStage.DETERMINISTIC_TESTED, True, (
            "v0.8.3 dedicated schema compiler court 15/15 PASS",
            "v0.8.3 restored full suite 446/446 PASS",
        )),
    ),
    "CAP-033": (
        ProofClaim(MaturityStage.SOURCE_IMPLEMENTED, True, (
            "Omega-One v0.8.3 schema sensitive-field sanitization implementation",
        )),
        ProofClaim(MaturityStage.DETERMINISTIC_TESTED, True, (
            "v0.8.3 schema secret/default/example sanitization court PASS",
        )),
    ),
}

CAPABILITY_HOLDS = {
    "CAP-034": (
        "v0.8.3 deliberately held OAuth2/OpenID Connect/mTLS for purpose-built adapters; no generic-auth maturity inheritance",
    ),
}


@dataclass(frozen=True)
class BlueprintCapability:
    capability_id: str
    upgrade: int
    name: str
    target_module: str
    domain_number: int
    domain_name: str
    preservation_state: str = "PRESERVED_FULL_CAPABILITY"
    zero_dilution: bool = True
    holds: tuple[str, ...] = ()


def blueprint_capabilities() -> tuple[BlueprintCapability, ...]:
    return tuple(
        BlueprintCapability(
            capability_id=capability_id,
            upgrade=upgrade,
            name=name,
            target_module=target_module,
            domain_number=domain_number,
            domain_name=domain_name,
            holds=tuple(CAPABILITY_HOLDS.get(capability_id, ())),
        )
        for capability_id, upgrade, name, target_module, domain_number, domain_name in BLUEPRINT_CAPABILITIES
    )


def maturity_records() -> tuple[CapabilityRecord, ...]:
    """Build 100 conservative records without umbrella maturity inheritance."""
    records = []
    for capability in blueprint_capabilities():
        claims = [
            ProofClaim(
                MaturityStage.DESIGNED,
                True,
                (BLUEPRINT_SOURCE_REF,),
                "Capability identity and target module are explicitly present in the Master Blueprint.",
            )
        ]
        claims.extend(INDIVIDUAL_PROOF.get(capability.capability_id, ()))
        records.append(
            CapabilityRecord(
                capability_id=capability.capability_id,
                name=capability.name,
                domain=capability.domain_name,
                claims=tuple(claims),
                declared_status="ARCHITECTURE_AVAILABLE",
                metadata={
                    "target_module": capability.target_module,
                    "upgrade": str(capability.upgrade),
                    "domain_number": str(capability.domain_number),
                    "preservation_state": capability.preservation_state,
                    "zero_dilution": str(capability.zero_dilution).lower(),
                    "holds": " | ".join(capability.holds),
                },
            )
        )
    return tuple(records)


def validate_blueprint_baseline(records: Iterable[CapabilityRecord] | None = None) -> dict[str, object]:
    records = tuple(records or maturity_records())
    ids = tuple(record.capability_id for record in records)
    expected = tuple(f"CAP-{i:03d}" for i in range(1, 101))
    return {
        "record_count": len(records),
        "unique_id_count": len(set(ids)),
        "ids_exact": ids == expected,
        "all_zero_dilution": all(record.metadata.get("zero_dilution") == "true" for record in records),
        "all_preserved": all(record.metadata.get("preservation_state") == "PRESERVED_FULL_CAPABILITY" for record in records),
        "portfolio_evidence_count": len(PORTFOLIO_EVIDENCE),
    }
