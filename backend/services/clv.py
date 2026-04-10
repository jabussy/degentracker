def calc_odds_clv(odds_taken: float, betfair_lay_close: float) -> float:
    """
    Betfair LAY price ≈ fair price (exchange has small margin).
    fair_prob = 1 / betfair_lay_close
    your_implied = 1 / odds_taken
    CLV% = (fair_prob - your_implied) / your_implied
    Positive = you got better than fair = value.
    """
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
