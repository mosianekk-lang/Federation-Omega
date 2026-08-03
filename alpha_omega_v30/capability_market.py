from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _version_key(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError as exc:
        raise ValueError(f"version must be numeric dotted form: {version}") from exc


@dataclass(frozen=True)
class CapabilitySpec:
    capability_id: str
    version: str
    purpose: str
    interfaces: tuple[str, ...]
    providers: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    fitness: Mapping[str, float] = field(default_factory=dict)
    parent_fingerprint: str | None = None
    proof_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.capability_id or not self.purpose:
            raise ValueError("capability_id and purpose are required")
        _version_key(self.version)
        if not self.interfaces or not self.providers:
            raise ValueError("interfaces and providers are required")
        if any(not 0.0 <= score <= 1.0 for score in self.fitness.values()):
            raise ValueError("fitness scores must be within [0, 1]")

    def payload(self) -> dict[str, Any]:
        self.validate()
        payload = asdict(self)
        payload["interfaces"] = sorted(set(self.interfaces))
        payload["providers"] = sorted(set(self.providers))
        payload["dependencies"] = sorted(set(self.dependencies))
        payload["proof_refs"] = sorted(set(self.proof_refs))
        payload["fitness"] = dict(sorted(self.fitness.items()))
        return payload

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.payload())


class CapabilityRegistry:
    """Append-only registry supporting compatibility, fitness and lineage queries."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def register(self, spec: CapabilitySpec) -> dict[str, Any]:
        payload = spec.payload()
        record = {"fingerprint": spec.fingerprint, "spec": payload}
        records = self._records()
        same_release = [
            item
            for item in records
            if item["spec"]["capability_id"] == spec.capability_id
            and item["spec"]["version"] == spec.version
        ]
        if same_release:
            if same_release[-1]["fingerprint"] != record["fingerprint"]:
                raise ValueError("immutable capability release conflict")
            return same_release[-1]
        if spec.parent_fingerprint and not any(item["fingerprint"] == spec.parent_fingerprint for item in records):
            raise ValueError("parent_fingerprint is not registered")
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        readback = self._records()[-1]
        if readback != record:
            raise IOError("capability registry readback mismatch")
        return record

    def resolve(
        self,
        required_interfaces: Iterable[str],
        provider: str,
        fitness_weights: Mapping[str, float] | None = None,
    ) -> dict[str, Any] | None:
        required = set(required_interfaces)
        weights = dict(fitness_weights or {"correctness": 0.5, "reliability": 0.3, "cost_efficiency": 0.2})
        candidates: list[dict[str, Any]] = []
        for record in self._records():
            spec = record["spec"]
            if provider not in spec["providers"] or not required.issubset(set(spec["interfaces"])):
                continue
            score = sum(float(spec["fitness"].get(key, 0.0)) * weight for key, weight in weights.items())
            candidates.append({**record, "selection_score": score})
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda item: (
                item["selection_score"],
                _version_key(item["spec"]["version"]),
                item["fingerprint"],
            ),
        )

    def lineage(self, fingerprint: str) -> list[str]:
        by_fingerprint = {record["fingerprint"]: record for record in self._records()}
        chain: list[str] = []
        current: str | None = fingerprint
        visited: set[str] = set()
        while current:
            if current in visited:
                raise ValueError("lineage cycle detected")
            visited.add(current)
            record = by_fingerprint.get(current)
            if record is None:
                raise KeyError(current)
            chain.append(current)
            current = record["spec"].get("parent_fingerprint")
        return chain

    def verify(self) -> dict[str, Any]:
        records = self._records()
        fingerprints: set[str] = set()
        releases: set[tuple[str, str]] = set()
        for record in records:
            spec = record["spec"]
            if _fingerprint(spec) != record["fingerprint"]:
                return {"valid": False, "reason": "fingerprint_mismatch"}
            release = (spec["capability_id"], spec["version"])
            if record["fingerprint"] in fingerprints or release in releases:
                return {"valid": False, "reason": "duplicate_release"}
            if spec.get("parent_fingerprint") and spec["parent_fingerprint"] not in fingerprints:
                return {"valid": False, "reason": "invalid_lineage_order"}
            fingerprints.add(record["fingerprint"])
            releases.add(release)
        return {
            "valid": True,
            "records": len(records),
            "head": records[-1]["fingerprint"] if records else "EMPTY",
        }
