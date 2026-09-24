from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Mapping, Sequence

SCHEMA = "FUSE_CODEX_CAPABILITY_HARVEST_V1"
VERSION = "1.0.0"

OFFICIAL_SOURCES = (
    "https://openai.com/index/introducing-the-codex-app/",
    "https://openai.com/codex/",
    "https://developers.openai.com/api/docs/guides/agents",
    "https://developers.openai.com/api/docs/guides/agents-api/overview",
    "https://developers.openai.com/api/docs/guides/agents-api/environments/self-hosted",
    "https://developers.openai.com/api/docs/guides/agents-api/environments/security",
    "https://developers.openai.com/api/docs/guides/tools-skills",
    "https://developers.openai.com/api/docs/guides/tools-connectors-mcp",
    "https://developers.openai.com/api/docs/guides/agents/guardrails-approvals",
    "https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra",
    "https://developers.openai.com/blog/mastering-codex-remote-for-engineering",
    "https://developers.openai.com/cookbook/topic/codex",
)

VALID_DISPOSITIONS = frozenset({
    "REUSE",
    "REBIND",
    "REPAIR",
    "EXTEND",
    "COMPOSE",
    "HARVEST",
    "BUILD_MINIMUM",
    "REJECT",
})


@dataclass(frozen=True, slots=True)
class CodexCapabilityGene:
    gene_id: str
    name: str
    category: str
    mechanism: str
    tags: tuple[str, ...]
    fuse_binding: tuple[str, ...]
    disposition: str
    maturity: str = "CANDIDATE_RESIDUAL"

    def __post_init__(self) -> None:
        if self.disposition not in VALID_DISPOSITIONS:
            raise ValueError(f"invalid disposition: {self.disposition}")
        if not self.gene_id.startswith("HG-CODEX-"):
            raise ValueError("gene id must use HG-CODEX namespace")
        if not self.fuse_binding:
            raise ValueError("every Codex mechanism must bind to an existing FUSE organ")

    def score(self, text: str) -> int:
        haystack = text.lower()
        return sum(1 for tag in self.tags if tag.lower() in haystack)

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        row["tags"] = list(self.tags)
        row["fuse_binding"] = list(self.fuse_binding)
        return row


CODEX_CAPABILITY_GENES: tuple[CodexCapabilityGene, ...] = (
    CodexCapabilityGene(
        "HG-CODEX-001",
        "Isolated Parallel Worktree Lane",
        "CONCURRENCY",
        "Each parallel engineering worker receives an isolated repository view and explicit fan-in boundary.",
        ("worktree", "parallel", "repo", "conflict"),
        ("FDOF", "WORK_PLANE", "FOREST_V2", "GITHUB_AIRLOCK"),
        "COMPOSE",
    ),
    CodexCapabilityGene(
        "HG-CODEX-002",
        "Project Thread Context Partition",
        "CONTEXT",
        "Partition long-running work by project/thread while preserving shared mission identity outside the client.",
        ("thread", "project", "context", "session"),
        ("CHATBRIDGE", "MEMORY_CONTINUUM", "SOL_6_2", "MISSION_BUS"),
        "COMPOSE",
    ),
    CodexCapabilityGene(
        "HG-CODEX-003",
        "Queued Steering Injection",
        "CONTROL",
        "Queue steering instructions into a running mission without restarting or losing committed progress.",
        ("steer", "queue", "running", "prompt"),
        ("MISSION_IR", "WORK_PLANE", "SOL_6_2", "GENESIS"),
        "EXTEND",
    ),
    CodexCapabilityGene(
        "HG-CODEX-004",
        "Speculative Side-Branch Conversation",
        "COGNITION",
        "Run side analysis against a frozen mission checkpoint and merge only explicit deltas back to the parent.",
        ("side", "branch", "speculative", "analysis"),
        ("COGNITIVE_COUNCIL", "FORMATION", "PORTABLE_STATE", "PROOFOS"),
        "COMPOSE",
    ),
    CodexCapabilityGene(
        "HG-CODEX-005",
        "Durable Goal Graph",
        "PLANNING",
        "Represent intermediate goals as resumable mission subgraphs with explicit completion predicates.",
        ("goal", "milestone", "dag", "plan"),
        ("MISSION_IR", "ALPHA_OMEGA", "WORK_PLANE", "SOL_6_2"),
        "REUSE",
    ),
    CodexCapabilityGene(
        "HG-CODEX-006",
        "Inline Diff Review Receipt",
        "PROOF",
        "Bind review comments and accepted/rejected diff hunks to immutable source identities and proof receipts.",
        ("diff", "review", "comment", "code"),
        ("PROOFOS", "REALITY_JUDGE", "GITHUB_AIRLOCK"),
        "EXTEND",
    ),
    CodexCapabilityGene(
        "HG-CODEX-007",
        "Automation Review Inbox",
        "DELIVERY",
        "Completed background jobs land in a durable review queue instead of being silently treated as accepted.",
        ("automation", "review", "inbox", "background"),
        ("DELIVERY_JOURNAL", "WORK_PLANE", "ALPHA_OMEGA", "PROOFOS"),
        "COMPOSE",
    ),
    CodexCapabilityGene(
        "HG-CODEX-008",
        "Scheduled Automation Adapter",
        "SCHEDULING",
        "Compile Codex-style scheduled work into the existing estate scheduler without creating a second scheduler.",
        ("schedule", "automation", "recurring", "background"),
        ("ALPHA_OMEGA", "FO_GAS", "GENESIS", "MISSION_BUS"),
        "REBIND",
    ),
    CodexCapabilityGene(
        "HG-CODEX-009",
        "Cloud Trigger Event Adapter",
        "SCHEDULING",
        "Translate external trigger events into idempotent mission wake packets under existing authority gates.",
        ("trigger", "event", "webhook", "cloud"),
        ("ALPHA_OMEGA", "MISSION_BUS", "FDOF", "GENESIS"),
        "EXTEND",
    ),
    CodexCapabilityGene(
        "HG-CODEX-010",
        "Managed Harness Provider Cell",
        "EXECUTION",
        "Expose an optional managed Codex-style harness as one provider-neutral execution cell, never as authority or truth root.",
        ("harness", "managed", "agent", "cloud"),
        ("FUSE_SOVEREIGN_PLANE", "CAPABILITY_MARKET", "SOL_6_2", "FIO"),
        "REBIND",
    ),
    CodexCapabilityGene(
        "HG-CODEX-011",
        "Automatic Context Compaction Checkpoint",
        "CONTEXT",
        "Compact long sessions only after a resumable checkpoint preserves mission, evidence, tool, effect, and pending-state identity.",
        ("context", "compaction", "checkpoint", "long"),
        ("CHATBRIDGE", "PORTABLE_STATE", "MEMORY_CONTINUUM", "SOL_6_2"),
        "EXTEND",
    ),
    CodexCapabilityGene(
        "HG-CODEX-012",
        "Subagent Context Isolation",
        "MULTI_AGENT",
        "Delegate bounded specialist work with minimum necessary context and explicit result contracts.",
        ("subagent", "delegate", "context", "specialist"),
        ("FOREST_V2", "COGNITIVE_COUNCIL", "MISSION_IR", "FDOF"),
        "REUSE",
    ),
    CodexCapabilityGene(
        "HG-CODEX-013",
        "Programmatic Tool-Call Plan",
        "TOOLS",
        "Represent tool sequences as typed, inspectable programs with per-call authority and semantic readback.",
        ("tool", "programmatic", "call", "batch"),
        ("FIO", "MCP", "FDOF", "SICF", "PROOFOS"),
        "COMPOSE",
    ),
    CodexCapabilityGene(
        "HG-CODEX-014",
        "Lazy Skill Directory Loader",
        "SKILLS",
        "Load skill metadata at startup and hydrate full instructions/resources only when the mission actually matches.",
        ("skill", "lazy", "directory", "instruction"),
        ("SKILLFORGE", "CAPABILITY_MARKET", "MEMORY_CONTINUUM"),
        "EXTEND",
    ),
    CodexCapabilityGene(
        "HG-CODEX-015",
        "Three-Mode Sandbox Contract",
        "SANDBOX",
        "Treat hosted sandbox, self-hosted sandbox, and no-sandbox execution as interchangeable qualified carriers behind one contract.",
        ("sandbox", "hosted", "self-hosted", "execution"),
        ("EXECUTION_POWER_POOLS", "FUSE_WORKSPACE", "LOCAL_RUNTIME", "PORTFOLIO_V2"),
        "COMPOSE",
    ),
    CodexCapabilityGene(
        "HG-CODEX-016",
        "Outbound-Only Self-Hosted Executor",
        "SANDBOX",
        "Use an outbound reconnecting executor so owner-controlled compute need not expose an inbound control port.",
        ("executor", "outbound", "websocket", "reconnect"),
        ("WINDOWS_NATIVE", "GENESIS", "FCOA_DEVICE_CONTROL", "FIO"),
        "BUILD_MINIMUM",
    ),
    CodexCapabilityGene(
        "HG-CODEX-017",
        "Restricted Environment-Key Separation",
        "SECURITY",
        "Separate environment-connect authority from application/provider authority and keep long-lived credentials outside agent code.",
        ("key", "restricted", "credential", "secret"),
        ("SECURE_CAPABILITY_BOX", "FIO", "SICF", "SECRET_MANAGER"),
        "REUSE",
    ),
    CodexCapabilityGene(
        "HG-CODEX-018",
        "Approval Interrupt With Serialized Resume",
        "AUTHORITY",
        "Pause a run at an approval boundary, persist exact state, and resume the same run without replaying prior effects.",
        ("approval", "interrupt", "resume", "state"),
        ("FDOF", "SICF", "SOL_6_2", "DELIVERY_JOURNAL"),
        "COMPOSE",
    ),
    CodexCapabilityGene(
        "HG-CODEX-019",
        "Cross-Client Session Portability",
        "CONTINUITY",
        "Carry the same mission/session configuration across CLI, IDE, desktop, mobile, and FUSE-owned clients without making any client canonical.",
        ("client", "cli", "ide", "mobile", "session"),
        ("CHATBRIDGE", "PORTABLE_STATE", "FUSE_MOBILE", "SOL_6_2"),
        "EXTEND",
    ),
    CodexCapabilityGene(
        "HG-CODEX-020",
        "Remote Owner Control Plane",
        "CONTROL",
        "Allow remote owner steering, review, attachments, and approvals over work executing on another qualified host.",
        ("remote", "mobile", "review", "steer"),
        ("FUSE_WORKSPACE", "FUSE_MOBILE", "CHATBRIDGE", "GENESIS"),
        "EXTEND",
    ),
    CodexCapabilityGene(
        "HG-CODEX-021",
        "Instruction Distillation / Prompt De-bloating",
        "CONTEXT",
        "Continuously challenge stale AGENTS/skill/prompt scaffolding and retain only instructions that improve matched outcomes.",
        ("agents.md", "prompt", "instruction", "context", "bloat"),
        ("SKILLFORGE", "HARNESS_TOURNAMENT", "CFBE", "MEMORY_CONTINUUM"),
        "EXTEND",
    ),
    CodexCapabilityGene(
        "HG-CODEX-022",
        "Trace-Eval Improvement Loop",
        "LEARNING",
        "Use execution traces, evals, failure fingerprints, and holdouts to improve agent policies without self-certification.",
        ("trace", "eval", "improve", "failure"),
        ("CFBE", "FAILURE_HARVEST", "RAEFI", "PROOFOS", "REALITY_JUDGE"),
        "REUSE",
    ),
    CodexCapabilityGene(
        "HG-CODEX-023",
        "Worktree Promotion Fan-In",
        "SOURCE",
        "Promote isolated worker output only after exact-base reconciliation, tests, source provenance, and collision revalidation.",
        ("worktree", "merge", "promotion", "source"),
        ("FDOF", "GITHUB_AIRLOCK", "SICF", "PROOFOS"),
        "COMPOSE",
    ),
    CodexCapabilityGene(
        "HG-CODEX-024",
        "Long-Run Harness Recovery",
        "DURABILITY",
        "Recover long-running agent work after client or executor interruption without rerunning committed effects.",
        ("long-running", "recovery", "disconnect", "resume"),
        ("SOL_6_2", "GENESIS", "PORTABLE_STATE", "DELIVERY_JOURNAL"),
        "REUSE",
    ),
)


def validate_catalog(genes: Sequence[CodexCapabilityGene] = CODEX_CAPABILITY_GENES) -> None:
    ids = [gene.gene_id for gene in genes]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate Codex harvest gene id")
    expected = [f"HG-CODEX-{i:03d}" for i in range(1, len(genes) + 1)]
    if ids != expected:
        raise ValueError("Codex harvest gene ids must be monotonic and contiguous")
    if any(gene.maturity != "CANDIDATE_RESIDUAL" for gene in genes):
        raise ValueError("harvest metadata cannot self-promote maturity")
    if any(not gene.fuse_binding for gene in genes):
        raise ValueError("unbound Codex mechanism")


def select_codex_genes(
    objective: str,
    *,
    limit: int = 8,
    genes: Sequence[CodexCapabilityGene] = CODEX_CAPABILITY_GENES,
) -> tuple[CodexCapabilityGene, ...]:
    if limit <= 0:
        return ()
    ranked = sorted(
        genes,
        key=lambda gene: (-gene.score(objective), gene.category, gene.gene_id),
    )
    matched = [gene for gene in ranked if gene.score(objective) > 0]
    if matched:
        return tuple(matched[:limit])

    selected: list[CodexCapabilityGene] = []
    seen_categories: set[str] = set()
    for gene in ranked:
        if gene.category in seen_categories:
            continue
        seen_categories.add(gene.category)
        selected.append(gene)
        if len(selected) >= limit:
            break
    return tuple(selected)


def compile_adoption_manifest(
    objective: str,
    *,
    limit: int = 8,
) -> Mapping[str, object]:
    selected = select_codex_genes(objective, limit=limit)
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "objective": objective,
        "selected": [gene.to_dict() for gene in selected],
        "official_sources": list(OFFICIAL_SOURCES),
        "provider_neutral_clean_room": True,
        "source_code_or_weights_copied": False,
        "authority_expansion": False,
        "new_controller_created": False,
        "new_truth_root_created": False,
        "new_scheduler_created": False,
        "promotion_required": (
            "SOURCE_IMPLEMENTED",
            "DETERMINISTIC_TESTED",
            "MATCHED_BENCHMARK_PASS",
            "PROOFOS_REALITY_JUDGE",
            "RUNTIME_READBACK",
            "OWNER_VALUE_VERIFIED",
        ),
    }


def catalog_summary() -> Mapping[str, object]:
    validate_catalog()
    categories = sorted({gene.category for gene in CODEX_CAPABILITY_GENES})
    dispositions = sorted({gene.disposition for gene in CODEX_CAPABILITY_GENES})
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "gene_count": len(CODEX_CAPABILITY_GENES),
        "first_gene": CODEX_CAPABILITY_GENES[0].gene_id,
        "last_gene": CODEX_CAPABILITY_GENES[-1].gene_id,
        "categories": categories,
        "dispositions": dispositions,
        "provider_neutral_clean_room": True,
        "authority_expansion": False,
        "controller_duplication": False,
        "truth_boundary": (
            "PUBLIC_MECHANISM_HARVEST_NE_SOURCE_IMPLEMENTED; "
            "SOURCE_IMPLEMENTED_NE_RUNTIME_VERIFIED; "
            "RUNTIME_VERIFIED_NE_OWNER_VALUE_VERIFIED"
        ),
    }
