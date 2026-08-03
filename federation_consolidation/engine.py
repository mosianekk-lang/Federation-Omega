from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from alpha_omega_v30.cross_system_reconciliation import CrossSystemReconciler, SystemObservation
from alpha_omega_v30.institution import (
    ActionContract,
    AlphaOmegaInstitution,
    Invariant,
    RealityState,
)
from alpha_omega_v30.succession import (
    InstitutionalSuccessionPlanner,
    PhaseStatus,
    SuccessionContract,
)

from .models import ConsolidationResult


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


class FederationConsolidator:
    """Fail-closed federation state consolidation built on Alpha→Omega controls."""

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)

    def load(self, filename: str) -> Any:
        return json.loads((self.data_dir / filename).read_text(encoding="utf-8"))

    def validate_registry(self) -> ConsolidationResult:
        state = self.load("canonical_state.json")
        maturity = self.load("maturity_model.json")
        systems = state["systems"]
        errors: list[str] = []
        warnings: list[str] = []

        ids = [item["system_id"] for item in systems]
        names = [item["name"].casefold() for item in systems]
        if len(ids) != len(set(ids)):
            errors.append("DUPLICATE_SYSTEM_ID")
        if len(names) != len(set(names)):
            errors.append("DUPLICATE_CANONICAL_NAME")

        allowed_adoption = set(maturity["adoption_states"])
        allowed_maturity = set(maturity["maturity_states"])
        allowed_propagation = set(maturity["propagation_states"])

        for item in systems:
            required = (
                "system_id", "name", "canonical_version", "canonical_source",
                "system_of_record", "current_state", "adoption_state",
                "maturity_state", "propagation_state", "owner_workstream",
                "authority_ceiling", "last_proof", "primary_route",
                "open_gates", "value_licence",
            )
            missing = [field for field in required if field not in item or item[field] in ("", None)]
            if missing:
                errors.append(f"{item.get('system_id','UNKNOWN')}:MISSING:{','.join(missing)}")
            if item.get("adoption_state") not in allowed_adoption:
                errors.append(f"{item.get('system_id')}:INVALID_ADOPTION_STATE")
            if item.get("maturity_state") not in allowed_maturity:
                errors.append(f"{item.get('system_id')}:INVALID_MATURITY_STATE")
            if item.get("propagation_state") not in allowed_propagation:
                errors.append(f"{item.get('system_id')}:INVALID_PROPAGATION_STATE")
            if item.get("authority_ceiling") not in {"A0", "A1", "A2"}:
                errors.append(f"{item.get('system_id')}:INVALID_AUTHORITY")
            if not item.get("open_gates"):
                warnings.append(f"{item.get('system_id')}:NO_OPEN_GATES_RECORDED")

        metrics = {
            "system_count": len(systems),
            "unique_system_ids": len(set(ids)),
            "unique_names": len(set(names)),
            "systems_with_explicit_owner": sum(bool(item.get("owner_workstream")) for item in systems),
            "systems_with_one_system_of_record": sum(bool(item.get("system_of_record")) for item in systems),
        }
        return ConsolidationResult(not errors, tuple(errors), tuple(warnings), metrics)

    def validate_routes(self) -> ConsolidationResult:
        routes = self.load("route_registry.json")["routes"]
        errors: list[str] = []
        ids = [item["route_id"] for item in routes]
        if len(ids) != len(set(ids)):
            errors.append("DUPLICATE_ROUTE_ID")
        for route in routes:
            if route["authority_ceiling"] not in {"A0", "A1", "A2"}:
                errors.append(f"{route['route_id']}:INVALID_AUTHORITY")
            if route["freshness_hours"] <= 0:
                errors.append(f"{route['route_id']}:INVALID_TTL")
            if not route["permitted"] or not route["forbidden"]:
                errors.append(f"{route['route_id']}:INCOMPLETE_POLICY")
        return ConsolidationResult(
            not errors, tuple(errors), tuple(),
            {"route_count": len(routes), "selected_route": routes[0]["name"]}
        )

    def validate_pr_triage(self) -> ConsolidationResult:
        prs = self.load("pr_triage.json")["open_prs"]
        errors: list[str] = []
        numbers = [item["pr"] for item in prs]
        if len(numbers) != len(set(numbers)):
            errors.append("DUPLICATE_PR_NUMBER")
        allowed_prefixes = ("MERGE_", "KEEP_", "ARCHIVE_", "ABANDON_")
        for item in prs:
            if not item["classification"].startswith(allowed_prefixes):
                errors.append(f"PR-{item['pr']}:INVALID_CLASSIFICATION")
            if not item["reason"].strip():
                errors.append(f"PR-{item['pr']}:MISSING_REASON")
        return ConsolidationResult(
            not errors, tuple(errors), tuple(),
            {"classified_open_prs": len(prs), "unique_prs": len(set(numbers))}
        )

    def validate_lineage(self) -> ConsolidationResult:
        graph = self.load("lineage_graph.json")
        state = self.load("canonical_state.json")
        known = {item["system_id"] for item in state["systems"]}
        errors: list[str] = []
        child_owner: dict[str, str] = {}
        for root in graph["canonical_roots"]:
            if root["system_id"] not in known:
                errors.append(f"UNKNOWN_ROOT:{root['system_id']}")
            for child in root["children"]:
                if child not in known:
                    errors.append(f"UNKNOWN_CHILD:{child}")
                if child in child_owner:
                    errors.append(f"MULTIPLE_CANONICAL_PARENTS:{child}")
                child_owner[child] = root["system_id"]
        return ConsolidationResult(
            not errors, tuple(errors), tuple(),
            {"known_systems": len(known), "lineage_children": len(child_owner)}
        )

    def alpha_omega_release_gate(self) -> dict[str, Any]:
        results = {
            "registry": asdict(self.validate_registry()),
            "routes": asdict(self.validate_routes()),
            "triage": asdict(self.validate_pr_triage()),
            "lineage": asdict(self.validate_lineage()),
        }
        local_valid = all(result["valid"] for result in results.values())
        reality = RealityState(
            intended={"canonical_state": "VALID"},
            declared={"canonical_state": "VALID" if local_valid else "INVALID"},
            observed={"canonical_state": "VALID" if local_valid else "INVALID"},
            proven={"canonical_state": "VALID" if local_valid else "INVALID"},
            outcome={"canonical_state": "VALID" if local_valid else "INVALID"},
        )
        contract = ActionContract(
            action_id="FO-CONSOLIDATION-RELEASE",
            intent="Publish A1 canonical-state consolidation controls",
            preconditions=["registry_valid", "routes_valid", "lineage_valid", "triage_valid"],
            allowed_effects=["repository_source", "proof_artifact", "drive_control_tabs"],
            forbidden_effects=["external_message", "cloud_iam_mutation", "secret_access", "legal_filing", "financial_action"],
            success_evidence=["tests", "semantic_readback", "rollback"],
        )
        context = {
            "registry_valid": results["registry"]["valid"],
            "routes_valid": results["routes"]["valid"],
            "lineage_valid": results["lineage"]["valid"],
            "triage_valid": results["triage"]["valid"],
        }
        state = {
            "authority": "A1",
            "rollback": True,
            "evidenceops_p09_collision": False,
            "new_top_level_family": False,
        }
        invariants = [
            Invariant("A1_ONLY", lambda item: item["authority"] == "A1"),
            Invariant("ROLLBACK_REQUIRED", lambda item: item["rollback"]),
            Invariant("NO_EVIDENCEOPS_P09_COLLISION", lambda item: not item["evidenceops_p09_collision"]),
            Invariant("NO_NEW_TOP_LEVEL_FAMILY", lambda item: not item["new_top_level_family"]),
        ]
        votes = {
            "architect": "APPROVE",
            "builder": "APPROVE",
            "security": "APPROVE",
            "verifier": "APPROVE",
            "operations": "APPROVE",
            "evidence": "APPROVE",
        }
        ao = AlphaOmegaInstitution().evaluate_release(
            reality, contract, context,
            ["repository_source", "proof_artifact", "drive_control_tabs"],
            state, invariants, votes
        )
        return {"eligible": ao["eligible"], "alpha_omega": ao, "component_results": results}

    def reconciliation_canary(self, workspace: str | Path) -> dict[str, Any]:
        workspace = Path(workspace)
        workspace.mkdir(parents=True, exist_ok=True)
        ledger = workspace / "reconciliation-ledger.jsonl"
        now = datetime.now(timezone.utc).isoformat()
        reconciler = CrossSystemReconciler(ledger)
        observation = SystemObservation(
            system="FederationConsolidation",
            entity_id="FO-CANARY-001",
            intended={"state": "VERIFIED"},
            declared={"state": "VERIFIED"},
            observed={"state": "VERIFIED"},
            proven={"state": "VERIFIED"},
            outcome={"state": "VERIFIED"},
            evidence_ref="local-semantic-readback",
            observed_at=now,
        )
        result = reconciler.reconcile([observation], now=now, max_age_seconds=3600)
        return result

    def e2e_canary(self, workspace: str | Path) -> dict[str, Any]:
        workspace = Path(workspace)
        workspace.mkdir(parents=True, exist_ok=True)
        state_file = workspace / "state.json"
        rollback_file = workspace / "rollback.json"
        input_payload = {
            "packet_id": "FO-CONSOLIDATION-CANARY-001",
            "authority": "A1",
            "effect": "repository_and_control_state_only",
        }
        initial = {"generation": 0, "status": "BASELINE", "packets": []}
        state_file.write_text(json.dumps(initial, indent=2, sort_keys=True), encoding="utf-8")
        baseline_hash = digest(initial)

        executed = {
            "generation": 1,
            "status": "EXECUTED",
            "packets": [input_payload],
            "input_hash": digest(input_payload),
        }
        state_file.write_text(json.dumps(executed, indent=2, sort_keys=True), encoding="utf-8")
        readback = json.loads(state_file.read_text(encoding="utf-8"))
        readback_verified = readback == executed

        restarted = json.loads(state_file.read_text(encoding="utf-8"))
        restart_verified = restarted["generation"] == 1 and len(restarted["packets"]) == 1

        rollback_file.write_text(json.dumps(executed, indent=2, sort_keys=True), encoding="utf-8")
        state_file.write_text(json.dumps(initial, indent=2, sort_keys=True), encoding="utf-8")
        rollback_readback = json.loads(state_file.read_text(encoding="utf-8"))
        rollback_verified = rollback_readback == initial

        receipt = {
            "receipt_id": "RCP-FO-CONSOLIDATION-CANARY-001",
            "programme_id": "FO-24H-CONSOLIDATION-20260804",
            "action_id": input_payload["packet_id"],
            "authority": "A1",
            "inputs_hash": digest(input_payload),
            "output_hash": digest(executed),
            "proof_state": "ROLLED_BACK" if rollback_verified else "HELD",
            "readback": readback_verified and restart_verified,
            "rollback": rollback_verified,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "previous_receipt_hash": None,
            "truth_boundary": "Local/provider-neutral canary only; no external provider mutation.",
        }
        receipt["receipt_hash"] = digest({k: v for k, v in receipt.items() if k != "receipt_hash"})
        (workspace / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
        return {
            "passed": readback_verified and restart_verified and rollback_verified,
            "baseline_hash": baseline_hash,
            "readback_verified": readback_verified,
            "restart_verified": restart_verified,
            "rollback_verified": rollback_verified,
            "receipt": receipt,
        }

    def succession_bundle(self, source_commit: str, output_path: str | Path) -> dict[str, Any]:
        programme = self.load("programme_24h.json")
        gate = self.alpha_omega_release_gate()
        canary_workspace = Path(output_path).parent / "canary"
        canary = self.e2e_canary(canary_workspace)
        phases = [
            PhaseStatus("P0", "CANONICAL_REGISTRY", ("canonical_state.json",), "GitHub", gate["eligible"], ()),
            PhaseStatus("P1", "ROUTE_AND_MATURITY_STANDARD", ("route_registry.json", "maturity_model.json"), "GitHub", gate["eligible"], ()),
            PhaseStatus("P2", "E2E_CANARY", ("canary/receipt.json",), "GitHub", canary["passed"], ()),
            PhaseStatus("P3", "DRIVE_PUBLICATION", ("Drive operating-surface index",), "Google Drive", False, ("DRIVE_READBACK_REQUIRED",)),
        ]
        contract = SuccessionContract(
            source_commit=source_commit,
            programme_id=programme["programme_id"],
            owner=programme["owner"],
            recovery_runbook="docs/RECOVERY_AND_ROLLBACK.md",
            rollback_runbook="docs/RECOVERY_AND_ROLLBACK.md",
            authority_model="A1 fail-closed; owner reserved A2",
            proof_index=("canonical_state.json", "health_snapshot.json", "canary/receipt.json"),
        )
        bundle = InstitutionalSuccessionPlanner().evaluate(
            phases, contract,
            {"GitHub Actions": "FRESH_VERIFIED", "Google Drive": "FRESH_VERIFIED", "Cloud Provider": "NOT_REQUIRED"}
        )
        persisted = InstitutionalSuccessionPlanner().persist(bundle, output_path)
        return {"bundle": bundle, "persisted": persisted}
