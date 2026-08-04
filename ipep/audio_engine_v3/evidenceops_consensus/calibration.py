from __future__ import annotations

from dataclasses import dataclass, asdict

from .normalize import normalize_phrase


def _tokens(text: str) -> list[str]:
    value = normalize_phrase(text)
    return value.split() if value else []


def edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for i, ref in enumerate(reference, start=1):
        current = [i]
        for j, hyp in enumerate(hypothesis, start=1):
            current.append(min(
                current[-1] + 1,
                previous[j] + 1,
                previous[j - 1] + (ref != hyp),
            ))
        previous = current
    return previous[-1]


def word_error_rate(reference: str, hypothesis: str) -> float:
    ref = _tokens(reference)
    hyp = _tokens(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return edit_distance(ref, hyp) / len(ref)


@dataclass(frozen=True)
class CalibrationResult:
    model: str
    architecture_family: str
    wer: float
    weight: float
    sample_words: int

    def to_dict(self):
        return asdict(self)


def calibrate_weights(
    reference: str,
    hypotheses: dict[str, tuple[str, str]],
    *,
    minimum_weight: float = 0.35,
    maximum_weight: float = 1.50,
) -> list[CalibrationResult]:
    """Calibrate model weights against one human-verified hearing sample."""
    sample_words = len(_tokens(reference))
    raw = []
    for model, (family, text) in hypotheses.items():
        wer = word_error_rate(reference, text)
        score = 1.0 / max(0.05, 0.15 + wer)
        raw.append((model, family, wer, score))
    if not raw:
        return []
    mean_score = sum(item[3] for item in raw) / len(raw)
    results = []
    for model, family, wer, score in raw:
        weight = min(maximum_weight, max(minimum_weight, score / mean_score))
        results.append(CalibrationResult(model, family, round(wer, 6), round(weight, 6), sample_words))
    return sorted(results, key=lambda item: (item.wer, item.model))
