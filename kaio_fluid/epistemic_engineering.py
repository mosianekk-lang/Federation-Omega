from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExpectedRecord:
    process: str
    stage: str
    record_type: str
    required: bool
    observed: bool


@dataclass(frozen=True)
class EvidenceDesignRecommendation:
    process: str
    stage: str
    recommendation: str
    priority: str


class EpistemicEngineering:
    """Redesign workflows so future truth is easier to establish."""

    def missing_expected_records(self, records: tuple[ExpectedRecord, ...]) -> tuple[ExpectedRecord, ...]:
        return tuple(r for r in records if r.required and not r.observed)

    def recommendations(self, records: tuple[ExpectedRecord, ...]) -> tuple[EvidenceDesignRecommendation, ...]:
        output: list[EvidenceDesignRecommendation] = []
        for record in self.missing_expected_records(records):
            output.append(
                EvidenceDesignRecommendation(
                    process=record.process,
                    stage=record.stage,
                    recommendation=(
                        f"Instrument stage '{record.stage}' to automatically emit a timestamped, "
                        f"source-identified '{record.record_type}' receipt with actor and version metadata."
                    ),
                    priority="HIGH" if record.required else "MEDIUM",
                )
            )
        return tuple(output)

    def proof_ready_process(self, records: tuple[ExpectedRecord, ...]) -> bool:
        return not self.missing_expected_records(records)
