from __future__ import annotations
import hashlib, json
from typing import Any, Dict
from .registry import FederationRegistry


def fingerprint(*, project_id: str, objective: str, proof_gap: str,
                action: str, target: str, source_version: str = "") -> str:
    payload = {
      "project_id": project_id, "objective": objective, "proof_gap": proof_gap,
      "action": action, "target": target, "source_version": source_version,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class FederationDeduplicator:
    def __init__(self, registry: FederationRegistry):
        self.registry = registry

    def preflight(self, *, project_id: str, objective: str, proof_gap: str,
                  action: str, target: str, source_version: str = "") -> Dict[str, Any]:
        fp = fingerprint(project_id=project_id, objective=objective, proof_gap=proof_gap,
                         action=action, target=target, source_version=source_version)
        rec = self.registry.receipt(fp)
        if not rec:
            return {"decision": "EXECUTE_NEW", "fingerprint": fp}
        if rec["state"] == "COMPLETE" and rec["semantic_ok"]:
            if source_version and rec.get("source_version") and source_version != rec["source_version"]:
                return {"decision": "REVALIDATE_MINIMUM_SLICE", "fingerprint": fp, "prior": rec}
            return {"decision": "REUSE_VERIFIED_RESULT", "fingerprint": fp, "prior": rec}
        if rec["state"] in ("ACTIVE", "PARTIAL", "BLOCKED"):
            return {"decision": "RESUME_FROM_CHECKPOINT", "fingerprint": fp, "prior": rec}
        return {"decision": "EXECUTE_NEW", "fingerprint": fp, "prior": rec}
