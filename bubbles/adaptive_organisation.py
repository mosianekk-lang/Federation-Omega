from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence


class ProofState(str, Enum):
    UNKNOWN = "UNKNOWN"
    PRESENT = "PRESENT"
    VERIFIED = "VERIFIED"
    STALE = "STALE"
    BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"


class NodeKind(str, Enum):
    CLAIM = "CLAIM"
    SOURCE = "SOURCE"
    IMPLEMENTATION = "IMPLEMENTATION"
    TEST = "TEST"
    RUNTIME = "RUNTIME"
    PROVIDER_READBACK = "PROVIDER_READBACK"
    DEMO = "DEMO"
    OUTCOME = "OUTCOME"


@dataclass(frozen=True)
class CapabilitySurface:
    name: str
    connected: bool
    can_read: bool = False
    can_write: bool = False
    can_execute: bool = False
    authority: str = "NONE"
    evidence_ref: str | None = None


@dataclass(frozen=True)
class ProofNode:
    node_id: str
    kind: NodeKind
    state: ProofState
    evidence_ref: str | None = None
    source_sha: str | None = None
    note: str = ""


@dataclass(frozen=True)
class ProofEdge:
    from_node: str
    to_node: str
    relation: str


@dataclass
class ProofGraph:
    nodes: dict[str, ProofNode] = field(default_factory=dict)
    edges: list[ProofEdge] = field(default_factory=list)

    def add_node(self, node: ProofNode) -> None:
        self.nodes[node.node_id] = node

    def add_edge(self, edge: ProofEdge) -> None:
        if edge.from_node not in self.nodes or edge.to_node not in self.nodes:
            raise ValueError("ProofGraph edges must reference existing nodes")
        self.edges.append(edge)

    def upstream(self, node_id: str) -> tuple[ProofNode, ...]:
        if node_id not in self.nodes:
            raise KeyError(node_id)
        seen: set[str] = set()
        frontier = [node_id]
        while frontier:
            current = frontier.pop()
            for edge in self.edges:
                if edge.to_node == current and edge.from_node not in seen:
                    seen.add(edge.from_node)
                    frontier.append(edge.from_node)
        return tuple(self.nodes[item] for item in sorted(seen))

    def claim_ready(self, claim_id: str, required_kinds: Iterable[NodeKind]) -> bool:
        proof = self.upstream(claim_id)
        verified = {node.kind for node in proof if node.state == ProofState.VERIFIED}
        return set(required_kinds).issubset(verified)

    def to_dict(self) -> dict[str, object]:
        return {
            "nodes": [
                {
                    **asdict(node),
                    "kind": node.kind.value,
                    "state": node.state.value,
                }
                for node in self.nodes.values()
            ],
            "edges": [asdict(edge) for edge in self.edges],
        }


@dataclass(frozen=True)
class WorkCandidate:
    work_id: str
    objective: str
    proof_gap: str
    action_type: str
    target: str
    required_disciplines: tuple[str, ...]
    value: float
    proof_gain: float
    career_or_product_leverage: float
    unblock_impact: float
    cost: float = 1.0
    risk: float = 1.0
    dependency_load: float = 1.0
    executable: bool = True
    source_sha: str | None = None

    @property
    def score(self) -> float:
        numerator = (
            max(self.value, 0.0)
            * max(self.proof_gain, 0.0)
            * max(self.career_or_product_leverage, 0.0)
            * max(self.unblock_impact, 0.0)
        )
        denominator = max(self.cost, 0.1) * max(self.risk, 0.1) * max(self.dependency_load, 0.1)
        return numerator / denominator

    @property
    def fingerprint(self) -> str:
        canonical = "|".join(
            part.strip().casefold()
            for part in (self.objective, self.proof_gap, self.action_type, self.target)
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SquadPlan:
    mission_id: str
    members: tuple[str, ...]
    rationale: Mapping[str, tuple[str, ...]]
    capability_constraints: tuple[str, ...]


@dataclass
class MissionManifest:
    mission_id: str
    objective: str
    current_source_sha: str | None = None
    current_maturity: str = "UNKNOWN"
    proof_receipts: list[str] = field(default_factory=list)
    open_blockers: list[str] = field(default_factory=list)
    active_work_ids: list[str] = field(default_factory=list)
    completed_fingerprints: list[str] = field(default_factory=list)
    approved_claims: list[str] = field(default_factory=list)
    next_gate: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: str | Path) -> "MissionManifest":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(**payload)


ROLE_DISCIPLINES: Mapping[str, tuple[str, ...]] = {
    "Bubbles": ("architecture", "orchestration", "proof-prioritisation"),
    "Forge": ("software", "runtime", "api", "persistence", "testing"),
    "Sparks": ("cloud", "provider", "deployment", "ci-cd", "identity"),
    "Pulse": ("evaluation", "benchmark", "science", "model-quality"),
    "Patch": ("reliability", "resilience", "observability", "recovery"),
    "Ledger": ("evidence", "claims", "provenance", "readback"),
    "Sentinel": ("security", "privacy", "threat-model", "trust"),
    "Bridge": ("integration", "automation", "queue", "connector"),
    "Scout": ("research", "innovation", "hypothesis"),
    "Prism": ("ux", "demo", "explainability"),
    "Beacon": ("product", "pilot", "metrics", "commercialisation"),
    "Showcase": ("portfolio", "career", "case-study", "communication"),
}

PROOF_GAP_DISCIPLINES: Mapping[str, tuple[str, ...]] = {
    "source": ("software",),
    "tests": ("testing", "evaluation"),
    "runtime": ("runtime", "reliability"),
    "provider_execution": ("provider", "security"),
    "provider_readback": ("readback", "provider"),
    "observability": ("observability",),
    "security": ("security",),
    "integration": ("integration",),
    "benchmark": ("evaluation", "science"),
    "user_demo": ("demo", "ux"),
    "pilot": ("pilot", "metrics"),
    "case_study": ("case-study", "claims"),
    "research": ("research",),
}


class BubblesOmega2:
    """Adaptive orchestration layer for the Bubbles Applied AI Engineering Cell.

    Omega2 adds capability discovery, minimum-viable squad formation, proof graphs,
    execution-economics ranking, duplicate/stale-state detection, an architecture
    anti-proliferation gate and synchronized engineering/human proof outputs.

    It is intentionally fail-closed: named roles model execution disciplines; this
    class does not claim background workers, credentials, provider authority or live
    deployment merely because the orchestration model exists.
    """

    version = "BUBBLES-CELL-OMEGA2"

    def __init__(self, roles: Mapping[str, Sequence[str]] | None = None) -> None:
        self.roles = {name: tuple(items) for name, items in (roles or ROLE_DISCIPLINES).items()}
        if "Bubbles" not in self.roles:
            raise ValueError("Bubbles must remain mission controller")

    def discover_capabilities(self, surfaces: Iterable[CapabilitySurface]) -> dict[str, object]:
        records = tuple(surfaces)
        connected = tuple(sorted(item.name for item in records if item.connected))
        executable = tuple(sorted(item.name for item in records if item.connected and item.can_execute))
        writable = tuple(sorted(item.name for item in records if item.connected and item.can_write))
        constraints = tuple(
            sorted(
                f"{item.name}:NO_EXECUTE"
                for item in records
                if item.connected and not item.can_execute
            )
        )
        return {
            "connected": connected,
            "writable": writable,
            "executable": executable,
            "constraints": constraints,
            "provider_authority_proven": any(
                item.connected and item.can_execute and item.authority not in {"", "NONE", "UNKNOWN"}
                for item in records
            ),
        }

    def select_squad(
        self,
        mission_id: str,
        required_disciplines: Iterable[str] = (),
        proof_gaps: Iterable[str] = (),
        capability_constraints: Iterable[str] = (),
    ) -> SquadPlan:
        wanted = {item.strip().casefold() for item in required_disciplines if item.strip()}
        for gap in proof_gaps:
            wanted.update(item.casefold() for item in PROOF_GAP_DISCIPLINES.get(gap, ()))

        rationale: dict[str, tuple[str, ...]] = {"Bubbles": ("mission-controller",)}
        members = ["Bubbles"]
        uncovered = set(wanted)

        candidates: list[tuple[int, int, str, set[str]]] = []
        for sequence, (name, disciplines) in enumerate(self.roles.items()):
            if name == "Bubbles":
                continue
            coverage = {item.casefold() for item in disciplines}.intersection(wanted)
            if coverage:
                candidates.append((-len(coverage), sequence, name, coverage))

        for _, _, name, coverage in sorted(candidates):
            net_new = coverage.intersection(uncovered)
            if not net_new:
                continue
            members.append(name)
            rationale[name] = tuple(sorted(net_new))
            uncovered.difference_update(net_new)
            if not uncovered:
                break

        if uncovered:
            rationale["Bubbles"] = tuple(sorted(set(rationale["Bubbles"]).union({f"uncovered:{x}" for x in uncovered})))

        return SquadPlan(
            mission_id=mission_id,
            members=tuple(members),
            rationale=rationale,
            capability_constraints=tuple(sorted(set(capability_constraints))),
        )

    def is_stale(self, candidate: WorkCandidate, manifest: MissionManifest) -> bool:
        return bool(
            candidate.source_sha
            and manifest.current_source_sha
            and candidate.source_sha != manifest.current_source_sha
        )

    def is_duplicate(self, candidate: WorkCandidate, manifest: MissionManifest) -> bool:
        return candidate.fingerprint in set(manifest.completed_fingerprints)

    def architecture_gate(
        self,
        candidate: WorkCandidate,
        all_candidates: Iterable[WorkCandidate],
        manifest: MissionManifest,
    ) -> tuple[bool, str]:
        if candidate.action_type != "NEW_ARCHITECTURE":
            return True, "NOT_NEW_ARCHITECTURE"
        alternatives = [
            item
            for item in all_candidates
            if item.work_id != candidate.work_id
            and item.executable
            and item.action_type != "NEW_ARCHITECTURE"
            and not self.is_duplicate(item, manifest)
            and not self.is_stale(item, manifest)
            and item.proof_gain > 0
        ]
        if alternatives:
            best = max(alternatives, key=lambda item: item.score)
            return False, f"EXECUTABLE_PROOF_GAP_TAKES_PRIORITY:{best.work_id}"
        return True, "NO_HIGHER_VALUE_EXECUTABLE_PROOF_GAP"

    def rank_work(
        self,
        candidates: Iterable[WorkCandidate],
        manifest: MissionManifest,
    ) -> tuple[WorkCandidate, ...]:
        source = tuple(candidates)
        admitted: list[WorkCandidate] = []
        for item in source:
            if not item.executable or self.is_duplicate(item, manifest) or self.is_stale(item, manifest):
                continue
            allowed, _ = self.architecture_gate(item, source, manifest)
            if allowed:
                admitted.append(item)
        return tuple(sorted(admitted, key=lambda item: (-item.score, item.work_id)))

    def choose_next(
        self,
        candidates: Iterable[WorkCandidate],
        manifest: MissionManifest,
    ) -> WorkCandidate | None:
        ranked = self.rank_work(candidates, manifest)
        return ranked[0] if ranked else None

    def dual_output(
        self,
        *,
        manifest: MissionManifest,
        engineering_receipts: Iterable[str],
        proposed_human_claims: Iterable[str],
    ) -> dict[str, object]:
        approved = set(manifest.approved_claims)
        claims = tuple(claim for claim in proposed_human_claims if claim in approved)
        rejected = tuple(claim for claim in proposed_human_claims if claim not in approved)
        return {
            "engineering_truth": {
                "mission_id": manifest.mission_id,
                "objective": manifest.objective,
                "maturity": manifest.current_maturity,
                "source_sha": manifest.current_source_sha,
                "receipts": tuple(engineering_receipts),
                "blockers": tuple(manifest.open_blockers),
                "next_gate": manifest.next_gate,
            },
            "human_proof": {
                "approved_claims": claims,
                "rejected_unproven_claims": rejected,
                "truth_boundary": "Human-facing proof may use only Ledger-approved claims.",
            },
        }
