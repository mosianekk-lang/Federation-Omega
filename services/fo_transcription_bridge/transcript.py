from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import timedelta
from typing import Any, Iterable


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float
    speaker: str
    confidence: float | None = None


@dataclass(frozen=True)
class Segment:
    index: int
    start: float
    end: float
    speaker: str
    text: str
    mean_confidence: float | None
    source_chunk: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def duration_seconds(value: Any) -> float:
    """Return seconds for protobuf Duration, timedelta, number, or None."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, timedelta):
        return value.total_seconds()
    total_seconds = getattr(value, "total_seconds", None)
    if callable(total_seconds):
        return float(total_seconds())
    seconds = float(getattr(value, "seconds", 0.0) or 0.0)
    nanos = float(getattr(value, "nanos", 0.0) or 0.0)
    return seconds + nanos / 1_000_000_000


def _mean(values: Iterable[float]) -> float | None:
    material = [value for value in values if value > 0]
    return sum(material) / len(material) if material else None


def words_to_segments(
    words: list[Word],
    *,
    chunk_index: int,
    pause_threshold: float = 1.5,
    max_segment_seconds: float = 30.0,
) -> list[Segment]:
    """Group timestamped words into readable speaker turns."""
    if not words:
        return []

    groups: list[list[Word]] = []
    current: list[Word] = []

    for word in words:
        if not current:
            current = [word]
            continue
        previous = current[-1]
        speaker_changed = word.speaker != previous.speaker
        pause = max(0.0, word.start - previous.end)
        too_long = word.end - current[0].start >= max_segment_seconds
        if speaker_changed or pause >= pause_threshold or too_long:
            groups.append(current)
            current = [word]
        else:
            current.append(word)

    if current:
        groups.append(current)

    segments: list[Segment] = []
    for group in groups:
        text = " ".join(item.text.strip() for item in group if item.text.strip()).strip()
        if not text:
            continue
        segments.append(
            Segment(
                index=len(segments) + 1,
                start=max(0.0, group[0].start),
                end=max(group[0].start, group[-1].end),
                speaker=group[0].speaker or f"Chunk{chunk_index:03d}-Speaker-UNRESOLVED",
                text=text,
                mean_confidence=_mean(
                    item.confidence for item in group if item.confidence is not None
                ),
                source_chunk=chunk_index,
            )
        )
    return segments


def renumber_segments(segments: list[Segment]) -> list[Segment]:
    return [
        Segment(
            index=index,
            start=item.start,
            end=item.end,
            speaker=item.speaker,
            text=item.text,
            mean_confidence=item.mean_confidence,
            source_chunk=item.source_chunk,
        )
        for index, item in enumerate(sorted(segments, key=lambda x: (x.start, x.end)), 1)
    ]


def format_timestamp(seconds: float, *, srt: bool) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    separator = "," if srt else "."
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def render_srt(segments: list[Segment]) -> str:
    blocks: list[str] = []
    for index, segment in enumerate(segments, 1):
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{format_timestamp(segment.start, srt=True)} --> "
                    f"{format_timestamp(segment.end, srt=True)}",
                    f"[{segment.speaker}] {segment.text}",
                ]
            )
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def render_vtt(segments: list[Segment]) -> str:
    blocks = ["WEBVTT", ""]
    for segment in segments:
        blocks.extend(
            [
                f"{format_timestamp(segment.start, srt=False)} --> "
                f"{format_timestamp(segment.end, srt=False)}",
                f"<{segment.speaker}>{segment.text}",
                "",
            ]
        )
    return "\n".join(blocks)


def render_text(segments: list[Segment]) -> str:
    lines: list[str] = []
    for segment in segments:
        lines.append(
            f"[{format_timestamp(segment.start, srt=False)}] "
            f"{segment.speaker}: {segment.text}"
        )
    return "\n\n".join(lines) + ("\n" if lines else "")
