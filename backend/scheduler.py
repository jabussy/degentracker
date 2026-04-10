import logging
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.db.session import AsyncSessionLocal
from backend.db import queries
from backend.services import odds_client, betfair_client
from backend.services.clv import calc_odds_clv, calc_line_clv
from backend.services.auto_result import attempt_auto_result
from backend.config import settings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def poll_upcoming_odds():
    """Snapshot Odds API lines for all events with open bets."""
    logger.info("poll_upcoming_odds: starting")
    async with AsyncSessionLocal() as db:
        open_bets = await queries.get_open_bets(db)
        # Map event_id → sport_key (last-writer-wins if multiple bets per event)
        event_sport: dict[str, str] = {b.event_id: b.sport_key for b in open_bets}
        for event_id, sport_key in event_sport.items():
            try:
                bookmakers = await odds_client.get_odds(event_id, sport_key)
                snapshots = odds_client.parse_bookmaker_lines(bookmakers)
                for snap in snapshots:
                    await queries.insert_odds_snapshot(db, {**snap, "event_id": event_id})
            except Exception as exc:
                logger.error("poll_upcoming_odds: error for event %s: %s", event_id, exc)
    logger.info("poll_upcoming_odds: done, %d events", len(event_sport))


async def poll_betfair():
    """Snapshot Betfair LAY for open bet selections."""
    if not settings.BETFAIR_ENABLED:
        return
    async with AsyncSessionLocal() as db:
        open_bets = await queries.get_open_bets(db)
        event_ids = list({b.event_id for b in open_bets})
        for event_id in event_ids:
            try:
                snapshot = await betfair_client.get_market_snapshot(event_id)
                if snapshot:
                    records = await betfair_client.build_betfair_snapshot_records(event_id, snapshot)
                    for rec in records:
                        await queries.insert_betfair_snapshot(db, rec)
            except Exception as exc:
                logger.error("poll_betfair: error for event %s: %s", event_id, exc)


async def capture_closing_lines():
    """Fire at commence_time - CLOSING_LINE_WINDOW_MINUTES per open bet."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    window = timedelta(minutes=settings.CLOSING_LINE_WINDOW_MINUTES)

    async with AsyncSessionLocal() as db:
        open_bets = await queries.get_open_bets(db)
        for bet in open_bets:
            close_trigger = bet.commence_time - window
            if now < close_trigger:
                continue

            cl = bet.closing_line
            if cl and cl.betfair_lay_at_close is not None:
                continue

            logger.info("capture_closing_lines: capturing for bet %d", bet.id)
            try:
                betfair_lay_close = await betfair_client.get_lay_price(bet.event_id, bet.selection)

                line_at_close = None
                if bet.market_type in ("handicap", "totals"):
                    snap = await queries.get_odds_snapshot_at(
                        db,
                        event_id=bet.event_id,
                        bookmaker="consensus",
                        market_type=bet.market_type,
                        before_time=bet.commence_time,
                    )
                    if snap:
                        line_at_close = snap.line

                odds_clv_pct = None
                beat_closing_odds = None
                if betfair_lay_close:
                    odds_clv_pct = calc_odds_clv(bet.odds_taken, betfair_lay_close)
                    beat_closing_odds = odds_clv_pct > 0

                line_clv_pts = None
                beat_closing_line = None
                line_at_open = cl.line_at_open if cl else bet.line
                if (
                    bet.market_type in ("handicap", "totals")
                    and line_at_open is not None
                    and line_at_close is not None
                ):
                    line_clv_pts = calc_line_clv(line_at_open, line_at_close, bet.side)
                    beat_closing_line = line_clv_pts > 0

                await queries.upsert_closing_line(
                    db,
                    bet.id,
                    {
                        "betfair_lay_at_bet": cl.betfair_lay_at_bet if cl else None,
                        "betfair_lay_at_close": betfair_lay_close,
                        "odds_clv_pct": odds_clv_pct,
                        "beat_closing_odds": beat_closing_odds,
                        "line_at_open": line_at_open,
                        "line_at_close": line_at_close,
                        "line_clv_pts": line_clv_pts,
                        "beat_closing_line": beat_closing_line,
                        "captured_at": now,
                        "capture_source": "scheduled",
                    },
                )
            except Exception as exc:
                logger.error("capture_closing_lines: error for bet %d: %s", bet.id, exc)


async def poll_scores():
    """Auto-result open bets that have passed their commence_time."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with AsyncSessionLocal() as db:
        open_bets = await queries.get_open_bets(db)
        eligible = [b for b in open_bets if b.commence_time <= now]
        if not eligible:
            return

        sport_keys = list({b.sport_key for b in eligible})
        all_scores: dict = {}
        for sport_key in sport_keys:
            try:
                raw_scores = await odds_client.get_scores(sport_key, days_from=3)
                parsed = odds_client.parse_scores_to_dict(raw_scores)
                all_scores.update(parsed)
                for game in raw_scores:
                    if game.get("completed") and game.get("scores"):
                        scores_by_team = {s["name"]: s["score"] for s in game["scores"]}
                        try:
                            await queries.update_event_scores(
                                db,
                                game["id"],
                                int(scores_by_team.get(game["home_team"], 0)),
                                int(scores_by_team.get(game["away_team"], 0)),
                                "completed",
                            )
                        except Exception:
                            pass
            except Exception as exc:
                logger.error("poll_scores: error for %s: %s", sport_key, exc)

        for bet in eligible:
            if bet.settle_source == "manual":
                continue
            result = attempt_auto_result(bet, all_scores)
            if result and result != "needs_manual":
                logger.info("poll_scores: auto-resulting bet %d as %s", bet.id, result)
                await queries.update_bet_status(db, bet.id, result, "auto_scores")


async def recover_missed_closes():
    """Re-attempt closing line capture for any missed bets."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with AsyncSessionLocal() as db:
        open_bets = await queries.get_open_bets(db)
        missed = [
            b for b in open_bets
            if b.commence_time < now
            and (b.closing_line is None or b.closing_line.betfair_lay_at_close is None)
        ]
        for bet in missed:
            cl = bet.closing_line
            try:
                betfair_lay_close = await betfair_client.get_lay_price(bet.event_id, bet.selection)
                odds_clv_pct = None
                beat_closing_odds = None
                if betfair_lay_close:
                    odds_clv_pct = calc_odds_clv(bet.odds_taken, betfair_lay_close)
                    beat_closing_odds = odds_clv_pct > 0

                await queries.upsert_closing_line(
                    db,
                    bet.id,
                    {
                        "betfair_lay_at_bet": cl.betfair_lay_at_bet if cl else None,
                        "betfair_lay_at_close": betfair_lay_close,
                        "odds_clv_pct": odds_clv_pct,
                        "beat_closing_odds": beat_closing_odds,
                        "line_at_open": cl.line_at_open if cl else bet.line,
                        "line_at_close": cl.line_at_close if cl else None,
                        "line_clv_pts": cl.line_clv_pts if cl else None,
                        "beat_closing_line": cl.beat_closing_line if cl else None,
                        "captured_at": now,
                        "capture_source": "missed_recovery",
                    },
                )
            except Exception as exc:
                logger.error("recover_missed_closes: error for bet %d: %s", bet.id, exc)


def start_scheduler():
    scheduler.add_job(poll_upcoming_odds, "interval", minutes=5, id="poll_upcoming_odds")
    scheduler.add_job(poll_betfair, "interval", minutes=5, id="poll_betfair")
    scheduler.add_job(capture_closing_lines, "interval", minutes=1, id="capture_closing_lines")
    scheduler.add_job(poll_scores, "interval", minutes=10, id="poll_scores")
    scheduler.add_job(recover_missed_closes, "interval", hours=1, id="recover_missed_closes")
    scheduler.start()
    logger.info("Scheduler started with 5 jobs")
