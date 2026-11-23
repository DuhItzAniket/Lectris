"""The acceptance model: the probability that a candidate edit is right (architecture §11.1).

``Acceptance.fit(examples)`` fits a logistic regression, p = sigmoid(w . x + b), on candidates
labelled 1 when the edit fixes its block (``lectris.eval.scoring.label_candidates``) and 0
otherwise. ``x`` is the candidate's features, each standardised by its mean and spread on the
training examples (a feature missing from a candidate is 0 before standardising); ``w`` has an L2
penalty, ``b`` none. It is fitted by Newton's method (iteratively reweighted least squares) until
the largest change in a weight is below ``tolerance``, all in plain Python, so the same examples
give the same weights.

``calibration(probabilities, labels)`` measures how far probabilities are from frequencies: the
expected calibration error over equal-mass bins, and the reliability table.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from lectris.edits import Candidate


@dataclass(frozen=True)
class Acceptance:
    """A fitted acceptance model."""

    names: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    weights: tuple[float, ...]
    bias: float

    @classmethod
    def fit(
        cls,
        examples: Sequence[tuple[Mapping[str, float], int]],
        *,
        l2: float = 1.0,
        tolerance: float = 1e-6,
        max_iterations: int = 50,
    ) -> "Acceptance":
        """The model of ``(features, label)`` examples, labels 0 or 1."""
        if not examples:
            raise ValueError("the acceptance model needs examples")
        labels = [label for _, label in examples]
        if set(labels) - {0, 1}:
            raise ValueError("labels are 0 or 1")
        names = tuple(sorted({name for features, _ in examples for name in features}))
        raw = [[features.get(name, 0.0) for name in names] for features, _ in examples]
        means = [sum(row[j] for row in raw) / len(raw) for j in range(len(names))]
        scales = []
        for j, mean in enumerate(means):
            spread = math.sqrt(sum((row[j] - mean) ** 2 for row in raw) / len(raw))
            scales.append(spread if spread > 0 else 1.0)
        rows = [[(row[j] - means[j]) / scales[j] for j in range(len(names))] + [1.0] for row in raw]
        size = len(names) + 1
        theta = [0.0] * size
        for _ in range(max_iterations):
            gradient = [0.0] * size
            hessian = [[0.0] * size for _ in range(size)]
            for row, label in zip(rows, labels, strict=True):
                p = _sigmoid(sum(t * x for t, x in zip(theta, row, strict=True)))
                weight = p * (1 - p)
                error = p - label
                for i in range(size):
                    xi = row[i]
                    gradient[i] += error * xi
                    if xi:
                        line = hessian[i]
                        scaled = weight * xi
                        for k in range(i, size):
                            line[k] += scaled * row[k]
            for i in range(size):
                for k in range(i):
                    hessian[i][k] = hessian[k][i]
            for i in range(size - 1):  # the penalty spares the bias
                gradient[i] += l2 * theta[i]
                hessian[i][i] += l2
            step = _solve(hessian, gradient)
            theta = [t - s for t, s in zip(theta, step, strict=True)]
            if max(abs(s) for s in step) < tolerance:
                break
        return cls(names, tuple(means), tuple(scales), tuple(theta[:-1]), theta[-1])

    def logit(self, features: Mapping[str, float]) -> float:
        """w . x + b for a candidate's features."""
        total = self.bias
        for name, mean, scale, weight in zip(
            self.names, self.means, self.scales, self.weights, strict=True
        ):
            total += weight * (features.get(name, 0.0) - mean) / scale
        return total

    def probability(self, candidate: Candidate) -> float:
        """The probability that ``candidate`` is right."""
        return _sigmoid(self.logit(dict(candidate.features)))

    def to_data(self) -> dict[str, Any]:
        return {
            "names": list(self.names),
            "means": list(self.means),
            "scales": list(self.scales),
            "weights": list(self.weights),
            "bias": self.bias,
        }

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> "Acceptance":
        return cls(
            tuple(str(n) for n in data["names"]),
            tuple(float(v) for v in data["means"]),
            tuple(float(v) for v in data["scales"]),
            tuple(float(v) for v in data["weights"]),
            float(data["bias"]),
        )


@dataclass(frozen=True, slots=True)
class Calibration:
    """The expected calibration error, and each bin's mean probability, frequency and size."""

    ece: float
    bins: tuple[tuple[float, float, int], ...]
    brier: float


def calibration(
    probabilities: Sequence[float], labels: Sequence[int], *, bins: int = 15
) -> Calibration:
    """ECE over ``bins`` equal-mass bins (by sorted probability), and the Brier score."""
    if len(probabilities) != len(labels) or not probabilities:
        raise ValueError("calibration needs as many labels as probabilities, at least one")
    pairs = sorted(zip(probabilities, labels, strict=True))
    size = len(pairs)
    table = []
    ece = 0.0
    for b in range(bins):
        part = pairs[b * size // bins : (b + 1) * size // bins]
        if not part:
            continue
        mean = sum(p for p, _ in part) / len(part)
        frequency = sum(y for _, y in part) / len(part)
        table.append((mean, frequency, len(part)))
        ece += len(part) / size * abs(mean - frequency)
    brier = sum((p - y) ** 2 for p, y in pairs) / size
    return Calibration(ece, tuple(table), brier)


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    z = math.exp(value)
    return z / (1.0 + z)


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """The solution of ``matrix @ x = vector``, by Gaussian elimination with partial pivoting."""
    size = len(vector)
    a = [[*row, vector[i]] for i, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda r: abs(a[r][column]))
        if abs(a[pivot][column]) < 1e-12:  # noqa: PLR2004 - a singular direction: no step
            continue
        a[column], a[pivot] = a[pivot], a[column]
        for r in range(size):
            if r != column and a[r][column]:
                factor = a[r][column] / a[column][column]
                row, base = a[r], a[column]
                for k in range(column, size + 1):
                    row[k] -= factor * base[k]
    return [
        a[i][size] / a[i][i] if abs(a[i][i]) >= 1e-12 else 0.0  # noqa: PLR2004
        for i in range(size)
    ]
