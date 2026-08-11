from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TENANT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,62}$")
ALLOWED_ROLES = {"owner", "admin", "operator", "auditor", "billing"}
ROLE_PERMISSIONS = {
    "owner": {"*"},
    "admin": {"tenant.read", "tenant.write", "workspace.provision", "workspace.rollback", "secret.reference", "usage.write", "invoice.export"},
    "operator": {"tenant.read", "workspace.provision", "workspace.rollback", "usage.write"},
    "auditor": {"tenant.read", "audit.read", "usage.read", "invoice.read"},
    "billing": {"tenant.read", "usage.read", "invoice.export", "invoice.read"},
}


@dataclass(frozen=True)
class Offer:
    offer_id: str
    name: str
    ideal_customer_profile: str
    outcome: str
    exclusions: tuple[str, ...]
    setup_price_zar: int
    monthly_price_zar: int
    contract_months: int
    included_builds: int
    included_support_hours: int
    monthly_budget_cap_zar: int
    validation_status: str


@dataclass(frozen=True)
class UsageEvent:
    tenant_id: str
    event_id: str
    occurred_at: str
    event_type: str
    quantity: float
    unit_cost_zar: float


@dataclass(frozen=True)
class SecretReference:
    tenant_id: str
    reference_id: str
    provider: str
    resource_name: str
    scope: tuple[str, ...]
    version: str
    rotation_due_at: str


class CommercialPlatform:
    """Proof-oriented commercial platform reference implementation for C01-C05.

    The implementation deliberately stores secret references only. It does not
    accept secret material, make payment-provider claims, or imply market demand.
    """

    def __init__(self, state_dir: str | Path) -> None:
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.workspaces_dir = self.state_dir / "workspaces"
        self.workspaces_dir.mkdir(exist_ok=True)
        self.state_file = self.state_dir / "commercial_state.json"
        self.audit_file = self.state_dir / "audit_ledger.jsonl"
        self.usage_file = self.state_dir / "usage_ledger.jsonl"
        self.receipts_dir = self.state_dir / "receipts"
        self.receipts_dir.mkdir(exist_ok=True)
        self.offers = self._offer_catalogue()
        if not self.state_file.exists():
            self._write_state({"tenants": {}, "secret_references": {}, "workspaces": {}})

    @staticmethod
    def _offer_catalogue() -> dict[str, Offer]:
        status = "INTERNAL_CONTRACT_VERIFIED_MARKET_PROOF_REQUIRED"
        return {
            "AO-PILOT": Offer(
                "AO-PILOT", "Operational Automation Pilot",
                "One department with one bounded, measurable manual process family",
                "A deployed, monitored and auditable workflow with a quantified baseline",
                ("unbounded custom development", "regulated production processing without assessment", "third-party licence fees"),
                200_000, 30_000, 12, 1, 10, 18_000, status,
            ),
            "AO-DEPARTMENT": Offer(
                "AO-DEPARTMENT", "Department Automation Platform",
                "A department requiring several governed workflows and operational reporting",
                "A managed departmental automation workspace with reusable controls and SLA reporting",
                ("enterprise-wide identity migration", "unlimited integrations", "third-party licence fees"),
                500_000, 75_000, 12, 4, 30, 42_000, status,
            ),
            "AO-ENTERPRISE": Offer(
                "AO-ENTERPRISE", "Enterprise Digital Systems Institution",
                "A multi-department organisation requiring governed delivery, evidence and recovery controls",
                "A federated service-enabled platform with enterprise assurance and managed operations",
                ("certification fees", "customer-owned cloud consumption", "unapproved consequential production changes"),
                1_500_000, 200_000, 24, 12, 80, 110_000, status,
            ),
        }

    def catalogue(self) -> list[dict[str, Any]]:
        return [asdict(self.offers[key]) for key in sorted(self.offers)]

    def sales_asset(self, offer_id: str) -> dict[str, Any]:
        offer = self._offer(offer_id)
        return {
            "offer_id": offer.offer_id,
            "headline": offer.name,
            "for": offer.ideal_customer_profile,
            "promised_outcome": offer.outcome,
            "commercial_model": {
                "setup_price_zar": offer.setup_price_zar,
                "monthly_price_zar": offer.monthly_price_zar,
                "minimum_term_months": offer.contract_months,
            },
            "exclusions": list(offer.exclusions),
            "truth_boundary": "Pricing and positioning are internal commercial hypotheses until external market evidence exists.",
        }

    def quote(self, offer_id: str, months: int | None = None) -> dict[str, Any]:
        offer = self._offer(offer_id)
        term = offer.contract_months if months is None else months
        if term < 1:
            raise ValueError("months must be positive")
        recurring = offer.monthly_price_zar * term
        return {
            "offer_id": offer.offer_id, "currency": "ZAR",
            "setup_zar": offer.setup_price_zar, "recurring_zar": recurring,
            "contract_value_zar": offer.setup_price_zar + recurring,
            "months": term, "status": "ESTIMATE_REQUIRES_OWNER_APPROVAL",
        }

    def create_tenant(self, tenant_id: str, name: str, offer_id: str, owner_subject: str) -> dict[str, Any]:
        self._validate_tenant_id(tenant_id)
        offer = self._offer(offer_id)
        state = self._read_state()
        if tenant_id in state["tenants"]:
            existing = state["tenants"][tenant_id]
            if existing["name"] == name and existing["offer_id"] == offer_id:
                return existing
            raise ValueError("tenant_id already exists with different attributes")
        tenant = {
            "tenant_id": tenant_id, "name": name, "offer_id": offer.offer_id,
            "status": "ACTIVE", "roles": {owner_subject: ["owner"]},
            "data_boundary": f"tenant/{tenant_id}", "created_at": self._now(),
        }
        state["tenants"][tenant_id] = tenant
        self._write_state(state)
        self._audit(tenant_id, owner_subject, "tenant.create", {"offer_id": offer_id})
        return tenant

    def assign_role(self, tenant_id: str, actor: str, subject: str, role: str) -> dict[str, Any]:
        if role not in ALLOWED_ROLES:
            raise ValueError("unknown role")
        self.require(tenant_id, actor, "tenant.write")
        state = self._read_state()
        roles = state["tenants"][tenant_id]["roles"].setdefault(subject, [])
        if role not in roles:
            roles.append(role)
            roles.sort()
            self._write_state(state)
            self._audit(tenant_id, actor, "role.assign", {"subject": subject, "role": role})
        return {"tenant_id": tenant_id, "subject": subject, "roles": roles}

    def require(self, tenant_id: str, subject: str, permission: str) -> None:
        state = self._read_state()
        tenant = state["tenants"].get(tenant_id)
        if tenant is None:
            raise KeyError("tenant not found")
        allowed: set[str] = set()
        for role in tenant["roles"].get(subject, []):
            allowed.update(ROLE_PERMISSIONS[role])
        if "*" not in allowed and permission not in allowed:
            raise PermissionError(f"{subject} lacks {permission} in {tenant_id}")

    def tenant_readback(self, tenant_id: str, subject: str) -> dict[str, Any]:
        self.require(tenant_id, subject, "tenant.read")
        return self._read_state()["tenants"][tenant_id]

    def register_secret_reference(self, actor: str, reference: SecretReference) -> dict[str, Any]:
        self.require(reference.tenant_id, actor, "secret.reference")
        serialized = asdict(reference)
        self._reject_secret_material(serialized)
        state = self._read_state()
        key = f"{reference.tenant_id}:{reference.reference_id}"
        existing = state["secret_references"].get(key)
        if existing and existing != serialized:
            raise ValueError("secret reference exists; rotate explicitly")
        state["secret_references"][key] = serialized
        self._write_state(state)
        self._audit(reference.tenant_id, actor, "secret.reference.register", {"reference_id": reference.reference_id, "version": reference.version})
        return serialized

    def rotate_secret_reference(self, tenant_id: str, actor: str, reference_id: str, new_version: str, rotation_due_at: str) -> dict[str, Any]:
        self.require(tenant_id, actor, "secret.reference")
        state = self._read_state()
        key = f"{tenant_id}:{reference_id}"
        current = state["secret_references"][key]
        previous_version = current["version"]
        current["version"] = new_version
        current["rotation_due_at"] = rotation_due_at
        self._write_state(state)
        self._audit(tenant_id, actor, "secret.reference.rotate", {"reference_id": reference_id, "from": previous_version, "to": new_version})
        return current

    def provision_workspace(self, tenant_id: str, actor: str) -> dict[str, Any]:
        self.require(tenant_id, actor, "workspace.provision")
        state = self._read_state()
        tenant = state["tenants"][tenant_id]
        workspace = self.workspaces_dir / tenant_id
        manifest_path = workspace / "workspace.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest["tenant_id"] != tenant_id:
                raise RuntimeError("workspace boundary mismatch")
            return manifest
        workspace.mkdir(parents=True, exist_ok=False)
        manifest = {
            "workspace_id": f"ws-{tenant_id}", "tenant_id": tenant_id,
            "offer_id": tenant["offer_id"], "provider": "local-reference-provider",
            "data_boundary": tenant["data_boundary"], "status": "READY", "created_at": self._now(),
        }
        self._atomic_json(manifest_path, manifest)
        receipt = self._receipt(tenant_id, "workspace.provision", manifest)
        manifest["receipt_sha256"] = receipt["receipt_sha256"]
        self._atomic_json(manifest_path, manifest)
        state["workspaces"][tenant_id] = {"path": str(workspace), "status": "READY", "receipt_sha256": receipt["receipt_sha256"]}
        self._write_state(state)
        self._audit(tenant_id, actor, "workspace.provision", {"workspace_id": manifest["workspace_id"]})
        return manifest

    def rollback_workspace(self, tenant_id: str, actor: str) -> dict[str, Any]:
        self.require(tenant_id, actor, "workspace.rollback")
        workspace = self.workspaces_dir / tenant_id
        existed = workspace.exists()
        if existed:
            shutil.rmtree(workspace)
        state = self._read_state()
        state["workspaces"][tenant_id] = {"path": str(workspace), "status": "ROLLED_BACK", "rolled_back_at": self._now()}
        self._write_state(state)
        proof = {"tenant_id": tenant_id, "existed_before": existed, "exists_after": workspace.exists(), "status": "ROLLED_BACK"}
        self._receipt(tenant_id, "workspace.rollback", proof)
        self._audit(tenant_id, actor, "workspace.rollback", proof)
        return proof

    def append_usage(self, actor: str, event: UsageEvent) -> dict[str, Any]:
        self.require(event.tenant_id, actor, "usage.write")
        if event.quantity < 0 or event.unit_cost_zar < 0:
            raise ValueError("usage quantities and costs must be non-negative")
        row = asdict(event)
        existing = {item["event_id"] for item in self._read_jsonl(self.usage_file)}
        if event.event_id in existing:
            raise ValueError("duplicate usage event")
        self._append_jsonl(self.usage_file, row)
        self._audit(event.tenant_id, actor, "usage.append", {"event_id": event.event_id, "event_type": event.event_type})
        return row

    def meter(self, tenant_id: str) -> dict[str, Any]:
        events = [row for row in self._read_jsonl(self.usage_file) if row["tenant_id"] == tenant_id]
        by_type: dict[str, dict[str, float]] = {}
        total_cost = 0.0
        for row in events:
            quantity = float(row["quantity"])
            cost = quantity * float(row["unit_cost_zar"])
            bucket = by_type.setdefault(row["event_type"], {"quantity": 0.0, "cost_zar": 0.0})
            bucket["quantity"] += quantity
            bucket["cost_zar"] += cost
            total_cost += cost
        for bucket in by_type.values():
            bucket["quantity"] = round(bucket["quantity"], 4)
            bucket["cost_zar"] = round(bucket["cost_zar"], 2)
        return {"tenant_id": tenant_id, "event_count": len(events), "cost_zar": round(total_cost, 2), "by_type": by_type}

    def plan_enforcement(self, tenant_id: str) -> dict[str, Any]:
        state = self._read_state()
        offer = self._offer(state["tenants"][tenant_id]["offer_id"])
        metered = self.meter(tenant_id)
        builds = metered["by_type"].get("build", {}).get("quantity", 0.0)
        support = metered["by_type"].get("support_hour", {}).get("quantity", 0.0)
        return {
            "tenant_id": tenant_id, "offer_id": offer.offer_id,
            "builds": {"used": builds, "included": offer.included_builds, "within_plan": builds <= offer.included_builds},
            "support_hours": {"used": support, "included": offer.included_support_hours, "within_plan": support <= offer.included_support_hours},
            "within_plan": builds <= offer.included_builds and support <= offer.included_support_hours,
        }

    def budget_control(self, tenant_id: str) -> dict[str, Any]:
        state = self._read_state()
        offer = self._offer(state["tenants"][tenant_id]["offer_id"])
        cost = self.meter(tenant_id)["cost_zar"]
        utilisation = cost / offer.monthly_budget_cap_zar if offer.monthly_budget_cap_zar else 0.0
        decision = "HOLD_NEW_COST" if utilisation >= 1 else "WARN" if utilisation >= 0.8 else "ALLOW"
        return {"tenant_id": tenant_id, "cost_zar": cost, "budget_cap_zar": offer.monthly_budget_cap_zar, "utilisation": round(utilisation, 4), "decision": decision}

    def invoice_ready_export(self, tenant_id: str, actor: str, output_path: str | Path) -> dict[str, Any]:
        self.require(tenant_id, actor, "invoice.export")
        state = self._read_state()
        tenant = state["tenants"][tenant_id]
        offer = self._offer(tenant["offer_id"])
        metered = self.meter(tenant_id)
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            ["tenant_id", "offer_id", "base_subscription_zar", "metered_delivery_cost_zar", "status"],
            [tenant_id, offer.offer_id, str(offer.monthly_price_zar), f"{metered['cost_zar']:.2f}", "INVOICE_READY_NOT_ISSUED"],
        ]
        with output.open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerows(rows)
        digest = self._sha256_bytes(output.read_bytes())
        receipt = self._receipt(tenant_id, "invoice.export", {"path": str(output), "sha256": digest})
        self._audit(tenant_id, actor, "invoice.export", {"sha256": digest})
        return {"path": str(output), "sha256": digest, "status": "INVOICE_READY_NOT_ISSUED", "receipt_sha256": receipt["receipt_sha256"]}

    def verify_audit_chain(self) -> bool:
        previous = "GENESIS"
        for row in self._read_jsonl(self.audit_file):
            if row["previous_hash"] != previous:
                return False
            payload = {key: row[key] for key in row if key != "event_hash"}
            if self._sha256_json(payload) != row["event_hash"]:
                return False
            previous = row["event_hash"]
        return True

    def state_hash(self) -> str:
        return self._sha256_bytes(self.state_file.read_bytes())

    def _audit(self, tenant_id: str, actor: str, action: str, detail: dict[str, Any]) -> dict[str, Any]:
        rows = self._read_jsonl(self.audit_file)
        event = {
            "event_id": f"audit-{len(rows)+1:06d}", "occurred_at": self._now(),
            "tenant_id": tenant_id, "actor": actor, "action": action, "detail": detail,
            "previous_hash": rows[-1]["event_hash"] if rows else "GENESIS",
        }
        event["event_hash"] = self._sha256_json(event)
        self._append_jsonl(self.audit_file, event)
        return event

    def _receipt(self, tenant_id: str, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        receipt = {"tenant_id": tenant_id, "action": action, "recorded_at": self._now(), "payload": payload}
        receipt["receipt_sha256"] = self._sha256_json(receipt)
        target = self.receipts_dir / f"{receipt['recorded_at'].replace(':', '-')}-{action.replace('.', '-')}-{tenant_id}.json"
        self._atomic_json(target, receipt)
        return receipt

    def _offer(self, offer_id: str) -> Offer:
        try:
            return self.offers[offer_id]
        except KeyError as exc:
            raise KeyError(f"unknown offer_id {offer_id}") from exc

    @staticmethod
    def _validate_tenant_id(tenant_id: str) -> None:
        if not TENANT_ID_RE.fullmatch(tenant_id):
            raise ValueError("tenant_id must be a lowercase DNS-safe slug of 3-63 characters")

    @staticmethod
    def _reject_secret_material(value: Any) -> None:
        forbidden_keys = {"secret", "token", "password", "private_key", "credential", "value"}
        if isinstance(value, dict):
            for key, child in value.items():
                if key.lower() in forbidden_keys:
                    raise ValueError(f"secret material field is forbidden: {key}")
                CommercialPlatform._reject_secret_material(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                CommercialPlatform._reject_secret_material(child)

    def _read_state(self) -> dict[str, Any]:
        return json.loads(self.state_file.read_text(encoding="utf-8"))

    def _write_state(self, value: dict[str, Any]) -> None:
        self._atomic_json(self.state_file, value)

    @staticmethod
    def _atomic_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp, path)

    @staticmethod
    def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    @staticmethod
    def _sha256_json(value: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    @staticmethod
    def _sha256_bytes(value: bytes) -> str:
        return hashlib.sha256(value).hexdigest()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
