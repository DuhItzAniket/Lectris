"""The paired bootstrap over pages (experiment protocol §4).

``bootstrap(units, statistic)`` resamples the units (pages) with replacement, ``resamples``
times, computes ``statistic`` on each resample, and returns the statistic on the full sample with
the percentile interval at ``level``. Pairing comes from the units: a unit that holds both
systems' scores for one page keeps them together, so a difference is resampled as a difference.
The generator is ``random.Random(seed)``, so the interval is the same on every run.
"""

import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Interval:
    """An estimate and its bootstrap percentile interval."""

    estimate: float
    low: float
    high: float

    @property
    def excludes_zero(self) -> bool:
        """Whether the whole interval lies on one side of zero: a "better" or "worse"."""
        return self.low > 0 or self.high < 0


def bootstrap[T](
    units: Sequence[T],
    statistic: Callable[[Sequence[T]], float],
    *,
    resamples: int = 1000,
    seed: int = 1337,
    level: float = 0.95,
) -> Interval:
    """The statistic on ``units`` and its percentile interval over ``resamples`` resamples."""
    if not units:
        raise ValueError("the bootstrap needs at least one unit")
    if resamples < 1:
        raise ValueError(f"resamples is at least 1, not {resamples}")
    if not 0 < level < 1:
        raise ValueError(f"the level is in (0, 1), not {level!r}")
    generator = random.Random(seed)  # noqa: S311 - resampling, not secrets
    values = sorted(statistic(generator.choices(units, k=len(units))) for _ in range(resamples))
    tail = (1 - level) / 2
    return Interval(
        statistic(units),
        values[max(0, math.floor(tail * resamples))],
        values[min(resamples - 1, math.ceil((1 - tail) * resamples) - 1)],
    )


def ratio(numerators: Sequence[float], denominators: Sequence[float]) -> float:
    """``sum(numerators) / sum(denominators)``, 0.0 when the denominator is 0: a micro-average."""
    total = sum(denominators)
    return sum(numerators) / total if total else 0.0
