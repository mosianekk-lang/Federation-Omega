from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

from .models import Correction
from .normalize import normalize_phrase, similarity


@dataclass(frozen=True)
class LexiconEntry:
    canonical: str
    aliases: tuple[str, ...]
    min_similarity: float = 0.84


class LegalLexicon:
    """Auditable phrase correction. It never invents an entry absent from the lexicon."""

    def __init__(self, entries: tuple[LexiconEntry, ...] = ()):
        self.entries = entries

    @classmethod
    def from_json(cls, path: str | Path) -> "LegalLexicon":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(tuple(
            LexiconEntry(
                canonical=item["canonical"],
                aliases=tuple(item.get("aliases", [])),
                min_similarity=float(item.get("min_similarity", 0.84)),
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
                max_words = max(len(v.split()) for v in variants)
                min_words = max(1, min(len(v.split()) for v in variants) - 1)
                for width in range(max_words + 1, min_words - 1, -1):
                    if i + width > len(out):
                        continue
                    observed = " ".join(out[i:i + width])
                    observed_norm = normalize_phrase(observed)
                    best = max((similarity(observed_norm, normalize_phrase(v)), v) for v in variants)
                    if best[0] >= entry.min_similarity and normalize_phrase(observed) != normalize_phrase(entry.canonical):
                        replacement = entry.canonical.split()
                        out[i:i + width] = replacement
                        corrections.append(Correction(
                            kind="LEGAL_LEXICON",
                            before=observed,
                            after=entry.canonical,
                            reason=f"matched approved alias {best[1]!r} at similarity {best[0]:.3f}",
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
