from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


class AuthorityReconciliationError(ValueError):
    """Raised when a claimed authority state conflicts with canonical evidence."""


def digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AuthorityReconciliationError(f"{path} must contain a JSON object")
    return value


def parse_workflow_env(text: str) -> dict[str, str]:
    """Extract the simple top-level provider targeting values used by the workflow."""
    values: dict[str, str] = {}
    for key in ("PROJECT_ID", "REGION", "SERVICE", "SERVICE_PATH"):
        match = re.search(rf"(?m)^\s{{2}}{key}:\s*['\"]?([^'\"\n#]+)", text)
        if match:
            values[key] = match.group(1).strip()
    return values


def _stage_map(programme: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    stages = programme.get("stages")
    if not isinstance(stages, list):
        raise AuthorityReconciliationError("programme stages must be a list")
    mapped = {str(stage.get("id")): stage for stage in stages if isinstance(stage, Mapping)}
    expected = [f"C{i:02d}" for i in range(1, 16)]
    if list(mapped) != expected:
        raise AuthorityReconciliationError(f"commercial dependency order drifted: {list(mapped)!r}")
    completed: set[str] = set()
    for stage_id in expected:
        stage = mapped[stage_id]
        deps = stage.get("depends_on", [])
        if not isinstance(deps, list) or any(dep not in completed for dep in deps):
            raise AuthorityReconciliationError(f"invalid dependency order at {stage_id}: {deps!r}")
        completed.add(stage_id)
    return mapped


def _cloud_requirement(requirements: Mapping[str, Any]) -> Mapping[str, Any]:
    rows = requirements.get("requirements")
    if not isinstance(rows, list):
        raise AuthorityReconciliationError("provider requirements must be a list")
    matches = [row for row in rows if isinstance(row, Mapping) and row.get("domain") == "cloud_run"]
    if len(matches) != 1:
        raise AuthorityReconciliationError("exactly one cloud_run requirement is required")
    return matches[0]


def _assert_no_live_cloud_claim(programme: Mapping[str, Any]) -> None:
    admission = programme.get("external_evidence_admission", {})
    provider_authority = admission.get("provider_authority", {}) if isinstance(admission, Mapping) else {}
    live = programme.get("live_provider_expansion", {})
    provider_states = live.get("provider_states", {}) if isinstance(live, Mapping) else {}
    values = [provider_authority.get("cloud_run"), provider_authority.get("live_cloud_operations"), provider_states.get("google_cloud_run")]
    for value in values:
        state = str(value or "")
        if "VERIFIED" in state and "BLOCKED" not in state and "UNPROVEN" not in state:
            raise AuthorityReconciliationError(f"unsupported live Cloud Run claim: {state}")


def reconcile(
    programme: Mapping[str, Any],
    requirements: Mapping[str, Any],
    manifest: Mapping[str, Any],
    provider_register: Mapping[str, Any],
    workflow_text: str,
) -> dict[str, Any]:
    if programme.get("programme_id") != "AO-COMMERCIAL-MATURITY-V1":
        raise AuthorityReconciliationError("unexpected commercial programme")
    if not str(manifest.get("manifest_id", "")).startswith("FO-CLAM-"):
        raise AuthorityReconciliationError("canonical authority manifest is missing or unrecognised")

    _stage_map(programme)
    _assert_no_live_cloud_claim(programme)
    cloud = manifest.get("cloud_run")
    if not isinstance(cloud, Mapping):
        raise AuthorityReconciliationError("canonical Cloud Run route is absent")
    route = {
        "project_id": cloud.get("project_id"),
        "region": cloud.get("region"),
        "service": cloud.get("service"),
        "path": cloud.get("path"),
    }
    if any(not value for value in route.values()):
        raise AuthorityReconciliationError(f"canonical Cloud Run route incomplete: {route}")
    if cloud.get("status") != "CONTROL_PLANE_PRESENT_LIVE_INVOCATION_UNPROVEN":
        raise AuthorityReconciliationError("Cloud Run must remain unproven until provider-native receipts pass")

    cloud_req = _cloud_requirement(requirements)
    required_proofs = set(cloud_req.get("required_proofs", []))
    if not {"provider_identity", "execution", "readback", "health", "persistence", "rollback"}.issubset(required_proofs):
        raise AuthorityReconciliationError("commercial Cloud Run proof contract is incomplete")

    workflow_env = parse_workflow_env(workflow_text)
    expected_env = {
        "PROJECT_ID": str(route["project_id"]),
        "REGION": str(route["region"]),
        "SERVICE": str(route["service"]),
        "SERVICE_PATH": str(route["path"]),
    }
    if workflow_env != expected_env:
        raise AuthorityReconciliationError(
            f"commercial workflow is not aligned to canonical route: expected {expected_env}, got {workflow_env}"
        )

    certified = set(manifest.get("certified_reversible_surfaces", []))
    providers = provider_register.get("providers", {})
    if not isinstance(providers, Mapping):
        raise AuthorityReconciliationError("provider certification register is malformed")
    operational = {name for name, row in providers.items() if isinstance(row, Mapping) and row.get("status") == "VERIFIED_OPERATIONAL"}
    if not certified.issubset(operational):
        raise AuthorityReconciliationError(f"certified surface drift: missing {sorted(certified - operational)}")

    reserved = set(programme.get("owner_reserved_authority", []))
    required_reserved = {
        "financial commitments",
        "contracts",
        "external communications",
        "consequential releases",
        "revenue recognition confirmation",
    }
    if not required_reserved.issubset(reserved):
        raise AuthorityReconciliationError("owner-reserved authority boundary was weakened")

    candidate_identities = list(cloud.get("candidate_identities", []))
    if not candidate_identities:
        raise AuthorityReconciliationError("canonical candidate identities are missing")

    gates = {
        "programme_dependency_order": True,
        "canonical_manifest_present": True,
        "canonical_target_route_aligned": True,
        "commercial_cloud_proof_contract_complete": True,
        "certified_reversible_surfaces_read_back": True,
        "unsupported_live_cloud_claim_rejected": True,
        "owner_reserved_authority_preserved": True,
        "external_maturity_gates_unchanged": not bool(programme.get("external_gate_evidence")),
    }
    if not all(gates.values()):
        raise AuthorityReconciliationError(f"reconciliation gate failed: {gates}")

    result = {
        "status": "CANONICAL_PROVIDER_ROUTE_ALIGNED_IDENTITY_AUTHORITY_UNAVAILABLE",
        "manifest_id": manifest["manifest_id"],
        "proof_scope": "C03_C06_C07_C11_C14_C15_CANONICAL_PROVIDER_AUTHORITY_RECONCILIATION",
        "cloud_run": {
            **route,
            "candidate_identities": candidate_identities,
            "required_sequence": list(cloud.get("required_sequence", [])),
            "required_receipts": list(cloud.get("promotion_receipts", [])),
            "live_invocation_proven": False,
            "cloud_mutation_performed": False,
            "identity_authority": "OWNER_OR_PROVIDER_CONFIGURATION_REQUIRED",
            "provider_state": "PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE",
        },
        "certified_reversible_surfaces": sorted(certified),
        "gates": gates,
        "truth_boundary": {
            "service_enabled_platform_priority_preserved": True,
            "customer_demand_proven": False,
            "signed_contract_proven": False,
            "payment_or_revenue_proven": False,
            "subscription_or_invoice_proven": False,
            "cloud_run_operation_proven": False,
            "enterprise_attestation_proven": False,
            "partner_adoption_proven": False,
            "external_case_study_proven": False,
            "production_scale_proven": False,
            "owner_reserved_authority_bypassed": False,
        },
    }
    result["receipt_sha256"] = digest(result)
    return result


def project_programme(programme: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deterministic programme projection without advancing external maturity gates."""
    projected = deepcopy(dict(programme))
    projected["canonical_authority_reconciliation"] = {
        "status": receipt["status"],
        "manifest_id": receipt["manifest_id"],
        "proof_scope": receipt["proof_scope"],
        "cloud_run": receipt["cloud_run"],
        "receipt_sha256": receipt["receipt_sha256"],
        "external_gate_effect": "UNCHANGED",
        "owner_authority_effect": "UNCHANGED",
        "full_commercial_maturity": False,
    }
    admission = projected["external_evidence_admission"]["provider_authority"]
    admission["cloud_run"] = "PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE"
    admission["live_cloud_operations"] = "PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE"

    stage_updates = {
        "C03": (
            "CANONICAL_PROVIDER_ROUTE_ALIGNED_SIX_REVERSIBLE_PROVIDERS_VERIFIED_IDENTITY_AUTHORITY_UNAVAILABLE",
            "six reversible providers remain verified; the canonical federation-omega-operator route is aligned, but fresh identity authority and live receipts remain unavailable",
        ),
        "C06": (
            "REVERSIBLE_PROVIDER_OPERATIONS_VERIFIED_CANONICAL_CLOUD_ROUTE_ALIGNED_LIVE_SLA_BLOCKED",
            "managed reversible operations remain verified; canonical Cloud Run targeting is aligned while live health, persistence and rollback evidence remain blocked",
        ),
        "C07": (
            "SIX_REVERSIBLE_PROVIDER_ADAPTERS_VERIFIED_CANONICAL_CLOUD_ADAPTER_PACKAGED_AUTHORITY_BLOCKED",
            "six provider-native adapters remain verified; the canonical Cloud Run adapter contract is packaged but cannot be promoted without identity authority",
        ),
        "C11": (
            "SERVICE_ENABLED_PLATFORM_VERIFIED_CANONICAL_CLOUD_ROUTE_ALIGNED_SELF_SERVICE_HELD",
            "service-enabled operations remain verified; live Cloud Run, send, payment, subscription and consequential self-service actions remain held",
        ),
        "C14": (
            "REFERENCE_RELIABILITY_VERIFIED_CANONICAL_CLOUD_ROUTE_ALIGNED_PRODUCTION_PROOF_REQUIRED",
            "reference reliability remains verified; canonical Cloud Run routing is aligned but production-scale and live provider evidence remain required",
        ),
        "C15": (
            "COMMERCIAL_READINESS_VERIFIED_CANONICAL_PROVIDER_ROUTE_ALIGNED_EXTERNAL_MATURITY_GATES_OPEN",
            "canonical receipts, six reversible providers and the canonical Cloud Run route are aligned; identity authority, live provider proof and all external maturity gates remain open",
        ),
    }
    for stage in projected["stages"]:
        if stage["id"] in stage_updates:
            stage["status"], stage["maturity_gate"] = stage_updates[stage["id"]]
    return projected
