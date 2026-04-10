import logging
from typing import Optional

logger = logging.getLogger(__name__)


def resolve_h2h(
    selection: str,
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
) -> str:
    if home_score == away_score:
        return "void"
    winner = home_team if home_score > away_score else away_team
    return "won" if selection == winner else "lost"


def resolve_totals(side: str, line: float, home_score: int, away_score: int) -> str:
    total = home_score + away_score
    if total == line:
        return "void"
    if side == "over":
        return "won" if total > line else "lost"
    else:
        return "won" if total < line else "lost"


def resolve_handicap(side: str, line: float, home_score: int, away_score: int) -> str:
    """line is from home team's perspective (e.g. home -3.5)."""
    margin = home_score - away_score
    if side == "home":
        adjusted = margin + line
    else:
        adjusted = -margin - line

    if adjusted == 0:
        return "void"
    return "won" if adjusted > 0 else "lost"


def attempt_auto_result(bet, scores_data: dict) -> Optional[str]:
    """
    Returns "won"|"lost"|"void"|"needs_manual" or None if can't resolve.
    Never calls if settle_source="manual" already set.
    """
    if bet.settle_source == "manual":
        logger.warning("Skipping auto-result for bet %d — already manually settled", bet.id)
        return None

    event_scores = scores_data.get(bet.event_id)
    if not event_scores:
        return None

    home_score = event_scores.get("home_score")
    away_score = event_scores.get("away_score")
    home_team = event_scores.get("home_team")
    away_team = event_scores.get("away_team")

    if home_score is None or away_score is None:
        return None

    try:
        if bet.market_type == "h2h":
            return resolve_h2h(bet.selection, home_team, away_team, home_score, away_score)
        elif bet.market_type == "totals":
            if bet.line is None:
                return None
            return resolve_totals(bet.side, bet.line, home_score, away_score)
        elif bet.market_type == "handicap":
            if bet.line is None:
                return None
            return resolve_handicap(bet.side, bet.line, home_score, away_score)
        else:
            return None
    except Exception as exc:
        logger.error("Error auto-resulting bet %d: %s", bet.id, exc)
        return None
