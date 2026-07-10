from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from sqlalchemy import select, update, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models import (
    BetfairSnapshot,
    ClosingLine,
    Event,
    OddsSnapshot,
    TrackedBet,
)


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

async def get_events(
    db: AsyncSession,
    sport_key: Optional[str] = None,
    days: int = 3,
) -> list[Event]:
    # commence_time is stored as naive UTC (see odds_client.get_events)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now + timedelta(days=days)
    stmt = select(Event).where(
        Event.status != "deleted",
        Event.commence_time >= now,
        Event.commence_time <= cutoff,
    )
    if sport_key:
        stmt = stmt.where(Event.sport_key == sport_key)
    stmt = stmt.order_by(Event.commence_time)
    result = await db.execute(stmt)
    return result.scalars().all()


async def upsert_event(db: AsyncSession, event_data: dict) -> Event:
    stmt = select(Event).where(Event.id == event_data["id"])
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()

    if event is None:
        event = Event(**event_data)
        db.add(event)
    else:
        for k, v in event_data.items():
            setattr(event, k, v)

    await db.commit()
    await db.refresh(event)
    return event


async def get_event(db: AsyncSession, event_id: str) -> Optional[Event]:
    result = await db.execute(select(Event).where(Event.id == event_id))
    return result.scalar_one_or_none()


async def update_event_scores(
    db: AsyncSession,
    event_id: str,
    home_score: int,
    away_score: int,
    status: str,
) -> None:
    await db.execute(
        update(Event)
        .where(Event.id == event_id)
        .values(home_score=home_score, away_score=away_score, status=status)
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Bets
# ---------------------------------------------------------------------------

async def create_bet(db: AsyncSession, bet_data: dict) -> TrackedBet:
    bet = TrackedBet(**bet_data)
    db.add(bet)
    await db.commit()
    await db.refresh(bet)
    return bet


async def get_bet(db: AsyncSession, bet_id: int) -> Optional[TrackedBet]:
    result = await db.execute(
        select(TrackedBet)
        .options(selectinload(TrackedBet.closing_line), selectinload(TrackedBet.event))
        .where(TrackedBet.id == bet_id)
    )
    return result.scalar_one_or_none()


async def list_bets(
    db: AsyncSession,
    status: Optional[str] = None,
    sport: Optional[str] = None,
    bookmaker: Optional[str] = None,
    market_type: Optional[str] = None,
) -> list[TrackedBet]:
    stmt = (
        select(TrackedBet)
        .options(selectinload(TrackedBet.closing_line), selectinload(TrackedBet.event))
        .where(TrackedBet.status != "deleted")
    )
    if status:
        stmt = stmt.where(TrackedBet.status == status)
    if sport:
        stmt = stmt.where(TrackedBet.sport_key == sport)
    if bookmaker:
        stmt = stmt.where(TrackedBet.bookmaker == bookmaker)
    if market_type:
        stmt = stmt.where(TrackedBet.market_type == market_type)
    stmt = stmt.order_by(TrackedBet.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


async def update_bet_status(
    db: AsyncSession,
    bet_id: int,
    status: str,
    settle_source: str,
) -> None:
    await db.execute(
        update(TrackedBet)
        .where(TrackedBet.id == bet_id)
        .values(status=status, settle_source=settle_source, updated_at=datetime.now(timezone.utc))
    )
    await db.commit()


async def soft_delete_bet(db: AsyncSession, bet_id: int) -> None:
    await db.execute(
        update(TrackedBet)
        .where(TrackedBet.id == bet_id)
        .values(status="deleted", updated_at=datetime.now(timezone.utc))
    )
    await db.commit()


async def get_open_bets(db: AsyncSession) -> list[TrackedBet]:
    result = await db.execute(
        select(TrackedBet)
        .options(selectinload(TrackedBet.closing_line), selectinload(TrackedBet.event))
        .where(TrackedBet.status == "open")
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Closing Lines
# ---------------------------------------------------------------------------

async def upsert_closing_line(db: AsyncSession, bet_id: int, data: dict) -> ClosingLine:
    stmt = select(ClosingLine).where(ClosingLine.bet_id == bet_id)
    result = await db.execute(stmt)
    cl = result.scalar_one_or_none()

    if cl is None:
        cl = ClosingLine(bet_id=bet_id, **data)
        db.add(cl)
    else:
        for k, v in data.items():
            setattr(cl, k, v)

    await db.commit()
    await db.refresh(cl)
    return cl


async def get_closing_line(db: AsyncSession, bet_id: int) -> Optional[ClosingLine]:
    result = await db.execute(
        select(ClosingLine).where(ClosingLine.bet_id == bet_id)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Odds Snapshots
# ---------------------------------------------------------------------------

async def insert_odds_snapshot(db: AsyncSession, data: dict) -> OddsSnapshot:
    snap = OddsSnapshot(**data)
    db.add(snap)
    await db.commit()
    await db.refresh(snap)
    return snap


async def insert_odds_snapshots_bulk(db: AsyncSession, rows: list[dict]) -> None:
    """Insert many odds snapshots in a single commit (EV scans write hundreds)."""
    if not rows:
        return
    db.add_all([OddsSnapshot(**row) for row in rows])
    await db.commit()


async def get_fresh_odds_snapshots(
    db: AsyncSession,
    event_id: str,
    bookmaker: str,
    since: datetime,
) -> list[OddsSnapshot]:
    """Latest snapshot per (market, selection, line) for one bookmaker, no older than `since`."""
    subq = (
        select(
            OddsSnapshot.market_type,
            OddsSnapshot.selection,
            OddsSnapshot.line,
            func.max(OddsSnapshot.snapshot_time).label("max_time"),
        )
        .where(
            and_(
                OddsSnapshot.event_id == event_id,
                OddsSnapshot.bookmaker == bookmaker,
                OddsSnapshot.snapshot_time >= since,
            )
        )
        .group_by(OddsSnapshot.market_type, OddsSnapshot.selection, OddsSnapshot.line)
        .subquery()
    )
    stmt = select(OddsSnapshot).join(
        subq,
        and_(
            OddsSnapshot.market_type == subq.c.market_type,
            OddsSnapshot.selection == subq.c.selection,
            func.coalesce(OddsSnapshot.line, -999999.0) == func.coalesce(subq.c.line, -999999.0),
            OddsSnapshot.snapshot_time == subq.c.max_time,
            OddsSnapshot.event_id == event_id,
            OddsSnapshot.bookmaker == bookmaker,
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_odds_snapshot_at(
    db: AsyncSession,
    event_id: str,
    bookmaker: str,
    market_type: str,
    before_time: datetime,
) -> Optional[OddsSnapshot]:
    result = await db.execute(
        select(OddsSnapshot)
        .where(
            and_(
                OddsSnapshot.event_id == event_id,
                OddsSnapshot.bookmaker == bookmaker,
                OddsSnapshot.market_type == market_type,
                OddsSnapshot.snapshot_time <= before_time,
            )
        )
        .order_by(OddsSnapshot.snapshot_time.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_latest_odds_snapshots_for_event(
    db: AsyncSession,
    event_id: str,
) -> list[OddsSnapshot]:
    subq = (
        select(
            OddsSnapshot.bookmaker,
            OddsSnapshot.market_type,
            OddsSnapshot.selection,
            func.max(OddsSnapshot.snapshot_time).label("max_time"),
        )
        .where(OddsSnapshot.event_id == event_id)
        .group_by(OddsSnapshot.bookmaker, OddsSnapshot.market_type, OddsSnapshot.selection)
        .subquery()
    )
    stmt = select(OddsSnapshot).join(
        subq,
        and_(
            OddsSnapshot.bookmaker == subq.c.bookmaker,
            OddsSnapshot.market_type == subq.c.market_type,
            OddsSnapshot.selection == subq.c.selection,
            OddsSnapshot.snapshot_time == subq.c.max_time,
            OddsSnapshot.event_id == event_id,
        ),
    )
    result = await db.execute(stmt)
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Betfair Snapshots
# ---------------------------------------------------------------------------

async def insert_betfair_snapshot(db: AsyncSession, data: dict) -> BetfairSnapshot:
    snap = BetfairSnapshot(**data)
    db.add(snap)
    await db.commit()
    await db.refresh(snap)
    return snap


async def insert_betfair_snapshots_bulk(db: AsyncSession, rows: list[dict]) -> None:
    """Insert many Betfair snapshots in a single commit (scraper writes dozens)."""
    if not rows:
        return
    db.add_all([BetfairSnapshot(**row) for row in rows])
    await db.commit()


async def get_latest_betfair_snapshot(
    db: AsyncSession,
    event_id: str,
    selection: str,
    side: str = "LAY",
) -> Optional[BetfairSnapshot]:
    result = await db.execute(
        select(BetfairSnapshot)
        .where(
            and_(
                BetfairSnapshot.event_id == event_id,
                BetfairSnapshot.selection_name == selection,
                BetfairSnapshot.side == side,
            )
        )
        .order_by(BetfairSnapshot.snapshot_time.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_latest_betfair_snapshots_for_event(
    db: AsyncSession,
    event_id: str,
    side: str = "LAY",
) -> list[BetfairSnapshot]:
    subq = (
        select(
            BetfairSnapshot.selection_name,
            func.max(BetfairSnapshot.snapshot_time).label("max_time"),
        )
        .where(
            and_(
                BetfairSnapshot.event_id == event_id,
                BetfairSnapshot.side == side,
            )
        )
        .group_by(BetfairSnapshot.selection_name)
        .subquery()
    )
    stmt = select(BetfairSnapshot).join(
        subq,
        and_(
            BetfairSnapshot.selection_name == subq.c.selection_name,
            BetfairSnapshot.snapshot_time == subq.c.max_time,
            BetfairSnapshot.event_id == event_id,
            BetfairSnapshot.side == side,
        ),
    )
    result = await db.execute(stmt)
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------

async def get_settled_bets(db: AsyncSession) -> list[TrackedBet]:
    result = await db.execute(
        select(TrackedBet)
        .options(selectinload(TrackedBet.closing_line))
        .where(TrackedBet.status.in_(["won", "lost", "void"]))
        .order_by(TrackedBet.updated_at.desc())
    )
    return result.scalars().all()
