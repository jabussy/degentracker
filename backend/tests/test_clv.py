from backend.services.clv import calc_odds_clv, calc_line_clv


# ---------------------------------------------------------------------------
# calc_odds_clv
# ---------------------------------------------------------------------------

def test_odds_clv_positive():
    """Bet at 2.00 when Betfair close was 1.90 — you beat the market."""
    result = calc_odds_clv(2.00, 1.90)
    # fair_prob = 1/1.90 ≈ 0.5263, your_implied = 1/2.00 = 0.5000
    # CLV = (0.5263 - 0.5000) / 0.5000 ≈ +0.0526
    assert abs(result - 0.0526) < 0.01, f"Expected ~+0.052, got {result:.4f}"
    assert result > 0


def test_odds_clv_negative():
    """Bet at 1.80 when Betfair close was 1.90 — you got worse than the market."""
    result = calc_odds_clv(1.80, 1.90)
    # fair_prob = 1/1.90 ≈ 0.5263, your_implied = 1/1.80 ≈ 0.5556
    # CLV = (0.5263 - 0.5556) / 0.5556 ≈ -0.0527
    assert abs(result - (-0.0527)) < 0.01, f"Expected ~-0.054, got {result:.4f}"
    assert result < 0


def test_odds_clv_breakeven():
    """Same odds as Betfair close — CLV is zero."""
    result = calc_odds_clv(2.00, 2.00)
    assert result == 0.0


# ---------------------------------------------------------------------------
# calc_line_clv
# ---------------------------------------------------------------------------

def test_line_clv_over_positive():
    """Took o160.5, market closed o168.5 — you locked in +8.0 pts of value."""
    assert calc_line_clv(160.5, 168.5, "over") == 8.0


def test_line_clv_over_negative():
    """Took o168.5, market closed o160.5 — line moved against you, -8.0 pts."""
    assert calc_line_clv(168.5, 160.5, "over") == -8.0


def test_line_clv_under_positive():
    """Took u168.5, market closed u160.5 — you locked in the high number, +8.0 pts."""
    assert calc_line_clv(168.5, 160.5, "under") == 8.0


def test_line_clv_under_negative():
    """Took u160.5, market closed u168.5 — line moved against you, -8.0 pts."""
    assert calc_line_clv(160.5, 168.5, "under") == -8.0


def test_line_clv_home_positive():
    """Home spread bet — same logic as 'over'."""
    assert calc_line_clv(3.5, 7.5, "home") == 4.0


def test_line_clv_away_positive():
    """Away spread bet — same logic as 'under'."""
    assert calc_line_clv(7.5, 3.5, "away") == 4.0
