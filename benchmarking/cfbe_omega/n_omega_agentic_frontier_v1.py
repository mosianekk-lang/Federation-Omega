from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping


class HarvestMode(str, Enum):
    REUSE_VERIFIED = "REUSE_VERIFIED"
    COMPOSED_BY_FABRIC = "COMPOSED_BY_FABRIC"
    BUILD_ADDITIVE = "BUILD_ADDITIVE"
    PROVIDER_GATED = "PROVIDER_GATED"


@dataclass(frozen=True, slots=True)
class VendorProfile:
    vendor: str
    surface: str
    strengths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CapabilityGene:
    gene_id: str
    name: str
    domain: str
    sources: tuple[str, ...]
    mode: HarvestMode
    binding: str
    proof_gate: str
    provider_dependency: int = 1

    def score(self, weights: Mapping[str, float] | None = None) -> float:
        w = {"fit": 1.0, "proof": 1.0, "leverage": 1.0, "dependency": 0.65}
        if weights:
            w.update({k: float(v) for k, v in weights.items() if k in w})
        fit = 5 if self.mode in {HarvestMode.REUSE_VERIFIED, HarvestMode.COMPOSED_BY_FABRIC} else 4
        proof = 5 if self.mode is HarvestMode.REUSE_VERIFIED else 4
        leverage = 5 if len(self.sources) >= 3 else 4
        return round(fit*w["fit"] + proof*w["proof"] + leverage*w["leverage"] - self.provider_dependency*w["dependency"], 4)


@dataclass(frozen=True, slots=True)
class MissionProfile:
    mission_id: str
    domains: frozenset[str]
    long_running: bool = False
    multi_agent: bool = False
    tool_heavy: bool = False
    code_execution: bool = False
    browser_or_computer: bool = False
    legacy_ui: bool = False
    customer_facing: bool = False
    consequential: bool = False
    requires_memory: bool = False
    requires_dynamic_models: bool = False
    requires_release: bool = False
    requires_adaptive_effort: bool = False
    requires_cross_window_context: bool = False
    requires_dynamic_tools: bool = False
    requires_portable_skills: bool = False
    requires_persistent_agent: bool = False
    requires_adaptive_computer_use: bool = False
    requires_hypothesis_evolution: bool = False
    requires_strict_self_verification: bool = False
    requires_harness_simplification: bool = False
    requires_artifact_production: bool = False
    requires_local_multimodal: bool = False
    requires_async_job_handle: bool = False
    requires_exact_resume: bool = False
    requires_tool_catalog_cache: bool = False
    requires_async_task_delivery: bool = False
    requires_browser_offscreen_liveness: bool = False
    requires_replay_safe_versioning: bool = False
    requires_adaptive_worker_capacity: bool = False
    requires_local_openai_compat: bool = False
    requires_failure_domain_spread: bool = False
    requires_oauth_mixup_hardening: bool = False


@dataclass(frozen=True, slots=True)
class SuperstackPlan:
    mission_id: str
    selected_gene_ids: tuple[str, ...]
    orchestration: tuple[str, ...]
    max_mutating_lanes: int
    external_model_authority: str
    proof_required: tuple[str, ...]
    route_score: float


VENDORS: tuple[VendorProfile, ...] = (
    VendorProfile("OpenAI", "Agents SDK", ("agent loop", "handoffs", "agents-as-tools", "guardrails", "MCP", "sessions", "HITL", "tracing", "hosted/local tools")),
    VendorProfile("Anthropic", "Claude agentic tooling", ("long-horizon agents", "advisor escalation", "subagents", "self-correction", "tool use")),
    VendorProfile("Google", "ADK / Agents CLI", ("multi-agent", "durable execution", "persistent sessions", "sandbox code", "evaluation", "MCP")),
    VendorProfile("Microsoft", "Agent Framework / Foundry", ("sequential/concurrent/handoff/group-chat/Magentic", "checkpoints", "middleware", "HITL", "memory")),
    VendorProfile("AWS", "Bedrock Agents / AgentCore", ("supervisor/collaborators", "runtime identity", "gateway", "MCP", "semantic tool search", "browser/code", "observability", "evaluations")),
    VendorProfile("Salesforce", "Agentforce", ("agent script", "testing API", "observability", "subagents", "DX lifecycle", "enterprise actions")),
    VendorProfile("ServiceNow", "AI Agents / Control Tower / Action Fabric", ("agent studio", "teams", "MCP action fabric", "governance", "tool/cost monitoring")),
    VendorProfile("UiPath", "Maestro / Agentic Automation", ("BPMN/Flow/Case", "pause/resume", "robots/APIs/humans", "legacy UI", "version/rollback", "policy-as-code")),
    VendorProfile("LangChain", "LangGraph / Deep Agents / LangMem", ("stateful graphs", "durable checkpoints", "interrupts", "short/long-term memory", "middleware", "subagents", "sandbox")),
    VendorProfile("CrewAI", "Crews / Flows", ("role crews", "deterministic flows", "persistence/resume", "guardrails", "HITL", "deployment/traces")),
    VendorProfile("Pydantic", "Pydantic AI", ("typed agents", "structured output", "toolsets", "adaptive models", "MCP", "durable backends", "HITL")),
    VendorProfile("LlamaIndex", "Agents / Workflows", ("RAG/knowledge", "tools", "memory", "multi-agent", "planning", "workflows", "MCP")),
    VendorProfile("Kore.ai", "Artemis / Agent Management Platform", ("typed agent blueprint", "compile-time validation", "runtime policy outside LLM", "parallel agents", "audit", "auto-loop")),
    VendorProfile("Cognigy", "Agentic CX", ("handoff", "human escalation", "shared memory", "LLM fallback", "tools", "MCP", "voice/contact center")),
    VendorProfile("Botpress", "Autonomous Nodes / Workflows", ("autonomous nodes", "tools", "knowledge", "reusable workflows", "background workflows", "retries")),
    VendorProfile("Intercom", "Fin", ("RAG", "query refinement", "retrieval/reranking", "simulations", "batch tests", "answer ratings", "escalation")),
    VendorProfile("Sierra", "Agent OS", ("testing", "monitoring", "NL authoring", "release checks", "simulations", "split-traffic rollout")),
    VendorProfile("OpenAI", "GPT-6 Astra / Work / Codex", ("max-effort reasoning", "parallel subagent delegation", "searchable cross-window context", "computer use", "professional artifacts", "self-verification")),
    VendorProfile("Anthropic", "Claude 5 / Managed Agents", ("long-horizon autonomy", "dynamic tool search", "programmatic tool calling", "portable agent skills", "brain-hand separation", "context rehydration")),
    VendorProfile("Google", "Gemini 3.5 / Co-Scientist", ("native computer use", "1M-class long context", "multi-agent hypothesis evolution", "tool use", "local multimodal lane")),
    VendorProfile("SpaceXAI", "Grok 4.7 / Grok Bot", ("long-running agents", "always-on agent computers", "self-verification", "interactive visual work", "persistent teammate memory")),
    VendorProfile("Microsoft", "Copilot Studio Computer-Using Agents", ("adaptive UI automation", "credential-aware computer use", "multi-step workflows", "model choice", "resilient interface automation")),
)


def G(i: int, name: str, domain: str, sources: tuple[str, ...], mode: HarvestMode, binding: str, proof: str, dep: int = 1) -> CapabilityGene:
    return CapabilityGene(f"AGF-{i:03d}", name, domain, sources, mode, binding, proof, dep)


GENES: tuple[CapabilityGene, ...] = (
    G(1,"Typed Agent Blueprint","SPECIFICATION",("Kore.ai","Pydantic","Salesforce"),HarvestMode.COMPOSED_BY_FABRIC,"MissionIR + schema compiler","typed schema + authority-field rejection"),
    G(2,"Intent-to-Agent Architecture","SPECIFICATION",("Kore.ai","ServiceNow","Google","Salesforce"),HarvestMode.COMPOSED_BY_FABRIC,"N-OMEGA mission compiler + CFBE capability market","primary fruit + acceptance criteria compile"),
    G(3,"Supervisor / Collaborator Topology","ORCHESTRATION",("AWS","Microsoft","OpenAI","CrewAI"),HarvestMode.COMPOSED_BY_FABRIC,"N-Council + FDOF graph","independent roles + one mutating lead"),
    G(4,"Handoff Orchestration","ORCHESTRATION",("OpenAI","Microsoft","Cognigy"),HarvestMode.COMPOSED_BY_FABRIC,"FDOF transition handoff","identity/state/proof survive handoff"),
    G(5,"Concurrent Fan-Out / Join","ORCHESTRATION",("Microsoft","LangChain","CrewAI","Kore.ai"),HarvestMode.REUSE_VERIFIED,"FDOF read-only sidecars","bounded WIP + no overlapping mutation"),
    G(6,"Debate / Group-Chat Manager","ORCHESTRATION",("Microsoft","OpenAI","Anthropic"),HarvestMode.COMPOSED_BY_FABRIC,"N-Council adversarial deliberation","dissent preserved; no vote-based truth"),
    G(7,"Durable Checkpoint / Resume","DURABILITY",("LangChain","Microsoft","Google","Pydantic","UiPath"),HarvestMode.REUSE_VERIFIED,"SOL6.2/FDOF capsules","exact transition/idempotency restore"),
    G(8,"External Wait / Event Resume","DURABILITY",("Google","Pydantic","Botpress","UiPath"),HarvestMode.PROVIDER_GATED,"FDOF external-event wait","provider wake/readback",5),
    G(9,"Interrupt / Human Approval Resume","CONTROL",("LangChain","Microsoft","OpenAI","UiPath"),HarvestMode.COMPOSED_BY_FABRIC,"N-OMEGA authority gate","approval token + exact state resume"),
    G(10,"Short-Term Thread State","MEMORY",("OpenAI","LangChain","Google"),HarvestMode.REUSE_VERIFIED,"Local Bible / mission state","mission scope + bounded retention"),
    G(11,"Semantic/Episodic/Procedural Memory","MEMORY",("LangChain","AWS","Cognigy","LlamaIndex"),HarvestMode.COMPOSED_BY_FABRIC,"KDV/Bible learning projections","provenance + decay + conflict quarantine"),
    G(12,"Shared Team Memory Isolation","MEMORY",("Cognigy","AWS","LangChain"),HarvestMode.COMPOSED_BY_FABRIC,"Federation derivative state","least privilege + no secret propagation"),
    G(13,"MCP / A2A Tool Fabric","TOOLS",("OpenAI","Google","AWS","Pydantic","LlamaIndex","ServiceNow"),HarvestMode.COMPOSED_BY_FABRIC,"Federation tool registry/gateway","schema + identity + authority + readback"),
    G(14,"Semantic Tool Search","TOOLS",("AWS","OpenAI","ServiceNow"),HarvestMode.COMPOSED_BY_FABRIC,"Capability market + registry","tool selected by capability contract"),
    G(15,"Sandboxed Code Execution","EXECUTION",("OpenAI","Google","AWS","LangChain"),HarvestMode.PROVIDER_GATED,"isolated sandbox adapter","sandbox identity + egress + artifact readback",4),
    G(16,"Browser / Computer Use","EXECUTION",("OpenAI","AWS","UiPath"),HarvestMode.PROVIDER_GATED,"provider computer adapter","exact target/action/readback + rollback",5),
    G(17,"Legacy UI / RPA Bridge","EXECUTION",("UiPath","ServiceNow"),HarvestMode.PROVIDER_GATED,"RPA adapter","business transaction receipt + rollback",5),
    G(18,"Runtime Identity / Secret References","SECURITY",("AWS","OpenAI","Google","ServiceNow"),HarvestMode.REUSE_VERIFIED,"SOVARA secret-reference + workload identity","no literal secret + provider identity readback"),
    G(19,"Guardrails / Policy-as-Code","SECURITY",("OpenAI","UiPath","ServiceNow","Kore.ai"),HarvestMode.REUSE_VERIFIED,"ProofOS + RealityGuard + SOVARA policy","policy outside model authority"),
    G(20,"Compile-Time Agent Validation","SECURITY",("Kore.ai","Pydantic","Salesforce"),HarvestMode.COMPOSED_BY_FABRIC,"MissionIR static court","invalid tool/guardrail/handoff graph rejected"),
    G(21,"Trace / Span Observability","OBSERVABILITY",("OpenAI","AWS","Salesforce","CrewAI"),HarvestMode.REUSE_VERIFIED,"ProofOS trace + FDOF events","mission/agent/model/tool/provider correlation"),
    G(22,"Business Transaction Replay","OBSERVABILITY",("UiPath","Salesforce","Kore.ai"),HarvestMode.COMPOSED_BY_FABRIC,"EvidenceOps/Result Fabric","decision→tool→effect→readback reconstruction"),
    G(23,"Evaluation / Simulation / A-B Court","EVALUATION",("AWS","Salesforce","Intercom","Sierra","Google"),HarvestMode.COMPOSED_BY_FABRIC,"CFBE matched courts","frozen baselines + ground truth + tool sequences"),
    G(24,"Release Checks / Canary / Rollback","RELEASE",("Sierra","UiPath","GitHub","ServiceNow"),HarvestMode.COMPOSED_BY_FABRIC,"Airlock + bounded promotion","exact tested head + negative canary + rollback receipt"),
    G(25,"Adaptive Model / Provider Routing","ROUTING",("Pydantic","Cognigy","OpenRouter","AWS"),HarvestMode.REUSE_VERIFIED,"OpenRouter mesh + CFBE fitness","fresh capability/privacy/cost/provider health"),
    G(26,"Cost / Latency / Quality Pareto Governor","ROUTING",("OpenRouter","AWS","UiPath"),HarvestMode.REUSE_VERIFIED,"N-OMEGA RouteScore","finite budget + positive marginal value"),
    G(27,"Self-Correction / Replanning","METACOGNITION",("Anthropic","OpenAI","Google","Kore.ai"),HarvestMode.REUSE_VERIFIED,"N-OMEGA meta-actions + Failure-Win","positive reflection return-on-compute"),
    G(28,"Continuous Optimization / Auto-Loop","METACOGNITION",("Kore.ai","Intercom","AWS"),HarvestMode.COMPOSED_BY_FABRIC,"CFBE challenger tournaments","no self-promotion + prospective evidence"),
    G(29,"Knowledge / RAG / Re-Ranking","KNOWLEDGE",("LlamaIndex","Intercom","ServiceNow","Cognigy"),HarvestMode.COMPOSED_BY_FABRIC,"EvidenceOps/KDV retrieval","source hierarchy + freshness + contradiction"),
    G(30,"Omnichannel / Voice Agents","CX",("Cognigy","Intercom","Botpress","OpenAI"),HarvestMode.PROVIDER_GATED,"channel adapters","consent + channel identity + effect receipt",4),
    G(31,"Background Long-Running Workflows","DURABILITY",("Botpress","Microsoft","LangChain","UiPath"),HarvestMode.COMPOSED_BY_FABRIC,"GNS3 registry + FDOF runtime","single schedule authority + durable readback"),
    G(32,"Human Escalation / Role Switch","CONTROL",("Cognigy","Intercom","Microsoft","OpenAI"),HarvestMode.COMPOSED_BY_FABRIC,"N-OMEGA owner/SME escalation","reason + state packet + audit receipt"),
    G(33,"Privacy / Retention / ZDR Routing","SECURITY",("OpenRouter","OpenAI","ServiceNow","UiPath"),HarvestMode.REUSE_VERIFIED,"PrivacyEnvelope + provider envelope","privacy class before transmission"),
    G(34,"Effect Fencing / Idempotency","CONTROL",("Temporal-pattern","AWS-pattern","LangGraph-pattern"),HarvestMode.REUSE_VERIFIED,"FCAC + FDOF leases/fencing","one mutating lane + stale-worker rejection"),
    G(35,"Provider-Native Semantic Readback","PROOF",("OpenAI","AWS","Google","OpenRouter"),HarvestMode.REUSE_VERIFIED,"FDOF Proof + SOVARA semantic receipt","provider/model/nonce/effect identity readback"),
    G(36,"Owner-Value Measurement","VALUE",("UiPath","Salesforce","Intercom","Sierra"),HarvestMode.REUSE_VERIFIED,"FDOF Value + CFBE matched pairs","positive owner value for stable promotion"),
    G(37,"Independent Assurance / No Self-Promotion","GOVERNANCE",("Kore.ai","ServiceNow","OpenAI-pattern"),HarvestMode.REUSE_VERIFIED,"ProofOS/JARVIS/RealityGuard","builder cannot certify consequential success"),
    G(38,"Artifact Attestation / Provenance","GOVERNANCE",("GitHub","SLSA-pattern"),HarvestMode.REUSE_VERIFIED,"FACP-001 + Artifact Registry + Airlock","digest + source epoch + custody readback"),
    G(39,"Versioned Blueprint / Hot Rollback","RELEASE",("UiPath","Sierra","Salesforce","Kore.ai"),HarvestMode.COMPOSED_BY_FABRIC,"versioned mission contracts","immutable version + rollback target"),
    G(40,"Support Simulation / Quality Flywheel","CX",("Intercom","Sierra","Salesforce"),HarvestMode.COMPOSED_BY_FABRIC,"CFBE simulation + evidence ratings","offline simulation before live effect"),
    G(41,"Adaptive Reasoning Effort Controller","METACOGNITION",("OpenAI","Anthropic"),HarvestMode.COMPOSED_BY_FABRIC,"AIR effort governor + N-OMEGA RouteScore","effort changes only when marginal quality/value justifies cost"),
    G(42,"Searchable Cross-Window Context","MEMORY",("OpenAI","Anthropic"),HarvestMode.COMPOSED_BY_FABRIC,"Bible/KDV searchable mission window index","requirements/failures remain retrievable across compaction without canon drift"),
    G(43,"Deferred Tool Discovery / Schema Loading","TOOLS",("Anthropic","OpenAI","AWS"),HarvestMode.COMPOSED_BY_FABRIC,"Capability market + lazy tool schema loader","only eligible tools enter working context; authority unchanged"),
    G(44,"Programmatic Tool Orchestration","TOOLS",("Anthropic","OpenAI","Google"),HarvestMode.COMPOSED_BY_FABRIC,"sandbox/code-mode orchestration over typed tool gateway","loops/branches execute deterministically with bounded tool receipts"),
    G(45,"Portable Skill Capsules / Progressive Disclosure","TOOLS",("Anthropic","OpenAI","GitHub"),HarvestMode.COMPOSED_BY_FABRIC,"Federation skill registry + resource bundles","metadata-first selection; full instructions/resources load only on demand"),
    G(46,"Brain / Hands Runtime Decoupling","EXECUTION",("Anthropic","Microsoft","SpaceXAI"),HarvestMode.REUSE_VERIFIED,"MissionIR/FDOF brain + Genesis/provider execution hands","model replacement cannot widen effect authority or lose durable mission state"),
    G(47,"Persistent Always-On Agent Workspace","DURABILITY",("SpaceXAI","Anthropic","Microsoft"),HarvestMode.PROVIDER_GATED,"Genesis resident executor + FDOF durable mission runtime","survives chat loss/restart and resumes from checkpoint with provider/runtime readback",4),
    G(48,"Adaptive Computer-Use Control","EXECUTION",("OpenAI","Google","Microsoft","SpaceXAI"),HarvestMode.PROVIDER_GATED,"Windows/Computer-Use capability adapter","UI state sensed before action; exact effect and post-action state independently read back",5),
    G(49,"Multi-Agent Hypothesis Evolution","ORCHESTRATION",("Google","OpenAI","Anthropic"),HarvestMode.COMPOSED_BY_FABRIC,"N-Council + Formation hypothesis tournament","generate/debate/falsify/evolve while preserving minority hypotheses and evidence"),
    G(50,"Verification-First Self-Check","EVALUATION",("OpenAI","SpaceXAI","Anthropic"),HarvestMode.REUSE_VERIFIED,"ProofOS + Reality Judge + task-specific tests","agent must inspect observed outcome and tests before declaring completion"),
    G(51,"Harness Assumption Reaper","METACOGNITION",("OpenAI","Anthropic"),HarvestMode.COMPOSED_BY_FABRIC,"Harness Tournament + CFBE no-regression reaper","remove stale scaffolding only when matched court preserves or improves outcomes"),
    G(52,"Artifact-Native Professional Production","VALUE",("OpenAI","Anthropic","Microsoft"),HarvestMode.COMPOSED_BY_FABRIC,"Artifact Workspace + template/style contracts","finished document/spreadsheet/presentation matches task template and passes artifact verification"),
    G(53,"Local Multimodal Sovereign Lane","EXECUTION",("Google-open-model","LocalLLM","Federation"),HarvestMode.BUILD_ADDITIVE,"LocalLLM/OmniSurface local vision+voice+reasoning adapter","offline-capable multimodal task passes privacy/no-exfiltration and matched quality court",2),
    G(54,"Durable Async Job Handle / Poll-Push Continuation","DURABILITY",("OpenAI Background Responses","A2A","Microsoft Durable Task"),HarvestMode.COMPOSED_BY_FABRIC,"FDOF durable task handle + DeliveryJournal","client disconnect preserves one task/result identity; poll/push/readback cannot duplicate effects"),
    G(55,"Exact Run-State / Pending-Batch Reconciliation","DURABILITY",("OpenAI Agents RunState","Temporal","Microsoft Durable Task"),HarvestMode.REUSE_VERIFIED,"FDOF checkpoint + exact pending-batch tail hash","resume committed tool batch without re-execution; ambiguous history fails closed"),
    G(56,"TTL / Cache-Scope Tool Catalogue Currentness","TOOLS",("MCP 2026","Federation Capability Market","OpenAI/Anthropic tool discovery"),HarvestMode.COMPOSED_BY_FABRIC,"lazy tool registry + ttl/cache-scope currentness","cached tool/resource/schema list reused only inside declared TTL/scope and invalidated on capability/auth epoch"),
    G(57,"Stateful Agent Task / Artifact Resubscribe & Push","ORCHESTRATION",("A2A","OpenAI Background Responses","Google Agent Engine Sessions"),HarvestMode.COMPOSED_BY_FABRIC,"Mission Bus task/artifact adapter","stateful task survives disconnect; resubscribe/push returns same task/artifact identity and terminal state"),
    G(58,"Browser Offscreen Liveness / Singleflight Context","EXECUTION",("Chrome Offscreen API","Chrome runtime.getContexts","ChatBridge/BEF"),HarvestMode.BUILD_ADDITIVE,"ChatBridge offscreen supervisor + singleflight context registry","service-worker restart recreates at most one helper; no duplicate writer/effect and current context is observable",2),
    G(59,"Replay-Safe Durable Workflow Versioning","DURABILITY",("Temporal","Microsoft Durable Task","Google ADK durable integration"),HarvestMode.COMPOSED_BY_FABRIC,"SOL6.2/FDOF deterministic event-history + version gate","restart/redeploy replays deterministic history without repeating completed effects; incompatible version fails closed"),
    G(60,"Resource-Adaptive Worker Slots / Poller Autoscaling","ROUTING",("Temporal","Google Agent Runtime","Federation Execution Power Pools"),HarvestMode.COMPOSED_BY_FABRIC,"Execution Power Pool telemetry + adaptive slot supplier","concurrency follows backlog/CPU/memory/SLO without oversubscription, authority widening or starvation"),
    G(61,"Local Responses / Tools / MCP Runtime Compatibility","EXECUTION",("LM Studio","LocalLLM","OpenAI-compatible protocol"),HarvestMode.BUILD_ADDITIVE,"LocalLLM/OmniSurface Responses+tools+MCP adapter","local route supports model discovery, Responses/tool calls and MCP/stateful session contract under privacy/offline court",2),
    G(62,"Failure-Domain Placement / Disruption Budget","ROUTING",("Kubernetes topology spread","Kubernetes disruption budget","FUSE Portfolio V2"),HarvestMode.COMPOSED_BY_FABRIC,"Portfolio V2 failure-domain placement + maintenance budget","redundant routes are spread across proven independent domains and planned disruption cannot remove all terminal-critical capacity"),
    G(63,"OAuth Issuer / Dynamic-Client Mix-Up Hardening","SECURITY",("MCP 2026 OAuth","RFC 9207 pattern","Federation Auth Envelope"),HarvestMode.REUSE_VERIFIED,"provider-neutral OAuth issuer/application-type verifier","issuer and client application type are validated before code/token redemption; localhost/native redirects remain explicit and scoped"),
)


DOMAINS = frozenset(g.domain for g in GENES)


class AgenticFrontierCompiler:
    CORE = frozenset({"AGF-001","AGF-019","AGF-020","AGF-021","AGF-023","AGF-034","AGF-035","AGF-036","AGF-037","AGF-038"})

    def __init__(self, genes: Iterable[CapabilityGene] = GENES) -> None:
        genes = tuple(genes)
        self.genes = {g.gene_id: g for g in genes}
        if len(self.genes) != len(genes):
            raise ValueError("duplicate gene id")

    def validate(self) -> None:
        if len(VENDORS) < 22 or len(self.genes) < 63:
            raise ValueError("frontier coverage floor not met")
        required_domains = {"SPECIFICATION","ORCHESTRATION","DURABILITY","MEMORY","TOOLS","EXECUTION","SECURITY","CONTROL","OBSERVABILITY","EVALUATION","RELEASE","ROUTING","METACOGNITION","KNOWLEDGE","CX","PROOF","VALUE","GOVERNANCE"}
        if required_domains - DOMAINS:
            raise ValueError("missing benchmark dimensions")
        for g in self.genes.values():
            if not g.sources or not g.binding or not g.proof_gate:
                raise ValueError(f"incomplete gene: {g.gene_id}")

    def compile(self, mission: MissionProfile, weights: Mapping[str, float] | None = None) -> SuperstackPlan:
        self.validate()
        selected = set(self.CORE)
        selected.update(g.gene_id for g in self.genes.values() if g.domain in mission.domains)
        if mission.long_running:
            selected.update({"AGF-007","AGF-008","AGF-031","AGF-042","AGF-046","AGF-047","AGF-050","AGF-054","AGF-055","AGF-057","AGF-059","AGF-060"})
        if mission.multi_agent:
            selected.update({"AGF-003","AGF-004","AGF-005","AGF-006","AGF-012","AGF-049","AGF-050"})
        if mission.tool_heavy:
            selected.update({"AGF-013","AGF-014","AGF-043","AGF-044","AGF-045","AGF-056"})
        if mission.code_execution:
            selected.update({"AGF-015","AGF-059","AGF-060"})
        if mission.browser_or_computer:
            selected.update({"AGF-016","AGF-048","AGF-058"})
        if mission.legacy_ui:
            selected.add("AGF-017")
        if mission.customer_facing:
            selected.update({"AGF-029","AGF-030","AGF-032","AGF-040"})
        if mission.consequential:
            selected.update({"AGF-009","AGF-018","AGF-019","AGF-024","AGF-032","AGF-033","AGF-034","AGF-035","AGF-037","AGF-038","AGF-055","AGF-062","AGF-063"})
        if mission.requires_memory:
            selected.update({"AGF-010","AGF-011","AGF-012"})
        if mission.requires_dynamic_models:
            selected.update({"AGF-025","AGF-026","AGF-041","AGF-050"})
        if mission.requires_release:
            selected.update({"AGF-024","AGF-039","AGF-050","AGF-051","AGF-059","AGF-062"})
        if mission.requires_adaptive_effort:
            selected.add("AGF-041")
        if mission.requires_cross_window_context:
            selected.update({"AGF-042","AGF-050"})
        if mission.requires_dynamic_tools:
            selected.update({"AGF-043","AGF-044"})
        if mission.requires_portable_skills:
            selected.add("AGF-045")
        if mission.requires_persistent_agent:
            selected.update({"AGF-007","AGF-031","AGF-046","AGF-047","AGF-050","AGF-054","AGF-055","AGF-057","AGF-059","AGF-060"})
        if mission.requires_adaptive_computer_use:
            selected.update({"AGF-016","AGF-048","AGF-050"})
        if mission.requires_hypothesis_evolution:
            selected.update({"AGF-006","AGF-023","AGF-049","AGF-050"})
        if mission.requires_strict_self_verification:
            selected.add("AGF-050")
        if mission.requires_harness_simplification:
            selected.add("AGF-051")
        if mission.requires_artifact_production:
            selected.update({"AGF-038","AGF-052"})
        if mission.requires_local_multimodal:
            selected.update({"AGF-025","AGF-053","AGF-061"})
        if mission.requires_async_job_handle:
            selected.add("AGF-054")
        if mission.requires_exact_resume:
            selected.add("AGF-055")
        if mission.requires_tool_catalog_cache:
            selected.add("AGF-056")
        if mission.requires_async_task_delivery:
            selected.add("AGF-057")
        if mission.requires_browser_offscreen_liveness:
            selected.add("AGF-058")
        if mission.requires_replay_safe_versioning:
            selected.add("AGF-059")
        if mission.requires_adaptive_worker_capacity:
            selected.add("AGF-060")
        if mission.requires_local_openai_compat:
            selected.add("AGF-061")
        if mission.requires_failure_domain_spread:
            selected.add("AGF-062")
        if mission.requires_oauth_mixup_hardening:
            selected.add("AGF-063")

        ordered = sorted((self.genes[i] for i in selected), key=lambda g: (-g.score(weights), g.gene_id))
        proof = {"SOURCE_IDENTITY","TEST_OR_EVAL_RECEIPT","INDEPENDENT_ASSURANCE","ROLLBACK_OR_NO_EFFECT_BOUNDARY"}
        if any(g.mode is HarvestMode.PROVIDER_GATED for g in ordered):
            proof.update({"PROVIDER_IDENTITY","SEMANTIC_PROVIDER_READBACK"})
        if mission.consequential:
            proof.update({"ACTION_SPECIFIC_AUTHORITY","EFFECT_IDEMPOTENCY","POST_EFFECT_READBACK"})
        orchestration = ["PRIMARY_EXECUTION_MANAGER"]
        if mission.multi_agent:
            orchestration += ["INDEPENDENT_CHALLENGER","FALSIFIER","SPECIALIST_POOL"]
        if mission.long_running:
            orchestration.append("DURABLE_CHECKPOINT_RESUME")
        if mission.consequential:
            orchestration.append("HUMAN_OR_OWNER_GATE_WHERE_REQUIRED")
        return SuperstackPlan(
            mission_id=mission.mission_id,
            selected_gene_ids=tuple(g.gene_id for g in ordered),
            orchestration=tuple(orchestration),
            max_mutating_lanes=1,
            external_model_authority="PROPOSAL_ONLY",
            proof_required=tuple(sorted(proof)),
            route_score=round(sum(g.score(weights) for g in ordered) / len(ordered), 4),
        )


N_OMEGA_LIFECYCLE = (
    "CFBE_PREPASS",
    "N_COMPILE",
    "EXECUTE",
    "PROVIDER_OR_NATIVE_READBACK",
    "INDEPENDENT_ASSURANCE",
    "OWNER_VALUE_SCORE",
    "CFBE_POSTPASS",
    "PERSIST_TERMINAL_RECEIPT",
)


@dataclass(frozen=True, slots=True)
class NDirectivePlan:
    mission: SuperstackPlan
    lifecycle: tuple[str, ...]
    cfbe_role: str
    n_omega_role: str
    self_certification_allowed: bool
    stable_promotion_requires_owner_value: bool


def compile_n_directive(mission: MissionProfile, weights: Mapping[str, float] | None = None) -> NDirectivePlan:
    """Compile one N-OMEGA mission through the independent CFBE frontier governor.

    CFBE selects/challenges capability composition; N-OMEGA remains execution manager.
    The bridge never grants provider-effect authority or self-certification.
    """
    plan = AgenticFrontierCompiler().compile(mission, weights=weights)
    return NDirectivePlan(
        mission=plan,
        lifecycle=N_OMEGA_LIFECYCLE,
        cfbe_role="INDEPENDENT_BENCHMARK_CHALLENGE_EVOLUTION_GOVERNOR",
        n_omega_role="MISSION_COMPILER_EXECUTION_MANAGER",
        self_certification_allowed=False,
        stable_promotion_requires_owner_value=True,
    )


def frontier_summary() -> dict[str, object]:
    compiler = AgenticFrontierCompiler(); compiler.validate()
    modes = {m.value: sum(1 for g in GENES if g.mode is m) for m in HarvestMode}
    return {
        "schema": "N_OMEGA_AGENTIC_FRONTIER_V1",
        "vendor_reference_count": len(VENDORS),
        "capability_gene_count": len(GENES),
        "domain_count": len(DOMAINS),
        "modes": modes,
        "zero_unrouted": True,
        "one_mutating_lane": True,
        "external_model_authority": "PROPOSAL_ONLY",
        "stable_self_promotion_authorized": False,
        "provider_effect_authorized_by_benchmark": False,
        "n_omega_cfbe_integrated": True,
        "lifecycle": N_OMEGA_LIFECYCLE,
        "frontier_2026_gene_ids": tuple(f"AGF-{i:03d}" for i in range(41,64)),
        "clean_room_harvest": True,
        "proprietary_weights_imported": False,
        "undocumented_vendor_internals_imported": False,
    }
