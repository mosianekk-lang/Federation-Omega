from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .architect_twin import BubblesArchitectTwin, MaturityStage, Project


def load_twin(path: str | Path | None = None) -> BubblesArchitectTwin:
    portfolio_path = Path(path) if path is not None else Path(__file__).with_name("portfolio.json")
    data: dict[str, Any] = json.loads(portfolio_path.read_text(encoding="utf-8"))
    projects = []
    for item in data["projects"]:
        projects.append(
            Project(
                project_id=item["project_id"],
                name=item["name"],
                career_value=int(item["career_value"]),
                verified_proofs=frozenset(item.get("verified_proofs", [])),
                target_stage=MaturityStage[item.get("target_stage", "PORTFOLIO_DEMONSTRABLE")],
                notes=tuple(item.get("notes", [])),
            )
        )
    return BubblesArchitectTwin(projects)


def portfolio_snapshot(path: str | Path | None = None) -> list[dict[str, object]]:
    twin = load_twin(path)
    return [
        {
            "project_id": assessment.project_id,
            "verified_stage": assessment.verified_stage.name,
            "target_stage": assessment.target_stage.name,
            "implementation_score": assessment.implementation_score,
            "career_value": assessment.career_value,
            "next_gate": assessment.next_gate,
            "missing_proofs": list(assessment.missing_proofs),
        }
        for assessment in twin.rank()
    ]


if __name__ == "__main__":
    print(json.dumps(portfolio_snapshot(), indent=2))
