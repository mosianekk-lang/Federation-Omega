from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .reference import (
    ConnectorRequest,
    IntegrityError,
    LocalRuntimeConnector,
    OperationConflict,
    PathBoundaryError,
    canonical_json,
)


def _report_hash(report: dict[str, Any]) -> str:
    unsigned = dict(report)
    unsigned.pop("report_sha256", None)
    return hashlib.sha256(canonical_json(unsigned).encode("utf-8")).hexdigest()


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_ects() -> dict[str, Any]:
    cases: list[dict[str, str]] = []

    def record(case_id: str, fn) -> None:
        try:
            fn()
        except Exception as exc:
            cases.append({"case_id": case_id, "state": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})
        else:
            cases.append({"case_id": case_id, "state": "PASS", "detail": "verified"})

    with TemporaryDirectory(prefix="ects-") as temp:
        connector = LocalRuntimeConnector(temp)

        put_receipt = connector.execute(
            ConnectorRequest(
                operation_id="ects-put-001",
                action="put_json",
                resource="records/sample.json",
                payload={"alpha": 1, "beta": ["x", "y"]},
            )
        )

        record(
            "ECTS-001-PUT-READBACK",
            lambda: _assert(
                connector.execute(
                    ConnectorRequest(
                        operation_id="ects-get-001",
                        action="get_json",
                        resource="records/sample.json",
                        expected_sha256=put_receipt.result["content_sha256"],
                    )
                ).result["value"]
                == {"alpha": 1, "beta": ["x", "y"]},
                "readback differed",
            ),
        )

        record(
            "ECTS-002-IDEMPOTENT-REPLAY",
            lambda: _assert(
                connector.execute(
                    ConnectorRequest(
                        operation_id="ects-put-001",
                        action="put_json",
                        resource="records/sample.json",
                        payload={"alpha": 1, "beta": ["x", "y"]},
                    )
                ).replayed,
                "replay was not marked",
            ),
        )

        def conflict() -> None:
            try:
                connector.execute(
                    ConnectorRequest(
                        operation_id="ects-put-001",
                        action="put_json",
                        resource="records/sample.json",
                        payload={"alpha": 999},
                    )
                )
            except OperationConflict:
                return
            raise AssertionError("conflicting replay was accepted")

        record("ECTS-003-CONFLICT-REJECTION", conflict)

        def boundary() -> None:
            try:
                connector.execute(
                    ConnectorRequest(
                        operation_id="ects-list-001",
                        action="list",
                        resource="../escape",
                    )
                )
            except PathBoundaryError:
                return
            raise AssertionError("path traversal was accepted")

        record("ECTS-004-PATH-BOUNDARY", boundary)

        def tamper() -> None:
            path = Path(temp) / "records" / "sample.json"
            path.write_text('{"tampered":true}\n', encoding="utf-8")
            try:
                connector.execute(
                    ConnectorRequest(
                        operation_id="ects-get-002",
                        action="get_json",
                        resource="records/sample.json",
                        expected_sha256=put_receipt.result["content_sha256"],
                    )
                )
            except IntegrityError:
                return
            raise AssertionError("tampered content was accepted")

        record("ECTS-005-TAMPER-DETECTION", tamper)
        record(
            "ECTS-006-JOURNAL-CHAIN",
            lambda: _assert(connector.verify_journal(), "receipt chain failed verification"),
        )

    passed = sum(case["state"] == "PASS" for case in cases)
    report: dict[str, Any] = {
        "standard": "EvidenceOps Connector Test Standard",
        "standard_version": "ECTS-1.0",
        "connector": "LocalRuntimeConnector",
        "case_count": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "state": "PASS" if passed == len(cases) else "FAIL",
        "cases": cases,
    }
    report["report_sha256"] = _report_hash(report)
    return report


if __name__ == "__main__":
    print(json.dumps(run_ects(), indent=2, sort_keys=True))
