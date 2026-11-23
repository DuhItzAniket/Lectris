"""Risk control: the acceptance threshold that bounds the harm rate (ADR-0002; architecture §11.2).

A candidate is accepted when its probability of being right is at least ``lambda``. A page's loss
at ``lambda`` is the characters broken by the harmful candidates it would accept, divided by its
reference's length, at most 1; the risk R(lambda) is its mean over pages. ``learn_then_test``
chooses ``lambda`` on calibration pages so that, with probability at least ``1 - delta``,
R(lambda) <= ``alpha`` on new pages like them (Angelopoulos et al., Learn then Test):

- for each ``lambda`` on a grid from strict (high) to permissive (low), it tests the null
  hypothesis R(lambda) > alpha with the Hoeffding-Bentkus p-value of the mean loss;
- fixed-sequence testing at level ``delta``: it walks the grid in that order and stops at the
  first ``lambda`` whose null it cannot reject; the thresholds rejected before it are certified
  (``certified``), and ``learn_then_test`` gives the most permissive of them, or ``None`` if the
  first one already fails (then nothing is accepted). ADR-0009 chooses among the certified ones
  by usefulness instead.

Pages, not edits, are the units: losses on one page are not independent.
"""

import math
from collections.abc import Callable, Sequence


def hoeffding_bentkus(mean: float, n: int, alpha: float) -> float:
    """The Hoeffding-Bentkus p-value of the null "the risk is above ``alpha``", given the mean
    of ``n`` losses in [0, 1] (Bates et al., 2021)."""
    if not 0 < alpha < 1:
        raise ValueError(f"alpha is in (0, 1), not {alpha!r}")
    if n < 1:
        raise ValueError("the p-value needs at least one loss")
    if mean >= alpha:
        return 1.0
    hoeffding = math.exp(-n * _kl(mean, alpha))
    bentkus = math.e * _binomial_cdf(math.ceil(n * mean), n, alpha)
    return min(1.0, hoeffding, bentkus)


def certified(
    losses: Callable[[float], Sequence[float]],
    grid: Sequence[float],
    *,
    alpha: float,
    delta: float,
) -> tuple[float, ...]:
    """The thresholds on ``grid`` (ordered strict to permissive) certified by fixed-sequence
    testing: those before the first whose null it cannot reject. With probability at least
    ``1 - delta``, every one of them has risk at most ``alpha`` (family-wise), so any choice among
    them keeps the guarantee (ADR-0009). ``losses(lambda)`` gives each page's loss."""
    if not 0 < delta < 1:
        raise ValueError(f"delta is in (0, 1), not {delta!r}")
    found: list[float] = []
    for threshold in grid:
        page_losses = losses(threshold)
        if any(not 0 <= loss <= 1 for loss in page_losses):
            raise ValueError("losses are in [0, 1]")
        mean = sum(page_losses) / len(page_losses)
        if hoeffding_bentkus(mean, len(page_losses), alpha) > delta:
            break
        found.append(threshold)
    return tuple(found)


def learn_then_test(
    losses: Callable[[float], Sequence[float]],
    grid: Sequence[float],
    *,
    alpha: float,
    delta: float,
) -> float | None:
    """The most permissive certified threshold (``certified``), or ``None`` if none is."""
    found = certified(losses, grid, alpha=alpha, delta=delta)
    return found[-1] if found else None


def grid(steps: int = 100) -> tuple[float, ...]:
    """Thresholds from 1.0 down to 0.0 in ``steps`` equal steps: the order Learn-then-Test walks."""
    return tuple(round(1 - i / steps, 10) for i in range(steps + 1))


def _kl(a: float, b: float) -> float:
    """The Bernoulli Kullback-Leibler divergence of ``a`` from ``b``."""
    value = 0.0
    if a > 0:
        value += a * math.log(a / b)
    if a < 1:
        value += (1 - a) * math.log((1 - a) / (1 - b))
    return value


def _binomial_cdf(k: int, n: int, p: float) -> float:
    """P(Binomial(n, p) <= k), summed in log space."""
    if k >= n:
        return 1.0
    total = 0.0
    log_p, log_q = math.log(p), math.log(1 - p)
    for i in range(k + 1):
        total += math.exp(
            math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
            + i * log_p + (n - i) * log_q
        )  # fmt: skip
    return min(1.0, total)
