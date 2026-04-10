from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.db import queries
from backend.services import odds_client, betfair_client

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
async def list_events(
    sport: str = Query(None),
    days: int = Query(3),
    db: AsyncSession = Depends(get_db),
):
    """Fetch events from Odds API, upsert to DB, return full list."""
    from backend.config import settings
    sports = [sport] if sport else settings.SPORTS

    for sport_key in sports:
        events = await odds_client.get_events(sport_key, days)
        for event_data in events:
            await queries.upsert_event(db, event_data)

    db_events = await queries.get_events(db, sport_key=sport, days=days)
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


@router.get("/{event_id}/lines")
async def get_event_lines(event_id: str, db: AsyncSession = Depends(get_db)):
    """Return current bookmaker lines for an event."""
    bookmakers = await odds_client.get_odds(event_id)
    snapshots = odds_client.parse_bookmaker_lines(bookmakers)

    for snap in snapshots:
        await queries.insert_odds_snapshot(db, {**snap, "event_id": event_id})

    event = await queries.get_event(db, event_id)
    return {
        "event_id": event_id,
        "event_name": f"{event.home_team} vs {event.away_team}" if event else None,
        "lines": snapshots,
        "bookmakers": bookmakers,
    }


@router.get("/{event_id}/betfair")
async def get_event_betfair(event_id: str, db: AsyncSession = Depends(get_db)):
    """Return current Betfair LAY snapshot for an event."""
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
