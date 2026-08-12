from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from .launch_now import LaunchDecision, LaunchRoute
from .zero_possession import IntegrityReceipt, ZeroPossessionReceiptService


THREAT_MODEL = Path(__file__).resolve().parent / "LAUNCH_NOW_THREAT_MODEL.json"


def load_threat_model(path: str | Path = THREAT_MODEL) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    ids = [str(item["id"]) for item in payload["threats"]]
    gates = [str(item["test_gate"]) for item in payload["threats"]]
    if len(ids) != len(set(ids)) or len(gates) != len(set(gates)):
        raise ValueError("threat IDs and test gates must be unique")
    return payload


def tamper_is_rejected(service: ZeroPossessionReceiptService, receipt: IntegrityReceipt) -> bool:
    tampered = replace(receipt, document_sha256=("0" if receipt.document_sha256[0] != "0" else "1") + receipt.document_sha256[1:])
    return service.verify(receipt) and not service.verify(tampered)


def launch_decision_is_truth_safe(decision: LaunchDecision) -> bool:
    label = decision.public_label.upper()
    if decision.route == LaunchRoute.ASSISTED_CERTIFICATION_DISPATCH:
        return decision.commissioner_required and "PENDING" in label and "CERTIFIED_COPY" not in label
    if decision.route == LaunchRoute.ASSISTED_AFFIDAVIT_DISPATCH:
        return decision.commissioner_required and "PENDING" in label and "COMMISSIONED_AFFIDAVIT" not in label
    if decision.route == LaunchRoute.SELF_SERVICE_INTEGRITY:
        return not decision.commissioner_required and decision.launchable_without_idv_contract and "CERTIFIED" not in label
    return True


def deployment_contract_is_safe(script_text: str) -> bool:
    required = (
        "--no-traffic",
        "--no-allow-unauthenticated",
        "ECERTIFY_MODE=launch_now",
        "ECERTIFY_INTEGRITY_SIGNING_SECRET_NAME",
        "gcloud secrets describe",
    )
    forbidden = (
        "gcloud secrets versions access",
        "--allow-unauthenticated",
    )
    return all(item in script_text for item in required) and all(item not in script_text for item in forbidden)


def registered_security_gates() -> tuple[str, ...]:
    return (
        "ZERO_POSSESSION_REJECTS_DOCUMENT_BYTES",
        "SIGNING_KEY_MINIMUM_256_BITS",
        "TAMPERED_RECEIPT_REJECTED",
        "PUBLIC_LABEL_TRUTH_BOUNDARY_ENFORCED",
        "LEGAL_AND_IDENTITY_BOUNDARIES_PRESERVED",
        "PUBLIC_LAUNCH_NOT_SELF_AUTHORISED",
        "BOUNDED_INPUTS_FAIL_CLOSED",
        "SECRET_HANDLE_NOT_PAYLOAD",
    )


def threat_model_is_fully_gated(path: str | Path = THREAT_MODEL) -> bool:
    model = load_threat_model(path)
    expected = {str(item["test_gate"]) for item in model["threats"]}
    return expected == set(registered_security_gates())
