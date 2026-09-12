from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping


SCORECARD_SCHEMA = "CFBE-OMEGA-FIDELITY-ADAPTER-CERTIFICATION-SCORECARD-V1"
OBSERVATION_SCHEMA = "CFBE-OMEGA-FIDELITY-ADAPTER-DISCOVERY-OBSERVATION-V1"
VERIFICATION_SCHEMA = "CFBE-OMEGA-FIDELITY-ADAPTER-CERTIFICATION-VERIFICATION-V1"
EXPECTED_PLATFORMS = ("github", "google-drive", "gmail", "canva")
PASSING_CANARY_STATES = frozenset({"PASS", "PASS_WITH_ROUTE_VARIANCE"})
FORBIDDEN_OBSERVATION_KEYS = frozenset(
    {"email", "messageId", "designId", "fileId", "continuation", "token", "secret", "rawBody"}
)


class VerificationError(ValueError):
    """Raised when a scorecard is malformed, unsafe, or hash-inconsistent."""


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _sha(value: object) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise VerificationError(code)


def _require_sha(value: object, code: str) -> None:
    _require(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value),
        code,
    )


def _walk_public_safe(value: object) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            _require(str(key) not in FORBIDDEN_OBSERVATION_KEYS, f"FORBIDDEN_OBSERVATION_KEY:{key}")
            _walk_public_safe(child)
    elif isinstance(value, list):
        for child in value:
            _walk_public_safe(child)
    elif isinstance(value, str):
        _require(
            re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", value, re.IGNORECASE)
            is None,
            "EMAIL_LIKE_VALUE_IN_OBSERVATION",
        )


def verify_scorecard(scorecard: Mapping[str, Any]) -> dict[str, Any]:
    _require(scorecard.get("schema") == SCORECARD_SCHEMA, "SCORECARD_SCHEMA_MISMATCH")
    supplied_receipt = scorecard.get("receiptSha256")
    _require_sha(supplied_receipt, "SCORECARD_RECEIPT_INVALID")
    body = deepcopy(dict(scorecard))
    del body["receiptSha256"]
    _require(_sha(body) == supplied_receipt, "SCORECARD_RECEIPT_MISMATCH")
    _require(scorecard.get("executionState") == "NOT_EXECUTED", "EXECUTION_OVERCLAIM")

    bubbles = scorecard.get("bubblesWave") or {}
    expected_work = sorted(f"CERTIFY-{item.upper()}" for item in EXPECTED_PLATFORMS)
    _require(bubbles.get("selectedWorkIds") == expected_work, "BUBBLES_SELECTION_MISMATCH")
    _require(bubbles.get("heldCount") == 0, "BUBBLES_HELD_WORK_PRESENT")
    _require(bubbles.get("providerEffectAuthorized") is False, "BUBBLES_PROVIDER_EFFECT_AUTHORIZED")
    _require(bubbles.get("financialEffectAuthorized") is False, "BUBBLES_FINANCIAL_EFFECT_AUTHORIZED")
    _require_sha(bubbles.get("receiptSha256"), "BUBBLES_RECEIPT_INVALID")

    courts = scorecard.get("courts")
    _require(isinstance(courts, list), "COURTS_REQUIRED")
    _require(tuple(item.get("platformId") for item in courts) == EXPECTED_PLATFORMS, "COURT_PORTFOLIO_MISMATCH")
    for court in courts:
        platform_id = str(court["platformId"])
        _require(court.get("courtPass") is True, f"COURT_NOT_PASS:{platform_id}")
        _require(court.get("resultState") == "ROUTE_READY_LOCAL", f"COURT_STATE_INVALID:{platform_id}")
        _require(court.get("executionState") == "NOT_EXECUTED", f"COURT_EXECUTION_OVERCLAIM:{platform_id}")
        _require(court.get("fidelityVerdict") == "ACCEPT_ZERO_DILUTION", f"DILUTION_DETECTED:{platform_id}")
        _require(court.get("canonicalPreserved") is True, f"CANONICAL_NOT_PRESERVED:{platform_id}")
        _require(court.get("providerMutationPerformed") is False, f"PROVIDER_MUTATION_PRESENT:{platform_id}")
        _require(isinstance(court.get("selectedAdapters"), list) and len(court["selectedAdapters"]) == 1, f"ADAPTER_SELECTION_INVALID:{platform_id}")
        _require(court.get("requirementCount") == 4, f"REQUIREMENT_COUNT_INVALID:{platform_id}")
        _require(court.get("buildTriggerCount") == 0, f"BUILD_TRIGGER_PRESENT:{platform_id}")
        _require_sha(court.get("connectorContractSha256"), f"CONTRACT_HASH_INVALID:{platform_id}")
        _require_sha(court.get("kernelReceiptSha256"), f"KERNEL_RECEIPT_INVALID:{platform_id}")

    comparison = scorecard.get("comparison") or {}
    _require(comparison.get("platformCount") == 4, "COMPARISON_PLATFORM_COUNT_INVALID")
    _require(comparison.get("courtPassCount") == 4, "COMPARISON_PASS_COUNT_INVALID")
    _require(comparison.get("requirementCountPerCourt") == 4, "COMPARISON_REQUIREMENT_COUNT_INVALID")
    _require(comparison.get("profileSymmetry") is True, "PROFILE_ASYMMETRY")
    _require(comparison.get("canonicalPreservationRate") == 1.0, "PRESERVATION_RATE_INVALID")
    _require(comparison.get("externalEffects") == 0, "EXTERNAL_EFFECT_PRESENT")
    _require(comparison.get("providerWrites") == 0, "PROVIDER_WRITE_PRESENT")
    _require(comparison.get("recurringCost") == 0, "RECURRING_COST_PRESENT")
    _require(comparison.get("ownerBurden") == 0, "OWNER_BURDEN_PRESENT")
    _require(comparison.get("authorityCeiling") == "A1", "AUTHORITY_CEILING_INVALID")

    observation = scorecard.get("connectorObservation") or {}
    payload = observation.get("payload")
    if observation.get("state") == "NOT_SUPPLIED":
        _require(payload is None and observation.get("sha256") == "", "EMPTY_OBSERVATION_INVALID")
        _require(comparison.get("liveCanaryPassCount") == 0, "UNSUPPLIED_CANARY_COUNT_INVALID")
        _require(
            scorecard.get("certificationState") == "LOCAL_COURTS_4_OF_4_PASS",
            "LOCAL_CERTIFICATION_STATE_INVALID",
        )
    else:
        _require(observation.get("state") == "SUPPLIED_PUBLIC_SAFE", "OBSERVATION_STATE_INVALID")
        _require(isinstance(payload, Mapping), "OBSERVATION_PAYLOAD_REQUIRED")
        _require(payload.get("schema") == OBSERVATION_SCHEMA, "OBSERVATION_SCHEMA_MISMATCH")
        _walk_public_safe(payload)
        _require(_sha(payload) == observation.get("sha256"), "OBSERVATION_HASH_MISMATCH")
        _require(payload.get("externalEffects") == 0, "OBSERVATION_EXTERNAL_EFFECT_PRESENT")
        _require(payload.get("providerWrites") == 0, "OBSERVATION_PROVIDER_WRITE_PRESENT")
        _require(payload.get("manualUserTasks") == [], "OBSERVATION_USER_BURDEN_PRESENT")
        source_head = payload.get("sourceHead")
        _require(
            isinstance(source_head, str)
            and len(source_head) == 40
            and all(character in "0123456789abcdef" for character in source_head),
            "OBSERVATION_SOURCE_HEAD_INVALID",
        )
        observed_platforms = payload.get("platforms") or []
        _require(tuple(item.get("platformId") for item in observed_platforms) == EXPECTED_PLATFORMS, "OBSERVATION_PORTFOLIO_MISMATCH")
        pass_count = sum(item.get("readCanaryState") in PASSING_CANARY_STATES for item in observed_platforms)
        _require(pass_count == comparison.get("liveCanaryPassCount"), "OBSERVATION_PASS_COUNT_MISMATCH")
        expected_state = (
            "LIVE_READ_CANARIES_4_OF_4_AND_LOCAL_COURTS_4_OF_4_PASS"
            if pass_count == 4
            else "LIVE_CANARY_FAILURE"
        )
        _require(scorecard.get("certificationState") == expected_state, "LIVE_CERTIFICATION_STATE_INVALID")
        for court, item in zip(courts, observed_platforms, strict=True):
            _require(item.get("connectorContractSha256") == court.get("connectorContractSha256"), f"OBSERVATION_CONTRACT_MISMATCH:{court['platformId']}")
            _require(item.get("readCanaryState") == court.get("readCanaryState"), f"OBSERVATION_STATE_MISMATCH:{court['platformId']}")
            _require(isinstance(item.get("proofRefs"), list) and item["proofRefs"], f"OBSERVATION_PROOF_MISSING:{court['platformId']}")

    truth = scorecard.get("truthBoundary") or {}
    for key in (
        "providerMutationPerformed",
        "providerDeploymentClaimed",
        "authorityInherited",
        "credentialsInherited",
        "stablePromotionAllowed",
    ):
        _require(truth.get(key) is False, f"TRUTH_BOUNDARY_INVALID:{key}")
    _require(truth.get("fullDoctrineRollbackPreserved") is True, "ROLLBACK_TRUTH_BOUNDARY_INVALID")

    verification = {
        "schema": VERIFICATION_SCHEMA,
        "decision": "VERIFIED",
        "scorecardReceiptSha256": supplied_receipt,
        "scorecardDocumentSha256": _sha(scorecard),
        "platformCount": 4,
        "courtPassCount": 4,
        "liveCanaryPassCount": comparison.get("liveCanaryPassCount"),
        "externalEffects": 0,
        "providerWrites": 0,
        "ownerBurden": 0,
        "authorityCeiling": "A1",
        "stablePromotionAllowed": False,
    }
    verification["verificationReceiptSha256"] = _sha(verification)
    return verification


def _write_atomic(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Independently verify a Wave 1 scorecard")
    parser.add_argument("scorecard")
    parser.add_argument("--output")
    args = parser.parse_args()
    scorecard = json.loads(Path(args.scorecard).read_text(encoding="utf-8"))
    receipt = verify_scorecard(scorecard)
    if args.output:
        _write_atomic(args.output, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
