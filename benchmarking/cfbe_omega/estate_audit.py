from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class RepoCensus:
    files: int
    python_files: int
    test_files: int
    workflow_files: int
    package_roots: tuple[str, ...]


@dataclass(frozen=True)
class LineageNode:
    name: str
    generation: str
    role: str
    status: str
    successor: str | None = None


@dataclass(frozen=True)
class WorkflowCluster:
    cluster_key: str
    members: tuple[str, ...]
    shared_primitive_candidate: bool
    consolidation_candidate: bool = False


def census_repository(root: str | Path) -> RepoCensus:
    base = Path(root)
    if not base.exists():
        raise FileNotFoundError(base)
    files = [path for path in base.rglob("*") if path.is_file() and ".git" not in path.parts]
    python_files = [path for path in files if path.suffix == ".py"]
    test_files = [
        path
        for path in files
        if path.name.startswith("test_") or "tests" in path.parts
    ]
    workflow_files = [
        path
        for path in files
        if ".github" in path.parts
        and "workflows" in path.parts
        and path.suffix in {".yml", ".yaml"}
    ]
    package_roots = sorted(
        {
            path.parts[len(base.parts)]
            for path in files
            if len(path.parts) > len(base.parts)
            and path.parts[len(base.parts)] not in {".github", "tests", "docs"}
        }
    )
    return RepoCensus(
        files=len(files),
        python_files=len(python_files),
        test_files=len(test_files),
        workflow_files=len(workflow_files),
        package_roots=tuple(package_roots),
    )


def alpha_omega_lineage() -> tuple[LineageNode, ...]:
    """Evidence-first, non-destructive Alpha→Omega lineage.

    Directory names are not treated as semantic version authority. The current
    maturity records show alpha_omega_v21 at 2.2.1 and alpha_omega_v2 at 2.4.0
    with canonical_path=alpha_omega_v2. v3.0 is a separate institutional
    evolution and must not silently inherit provider maturity from either v2
    line.
    """
    return (
        LineageNode(
            "alpha_omega_v21",
            "2.2.1",
            "Operational foundry plus maintenance, drift, repair, learning and Drive manifest controls",
            "HISTORICAL_INTERMEDIATE_RETAIN",
            "alpha_omega_v2",
        ),
        LineageNode(
            "alpha_omega_v2",
            "2.4.0",
            "Canonical v2 operational foundry with GitHub provider proof and outcome/cost governor",
            "CURRENT_CANONICAL_V2_LINE_RETAIN",
            "alpha_omega_v30",
        ),
        LineageNode(
            "alpha_omega_v30",
            "3.0",
            "Self-verifying digital systems institution with proof-carrying actions, capability market and institutional controls",
            "CURRENT_INSTITUTIONAL_EVOLUTION_CANDIDATE",
            None,
        ),
    )


def _workflow_key(filename: str) -> str:
    stem = filename.rsplit(".", 1)[0].lower()
    tokens = stem.split("-")
    tokens = [token for token in tokens if token not in {"release", "now", "manual"}]
    return "-".join(tokens)


def cluster_workflows(filenames: Iterable[str]) -> tuple[WorkflowCluster, ...]:
    """Group naming siblings for semantic review without auto-consolidating them.

    Filename similarity alone is insufficient to declare duplicate workflows.
    Release and implementation siblings may intentionally preserve different
    proof stages. A cluster therefore becomes a shared-primitive candidate only;
    consolidation remains false until step/input/output/proof semantics are
    compared independently.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for filename in sorted(set(filenames)):
        if filename.endswith((".yml", ".yaml")):
            groups[_workflow_key(filename)].append(filename)

    return tuple(
        WorkflowCluster(
            cluster_key=key,
            members=tuple(members),
            shared_primitive_candidate=len(members) > 1,
            consolidation_candidate=False,
        )
        for key, members in sorted(groups.items())
    )


def workflow_family_counts(filenames: Iterable[str]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for name in filenames:
        stem = name.lower()
        if stem.startswith("alpha-omega-commercial-authority-"):
            counts["alpha_omega_commercial_authority"] += 1
        elif stem.startswith("alpha-omega-"):
            counts["alpha_omega_other"] += 1
        elif stem.endswith((".yml", ".yaml")):
            counts["other_workflows"] += 1
    return dict(counts)

