import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db, AsyncSessionLocal
from backend.db import queries
from backend.services import odds_client, betfair_client
from backend.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/events", tags=["events"])


async def _snapshot_odds_for_events(events_info: list[dict]) -> None:
    """Background task: snapshot current odds for a list of events."""
    async with AsyncSessionLocal() as db:
        for ev in events_info:
            try:
                bookmakers = await odds_client.get_odds(ev["id"], ev["sport_key"])
                snapshots = odds_client.parse_bookmaker_lines(bookmakers)
                for snap in snapshots:
                    await queries.insert_odds_snapshot(db, {**snap, "event_id": ev["id"]})
            except Exception as exc:
                logger.error(
                    "_snapshot_odds_for_events: error for event %s: %s", ev["id"], exc
                )


@router.get("")
async def list_events(
    sport: str = Query(None),
    days: int = Query(3),
    background_tasks: BackgroundTasks = ...,
    db: AsyncSession = Depends(get_db),
):
    """Fetch events from Odds API, upsert to DB, return full list."""
    sports = [sport] if sport else settings.SPORTS

    for sport_key in sports:
        try:
            events = await odds_client.get_events(sport_key, days)
            for event_data in events:
                await queries.upsert_event(db, event_data)
        except Exception as exc:
            logger.error("list_events: error fetching sport %s: %s", sport_key, exc)

    db_events = await queries.get_events(db, sport_key=sport, days=days)

    events_info = [{"id": e.id, "sport_key": e.sport_key} for e in db_events]
    background_tasks.add_task(_snapshot_odds_for_events, events_info)

    return [
        {
            "id": e.id,
            "sport_key": e.sport_key,
            "sport_title": e.sport_title,
            "commence_time": e.commence_time.isoformat() if e.commence_time else None,
            "home_team": e.home_team,
            "away_team": e.away_team,
            "status": e.status,
            "home_score": e.home_score,
            "away_score": e.away_score,
            "event_name": f"{e.home_team} vs {e.away_team}",
        }
        for e in db_events
    ]


def _parse_structured_lines(
    bookmakers: list[dict],
    home_team: str,
    away_team: str,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Parse raw Odds API bookmakers into h2h / spreads / totals lists."""
    h2h: list[dict] = []
    spreads: list[dict] = []
    totals: list[dict] = []

    for bm in bookmakers:
        bm_key = bm.get("key", "")
        bm_title = bm.get("title", bm_key)
        for market in bm.get("markets", []):
            mkey = market.get("key", "")
            outcomes = {o["name"]: o for o in market.get("outcomes", [])}

            if mkey == "h2h":
                home_out = outcomes.get(home_team, {})
                away_out = outcomes.get(away_team, {})
                if home_out or away_out:
                    h2h.append(
                        {
                            "bookmaker": bm_title,
                            "bookmaker_key": bm_key,
                            "home_odds": home_out.get("price"),
                            "away_odds": away_out.get("price"),
                            "home_team": home_team,
                            "away_team": away_team,
                        }
                    )

            elif mkey == "spreads":
                home_out = outcomes.get(home_team, {})
                away_out = outcomes.get(away_team, {})
                if home_out or away_out:
                    spreads.append(
                        {
                            "bookmaker": bm_title,
                            "bookmaker_key": bm_key,
                            "home_line": home_out.get("point"),
                            "home_odds": home_out.get("price"),
                            "away_line": away_out.get("point"),
                            "away_odds": away_out.get("price"),
                            "home_team": home_team,
                            "away_team": away_team,
                        }
                    )

            elif mkey == "totals":
                over_out = outcomes.get("Over", {})
                under_out = outcomes.get("Under", {})
                line = over_out.get("point") or under_out.get("point")
                if over_out or under_out:
                    totals.append(
                        {
                            "bookmaker": bm_title,
                            "bookmaker_key": bm_key,
                            "line": line,
                            "over_odds": over_out.get("price"),
                            "under_odds": under_out.get("price"),
                        }
                    )

    return (
        sorted(h2h, key=lambda x: x["bookmaker"]),
        sorted(spreads, key=lambda x: x["bookmaker"]),
        sorted(totals, key=lambda x: x["bookmaker"]),
    )


@router.get("/{event_id}/lines")
async def get_event_lines(event_id: str, db: AsyncSession = Depends(get_db)):
    """Return structured bookmaker lines for an event (h2h / spreads / totals)."""
    event = await queries.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    bookmakers = await odds_client.get_odds(event_id, event.sport_key)

    # Snapshot raw lines into odds_snapshots DB
    snapshots = odds_client.parse_bookmaker_lines(bookmakers)
    for snap in snapshots:
        await queries.insert_odds_snapshot(db, {**snap, "event_id": event_id})

    h2h, spreads, totals_data = _parse_structured_lines(
        bookmakers, event.home_team, event.away_team
    )

    # Betfair LAY from DB snapshots — best-effort name match
    bf_snaps = await queries.get_latest_betfair_snapshots_for_event(db, event_id, side="LAY")
    betfair_lay: dict | None = None
    if bf_snaps:
        betfair_lay = {}
        home_lower = event.home_team.lower()
        away_lower = event.away_team.lower()
        for snap in bf_snaps:
            name = snap.selection_name.lower()
            if home_lower in name or name in home_lower:
                betfair_lay["home"] = snap.price
            elif away_lower in name or name in away_lower:
                betfair_lay["away"] = snap.price
        if not betfair_lay:
            betfair_lay = None

    return {
        "event_id": event_id,
        "h2h": h2h,
        "spreads": spreads,
        "totals": totals_data,
        "betfair_lay": betfair_lay,
    }


@router.get("/{event_id}/betfair")
async def get_event_betfair(event_id: str, db: AsyncSession = Depends(get_db)):
    """Return current Betfair LAY snapshot for an event."""
    if not settings.BETFAIR_ENABLED:
        return {"event_id": event_id, "runners": []}

    snapshot = await betfair_client.get_market_snapshot(event_id)

    if snapshot:
        records = await betfair_client.build_betfair_snapshot_records(event_id, snapshot)
        for rec in records:
            await queries.insert_betfair_snapshot(db, rec)

    db_snaps = await queries.get_latest_betfair_snapshots_for_event(db, event_id, side="LAY")
    return {
        "event_id": event_id,
        "runners": [
            {
                "selection_name": s.selection_name,
                "lay_price": s.price,
                "size_available": s.size_available,
                "snapshot_time": s.snapshot_time.isoformat() if s.snapshot_time else None,
            }
            for s in db_snaps
        ],
    }
