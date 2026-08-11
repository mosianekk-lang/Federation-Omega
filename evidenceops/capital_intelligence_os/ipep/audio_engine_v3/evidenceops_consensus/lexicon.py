from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from difflib import SequenceMatcher
import json

from .models import Correction
from .normalize import normalize_phrase


@dataclass(frozen=True)
class LexiconEntry:
    canonical: str
    aliases: tuple[str, ...]
    min_similarity: float = 0.92
    allow_fuzzy: bool = False


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(part for part in normalize_phrase(value).split() if part)


def _safe_phrase_similarity(observed: str, expected: str) -> float:
    """Conservative phrase score that preserves word boundaries."""
    a, b = _tokens(observed), _tokens(expected)
    if not a or not b or abs(len(a) - len(b)) > 1:
        return 0.0
    first = SequenceMatcher(None, a[0], b[0]).ratio()
    last = SequenceMatcher(None, a[-1], b[-1]).ratio()
    if max(first, last) < 0.72:
        return 0.0
    sequence = SequenceMatcher(None, " ".join(a), " ".join(b)).ratio()
    overlap = len(set(a) & set(b)) / max(len(set(a) | set(b)), 1)
    return 0.7 * sequence + 0.3 * overlap


class LegalLexicon:
    """Auditable legal/entity correction.

    Default behaviour is exact approved-alias replacement. Fuzzy replacement
    must be enabled per entry and pass conservative token-boundary checks.
    """

    def __init__(self, entries: tuple[LexiconEntry, ...] = ()):
        self.entries = entries

    @classmethod
    def from_json(cls, path: str | Path) -> "LegalLexicon":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(tuple(
            LexiconEntry(
                canonical=item["canonical"],
                aliases=tuple(item.get("aliases", [])),
                min_similarity=float(item.get("min_similarity", 0.92)),
                allow_fuzzy=bool(item.get("allow_fuzzy", False)),
            )
            for item in raw.get("entries", [])
        ))

    def apply(self, tokens: list[str]) -> tuple[list[str], list[Correction]]:
        if not self.entries or not tokens:
            return tokens, []
        out = list(tokens)
        corrections: list[Correction] = []
        candidates = sorted(
            self.entries,
            key=lambda x: max([len(x.canonical.split()), *[len(a.split()) for a in x.aliases]]),
            reverse=True,
        )
        i = 0
        while i < len(out):
            applied = False
            for entry in candidates:
                variants = (entry.canonical,) + entry.aliases
                for variant in variants:
                    width = len(_tokens(variant))
                    if width < 1 or i + width > len(out):
                        continue
                    observed = " ".join(out[i:i + width])
                    observed_norm = normalize_phrase(observed)
                    variant_norm = normalize_phrase(variant)
                    if observed_norm == variant_norm:
                        score = 1.0
                    elif entry.allow_fuzzy:
                        score = _safe_phrase_similarity(observed, variant)
                    else:
                        score = 0.0
                    if score >= entry.min_similarity and observed_norm != normalize_phrase(entry.canonical):
                        replacement = entry.canonical.split()
                        out[i:i + width] = replacement
                        corrections.append(Correction(
                            kind="LEGAL_LEXICON",
                            before=observed,
                            after=entry.canonical,
                            reason=f"matched approved alias {variant!r} at score {score:.3f}",
                            index=i,
                        ))
                        i += len(replacement)
                        applied = True
                        break
                if applied:
                    break
            if not applied:
                i += 1
        return out, corrections
