from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True)
class PhaseStatus:
    phase_id: str
    status: str
    evidence_refs: tuple[str, ...]
    provider: str
    operational: bool
    blockers: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.phase_id or not self.status or not self.provider:
            raise ValueError("phase_id, status and provider are required")
        if self.operational and not self.evidence_refs:
            raise ValueError("operational phases require evidence_refs")


@dataclass(frozen=True)
class SuccessionContract:
    source_commit: str
    programme_id: str
    owner: str
    recovery_runbook: str
    rollback_runbook: str
    authority_model: str
    proof_index: tuple[str, ...]

    def validate(self) -> None:
        required = (
            self.source_commit,
            self.programme_id,
            self.owner,
            self.recovery_runbook,
            self.rollback_runbook,
            self.authority_model,
        )
        if not all(item.strip() for item in required):
            raise ValueError("succession contract fields are required")
        if not self.proof_index:
            raise ValueError("proof_index is required")


class InstitutionalSuccessionPlanner:
    """Builds a portable succession bundle without overstating maturity."""

    def evaluate(
        self,
        phases: Iterable[PhaseStatus],
        contract: SuccessionContract,
        provider_authority: Mapping[str, str],
    ) -> dict[str, Any]:
        contract.validate()
        phase_list = list(phases)
        if not phase_list:
            raise ValueError("at least one phase status is required")
        phase_ids: set[str] = set()
        blockers: list[str] = []
        operational_count = 0
        phase_payload: list[dict[str, Any]] = []

        for phase in phase_list:
            phase.validate()
            if phase.phase_id in phase_ids:
                raise ValueError(f"duplicate phase: {phase.phase_id}")
            phase_ids.add(phase.phase_id)
            operational_count += int(phase.operational)
            blockers.extend(f"{phase.phase_id}:{item}" for item in phase.blockers)
            phase_payload.append(asdict(phase))

        for provider, status in sorted(provider_authority.items()):
            if status not in {"FRESH_VERIFIED", "NOT_REQUIRED"}:
                blockers.append(f"PROVIDER:{provider}:{status}")

        blockers = sorted(set(blockers))
        all_operational = operational_count == len(phase_list)
        complete = all_operational and not blockers
        maturity_status = (
            "INSTITUTIONAL_COMPLETION_VERIFIED"
            if complete
            else "READINESS_VERIFIED_INSTITUTIONAL_COMPLETION_BLOCKED"
        )
        bundle = {
            "programme_id": contract.programme_id,
            "source_commit": contract.source_commit,
            "owner": contract.owner,
            "phase_statuses": phase_payload,
            "operational_phases": operational_count,
            "total_phases": len(phase_list),
            "all_operational": all_operational,
            "provider_authority": dict(sorted(provider_authority.items())),
            "blockers": blockers,
            "maturity_status": maturity_status,
            "recovery_runbook": contract.recovery_runbook,
            "rollback_runbook": contract.rollback_runbook,
            "authority_model": contract.authority_model,
            "proof_index": sorted(set(contract.proof_index)),
        }
        bundle["bundle_hash"] = _digest(bundle)
        return bundle

    def persist(self, bundle: Mapping[str, Any], path: str | Path) -> dict[str, Any]:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + ".tmp")
        temp.write_text(json.dumps(dict(bundle), sort_keys=True, indent=2), encoding="utf-8")
        temp.replace(target)
        readback = json.loads(target.read_text(encoding="utf-8"))
        return {
            "readback_verified": _canonical(readback) == _canonical(bundle),
            "bundle_hash": readback.get("bundle_hash"),
            "path": str(target),
        }
