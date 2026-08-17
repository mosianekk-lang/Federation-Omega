from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any


ALLOWED_EPISTEMIC_CLASSES = {"EMPIRICAL_LAW", "MATHEMATICAL_THEOREM", "HEURISTIC", "METAPHOR"}


@lru_cache(maxsize=1)
def doctrine() -> dict[str, Any]:
    path = files("jarvis.resources").joinpath("science_doctrine_v1.json")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    categories = loaded.get("categories", [])
    principles = [principle for category in categories for principle in category.get("principles", [])]
    if len(principles) != 32:
        raise ValueError("SCIENCE_DOCTRINE_COUNT_INVALID")
    if any(principle.get("epistemicClass") not in ALLOWED_EPISTEMIC_CLASSES for principle in principles):
        raise ValueError("SCIENCE_DOCTRINE_CLASS_INVALID")
    if not all(principle.get("operationalUse") and principle.get("limits") and principle.get("falsificationChecks") for principle in principles):
        raise ValueError("SCIENCE_DOCTRINE_SCOPE_INVALID")
    return loaded


def catalogue() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for category in doctrine()["categories"]:
        for principle in category["principles"]:
            rows.append({"category": category["id"], **principle})
    return rows


def doctrine_summary() -> dict[str, Any]:
    loaded = doctrine()
    return {
        "doctrineId": loaded["doctrineId"],
        "status": loaded["status"],
        "categoryCount": len(loaded["categories"]),
        "principleCount": len(catalogue()),
        "epistemicClasses": loaded["epistemicClasses"],
        "scopeRules": loaded["scopeRules"],
    }
