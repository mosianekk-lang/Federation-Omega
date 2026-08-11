from __future__ import annotations

from .models import Correction
from .normalize import normalize_token


def suppress_repetition(tokens: list[str], max_repeat: int = 2, max_ngram: int = 6) -> tuple[list[str], list[Correction]]:
    out: list[str] = []
    corrections: list[Correction] = []
    i = 0
    while i < len(tokens):
        removed = False
        for width in range(min(max_ngram, (len(tokens) - i) // (max_repeat + 1)), 0, -1):
            phrase = tokens[i:i + width]
            normalized = [normalize_token(x) for x in phrase]
            if not all(normalized):
                continue
            repeats = 1
            while i + (repeats + 1) * width <= len(tokens):
                nxt = [normalize_token(x) for x in tokens[i + repeats * width:i + (repeats + 1) * width]]
                if nxt != normalized:
                    break
                repeats += 1
            if repeats > max_repeat:
                out.extend(phrase * max_repeat)
                before = " ".join(tokens[i:i + repeats * width])
                after = " ".join(phrase * max_repeat)
                corrections.append(Correction(
                    kind="REPETITION_SUPPRESSION",
                    before=before,
                    after=after,
                    reason=f"collapsed {repeats} consecutive repeats to {max_repeat}",
                    index=len(out) - len(phrase) * max_repeat,
                ))
                i += repeats * width
                removed = True
                break
        if not removed:
            out.append(tokens[i])
            i += 1
    return out, corrections
