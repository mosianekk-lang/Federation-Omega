from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
import math
import random
from typing import Iterable, Sequence

from .immune_graph import analyze_evidence_graph
from ..schemas import SecurityEvent


FEATURE_NAMES = (
    "max_weighted_risk", "mean_weighted_risk", "source_diversity", "class_diversity",
    "source_concentration", "replay_ratio", "graph_corroboration", "poisoning_resistance",
)


@dataclass(frozen=True, slots=True)
class NeuralSentinelReceipt:
    schema: str
    shadow_only: bool
    synthetic_training_only: bool
    training_samples: int
    holdout_samples: int
    holdout_accuracy: float
    training_loss: float
    model_sha256: str


def _sigmoid(x: float) -> float:
    x = max(-30.0, min(30.0, x))
    return 1.0 / (1.0 + math.exp(-x))


def feature_vector(events: Sequence[SecurityEvent]) -> tuple[float, ...]:
    report = analyze_evidence_graph(events)
    weights = {
        "device_integrity": 1.0, "forensic_artifact": 1.0, "platform_alert": .95,
        "identity_risk": .85, "network_risk": .75, "app_risk": .75, "control_state": .55,
    }
    scores = [max(0.0, min(1.0, e.severity * e.confidence * weights.get(e.event_class.value, .5))) for e in events]
    max_score = max(scores, default=0.0)
    mean_score = sum(scores) / len(scores) if scores else 0.0
    return (
        max_score,
        mean_score,
        min(1.0, report.independent_sources / 4.0),
        min(1.0, report.independent_classes / 4.0),
        report.source_concentration,
        report.replay_ratio,
        report.corroboration_score,
        report.poisoning_resistance_factor,
    )


class NeuralSentinel:
    """Tiny deterministic neural challenger for shadow-mode defensive scoring.

    The reference implementation is intentionally small and dependency-free. It is
    trained only on synthetic defensive scenario features and therefore cannot be
    promoted to production decision authority. Its role is to disagree usefully
    with the deterministic fusion engine and generate falsifiable challenger data.
    """

    SCHEMA = "AEGIS_SHADOW_NEURAL_SENTINEL_V1"

    def __init__(self, *, hidden: int = 6, seed: int = 23) -> None:
        if hidden < 2 or hidden > 32:
            raise ValueError("AEGIS_NEURAL_HIDDEN_OUT_OF_RANGE")
        rng = random.Random(seed)
        n = len(FEATURE_NAMES)
        self.hidden = hidden
        self.w1 = [[rng.uniform(-.35, .35) for _ in range(n)] for _ in range(hidden)]
        self.b1 = [0.0] * hidden
        self.w2 = [rng.uniform(-.35, .35) for _ in range(hidden)]
        self.b2 = 0.0

    def _forward(self, x: Sequence[float]) -> tuple[list[float], float]:
        h = [math.tanh(sum(w * v for w, v in zip(row, x)) + b) for row, b in zip(self.w1, self.b1)]
        y = _sigmoid(sum(w * v for w, v in zip(self.w2, h)) + self.b2)
        return h, y

    def predict(self, x: Sequence[float]) -> float:
        if len(x) != len(FEATURE_NAMES):
            raise ValueError("AEGIS_NEURAL_FEATURE_COUNT_MISMATCH")
        return self._forward(x)[1]

    def fit(self, samples: Iterable[tuple[Sequence[float], int]], *, epochs: int = 180, lr: float = .08) -> float:
        data = [(tuple(float(v) for v in x), int(y)) for x, y in samples]
        if len(data) < 8:
            raise ValueError("AEGIS_NEURAL_MINIMUM_TRAINING_SET_8")
        last_loss = 0.0
        for _ in range(epochs):
            total = 0.0
            for x, target in data:
                h, y = self._forward(x)
                y = max(1e-6, min(1 - 1e-6, y))
                total += -(target * math.log(y) + (1 - target) * math.log(1 - y))
                dy = y - target
                old_w2 = list(self.w2)
                for j in range(self.hidden):
                    self.w2[j] -= lr * dy * h[j]
                self.b2 -= lr * dy
                for j in range(self.hidden):
                    dh = dy * old_w2[j] * (1.0 - h[j] * h[j])
                    for i in range(len(x)):
                        self.w1[j][i] -= lr * dh * x[i]
                    self.b1[j] -= lr * dh
            last_loss = total / len(data)
        return last_loss

    def model_hash(self) -> str:
        body = {"w1": self.w1, "b1": self.b1, "w2": self.w2, "b2": self.b2, "features": FEATURE_NAMES}
        raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @classmethod
    def train_synthetic_shadow(cls, train: Sequence[tuple[Sequence[float], int]], holdout: Sequence[tuple[Sequence[float], int]]) -> tuple["NeuralSentinel", NeuralSentinelReceipt]:
        model = cls()
        loss = model.fit(train)
        correct = 0
        for x, target in holdout:
            pred = 1 if model.predict(x) >= .5 else 0
            correct += pred == target
        accuracy = correct / len(holdout) if holdout else 0.0
        receipt = NeuralSentinelReceipt(
            schema=cls.SCHEMA,
            shadow_only=True,
            synthetic_training_only=True,
            training_samples=len(train),
            holdout_samples=len(holdout),
            holdout_accuracy=round(accuracy, 6),
            training_loss=round(loss, 6),
            model_sha256=model.model_hash(),
        )
        return model, receipt
