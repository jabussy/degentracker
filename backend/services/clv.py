from typing import Optional


def power_devig(odds: list[float], tol: float = 1e-10, max_iter: int = 200) -> list[float]:
    """
    Remove vigorish from a set of decimal odds using Clarke's (2007) power method.

    Each implied probability is raised to a common exponent ``e`` (the paper's 1/k),
    chosen so the adjusted probabilities sum to exactly 1:

        fair_i = (1 / odds_i) ** e ,   solve for  sum(fair_i) == 1

    Unlike normalisation (a constant proportional cut) or equal-distribution (a
    constant absolute cut), the power method takes proportionally more margin out of
    longshots than favourites — matching how prices are actually set — and never
    yields negative probabilities. Returns fair probabilities in input order.

    The analytic seed k = log(nR)/log(n) from the paper is exact only when all
    outcomes are equally likely, so we solve for e numerically instead. s(e) =
    Σ (1/odds_i)**e is continuous and strictly decreasing in e (every term < 1),
    running from n down to 0, so a unique root for s(e) == 1 always exists.
    """
    if len(odds) < 2:
        return [1.0 / o for o in odds]

    implied = [1.0 / o for o in odds]
    if abs(sum(implied) - 1.0) < tol:
        return implied

    lo, hi = 1e-9, 1000.0
    e = 1.0
    for _ in range(max_iter):
        e = (lo + hi) / 2
        s = sum(p ** e for p in implied)
        if abs(s - 1.0) < tol:
            break
        if s > 1.0:
            lo = e  # sum too high → need a larger exponent to shrink it
        else:
            hi = e
    return [p ** e for p in implied]


def calc_odds_clv(
    odds_taken: float,
    betfair_lay_close: float,
    other_lays: Optional[list[float]] = None,
) -> float:
    """
    Betfair LAY price ≈ fair price (exchange has small margin).

    When the other runners' LAY prices are supplied, the market is power-devigged
    (Clarke 2007) so the reference is a true fair probability that sums to 1 across
    all outcomes. Without them, falls back to the raw 1/lay implied probability.

    your_implied = 1 / odds_taken
    CLV% = (fair_prob - your_implied) / your_implied
    Positive = you got better than fair = value.
    """
    if other_lays:
        fair_prob = power_devig([betfair_lay_close, *other_lays])[0]
    else:
        fair_prob = 1 / betfair_lay_close
    your_implied = 1 / odds_taken
    return (fair_prob - your_implied) / your_implied


def calc_line_clv(line_taken: float, line_at_close: float, side: str) -> float:
    """
    Points of line value captured. Positive always = you got the better number.

    OVER / HOME bets: higher line = worse for you
        line_clv = line_at_close - line_taken
        e.g. took o160.5, closed o168.5 → +8.0 pts ✓
        e.g. took o168.5, closed o160.5 → -8.0 pts ✗

    UNDER / AWAY bets: lower line = worse for you
        line_clv = line_taken - line_at_close
        e.g. took u168.5, closed u160.5 → +8.0 pts ✓
    """
    if side in ("over", "home"):
        return line_at_close - line_taken
    else:
        return line_taken - line_at_close
