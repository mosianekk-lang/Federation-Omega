from __future__ import annotations
import json, hashlib, datetime
from pathlib import Path
from .models import Concept, WorkPacket, BuildPlan, Stage

class AlphaOmegaEngine:
    def __init__(self, workspace: str | Path):
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.receipts = self.workspace / "receipts"
        self.receipts.mkdir(exist_ok=True)

    def _id(self, prefix: str, payload: str) -> str:
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
        return f"{prefix}-{digest}"

    def compile_concept(self, raw: dict) -> Concept:
        title = str(raw.get("title", "")).strip()
        description = str(raw.get("description", "")).strip()
        if not title or not description:
            raise ValueError("title and description are required")
        return Concept(title=title, description=description, users=list(raw.get("users", [])), outcomes=list(raw.get("outcomes", [])), constraints=list(raw.get("constraints", [])), preferred_surfaces=list(raw.get("preferred_surfaces", [])))

    def discover_capabilities(self, concept: Concept) -> dict:
        text = f"{concept.title} {concept.description}".lower()
        inferred = []
        for key, cap in [("api", "API service"), ("dashboard", "web dashboard"), ("workflow", "workflow orchestrator"), ("document", "document generation"), ("email", "email integration"), ("data", "data store and schema"), ("agent", "agent orchestration"), ("mobile", "mobile interface"), ("report", "reporting layer")]:
            if key in text:
                inferred.append(cap)
        if not inferred:
            inferred = ["core service", "operator interface", "evidence and logging layer"]
        return {"reuse_candidates": concept.preferred_surfaces, "required_capabilities": inferred, "missing_capabilities": []}

    def synthesize_architecture(self, concept: Concept, discovery: dict) -> dict:
        return {
            "system_name": self._id("SYS", concept.title),
            "layers": [
                {"name": "intake", "responsibility": "validate and normalize concept"},
                {"name": "orchestrator", "responsibility": "decompose and route work"},
                {"name": "build", "responsibility": "generate artifacts and integrations"},
                {"name": "test", "responsibility": "functional, regression, security and rollback tests"},
                {"name": "deploy", "responsibility": "route to authorised provider"},
                {"name": "operate", "responsibility": "health, drift and maintenance"},
                {"name": "proof", "responsibility": "receipts, readback and maturity state"}],
            "capabilities": discovery["required_capabilities"],
            "invariants": ["proof_before_claim", "owner_final_authority_for_consequential_actions", "snapshot_before_material_mutation", "rollback_required", "no_prototype_as_operational_claim"]}

    def decompose(self, concept: Concept, architecture: dict) -> list[WorkPacket]:
        stages = [
            (Stage.DISCOVERY, "Discover reusable capabilities and authorised surfaces", "capability map"),
            (Stage.DECOMPOSITION, "Split concept into independently verifiable workstreams", "workstream graph"),
            (Stage.ARCHITECTURE, "Compile target architecture and interfaces", "architecture specification"),
            (Stage.BUILD, "Build minimum complete operational components", "working artifacts"),
            (Stage.TEST, "Run functional, regression, security and rollback tests", "test receipts"),
            (Stage.DEPLOY, "Deploy to the strongest authorised surface", "provider deployment receipt"),
            (Stage.VERIFY, "Read back target state and verify health and persistence", "verification receipt"),
            (Stage.OPERATE, "Start monitored operation and drift detection", "operational health state"),
            (Stage.MAINTAIN, "Schedule maintenance, upgrades and recovery", "maintenance policy")]
        packets, previous = [], []
        for idx, (stage, objective, output) in enumerate(stages, 1):
            pid = f"PKT-{idx:02d}-{self._id('X', objective)[2:]}"
            packets.append(WorkPacket(packet_id=pid, stage=stage, objective=objective, inputs=[concept.title] if idx == 1 else [previous[-1]], outputs=[output], proof_gate=f"{stage.value}_READBACK", authority="A0" if stage in {Stage.DISCOVERY, Stage.DECOMPOSITION, Stage.ARCHITECTURE, Stage.TEST} else "A1_OR_PROVIDER_GATED", dependencies=previous[-1:] if previous else []))
            previous.append(pid)
        return packets

    def choose_deployment_routes(self, concept: Concept) -> list[dict]:
        surfaces = concept.preferred_surfaces or ["local_package", "google_drive", "github", "cloud_run"]
        return [{"priority": i, "surface": surface, "authority_required": "provider-specific", "proof_required": ["deployment_receipt", "execution_log", "target_readback", "health_check", "rollback_test"]} for i, surface in enumerate(surfaces, 1)]

    def build_plan(self, raw: dict) -> BuildPlan:
        concept = self.compile_concept(raw)
        discovery = self.discover_capabilities(concept)
        architecture = self.synthesize_architecture(concept, discovery)
        packets = self.decompose(concept, architecture)
        routes = self.choose_deployment_routes(concept)
        maintenance = {"health_checks": ["availability", "latency", "error_rate", "proof_freshness"], "drift_checks": ["schema", "permissions", "dependencies", "provider_config"], "maintenance_modes": ["repair_in_place", "forward_fix", "rollback", "provider_failover"]}
        truth = {"plan_created": True, "artifacts_built": False, "provider_deployed": False, "operational_verified": False}
        return BuildPlan(concept, packets, architecture, routes, maintenance, truth)

    def execute_local_build(self, plan: BuildPlan) -> dict:
        build_dir = self.workspace / plan.architecture["system_name"]
        build_dir.mkdir(exist_ok=True)
        (build_dir / "architecture.json").write_text(json.dumps(plan.architecture, indent=2), encoding="utf-8")
        (build_dir / "work_packets.json").write_text(json.dumps([p.__dict__ | {"stage": p.stage.value} for p in plan.packets], indent=2), encoding="utf-8")
        (build_dir / "maintenance.json").write_text(json.dumps(plan.maintenance_plan, indent=2), encoding="utf-8")
        (build_dir / "README.md").write_text(f"# {plan.concept.title}\n\n{plan.concept.description}\n\nGenerated by Alpha→Omega Turnkey Engine.\n", encoding="utf-8")
        plan.truth_boundary["artifacts_built"] = True
        receipt = {"receipt_id": self._id("RCP", plan.architecture["system_name"] + datetime.datetime.now(datetime.UTC).isoformat()), "timestamp_utc": datetime.datetime.now(datetime.UTC).isoformat(), "state": "LOCAL_OPERATIONAL_PACKAGE_BUILT", "build_dir": str(build_dir), "truth_boundary": plan.truth_boundary}
        (self.receipts / f"{receipt['receipt_id']}.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        return receipt
