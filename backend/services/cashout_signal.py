def cashout_signal(
    odds_taken: float,
    betfair_lay_at_bet: float,
    current_betfair_lay: float,
    threshold: float = 0.03,
) -> dict:
    """
    Measures edge erosion since bet was placed.
    original_edge = fair_prob_at_bet - your_implied
    current_edge  = current_fair_prob - your_implied
    If current_edge < -threshold: recommend cashout
    """
    your_implied = 1 / odds_taken
    original_edge = (1 / betfair_lay_at_bet) - your_implied
    current_edge = (1 / current_betfair_lay) - your_implied

    if current_edge > 0:
        severity = "clear"
    elif current_edge > -threshold:
        severity = "watch"
    else:
        severity = "cashout"

    return {
        "recommend_cashout": severity == "cashout",
        "severity": severity,
        "original_edge_pct": round(original_edge * 100, 2),
        "current_edge_pct": round(current_edge * 100, 2),
        "current_betfair_lay": current_betfair_lay,
    }
