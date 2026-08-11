from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Iterable, Mapping, Sequence


class MaturityStage(IntEnum):
    DESIGN_ONLY = 0
    IMPLEMENTED = 1
    DETERMINISTIC_TESTED = 2
    LOCAL_RUNTIME_VERIFIED = 3
    PROVIDER_CANARY_READY = 4
    PROVIDER_EXECUTED_UNREADBACK = 5
    PROVIDER_VERIFIED = 6
    DEPLOYED = 7
    OPERATIONAL_VERIFIED = 8
    PORTFOLIO_DEMONSTRABLE = 9


PROOF_LADDER: tuple[str, ...] = (
    "source",
    "tests",
    "runtime",
    "provider_canary_contract",
    "provider_execution",
    "provider_readback",
    "deployment_receipt",
    "health",
    "persistence",
    "rollback",
    "observability",
    "user_demo",
    "case_study",
)


STAGE_REQUIREMENTS: dict[MaturityStage, frozenset[str]] = {
    MaturityStage.DESIGN_ONLY: frozenset(),
    MaturityStage.IMPLEMENTED: frozenset({"source"}),
    MaturityStage.DETERMINISTIC_TESTED: frozenset({"source", "tests"}),
    MaturityStage.LOCAL_RUNTIME_VERIFIED: frozenset({"source", "tests", "runtime"}),
    MaturityStage.PROVIDER_CANARY_READY: frozenset(
        {"source", "tests", "runtime", "provider_canary_contract"}
    ),
    MaturityStage.PROVIDER_EXECUTED_UNREADBACK: frozenset(
        {
            "source",
            "tests",
            "runtime",
            "provider_canary_contract",
            "provider_execution",
        }
    ),
    MaturityStage.PROVIDER_VERIFIED: frozenset(
        {
            "source",
            "tests",
            "runtime",
            "provider_canary_contract",
            "provider_execution",
            "provider_readback",
        }
    ),
    MaturityStage.DEPLOYED: frozenset(
        {
            "source",
            "tests",
            "runtime",
            "provider_canary_contract",
            "provider_execution",
            "provider_readback",
            "deployment_receipt",
            "health",
            "persistence",
            "rollback",
        }
    ),
    MaturityStage.OPERATIONAL_VERIFIED: frozenset(
        {
            "source",
            "tests",
            "runtime",
            "provider_canary_contract",
            "provider_execution",
            "provider_readback",
            "deployment_receipt",
            "health",
            "persistence",
            "rollback",
            "observability",
        }
    ),
    MaturityStage.PORTFOLIO_DEMONSTRABLE: frozenset(PROOF_LADDER),
}


@dataclass(frozen=True)
class Project:
    project_id: str
    name: str
    career_value: int
    verified_proofs: frozenset[str] = field(default_factory=frozenset)
    target_stage: MaturityStage = MaturityStage.PORTFOLIO_DEMONSTRABLE
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        unknown = self.verified_proofs.difference(PROOF_LADDER)
        if unknown:
            raise ValueError(f"Unknown proof keys for {self.project_id}: {sorted(unknown)}")
        if not 1 <= self.career_value <= 100:
            raise ValueError("career_value must be between 1 and 100")


@dataclass(frozen=True)
class ProjectAssessment:
    project_id: str
    verified_stage: MaturityStage
    target_stage: MaturityStage
    missing_proofs: tuple[str, ...]
    next_gate: str | None
    career_value: int
    implementation_score: int


class BubblesArchitectTwin:
    """Proof-bound implementation-depth coach and portfolio governor.

    Bubbles never upgrades a project's maturity from labels, filenames, plans,
    code existence, or a generic success response. Stage is derived only from
    explicit proof keys supplied by a caller or loaded from a separately
    verified evidence adapter.
    """

    name = "Bubbles"
    role = "Applied AI Systems Architect Twin"
    authority_ceiling = "A1_INTERNAL"

    def __init__(self, projects: Sequence[Project]) -> None:
        ids = [project.project_id for project in projects]
        if len(ids) != len(set(ids)):
            raise ValueError("project_id values must be unique")
        self._projects = tuple(projects)

    @staticmethod
    def verified_stage(proofs: Iterable[str]) -> MaturityStage:
        proof_set = frozenset(proofs)
        unknown = proof_set.difference(PROOF_LADDER)
        if unknown:
            raise ValueError(f"Unknown proof keys: {sorted(unknown)}")

        attained = MaturityStage.DESIGN_ONLY
        for stage in MaturityStage:
            if STAGE_REQUIREMENTS[stage].issubset(proof_set):
                attained = stage
            else:
                break
        return attained

    @staticmethod
    def missing_for_stage(
        proofs: Iterable[str], target: MaturityStage
    ) -> tuple[str, ...]:
        proof_set = frozenset(proofs)
        required = STAGE_REQUIREMENTS[target]
        return tuple(item for item in PROOF_LADDER if item in required and item not in proof_set)

    @staticmethod
    def next_gate(proofs: Iterable[str], target: MaturityStage) -> str | None:
        missing = BubblesArchitectTwin.missing_for_stage(proofs, target)
        return missing[0] if missing else None

    @staticmethod
    def implementation_score(proofs: Iterable[str]) -> int:
        proof_set = frozenset(proofs)
        earned = sum(1 for item in PROOF_LADDER if item in proof_set)
        return round((earned / len(PROOF_LADDER)) * 100)

    def assess(self, project: Project) -> ProjectAssessment:
        stage = self.verified_stage(project.verified_proofs)
        missing = self.missing_for_stage(project.verified_proofs, project.target_stage)
        return ProjectAssessment(
            project_id=project.project_id,
            verified_stage=stage,
            target_stage=project.target_stage,
            missing_proofs=missing,
            next_gate=missing[0] if missing else None,
            career_value=project.career_value,
            implementation_score=self.implementation_score(project.verified_proofs),
        )

    def rank(self) -> tuple[ProjectAssessment, ...]:
        """Rank by career value, proof proximity, then verified maturity.

        The model deliberately rewards projects that are valuable and close to
        an externally demonstrable proof state rather than projects that merely
        have large architectures.
        """
        assessments = [self.assess(project) for project in self._projects]

        def priority(item: ProjectAssessment) -> tuple[int, int, int]:
            proximity = 100 - len(item.missing_proofs) * 7
            return (item.career_value, proximity, int(item.verified_stage))

        return tuple(sorted(assessments, key=priority, reverse=True))

    def project(self, project_id: str) -> Project:
        for project in self._projects:
            if project.project_id == project_id:
                return project
        raise KeyError(project_id)

    def build_plan(self, project_id: str) -> tuple[str, ...]:
        project = self.project(project_id)
        missing = self.missing_for_stage(project.verified_proofs, project.target_stage)
        actions: list[str] = []
        action_map: Mapping[str, str] = {
            "source": "Implement the minimum complete vertical slice in canonical source.",
            "tests": "Run deterministic happy-path, failure-path, security and regression tests.",
            "runtime": "Run the vertical slice in a real bounded runtime and capture exact runtime evidence.",
            "provider_canary_contract": "Define a harmless provider canary with identity, target, scope, rollback and readback gates.",
            "provider_execution": "Execute one authorised harmless provider canary without broadening authority.",
            "provider_readback": "Independently verify provider identity, target, response and state through provider-native readback.",
            "deployment_receipt": "Deploy the exact tested build and bind the target runtime/revision/image to an immutable receipt.",
            "health": "Prove application health and semantic readiness on the deployed target.",
            "persistence": "Prove data survives process restart/reopen on the target persistence layer.",
            "rollback": "Prove a bounded rollback or restoration path to the prior known-good state.",
            "observability": "Expose structured logs, metrics, traces or equivalent runtime telemetry and retain proof.",
            "user_demo": "Run one end-to-end user-visible journey from input to useful output on the deployed system.",
            "case_study": "Publish a proof-safe case study with architecture, test evidence, runtime proof, limitations and measurable outcome.",
        }
        for proof in missing:
            actions.append(action_map[proof])
        return tuple(actions)

    def proof_receipt(
        self,
        project_id: str,
        observed_proofs: Iterable[str],
    ) -> dict[str, object]:
        project = self.project(project_id)
        observed = frozenset(observed_proofs)
        stage = self.verified_stage(observed)
        return {
            "architect_twin": self.name,
            "role": self.role,
            "project_id": project.project_id,
            "project_name": project.name,
            "authority_ceiling": self.authority_ceiling,
            "verified_stage": stage.name,
            "proofs": [item for item in PROOF_LADDER if item in observed],
            "missing_to_target": list(self.missing_for_stage(observed, project.target_stage)),
            "target_stage": project.target_stage.name,
            "truth_boundary": "Stage derived only from supplied verified proofs; receipt does not create provider authority or deployment.",
        }
