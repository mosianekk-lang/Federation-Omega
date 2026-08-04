from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .models import ConsensusWord, TranscriptHypothesis, WordHypothesis
from .normalize import normalize_token, similarity


@dataclass
class _Slot:
    votes: list[tuple[WordHypothesis, float]]


def _align(anchor: tuple[WordHypothesis, ...], other: tuple[WordHypothesis, ...]) -> list[tuple[int | None, int | None]]:
    """Needleman-Wunsch alignment using lexical and optional timing proximity."""
    n, m = len(anchor), len(other)
    gap = -1.0
    scores = [[0.0] * (m + 1) for _ in range(n + 1)]
    back: list[list[str | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        scores[i][0] = i * gap
        back[i][0] = "up"
    for j in range(1, m + 1):
        scores[0][j] = j * gap
        back[0][j] = "left"
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            a, b = anchor[i - 1], other[j - 1]
            lexical = similarity(a.text, b.text)
            time_bonus = 0.0
            if a.start is not None and b.start is not None:
                delta = abs(a.start - b.start)
                time_bonus = max(0.0, 0.4 - min(delta, 2.0) * 0.2)
            diag_score = scores[i - 1][j - 1] + (-0.8 + lexical * 2.8 + time_bonus)
            up_score = scores[i - 1][j] + gap
            left_score = scores[i][j - 1] + gap
            best = max((diag_score, "diag"), (up_score, "up"), (left_score, "left"), key=lambda x: x[0])
            scores[i][j], back[i][j] = best
    pairs: list[tuple[int | None, int | None]] = []
    i, j = n, m
    while i or j:
        direction = back[i][j]
        if direction == "diag":
            pairs.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif direction == "up":
            pairs.append((i - 1, None))
            i -= 1
        else:
            pairs.append((None, j - 1))
            j -= 1
    pairs.reverse()
    return pairs


def _weighted_median(values: Iterable[tuple[float, float]]) -> float | None:
    material = sorted((value, weight) for value, weight in values if value is not None and weight > 0)
    if not material:
        return None
    total = sum(weight for _, weight in material)
    running = 0.0
    for value, weight in material:
        running += weight
        if running >= total / 2:
            return value
    return material[-1][0]


def fuse(hypotheses: list[TranscriptHypothesis], review_threshold: float = 0.67) -> list[ConsensusWord]:
    if not hypotheses:
        return []
    anchor_h = max(hypotheses, key=lambda h: (h.weight, len(h.words)))
    slots = [_Slot([(word, anchor_h.weight * max(0.05, word.confidence))]) for word in anchor_h.words]
    insertion_buckets: dict[int, list[tuple[WordHypothesis, float]]] = defaultdict(list)

    for hypothesis in hypotheses:
        if hypothesis is anchor_h:
            continue
        pairs = _align(anchor_h.words, hypothesis.words)
        cursor = 0
        for ai, bi in pairs:
            if ai is not None:
                cursor = ai
            if ai is not None and bi is not None:
                word = hypothesis.words[bi]
                slots[ai].votes.append((word, hypothesis.weight * max(0.05, word.confidence)))
            elif ai is None and bi is not None:
                word = hypothesis.words[bi]
                insertion_buckets[cursor].append((word, hypothesis.weight * max(0.05, word.confidence)))

    result: list[ConsensusWord] = []
    for index, slot in enumerate(slots):
        if index in insertion_buckets:
            grouped: dict[str, list[tuple[WordHypothesis, float]]] = defaultdict(list)
            for word, weight in insertion_buckets[index]:
                grouped[normalize_token(word.text)].append((word, weight))
            for key, votes in grouped.items():
                if not key:
                    continue
                support_models = {word.source for word, _ in votes if word.source}
                weight = sum(v for _, v in votes)
                total_hypothesis_weight = sum(h.weight for h in hypotheses)
                if len(support_models) >= 2 or weight >= total_hypothesis_weight * 0.5:
                    result.append(_consensus_word(votes, review_threshold))
        result.append(_consensus_word(slot.votes, review_threshold))
    return result


def _consensus_word(votes: list[tuple[WordHypothesis, float]], review_threshold: float) -> ConsensusWord:
    grouped: dict[str, list[tuple[WordHypothesis, float]]] = defaultdict(list)
    for word, weight in votes:
        key = normalize_token(word.text)
        if key:
            grouped[key].append((word, weight))
    if not grouped:
        fallback = votes[0][0]
        return ConsensusWord(fallback.text, fallback.start, fallback.end, fallback.speaker, 0.0, (), (), True)
    totals = {key: sum(weight for _, weight in items) for key, items in grouped.items()}
    winner_key = max(totals, key=totals.get)
    winner_votes = grouped[winner_key]
    total_weight = sum(totals.values())
    agreement = totals[winner_key] / total_weight if total_weight else 0.0
    representative = max(winner_votes, key=lambda item: item[1])[0]
    speaker_totals: dict[str, float] = defaultdict(float)
    for word, weight in winner_votes:
        if word.speaker:
            speaker_totals[word.speaker] += weight
    speaker = max(speaker_totals, key=speaker_totals.get) if speaker_totals else representative.speaker
    starts = [(word.start, weight) for word, weight in winner_votes if word.start is not None]
    ends = [(word.end, weight) for word, weight in winner_votes if word.end is not None]
    alternatives = tuple(sorted(((key, value / total_weight) for key, value in totals.items()), key=lambda x: x[1], reverse=True))
    sources = tuple(sorted({word.source for word, _ in winner_votes if word.source}))
    return ConsensusWord(
        text=representative.text,
        start=_weighted_median(starts),
        end=_weighted_median(ends),
        speaker=speaker,
        agreement=round(agreement, 6),
        alternatives=alternatives,
        sources=sources,
        needs_review=agreement < review_threshold or len(sources) < 2,
    )
