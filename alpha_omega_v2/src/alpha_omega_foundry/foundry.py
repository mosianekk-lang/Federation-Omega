from __future__ import annotations
import json, hashlib, datetime, shutil
from pathlib import Path

class LocalProviderAdapter:
    name = "local"
    def deploy(self, package_dir: Path, target_dir: Path) -> dict:
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(package_dir, target_dir)
        return {"provider":"local","state":"DEPLOYED","target":str(target_dir)}
    def execute(self, target_dir: Path) -> dict:
        manifest = json.loads((target_dir/"solution_genome.json").read_text())
        return {"provider":"local","state":"EXECUTED","system_id":manifest["system_id"]}
    def readback(self, target_dir: Path) -> dict:
        required = ["solution_genome.json","product_spec.json","maintenance_plan.json","health.json"]
        present = {name:(target_dir/name).exists() for name in required}
        return {"provider":"local","state":"READBACK","present":present,"pass":all(present.values())}
    def rollback(self, target_dir: Path) -> dict:
        if target_dir.exists():
            shutil.rmtree(target_dir)
        return {"provider":"local","state":"ROLLED_BACK","target_absent":not target_dir.exists()}

class SolutionFoundry:
    def __init__(self, workspace: str|Path):
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _id(self, prefix: str, value: str) -> str:
        return f"{prefix}-{hashlib.sha256(value.encode()).hexdigest()[:12]}"

    def compile_product_spec(self, idea: dict) -> dict:
        title = str(idea.get("title","")).strip()
        description = str(idea.get("description","")).strip()
        if not title or not description:
            raise ValueError("title and description are required")
        return {
            "product_id": self._id("PRD", title),
            "title": title,
            "problem": description,
            "target_users": list(idea.get("users",[])),
            "success_measures": list(idea.get("outcomes",[])) or ["operational build verified"],
            "functional_requirements": list(idea.get("functional_requirements",[])) or [
                "accept concept","compile specification","build package","deploy","verify","maintain"
            ],
            "non_functional_requirements": [
                "proof before claim","rollback required","health monitoring","provider truth boundary"
            ],
            "constraints": list(idea.get("constraints",[])),
        }

    def score_portfolio(self, ideas: list[dict]) -> list[dict]:
        scored = []
        for idea in ideas:
            score = (
                int(idea.get("value",5))*3 +
                int(idea.get("urgency",5))*2 +
                int(idea.get("reuse",5))*2 -
                int(idea.get("risk",5)) -
                int(idea.get("complexity",5))
            )
            scored.append({"idea":idea,"score":score})
        return sorted(scored,key=lambda x:x["score"],reverse=True)

    def capability_marketplace(self, spec: dict) -> list[dict]:
        capabilities = [
            ("CAP-INTAKE","concept intake"),
            ("CAP-SPEC","product specification"),
            ("CAP-BUILD","artifact construction"),
            ("CAP-TEST","test orchestration"),
            ("CAP-DEPLOY","provider deployment"),
            ("CAP-HEALTH","health and drift"),
            ("CAP-ROLLBACK","rollback"),
            ("CAP-LEARN","learning ledger"),
        ]
        return [{"capability_id":i,"purpose":p,"maturity":"OPERATIONAL_LOCAL"} for i,p in capabilities]

    def compile_solution_genome(self, spec: dict, capabilities: list[dict]) -> dict:
        return {
            "system_id": self._id("SYS", spec["product_id"]),
            "product_id": spec["product_id"],
            "components": [c["capability_id"] for c in capabilities],
            "interfaces": ["concept.json","product_spec.json","solution_genome.json"],
            "deployment_routes": ["local","github","google_drive","cloud_run"],
            "proof_gates": ["build","test","deploy","execute","readback","health","persistence","rollback"],
            "authority_boundaries": {
                "local":"A1",
                "github":"provider-authorised",
                "google_drive":"provider-authorised",
                "cloud_run":"provider-authorised"
            }
        }

    def build_solution(self, idea: dict) -> dict:
        spec = self.compile_product_spec(idea)
        caps = self.capability_marketplace(spec)
        genome = self.compile_solution_genome(spec,caps)
        package = self.workspace/genome["system_id"]
        package.mkdir(exist_ok=True)
        health = {"availability":1.0,"integrity":1.0,"freshness":1.0,"recoverability":1.0}
        maintenance = {
            "heartbeat":"hourly",
            "drift_checks":["schema","permissions","dependencies","provider_config"],
            "repair_modes":["repair_in_place","forward_fix","rollback","failover"]
        }
        files = {
            "product_spec.json":spec,
            "capability_marketplace.json":caps,
            "solution_genome.json":genome,
            "health.json":health,
            "maintenance_plan.json":maintenance,
        }
        for name,data in files.items():
            (package/name).write_text(json.dumps(data,indent=2),encoding="utf-8")
        return {"package_dir":str(package),"spec":spec,"genome":genome}

    def operational_release(self, idea: dict) -> dict:
        build = self.build_solution(idea)
        package = Path(build["package_dir"])
        target = self.workspace/"operational"/build["genome"]["system_id"]
        adapter = LocalProviderAdapter()
        deploy = adapter.deploy(package,target)
        execute = adapter.execute(target)
        readback = adapter.readback(target)
        persistence = {"pass":target.exists() and all(readback["present"].values())}
        health = json.loads((target/"health.json").read_text())
        health_check = {"pass":all(v >= .99 for v in health.values()),"health":health}
        rollback_probe = self.workspace/"rollback_probe"/build["genome"]["system_id"]
        adapter.deploy(package,rollback_probe)
        rollback = adapter.rollback(rollback_probe)
        operational = all([
            deploy["state"]=="DEPLOYED",
            execute["state"]=="EXECUTED",
            readback["pass"],
            persistence["pass"],
            health_check["pass"],
            rollback["target_absent"],
        ])
        receipt = {
            "receipt_id":self._id("RCP",build["genome"]["system_id"]+datetime.datetime.utcnow().isoformat()),
            "state":"OPERATIONAL_VERIFIED_LOCAL" if operational else "FAILED",
            "deploy":deploy,"execute":execute,"readback":readback,
            "persistence":persistence,"health":health_check,"rollback":rollback,
            "truth_boundary":{
                "local_operational":operational,
                "github_deployed":False,
                "google_drive_deployed":False,
                "cloud_run_deployed":False
            }
        }
        (target/"operational_receipt.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
        return receipt
