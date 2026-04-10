import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.db import queries
from backend.services import betfair_client, odds_client
from backend.services.odds_client import parse_bookmaker_lines
from backend.services.cashout_signal import cashout_signal
from backend.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/bets", tags=["bets"])


class CreateBetRequest(BaseModel):
    event_id: str
    sport_key: str
    selection: str
    market_type: str
    line: Optional[float] = None
    side: str
    odds_taken: float
    stake: float
    bookmaker: str
    notes: Optional[str] = None

    @field_validator("market_type")
    @classmethod
    def valid_market_type(cls, v: str) -> str:
        if v not in ("h2h", "handicap", "totals"):
            raise ValueError("market_type must be h2h, handicap, or totals")
        return v

    @field_validator("odds_taken")
    @classmethod
    def odds_must_be_gt_one(cls, v: float) -> float:
        if v <= 1.0:
            raise ValueError("odds_taken must be greater than 1.0")
        return v

    @field_validator("stake")
    @classmethod
    def stake_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("stake must be positive")
        return v

    @model_validator(mode="after")
    def validate_market_fields(self) -> "CreateBetRequest":
        if self.market_type in ("handicap", "totals"):
            if self.line is None:
                raise ValueError("line is required for handicap and totals markets")
            if not self.side:
                raise ValueError("side is required for handicap and totals markets")
        if self.market_type == "totals" and self.side not in ("over", "under"):
            raise ValueError("side must be 'over' or 'under' for totals markets")
        if self.market_type == "handicap" and self.side not in ("home", "away"):
            raise ValueError("side must be 'home' or 'away' for handicap markets")
        return self


class ManualResultRequest(BaseModel):
    outcome: str

    @field_validator("outcome")
    @classmethod
    def valid_outcome(cls, v: str) -> str:
        if v not in ("won", "lost", "void"):
            raise ValueError("outcome must be won, lost, or void")
        return v


@router.get("")
async def list_bets(
    status: Optional[str] = Query(None),
    sport: Optional[str] = Query(None),
    bookmaker: Optional[str] = Query(None),
    market_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    bets = await queries.list_bets(
        db, status=status, sport=sport, bookmaker=bookmaker, market_type=market_type
    )
    return [_serialize_bet(b) for b in bets]


@router.post("", status_code=201)
async def create_bet(payload: CreateBetRequest, db: AsyncSession = Depends(get_db)):
    event = await queries.get_event(db, payload.event_id)
    if not event:
        raise HTTPException(
            status_code=404,
            detail=f"Event {payload.event_id} not found — fetch events first",
        )

    bet_data = {
        "event_id": payload.event_id,
        "sport_key": payload.sport_key,
        "event_name": f"{event.home_team} vs {event.away_team}",
        "commence_time": event.commence_time,
        "selection": payload.selection,
        "market_type": payload.market_type,
        "line": payload.line,
        "side": payload.side,
        "odds_taken": payload.odds_taken,
        "stake": payload.stake,
        "bookmaker": payload.bookmaker,
        "status": "open",
        "notes": payload.notes,
        "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
        "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
    }
    bet = await queries.create_bet(db, bet_data)

    # Immediately snapshot Betfair LAY — baseline for cashout edge erosion
    betfair_lay_at_bet: Optional[float] = None
    if settings.BETFAIR_ENABLED:
        try:
            betfair_lay_at_bet = await betfair_client.get_lay_price(
                payload.event_id, payload.selection
            )
            if betfair_lay_at_bet:
                await queries.insert_betfair_snapshot(
                    db,
                    {
                        "event_id": payload.event_id,
                        "market_id": None,
                        "selection_id": None,
                        "selection_name": payload.selection,
                        "market_type": payload.market_type,
                        "side": "LAY",
                        "price": betfair_lay_at_bet,
                        "size_available": None,
                        "snapshot_time": datetime.now(timezone.utc).replace(tzinfo=None),
                    },
                )
        except Exception as exc:
            logger.warning(
                "Failed to fetch Betfair LAY at bet creation for bet %d: %s", bet.id, exc
            )

    # Snapshot current Odds API line — stored as line_at_open for line CLV
    line_at_open: Optional[float] = payload.line
    if payload.market_type in ("handicap", "totals") and payload.line is None:
        try:
            bookmakers = await odds_client.get_odds(payload.event_id, payload.sport_key)
            snaps = parse_bookmaker_lines(bookmakers)
            market_key = "handicap" if payload.market_type == "handicap" else "totals"
            sel_lower = payload.selection.lower()
            for s in snaps:
                if s["market_type"] == market_key and s["selection"].lower() == sel_lower:
                    line_at_open = s.get("line")
                    break
        except Exception as exc:
            logger.warning("Failed to snapshot line_at_open for bet %d: %s", bet.id, exc)

    await queries.upsert_closing_line(
        db,
        bet.id,
        {
            "betfair_lay_at_bet": betfair_lay_at_bet,
            "betfair_lay_at_close": None,
            "odds_clv_pct": None,
            "beat_closing_odds": None,
            "line_at_open": line_at_open,
            "line_at_close": None,
            "line_clv_pts": None,
            "beat_closing_line": None,
            "captured_at": None,
            "capture_source": None,
        },
    )

    return _serialize_bet(await queries.get_bet(db, bet.id))


@router.get("/{bet_id}")
async def get_bet(bet_id: int, db: AsyncSession = Depends(get_db)):
    bet = await queries.get_bet(db, bet_id)
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")

    result = _serialize_bet(bet)

    if bet.status == "open":
        if (
            bet.closing_line
            and bet.closing_line.betfair_lay_at_bet
            and settings.BETFAIR_ENABLED
        ):
            current_lay = await betfair_client.get_lay_price(bet.event_id, bet.selection)
            if current_lay:
                result["cashout_signal"] = cashout_signal(
                    odds_taken=bet.odds_taken,
                    betfair_lay_at_bet=bet.closing_line.betfair_lay_at_bet,
                    current_betfair_lay=current_lay,
                    threshold=settings.CASHOUT_EDGE_THRESHOLD,
                )
            else:
                result["cashout_signal"] = {
                    "severity": "unavailable",
                    "recommend_cashout": False,
                }
        else:
            result["cashout_signal"] = {
                "severity": "unavailable",
                "recommend_cashout": False,
            }
    else:
        result["cashout_signal"] = None

    return result


@router.patch("/{bet_id}/result")
async def manual_result(
    bet_id: int,
    payload: ManualResultRequest,
    db: AsyncSession = Depends(get_db),
):
    bet = await queries.get_bet(db, bet_id)
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")
    if bet.status == "deleted":
        raise HTTPException(status_code=400, detail="Cannot update a deleted bet")

    await queries.update_bet_status(db, bet_id, payload.outcome, "manual")
    return {"id": bet_id, "status": payload.outcome, "settle_source": "manual"}


@router.delete("/{bet_id}")
async def delete_bet(bet_id: int, db: AsyncSession = Depends(get_db)):
    bet = await queries.get_bet(db, bet_id)
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")

    await queries.soft_delete_bet(db, bet_id)
    return {"id": bet_id, "status": "deleted"}


def _serialize_bet(bet) -> dict:
    cl = bet.closing_line
    return {
        "id": bet.id,
        "event_id": bet.event_id,
        "sport_key": bet.sport_key,
        "event_name": bet.event_name,
        "commence_time": bet.commence_time.isoformat() if bet.commence_time else None,
        "selection": bet.selection,
        "market_type": bet.market_type,
        "line": bet.line,
        "side": bet.side,
        "odds_taken": bet.odds_taken,
        "stake": bet.stake,
        "bookmaker": bet.bookmaker,
        "status": bet.status,
        "settle_source": bet.settle_source,
        "notes": bet.notes,
        "created_at": bet.created_at.isoformat() if bet.created_at else None,
        "updated_at": bet.updated_at.isoformat() if bet.updated_at else None,
        "pnl": _calc_pnl(bet),
        "closing_line": {
            "betfair_lay_at_bet": cl.betfair_lay_at_bet,
            "betfair_lay_at_close": cl.betfair_lay_at_close,
            "odds_clv_pct": cl.odds_clv_pct,
            "beat_closing_odds": cl.beat_closing_odds,
            "line_at_open": cl.line_at_open,
            "line_at_close": cl.line_at_close,
            "line_clv_pts": cl.line_clv_pts,
            "beat_closing_line": cl.beat_closing_line,
            "captured_at": cl.captured_at.isoformat() if cl.captured_at else None,
            "capture_source": cl.capture_source,
        }
        if cl
        else None,
    }


def _calc_pnl(bet) -> Optional[float]:
    if bet.status == "won":
        return round((bet.odds_taken - 1) * bet.stake, 2)
    elif bet.status == "lost":
        return round(-bet.stake, 2)
    elif bet.status == "void":
        return 0.0
    return None
