import logging
from datetime import datetime, timezone
from typing import Optional
import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

ODDS_API_BASE = "https://api.the-odds-api.com/v4"


async def get_events(sport_key: str, days: int = 3) -> list[dict]:
    """Fetch upcoming events from The Odds API."""
    if not settings.ODDS_API_KEY:
        logger.warning("ODDS_API_KEY not set — returning empty events list")
        return []

    params = {"apiKey": settings.ODDS_API_KEY, "daysFrom": days}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{ODDS_API_BASE}/sports/{sport_key}/events", params=params
            )
            if resp.status_code == 429:
                logger.warning("Odds API quota exceeded (429) for events/%s", sport_key)
                return []
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "id": e["id"],
                    "sport_key": e["sport_key"],
                    "sport_title": e.get("sport_title", sport_key),
                    "commence_time": datetime.fromisoformat(
                        e["commence_time"].replace("Z", "+00:00")
                    ).replace(tzinfo=None),
                    "home_team": e["home_team"],
                    "away_team": e["away_team"],
                    "status": "scheduled",
                    "last_updated": datetime.now(timezone.utc).replace(tzinfo=None),
                }
                for e in data
            ]
    except Exception as exc:
        logger.error("Error fetching events for %s: %s", sport_key, exc)
        return []


async def get_odds(event_id: str, markets: Optional[list[str]] = None) -> list[dict]:
    """Fetch current bookmaker lines for a specific event."""
    if not settings.ODDS_API_KEY:
        logger.warning("ODDS_API_KEY not set — returning empty odds")
        return []

    if markets is None:
        markets = ["h2h", "spreads", "totals"]

    params = {
        "apiKey": settings.ODDS_API_KEY,
        "regions": "au",
        "markets": ",".join(markets),
        "oddsFormat": "decimal",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{ODDS_API_BASE}/sports/upcoming/events/{event_id}/odds", params=params
            )
            if resp.status_code == 429:
                logger.warning("Odds API quota exceeded (429) for event %s", event_id)
                return []
            resp.raise_for_status()
            return resp.json().get("bookmakers", [])
    except Exception as exc:
        logger.error("Error fetching odds for event %s: %s", event_id, exc)
        return []


async def get_scores(sport_key: str, days_from: int = 2) -> list[dict]:
    """Fetch completed scores from The Odds API."""
    if not settings.ODDS_API_KEY:
        logger.warning("ODDS_API_KEY not set — returning empty scores")
        return []

    params = {"apiKey": settings.ODDS_API_KEY, "daysFrom": days_from}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{ODDS_API_BASE}/sports/{sport_key}/scores", params=params
            )
            if resp.status_code == 429:
                logger.warning("Odds API quota exceeded (429) for scores/%s", sport_key)
                return []
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.error("Error fetching scores for %s: %s", sport_key, exc)
        return []


def parse_scores_to_dict(scores_data: list[dict]) -> dict:
    """Convert scores list to dict keyed by event_id."""
    result = {}
    for game in scores_data:
        if game.get("completed") and game.get("scores"):
            scores_by_team = {s["name"]: s["score"] for s in game["scores"]}
            home_team = game["home_team"]
            away_team = game["away_team"]
            try:
                result[game["id"]] = {
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_score": int(scores_by_team.get(home_team, 0)),
                    "away_score": int(scores_by_team.get(away_team, 0)),
                    "completed": True,
                }
            except (ValueError, KeyError):
                pass
    return result


def parse_bookmaker_lines(bookmakers: list[dict]) -> list[dict]:
    """Flatten bookmaker odds response into snapshot records."""
    snapshots = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    market_type_map = {"h2h": "h2h", "spreads": "handicap", "totals": "totals"}
    for bm in bookmakers:
        bm_key = bm["key"]
        for market in bm.get("markets", []):
            mtype = market_type_map.get(market["key"], market["key"])
            for outcome in market.get("outcomes", []):
                snapshots.append(
                    {
                        "bookmaker": bm_key,
                        "market_type": mtype,
                        "selection": outcome["name"],
                        "odds": outcome["price"],
                        "line": outcome.get("point"),
                        "snapshot_time": now,
                    }
                )
    return snapshots
