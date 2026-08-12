from __future__ import annotations

import json
from pathlib import Path

from .engineering_cell import BubblesEngineeringCell, build_roles, build_work_orders


ROOT = Path(__file__).resolve().parent
DEFAULT_ROSTER = ROOT / "engineering_cell_roster.json"
DEFAULT_WORK = ROOT / "initial_work_orders.json"


def load_cell(
    roster_path: str | Path = DEFAULT_ROSTER,
    work_path: str | Path = DEFAULT_WORK,
) -> BubblesEngineeringCell:
    roster_payload = json.loads(Path(roster_path).read_text(encoding="utf-8"))
    work_payload = json.loads(Path(work_path).read_text(encoding="utf-8"))
    return BubblesEngineeringCell(
        build_roles(roster_payload["roles"]),
        build_work_orders(work_payload["work_orders"]),
    )


def status() -> dict[str, object]:
    cell = load_cell()
    report = cell.accountability_report()
    report["active_work"] = [item.work_id for item in cell.next_internal_work()]
    report["externally_blocked_work"] = [item.work_id for item in cell.externally_blocked_work()]
    return report
