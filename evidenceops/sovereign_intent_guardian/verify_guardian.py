#!/usr/bin/env python3
"""Static proof gate for the read-only guardian foundation."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT / "sovereign_intent_guardian"
REQUIRED = {
    "README.md", "FORMATION_SPEC.md", "PROJECT_MEMORY.md", "AI_HANDOFF.md", "LEARNING_LOOP.md",
    "LEARNING_INCIDENTS.json",
    "BUILD_CONTRACT.json", ".gitignore", "sovereign_intent_guardian/__init__.py",
    "validate_build_contract.py",
    "sovereign_intent_guardian/__main__.py", "sovereign_intent_guardian/cli.py",
    "sovereign_intent_guardian/contracts.py", "sovereign_intent_guardian/policy.py",
    "sovereign_intent_guardian/provider.py", "sovereign_intent_guardian/store.py",
    "sovereign_intent_guardian/worker.py",
}
FORBIDDEN_IMPORT_ROOTS = {
    "boto3", "google", "httpx", "openai", "requests", "socket", "subprocess",
    "urllib", "smtplib", "imaplib", "poplib", "ftplib", "paramiko", "github",
}
FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__"}
SECRET_RE = re.compile(
    r"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\bAIza[0-9A-Za-z_-]{20,}\b|\bgh[pousr]_[0-9A-Za-z]{20,}\b|\bsk-[0-9A-Za-z_-]{20,}\b)"
)
REQUIRED_EFFECT_ENUMS = {
    "IMPERSONATE_OWNER", "SEND_COMMUNICATION", "CONSENT_OR_WAIVER",
    "LEGAL_SETTLEMENT", "SPEND_OR_BILL", "ACCESS_SECRET", "PUBLISH",
    "DEPLOY", "MERGE", "WORKFLOW_DISPATCH", "CLOUD_MUTATION",
    "WRITE_LOCAL_OR_REMOTE", "DELETE_RESOURCE", "EXECUTE_COMMAND",
}
LEARNING_FINGERPRINT_FIELDS = [
    "failureClass", "surface", "control", "claim", "fruit", "remediation",
    "severity", "recurrenceCount", "userCorrection", "metric",
    "metricBreached", "rollbackBoundary", "authorityEffect", "costEffect",
    "failureFirstTest", "healthyCaseTest", "sourceReview", "formationPermit",
]
LEARNING_REQUIRED_TEXT_FIELDS = {
    "failureClass", "surface", "control", "claim", "fruit", "remediation",
    "userCorrection", "metric", "rollbackBoundary", "failureFirstTest",
    "healthyCaseTest", "sourceReview", "formationPermit",
}


def main() -> int:
    errors: list[str] = []
    relative_files = {
        str(path.relative_to(ROOT)).replace("\\", "/")
        for path in ROOT.rglob("*") if path.is_file()
    }
    for path in sorted(REQUIRED - relative_files):
        errors.append(f"MISSING_REQUIRED_FILE:{path}")
    for path in ROOT.rglob("*"):
        if path.is_symlink():
            errors.append(f"SYMLINK_PROHIBITED:{path.relative_to(ROOT)}")
        if path.is_file() and path.suffix in {".db", ".sqlite", ".sqlite3", ".wal", ".shm"}:
            errors.append(f"RUNTIME_DATABASE_PROHIBITED:{path.relative_to(ROOT)}")

    source_hashes: dict[str, str] = {}
    imported_roots: set[str] = set()
    for path in sorted(PACKAGE.glob("*.py")):
        raw = path.read_bytes()
        source_hashes[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
        text = raw.decode("utf-8")
        if SECRET_RE.search(text):
            errors.append(f"SECRET_PATTERN:{path.name}")
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in FORBIDDEN_CALLS:
                    errors.append(f"DYNAMIC_EXECUTION_PROHIBITED:{path.name}:{node.func.id}")
    for name in sorted(imported_roots & FORBIDDEN_IMPORT_ROOTS):
        errors.append(f"EFFECT_OR_NETWORK_IMPORT_PROHIBITED:{name}")

    contracts_text = (PACKAGE / "contracts.py").read_text(encoding="utf-8")
    policy_text = (PACKAGE / "policy.py").read_text(encoding="utf-8")
    missing_effects = sorted(code for code in REQUIRED_EFFECT_ENUMS if code not in contracts_text)
    errors.extend(f"PROHIBITED_EFFECT_ENUM_MISSING:{code}" for code in missing_effects)
    if "for effect in action.requested_effects" not in policy_text:
        errors.append("CLOSED_EFFECT_POLICY_MISSING")
    provider_text = (PACKAGE / "provider.py").read_text(encoding="utf-8")
    worker_text = (PACKAGE / "worker.py").read_text(encoding="utf-8")
    if "Protocol" in provider_text or ".review(" in worker_text:
        errors.append("EXECUTABLE_PROVIDER_BOUNDARY_PRESENT")

    contract_path = ROOT / "BUILD_CONTRACT.json"
    if contract_path.exists():
        try:
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            states = contract.get("states", {})
            if states.get("deployed") is not False or states.get("proven") is not False:
                errors.append("MATURITY_OVERCLAIM")
        except json.JSONDecodeError:
            errors.append("BUILD_CONTRACT_INVALID_JSON")

    learning_path = ROOT / "LEARNING_INCIDENTS.json"
    if learning_path.exists():
        try:
            learning = json.loads(learning_path.read_text(encoding="utf-8"))
            if (
                learning.get("schemaVersion") != "SIG-LEARNING-1.1"
                or learning.get("fingerprintAlgorithm")
                != "sha256(canonical JSON of fingerprintFields)[:16]"
                or learning.get("fingerprintFields") != LEARNING_FINGERPRINT_FIELDS
                or learning.get("authorityExpansion") is not False
                or learning.get("recurringCost") != 0
                or learning.get("selfPromotionAllowed") is not False
                or learning.get("behaviorProven") is not False
            ):
                errors.append("LEARNING_BOUNDARY_INVALID")
            test_text = "\n".join(
                path.read_text(encoding="utf-8") for path in sorted((ROOT / "tests").glob("test_*.py"))
            )
            incidents = learning.get("incidents")
            if not isinstance(incidents, list) or not incidents:
                errors.append("LEARNING_INCIDENTS_REQUIRED")
            else:
                seen: set[str] = set()
                for row in incidents:
                    if not isinstance(row, dict):
                        errors.append("LEARNING_INCIDENT_ROW_INVALID")
                        continue
                    fingerprint_payload = {
                        field: row.get(field) for field in LEARNING_FINGERPRINT_FIELDS
                    }
                    encoded = json.dumps(
                        fingerprint_payload,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ).encode("utf-8")
                    expected = hashlib.sha256(encoded).hexdigest()[:16]
                    if row.get("fingerprint") != expected or expected in seen:
                        errors.append(f"LEARNING_FINGERPRINT_INVALID:{expected}")
                    seen.add(expected)
                    for key in LEARNING_REQUIRED_TEXT_FIELDS:
                        if not isinstance(row.get(key), str) or not row[key].strip():
                            errors.append(f"LEARNING_FIELD_MISSING:{expected}:{key}")
                    for key in ("failureFirstTest", "healthyCaseTest"):
                        if row.get(key) not in test_text:
                            errors.append(f"LEARNING_TEST_MISSING:{expected}:{key}")
                    if row.get("severity") not in {"HIGH", "CRITICAL"}:
                        errors.append(f"LEARNING_SEVERITY_INVALID:{expected}")
                    recurrence = row.get("recurrenceCount")
                    if isinstance(recurrence, bool) or not isinstance(recurrence, int) or recurrence < 1:
                        errors.append(f"LEARNING_RECURRENCE_INVALID:{expected}")
                    if row.get("metricBreached") is not True:
                        errors.append(f"LEARNING_METRIC_STATE_INVALID:{expected}")
                    if row.get("authorityEffect") != "NONE" or row.get("costEffect") != 0:
                        errors.append(f"LEARNING_AUTHORITY_OR_COST_EXPANSION:{expected}")
                    if row.get("independentReview") != {
                        "result": "BLOCK_REPRODUCED", "route": row.get("sourceReview")
                    }:
                        errors.append(f"LEARNING_REVIEW_INVALID:{expected}")
                    if row.get("forwardTest") != {
                        "status": "PENDING", "behaviorProven": False
                    }:
                        errors.append(f"LEARNING_FORWARD_TEST_OVERCLAIM:{expected}")
                    if row.get("state") != "REMEDIATED_PENDING_FROZEN_SOURCE_RECHECK":
                        errors.append(f"LEARNING_STATE_OVERCLAIM:{expected}")
        except (OSError, json.JSONDecodeError, AttributeError):
            errors.append("LEARNING_INCIDENTS_INVALID_JSON")

    result = {
        "classification": "DURABLE_FOUNDATION_IMPLEMENTED_NOT_DEPLOYED",
        "valid": not errors,
        "errors": sorted(set(errors)),
        "effect_imports": [],
        "network_imports": [],
        "provider_execution_supported": False,
        "cloud_mutation_performed": False,
        "release_authority": "NONE",
        "source_hashes": source_hashes,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
