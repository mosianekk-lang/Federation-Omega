from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class BenchmarkDimension:
    dimension_id: str
    name: str
    weight: float
    current_score: float
    target_score: float
    evidence_state: str
    rationale: str

    def validate(self) -> "BenchmarkDimension":
        if not 0 < self.weight:
            raise ValueError("weight must be positive")
        for field_name, value in (("current_score", self.current_score), ("target_score", self.target_score)):
            if not 0 <= value <= 10:
                raise ValueError(f"{field_name} must be in [0,10]")
        if self.target_score < self.current_score:
            raise ValueError("target score cannot be below current score")
        return self


@dataclass(frozen=True, slots=True)
class CapabilityGene:
    gene_id: str
    name: str
    pattern_source: str
    current_state: str
    priority: str
    target_contract: str
    reuse_first: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    schema: str
    architecture_score: float
    target_score: float
    proof_adjusted_operational_score: float
    gap: float
    hard_gates: tuple[str, ...]
    dimensions: tuple[BenchmarkDimension, ...]
    genes: tuple[CapabilityGene, ...]


DIMENSIONS: tuple[BenchmarkDimension, ...] = (
    BenchmarkDimension("MEM-01", "immutable event truth", 1.4, 8.5, 9.8, "STRONG_FRAGMENTED", "Append-only ledgers and hash-chain semantic memory exist, but no single Federation-wide event store is authoritative."),
    BenchmarkDimension("MEM-02", "current verified projections", 1.3, 7.0, 9.7, "STRONG_MANUAL_DRIFT", "KDV projection rules are strong, but current-state rows still drift and require manual reconciliation."),
    BenchmarkDimension("MEM-03", "human-readable Bible projections", 0.8, 9.0, 9.6, "STRONG", "Canonical Bibles are rich human-readable knowledge surfaces."),
    BenchmarkDimension("MEM-04", "directive and mission lineage", 1.1, 7.0, 9.7, "PARTIAL", "Directives, missions and checkpoints exist across multiple ledgers but are not one typed lineage graph."),
    BenchmarkDimension("MEM-05", "durable workflow history and replay", 1.3, 6.0, 9.5, "PARTIAL", "ChatBridge and checkpoints provide continuity, but durable workflow execution history is not a universal substrate."),
    BenchmarkDimension("MEM-06", "write-ahead checkpoint and restore", 1.1, 8.0, 9.7, "STRONG_BOUNDED", "ChatBridge CEG/LBS controls are mature at bounded source/readback scope."),
    BenchmarkDimension("MEM-07", "conflict, correction and supersession", 1.1, 9.0, 9.8, "STRONG", "Conflict Queue, supersession and historical preservation are explicit Federation laws."),
    BenchmarkDimension("MEM-08", "provenance and attestation", 1.2, 8.3, 9.8, "STRONG", "Hashes, receipts, source/version boundaries and proof references are strong; build-style attestation can be made uniform."),
    BenchmarkDimension("MEM-09", "idempotency and optimistic concurrency", 1.2, 7.3, 9.8, "PARTIAL_STRONG", "Multiple idempotency controls exist; universal durable stream-version enforcement is still absent."),
    BenchmarkDimension("MEM-10", "schema registry and event evolution", 1.0, 6.2, 9.5, "PARTIAL", "KDV schemas and instrument replay exist, but event upcasting/backward-compatible replay are not one standard."),
    BenchmarkDimension("MEM-11", "bitemporal valid-time and system-time state", 1.2, 4.5, 9.5, "GAP", "Event-date and observed-at controls exist, but not as a general bitemporal query model."),
    BenchmarkDimension("MEM-12", "automated materialized view rebuild", 1.2, 4.5, 9.7, "GAP", "Sheets/Docs are largely written as control surfaces rather than deterministically rebuilt projections."),
    BenchmarkDimension("MEM-13", "hybrid semantic, lexical and graph retrieval", 1.4, 5.5, 9.8, "PARTIAL", "SemanticMemory and dependency graphs exist, but vector/full-text/graph retrieval is fragmented."),
    BenchmarkDimension("MEM-14", "knowledge and dependency graph", 1.0, 6.5, 9.6, "PARTIAL_STRONG", "Dependency graphs exist but are not the universal memory relationship index."),
    BenchmarkDimension("MEM-15", "continuous capture coverage", 1.4, 5.2, 9.6, "PARTIAL", "ChatBridge-active work can checkpoint continuously; native universal input/tool capture is not available or proven."),
    BenchmarkDimension("MEM-16", "privacy and matter/workstream compartmentalization", 1.4, 8.5, 9.9, "STRONG", "Matter walls and minimal public projections are strong; field-level memory policy can be standardized further."),
    BenchmarkDimension("MEM-17", "backup, PITR and disaster recovery", 1.2, 6.0, 9.6, "PARTIAL", "Restore/checkpoint proof exists, but provider-grade PITR, archive tiers and routine restore drills are not universal."),
    BenchmarkDimension("MEM-18", "memory observability and SLOs", 1.2, 5.8, 9.5, "PARTIAL", "Sentinel and CFBE observe health, but memory lag, replay RTO/RPO and retrieval quality lack one SLO contract."),
    BenchmarkDimension("MEM-19", "typed SDK and developer ergonomics", 1.0, 5.5, 9.5, "PARTIAL", "Many APIs exist, but no single memory API covers append/query/as-of/replay/render/trace."),
    BenchmarkDimension("MEM-20", "retention, compaction and storage tiering", 1.0, 4.5, 9.4, "GAP", "Context compaction exists, but durable hot/warm/cold/archive retention is not a unified memory lifecycle."),
    BenchmarkDimension("MEM-21", "retrieval-context budget control", 1.0, 8.0, 9.7, "STRONG_BOUNDED", "Bubbles context pressure and mission capsules already provide a strong foundation."),
    BenchmarkDimension("MEM-22", "owner-burden automation", 1.2, 6.5, 9.6, "PARTIAL", "No-avoidable-owner-work is doctrine; current manual reconciliation shows it is not yet fully realized."),
    BenchmarkDimension("MEM-23", "cross-system currentness coherence", 1.4, 5.5, 9.8, "GAP_CONFIRMED", "Recent coherence recovery proved stale projection and consumer-plane drift remain material risks."),
    BenchmarkDimension("MEM-24", "memory quality and learning promotion", 1.0, 7.5, 9.7, "STRONG_PARTIAL", "METHODGEN/KUAG/CFBE provide proof-bounded learning, but memory-quality evaluation is not one automated court."),
)


GENES: tuple[CapabilityGene, ...] = (
    CapabilityGene("BMF-001", "Intent-first immutable event store", "Microsoft/AWS event sourcing", "PARTIAL", "P0", "Every material directive/work/result change appends a typed immutable event with stream version and intent semantics.", ("Sync Events", "SemanticMemory", "Heartbeat Events")),
    CapabilityGene("BMF-002", "CQRS command/read separation", "Microsoft CQRS", "MISSING_AS_UNIFIED_LAYER", "P0", "Commands mutate only through governed writers; query projections are independently rebuildable.", ("KDV projection contract",)),
    CapabilityGene("BMF-003", "Materialized current-state compiler", "Microsoft/AWS materialized views", "PARTIAL", "P0", "Systems/current mission/Bible operational sections are generated from events rather than manually curated truth.", ("KDV", "Sentinel", "Bubbles mission capsules")),
    CapabilityGene("BMF-004", "Transactional outbox and idempotent consumers", "Microsoft CQRS", "MISSING_AS_UNIVERSAL", "P0", "State/event publication is atomic or PREPARED→COMMITTED; consumers tolerate duplicate delivery.", ("REFINT", "finality", "Bubbles idempotency")),
    CapabilityGene("BMF-005", "Optimistic per-stream concurrency", "Microsoft/AWS event sourcing", "PARTIAL", "P0", "Append requires expected stream version; conflicts are explicit and replayable.", ("concurrent writer rules",)),
    CapabilityGene("BMF-006", "Mission/workflow durable history", "Uber Cadence", "PARTIAL", "P0", "Long-running missions retain deterministic workflow state, retries, checkpoints, version and replay metadata.", ("ChatBridge", "Omega-One", "Bubbles Agent Fabric")),
    CapabilityGene("BMF-007", "Workflow replay/shadow/version court", "Uber Cadence", "PARTIAL", "P1", "New orchestration versions replay historic workflow traces before promotion.", ("ProofOS", "CFBE champion/challenger")),
    CapabilityGene("BMF-008", "Hybrid vector + lexical + graph retrieval", "Google Spanner AI/Graph", "PARTIAL", "P0", "Memory retrieval combines semantic similarity, exact text, structured filters and dependency traversal.", ("SemanticMemory", "KDV graph")),
    CapabilityGene("BMF-009", "Bitemporal memory", "Temporal data architecture", "MISSING_GENERAL", "P0", "Store both valid-time and recorded/transaction-time; support current and as-of queries without rewriting history.", ("EVENTDATE", "observed_at")),
    CapabilityGene("BMF-010", "Content-addressed provenance envelope", "GitHub attestations/SLSA", "PARTIAL_STRONG", "P0", "Every derived memory/Bible projection binds source refs, hashes, compiler/version and proof lineage.", ("ProofOS", "KDV receipts")),
    CapabilityGene("BMF-011", "Uniform idempotency envelope", "Stripe idempotency", "PARTIAL_STRONG", "P0", "Same operation key + same parameters returns/reuses prior result; mismatched reuse fails closed.", ("Bubbles idempotency", "Mission Result Index")),
    CapabilityGene("BMF-012", "Change-stream projection fanout", "Google Spanner change streams", "MISSING_PROVIDER_DURABLE", "P1", "Committed memory change can feed projection/index/analytics consumers with measurable lag.", ("Sync Bus", "EventBus")),
    CapabilityGene("BMF-013", "Hot/warm/cold/archive memory tiers", "Large-scale storage practice", "PARTIAL", "P0", "Hot mission capsule, warm workstream, cold immutable ledger, archival payload store; summaries never replace event truth.", ("Bubbles context governor", "ChatBridge HOT checkpoints")),
    CapabilityGene("BMF-014", "Snapshots plus replay", "Microsoft/AWS event sourcing", "PARTIAL", "P0", "Snapshots accelerate restore but remain disposable/rebuildable from immutable events.", ("ChatBridge checkpoints",)),
    CapabilityGene("BMF-015", "Schema version/upcaster registry", "Event sourcing evolution", "PARTIAL", "P1", "Old events remain immutable; readers deterministically upcast historical schema versions.", ("KDV schema registry", "INSTRREPLAY")),
    CapabilityGene("BMF-016", "Directive lineage graph", "Engineering decision logs + traceability", "PARTIAL", "P0", "Every directive links to objective, mission, decisions, corrections, work, proof, result and supersession.", ("KIOAS directive genome", "Method Genesis")),
    CapabilityGene("BMF-017", "Architectural decision records", "AWS ADR practice", "PARTIAL", "P1", "Significant decisions are immutable, superseded by successor decisions and linked to outcomes.", ("Decisions_Corrections", "METHODGEN")),
    CapabilityGene("BMF-018", "Memory privacy envelope", "Privacy-by-design event sourcing", "PARTIAL_STRONG", "P0", "Global memory stores minimum necessary fields/pointers; sensitive payload remains in authorized domain stores with tombstone/redaction semantics.", ("matter walls", "public projection boundary")),
    CapabilityGene("BMF-019", "Memory SLO/error budget", "SRE practice", "MISSING_UNIFIED", "P1", "Track capture lag, projection lag, replay RTO, lost-tail rate, retrieval precision, stale-read rate and owner reconstruction rate.", ("Sentinel", "CFBE")),
    CapabilityGene("BMF-020", "Restore drills and PITR", "Cloud reliability practice", "PARTIAL", "P1", "Scheduled no-effect restore drills validate event integrity, snapshots, projection rebuild and RTO/RPO.", ("ChatBridge restore canaries",)),
    CapabilityGene("BMF-021", "Bible renderer", "Docs-as-code/materialized view practice", "MISSING_UNIFIED", "P0", "Dynamic operational Bible sections are generated from machine memory; doctrine prose remains human-governed.", ("individual Bibles", "LBS-2.0")),
    CapabilityGene("BMF-022", "Memory API/SDK", "Platform engineering", "MISSING_UNIFIED", "P0", "Expose append_event, current_state, as_of, retrieve, trace_directive, replay_mission, checkpoint and render_bible.", ("Respawn API", "SemanticMemory")),
    CapabilityGene("BMF-023", "Automated memory quality court", "CFBE/observability", "PARTIAL", "P0", "Hard-veto orphan refs, stale current claims, contradiction laundering, sensitive leakage, broken lineage and authority inflation.", ("JARVIS", "ProofOS", "RealityGuard")),
    CapabilityGene("BMF-024", "Continuous capability harvest lifecycle", "Internal AAA + frontier benchmarking", "STRONG_PARTIAL", "P1", "CFBE continuously discovers, abstracts, adapts, shadows and promotes memory genes only after measured value.", ("AAA", "CFBE", "KUAG")),
)


def _weighted_score(dimensions: Iterable[BenchmarkDimension], field: str) -> float:
    rows = tuple(item.validate() for item in dimensions)
    total_weight = sum(item.weight for item in rows)
    return round(sum(getattr(item, field) * item.weight for item in rows) / total_weight * 10.0, 2)


def build_report() -> BenchmarkReport:
    architecture_score = _weighted_score(DIMENSIONS, "current_score")
    target_score = _weighted_score(DIMENSIONS, "target_score")
    # Operational proof is deliberately lower than design because provider-wide
    # continuous capture, durable hosted event delivery, unified retrieval and
    # automated projection rebuild are not currently proven end-to-end.
    proof_adjusted = round(architecture_score * 0.76, 2)
    return BenchmarkReport(
        schema="CFBE-BIBLE-MEMORY-BENCHMARK-V1",
        architecture_score=architecture_score,
        target_score=target_score,
        proof_adjusted_operational_score=proof_adjusted,
        gap=round(target_score - architecture_score, 2),
        hard_gates=(
            "NO_BIBLE_OR_DOMAIN_AUTHORITY_FLATTENING",
            "NO_RAW_PRIVATE_TRANSCRIPT_TO_GLOBAL_MEMORY",
            "NO_MODEL_WEIGHT_LEARNING_CLAIM",
            "NO_PROVIDER_RUNTIME_CLAIM_FROM_SOURCE",
            "EVENT_TRUTH_NEVER_REPLACED_BY_SUMMARY",
            "CONSEQUENTIAL_EFFECTS_REMAIN_AUTHORITY_GATED",
        ),
        dimensions=DIMENSIONS,
        genes=GENES,
    )
