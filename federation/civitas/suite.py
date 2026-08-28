from __future__ import annotations

"""Federation Ω CIVITAS integrated product/service suite."""

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from .adapters import AdapterRegistry
from .causal import CausalFederationTwin
from .civilization import CivilizationFabric
from .civitas import InstitutionalConstitution, CivitasInstitution
from .contracts import (
    CivitasError,
    MaturityEvidence,
    MaturityStage,
    ProofLevel,
    ProofRef,
    SCHEMA,
    VERSION,
    digest,
    safe_id,
)
from .ecology import CognitiveEcologyMarket, CognitiveInstitution
from .genesis import ArchitectureGenomeRegistry, CapabilityFoundry
from .metabolism import FederationMetabolism, ResourceBudget, StrategicPortfolioBrain


@dataclass(frozen=True)
class ServiceDefinition:
    service_id: str
    name: str
    layer: str
    purpose: str
    capabilities: tuple[str, ...]
    dependencies: tuple[str, ...]
    proof_requirements: tuple[str, ...]
    maturity_ceiling: MaturityStage = MaturityStage.DETERMINISTIC_TESTED
    authority_ceiling: str = "A1_INTERNAL"
    external_effects: int = 0

    def validate(self) -> "ServiceDefinition":
        safe_id(self.service_id, "service_id")
        if not self.name.strip() or not self.layer.strip() or not self.purpose.strip():
            raise ValueError("service name, layer and purpose required")
        if not self.capabilities or not self.proof_requirements:
            raise ValueError("service capabilities and proof requirements required")
        if self.authority_ceiling != "A1_INTERNAL" or self.external_effects:
            raise CivitasError("service definition cannot create provider authority/effects")
        return self


@dataclass(frozen=True)
class ProductBundle:
    product_id: str
    name: str
    target_users: tuple[str, ...]
    outcome: str
    service_ids: tuple[str, ...]
    delivery_mode: str
    commercial_state: str = "DESIGNED_INTERNAL"
    external_launch_authorized: bool = False

    def validate(self, service_ids: set[str]) -> "ProductBundle":
        safe_id(self.product_id, "product_id")
        if not self.name.strip() or not self.target_users or not self.outcome.strip():
            raise ValueError("product name, target users and outcome required")
        unknown = set(self.service_ids).difference(service_ids)
        if unknown:
            raise CivitasError("product references unknown service: " + sorted(unknown)[0])
        if self.external_launch_authorized:
            raise CivitasError("catalog definition cannot authorize external launch")
        return self


@dataclass(frozen=True)
class DeploymentReceipt:
    suite_id: str
    deployment_mode: str
    service_count: int
    product_count: int
    claimed_maturity: str
    justified_maturity: str
    tests_passed: bool
    local_runtime_readback: bool
    provider_runtime_proven: bool
    provider_effects: int
    authority_created: bool
    proof_refs: tuple[str, ...]
    truth_boundary: Mapping[str, Any]

    @property
    def receipt_sha256(self) -> str:
        return digest(asdict(self))


class ServiceCatalog:
    def __init__(self, services: Sequence[ServiceDefinition], products: Sequence[ProductBundle]) -> None:
        self.services: dict[str, ServiceDefinition] = {}
        for service in services:
            service.validate()
            if service.service_id in self.services:
                raise CivitasError("duplicate service id")
            self.services[service.service_id] = service
        self.products: dict[str, ProductBundle] = {}
        ids = set(self.services)
        for product in products:
            product.validate(ids)
            if product.product_id in self.products:
                raise CivitasError("duplicate product id")
            self.products[product.product_id] = product

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "services": tuple(asdict(item) for item in self.services.values()),
            "products": tuple(asdict(item) for item in self.products.values()),
        }


class OperatorQueryEngine:
    """Compact explanation plane for operator questions."""

    def __init__(self, suite: "FederationCivitasSuite") -> None:
        self.suite = suite

    def answer(self, question: str) -> Mapping[str, Any]:
        text = str(question).strip().lower()
        if not text:
            raise ValueError("question required")
        if "matur" in text or "fully established" in text:
            answer = {
                "answer": "The suite is source/local-runtime shadow capable; provider runtime and FULLY_ESTABLISHED maturity require separate provider, rollback, resilience and soak proof.",
                "provider_runtime_proven": False,
                "fully_established": False,
            }
        elif "what changed" in text or "new" in text:
            answer = {
                "answer": "CIVITAS adds proof-preserving sensors, causal twin, strategic metabolism, capability genesis, institutional court, ecology market, compounding, anti-entropy and succession above Living State.",
                "service_ids": tuple(self.suite.catalog.services),
            }
        elif "weak" in text or "spof" in text or "fragil" in text:
            answer = {
                "answer": "Weakness must be derived from current Living State dependency/readback evidence; the suite will not invent a weakest dependency without observations.",
                "required_input": "current dependency graph plus proof-fresh node state",
            }
        elif "stale" in text or "fresh" in text:
            answer = {
                "answer": "Freshness is a property of the source proof and TTL; adapters preserve it and never infer health from missing visibility.",
                "rule": "provider/source evidence outranks projections; missing visibility is UNKNOWN/NOT_EXPOSED, not healthy",
            }
        elif "build next" in text or "capability" in text:
            answer = {
                "answer": "Use REUSE → EXTEND → COMPOSE → NEW LAST, then Capability Genesis stages through regression, red team, shadow, value and promotion eligibility.",
                "foundry_stage_count": 9,
            }
        else:
            answer = {
                "answer": "Question recognized at the operator plane, but a proof-bearing Living State snapshot is required for mission-specific conclusions.",
                "supported_queries": (
                    "what changed", "what is stale", "what is the weakest dependency",
                    "what capability should be built next", "what is the current maturity",
                ),
            }
        body = {
            "schema": "FEDERATION-CIVITAS-OPERATOR-QUERY-V1",
            "question": question,
            **answer,
            "external_effects": 0,
            "authority_created": False,
        }
        return {**body, "receipt_sha256": digest(body)}


class FederationCivitasSuite:
    SUITE_ID = "FEDERATION-OMEGA-CIVITAS-SUITE-V1"

    def __init__(self, *, owner_root: str = "Kim-Kagiso-Mosiane") -> None:
        self.adapters = AdapterRegistry.default()
        self.causal_twin = CausalFederationTwin()
        self.genomes = ArchitectureGenomeRegistry()
        self.foundry = CapabilityFoundry(self.genomes)
        self.civilization = CivilizationFabric()
        self.constitution = InstitutionalConstitution(
            "CIVITAS-CONSTITUTION-V1",
            owner_root,
            "maximize lawful, proof-bound Federation capability while reducing complexity and owner burden",
        )
        self.institution = CivitasInstitution(self.constitution)
        self.catalog = self._catalog()
        self.query_engine = OperatorQueryEngine(self)

    @staticmethod
    def _services() -> tuple[ServiceDefinition, ...]:
        common = ("source/readback proof", "zero external effect", "no authority inheritance")
        return (
            ServiceDefinition("SVC-OBSERVATION", "Proof-Preserving Observation Service", "SENSORS", "Normalize provider, source, route, context, learning and benchmark observations without evidence upgrade.", ("proof ceiling", "secret rejection", "transactional handoff"), ("Living State ingress",), common),
            ServiceDefinition("SVC-CAUSAL-TWIN", "Causal Federation Twin", "WORLD_MODEL", "Separate correlation, hypotheses, replicated causation and rejected explanations.", ("causal gates", "counterfactual topology", "falsifier design", "precursor signals"), ("SVC-OBSERVATION",), common + ("independent replication",)),
            ServiceDefinition("SVC-METABOLISM", "Federation Metabolism", "RESOURCE_ECONOMY", "Allocate compute, tokens, money, latency, storage, proof effort and owner attention under reserve.", ("reserve protection", "feature rent", "anti-waste"), ("SVC-OBSERVATION",), common),
            ServiceDefinition("SVC-PORTFOLIO", "Strategic Portfolio Brain", "STRATEGY", "Choose which missions should exist and which shared investment unlocks the portfolio.", ("Pareto portfolio", "dependency unlock", "multi-horizon priority"), ("SVC-METABOLISM", "SVC-CAUSAL-TWIN"), common),
            ServiceDefinition("SVC-GENESIS", "Capability Genesis Foundry", "CAPABILITY_FACTORY", "Manufacture missing capabilities through reuse-first evidence-bearing stages.", ("architecture genome", "strict lifecycle", "shadow/value gate"), ("SVC-PORTFOLIO",), common + ("regression and red-team proof",)),
            ServiceDefinition("SVC-CIVITAS", "Ω-CIVITAS Cognitive Institution", "INSTITUTION", "Compile temporary cognitive organizations and independently govern decisions.", ("organization compiler", "constitutional court", "multi-timescale organization"), ("SVC-GENESIS", "SVC-PORTFOLIO"), common + ("four-role independent court",)),
            ServiceDefinition("SVC-ECOLOGY", "Ω-ECOLOGY Cognitive Market", "ECOLOGY", "Coordinate multiple sovereign cognitive institutions through eligibility-first competition and cooperation.", ("technology market", "champion/shadow", "sanitized gene exchange"), ("SVC-CIVITAS",), common + ("receiver-local proof",)),
            ServiceDefinition("SVC-CIVILIZATION", "Ω-CIVILIZATION Capability Compounder", "CIVILIZATION", "Close need-to-diffusion capability loops and improve the improvement mechanism.", ("compounding loop", "anti-entropy", "succession"), ("SVC-ECOLOGY", "SVC-GENESIS"), common + ("positive measured value",)),
            ServiceDefinition("SVC-QUERY", "Operator Query & Explanation", "OPERATOR", "Answer why, what changed, what is stale, what blocks and what should be built next.", ("explanation", "truth boundary", "counterfactual trace"), ("SVC-OBSERVATION", "SVC-PORTFOLIO"), common),
            ServiceDefinition("SVC-PREVENTION", "Predictive Failure Prevention", "IMMUNE_SYSTEM", "Detect proof decay, repeated near misses, failure-domain concentration and context exhaustion before failure.", ("precursor signatures", "prewarm", "checkpoint/reroute proposals"), ("SVC-CAUSAL-TWIN", "SVC-OBSERVATION"), common),
            ServiceDefinition("SVC-FORGE", "Ω-Forge Product & Service Factory", "PRODUCT_FACTORY", "Compose validated capabilities into deployable product genomes and vertical service bundles.", ("product genome", "vertical completion", "service blueprint"), ("SVC-GENESIS", "SVC-CIVITAS"), common),
            ServiceDefinition("SVC-SUCCESSION", "Institutional Succession & Recovery", "CONTINUITY", "Replace providers, runtimes and systems without losing memory, evidence, rollback or institutional identity.", ("archive-first succession", "rollback", "observation window"), ("SVC-CIVILIZATION",), common + ("successor shadow proof",)),
        )

    @staticmethod
    def _products() -> tuple[ProductBundle, ...]:
        return (
            ProductBundle("PRD-FEDERATION-CONTROL", "Federation Intelligence Control Plane", ("Federation owner", "operators", "architects"), "Proof-aware estate observation, strategy, capability formation and institutional coordination.", ("SVC-OBSERVATION", "SVC-CAUSAL-TWIN", "SVC-METABOLISM", "SVC-PORTFOLIO", "SVC-CIVITAS", "SVC-QUERY"), "PRIVATE_CONTROL_PLANE"),
            ProductBundle("PRD-LIVING-OBSERVATORY", "Living Estate Observatory", ("operations", "assurance", "governance"), "Current proof-fresh view of capabilities, providers, routes, failures, missions, context and debt.", ("SVC-OBSERVATION", "SVC-QUERY", "SVC-PREVENTION"), "PRIVATE_DASHBOARD_API"),
            ProductBundle("PRD-CAPABILITY-FOUNDRY", "Capability Foundry Studio", ("engineering", "R&D", "system architects"), "Reuse-first capability and product generation with regression, red team, shadow and value gates.", ("SVC-GENESIS", "SVC-FORGE", "SVC-SUCCESSION"), "PRIVATE_ENGINEERING_SERVICE"),
            ProductBundle("PRD-INSTITUTIONAL-MESH", "Cognitive Institution & Ecology Mesh", ("multi-system programmes", "mission leaders"), "Temporary cognitive organizations and a market of cooperating sovereign institutions.", ("SVC-CIVITAS", "SVC-ECOLOGY", "SVC-CIVILIZATION"), "PRIVATE_MISSION_SERVICE"),
            ProductBundle("PRD-EVIDENCEOPS-RAPID", "EvidenceOps Rapid Case Intelligence", ("legal teams", "unions", "case owners"), "Source-linked timelines, contradiction analysis, issue matrices and human-reviewed decision support.", ("SVC-OBSERVATION", "SVC-CAUSAL-TWIN", "SVC-CIVITAS", "SVC-QUERY"), "HUMAN_REVIEWED_SERVICE_TEMPLATE"),
            ProductBundle("PRD-AI-GOVERNANCE", "AI Governance & Agent Assurance", ("enterprises", "public institutions", "AI teams"), "Independent proof, maturity, authority, drift and failure review for AI systems and agent estates.", ("SVC-OBSERVATION", "SVC-PREVENTION", "SVC-CIVITAS", "SVC-SUCCESSION"), "ASSURANCE_SERVICE_TEMPLATE"),
            ProductBundle("PRD-CAPITAL-INTELLIGENCE", "Capital Intelligence & Execution Assurance", ("owner capital", "quant teams", "risk functions"), "Evidence-bound strategy research, route competition, risk controls and separate execution admission.", ("SVC-CAUSAL-TWIN", "SVC-METABOLISM", "SVC-PORTFOLIO", "SVC-CIVITAS"), "RESEARCH_AND_ASSURANCE_TEMPLATE"),
            ProductBundle("PRD-CREATIVE-COMMERCE", "Creative Product & Commerce Foundry", ("creators", "fashion businesses", "digital studios"), "Product-genome design, experiment portfolios, creative production and measured commercial learning.", ("SVC-GENESIS", "SVC-FORGE", "SVC-ECOLOGY"), "CREATIVE_SERVICE_TEMPLATE"),
        )

    @classmethod
    def _catalog(cls) -> ServiceCatalog:
        return ServiceCatalog(cls._services(), cls._products())

    def metabolism(self, budget: ResourceBudget) -> FederationMetabolism:
        return FederationMetabolism(budget)

    def portfolio_brain(self, budget: ResourceBudget) -> StrategicPortfolioBrain:
        return StrategicPortfolioBrain(self.metabolism(budget))

    def ecology(self, institutions: Sequence[CognitiveInstitution]) -> CognitiveEcologyMarket:
        return CognitiveEcologyMarket(institutions)

    def query(self, question: str) -> Mapping[str, Any]:
        return self.query_engine.answer(question)

    def manifest(self) -> Mapping[str, Any]:
        body = {
            "schema": SCHEMA,
            "version": VERSION,
            "suite_id": self.SUITE_ID,
            "service_count": len(self.catalog.services),
            "product_count": len(self.catalog.products),
            "services": tuple(asdict(item) for item in self.catalog.services.values()),
            "products": tuple(asdict(item) for item in self.catalog.products.values()),
            "authority_ceiling": "A1_INTERNAL",
            "external_effects": 0,
            "truth_boundary": {
                "source_presence_is_not_provider_deployment": True,
                "local_runtime_is_not_provider_runtime": True,
                "tests_are_not_behavioral_provider_proof": True,
                "provider_effect_admission_remains_sovara_separate": True,
                "fully_established_requires_exact_runtime_provider_resilience_and_soak_proof": True,
            },
        }
        return {**body, "manifest_sha256": digest(body)}

    def shadow_deploy(self, evidence: MaturityEvidence) -> DeploymentReceipt:
        justified = evidence.assert_no_inflation()
        if evidence.claimed_stage.value not in {stage.value for stage in MaturityStage}:
            raise CivitasError("unsupported maturity claim")
        return DeploymentReceipt(
            suite_id=self.SUITE_ID,
            deployment_mode="INTERNAL_SHADOW_LOCAL_RUNTIME",
            service_count=len(self.catalog.services),
            product_count=len(self.catalog.products),
            claimed_maturity=evidence.claimed_stage.value,
            justified_maturity=justified.value,
            tests_passed=evidence.tests_passed,
            local_runtime_readback=evidence.runtime_readback,
            provider_runtime_proven=evidence.provider_readback,
            provider_effects=0,
            authority_created=False,
            proof_refs=tuple(ref.proof_ref for ref in evidence.proof_refs),
            truth_boundary={
                "provider_runtime_proven": evidence.provider_readback,
                "production_traffic_changed": False,
                "external_authority_created": False,
                "separate_sovara_effect_admission_required": True,
            },
        )


__all__ = [
    "ServiceDefinition", "ProductBundle", "DeploymentReceipt", "ServiceCatalog",
    "OperatorQueryEngine", "FederationCivitasSuite",
]
