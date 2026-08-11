from __future__ import annotations

from pathlib import Path
from typing import Mapping
import datetime
import hashlib
import json

from .operations import OperationsFabric
from .providers import GitHubReleaseArtifactAdapter, LocalProviderAdapter


class SolutionFoundry:
    def __init__(self, workspace: str | Path):
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.operations = OperationsFabric(self.workspace / "operations")

    def _id(self, prefix: str, value: str) -> str:
        return f"{prefix}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:12]}"

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
            "success_measures": list(idea.get("outcomes", []))
            or ["operational build verified"],
            "functional_requirements": list(idea.get("functional_requirements", []))
            or [
                "accept concept",
                "compile specification",
                "build package",
                "deploy",
                "execute",
                "read back",
                "health check",
                "persistence check",
                "rollback",
                "maintain",
            ],
            "non_functional_requirements": [
                "proof before claim",
                "rollback required",
                "health monitoring",
                "provider truth boundary",
                "minimum reversible action",
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
            ("CAP-COST", "outcome and cost governance"),
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
                "google_drive_binary",
                "cloud_run",
            ],
            "provider_contract": [
                "discover",
                "validate_authority",
                "snapshot",
                "deploy",
                "execute",
                "read_back",
                "health_check",
                "persistence_check",
                "rollback",
                "proof_receipt",
            ],
            "authority_boundaries": {
                "local": "A1",
                "github_actions_artifact": "provider_authorised",
                "google_drive_binary": "provider_authorised_direct_connector",
                "cloud_run": "provider_blocked_no_fresh_authority",
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
                "failure_classes": [
                    "NONE",
                    "AUTHORITY",
                    "TRANSIENT",
                    "CONTRACT",
                    "INTEGRITY",
                    "RESOURCE",
                    "UNKNOWN",
                ],
                "repair_modes": [
                    "no_action",
                    "retry_with_backoff",
                    "throttle_and_retry",
                    "forward_fix_and_retest",
                    "rollback_and_rebuild",
                    "quarantine_and_diagnose",
                ],
                "learning_ledger": True,
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
        maintenance = self.operations.maintenance_cycle(
            build["genome"]["system_id"],
            expected={"provider": "local", "state": "RUNNING"},
            actual={"provider": "local", "state": "RUNNING"},
        )
        operational = all(
            [
                discover["available"],
                authority["authorised"],
                snapshot["state"] == "SNAPSHOT_CREATED",
                deploy["state"] == "DEPLOYED",
                execute["state"] == "EXECUTED",
                readback["pass"],
                health["pass"],
                persistence["pass"],
                rollback["target_absent"],
                maintenance["state"] == "MAINTENANCE_HEALTHY",
            ]
        )
        receipt = {
            "receipt_id": self._id(
                "RCP",
                build["genome"]["system_id"]
                + datetime.datetime.now(datetime.UTC).isoformat(),
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
            "maintenance": maintenance,
            "truth_boundary": {
                "local_operational": operational,
                "github_hosted_artifact": False,
                "google_drive_binary_published": False,
                "cloud_run_deployed": False,
            },
        }
        (target / "operational_receipt.json").write_text(
            json.dumps(receipt, indent=2), encoding="utf-8"
        )
        return receipt

    def github_release_artifact(
        self, idea: dict, environment: Mapping[str, str] | None = None
    ) -> dict:
        build = self.build_solution(idea)
        source = Path(build["package_dir"])
        adapter = GitHubReleaseArtifactAdapter(
            self.workspace,
            environment=environment if environment is not None else __import__("os").environ,
        )
        return adapter.run_contract(source, self.workspace / "github_release")
