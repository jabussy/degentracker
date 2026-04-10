from backend.services.cashout_signal import cashout_signal


# ---------------------------------------------------------------------------
# cashout_signal severity levels
# ---------------------------------------------------------------------------

def test_cashout_severity_clear():
    """
    Bet at 2.10, Betfair LAY at bet=2.00, current LAY=1.85.
    Current LAY dropped (selection is now less likely) — edge has grown, clear signal.
    """
    result = cashout_signal(odds_taken=2.10, betfair_lay_at_bet=2.00, current_betfair_lay=1.85)
    # your_implied = 1/2.10 ≈ 0.4762
    # current_edge = 1/1.85 - 0.4762 ≈ 0.5405 - 0.4762 = +0.0643 > 0 → clear
    assert result["severity"] == "clear"
    assert result["recommend_cashout"] is False
    assert result["current_edge_pct"] > 0


def test_cashout_severity_watch():
    """
    Bet at 2.10, Betfair LAY at bet=2.00, current LAY=2.15.
    Small edge erosion — within threshold, 'watch'.
    """
    result = cashout_signal(odds_taken=2.10, betfair_lay_at_bet=2.00, current_betfair_lay=2.15)
    # current_edge = 1/2.15 - 0.4762 ≈ 0.4651 - 0.4762 = -0.0111
    # -0.03 < -0.0111 → watch
    assert result["severity"] == "watch"
    assert result["recommend_cashout"] is False
    assert -3.0 < result["current_edge_pct"] < 0


def test_cashout_severity_cashout():
    """
    Bet at 2.10, Betfair LAY at bet=2.00, current LAY=2.50.
    Edge has completely eroded — recommend cashout.
    """
    result = cashout_signal(odds_taken=2.10, betfair_lay_at_bet=2.00, current_betfair_lay=2.50)
    # current_edge = 1/2.50 - 0.4762 = 0.4000 - 0.4762 = -0.0762 < -0.03 → cashout
    assert result["severity"] == "cashout"
    assert result["recommend_cashout"] is True
    assert result["current_edge_pct"] < -3.0


def test_cashout_fields_present():
    """Response must always include all required fields."""
    result = cashout_signal(odds_taken=2.00, betfair_lay_at_bet=1.90, current_betfair_lay=2.10)
    assert "severity" in result
    assert "recommend_cashout" in result
    assert "original_edge_pct" in result
    assert "current_edge_pct" in result
    assert "current_betfair_lay" in result
    assert result["current_betfair_lay"] == 2.10


def test_cashout_original_edge_positive():
    """When you had a genuine edge at bet time, original_edge_pct should be positive."""
    result = cashout_signal(odds_taken=2.10, betfair_lay_at_bet=2.00, current_betfair_lay=2.00)
    assert result["original_edge_pct"] > 0


def test_cashout_custom_threshold():
    """Severity boundary respects the threshold parameter."""
    # current_edge ≈ -0.02, threshold=0.01 → cashout
    result = cashout_signal(
        odds_taken=2.10,
        betfair_lay_at_bet=2.00,
        current_betfair_lay=2.15,
        threshold=0.01,
    )
    assert result["severity"] == "cashout"
