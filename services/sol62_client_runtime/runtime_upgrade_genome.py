from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


GENOME_SCHEMA = "SOL62_RUNTIME_UPGRADE_GENOME_V1"


@dataclass(frozen=True)
class UpgradeGene:
    gene_id: str
    category: str
    mechanism: str
    tags: tuple[str, ...]
    provenance: str
    maturity: str

    def score(self, text: str) -> int:
        haystack = text.lower()
        return sum(1 for tag in self.tags if tag.lower() in haystack)


UPGRADE_GENOME: tuple[UpgradeGene, ...] = (
    UpgradeGene("HG-SOL62-101", "DURABLE_EXECUTION", "eager_start_with_durable_fallback", ("latency","start","retry",), "Temporal durable execution / LangGraph persistence", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-102", "DURABLE_EXECUTION", "checkpoint_granularity_optimizer", ("checkpoint","resume","replay",), "Temporal durable execution / LangGraph persistence", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-103", "DURABLE_EXECUTION", "deterministic_replay_guard", ("replay","determinism","history",), "Temporal durable execution / LangGraph persistence", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-104", "DURABLE_EXECUTION", "workflow_version_compatibility_gate", ("version","upgrade","replay",), "Temporal durable execution / LangGraph persistence", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-105", "DURABLE_EXECUTION", "activity_heartbeat_progress_resume", ("heartbeat","progress","resume",), "Temporal durable execution / LangGraph persistence", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-106", "DURABLE_EXECUTION", "compensation_stack_planner", ("compensation","rollback","effect",), "Temporal durable execution / LangGraph persistence", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-107", "DURABLE_EXECUTION", "long_run_continue_as_new", ("history","rotation","long_run",), "Temporal durable execution / LangGraph persistence", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-108", "DURABLE_EXECUTION", "durable_timer_coalescing", ("timer","wake","cost",), "Temporal durable execution / LangGraph persistence", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-109", "DURABLE_EXECUTION", "workflow_cache_pressure_control", ("cache","worker","memory",), "Temporal durable execution / LangGraph persistence", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-110", "DURABLE_EXECUTION", "sticky_execution_affinity", ("affinity","latency","worker",), "Temporal durable execution / LangGraph persistence", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-111", "SCHEDULING_BACKPRESSURE", "adaptive_poller_autoscaling", ("poller","backlog","throughput",), "Temporal worker performance / Kubernetes scheduling / Ray Serve", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-112", "SCHEDULING_BACKPRESSURE", "slot_supplier_resource_governor", ("slots","cpu","memory",), "Temporal worker performance / Kubernetes scheduling / Ray Serve", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-113", "SCHEDULING_BACKPRESSURE", "priority_aging_scheduler", ("priority","starvation","fairness",), "Temporal worker performance / Kubernetes scheduling / Ray Serve", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-114", "SCHEDULING_BACKPRESSURE", "workload_aware_preemption", ("preemption","priority","capacity",), "Temporal worker performance / Kubernetes scheduling / Ray Serve", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-115", "SCHEDULING_BACKPRESSURE", "disruption_budget_aware_reroute", ("availability","preemption","resilience",), "Temporal worker performance / Kubernetes scheduling / Ray Serve", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-116", "SCHEDULING_BACKPRESSURE", "topology_spread_provider_diversity", ("topology","diversity","failure_domain",), "Temporal worker performance / Kubernetes scheduling / Ray Serve", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-117", "SCHEDULING_BACKPRESSURE", "queue_lag_pid_controller", ("lag","backpressure","concurrency",), "Temporal worker performance / Kubernetes scheduling / Ray Serve", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-118", "SCHEDULING_BACKPRESSURE", "eager_local_execution_fast_path", ("eager","local","latency",), "Temporal worker performance / Kubernetes scheduling / Ray Serve", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-119", "SCHEDULING_BACKPRESSURE", "load_shed_with_mission_preservation", ("overload","shed","mission",), "Temporal worker performance / Kubernetes scheduling / Ray Serve", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-120", "SCHEDULING_BACKPRESSURE", "brownout_degraded_mode_contract", ("degraded","graceful","capacity",), "Temporal worker performance / Kubernetes scheduling / Ray Serve", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-121", "DISTRIBUTED_RECOVERY", "pending_entry_lease_recovery", ("pending","lease","recovery",), "Redis Streams / NATS JetStream delivery recovery", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-122", "DISTRIBUTED_RECOVERY", "idle_consumer_autoclaim", ("consumer","claim","recovery",), "Redis Streams / NATS JetStream delivery recovery", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-123", "DISTRIBUTED_RECOVERY", "ack_after_semantic_readback", ("ack","readback","effect",), "Redis Streams / NATS JetStream delivery recovery", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-124", "DISTRIBUTED_RECOVERY", "redelivery_counter_circuit_breaker", ("redelivery","retry","circuit",), "Redis Streams / NATS JetStream delivery recovery", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-125", "DISTRIBUTED_RECOVERY", "consumer_lag_health_signal", ("lag","health","queue",), "Redis Streams / NATS JetStream delivery recovery", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-126", "DISTRIBUTED_RECOVERY", "durable_consumer_identity", ("consumer","identity","resume",), "Redis Streams / NATS JetStream delivery recovery", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-127", "DISTRIBUTED_RECOVERY", "cross_domain_ack_namespace", ("ack","namespace","multi_domain",), "Redis Streams / NATS JetStream delivery recovery", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-128", "DISTRIBUTED_RECOVERY", "flow_control_stall_detector", ("flow_control","stall","backpressure",), "Redis Streams / NATS JetStream delivery recovery", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-129", "DISTRIBUTED_RECOVERY", "poison_message_quarantine_repair", ("poison","quarantine","repair",), "Redis Streams / NATS JetStream delivery recovery", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-130", "DISTRIBUTED_RECOVERY", "exactly_once_effect_envelope", ("dedup","idempotency","effect",), "Redis Streams / NATS JetStream delivery recovery", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-131", "TRANSACTIONAL_CONCURRENCY", "serializable_retry_envelope", ("serializable","retry","transaction",), "PostgreSQL serializable isolation / advisory locks / logical replication", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-132", "TRANSACTIONAL_CONCURRENCY", "transaction_scoped_advisory_fence", ("advisory_lock","fence","transaction",), "PostgreSQL serializable isolation / advisory locks / logical replication", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-133", "TRANSACTIONAL_CONCURRENCY", "lock_order_deadlock_prevention", ("lock","deadlock","ordering",), "PostgreSQL serializable isolation / advisory locks / logical replication", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-134", "TRANSACTIONAL_CONCURRENCY", "read_snapshot_epoch_pin", ("snapshot","epoch","currentness",), "PostgreSQL serializable isolation / advisory locks / logical replication", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-135", "TRANSACTIONAL_CONCURRENCY", "write_skew_detector", ("serializable","write_skew","conflict",), "PostgreSQL serializable isolation / advisory locks / logical replication", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-136", "TRANSACTIONAL_CONCURRENCY", "compare_and_swap_revision_guard", ("cas","revision","write",), "PostgreSQL serializable isolation / advisory locks / logical replication", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-137", "TRANSACTIONAL_CONCURRENCY", "effect_outbox_transaction", ("outbox","effect","transaction",), "PostgreSQL serializable isolation / advisory locks / logical replication", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-138", "TRANSACTIONAL_CONCURRENCY", "inbox_dedup_transaction", ("inbox","dedup","transaction",), "PostgreSQL serializable isolation / advisory locks / logical replication", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-139", "TRANSACTIONAL_CONCURRENCY", "logical_replication_read_model", ("replication","projection","read_model",), "PostgreSQL serializable isolation / advisory locks / logical replication", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-140", "TRANSACTIONAL_CONCURRENCY", "replication_lag_currentness_gate", ("replication","lag","currentness",), "PostgreSQL serializable isolation / advisory locks / logical replication", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-141", "OBSERVABILITY_PROVENANCE", "otel_trace_semantic_contract", ("trace","semantic","observability",), "OpenTelemetry semantic conventions", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-142", "OBSERVABILITY_PROVENANCE", "trace_metric_log_correlation", ("trace","metric","log",), "OpenTelemetry semantic conventions", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-143", "OBSERVABILITY_PROVENANCE", "baggage_mission_lineage", ("baggage","lineage","mission",), "OpenTelemetry semantic conventions", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-144", "OBSERVABILITY_PROVENANCE", "provider_request_id_correlation", ("provider","request_id","trace",), "OpenTelemetry semantic conventions", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-145", "OBSERVABILITY_PROVENANCE", "runtime_resource_identity", ("runtime","resource","identity",), "OpenTelemetry semantic conventions", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-146", "OBSERVABILITY_PROVENANCE", "structured_exception_taxonomy", ("exception","failure","taxonomy",), "OpenTelemetry semantic conventions", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-147", "OBSERVABILITY_PROVENANCE", "queue_wait_span_decomposition", ("queue","latency","span",), "OpenTelemetry semantic conventions", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-148", "OBSERVABILITY_PROVENANCE", "effect_readback_span_link", ("effect","readback","trace",), "OpenTelemetry semantic conventions", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-149", "OBSERVABILITY_PROVENANCE", "proof_artifact_span_link", ("proof","artifact","trace",), "OpenTelemetry semantic conventions", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-150", "OBSERVABILITY_PROVENANCE", "cost_token_energy_attribution", ("cost","usage","attribution",), "OpenTelemetry semantic conventions", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-151", "AGENT_RUNTIME_INTELLIGENCE", "handoff_ownership_contract", ("handoff","agent","ownership",), "OpenAI Agents SDK / Google ADK / Anthropic agent guidance", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-152", "AGENT_RUNTIME_INTELLIGENCE", "guardrail_preflight_pipeline", ("guardrail","preflight","safety",), "OpenAI Agents SDK / Google ADK / Anthropic agent guidance", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-153", "AGENT_RUNTIME_INTELLIGENCE", "tool_schema_capability_negotiation", ("tool","schema","capability",), "OpenAI Agents SDK / Google ADK / Anthropic agent guidance", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-154", "AGENT_RUNTIME_INTELLIGENCE", "session_state_delta_compaction", ("session","state","compaction",), "OpenAI Agents SDK / Google ADK / Anthropic agent guidance", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-155", "AGENT_RUNTIME_INTELLIGENCE", "artifact_aware_instruction_binding", ("artifact","instruction","state",), "OpenAI Agents SDK / Google ADK / Anthropic agent guidance", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-156", "AGENT_RUNTIME_INTELLIGENCE", "subagent_spawn_damping", ("subagent","delegation","cost",), "OpenAI Agents SDK / Google ADK / Anthropic agent guidance", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-157", "AGENT_RUNTIME_INTELLIGENCE", "specialist_context_isolation", ("subagent","context","isolation",), "OpenAI Agents SDK / Google ADK / Anthropic agent guidance", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-158", "AGENT_RUNTIME_INTELLIGENCE", "resume_tokenized_agent_state", ("resume","state","agent",), "OpenAI Agents SDK / Google ADK / Anthropic agent guidance", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-159", "AGENT_RUNTIME_INTELLIGENCE", "agent_result_state_separation", ("result","state","truth",), "OpenAI Agents SDK / Google ADK / Anthropic agent guidance", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-160", "AGENT_RUNTIME_INTELLIGENCE", "human_review_interrupt_resume", ("interrupt","review","resume",), "OpenAI Agents SDK / Google ADK / Anthropic agent guidance", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-161", "CONTEXT_MEMORY", "context_budget_watermarking", ("context","budget","watermark",), "OpenAI agent state / Google ADK sessions / Anthropic long-run memory guidance", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-162", "CONTEXT_MEMORY", "pre_compaction_checkpoint", ("context","compaction","checkpoint",), "OpenAI agent state / Google ADK sessions / Anthropic long-run memory guidance", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-163", "CONTEXT_MEMORY", "episodic_memory_relevance_decay", ("memory","relevance","decay",), "OpenAI agent state / Google ADK sessions / Anthropic long-run memory guidance", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-164", "CONTEXT_MEMORY", "negative_memory_retention", ("memory","failure","negative",), "OpenAI agent state / Google ADK sessions / Anthropic long-run memory guidance", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-165", "CONTEXT_MEMORY", "semantic_cache_authority_keying", ("cache","authority","privacy",), "OpenAI agent state / Google ADK sessions / Anthropic long-run memory guidance", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-166", "CONTEXT_MEMORY", "cache_currentness_ttl", ("cache","currentness","ttl",), "OpenAI agent state / Google ADK sessions / Anthropic long-run memory guidance", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-167", "CONTEXT_MEMORY", "retrieval_version_coherence", ("retrieval","version","currentness",), "OpenAI agent state / Google ADK sessions / Anthropic long-run memory guidance", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-168", "CONTEXT_MEMORY", "contradiction_first_retrieval", ("retrieval","contradiction","evidence",), "OpenAI agent state / Google ADK sessions / Anthropic long-run memory guidance", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-169", "CONTEXT_MEMORY", "memory_write_quality_gate", ("memory","write","quality",), "OpenAI agent state / Google ADK sessions / Anthropic long-run memory guidance", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-170", "CONTEXT_MEMORY", "cross_session_state_hydration", ("session","hydrate","continuity",), "OpenAI agent state / Google ADK sessions / Anthropic long-run memory guidance", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-171", "SANDBOX_EXECUTION", "persistent_task_sandbox", ("sandbox","persistent","code",), "Google Agent Runtime code execution / OpenAI sandbox agents", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-172", "SANDBOX_EXECUTION", "sandbox_ttl_reaper", ("sandbox","ttl","cleanup",), "Google Agent Runtime code execution / OpenAI sandbox agents", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-173", "SANDBOX_EXECUTION", "sandbox_resource_quota", ("sandbox","cpu","memory",), "Google Agent Runtime code execution / OpenAI sandbox agents", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-174", "SANDBOX_EXECUTION", "sandbox_network_egress_policy", ("sandbox","network","privacy",), "Google Agent Runtime code execution / OpenAI sandbox agents", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-175", "SANDBOX_EXECUTION", "sandbox_filesystem_snapshot", ("sandbox","filesystem","snapshot",), "Google Agent Runtime code execution / OpenAI sandbox agents", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-176", "SANDBOX_EXECUTION", "sandbox_warm_pool", ("sandbox","warm","latency",), "Google Agent Runtime code execution / OpenAI sandbox agents", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-177", "SANDBOX_EXECUTION", "sandbox_dependency_manifest_lock", ("sandbox","dependency","reproducible",), "Google Agent Runtime code execution / OpenAI sandbox agents", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-178", "SANDBOX_EXECUTION", "sandbox_secret_zeroization", ("sandbox","secret","cleanup",), "Google Agent Runtime code execution / OpenAI sandbox agents", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-179", "SANDBOX_EXECUTION", "sandbox_result_provenance", ("sandbox","result","provenance",), "Google Agent Runtime code execution / OpenAI sandbox agents", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-180", "SANDBOX_EXECUTION", "sandbox_escape_adversarial_court", ("sandbox","security","court",), "Google Agent Runtime code execution / OpenAI sandbox agents", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-181", "ROUTING_PORTFOLIO", "route_regret_tracker", ("route","regret","learning",), "FUSE residual synthesis informed by multi-provider agent/runtime patterns", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-182", "ROUTING_PORTFOLIO", "failure_domain_diversity_score", ("route","diversity","failure_domain",), "FUSE residual synthesis informed by multi-provider agent/runtime patterns", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-183", "ROUTING_PORTFOLIO", "provider_health_decay", ("provider","health","decay",), "FUSE residual synthesis informed by multi-provider agent/runtime patterns", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-184", "ROUTING_PORTFOLIO", "cold_start_latency_model", ("route","cold_start","latency",), "FUSE residual synthesis informed by multi-provider agent/runtime patterns", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-185", "ROUTING_PORTFOLIO", "route_cost_quality_pareto", ("route","cost","quality",), "FUSE residual synthesis informed by multi-provider agent/runtime patterns", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-186", "ROUTING_PORTFOLIO", "capability_lease_ttl_refresh", ("capability","lease","currentness",), "FUSE residual synthesis informed by multi-provider agent/runtime patterns", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-187", "ROUTING_PORTFOLIO", "shadow_route_canary", ("route","shadow","canary",), "FUSE residual synthesis informed by multi-provider agent/runtime patterns", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-188", "ROUTING_PORTFOLIO", "route_semantic_equivalence_court", ("route","semantic","equivalence",), "FUSE residual synthesis informed by multi-provider agent/runtime patterns", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-189", "ROUTING_PORTFOLIO", "unknown_route_effect_readback", ("route","effect","readback",), "FUSE residual synthesis informed by multi-provider agent/runtime patterns", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-190", "ROUTING_PORTFOLIO", "portfolio_exploration_budget", ("route","exploration","budget",), "FUSE residual synthesis informed by multi-provider agent/runtime patterns", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-191", "SELF_IMPROVEMENT_EVALUATION", "counterfactual_failure_replay", ("failure","replay","counterfactual",), "FUSE ProofOS/CFBE residual synthesis informed by agent eval/observability patterns", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-192", "SELF_IMPROVEMENT_EVALUATION", "untouched_holdout_cases", ("evaluation","holdout","falsification",), "FUSE ProofOS/CFBE residual synthesis informed by agent eval/observability patterns", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-193", "SELF_IMPROVEMENT_EVALUATION", "mutation_testing_for_runtime_rules", ("mutation","test","runtime",), "FUSE ProofOS/CFBE residual synthesis informed by agent eval/observability patterns", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-194", "SELF_IMPROVEMENT_EVALUATION", "metamorphic_property_courts", ("metamorphic","property","court",), "FUSE ProofOS/CFBE residual synthesis informed by agent eval/observability patterns", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-195", "SELF_IMPROVEMENT_EVALUATION", "shadow_challenger_tournament", ("challenger","shadow","benchmark",), "FUSE ProofOS/CFBE residual synthesis informed by agent eval/observability patterns", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-196", "SELF_IMPROVEMENT_EVALUATION", "false_green_detector", ("proof","false_green","evaluation",), "FUSE ProofOS/CFBE residual synthesis informed by agent eval/observability patterns", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-197", "SELF_IMPROVEMENT_EVALUATION", "owner_burden_regression_metric", ("owner_burden","metric","value",), "FUSE ProofOS/CFBE residual synthesis informed by agent eval/observability patterns", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-198", "SELF_IMPROVEMENT_EVALUATION", "recovery_time_regression_metric", ("recovery","metric","resilience",), "FUSE ProofOS/CFBE residual synthesis informed by agent eval/observability patterns", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-199", "SELF_IMPROVEMENT_EVALUATION", "prompt_zero_continuation_court", ("continuation","prompt_zero","court",), "FUSE ProofOS/CFBE residual synthesis informed by agent eval/observability patterns", "CANDIDATE_RESIDUAL"),
    UpgradeGene("HG-SOL62-200", "SELF_IMPROVEMENT_EVALUATION", "mechanism_change_required_on_repeat_failure", ("failure","repair","mechanism",), "FUSE ProofOS/CFBE residual synthesis informed by agent eval/observability patterns", "CANDIDATE_RESIDUAL"),
)


def select_upgrade_genes(
    *, objective: str, reason: str, limit: int = 12, include_zero_score: bool = False
) -> tuple[UpgradeGene, ...]:
    """Select residual upgrade candidates without granting maturity or authority."""
    if limit <= 0:
        return ()
    query = f"{objective} {reason}".lower()
    ranked = sorted(
        UPGRADE_GENOME,
        key=lambda gene: (-gene.score(query), gene.category, gene.gene_id),
    )
    if include_zero_score:
        return tuple(ranked[:limit])
    matched = tuple(gene for gene in ranked if gene.score(query) > 0)
    if matched:
        return matched[:limit]

    # No lexical match should not collapse the genome to nothing. Use a balanced
    # deterministic seed across categories for source-independent exploration.
    seen: set[str] = set()
    fallback: list[UpgradeGene] = []
    for gene in ranked:
        if gene.category in seen:
            continue
        seen.add(gene.category)
        fallback.append(gene)
        if len(fallback) >= min(limit, 10):
            break
    return tuple(fallback)


def genome_summary() -> dict[str, object]:
    categories = sorted({gene.category for gene in UPGRADE_GENOME})
    return {
        "schema": GENOME_SCHEMA,
        "count": len(UPGRADE_GENOME),
        "first_id": UPGRADE_GENOME[0].gene_id,
        "last_id": UPGRADE_GENOME[-1].gene_id,
        "categories": categories,
        "maturity": "CANDIDATE_RESIDUAL",
        "truth_boundary": (
            "GENOME_REGISTERED_NE_IMPLEMENTED; IMPLEMENTED_NE_BENCHMARK_PASS; "
            "BENCHMARK_PASS_NE_SOURCE_ADMITTED; SOURCE_ADMITTED_NE_LIVE_RUNTIME"
        ),
    }
