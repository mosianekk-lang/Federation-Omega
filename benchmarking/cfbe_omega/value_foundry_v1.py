from __future__ import annotations

"""CFBE Value Foundry v1.

Composes the existing Sentinel owner-value ingress and Bubbles owner-value /
deployment court with a fail-closed trusted-evidence resolver.  It performs no
provider call, deployment, external mutation, stable promotion, or measurement
invention.
"""

from argparse import ArgumentParser
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from benchmarking.cfbe_omega.federation_competitive_upgrade_fabric_v1 import ResolvedEvidenceRef
from evidenceops.caseforge.owner_value_deployment_court_v2 import evaluate_proof_court
from federation.sentinel_omega.owner_value_ingress import OwnerValueMissionRecord, OwnerValuePairCompiler

SCHEMA = "CFBE-VALUE-FOUNDRY-V1"
EVIDENCE_SCHEMA = "CFBE-TRUSTED-EVIDENCE-RECEIPT-V1"


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def record_hash(value: Mapping[str, Any]) -> str:
    payload = {key: item for key, item in value.items() if key not in {"proof_refs", "proof_refs_json"}}
    return canonical_hash(payload)


@dataclass(frozen=True, slots=True)
class TrustedEvidenceReceipt:
    schema: str
    evidence_id: str
    subject: str
    evidence_class: str
    source_head_sha: str
    record_sha256: str
    payload_sha256: str
    verifier_id: str
    verified_at: str
    independent_readback: bool
    status: str
    receipt_sha256: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "TrustedEvidenceReceipt":
        return cls(
            schema=str(value.get("schema") or ""),
            evidence_id=str(value.get("evidence_id") or ""),
            subject=str(value.get("subject") or ""),
            evidence_class=str(value.get("evidence_class") or ""),
            source_head_sha=str(value.get("source_head_sha") or "").lower(),
            record_sha256=str(value.get("record_sha256") or ""),
            payload_sha256=str(value.get("payload_sha256") or ""),
            verifier_id=str(value.get("verifier_id") or ""),
            verified_at=str(value.get("verified_at") or ""),
            independent_readback=value.get("independent_readback") is True,
            status=str(value.get("status") or ""),
            receipt_sha256=str(value.get("receipt_sha256") or ""),
        )

    def unsigned_mapping(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("receipt_sha256")
        return payload


class TrustedEvidenceResolver:
    """Resolve references only through a caller-bound trusted receipt registry."""

    def __init__(self, registry: Mapping[str, Mapping[str, Any]], trusted_verifiers: Iterable[str]):
        self._registry = dict(registry)
        self._trusted_verifiers = frozenset(str(item).strip() for item in trusted_verifiers if str(item).strip())
        if not self._trusted_verifiers:
            raise ValueError("TRUSTED_VERIFIER_SET_REQUIRED")

    def resolve(
        self,
        reference: str,
        *,
        subject: str,
        source_head_sha: str,
        expected_record_sha256: str,
    ) -> ResolvedEvidenceRef:
        if reference not in self._registry:
            raise ValueError("EVIDENCE_REFERENCE_UNRESOLVED")
        receipt = TrustedEvidenceReceipt.from_mapping(self._registry[reference])
        failures: list[str] = []
        if receipt.schema != EVIDENCE_SCHEMA:
            failures.append("EVIDENCE_SCHEMA_INVALID")
        if receipt.evidence_id != reference:
            failures.append("EVIDENCE_ID_MISMATCH")
        if receipt.subject != subject:
            failures.append("EVIDENCE_SUBJECT_MISMATCH")
        if receipt.source_head_sha != source_head_sha.lower():
            failures.append("EVIDENCE_SOURCE_HEAD_MISMATCH")
        if receipt.record_sha256 != expected_record_sha256:
            failures.append("EVIDENCE_RECORD_HASH_MISMATCH")
        if receipt.verifier_id not in self._trusted_verifiers:
            failures.append("EVIDENCE_VERIFIER_UNTRUSTED")
        if not receipt.independent_readback:
            failures.append("EVIDENCE_INDEPENDENT_READBACK_REQUIRED")
        if receipt.status != "VERIFIED":
            failures.append("EVIDENCE_STATUS_NOT_VERIFIED")
        if not receipt.verified_at:
            failures.append("EVIDENCE_VERIFIED_AT_REQUIRED")
        if receipt.receipt_sha256 != canonical_hash(receipt.unsigned_mapping()):
            failures.append("EVIDENCE_RECEIPT_HASH_MISMATCH")
        if not receipt.payload_sha256.startswith("sha256:") or len(receipt.payload_sha256) != 71:
            failures.append("EVIDENCE_PAYLOAD_HASH_INVALID")
        if failures:
            raise ValueError("|".join(sorted(failures)))
        return ResolvedEvidenceRef(
            evidence_id=receipt.evidence_id,
            subject=receipt.subject,
            verifier_id=receipt.verifier_id,
            payload_sha256=receipt.payload_sha256,
            receipt_sha256=receipt.receipt_sha256,
            independently_read_back=True,
        )


@dataclass(frozen=True, slots=True)
class ValueFoundryReceipt:
    schema: str
    champion_id: str
    candidate_id: str
    source_head_sha: str
    resolved_evidence_count: int
    owner_value_pair_count: int
    owner_value_proven: bool
    provider_deployment_proven: bool
    decision: str
    blockers: tuple[str, ...]
    stable_promotion_allowed: bool
    provider_effect_authorized: bool
    external_effect: bool
    truth_boundary: tuple[str, ...]
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _receipt(
    *, champion_id: str, candidate_id: str, source_head_sha: str,
    resolved_count: int, pair_count: int, owner_value_proven: bool,
    provider_deployment_proven: bool, decision: str, blockers: Iterable[str],
) -> ValueFoundryReceipt:
    payload = {
        "schema": SCHEMA,
        "champion_id": champion_id,
        "candidate_id": candidate_id,
        "source_head_sha": source_head_sha,
        "resolved_evidence_count": resolved_count,
        "owner_value_pair_count": pair_count,
        "owner_value_proven": owner_value_proven,
        "provider_deployment_proven": provider_deployment_proven,
        "decision": decision,
        "blockers": tuple(sorted(set(blockers))),
        "stable_promotion_allowed": False,
        "provider_effect_authorized": False,
        "external_effect": False,
        "truth_boundary": (
            "A reference becomes admissible only after exact registry, subject, source, record, verifier, readback and receipt-hash resolution.",
            "Prospective owner value requires matched measured BASELINE/BUBBLES observations; the foundry never invents measurements.",
            "A successful court may become ready for separate owner promotion review but cannot self-promote.",
            "Source tests do not prove provider deployment, external effect, stable promotion, market leadership or sustained owner value.",
        ),
    }
    return ValueFoundryReceipt(**payload, receipt_sha256=canonical_hash(payload))


def evaluate_value_foundry(
    *,
    champion_id: str,
    candidate_id: str,
    source_head_sha: str,
    owner_value_records: Sequence[Mapping[str, Any]] = (),
    runtime_or_deployment_evidence: Sequence[Mapping[str, Any]] = (),
    evidence_registry: Mapping[str, Mapping[str, Any]],
    trusted_verifiers: Iterable[str],
    minimum_owner_value_pairs: int = 10,
) -> ValueFoundryReceipt:
    if not champion_id.strip() or not candidate_id.strip() or champion_id == candidate_id:
        raise ValueError("FOUNDRY_DISTINCT_CHAMPION_AND_CANDIDATE_REQUIRED")
    resolver = TrustedEvidenceResolver(evidence_registry, trusted_verifiers)
    resolved_count = 0
    try:
        records: list[OwnerValueMissionRecord] = []
        for raw in owner_value_records:
            item = OwnerValueMissionRecord.from_mapping(raw)
            for reference in item.proof_refs:
                resolver.resolve(
                    reference,
                    subject=f"owner-value:{item.observation_id}",
                    source_head_sha=source_head_sha,
                    expected_record_sha256=record_hash(raw),
                )
                resolved_count += 1
            records.append(item)

        grouped: dict[str, list[OwnerValueMissionRecord]] = {}
        for item in records:
            grouped.setdefault(item.pair_id, []).append(item)
        compiled = []
        for pair_id in sorted(grouped):
            if len(grouped[pair_id]) != 2:
                raise ValueError("OWNER_VALUE_PAIR_CARDINALITY_INVALID")
            compiled.append(OwnerValuePairCompiler.compile(*grouped[pair_id]).to_court_mapping())

        runtime_items = []
        for raw in runtime_or_deployment_evidence:
            evidence_id = str(raw.get("evidence_id") or "")
            for reference in tuple(str(item).strip() for item in raw.get("proof_refs") or () if str(item).strip()):
                resolver.resolve(
                    reference,
                    subject=f"runtime:{evidence_id}",
                    source_head_sha=source_head_sha,
                    expected_record_sha256=record_hash(raw),
                )
                resolved_count += 1
            runtime_items.append(raw)

        court = evaluate_proof_court(
            candidate_id=candidate_id,
            source_head_sha=source_head_sha,
            owner_value_observations=compiled,
            runtime_or_deployment_evidence=runtime_items,
            minimum_owner_value_pairs=minimum_owner_value_pairs,
        )
        decision = court.decision
        if decision == "OWNER_VALUE_AND_DEPLOYMENT_PROOF_SATISFIED_PROMOTION_REVIEW_REQUIRED":
            decision = "READY_FOR_SEPARATE_OWNER_PROMOTION_REVIEW"
        return _receipt(
            champion_id=champion_id,
            candidate_id=candidate_id,
            source_head_sha=source_head_sha,
            resolved_count=resolved_count,
            pair_count=court.owner_value_pair_count,
            owner_value_proven=court.owner_value_proven,
            provider_deployment_proven=court.provider_deployment_proven,
            decision=decision,
            blockers=court.blockers,
        )
    except (TypeError, ValueError) as exc:
        return _receipt(
            champion_id=champion_id,
            candidate_id=candidate_id,
            source_head_sha=source_head_sha,
            resolved_count=resolved_count,
            pair_count=0,
            owner_value_proven=False,
            provider_deployment_proven=False,
            decision="HOLD_UNTRUSTED_OR_INCOMPLETE_EVIDENCE",
            blockers=(str(exc),),
        )


def main() -> int:
    parser = ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    receipt = evaluate_value_foundry(**payload).to_dict()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
