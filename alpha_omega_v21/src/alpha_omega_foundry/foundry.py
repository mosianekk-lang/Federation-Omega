from __future__ import annotations

from pathlib import Path
import datetime
import hashlib
import json

from .operations import OperationsFabric
from .providers import LocalProviderAdapter, ReleaseArtifactAdapter


class SolutionFoundry:
    def __init__(self, workspace: str | Path):
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.operations = OperationsFabric(self.workspace / "operations")

    def _id(self, prefix: str, value: str) -> str:
        return f"{prefix}-{hashlib.sha256(value.encode()).hexdigest()[:12]}"

    def compile_product_spec(self, idea: dict) -> dict:
        title = str(idea.get("title", "")).strip()
        description = str(idea.get("description", "")).strip()
        if not title or not description:
            raise ValueError("title and description are required")
        return {
            "product_id": self._id("PRD", title),
            "title": title,
            "problem": description,
            "target_users": list(idea.get("users", [])),
            "success_measures": list(idea.get("outcomes", [])) or ["operational build verified"],
            "functional_requirements": list(idea.get("functional_requirements", [])) or [
                "accept concept",
                "compile specification",
                "build package",
                "deploy",
                "verify",
                "maintain",
            ],
            "non_functional_requirements": [
                "proof before claim",
                "rollback required",
                "health monitoring",
                "provider truth boundary",
            ],
            "constraints": list(idea.get("constraints", [])),
        }

    def score_portfolio(self, ideas: list[dict]) -> list[dict]:
        ranked = []
        for idea in ideas:
            score = (
                int(idea.get("value", 5)) * 3
                + int(idea.get("urgency", 5)) * 2
                + int(idea.get("reuse", 5)) * 2
                - int(idea.get("risk", 5))
                - int(idea.get("complexity", 5))
            )
            ranked.append({"idea": idea, "score": score})
        return sorted(ranked, key=lambda item: item["score"], reverse=True)

    def capability_marketplace(self) -> list[dict]:
        capabilities = [
            ("CAP-INTAKE", "concept intake"),
            ("CAP-SPEC", "product specification"),
            ("CAP-BUILD", "artifact construction"),
            ("CAP-TEST", "test orchestration"),
            ("CAP-DEPLOY", "provider deployment"),
            ("CAP-HEALTH", "health and drift"),
            ("CAP-ROLLBACK", "rollback"),
            ("CAP-LEARN", "learning ledger"),
            ("CAP-RETIRE", "retirement control"),
        ]
        return [
            {"capability_id": identifier, "purpose": purpose, "maturity": "OPERATIONAL_LOCAL"}
            for identifier, purpose in capabilities
        ]

    def compile_solution_genome(self, spec: dict, capabilities: list[dict]) -> dict:
        return {
            "system_id": self._id("SYS", spec["product_id"]),
            "product_id": spec["product_id"],
            "components": [item["capability_id"] for item in capabilities],
            "interfaces": ["concept.json", "product_spec.json", "solution_genome.json"],
            "deployment_routes": [
                "local",
                "github_actions_artifact",
                "google_drive_manifest",
                "cloud_run",
            ],
            "proof_gates": [
                "discover",
                "authority",
                "snapshot",
                "deploy",
                "execute",
                "readback",
                "health",
                "persistence",
                "rollback",
                "receipt",
            ],
            "authority_boundaries": {
                "local": "A1",
                "github": "provider-authorised",
                "google_drive": "provider-authorised",
                "cloud_run": "provider-authorised",
            },
        }

    def build_solution(self, idea: dict) -> dict:
        spec = self.compile_product_spec(idea)
        capabilities = self.capability_marketplace()
        genome = self.compile_solution_genome(spec, capabilities)
        package = self.workspace / "builds" / genome["system_id"]
        package.mkdir(parents=True, exist_ok=True)
        files = {
            "product_spec.json": spec,
            "capability_marketplace.json": capabilities,
            "solution_genome.json": genome,
            "health.json": {
                "availability": 1.0,
                "integrity": 1.0,
                "freshness": 1.0,
                "recoverability": 1.0,
            },
            "maintenance_plan.json": {
                "heartbeat": "hourly",
                "drift_checks": ["schema", "permissions", "dependencies", "provider_config"],
                "repair_modes": ["repair_in_place", "forward_fix", "rollback", "failover"],
                "retirement_controls": True,
            },
        }
        for name, data in files.items():
            (package / name).write_text(json.dumps(data, indent=2), encoding="utf-8")
        return {"package_dir": str(package), "spec": spec, "genome": genome}

    def operational_release(self, idea: dict) -> dict:
        build = self.build_solution(idea)
        source = Path(build["package_dir"])
        target = self.workspace / "operational" / build["genome"]["system_id"]
        adapter = LocalProviderAdapter(self.workspace / "provider_state")
        discover = adapter.discover()
        authority = adapter.validate_authority()
        snapshot = adapter.snapshot(source)
        deploy = adapter.deploy(source, target)
        execute = adapter.execute(target)
        readback = adapter.read_back(target)
        health = adapter.health_check(target)
        persistence = adapter.persistence_check(target)
        rollback_probe = self.workspace / "rollback_probe" / build["genome"]["system_id"]
        adapter.deploy(source, rollback_probe)
        rollback = adapter.rollback(rollback_probe)
        artifact = ReleaseArtifactAdapter().build(target, self.workspace / "releases")
        heartbeat = self.operations.heartbeat(build["genome"]["system_id"])
        operational = all(
            [
                discover["available"],
                authority["authorised"],
                deploy["state"] == "DEPLOYED",
                execute["state"] == "EXECUTED",
                readback["pass"],
                health["pass"],
                persistence["pass"],
                rollback["target_absent"],
                artifact["state"] == "ARTIFACT_VERIFIED",
            ]
        )
        receipt = {
            "receipt_id": self._id(
                "RCP",
                build["genome"]["system_id"] + datetime.datetime.now(datetime.UTC).isoformat(),
            ),
            "state": "OPERATIONAL_VERIFIED_LOCAL" if operational else "FAILED",
            "discover": discover,
            "authority": authority,
            "snapshot": snapshot,
            "deploy": deploy,
            "execute": execute,
            "readback": readback,
            "health": health,
            "persistence": persistence,
            "rollback": rollback,
            "artifact": artifact,
            "heartbeat": heartbeat,
            "truth_boundary": {
                "local_operational": operational,
                "github_source_deployed": False,
                "github_artifact_run_verified": False,
                "google_drive_manifest_published": False,
                "cloud_run_deployed": False,
            },
        }
        (target / "operational_receipt.json").write_text(
            json.dumps(receipt, indent=2), encoding="utf-8"
        )
        return receipt
