import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db import queries
from backend.db.session import get_db, AsyncSessionLocal
from backend.services import bet365_scraper, betfair_scraper, odds_client
from backend.services.ev import BETFAIR_API_KEY, build_ev_opportunities
from backend.services.team_match import match_event, same_team

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ev", tags=["ev"])


async def _persist_snapshots(snapshot_rows: list[dict]) -> None:
    """Background task: bulk-write odds snapshots gathered during an EV scan."""
    try:
        async with AsyncSessionLocal() as db:
            await queries.insert_odds_snapshots_bulk(db, snapshot_rows)
    except Exception as exc:
        logger.error("_persist_snapshots: %s", exc)


# odds_snapshots market_type -> Odds API market key
_SNAPSHOT_MARKET_KEYS = {"h2h": "h2h", "handicap": "spreads", "totals": "totals"}


async def _bet365_synthetic_bookmaker(
    db: AsyncSession, event_id: str, now: datetime
) -> Optional[dict]:
    """Fresh scraped bet365 snapshots as an Odds API-shaped bookmaker entry."""
    since = now - timedelta(minutes=settings.SCRAPED_SNAPSHOT_MAX_AGE_MINUTES)
    snaps = await queries.get_fresh_odds_snapshots(db, event_id, "bet365", since)
    if not snaps:
        return None

    markets: dict[str, list[dict]] = {}
    for s in snaps:
        mkey = _SNAPSHOT_MARKET_KEYS.get(s.market_type)
        if mkey is None:
            continue
        markets.setdefault(mkey, []).append(
            {"name": s.selection, "price": s.odds, "point": s.line}
        )
    if not markets:
        return None
    return {
        "key": "bet365",
        "title": "Bet365 (scraped)",
        "markets": [{"key": k, "outcomes": v} for k, v in markets.items()],
    }


async def _betfair_scraped_bookmaker(
    db: AsyncSession, event_id: str, now: datetime
) -> Optional[dict]:
    """
    Fresh scraped Betfair BACK/LAY snapshots as an Odds API-shaped bookmaker.
    Scraped straight off the exchange coupon, these are the true best prices —
    they replace The Odds API's betfair_ex_au entry, which relays junk ladder
    orders on thin markets.
    """
    since = now - timedelta(minutes=settings.SCRAPED_SNAPSHOT_MAX_AGE_MINUTES)
    markets = []
    for side, mkey in (("BACK", "h2h"), ("LAY", "h2h_lay")):
        snaps = await queries.get_latest_betfair_snapshots_for_event(db, event_id, side=side)
        outcomes = [
            {"name": s.selection_name, "price": s.price}
            for s in snaps
            if s.snapshot_time and s.snapshot_time >= since and s.market_type == "h2h"
        ]
        if outcomes:
            markets.append({"key": mkey, "outcomes": outcomes})
    if not markets:
        return None
    return {"key": BETFAIR_API_KEY, "title": "Betfair (scraped)", "markets": markets}


@router.get("")
async def find_ev(
    background_tasks: BackgroundTasks,
    sport: Optional[str] = Query(None),
    days: int = Query(3),
    min_ev: Optional[float] = Query(None, description="Minimum EV%% filter"),
    db: AsyncSession = Depends(get_db),
):
    """
    Scan upcoming events for +EV bets vs the Betfair fair line.

    One bulk Odds API request per sport (all events, all tracked bookmakers,
    Betfair LAY included via h2h_lay) — far cheaper than per-event calls.
    """
    sports = [sport] if sport else settings.SPORTS
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now + timedelta(days=days)

    opportunities: list[dict] = []
    snapshot_rows: list[dict] = []

    for sport_key in sports:
        try:
            raw_events = await odds_client.get_sport_odds(sport_key)
        except Exception as exc:
            logger.error("find_ev: error fetching sport %s: %s", sport_key, exc)
            continue

        for ev_data in raw_events:
            try:
                commence = datetime.fromisoformat(
                    ev_data["commence_time"].replace("Z", "+00:00")
                ).replace(tzinfo=None)
            except (KeyError, ValueError):
                continue
            if commence < now or commence > cutoff:
                continue

            event_info = {
                "id": ev_data["id"],
                "sport_key": ev_data.get("sport_key", sport_key),
                "sport_title": ev_data.get("sport_title", sport_key),
                "commence_time": commence,
                "home_team": ev_data.get("home_team"),
                "away_team": ev_data.get("away_team"),
                "status": "scheduled",
                "last_updated": now,
            }
            try:
                await queries.upsert_event(db, event_info)
            except Exception as exc:
                logger.error("find_ev: upsert_event %s: %s", ev_data["id"], exc)

            snaps = odds_client.parse_bookmaker_lines(ev_data.get("bookmakers", []))
            snapshot_rows.extend({**s, "event_id": ev_data["id"]} for s in snaps)

            # Prefer coupon-scraped Betfair prices over The Odds API's relay
            # of the same book — the scrape reads the true best back/lay.
            bf_scraped = await _betfair_scraped_bookmaker(db, ev_data["id"], now)
            if bf_scraped:
                others = [
                    b
                    for b in ev_data.get("bookmakers", [])
                    if b.get("key") != BETFAIR_API_KEY
                ]
                ev_data = {**ev_data, "bookmakers": [*others, bf_scraped]}

            # Merge in scraped bet365 prices (if a recent scrape exists) so
            # they're scored against the same Betfair fair line.
            bet365_bm = await _bet365_synthetic_bookmaker(db, ev_data["id"], now)
            if bet365_bm:
                ev_data = {
                    **ev_data,
                    "bookmakers": [*ev_data.get("bookmakers", []), bet365_bm],
                }

            event_name = f"{event_info['home_team']} vs {event_info['away_team']}"
            for row in build_ev_opportunities(ev_data):
                opportunities.append(
                    {
                        "event_id": ev_data["id"],
                        "event_name": event_name,
                        "sport_key": event_info["sport_key"],
                        "sport_title": event_info["sport_title"],
                        "commence_time": commence.isoformat(),
                        **row,
                    }
                )

    if snapshot_rows:
        background_tasks.add_task(_persist_snapshots, snapshot_rows)

    if min_ev is not None:
        opportunities = [
            o for o in opportunities if o["ev_pct"] is not None and o["ev_pct"] >= min_ev
        ]

    # Best EV first; rows without a Betfair reference sink to the bottom
    opportunities.sort(
        key=lambda o: o["ev_pct"] if o["ev_pct"] is not None else float("-inf"),
        reverse=True,
    )

    return {
        "generated_at": now.isoformat(),
        "count": len(opportunities),
        "opportunities": opportunities,
    }


@router.post("/bet365")
async def scrape_bet365(db: AsyncSession = Depends(get_db)):
    """
    Scrape bet365 AU coupons (AFL/NRL), match fixtures to tracked events by
    team name, and store H2H prices as bet365 odds snapshots. The next EV
    scan then scores them against the Betfair fair line.
    """
    if not settings.BET365_SCRAPE_ENABLED:
        raise HTTPException(status_code=400, detail="bet365 scraping is disabled")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    fixtures_by_sport: dict[str, int] = {}
    unmatched: list[str] = []
    snapshot_rows: list[dict] = []

    scraped = await bet365_scraper.scrape_sports(list(settings.SPORTS))
    for sport_key, fixtures in scraped.items():
        fixtures_by_sport[sport_key] = len(fixtures)
        if not fixtures:
            continue

        events = await queries.get_events(db, sport_key=sport_key, days=7)
        for fx in fixtures:
            event = bet365_scraper.match_event(fx["team_a"], fx["team_b"], events)
            if event is None:
                unmatched.append(f"{fx['team_a']} v {fx['team_b']}")
                continue
            # Coupon order isn't guaranteed home-first — resolve by name
            if bet365_scraper.same_team(fx["team_a"], event.home_team):
                pairs = ((event.home_team, fx["odds_a"]), (event.away_team, fx["odds_b"]))
            else:
                pairs = ((event.home_team, fx["odds_b"]), (event.away_team, fx["odds_a"]))
            for selection, odds in pairs:
                snapshot_rows.append(
                    {
                        "event_id": event.id,
                        "bookmaker": "bet365",
                        "market_type": "h2h",
                        "selection": selection,
                        "odds": odds,
                        "line": None,
                        "snapshot_time": now,
                    }
                )

    if snapshot_rows:
        await queries.insert_odds_snapshots_bulk(db, snapshot_rows)

    return {
        "scraped_at": now.isoformat(),
        "fixtures": fixtures_by_sport,
        "snapshots": len(snapshot_rows),
        "unmatched": unmatched,
    }


@router.post("/betfair")
async def scrape_betfair(db: AsyncSession = Depends(get_db)):
    """
    Scrape the Betfair Exchange coupons (AFL/NRL) for true best BACK/LAY
    prices with sizes, matched to tracked events and stored as
    betfair_snapshots. The next EV scan uses these as the fair-line source
    in place of The Odds API's betfair_ex_au relay.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    fixtures_by_sport: dict[str, int] = {}
    unmatched: list[str] = []
    rows: list[dict] = []

    scraped = await betfair_scraper.scrape_sports(list(settings.SPORTS))
    for sport_key, fixtures in scraped.items():
        fixtures_by_sport[sport_key] = len(fixtures)
        if not fixtures:
            continue

        events = await queries.get_events(db, sport_key=sport_key, days=7)
        for fx in fixtures:
            event = match_event(fx["team_a"], fx["team_b"], events)
            if event is None:
                unmatched.append(f"{fx['team_a']} v {fx['team_b']}")
                continue
            if same_team(fx["team_a"], event.home_team):
                oriented = (
                    (event.home_team, fx["back_a"], fx["lay_a"]),
                    (event.away_team, fx["back_b"], fx["lay_b"]),
                )
            else:
                oriented = (
                    (event.home_team, fx["back_b"], fx["lay_b"]),
                    (event.away_team, fx["back_a"], fx["lay_a"]),
                )
            for selection, back, lay in oriented:
                for side, cell in (("BACK", back), ("LAY", lay)):
                    if cell is None:
                        continue
                    rows.append(
                        {
                            "event_id": event.id,
                            "market_id": "scraped",
                            "selection_id": None,
                            "selection_name": selection,
                            "market_type": "h2h",
                            "side": side,
                            "price": cell["price"],
                            "size_available": cell["size"],
                            "snapshot_time": now,
                        }
                    )

    if rows:
        await queries.insert_betfair_snapshots_bulk(db, rows)

    return {
        "scraped_at": now.isoformat(),
        "fixtures": fixtures_by_sport,
        "snapshots": len(rows),
        "unmatched": unmatched,
    }
