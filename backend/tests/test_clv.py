from backend.services.clv import calc_odds_clv, calc_line_clv, power_devig


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


# ---------------------------------------------------------------------------
# power_devig — Clarke (2007) power method, verified against the paper's examples
# ---------------------------------------------------------------------------

def test_power_devig_sums_to_one():
    fair = power_devig([1.90, 2.10])
    assert abs(sum(fair) - 1.0) < 1e-9


def test_power_devig_tennis_example():
    """Paper §4: prices $1.22 / $4.33 devig to fair $1.25 / $5.05."""
    fair = power_devig([1.22, 4.33])
    assert abs(sum(fair) - 1.0) < 1e-9
    assert abs(fair[0] - 0.802) < 0.005, f"expected ~0.802, got {fair[0]:.4f}"
    assert abs(fair[1] - 0.198) < 0.005, f"expected ~0.198, got {fair[1]:.4f}"
    # fair prices
    assert abs((1 / fair[0]) - 1.25) < 0.02
    assert abs((1 / fair[1]) - 5.05) < 0.05


def test_power_devig_six_runner_table4():
    """Paper Table 4: 6-runner race, 20%+ over-round, power column."""
    fair = power_devig([1.15, 5.00, 10.00, 20.00, 50.00, 100.00])
    expected = [0.825, 0.110, 0.042, 0.016, 0.005, 0.002]
    assert abs(sum(fair) - 1.0) < 1e-9
    for got, exp in zip(fair, expected):
        assert abs(got - exp) < 0.005, f"expected ~{exp}, got {got:.4f}"


def test_power_devig_longshot_bias_vs_normalisation():
    """Power method removes less margin from the favourite, more from the longshot."""
    odds = [1.22, 4.33]
    implied = [1 / o for o in odds]
    booksum = sum(implied)
    norm = [p / booksum for p in implied]  # simple normalisation
    fair = power_devig(odds)
    assert fair[0] > norm[0]  # favourite cut less
    assert fair[1] < norm[1]  # longshot cut more


def test_power_devig_never_negative():
    """Equal-distribution breaks down here; the power method must stay positive."""
    fair = power_devig([1.12, 5.00, 20.00, 30.00, 40.00])
    assert all(p > 0 for p in fair)
    assert abs(sum(fair) - 1.0) < 1e-9


def test_power_devig_already_fair_unchanged():
    fair = power_devig([2.0, 2.0])
    assert abs(fair[0] - 0.5) < 1e-9
    assert abs(fair[1] - 0.5) < 1e-9


# ---------------------------------------------------------------------------
# calc_odds_clv with devig
# ---------------------------------------------------------------------------

def test_odds_clv_devig_uses_fair_prob():
    """With the opposite LAY supplied, CLV references the devigged fair prob."""
    # LAY pair 1.90 / 2.10 → devigged fair prob for side 1 is below raw 1/1.90
    raw = calc_odds_clv(2.00, 1.90)
    devigged = calc_odds_clv(2.00, 1.90, [2.10])
    assert devigged < raw  # removing the LAY over-round lowers the fair prob


def test_odds_clv_no_opp_matches_legacy():
    """Without opposite LAY, behaviour is unchanged (raw 1/lay)."""
    assert calc_odds_clv(2.00, 1.90) == calc_odds_clv(2.00, 1.90, None)
